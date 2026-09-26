"""
M-Pay Controller & Routes (routes/mpay_routes.py)
Módulo independente do M-Pay para recebimento de comprovantes (PDF/Imagens/Câmera),
leitura com IA Gemini, preenchimento de grade interativa em tempo real e exportação XLSX/CSV.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from database import db
from routes.helpers import audit, current_user, login_required
from services.mpay_ai_service import calculate_file_hash, extract_receipt_data
from services.mpay_export_service import export_mpay_dataset
from services.mpay_sheets_service import (
    apply_google_sheets_update,
    get_mpay_setting,
    log_mpay_audit,
    set_mpay_setting,
    sync_transaction_to_google_sheet,
)

logger = logging.getLogger(__name__)

mpay_bp = Blueprint("mpay", __name__, url_prefix="/m-pay")

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("VERCEL"):
    MPAY_UPLOAD_DIR = Path("/tmp/uploads/mpay")
else:
    MPAY_UPLOAD_DIR = BASE_DIR / "uploads" / "mpay"
MPAY_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def check_mpay_access(user: dict[str, Any] | None) -> bool:
    """Verifica se o usuário tem permissão para acessar o M-Pay (Diretoria, Financeiro, Suporte ou permissão concedida)."""
    if not user:
        return False
    role = user.get("role")
    if role in ("admin", "finance", "support"):
        return True
    custom_perms = user.get("custom_permissions") or {}
    return bool(custom_perms.get("can_access_mpay"))


@mpay_bp.route("", methods=["GET"])
@login_required
def index():
    """Painel Principal do M-Pay: visualizador de comprovantes superior e grade interativa inferior."""
    me = current_user()
    if not check_mpay_access(me):
        flash("Acesso não autorizado ao módulo M-Pay. Solicite permissão à Diretoria.", "error")
        return redirect(url_for("dashboard.dashboard"))

    # Filtros opcionais
    month_filter = request.args.get("month", "").strip()  # Formato YYYY-MM
    search_q = request.args.get("q", "").strip()

    sql_where = []
    params: list[Any] = []

    if month_filter:
        sql_where.append("TO_CHAR(paid_at, 'YYYY-MM') = %s")
        params.append(month_filter)

    if search_q:
        sql_where.append("(beneficiary_name ILIKE %s OR notes ILIKE %s OR bank_origin ILIKE %s OR beneficiary_document ILIKE %s OR paying_company ILIKE %s OR payment_source ILIKE %s)")
        like_term = f"%{search_q}%"
        params.extend([like_term, like_term, like_term, like_term, like_term, like_term])

    where_clause = f"WHERE {' AND '.join(sql_where)}" if sql_where else ""

    with db() as conn:
        transactions = conn.execute(
            f"""
            SELECT t.*, u.name as created_by_name
            FROM mpay_transactions t
            LEFT JOIN users u ON u.id = t.created_by
            {where_clause}
            ORDER BY t.paid_at DESC NULLS LAST, t.id DESC
            LIMIT 500
            """,
            params,
        ).fetchall()

        # Métricas rápidas
        stats = conn.execute(
            """
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(*) FILTER (WHERE confidence_status = 'verified') as verified_count,
                COUNT(*) FILTER (WHERE confidence_status = 'partial') as partial_count,
                COUNT(*) FILTER (WHERE confidence_status = 'manual') as manual_count
            FROM mpay_transactions
            """
        ).fetchone()

        # Meses disponíveis para filtro
        available_months = conn.execute(
            """
            SELECT DISTINCT TO_CHAR(paid_at, 'YYYY-MM') as month_str
            FROM mpay_transactions
            WHERE paid_at IS NOT NULL
            ORDER BY month_str DESC
            """
        ).fetchall()

    sheets_webhook_url = get_mpay_setting("google_sheets_webhook_url")

    return render_template(
        "mpay.html",
        me=me,
        transactions=[dict(t) for t in transactions],
        stats=dict(stats) if stats else {},
        available_months=[m["month_str"] for m in available_months if m.get("month_str")],
        current_month_filter=month_filter,
        search_q=search_q,
        sheets_webhook_url=sheets_webhook_url,
        hide_sidebar=True,
    )


@mpay_bp.route("/upload", methods=["POST"])
@login_required
def upload_receipts():
    """Recebe arquivos múltiplos ou fotos diretas de comprovantes e os processa com IA."""
    me = current_user()
    if not check_mpay_access(me):
        return jsonify({"success": False, "message": "Acesso não autorizado."}), 403

    files = request.files.getlist("receipts")
    if not files or all(not f or not f.filename for f in files):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "message": "Nenhum arquivo enviado."}), 400
        flash("Nenhum arquivo foi selecionado.", "error")
        return redirect(url_for("mpay.index"))

    # Empresa pagadora e origem de pagamento selecionadas na UI
    default_company = (request.form.get("paying_company") or request.args.get("paying_company") or "M-one").strip()
    default_source = (request.form.get("payment_source") or request.args.get("payment_source") or "Conta da Empresa").strip()

    user_id = me.get("id") if me else None
    imported_items = []

    with db() as conn:
        for f in files:
            if not f or not f.filename:
                continue

            orig_filename = secure_filename(f.filename)
            file_bytes = f.read()
            if not file_bytes:
                continue

            file_hash = calculate_file_hash(file_bytes)
            unique_filename = f"mpay_{file_hash[:10]}_{orig_filename}"
            save_path = MPAY_UPLOAD_DIR / unique_filename
            save_path.write_bytes(file_bytes)

            mime = f.content_type or "application/pdf"
            extracted = extract_receipt_data(
                file_bytes=file_bytes,
                filename=orig_filename,
                mime_type=mime,
                default_paying_company=default_company,
                default_payment_source=default_source,
            )

            paid_at = extracted.get("paid_at") or None
            paying_company = (extracted.get("paying_company") or default_company).strip()
            payment_source = (extracted.get("payment_source") or default_source).strip()
            beneficiary = (extracted.get("beneficiary_name") or "").strip()
            doc_num = (extracted.get("beneficiary_document") or "").strip()
            amt = float(extracted.get("amount") or 0.0)
            bank = (extracted.get("bank_origin") or "").strip()
            method = (extracted.get("payment_method") or "PIX").strip().upper()
            category = (extracted.get("category") or "Geral").strip()
            notes = (extracted.get("notes") or "").strip()
            conf_status = extracted.get("confidence_status", "manual")

            file_url_rel = f"mpay/{unique_filename}"

            row = conn.execute(
                """
                INSERT INTO mpay_transactions (
                    paid_at, paying_company, payment_source, beneficiary_name, beneficiary_document, amount,
                    bank_origin, payment_method, category, notes,
                    file_url, orig_filename, file_hash, confidence_status,
                    raw_extracted_data, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, paid_at, paying_company, payment_source, beneficiary_name, beneficiary_document, amount, bank_origin, payment_method, category, notes, confidence_status
                """,
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
                    json.dumps(extracted),
                    user_id,
                ),
            ).fetchone()

            if row:
                r_dict = dict(row)
                actor = me.get("name") if me else "Sistema IA"
                log_mpay_audit(row["id"], "created", "mpay_ai", actor_name=actor)
                sync_transaction_to_google_sheet("create", r_dict, actor_name=actor)
                imported_items.append({
                    "id": row["id"],
                    "filename": orig_filename,
                    "paying_company": paying_company,
                    "payment_source": payment_source,
                    "beneficiary_name": beneficiary,
                    "amount": amt,
                    "status": conf_status,
                })

        audit("mpay.receipts_uploaded", f"user={user_id}, count={len(imported_items)}")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({
            "success": True,
            "message": f"{len(imported_items)} comprovante(s) processado(s) com sucesso!",
            "items": imported_items,
        })

    flash(f"{len(imported_items)} comprovante(s) lido(s) com sucesso pela IA!", "success")
    return redirect(url_for("mpay.index"))


@mpay_bp.route("/api/transactions/new", methods=["POST"])
@login_required
def create_manual_row():
    """Adiciona uma nova linha vazia na planilha para digitação manual."""
    me = current_user()
    if not check_mpay_access(me):
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    data = request.get_json() or {}
    company = data.get("paying_company", "M-one").strip()
    source = data.get("payment_source", "Conta da Empresa").strip()

    user_id = me.get("id") if me else None
    today_str = date.today().isoformat()
    actor = me.get("name") if me else "Usuário"

    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO mpay_transactions (
                paid_at, paying_company, payment_source, beneficiary_name, beneficiary_document, amount,
                bank_origin, payment_method, category, notes,
                confidence_status, created_by
            ) VALUES (%s, %s, %s, 'Novo Favorecido', '', 0.00, '', 'PIX', 'Geral', '', 'manual', %s)
            RETURNING id, paid_at, paying_company, payment_source, beneficiary_name, beneficiary_document, amount, bank_origin, payment_method, category, notes, confidence_status
            """,
            (today_str, company, source, user_id),
        ).fetchone()

    if row:
        r_dict = dict(row)
        log_mpay_audit(row["id"], "created", "mpay_manual", actor_name=actor)
        sync_transaction_to_google_sheet("create", r_dict, actor_name=actor)

    return jsonify({"success": True, "transaction": dict(row) if row else {}})


