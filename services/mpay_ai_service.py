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
from decimal import Decimal
from typing import Any

from services.gemini_client import execute_gemini_payload
from services.pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)


def calculate_file_hash(content: bytes) -> str:
    """Gera hash MD5 do arquivo para prevenção de duplicidades."""
    return hashlib.md5(content).hexdigest()


def extract_receipt_data(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "application/pdf",
    default_paying_company: str = "M-one",
    default_payment_source: str = "Conta da Empresa",
) -> dict[str, Any]:
    """
    Processa um comprovante bancário ou recibo via IA multimodal / OCR.
    Retorna dicionário padronizado com campos para preenchimento da planilha M-Pay.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    is_pdf = mime_type == "application/pdf" or ext == "pdf"
    
    extracted_text = ""
    if is_pdf:
        try:
            extracted_text = extract_text_from_pdf(file_bytes) or ""
        except Exception as err:
            logger.warning("[M-Pay AI] Falha ao extrair texto nativo do PDF %s: %s", filename, err)

    parts: list[dict[str, Any]] = []

    # Prompt especialista em comprovantes bancários brasileiros e internacionais
    prompt_text = f"""
Você é um auditor financeiro especialista em conferência de comprovantes de pagamento e transferências bancárias.
Analise detalhadamente o comprovante de pagamento fornecido: "{filename}".

EXTRAIA COM RIGOR OS SEGUINTES CAMPOS EM FORMATO JSON:
- "paid_at": Data do pagamento/débito no formato "YYYY-MM-DD" (Ex: "2026-09-25"). Se encontrar apenas dia e mês com ano abreviado, ajuste para ano completo de 4 dígitos. Se não encontrar, retorne null.
- "paying_company": Empresa pagadora identificada no documento se explicitamente citada ("M-one", "Colvix", "Maj Antiga", "Maj Vitória", "Factor", "Groove"). Se não for claramente mencionada, use exatamente "{default_paying_company}".
- "payment_source": Origem/forma do pagamento ("Conta da Empresa" para conta bancária/PIX/TED/boleto ou "Dinheiro" para recibo em espécie/papel). Se não identificada, use "{default_payment_source}".
- "beneficiary_name": Nome completo ou Razão Social do FAVORECIDO / DESTINATÁRIO / QUEM RECEBEU O PAGAMENTO (Ex: "COLVIX TRADING IMPORT LTDA", "João da Silva", "Enel SP", etc.). Nunca coloque o nome do pagador aqui!
- "beneficiary_document": CPF, CNPJ ou Chave PIX do favorecido (limpe caracteres especiais opcionais se quiser, ou mantenha legível). Se não informado, retorne null.
- "amount": Valor monetário efetivamente pago/debitado em número decimal (Ex: 1250.50, 48499.00). Não inclua símbolo de moeda. Se não encontrar, retorne 0.00.
- "currency": "BRL" para Real ou "USD" / "EUR" se for internacional. Padrão: "BRL".
- "bank_origin": Nome da instituição financeira ou banco por onde foi feito o pagamento (Ex: "Itaú", "Bradesco", "Banco do Brasil", "Santander", "Nubank", "Banco BS2", "Banco Inter", "C6 Bank", "Sicoob", "Sicredi", etc.).
- "payment_method": Tipo do pagamento: "PIX", "TED", "DOC", "BOLETO", "CARTAO", "SWIFT", "DEBITO_AUTOMATICO" ou "OUTRO".
- "category": Categoria sugerida de despesa (Ex: "Fornecedor", "Impostos / Tributos", "Frete / Logística", "Serviços", "Operacional", "Aluguel", "Geral").
- "notes": Código de autenticação bancária, ID da transação PIX (E2E), protocolo ou observação relevante do comprovante.

RESPOSTA OBRIGATÓRIA:
Retorne ESTRITAMENTE um objeto JSON válido no seguinte formato, sem texto antes ou depois:
{{
  "paid_at": "YYYY-MM-DD",
  "paying_company": "{default_paying_company}",
  "payment_source": "{default_payment_source}",
  "beneficiary_name": "Nome do Favorecido",
  "beneficiary_document": "CPF/CNPJ/Chave Pix",
  "amount": 0.00,
  "currency": "BRL",
  "bank_origin": "Nome do Banco",
  "payment_method": "PIX",
  "category": "Geral",
  "notes": "Autenticação / Protocolo"
}}
"""

    # Se tiver texto nativo relevante extraído do PDF (> 50 caracteres)
    if len(extracted_text.strip()) > 50:
        parts.append({"text": f"{prompt_text}\n\n--- TEXTO NATIVO EXTRAÍDO DO COMPROVANTE ---\n{extracted_text[:14000]}"})
    else:
        # Modo multimodal: envia o arquivo (PDF ou imagem) em base64
        inline_mime = mime_type
        if is_pdf:
            inline_mime = "application/pdf"
        elif ext in ["jpg", "jpeg"]:
            inline_mime = "image/jpeg"
        elif ext == "png":
            inline_mime = "image/png"
        elif ext == "webp":
            inline_mime = "image/webp"

        b64_content = base64.b64encode(file_bytes).decode("utf-8")
        parts.append({"text": prompt_text})
        parts.append({
            "inlineData": {
                "mimeType": inline_mime,
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
        response_json = execute_gemini_payload(payload, timeout=40)
        candidates = response_json.get("candidates", [])
        if not candidates:
            return fallback_receipt(filename, default_paying_company, default_payment_source)

        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        raw_text = raw_text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        data = json.loads(raw_text.strip())

        # Garantir que empresa pagadora e origem do pagamento estejam presentes
        if not data.get("paying_company"):
            data["paying_company"] = default_paying_company
        if not data.get("payment_source"):
            data["payment_source"] = default_payment_source

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
        logger.error("[M-Pay AI] Erro ao interpretar comprovante %s com Gemini: %s", filename, err)
        return fallback_receipt(filename, default_paying_company, default_payment_source)


def fallback_receipt(
    filename: str,
    default_paying_company: str = "M-one",
    default_payment_source: str = "Conta da Empresa",
) -> dict[str, Any]:
    """Retorno padrão caso a IA falhe ou o arquivo não seja legível, permitindo preenchimento manual."""
    return {
        "paid_at": None,
        "paying_company": default_paying_company,
        "payment_source": default_payment_source,
        "beneficiary_name": "",
        "beneficiary_document": "",
        "amount": 0.00,
        "currency": "BRL",
        "bank_origin": "",
        "payment_method": "OUTRO",
        "category": "Geral",
        "notes": f"Preenchimento manual (arquivo: {filename})",
        "confidence_status": "manual",
    }
