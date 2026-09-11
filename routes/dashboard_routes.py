"""
M-One Dashboard & Media Blueprint (routes/dashboard_routes.py)
Rotas da Visão Geral (Dashboard), Uploads estáticos e Logs de Auditoria.
"""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template, request, send_from_directory

from database import db
from routes.helpers import UPLOAD_DIR, current_user, login_required, roles_required, user_has_permission

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def dashboard():
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    today_iso = today.isoformat()
    ago90 = (today - timedelta(days=90)).isoformat()
    ago30 = (today - timedelta(days=30)).isoformat()

    me = current_user()
    is_seller = bool(me and me.get("role") == "sales" and not user_has_permission(me, "all_sales", default_for_sales=False))

    with db() as conn:
        if is_seller:
            st_row = conn.execute(
                "SELECT COALESCE(SUM(total_value),0) v, COUNT(*) c FROM sales WHERE sold_at=%s AND created_by=%s",
                (today_iso, me["id"])
            ).fetchone()
            sales_today = st_row["v"]
            sales_today_count = st_row["c"]
            sales_month = conn.execute(
                "SELECT COALESCE(SUM(total_value),0) v FROM sales WHERE sold_at>=%s AND created_by=%s",
                (month_start, me["id"])
            ).fetchone()["v"]
            payments_month = 0.0
        else:
            st_row = conn.execute(
                "SELECT COALESCE(SUM(total_value),0) v, COUNT(*) c FROM sales WHERE sold_at=%s",
                (today_iso,)
            ).fetchone()
            sales_today = st_row["v"]
            sales_today_count = st_row["c"]
            sales_month = conn.execute(
                "SELECT COALESCE(SUM(total_value),0) v FROM sales WHERE sold_at>=%s",
                (month_start,)
            ).fetchone()["v"]
            payments_month = conn.execute(
                "SELECT COALESCE(SUM(amount),0) v FROM payments WHERE paid_at>=%s",
                (month_start,)
            ).fetchone()["v"]
        stock_available = conn.execute(
            "SELECT COUNT(*) c FROM stock_units WHERE status='available'"
        ).fetchone()["c"]
        top_products = conn.execute(
            """
            SELECT p.id, p.name, COUNT(su.id) units, COALESCE(SUM(su.unit_value),0) revenue
            FROM sale_units su
            JOIN sales s ON s.id = su.sale_id
            JOIN products p ON p.id = su.product_id
            WHERE s.sold_at >= %s
            GROUP BY p.id, p.name
            ORDER BY units DESC, revenue DESC
            LIMIT 6
            """,
            (month_start,)
        ).fetchall()
        opportunities = conn.execute(
            """
            SELECT p.id, p.name, p.unit_cost, p.wholesale_price, p.retail_price,
                   COUNT(st.id) AS available,
                   MIN(COALESCE(st.received_at::date, st.created_at::date)) AS oldest_date,
                   COALESCE((SELECT COUNT(*) FROM sale_units su2 JOIN sales s2 ON s2.id = su2.sale_id
                             WHERE su2.product_id = p.id AND s2.sold_at >= %s), 0) AS sold_30
            FROM products p
            JOIN stock_units st ON st.product_id = p.id AND st.status = 'available'
            WHERE p.promo_eligible = TRUE
            GROUP BY p.id, p.name, p.unit_cost, p.wholesale_price, p.retail_price
            HAVING COUNT(st.id) > 0 AND MIN(COALESCE(st.received_at::date, st.created_at::date)) <= %s::date
            ORDER BY sold_30 ASC, oldest_date ASC, available DESC
            LIMIT 6
            """,
            (ago30, ago90)
        ).fetchall()
        chassis_alerts = conn.execute(
            """
            SELECT COUNT(*) c FROM stock_units st
            LEFT JOIN imports i ON i.id = st.import_id
            WHERE st.status = 'available' AND (i.id IS NULL OR i.status != 'released')
            """
        ).fetchone()["c"]

    opp = []
    for r in opportunities:
        d = dict(r)
        d["suggested_price"] = round(float(d.get("unit_cost") or 0) * 1.10, 2)
        try:
            oldest_val = d.get("oldest_date")
            if isinstance(oldest_val, str):
                oldest = date.fromisoformat(oldest_val)
            elif isinstance(oldest_val, date):
                oldest = oldest_val
            else:
                oldest = today
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
                   WHERE a.action ILIKE %s OR a.detail ILIKE %s OR u.name ILIKE %s 
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


@dashboard_bp.route("/api/dashboard/chart-data")
@login_required
def api_dashboard_chart_data():
    """Retorna dados agregados de vendas e categorias para renderização de gráficos no dashboard."""
    period = request.args.get("period", "30d").strip().lower()
    today = date.today()

    if period == "7d":
        start_date = today - timedelta(days=6)
    elif period == "month":
        start_date = today.replace(day=1)
    elif period == "year":
        start_date = today.replace(month=1, day=1)
    else:  # default 30d
        period = "30d"
        start_date = today - timedelta(days=29)

    start_iso = start_date.isoformat()
    me = current_user()
    is_seller = bool(me and me.get("role") == "sales" and not user_has_permission(me, "all_sales", default_for_sales=False))

    seller_filter = "AND s.created_by = %s" if is_seller else ""
    query_params = (start_iso, me["id"]) if is_seller else (start_iso,)

    with db() as conn:
        # Tendência diária de vendas
        daily_rows = conn.execute(
            f"""
            SELECT s.sold_at::date AS dia, COALESCE(SUM(s.total_value), 0) AS total, COUNT(s.id) AS count
            FROM sales s
            WHERE s.sold_at >= %s {seller_filter}
            GROUP BY s.sold_at::date
            ORDER BY s.sold_at::date ASC
            """,
            query_params
        ).fetchall()

        # Distribuição por categoria/produto
        cat_rows = conn.execute(
            f"""
            SELECT COALESCE(NULLIF(TRIM(p.category), ''), 'Outros') AS cat,
                   COUNT(su.id) AS units,
                   COALESCE(SUM(su.unit_value), 0) AS revenue
            FROM sale_units su
            JOIN sales s ON s.id = su.sale_id
            JOIN products p ON p.id = su.product_id
            WHERE s.sold_at >= %s {seller_filter}
            GROUP BY COALESCE(NULLIF(TRIM(p.category), ''), 'Outros')
            ORDER BY revenue DESC
            LIMIT 5
            """,
            query_params
        ).fetchall()

    # Mapear dias para garantir gráfico contínuo sem buracos
    day_map = {str(r["dia"]): {"total": float(r["total"]), "count": int(r["count"])} for r in daily_rows}
    labels = []
    values = []
    counts = []

    curr = start_date
    while curr <= today:
        curr_str = curr.isoformat()
        labels.append(curr.strftime("%d/%m"))
        data_day = day_map.get(curr_str, {"total": 0.0, "count": 0})
        values.append(data_day["total"])
        counts.append(data_day["count"])
        curr += timedelta(days=1)

    return jsonify({
        "success": True,
        "period": period,
        "trend": {
            "labels": labels,
            "values": values,
            "counts": counts,
            "total_revenue": sum(values),
            "total_orders": sum(counts),
        },
        "categories": {
            "labels": [r["cat"] for r in cat_rows] or ["Sem vendas"],
            "values": [float(r["revenue"]) for r in cat_rows] or [0],
            "units": [int(r["units"]) for r in cat_rows] or [0],
        }
    })