@mpay_bp.route("/api/transactions/<int:tid>", methods=["PUT"])
@login_required
def update_transaction(tid: int):
    """Atualiza qualquer célula da planilha inline instantaneamente."""
    me = current_user()
    if not check_mpay_access(me):
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    data = request.get_json() or {}
    allowed_fields = [
        "paid_at",
        "paying_company",
        "payment_source",
        "beneficiary_name",
        "beneficiary_document",
        "amount",
        "bank_origin",
        "payment_method",
        "category",
        "notes",
    ]

    updates = []
    values = []

    for f in allowed_fields:
        if f in data:
            val = data[f]
            if f == "amount":
                try:
                    val = float(str(val).replace(",", ".").replace("R$", "").strip() or 0)
                except Exception:
                    val = 0.0
            elif f == "paid_at" and not val:
                val = None
            updates.append(f"{f} = %s")
            values.append(val)

    if not updates:
        return jsonify({"success": False, "message": "Nenhum campo para atualizar."}), 400

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(tid)

    actor = me.get("name") if me else "Usuário"
    with db() as conn:
        current = conn.execute("SELECT * FROM mpay_transactions WHERE id = %s", (tid,)).fetchone()
        conn.execute(
            f"""
            UPDATE mpay_transactions
            SET {', '.join(updates)}
            WHERE id = %s
            """,
            values,
        )
        updated_row = conn.execute("SELECT * FROM mpay_transactions WHERE id = %s", (tid,)).fetchone()

    if updated_row:
        u_dict = dict(updated_row)
        for f in allowed_fields:
            if f in data and current and current.get(f) != updated_row.get(f):
                log_mpay_audit(
                    tid,
                    "updated",
                    "mpay_inline",
                    field_name=f,
                    old_value=current.get(f),
                    new_value=updated_row.get(f),
                    actor_name=actor,
                )
        sync_transaction_to_google_sheet("update", u_dict, actor_name=actor)

    return jsonify({"success": True, "message": "Salvo!"})


