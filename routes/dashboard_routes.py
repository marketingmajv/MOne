"""
M-One Dashboard & Media Blueprint (routes/dashboard_routes.py)
Rotas da Visão Geral (Dashboard), Uploads estáticos e Logs de Auditoria.
"""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, render_template, request, send_from_directory

from database import db
from routes.helpers import UPLOAD_DIR, login_required, roles_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def dashboard():
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    today_iso = today.isoformat()
    ago90 = (today - timedelta(days=90)).isoformat()
    ago30 = (today - timedelta(days=30)).isoformat()

    with db() as conn:
        st_row = conn.execute(
            "SELECT COALESCE(SUM(total_value),0) v, COUNT(*) c FROM sales WHERE sold_at=?",
            (today_iso,)
        ).fetchone()
        sales_today = st_row["v"]
        sales_today_count = st_row["c"]
        sales_month = conn.execute(
            "SELECT COALESCE(SUM(total_value),0) v FROM sales WHERE sold_at>=?",
            (month_start,)
        ).fetchone()["v"]
        payments_month = conn.execute(
            "SELECT COALESCE(SUM(amount),0) v FROM payments WHERE paid_at>=?",
            (month_start,)
        ).fetchone()["v"]
        stock_available = conn.execute(
            "SELECT COUNT(*) c FROM stock_units WHERE status='available'"
        ).fetchone()["c"]
        top_products = conn.execute(
            """
            SELECT p.id,p.name,COUNT(su.id) units,COALESCE(SUM(su.unit_value),0) revenue
            FROM sale_units su JOIN sales s ON s.id=su.sale_id JOIN products p ON p.id=su.product_id
            WHERE s.sold_at>=?
            GROUP BY p.id,p.name ORDER BY units DESC,revenue DESC LIMIT 6
            """,
            (month_start,)
        ).fetchall()
        opportunities = conn.execute(
            """
            SELECT p.id,p.name,p.unit_cost,p.wholesale_price,p.retail_price,
                   COUNT(st.id) available,
                   MIN(COALESCE(st.received_at, substr(st.created_at,1,10))) oldest_date,
                   COALESCE((SELECT COUNT(*) FROM sale_units su2 JOIN sales s2 ON s2.id=su2.sale_id
                             WHERE su2.product_id=p.id AND s2.sold_at>=?),0) sold_30
            FROM products p JOIN stock_units st ON st.product_id=p.id AND st.status='available'
            WHERE p.promo_eligible=1
            GROUP BY p.id
            HAVING available>0 AND oldest_date<=?
            ORDER BY sold_30 ASC, oldest_date ASC, available DESC LIMIT 6
            """,
            (ago30, ago90)
        ).fetchall()
        chassis_alerts = conn.execute(
            """
            SELECT COUNT(*) c FROM stock_units st
            LEFT JOIN imports i ON i.id=st.import_id
            WHERE st.status='available' AND (i.id IS NULL OR i.status!='released')
            """
        ).fetchone()["c"]

    opp = []
    for r in opportunities:
        d = dict(r)
        d["suggested_price"] = round(float(d["unit_cost"] or 0) * 1.10, 2)
        try:
            oldest = date.fromisoformat(d["oldest_date"])
            d["days_in_stock"] = (today - oldest).days
        except Exception:
            d["days_in_stock"] = 0
        opp.append(d)

    return render_template(
        "dashboard.html",
        sales_today=sales_today,
        sales_today_count=sales_today_count,
        sales_month=sales_month,
        payments_month=payments_month,
        stock_available=stock_available,
        top_products=top_products,
        opportunities=opp,
        chassis_alerts=chassis_alerts,
    )


@dashboard_bp.route("/audit-logs")
@login_required
@roles_required("admin", "support")
def audit_logs():
    q = request.args.get("q", "").strip()
    with db() as conn:
        if q:
            rows = conn.execute(
                """SELECT a.*, u.name user_name, u.role user_role 
                   FROM audit_log a 
                   LEFT JOIN users u ON u.id = a.user_id 
                   WHERE a.action LIKE ? OR a.detail LIKE ? OR u.name LIKE ? 
                   ORDER BY a.id DESC LIMIT 300""",
                (f"%{q}%", f"%{q}%", f"%{q}%")
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT a.*, u.name user_name, u.role user_role 
                   FROM audit_log a 
                   LEFT JOIN users u ON u.id = a.user_id 
                   ORDER BY a.id DESC LIMIT 300"""
            ).fetchall()
    return render_template("audit_logs.html", logs=rows, q=q)


@dashboard_bp.route("/uploads/<path:filename>")
@login_required
def uploads(filename: str):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)
