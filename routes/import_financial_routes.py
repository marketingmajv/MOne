"""
M-One Import Financial Blueprint (routes/import_financial_routes.py)
Rotas de controle financeiro: Pagamentos da China, Despesas no Brasil,
Conciliação de Numerário Aduaneiro e Itens de Produtos.
"""

from __future__ import annotations

import logging
import os
from flask import Blueprint, current_app, flash, jsonify, redirect, request, url_for
from werkzeug.utils import secure_filename

from database import db
from routes.helpers import audit, current_user, login_required, roles_required
from services.import_audit_service import run_import_audit_checks
from services.import_calculator import calculate_import_financials

logger = logging.getLogger(__name__)

import_financial_bp = Blueprint("import_financial", __name__)


@import_financial_bp.route("/api/imports/<int:iid>/payments-china", methods=["POST"])
@login_required
@roles_required("admin", "support")
def add_payment_china(iid: int):
    """Adiciona lançamento de pagamento ao fornecedor na China."""
    category = request.form.get("payment_category", "ci_payment")
    description = request.form.get("description", "").strip()
    amount_usd = request.form.get("amount_usd", "0")
    amount_brl = request.form.get("amount_brl", "0")
    exchange_rate = request.form.get("exchange_rate") or None
    bank_fees_brl = request.form.get("bank_fees_brl", "0")
    paid_at = request.form.get("paid_at") or None
    doc_id = request.form.get("document_id") or None

    # Normalizar valores numéricos e câmbio
    try:
        val_usd = float(amount_usd or 0)
        val_brl = float(amount_brl or 0)
        if not exchange_rate and val_usd > 0 and val_brl > 0:
            exchange_rate = str(round(val_brl / val_usd, 4))
    except (ValueError, ZeroDivisionError):
        pass

    # Upload opcional de comprovante (se fornecido)
    receipt_file = request.files.get("receipt_file")
    me = current_user() or {}

    try:
        with db() as conn:
            if receipt_file and receipt_file.filename:
                orig_filename = secure_filename(receipt_file.filename)
                file_bytes = receipt_file.read()
                if file_bytes:
                    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
                    os.makedirs(upload_folder, exist_ok=True)
                    from services.import_ai_service import calculate_file_hash
                    file_hash = calculate_file_hash(file_bytes)
                    unique_filename = f"imp_{iid}_{file_hash[:8]}_{orig_filename}"
                    save_path = os.path.join(upload_folder, unique_filename)
                    with open(save_path, "wb") as out_f:
                        out_f.write(file_bytes)
                    doc_type = "SUPPLIER_PAYMENT"
                    title = f"Comprovante - {description or ('Outros Débitos' if category in ('additional_payment', 'other_debit') else 'Pagamento')}"
                    new_doc = conn.execute(
                        """
                        INSERT INTO import_documents (
                            import_id, doc_type, title, filename, file_url, file_size, file_hash,
                            extracted_data, ai_status, uploaded_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, '{}', 'manual', %s)
                        RETURNING id
                        """,
                        (iid, doc_type, title, orig_filename, unique_filename, len(file_bytes), file_hash, me.get("id")),
                    ).fetchone()
                    if new_doc:
                        doc_id = new_doc["id"]

            conn.execute(
                """
                INSERT INTO import_payments_china (
                    import_id, payment_category, description, amount_usd, amount_brl, 
                    exchange_rate, bank_fees_brl, paid_at, document_id, is_verified
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                """,
                (iid, category, description, amount_usd, amount_brl, exchange_rate, bank_fees_brl, paid_at, doc_id),
            )
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.payment_china_added", f"import_id={iid}, cat={category}, usd={amount_usd}, brl={amount_brl}")
        
        msg = "Outro débito registrado com sucesso!" if category in ("additional_payment", "other_debit") else "Pagamento no exterior registrado com sucesso!"
        flash(msg, "success")
    except Exception as e:
        logger.error("Erro ao registrar pagamento na China: %s", e)
        flash(f"Erro ao salvar pagamento: {str(e)}", "error")

    return redirect(url_for("imports.import_detail", iid=iid, tab="payments"))