@mpay_bp.route("/api/transactions/<int:tid>", methods=["DELETE"])
@login_required
def delete_transaction(tid: int):
    """Exclui um registro da planilha."""
    me = current_user()
    if not check_mpay_access(me):
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    actor = me.get("name") if me else "Usuário"
    with db() as conn:
        conn.execute("DELETE FROM mpay_transactions WHERE id = %s", (tid,))

    log_mpay_audit(tid, "deleted", "mpay_inline", actor_name=actor)
    sync_transaction_to_google_sheet("delete", {"id": tid}, actor_name=actor)

    return jsonify({"success": True, "message": "Registro excluído com sucesso."})


@mpay_bp.route("/api/sheets/config", methods=["GET", "POST"])
@login_required
def sheets_config():
    """Configura ou obtém a URL do Webhook do Google Sheets."""
    me = current_user()
    if not check_mpay_access(me):
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    if request.method == "POST":
        data = request.get_json() or {}
        webhook_url = data.get("webhook_url", "").strip()
        set_mpay_setting("google_sheets_webhook_url", webhook_url)
        return jsonify({"success": True, "message": "Webhook do Google Sheets configurado com sucesso!"})

    current_url = get_mpay_setting("google_sheets_webhook_url")
    return jsonify({"success": True, "webhook_url": current_url})


