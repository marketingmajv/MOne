"""
M-Pay Service Layer (services/mpay_service.py)
Gerencia o fluxo de pré-visualização/análise por IA e confirmação de comprovantes.
Mantém o routes/mpay_routes.py limpo e modular (< 500 linhas).
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from database import db
from services.mpay_ai_service import calculate_file_hash, clean_amount, detect_file_mime, extract_receipt_data
from services.mpay_sheets_service import (
    archive_receipt_to_local_gdrive,
    log_mpay_audit,
    sync_transaction_to_google_sheet,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("VERCEL"):
    MPAY_UPLOAD_DIR = Path("/tmp/uploads/mpay")
else:
    MPAY_UPLOAD_DIR = BASE_DIR / "uploads" / "mpay"
MPAY_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def analyze_receipt_for_modal(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "application/pdf",
) -> dict[str, Any]:
    """
    Executa a análise do comprovante via IA Gemini sem salvar no banco de dados.
    Retorna os dados extraídos, sugestão inteligente de Empresa e Forma, e pré-visualização Base64.
    """
    real_mime, is_pdf = detect_file_mime(file_bytes, filename, mime_type)
    file_hash = calculate_file_hash(file_bytes)

    extracted = extract_receipt_data(
        file_bytes=file_bytes,
        filename=filename,
        mime_type=real_mime,
        default_paying_company="M-one",
        default_payment_source="Conta da Empresa",
    )

    b64_content = base64.b64encode(file_bytes).decode("utf-8")
    preview_url = f"data:{real_mime};base64,{b64_content}"

    return {
        "success": True,
        "filename": filename,
        "file_hash": file_hash,
        "mime_type": real_mime,
        "is_pdf": is_pdf,
        "file_base64": b64_content,
        "preview_url": preview_url,
        "extracted": {
            "paid_at": extracted.get("paid_at") or date.today().isoformat(),
            "paying_company": (extracted.get("paying_company") or "M-one").strip(),
            "payment_source": (extracted.get("payment_source") or "Conta da Empresa").strip(),
            "beneficiary_name": (extracted.get("beneficiary_name") or "").strip(),
            "beneficiary_document": (extracted.get("beneficiary_document") or "").strip(),
            "amount": float(extracted.get("amount") or 0.0),
            "bank_origin": (extracted.get("bank_origin") or "").strip(),
            "payment_method": (extracted.get("payment_method") or "PIX").strip().upper(),
            "category": (extracted.get("category") or "Geral").strip(),
            "notes": (extracted.get("notes") or "").strip(),
            "confidence_status": extracted.get("confidence_status", "verified"),
        },
    }


def confirm_and_save_transaction(
    payload: dict[str, Any],
    user_id: int | None,
    actor_name: str = "Usuário",
) -> dict[str, Any]:
    """
    Persiste definitivamente a transação no banco de dados Supabase,
    grava o arquivo, arquiva no Google Drive e dispara a sincronização para o Google Sheets.
    """
    orig_filename = (payload.get("orig_filename") or payload.get("filename") or "comprovante.pdf").strip()
    file_base64 = payload.get("file_base64") or ""
    mime_type = payload.get("mime_type") or "application/pdf"
    file_hash = payload.get("file_hash") or ""

    file_bytes = b""
    if file_base64:
        try:
            file_bytes = base64.b64decode(file_base64)
            if not file_hash:
                file_hash = calculate_file_hash(file_bytes)
        except Exception as e:
            logger.warning("[M-Pay] Falha ao decodificar Base64: %s", e)

    unique_filename = f"mpay_{file_hash[:10]}_{orig_filename}" if file_hash else f"mpay_{orig_filename}"
    if file_bytes:
        try:
            (MPAY_UPLOAD_DIR / unique_filename).write_bytes(file_bytes)
        except Exception as d_err:
            logger.warning("[M-Pay] Falha ao gravar em disco: %s", d_err)

    paid_at = payload.get("paid_at") or None
    paying_company = (payload.get("paying_company") or "M-one").strip()
    payment_source = (payload.get("payment_source") or "Conta da Empresa").strip()
    beneficiary = (payload.get("beneficiary_name") or "Favorecido").strip()
    doc_num = (payload.get("beneficiary_document") or "").strip()
    amt = clean_amount(payload.get("amount") or 0.0)
    bank = (payload.get("bank_origin") or "").strip()
    method = (payload.get("payment_method") or "PIX").strip().upper()
    category = (payload.get("category") or "Geral").strip()
    notes = (payload.get("notes") or "").strip()
    conf_status = payload.get("confidence_status") or "verified"
    file_url_rel = f"mpay/{unique_filename}"

    raw_extracted = {
        "paid_at": paid_at,
        "paying_company": paying_company,
        "payment_source": payment_source,
        "beneficiary_name": beneficiary,
        "beneficiary_document": doc_num,
        "amount": amt,
        "bank_origin": bank,
        "payment_method": method,
        "category": category,
        "notes": notes,
        "confidence_status": conf_status,
        "orig_filename": orig_filename,
        "mime_type": mime_type,
        "file_base64": file_base64,
    }

    with db() as conn:
        row = conn.execute(
            """INSERT INTO mpay_transactions (
                paid_at, paying_company, payment_source, beneficiary_name, beneficiary_document, amount,
                bank_origin, payment_method, category, notes, file_url, orig_filename, file_hash, confidence_status, raw_extracted_data, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, paid_at, paying_company, payment_source, beneficiary_name, beneficiary_document, amount, bank_origin, payment_method, category, notes, confidence_status""",
            (
                paid_at,
                paying_company,
                payment_source,
                beneficiary,
                doc_num,
                amt,
                bank,
                method,
                category,
                notes,
                file_url_rel,
                orig_filename,
                file_hash,
                conf_status,
                json.dumps(raw_extracted),
                user_id,
            ),
        ).fetchone()

    if not row:
        raise RuntimeError("Erro ao inserir transação no banco de dados.")

    r_dict = dict(row)
    log_mpay_audit(row["id"], "created", "mpay_modal_confirm", actor_name=actor_name)

    if file_bytes:
        archive_receipt_to_local_gdrive(file_bytes, orig_filename, company=paying_company)
        sync_transaction_to_google_sheet(
            "create",
            r_dict,
            actor_name=actor_name,
            file_bytes=file_bytes,
            filename=orig_filename,
            mime_type=mime_type,
        )
    else:
        sync_transaction_to_google_sheet("create", r_dict, actor_name=actor_name)

    return r_dict
