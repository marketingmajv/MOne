"""
M-One Finance & Payments Blueprint (routes/finance_routes.py)
Rotas de Registro de Pagamentos, Exportação de Extratos e Análise de Comprovantes por IA.
"""

from __future__ import annotations

import base64
import csv
import io
from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from database import db
from gemini_service import (
    ACCOUNTS_LIST,
    PAYMENT_CATEGORIES,
    PAYMENT_METHODS,
    analyze_payment_receipt,
)
from routes.helpers import (
    audit,
    current_user,
    login_required,
    roles_required,
    save_base64_upload,
    save_upload,
)

finance_bp = Blueprint("finance", __name__)


def ensure_payments_columns():
    try:
        with db() as conn:
            for col, col_type in [
                ("payment_method", "TEXT"),
                ("card_last4", "TEXT"),
                ("supplier", "TEXT"),
                ("document_no", "TEXT"),
                ("ai_verified", "INTEGER DEFAULT 0")
            ]:
                try:
                    conn.execute(f"ALTER TABLE payments ADD COLUMN {col} {col_type}")
                except Exception:
                    pass
            conn.commit()
    except Exception:
        pass


@finance_bp.route("/payments", methods=["GET", "POST"])
@login_required
@roles_required("admin", "finance", "support")
def payments():
    ensure_payments_columns()

    if request.method == "POST":
        paid_at = request.form.get("paid_at") or date.today().isoformat()
        description = request.form.get("description", "").strip()
        amount = float(request.form.get("amount") or 0)
        category = request.form.get("category", "").strip()
        account = request.form.get("account", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        card_last4 = request.form.get("card_last4", "").strip()
        supplier = request.form.get("supplier", "").strip()
        document_no = request.form.get("document_no", "").strip()
        import_id = request.form.get("import_id") or None
        visibility = "admin_only" if import_id else "finance"

        try:
            receipt = save_base64_upload(request.form.get("captured_image_data"), "pagamento")
            if not receipt:
                receipt = save_upload(request.files.get("receipt_file"), "pagamento")
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("payments"))

        if not receipt:
            flash("⚠️ É OBRIGATÓRIO anexar a Nota Fiscal do Fornecedor ou Recibo de Pagamento (por foto ou arquivo).", "danger")
            return redirect(url_for("payments"))

        if not description or amount <= 0:
            flash("Descrição e valor são obrigatórios.", "danger")
            return redirect(url_for("payments"))

        with db() as conn:
            conn.execute(
                """INSERT INTO payments(paid_at, description, category, amount, account, payment_method, card_last4, supplier, document_no, receipt_file, import_id, visibility, created_by)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (paid_at, description, category, amount, account, payment_method, card_last4, supplier, document_no, receipt, import_id, visibility, session["user_id"]),
            )
            conn.commit()
        audit("payment.created", f"{description}; R$ {amount}; Categoria: {category}; Conta: {account}")
        flash("🎉 Pagamento realizado registrado com sucesso!", "success")
        return redirect(url_for("payments"))

    u = current_user()
    with db() as conn:
        if u and u.get("role") in ("admin", "support"):
            rows = conn.execute("SELECT p.*,i.reference import_ref FROM payments p LEFT JOIN imports i ON i.id=p.import_id ORDER BY p.paid_at DESC,p.id DESC LIMIT 300").fetchall()
            imports_rows = conn.execute("SELECT id,reference FROM imports ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT p.*,NULL import_ref FROM payments p WHERE visibility='finance' ORDER BY p.paid_at DESC,p.id DESC LIMIT 300").fetchall()
            imports_rows = []
    return render_template(
        "payments.html",
        payments=rows,
        imports=imports_rows,
        categories=PAYMENT_CATEGORIES,
        accounts=ACCOUNTS_LIST,
        payment_methods=PAYMENT_METHODS
    )


@finance_bp.route("/api/payments/analyze-receipt", methods=["POST"])
@login_required
def api_analyze_payment_receipt():
    try:
        image_bytes = None
        mime_type = "image/jpeg"

        base64_str = request.form.get("captured_image_data")
        if base64_str and "," in base64_str:
            header, data = base64_str.split(",", 1)
            image_bytes = base64.b64decode(data)
            mime_type = "image/png" if "png" in header else "image/jpeg"
        elif "receipt_file" in request.files:
            f = request.files["receipt_file"]
            image_bytes = f.read()
            mime_type = f.content_type or "image/jpeg"

        if not image_bytes:
            return jsonify({"success": False, "message": "Nenhum arquivo ou foto foi enviado para análise."}), 400

        form_data = {
            "amount": request.form.get("amount"),
            "paid_at": request.form.get("paid_at"),
            "category": request.form.get("category"),
            "account": request.form.get("account"),
            "payment_method": request.form.get("payment_method"),
            "card_last4": request.form.get("card_last4")
        }

        analysis = analyze_payment_receipt(image_bytes, mime_type=mime_type, form_data=form_data)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@finance_bp.route("/payments/export")
@login_required
@roles_required("admin", "finance", "support")
def export_payments():
    audit("payments.exported", "")
    u = current_user()
    with db() as conn:
        if u and u.get("role") in ("admin", "support"):
            rows = conn.execute(
                """SELECT p.paid_at, p.description, p.category, p.account, p.amount, i.reference import_ref
                   FROM payments p LEFT JOIN imports i ON i.id=p.import_id ORDER BY p.paid_at DESC"""
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT p.paid_at, p.description, p.category, p.account, p.amount, NULL import_ref
                   FROM payments p WHERE visibility='finance' ORDER BY p.paid_at DESC"""
            ).fetchall()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["DATA", "DESCRICAO", "CATEGORIA", "CONTA", "VALOR", "IMPORTACAO"])
    for r in rows:
        writer.writerow([r["paid_at"], r["description"], r["category"] or "", r["account"] or "", f"{r['amount']:.2f}".replace(".", ","), r["import_ref"] or ""])
    return out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8-sig", "Content-Disposition": "attachment; filename=pagamentos_m_one.csv"}