@mpay_bp.route("/api/sheets/webhook-sync", methods=["POST"])
def sheets_incoming_webhook():
    """Webhook público chamado pelo Google Apps Script para sincronizar edições do Google Sheets."""
    payload = request.get_json(force=True, silent=True) or {}
    success, msg = apply_google_sheets_update(payload)
    status_code = 200 if success else 400
    return jsonify({"success": success, "message": msg}), status_code


@mpay_bp.route("/api/sheets/sync-all", methods=["POST"])
@login_required
def sheets_sync_all():
    """Envia todos os lançamentos para a planilha do Google Sheets."""
    me = current_user()
    if not check_mpay_access(me):
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    with db() as conn:
        rows = conn.execute("SELECT * FROM mpay_transactions ORDER BY id ASC").fetchall()

    success_count = 0
    actor = me.get("name") if me else "M-Pay Sincronizador"
    for r in rows:
        res = sync_transaction_to_google_sheet("create", dict(r), actor_name=actor)
        if res.get("success"):
            success_count += 1

    return jsonify({
        "success": True,
        "message": f"{success_count} de {len(rows)} comprovante(s) sincronizados com o Google Sheets.",
    })


@mpay_bp.route("/api/audit-logs/<int:tid>", methods=["GET"])
@login_required
def get_audit_logs(tid: int):
    """Consulta o histórico detalhado de alterações de um comprovante específico."""
    me = current_user()
    if not check_mpay_access(me):
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    with db() as conn:
        logs = conn.execute(
            """
            SELECT id, transaction_id, action, source, field_name, old_value, new_value, actor_name, created_at
            FROM mpay_audit_logs
            WHERE transaction_id = %s
            ORDER BY created_at DESC
            """,
            (tid,),
        ).fetchall()

    formatted_logs = []
    for l in logs:
        c_at = l.get("created_at").strftime("%d/%m/%Y %H:%M:%S") if l.get("created_at") else ""
        formatted_logs.append({
            "id": l["id"],
            "action": l["action"],
            "source": l["source"],
            "field_name": l["field_name"],
            "old_value": l["old_value"],
            "new_value": l["new_value"],
            "actor_name": l["actor_name"],
            "created_at": c_at,
        })

    return jsonify({"success": True, "logs": formatted_logs})


@mpay_bp.route("/export/xlsx", methods=["GET"])
@login_required
def export_xlsx():
    """Exporta a planilha atual para formato Microsoft Excel (.xlsx) estilizado."""
    if not check_mpay_access(current_user()):
        return "Acesso negado", 403
    return export_mpay_dataset("xlsx", request.args.get("month", "").strip(), request.args.get("q", "").strip())


@mpay_bp.route("/export/csv", methods=["GET"])
@login_required
def export_csv():
    """Exporta os comprovantes em formato CSV delimitado por ponto e vírgula com UTF-8 BOM."""
    if not check_mpay_access(current_user()):
        return "Acesso negado", 403
    return export_mpay_dataset("csv", request.args.get("month", "").strip(), request.args.get("q", "").strip())
