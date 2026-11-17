"""
M-One Stock Chassis Sales & Separation Blueprint (routes/stock_chassis_sales_routes.py)
Rotas operacionais para o Financeiro/Vendas (Marisa):
- Busca rápida / bipagem de chassi (/api/chassis/search)
- Marcar mercadoria como Separada para Venda com Nº Pedido (/sales/chassis-separate)
- Baixa de venda por chassi com NF Venda e NF Transf. 1/2 (/sales/chassis-checkout)
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from routes.helpers import audit, current_user, login_required, permission_required
from services.stock_chassis_action_service import (
    checkout_chassis_sale,
    search_chassis_candidates,
    separate_chassis_for_sale,
)

stock_chassis_sales_bp = Blueprint("stock_chassis_sales", __name__)


@stock_chassis_sales_bp.route("/api/chassis/search", methods=["GET"])
@login_required
def api_chassis_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"ok": True, "items": []})
    items = search_chassis_candidates(q, limit=15)
    return jsonify({"ok": True, "items": items})


@stock_chassis_sales_bp.route("/sales/chassis-separate", methods=["POST"])
@login_required
@permission_required("chassis_sales")
def chassis_separate():
    data = request.get_json(silent=True) or request.form or {}
    chassis = data.get("chassis", "")
    order_number = data.get("order_number", "")
    u = current_user() or {}
    res = separate_chassis_for_sale(chassis, order_number, u.get("id"))
    if res.get("ok"):
        audit("stock.chassis_separated", f"chassis={res['chassis']} order={res['order_number']}")
    return jsonify(res), (200 if res.get("ok") else 400)


@stock_chassis_sales_bp.route("/sales/chassis-checkout", methods=["POST"])
@login_required
@permission_required("chassis_sales")
def chassis_checkout():
    data = request.get_json(silent=True) or request.form or {}
    u = current_user() or {}
    res = checkout_chassis_sale(data, u.get("id"))
    if res.get("ok"):
        audit(
            "sales.chassis_checkout",
            f"sale_id={res['sale_id']} chassis={res['chassis']} nf={res['invoice_number']} val={res['total_value']}",
        )
    return jsonify(res), (200 if res.get("ok") else 400)
