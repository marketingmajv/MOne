"""
M-Pay AI Receipt Scanner & Extractor (services/mpay_ai_service.py)
Motor de IA para leitura óptica e estruturação de comprovantes de pagamento (PDF e Imagens).
Extrai automaticamente: Data, Favorecido, Documento (CPF/CNPJ/Pix), Valor, Banco e Método.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any

from services.gemini_client import execute_gemini_payload
from services.pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)


def calculate_file_hash(content: bytes) -> str:
    """Gera hash MD5 do arquivo para prevenção de duplicidades."""
    return hashlib.md5(content).hexdigest()


def detect_file_mime(file_bytes: bytes, filename: str, mime_type: str | None = None) -> tuple[str, bool]:
    """Detecta o MIME type real e se é PDF inspecionando magic bytes do arquivo."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    
    # Inspecionar Magic Bytes nativos do arquivo
    if file_bytes.startswith(b"%PDF"):
        return "application/pdf", True
    if file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", False
    if file_bytes.startswith(b"\x89PNG"):
        return "image/png", False
    if file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]:
        return "image/webp", False
    if file_bytes.startswith(b"GIF8"):
        return "image/gif", False

    # Fallback por extensão
    if ext == "pdf":
        return "application/pdf", True
    if ext in ["jpg", "jpeg"]:
        return "image/jpeg", False
    if ext == "png":
        return "image/png", False
    if ext == "webp":
        return "image/webp", False
    if ext in ["heic", "heif"]:
        return "image/heic", False

    if mime_type and "image/" in mime_type:
        return mime_type, False

    return mime_type or "application/pdf", (mime_type == "application/pdf" or ext == "pdf")


