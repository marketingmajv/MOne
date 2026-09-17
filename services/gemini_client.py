"""
M-One Resilient Gemini API Client (services/gemini_client.py)
Cliente resiliente para a Google Generative Language API com failover automático
entre modelos (Flash / Flash-Lite / 3-Flash), retry com backoff exponencial e mensagens amigáveis.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_gemini_api_key() -> str:
    """Obtém a chave da API do Gemini do ambiente ou da tabela integrations no Supabase."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        try:
            from database import db
            with db() as conn:
                row = conn.execute("SELECT access_token FROM integrations WHERE service_name = 'gemini'").fetchone()
                if row and row.get("access_token"):
                    key = row["access_token"].strip()
        except Exception:
            pass
    return key or DEFAULT_GEMINI_KEY


def get_candidate_models() -> list[str]:
    """Retorna a lista ordenada de modelos candidatos para failover automático."""
    primary = os.environ.get("GEMINI_MODEL", "gemini-flash-latest").strip() or "gemini-flash-latest"
    # Ordem prioritária de resiliência:
    # 1. Modelo principal configurado
    # 2. Flash-Lite (altíssima disponibilidade e baixa latência contra picos de 503)
    # 3. Gemini 3 Flash Preview (segundo nó de redundância)
    preferred = [primary, "gemini-flash-lite-latest", "gemini-3-flash-preview"]
    seen = set()
    result = []
    for m in preferred:
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


def execute_gemini_payload(
    payload: dict[str, Any],
    api_key: str | None = None,
    timeout: int = 35,
    max_retries_per_model: int = 2,
    custom_models: list[str] | None = None,
) -> dict[str, Any]:
    """Envia requisição para a API do Gemini com cascata de modelos e retentativas automáticas.

    Returns:
        dict contendo:
          success: bool
          text: str (conteúdo retornado)
          data: dict (se o retorno for JSON estruturado)
          model_used: str
          error_type: str (opcional em caso de erro)
          message: str
    """
    key = api_key or get_gemini_api_key()
    if not key:
        return {
            "success": False,
            "error_type": "MISSING_KEY",
            "message": "Chave da API do Google Gemini (GEMINI_API_KEY) não configurada no servidor.",
        }

    candidate_models = custom_models or get_candidate_models()
    last_error: Exception | None = None
    last_status_code: int | None = None
    last_err_detail: str = ""

    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        encoded_body = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries_per_model):
            try:
                req = urllib.request.Request(
                    url,
                    data=encoded_body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    candidates = res_data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        raw_text = "".join([p.get("text", "") for p in parts]).strip()
                        parsed_json = None
                        try:
                            parsed_json = json.loads(raw_text)
                        except Exception:
                            pass

                        return {
                            "success": True,
                            "text": raw_text,
                            "data": parsed_json,
                            "model_used": model_name,
                            "raw": res_data,
                        }

                    return {
                        "success": False,
                        "error_type": "EMPTY_RESPONSE",
                        "message": "O modelo Gemini processou a requisição mas não retornou conteúdo textual.",
                    }

            except urllib.error.HTTPError as http_err:
                last_error = http_err
                last_status_code = http_err.code
                raw_err = http_err.read().decode("utf-8", errors="ignore")
                try:
                    err_json = json.loads(raw_err)
                    last_err_detail = err_json.get("error", {}).get("message", raw_err)
                except Exception:
                    last_err_detail = raw_err

                # Se a chave for comprovadamente inválida, interrompe imediatamente
                if http_err.code == 400 and "API_KEY_INVALID" in last_err_detail:
                    return {
                        "success": False,
                        "error_type": "INVALID_KEY",
                        "message": "A chave GEMINI_API_KEY configurada é inválida ou expirou.",
                    }

                # Erros transitórios de sobrecarga do Google (503, 429, 500, 502, 504)
                if http_err.code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Gemini API %s retornou HTTP %d (tentativa %d/%d). Acionando backoff/failover...",
                        model_name,
                        http_err.code,
                        attempt + 1,
                        max_retries_per_model,
                    )
                    time.sleep(1.2 * (attempt + 1))
                    continue

                # Outro erro HTTP 4xx não transitório: tenta o próximo modelo
                logger.warning("Gemini API %s retornou HTTP %d: %s", model_name, http_err.code, last_err_detail)
                break

            except Exception as ex:
                last_error = ex
                logger.warning(
                    "Erro de conexão com %s (tentativa %d/%d): %s",
                    model_name,
                    attempt + 1,
                    max_retries_per_model,
                    ex,
                )
                time.sleep(1.0 * (attempt + 1))
                continue

    # Se todos os modelos e retentativas esgotaram
    if last_status_code in (503, 502, 504):
        friendly_msg = (
            "Os servidores do Google Gemini estão temporariamente com alta demanda de processamento (503 Service Unavailable). "
            "Realizamos o failover automático entre múltiplos modelos sem sucesso no momento. "
            "Por favor, tente novamente em alguns segundos ou preencha os dados manualmente."
        )
    elif last_status_code == 429:
        friendly_msg = (
            "Limite de requisições por minuto atingido na API do Google Gemini (429 Too Many Requests). "
            "Aguarde cerca de 30 segundos e tente novamente."
        )
    else:
        err_str = f" ({last_status_code}): {last_err_detail}" if last_status_code else f": {last_error}"
        friendly_msg = f"Falha na comunicação com os servidores do Google Gemini{err_str}"

    return {
        "success": False,
        "error_type": "FAILOVER_EXHAUSTED",
        "message": friendly_msg,
        "last_status_code": last_status_code,
    }