@import_financial_bp.route("/api/imports/<int:iid>/payments-china/<int:pid>/delete", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_payment_china(iid: int, pid: int):
    """Remove lançamento de pagamento no exterior."""
    try:
        with db() as conn:
            conn.execute("DELETE FROM import_payments_china WHERE id = %s AND import_id = %s", (pid, iid))
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.payment_china_deleted", f"import_id={iid}, pid={pid}")
        flash("Pagamento removido com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao remover: {str(e)}", "error")
    return redirect(url_for("imports.import_detail", iid=iid, tab="payments"))


@import_financial_bp.route("/api/imports/<int:iid>/expenses-brazil", methods=["POST"])
@login_required
@roles_required("admin", "support")
def add_expense_brazil(iid: int):
    """Adiciona lançamento de despesa ou tributo no Brasil."""
    category = request.form.get("category", "outras")
    provider = request.form.get("provider", "").strip()
    description = request.form.get("description", "").strip()
    predicted_amount = request.form.get("predicted_amount", "0")
    actual_amount = request.form.get("actual_amount", "0")
    due_date = request.form.get("due_date") or None
    paid_at = request.form.get("paid_at") or None
    payment_mode = request.form.get("payment_mode", "direct")
    icms_in_num = bool(request.form.get("icms_in_numerario"))
    doc_id = request.form.get("document_id") or None

    try:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO import_brazil_expenses (
                    import_id, category, provider, description, predicted_amount, actual_amount,
                    due_date, paid_at, payment_mode, icms_in_numerario, document_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (iid, category, provider, description, predicted_amount, actual_amount, due_date, paid_at, payment_mode, icms_in_num, doc_id),
            )
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.expense_brazil_added", f"import_id={iid}, cat={category}, val={actual_amount or predicted_amount}")
        flash("Despesa nacional registrada com sucesso!", "success")
    except Exception as e:
        logger.error("Erro ao registrar despesa: %s", e)
        flash(f"Erro ao salvar despesa: {str(e)}", "error")

    return redirect(url_for("imports.import_detail", iid=iid, tab="expenses"))


@import_financial_bp.route("/api/imports/<int:iid>/expenses-brazil/<int:eid>/delete", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_expense_brazil(iid: int, eid: int):
    """Remove lançamento de despesa no Brasil."""
    try:
        with db() as conn:
            conn.execute("DELETE FROM import_brazil_expenses WHERE id = %s AND import_id = %s", (eid, iid))
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.expense_brazil_deleted", f"import_id={iid}, eid={eid}")
        flash("Despesa removida.", "success")
    except Exception as e:
        flash(f"Erro ao remover: {str(e)}", "error")
    return redirect(url_for("imports.import_detail", iid=iid, tab="expenses"))


@import_financial_bp.route("/api/imports/<int:iid>/numerario", methods=["POST"])
@login_required
@roles_required("admin", "support")
def add_numerario_entry(iid: int):
    """Registra adiantamento, despesa comprovada ou devolução de numerário."""
    entry_type = request.form.get("entry_type", "advance")
    amount = request.form.get("amount", "0")
    entry_date = request.form.get("entry_date") or None
    description = request.form.get("description", "").strip()
    doc_id = request.form.get("document_id") or None

    try:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO import_numerario (import_id, entry_type, amount, entry_date, description, document_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (iid, entry_type, amount, entry_date, description, doc_id),
            )
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.numerario_added", f"import_id={iid}, type={entry_type}, val={amount}")
        flash("Lançamento de numerário salvo com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao salvar numerário: {str(e)}", "error")

    return redirect(url_for("imports.import_detail", iid=iid, tab="numerario"))


@import_financial_bp.route("/api/imports/<int:iid>/numerario/<int:nid>/delete", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_numerario_entry(iid: int, nid: int):
    """Remove lançamento de numerário."""
    try:
        with db() as conn:
            conn.execute("DELETE FROM import_numerario WHERE id = %s AND import_id = %s", (nid, iid))
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.numerario_deleted", f"import_id={iid}, nid={nid}")
        flash("Lançamento de numerário removido.", "success")
    except Exception as e:
        flash(f"Erro ao remover: {str(e)}", "error")
    return redirect(url_for("imports.import_detail", iid=iid, tab="numerario"))


@import_financial_bp.route("/api/imports/<int:iid>/items", methods=["POST"])
@login_required
@roles_required("admin", "support")
def add_import_item(iid: int):
    """Adiciona produto e quantidade à lista da importação."""
    product_id = request.form.get("product_id") or None
    product_name_custom = request.form.get("product_name_custom", "").strip()
    quantity = int(request.form.get("quantity", "1") or 1)
    unit_price_usd = request.form.get("unit_price_usd", "0")
    total_price_usd = float(unit_price_usd or 0) * quantity

    try:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO import_items (
                    import_id, product_id, product_name_custom, quantity, unit_price_usd, total_price_usd
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (iid, product_id, product_name_custom, quantity, unit_price_usd, total_price_usd),
            )
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.item_added", f"import_id={iid}, qty={quantity}, val={total_price_usd}")
        flash("Item adicionado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao adicionar produto: {str(e)}", "error")

    return redirect(url_for("imports.import_detail", iid=iid, tab="products"))


@import_financial_bp.route("/api/imports/<int:iid>/items/<int:item_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_import_item(iid: int, item_id: int):
    """Remove item da importação."""
    try:
        with db() as conn:
            conn.execute("DELETE FROM import_items WHERE id = %s AND import_id = %s", (item_id, iid))
            calculate_import_financials(iid, conn)
            run_import_audit_checks(iid, conn)
            audit("import.item_deleted", f"import_id={iid}, item_id={item_id}")
        flash("Item removido com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao remover item: {str(e)}", "error")
    return redirect(url_for("imports.import_detail", iid=iid, tab="products"))