def extract_receipt_data(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "application/pdf",
    default_paying_company: str = "M-one",
    default_payment_source: str = "Conta da Empresa",
) -> dict[str, Any]:
    """
    Processa um comprovante bancário, foto de recibo impresso/manuscrito ou nota via IA Gemini Multimodal.
    Retorna dicionário padronizado garantindo preenchimento de Data, Valor e Descrição.
    """
    real_mime, is_pdf = detect_file_mime(file_bytes, filename, mime_type)
    today_str = date.today().isoformat()
    
    extracted_text = ""
    if is_pdf:
        try:
            extracted_text = extract_text_from_pdf(file_bytes) or ""
        except Exception as err:
            logger.warning("[M-Pay AI] Falha ao extrair texto nativo do PDF %s: %s", filename, err)

    parts: list[dict[str, Any]] = []

    # Prompt especialista em comprovantes bancários, fotos de celular, recibos manuais e cupons fiscais
    prompt_text = f"""
Você é um auditor financeiro sênior especialista em leitura e auditoria de comprovantes de pagamento, recibos em papel, fotos de notas, recibos manuscritos, cupons fiscais e comprovantes de transferências (PIX, TED, Boletos, Cartões).
Analise com EXTREMA ATENÇÃO a foto do recibo/comprovante fornecido: "{filename}".

EXTRAIA COM MÁXIMA PRECISÃO TODOS OS DADOS VISÍVEIS EM FORMATO JSON:
1. "paid_at": Data do pagamento/recibo no formato "YYYY-MM-DD". Procure por datas impressas ou manuscritas no papel (Ex: "26/09/2026", "25/09/26", "25 de Setembro de 2026"). Se encontrar ano com 2 dígitos, converta para 4 dígitos (Ex: 2026). Se NÃO encontrar nenhuma data escrita no documento, retorne exatamente "{today_str}".
2. "paying_company": Empresa pagadora citada ("M-one", "Colvix", "Maj Antiga", "Maj Vitória", "Factor", "Groove"). Se não informada no papel, use exatamente "{default_paying_company}".
3. "payment_source": Forma de pagamento ("Conta da Empresa" para PIX/TED/banco ou "Dinheiro" para recibos em papel/espécie). Se for recibo em papel/manuscrito ou em dinheiro, use "Dinheiro". Senão use "{default_payment_source}".
4. "beneficiary_name": EMPRESA OU PESSOA QUE RECEBEU O DINHEIRO / Favorecido / Razão Social / Nome do Estabelecimento (Ex: "Posto Shell", "Oficina Mecânica Silva", "João da Silva", "Restaurante X", "Fornecedor Z").
5. "beneficiary_document": CPF, CNPJ ou Chave PIX do favorecido se houver.
6. "amount": Valor monetário TOTAL efetivamente pago/recebido em número decimal (Ex: 150.00, 48.50, 1250.00). Procure por "Total", "Valor", "R$", "Importância de R$", "Soma", "Valor Pago". Não retorne 0.00 se houver qualquer valor numérico visível.
7. "currency": "BRL" para Real.
8. "bank_origin": Nome do banco de origem (Ex: "Itaú", "Bradesco", "Banco do Brasil", "Nubank", "Banco Inter", etc.). Se for recibo físico em dinheiro, coloque "Dinheiro / Em Espécie".
9. "payment_method": "PIX", "TED", "BOLETO", "CARTAO", "DINHEIRO" ou "OUTRO".
10. "category": Categoria da despesa (Ex: "Operacional", "Alimentação", "Transporte / Frete", "Manutenção", "Serviços", "Suprimentos", "Geral").
11. "notes": DISCRIMINAÇÃO DO TIPO DE PRODUTO OU SERVIÇO PAGO / Motivo do recibo (Ex: "Compra de 2 pneus e alinhamento", "Refeição de trabalho", "Combustível Óleo Diesel", "Serviço de Frete e Entrega", "Material de Escritório", "Autenticação N° 123456"). Descreva o produto ou serviço com o máximo de detalhes possível a partir da foto!

RESPOSTA OBRIGATÓRIA:
Retorne ESTRITAMENTE um objeto JSON válido no seguinte formato, sem texto antes ou depois:
{{
  "paid_at": "{today_str}",
  "paying_company": "{default_paying_company}",
  "payment_source": "{default_payment_source}",
  "beneficiary_name": "Nome da Empresa que Recebeu",
  "beneficiary_document": "CPF/CNPJ/Pix",
  "amount": 0.00,
  "currency": "BRL",
  "bank_origin": "Banco de Origem / Dinheiro",
  "payment_method": "DINHEIRO",
  "category": "Geral",
  "notes": "Discriminação detalhada do produto ou serviço pago"
}}
"""

    # Se tiver texto nativo relevante extraído do PDF (> 50 caracteres)
    if len(extracted_text.strip()) > 50:
        parts.append({"text": f"{prompt_text}\n\n--- TEXTO NATIVO EXTRAÍDO DO COMPROVANTE ---\n{extracted_text[:14000]}"})
    else:
        # Modo multimodal para fotos de celular e imagens
        b64_content = base64.b64encode(file_bytes).decode("utf-8")
        parts.append({"text": prompt_text})
        parts.append({
            "inlineData": {
                "mimeType": real_mime,
                "data": b64_content,
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        response_json = execute_gemini_payload(payload, timeout=35)
        if not response_json or not response_json.get("success"):
            err_msg = response_json.get("message") if response_json else "IA indisponível"
            return fallback_receipt(
                filename,
                default_paying_company,
                default_payment_source,
                error_reason=err_msg,
                raw_text=extracted_text,
            )

        data = response_json.get("data")
        if not data and response_json.get("text"):
            raw_text = response_json["text"].strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            try:
                data = json.loads(raw_text.strip())
            except Exception:
                data = None

        if not data:
            return fallback_receipt(
                filename,
                default_paying_company,
                default_payment_source,
                error_reason="Formato de resposta inválido da IA",
                raw_text=extracted_text,
            )

        # Garantir preenchimento dos campos essenciais se nulos/vazios
        if not data.get("paid_at") or str(data.get("paid_at")).strip() in ["null", "", "None"]:
            data["paid_at"] = today_str

        if not data.get("paying_company"):
            data["paying_company"] = default_paying_company
        if not data.get("payment_source"):
            data["payment_source"] = default_payment_source

        if not data.get("notes") or not str(data.get("notes")).strip():
            b_name = data.get("beneficiary_name") or "Favorecido"
            cat = data.get("category") or "Despesa"
            data["notes"] = f"{cat} - {b_name} (Recibo {filename})"

        # Avaliar grau de confiança na extração
        has_amount = float(data.get("amount") or 0) > 0
        has_dest = bool(data.get("beneficiary_name") and str(data.get("beneficiary_name")).strip())
        has_date = bool(data.get("paid_at") and str(data.get("paid_at")).strip())

        if has_amount and has_dest and has_date:
            confidence = "verified"
        elif has_amount or has_dest:
            confidence = "partial"
        else:
            confidence = "manual"

        data["confidence_status"] = confidence
        return data

    except Exception as err:
        err_msg = str(err)
        logger.error("[M-Pay AI] Erro ao interpretar comprovante %s com Gemini: %s", filename, err_msg)
        reason = "IA indisponível no momento"
        if "429" in err_msg or "ResourceExhausted" in err_msg:
            reason = "Limite de requisições temporário da IA"
        elif "timeout" in err_msg.lower():
            reason = "Tempo limite da IA excedido"
        elif "API_KEY" in err_msg or "api key" in err_msg.lower():
            reason = "Chave da API da IA não configurada"
        return fallback_receipt(filename, default_paying_company, default_payment_source, error_reason=reason, raw_text=extracted_text)


def fallback_receipt(
    filename: str,
    default_paying_company: str = "M-one",
    default_payment_source: str = "Conta da Empresa",
    error_reason: str | None = None,
    raw_text: str = "",
) -> dict[str, Any]:
    """Retorno de contingência com extração local por padrões caso a IA esteja temporariamente sobrecarregada."""
    import re

    today_str = date.today().isoformat()
    note_txt = f"Recibo: {filename}"
    if error_reason:
        note_txt += f" ({error_reason} - preencher dados)"

    res = {
        "paid_at": today_str,
        "paying_company": default_paying_company,
        "payment_source": default_payment_source,
        "beneficiary_name": "Novo Favorecido",
        "beneficiary_document": "",
        "amount": 0.00,
        "currency": "BRL",
        "bank_origin": "Dinheiro / Banco",
        "payment_method": "OUTRO",
        "category": "Geral",
        "notes": note_txt,
        "confidence_status": "manual",
        "ai_error": bool(error_reason),
    }

    # Se houver texto extraído do documento, aplica regex local de alta precisão
    if raw_text and len(raw_text.strip()) > 10:
        # 1. Valor monetário
        amt_match = re.search(r"R\$\s*([0-9\.,]+)", raw_text)
        if amt_match:
            res["amount"] = clean_amount(amt_match.group(1))

        # 2. Data
        date_match = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", raw_text)
        if date_match:
            res["paid_at"] = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"

        # 3. Documento CPF/CNPJ
        doc_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})", raw_text)
        if doc_match:
            res["beneficiary_document"] = doc_match.group(1)

        # 4. Favorecido / Destino
        ben_match = re.search(r"(?:Favorecido|Destino|Recebedor)[\s/:]*\n\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        if ben_match:
            candidate = ben_match.group(1).strip()
            if len(candidate) > 2 and not candidate.startswith("R$"):
                res["beneficiary_name"] = candidate

        # 5. Banco de Origem
        for b_name in ["Banco Inter", "Inter", "Itaú", "Bradesco", "Nubank", "Banco do Brasil", "Santander", "Caixa"]:
            if b_name.lower() in raw_text.lower():
                res["bank_origin"] = b_name
                break

        # 6. Método
        if "pix" in raw_text.lower():
            res["payment_method"] = "PIX"

        # 7. Descrição / Observações
        notes_match = re.search(r"(?:Observações|Descrição|Histórico)[\s/:]*\n\s*([^\n\r]+)", raw_text, re.IGNORECASE)
        if notes_match:
            res["notes"] = notes_match.group(1).strip()

        if res["amount"] > 0:
            res["confidence_status"] = "partial" if res["beneficiary_name"] == "Novo Favorecido" else "verified"
            res["ai_error"] = False

    return res


def clean_amount(val: Any) -> float:
    """
    Converte com segurança valores monetários (BRL ou US) para float.
    Trata separadores de milhar e vírgula decimal (ex: '1.250,50' -> 1250.50).
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).replace("R$", "").replace("$", "").replace(" ", "").strip()
    if not s:
        return 0.0

    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            s = s.replace(".", "")
        elif len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            s = s.replace(".", "")

    try:
        return float(s)
    except Exception:
        return 0.0

