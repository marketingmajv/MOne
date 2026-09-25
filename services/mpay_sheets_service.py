"""
M-Pay Google Sheets Service (services/mpay_sheets_service.py)
Gerencia a integração e sincronização bidirecional entre o M-Pay e o Google Planilhas via Apps Script,
além de registrar logs de auditoria detalhados de cada alteração de dados.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any

from database import db

logger = logging.getLogger(__name__)


def get_mpay_setting(key: str, default: str = "") -> str:
    """Recupera uma configuração do M-Pay pelo banco de dados ou variável de ambiente."""
    env_val = os.environ.get(f"MPAY_{key.upper()}")
    if env_val:
        return env_val

    try:
        with db() as conn:
            row = conn.execute(
                "SELECT value FROM mpay_settings WHERE key = %s",
                [key],
            ).fetchone()
            if row and row.get("value") is not None:
                return str(row.get("value")).strip()
    except Exception as e:
        logger.warning(f"Erro ao buscar configuração {key}: {e}")

    return default


def set_mpay_setting(key: str, value: str) -> None:
    """Salva ou atualiza uma configuração do M-Pay no banco de dados."""
    with db() as conn:
        conn.execute(
            """
            INSERT INTO mpay_settings (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = NOW()
            """,
            [key, value.strip()],
        )


def log_mpay_audit(
    transaction_id: int | None,
    action: str,
    source: str,
    field_name: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    actor_name: str | None = None,
) -> None:
    """Registra uma entrada no histórico de alterações e auditoria do M-Pay."""
    try:
        s_old = str(old_value) if old_value is not None else None
        s_new = str(new_value) if new_value is not None else None
        with db() as conn:
            conn.execute(
                """
                INSERT INTO mpay_audit_logs
                (transaction_id, action, source, field_name, old_value, new_value, actor_name, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                [
                    transaction_id,
                    action,
                    source,
                    field_name,
                    s_old,
                    s_new,
                    actor_name or "Sistema",
                ],
            )
    except Exception as e:
        logger.error(f"Erro ao registrar auditoria M-Pay: {e}")


def sync_transaction_to_google_sheet(
    action: str,
    tx_data: dict[str, Any],
    actor_name: str = "M-Pay",
) -> dict[str, Any]:
    """
    Envia atualização para a planilha do Google Sheets via Webhook Apps Script.
    Action pode ser: 'create', 'update', 'delete'.
    """
    webhook_url = get_mpay_setting("google_sheets_webhook_url")
    if not webhook_url:
        return {"success": False, "message": "Webhook do Google Sheets não configurado."}

    pdate = tx_data.get("paid_at")
    if isinstance(pdate, (date, datetime)):
        formatted_date = pdate.strftime("%d/%m/%Y")
    else:
        formatted_date = str(pdate or "")

    payload = {
        "action": action,
        "source": "mpay",
        "actor": actor_name,
        "transaction": {
            "id": tx_data.get("id"),
            "paid_at": formatted_date,
            "beneficiary_name": tx_data.get("beneficiary_name") or "",
            "beneficiary_document": tx_data.get("beneficiary_document") or "",
            "amount": float(tx_data.get("amount") or 0.0),
            "bank_origin": tx_data.get("bank_origin") or "",
            "payment_method": tx_data.get("payment_method") or "",
            "category": tx_data.get("category") or "",
            "notes": tx_data.get("notes") or "",
            "confidence_status": tx_data.get("confidence_status") or "verified",
        },
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "M-Pay-Sheets-Sync/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(resp_body)
            except Exception:
                parsed = resp_body
            return {"success": True, "data": parsed}
    except Exception as e:
        logger.warning(f"Falha ao sincronizar com Google Sheets: {e}")
        return {"success": False, "error": str(e)}


def apply_google_sheets_update(payload: dict[str, Any]) -> tuple[bool, str]:
    """
    Processa uma atualização recebida do Google Sheets (gatilho onEdit ou batch).
    Evita loops infinitos garantindo a gravação com origem 'google_sheets'.
    """
    tx_id = payload.get("id") or payload.get("transaction_id")
    if not tx_id:
        return False, "ID da transação não fornecido."

    actor = payload.get("actor") or "Google Sheets User"
    allowed_fields = {
        "paid_at",
        "beneficiary_name",
        "beneficiary_document",
        "amount",
        "bank_origin",
        "payment_method",
        "category",
        "notes",
    }

    updates = {}
    for f in allowed_fields:
        if f in payload:
            updates[f] = payload[f]

    if not updates:
        return False, "Nenhum campo válido para atualização."

    with db() as conn:
        current = conn.execute(
            "SELECT * FROM mpay_transactions WHERE id = %s",
            [tx_id],
        ).fetchone()

        if not current:
            return False, f"Transação ID {tx_id} não encontrada no M-One."

        set_clauses = []
        params = []
        for k, new_val in updates.items():
            old_val = current.get(k)
            # Normalização de tipos
            if k == "amount":
                try:
                    cleaned = str(new_val).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
                    new_val = float(cleaned)
                except Exception:
                    continue
            elif k == "paid_at" and isinstance(new_val, str) and "/" in new_val:
                try:
                    parts = new_val.strip().split("/")
                    if len(parts) == 3:
                        new_val = f"{parts[2]}-{parts[1]}-{parts[0]}"
                except Exception:
                    pass

            set_clauses.append(f"{k} = %s")
            params.append(new_val)

            # Registrar log de auditoria
            log_mpay_audit(
                transaction_id=tx_id,
                action="updated",
                source="google_sheets",
                field_name=k,
                old_value=old_val,
                new_value=new_val,
                actor_name=actor,
            )

        if set_clauses:
            params.append(tx_id)
            conn.execute(
                f"""
                UPDATE mpay_transactions
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = %s
                """,
                params,
            )

    return True, "Atualização aplicada com sucesso."
