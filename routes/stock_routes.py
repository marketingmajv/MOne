"""
M-One Stock & Chassis Blueprint (routes/stock_routes.py)
Rotas de Consulta de Estoque, Cadastro de Chassi, Exportação e API de Validação de Chassi.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from database import db
from routes.helpers import audit, login_required, roles_required

stock_bp = Blueprint("stock", __name__)


@stock_bp.route("/stock")
@login_required
def stock():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "available")
    params = []
    where = ["1=1"]
    if q:
        where.append("(st.chassis LIKE ? OR p.name LIKE ? OR st.color LIKE ? OR st.motor_no LIKE ?)")
        term = f"%{q}%"
        params += [term, term, term, term]
    if status and status != "all":
        where.append("st.status=?")
        params.append(status)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT st.*,p.name product_name,i.reference import_ref,i.status import_status,s.invoice_number
            FROM stock_units st JOIN products p ON p.id=st.product_id
            LEFT JOIN imports i ON i.id=st.import_id
            LEFT JOIN sales s ON s.id=st.sale_id
            WHERE {' AND '.join(where)} ORDER BY st.created_at DESC LIMIT 500
            """,
            params
        ).fetchall()
        products_list = conn.execute("SELECT id, name FROM products ORDER BY name").fetchall()
    return render_template("stock.html", units=rows, q=q, status=status, products=products_list)


@stock_bp.route("/api/chassis/<path:chassis>")
@login_required
def api_chassis(chassis):
    audit("chassis.queried", f"chassis={chassis}")
    with db() as conn:
        row = conn.execute(
            """SELECT st.chassis,st.status,st.color,st.motor_no,p.name product,i.reference import_ref,i.status import_status,s.invoice_number
               FROM stock_units st JOIN products p ON p.id=st.product_id LEFT JOIN imports i ON i.id=st.import_id LEFT JOIN sales s ON s.id=st.sale_id
               WHERE st.chassis=?""",
            (chassis,)
        ).fetchone()
    if not row:
        return jsonify({"ok": False, "message": "Chassi não encontrado. Importe a planilha do contêiner."}), 404
    return jsonify({"ok": True, "unit": dict(row)})


@stock_bp.route("/stock/add", methods=["POST"])
@login_required
@roles_required("admin", "stock", "support")
def add_stock_unit():
    chassis = request.form.get("chassis", "").strip()
    product_id = request.form.get("product_id")
    color = request.form.get("color", "").strip()
    motor_no = request.form.get("motor_no", "").strip()
    location = request.form.get("location", "Depósito").strip()
    received_at = request.form.get("received_at") or date.today().isoformat()
    if not chassis or not product_id:
        flash("Chassi e produto são obrigatórios.", "danger")
        return redirect(url_for("stock"))
    with db() as conn:
        if conn.execute("SELECT 1 FROM stock_units WHERE chassis=?", (chassis,)).fetchone():
            flash("Chassi já cadastrado na base.", "danger")
            return redirect(url_for("stock"))
        conn.execute(
            """INSERT INTO stock_units(chassis,motor_no,product_id,color,status,location,received_at)
               VALUES(?,?,?,?,'available',?,?)""",
            (chassis, motor_no, product_id, color, location, received_at)
        )
        conn.commit()
    audit("stock.unit_added", f"chassis={chassis}")
    flash("Unidade adicionada ao estoque com sucesso.", "success")
    return redirect(url_for("stock"))


@stock_bp.route("/stock/export")
@login_required
def export_stock():
    audit("stock.exported", "")
    with db() as conn:
        rows = conn.execute(
            """SELECT st.chassis, p.name product_name, st.color, st.motor_no, COALESCE(i.reference, 'Nacional') import_ref, st.location, st.status, st.received_at
               FROM stock_units st JOIN products p ON p.id=st.product_id LEFT JOIN imports i ON i.id=st.import_id
               ORDER BY st.created_at DESC"""
        ).fetchall()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["CHASSI", "PRODUTO", "COR", "MOTOR", "IMPORTACAO", "LOCAL", "STATUS", "DATA_ENTRADA"])
    for r in rows:
        writer.writerow([r["chassis"], r["product_name"], r["color"] or "", r["motor_no"] or "", r["import_ref"], r["location"], r["status"], r["received_at"] or ""])
    return out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8-sig", "Content-Disposition": "attachment; filename=estoque_m_one.csv"}
