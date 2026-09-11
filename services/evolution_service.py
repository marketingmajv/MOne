"""
M-One Evolution API Service (services/evolution_service.py)
Gerencia instâncias autônomas de WhatsApp (criação, QR Code, status e webhooks).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from database import db

logger = logging.getLogger(__name__)


def get_evolution_config() -> Dict[str, str]:
    """Recupera a URL e Chave da Evolution API do ambiente ou banco de dados."""
    url = (os.environ.get("EVOLUTION_API_URL") or "").rstrip("/")
    key = (os.environ.get("EVOLUTION_API_KEY") or "").strip()

    if not url or not key:
        try:
            with db() as conn:
                row = conn.execute(
                    "SELECT access_token, settings_json FROM integrations WHERE service_name = 'evolution' LIMIT 1"
                ).fetchone()
                if row:
                    key = key or str(row.get("access_token") or "").strip()
                    settings = row.get("settings_json") or {}
                    if isinstance(settings, str):
                        try:
                            settings = json.loads(settings)
                        except Exception:
                            settings = {}
                    url = url or str(settings.get("api_url") or "").rstrip("/")
        except Exception as e:
            logger.debug("Falha ao buscar config Evolution no banco: %s", e)

    return {"api_url": url, "api_key": key}


def save_evolution_config(api_url: str, api_key: str) -> bool:
    """Salva a URL e chave da Evolution API no banco de dados."""
    try:
        clean_url = api_url.strip().rstrip("/")
        clean_key = api_key.strip()
        settings = json.dumps({"api_url": clean_url})
        with db() as conn:
            row = conn.execute(
                "SELECT id FROM integrations WHERE service_name = 'evolution' LIMIT 1"
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE integrations SET access_token=%s, settings_json=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                    (clean_key, settings, row["id"])
                )
            else:
                conn.execute(
                    "INSERT INTO integrations (service_name, access_token, settings_json) VALUES ('evolution', %s, %s)",
                    (clean_key, settings)
                )
            conn.commit()
        return True
    except Exception as e:
        logger.error("[Save Evolution Config Error]: %s", e)
        return False


def _api_request(endpoint: str, method: str = "GET", payload: Optional[dict] = None) -> Optional[dict]:
    """Executa requisição HTTP autenticada para a Evolution API."""
    cfg = get_evolution_config()
    api_url = cfg["api_url"]
    api_key = cfg["api_key"]

    if not api_url or not api_key:
        logger.warning("[Evolution API] URL ou API Key não configurada.")
        return None

    full_url = f"{api_url}/{endpoint.lstrip('/')}"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
        "User-Agent": "M-One-WhatsApp-Hub/1.0",
    }

    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")

    try:
        req = urllib.request.Request(full_url, data=data_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as he:
        body = he.read().decode("utf-8", errors="ignore")
        logger.warning("[Evolution API HTTP %d] %s: %s", he.code, full_url, body)
        try:
            return json.loads(body)
        except Exception:
            return {"error": body, "status": he.code}
    except Exception as e:
        logger.error("[Evolution API Request Error] %s: %s", full_url, e)
        return None


def create_or_get_instance(instance_name: str, webhook_target_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Cria uma nova instância para o vendedor ou recupera a existente,
    configurando automaticamente o webhook espelho.
    """
    clean_name = "".join(c for c in instance_name if c.isalnum() or c in ("-", "_")).lower()
    payload = {
        "instanceName": clean_name,
        "token": f"mone_inst_{clean_name}",
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
    }

    res = _api_request("/instance/create", method="POST", payload=payload)
    if not res:
        # Tenta obter status da existente
        return get_instance_connection(clean_name)

    # Configurar webhook se URL fornecida
    if webhook_target_url:
        set_instance_webhook(clean_name, webhook_target_url)

    # Extrair QR Code se presente
    qrcode_data = res.get("qrcode") or {}
    b64 = qrcode_data.get("base64") or res.get("base64")
    return {
        "success": True,
        "instance_name": clean_name,
        "qrcode": b64,
        "state": "connecting" if b64 else "open"
    }


def get_instance_connection(instance_name: str) -> Dict[str, Any]:
    """Obtém o estado de conexão e QR Code atual da instância."""
    clean_name = "".join(c for c in instance_name if c.isalnum() or c in ("-", "_")).lower()
    
    # Checar estado
    state_res = _api_request(f"/instance/connectionState/{clean_name}", method="GET")
    state = "close"
    if state_res:
        inst_info = state_res.get("instance") or {}
        state = inst_info.get("state") or state_res.get("state", "close")

    if state == "open":
        return {"success": True, "instance_name": clean_name, "state": "open", "qrcode": None}

    # Se não estiver aberta, requisitar novo QR Code
    connect_res = _api_request(f"/instance/connect/{clean_name}", method="GET")
    b64 = None
    if connect_res:
        b64 = connect_res.get("base64") or (connect_res.get("qrcode") or {}).get("base64")

    return {
        "success": True,
        "instance_name": clean_name,
        "state": state,
        "qrcode": b64
    }


def set_instance_webhook(instance_name: str, webhook_target_url: str) -> bool:
    """Configura a URL de webhook do M-One para a instância na Evolution API."""
    clean_name = "".join(c for c in instance_name if c.isalnum() or c in ("-", "_")).lower()
    payload = {
        "webhook": {
            "enabled": True,
            "url": webhook_target_url,
            "byEvents": False,
            "base64": True,
            "events": [
                "MESSAGES_UPSERT",
                "CONNECTION_UPDATE"
            ]
        }
    }
    res = _api_request(f"/webhook/set/{clean_name}", method="POST", payload=payload)
    return bool(res and not res.get("error"))


def logout_instance(instance_name: str) -> bool:
    """Desconecta a sessão do WhatsApp da instância."""
    clean_name = "".join(c for c in instance_name if c.isalnum() or c in ("-", "_")).lower()
    res = _api_request(f"/instance/logout/{clean_name}", method="DELETE")
    return bool(res and not res.get("error"))
