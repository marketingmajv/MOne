"""
M-One Dashboard Service (services/dashboard_service.py)
Consolida métricas e inteligência operacional real do sistema:
- Patrimônio em Catálogos (Atacado B2B + Outlet B2C)
- Pátio de Veículos e Chassis
- Importações China e Faturas Marítimas
- Malha Logística e Cotações de Frete
- Modelos em Destaque do Showroom
Em estrita conformidade com a arquitetura modular anti-monólito (< 500 linhas).
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List
from database import db


def get_dashboard_operational_data(user: dict | None) -> Dict[str, Any]:
    """Retorna dados executivos e operacionais reais para a Visão Geral."""
    is_admin = bool(user and user.get("role") in ["admin", "support", "finance"])

    with db() as conn:
        # 1. Atacado B2B
        at_stat = conn.execute(
            """
            SELECT 
                COUNT(*) as count, 
                COALESCE(SUM(stock_qty), 0) as total_qty, 
                COALESCE(SUM(stock_qty * price_outlet), 0) as total_val
            FROM atacado_items 
            WHERE status = 'active'
            """
        ).fetchone()

        # 2. Outlet B2C
        out_stat = conn.execute(
            """
            SELECT 
                COUNT(*) as count, 
                COALESCE(SUM(stock_qty), 0) as total_qty, 
                COALESCE(SUM(stock_qty * price_outlet), 0) as total_val, 
                COALESCE(AVG(discount_percent), 0) as avg_disc
            FROM outlet_items 
            WHERE status = 'active'
            """
        ).fetchone()

        # 3. Pátio Físico / Chassis
        st_stat = conn.execute("SELECT COUNT(*) as count FROM stock_units").fetchone()

        # 4. Importações China (US$)
        imp_stat = conn.execute(
            """
            SELECT 
                COUNT(*) as count, 
                COALESCE(SUM(pi_amount_usd), 0) + COALESCE(SUM(ocean_freight_usd), 0) as total_usd
            FROM imports 
            WHERE is_archived = FALSE
            """
        ).fetchone()

        # 5. Malha de Fretes
        fr_stat = conn.execute(
            """
            SELECT 
                (SELECT COUNT(*) FROM carriers WHERE active = 1) as carriers_count,
                (SELECT COUNT(*) FROM freight_rates) as rates_count,
                (SELECT COUNT(*) FROM freight_quotes) as quotes_count
            """
        ).fetchone()

        # 6. Catálogos Personalizados Ativos
        custom_catalogs = []
        try:
            cats = conn.execute(
                """
                SELECT id, slug, title, client_name, source_matrix, percentage_markup, views_count, whatsapp_clicks_count, is_active, created_at
                FROM maj_custom_catalogs
                WHERE is_active = TRUE
                ORDER BY id DESC
                LIMIT 4
                """
            ).fetchall()
            custom_catalogs = [dict(c) for c in cats]
        except Exception:
            custom_catalogs = []

        # 7. Modelos em Destaque do Showroom
        showroom_models = []
        try:
            m_rows = conn.execute(
                """
                SELECT id, name, slug, category, image_main, specs_json, price_outlet, price_original, discount_percent, stock_qty
                FROM outlet_items
                WHERE status = 'active' AND image_main IS NOT NULL
                ORDER BY stock_qty DESC, id ASC
                LIMIT 4
                """
            ).fetchall()
            for r in m_rows:
                m = dict(r)
                specs = {}
                try:
                    if m.get("specs_json"):
                        specs = json.loads(m["specs_json"]) if isinstance(m["specs_json"], str) else m["specs_json"]
                except Exception:
                    specs = {}
                m["speed"] = specs.get("Velocidade Máxima") or specs.get("Velocidade") or "Até 32 km/h"
                m["range"] = specs.get("Autonomia") or "Até 50 km"
                m["motor"] = specs.get("Motor") or "1000W Brushless"
                showroom_models.append(m)
        except Exception:
            showroom_models = []

        # 8. Cotações Recentes de Frete
        recent_quotes = []
        try:
            q_rows = conn.execute(
                """
                SELECT id, quote_number, customer_name, cep_dest, items_summary, carrier_results_json, created_at
                FROM freight_quotes
                ORDER BY id DESC
                LIMIT 5
                """
            ).fetchall()
            for r in q_rows:
                q = dict(r)
                # Parse do melhor frete retornado no json
                best_carrier = "Sob consulta"
                best_price = Decimal("0.00")
                delivery_days = "-"
                item_name = "Veículo Elétrico MAJ"
                try:
                    if q.get("items_summary"):
                        items = json.loads(q["items_summary"]) if isinstance(q["items_summary"], str) else q["items_summary"]
                        if items and len(items) > 0:
                            item_name = items[0].get("name", item_name)
                    if q.get("carrier_results_json"):
                        c_results = json.loads(q["carrier_results_json"]) if isinstance(q["carrier_results_json"], str) else q["carrier_results_json"]
                        if c_results and len(c_results) > 0:
                            best = c_results[0]
                            best_carrier = best.get("carrier_name", best_carrier)
                            best_price = Decimal(str(best.get("total_price", 0)))
                            delivery_days = f"{best.get('delivery_days', '-')} dias"
                except Exception:
                    pass

                q["item_name"] = item_name
                q["best_carrier"] = best_carrier
                q["best_price"] = best_price
                q["delivery_days"] = delivery_days
                recent_quotes.append(q)
        except Exception:
            recent_quotes = []

        # 9. Atividades Recentes do Log
        recent_activities = []
        try:
            acts = conn.execute(
                """
                SELECT a.action, a.detail, a.created_at, COALESCE(u.name, 'Sistema') as user_name
                FROM audit_log a
                LEFT JOIN users u ON u.id = a.user_id
                ORDER BY a.id DESC
                LIMIT 6
                """
            ).fetchall()
            recent_activities = [dict(a) for a in acts]
        except Exception:
            recent_activities = []

    # Cálculos Consolidados
    val_at = Decimal(str(at_stat["total_val"] or 0))
    val_out = Decimal(str(out_stat["total_val"] or 0))
    total_catalog_val = val_at + val_out
    total_catalog_units = int(at_stat["total_qty"] or 0) + int(out_stat["total_qty"] or 0)

    return {
        "kpis": {
            "total_catalog_value": total_catalog_val,
            "total_catalog_units": total_catalog_units,
            "stock_chassis_count": int(st_stat["count"] or 0),
            "stock_location": "Depósito Consolação & Galpão MAJ",
            "imports_count": int(imp_stat["count"] or 0),
            "imports_total_usd": float(imp_stat["total_usd"] or 0.0),
            "carriers_count": int(fr_stat["carriers_count"] or 0),
            "freight_rates_count": int(fr_stat["rates_count"] or 0),
            "freight_quotes_count": int(fr_stat["quotes_count"] or 0),
        },
        "channels": {
            "outlet": {
                "count": int(out_stat["count"] or 0),
                "qty": int(out_stat["total_qty"] or 0),
                "val": val_out,
                "avg_discount": round(float(out_stat["avg_disc"] or 0), 1),
            },
            "atacado": {
                "count": int(at_stat["count"] or 0),
                "qty": int(at_stat["total_qty"] or 0),
                "val": val_at,
            },
            "custom_catalogs": custom_catalogs,
        },
        "showroom_models": showroom_models,
        "recent_quotes": recent_quotes,
        "recent_activities": recent_activities,
        "is_admin_or_support": is_admin,
    }
