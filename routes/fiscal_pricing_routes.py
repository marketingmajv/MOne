"""
Rotas e endpoints do Módulo de Precificação Fiscal & Intercompany (COLVIX -> M-ONE / PJ).
Respeita estritamente o limite de 500 linhas da regra anti-monólito do M-One.
"""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, render_template, request
from database import db
from routes.helpers import current_user, login_required
from services.fiscal_cost_calculator import calculate_apportionment
from services.fiscal_parser_service import parse_excel_file, parse_mone_import, parse_nfe_xml
from services.tax_simulation_service import generate_nfe_mirror_data, simulate_commercial_sale

logger = logging.getLogger("mone.fiscal_routes")

fiscal_pricing_bp = Blueprint("fiscal_pricing", __name__)


# -----------------------------------------------------------------------------
# Helpers de Banco de Dados (Compatíveis com PostgreSQL Supabase e SQLite)
# -----------------------------------------------------------------------------
def _is_pg(conn) -> bool:
    return hasattr(conn, "conn") or hasattr(conn, "pg_conn") or type(conn).__name__ == "PGConnWrapper"


def _fmt(sql: str, is_pg: bool) -> str:
    if is_pg:
        return sql.replace("?", "%s")
    return sql


def _fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with db() as conn:
        formatted_sql = _fmt(sql, _is_pg(conn))
        rows = conn.execute(formatted_sql, params).fetchall()
        return [dict(r) if hasattr(r, "keys") else r for r in rows]


def _fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with db() as conn:
        formatted_sql = _fmt(sql, _is_pg(conn))
        row = conn.execute(formatted_sql, params).fetchone()
        if not row:
            return None
        return dict(row) if hasattr(row, "keys") else row


def _execute(sql: str, params: tuple = ()) -> None:
    with db() as conn:
        formatted_sql = _fmt(sql, _is_pg(conn))
        conn.execute(formatted_sql, params)


def _insert(sql: str, params: tuple = ()) -> int:
    with db() as conn:
        is_pg = _is_pg(conn)
        formatted_sql = _fmt(sql, is_pg)
        if is_pg and "RETURNING" not in formatted_sql.upper():
            formatted_sql += " RETURNING id"

        cur = conn.execute(formatted_sql, params)
        if hasattr(cur, "returned_row") and cur.returned_row:
            row = cur.returned_row
            return row.get("id", 1) if isinstance(row, dict) else row[0]
        if hasattr(cur, "lastrowid") and cur.lastrowid:
            return cur.lastrowid
        try:
            row = cur.fetchone()
            if row:
                return row[0] if isinstance(row, tuple) else row.get("id", 1)
        except Exception:
            pass
        return 1


# -----------------------------------------------------------------------------
# Views HTML
# -----------------------------------------------------------------------------
@fiscal_pricing_bp.route("/fiscal-pricing/")
@login_required
def index():
    """Dashboard principal do módulo de Precificação Fiscal."""
    batches = _fetch_all("SELECT * FROM fiscal_batches ORDER BY id DESC LIMIT 50")
    total_active_batches = len([b for b in batches if b.get("status") in ["simulacao", "efetivado"]])

    tot_pis_cred = sum(float(b.get("pis_credit_balance", 0) or 0) for b in batches)
    tot_cofins_cred = sum(float(b.get("cofins_credit_balance", 0) or 0) for b in batches)
    tot_icms_cred = sum(float(b.get("icms_credit_balance", 0) or 0) for b in batches)
    tot_ipi_cred = sum(float(b.get("ipi_credit_balance", 0) or 0) for b in batches)

    return render_template(
        "fiscal_pricing/index.html",
        batches=batches,
        total_active_batches=total_active_batches,
        tot_pis_cred=tot_pis_cred,
        tot_cofins_cred=tot_cofins_cred,
        tot_icms_cred=tot_icms_cred,
        tot_ipi_cred=tot_ipi_cred,
        active_tab="dashboard",
    )


@fiscal_pricing_bp.route("/fiscal-pricing/cost-entry")
@login_required
def cost_entry():
    """Interface de entrada de custos e conferência da NF de entrada COLVIX."""
    imports_list = _fetch_all("SELECT id, reference, invoice_no, status, created_at FROM imports ORDER BY id DESC LIMIT 20")
    return render_template("fiscal_pricing/cost_entry.html", imports_list=imports_list, active_tab="cost_entry")


@fiscal_pricing_bp.route("/fiscal-pricing/simulation")
@login_required
def simulation_dual():
    """Simulador comercial comparativo (M-ONE vs PJ Direto)."""
    batches = _fetch_all("SELECT id, batch_code, supplier_name, status FROM fiscal_batches ORDER BY id DESC LIMIT 30")
    return render_template("fiscal_pricing/simulation_dual.html", batches=batches, active_tab="simulation")


@fiscal_pricing_bp.route("/fiscal-pricing/ledger")
@login_required
def credits_ledger():
    """Conta-corrente de créditos fiscais no Lucro Real."""
    batches = _fetch_all("SELECT * FROM fiscal_batches ORDER BY id DESC")
    return render_template("fiscal_pricing/credits_ledger.html", batches=batches, active_tab="ledger")


# -----------------------------------------------------------------------------
# APIs JSON
# -----------------------------------------------------------------------------
@fiscal_pricing_bp.route("/fiscal-pricing/api/parse-xml", methods=["POST"])
@login_required
def api_parse_xml():
    """Upload e parsing de arquivo XML de NF-e da COLVIX."""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "Nenhum arquivo enviado."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Arquivo XML inválido."}), 400

    try:
        content = file.read()
        parsed = parse_nfe_xml(content)
        apportioned = calculate_apportionment(
            items_raw=parsed["items_raw"],
            total_ii_header=parsed["total_ii_val"],
            total_pis_header=parsed["total_pis_val"],
            total_cofins_header=parsed["total_cofins_val"],
            general_expenses_header=parsed["general_expenses_header"],
        )
        return jsonify({"success": True, "data": {**parsed, **apportioned}})
    except Exception as e:
        logger.warning("[API Parse XML Error]: %s", e)
        return jsonify({"success": False, "message": str(e)}), 400


@fiscal_pricing_bp.route("/fiscal-pricing/api/parse-excel", methods=["POST"])
@login_required
def api_parse_excel():
    """Upload e parsing de planilha Excel (.xlsx / .csv) como fonte única de dados."""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "Nenhum arquivo enviado."}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Arquivo inválido."}), 400

    try:
        content = file.read()
        parsed = parse_excel_file(content, file.filename)
        apportioned = calculate_apportionment(
            items_raw=parsed["items_raw"],
            total_ii_header=parsed["total_ii_val"],
            total_pis_header=parsed["total_pis_val"],
            total_cofins_header=parsed["total_cofins_val"],
            general_expenses_header=parsed["general_expenses_header"],
        )
        return jsonify({"success": True, "data": {**parsed, **apportioned}})
    except Exception as e:
        logger.warning("[API Parse Excel Error]: %s", e)
        return jsonify({"success": False, "message": str(e)}), 400


@fiscal_pricing_bp.route("/fiscal-pricing/api/import-detail/<int:import_id>")
@login_required
def api_import_detail(import_id: int):
    """Retorna o rateio fiscal a partir de um lote de importação do M-One."""
    try:
        parsed = parse_mone_import(import_id)
        apportioned = calculate_apportionment(
            items_raw=parsed["items_raw"],
            total_ii_header=parsed["total_ii_val"],
            total_pis_header=parsed["total_pis_val"],
            total_cofins_header=parsed["total_cofins_val"],
            general_expenses_header=parsed["general_expenses_header"],
        )
        return jsonify({"success": True, "data": {**parsed, **apportioned}})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@fiscal_pricing_bp.route("/fiscal-pricing/api/calculate-apportionment", methods=["POST"])
@login_required
def api_calculate_apportionment():
    """Recalcula o rateio proporcional de tributos e despesas a partir do payload JSON."""
    payload = request.get_json(silent=True) or {}
    items_raw = payload.get("items_raw", [])
    total_ii_header = float(payload.get("total_ii_val", 0) or 0)
    total_pis_header = float(payload.get("total_pis_val", 0) or 0)
    total_cofins_header = float(payload.get("total_cofins_val", 0) or 0)
    general_expenses_header = float(payload.get("general_expenses_header", 0) or 0)

    res = calculate_apportionment(
        items_raw=items_raw,
        total_ii_header=total_ii_header,
        total_pis_header=total_pis_header,
        total_cofins_header=total_cofins_header,
        general_expenses_header=general_expenses_header,
    )
    return jsonify({"success": True, "data": res})


@fiscal_pricing_bp.route("/fiscal-pricing/api/save-batch", methods=["POST"])
@login_required
def api_save_batch():
    """Salva ou efetiva um lote fiscal de entrada da COLVIX."""
    payload = request.get_json(silent=True) or {}
    user = current_user()
    user_id = user.get("id") if isinstance(user, dict) else None

    c_row = _fetch_one("SELECT COUNT(*) as c FROM fiscal_batches") or {"c": 0}
    batch_count = c_row.get("c", 0) + 1
    batch_code = payload.get("batch_code") or f"LOTE-COLVIX-{batch_count:03d}"
    totals = payload.get("totals", {})
    items = payload.get("items", [])
    status = payload.get("status", "simulacao")

    batch_id = _insert(
        """
        INSERT INTO fiscal_batches (
            batch_code, source_type, source_ref, supplier_name, invoice_number, invoice_date,
            total_products_val, total_ii_val, total_pis_val, total_cofins_val, total_icms_val, total_ipi_val,
            total_other_expenses_val, total_cost_colvix, pis_credit_initial, pis_credit_balance,
            cofins_credit_initial, cofins_credit_balance, icms_credit_initial, icms_credit_balance,
            ipi_credit_initial, ipi_credit_balance, status, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_code,
            payload.get("source_type", "manual"),
            payload.get("source_ref", ""),
            payload.get("supplier_name", "COLVIX"),
            payload.get("invoice_number", ""),
            payload.get("invoice_date", ""),
            float(totals.get("total_products_val", 0) or 0),
            float(totals.get("total_ii_val", 0) or 0),
            float(totals.get("total_pis_val", 0) or 0),
            float(totals.get("total_cofins_val", 0) or 0),
            float(totals.get("total_icms_val", 0) or 0),
            float(totals.get("total_ipi_val", 0) or 0),
            float(totals.get("total_other_expenses_val", 0) or 0),
            float(totals.get("total_cost_colvix", 0) or 0),
            float(totals.get("pis_credit_initial", 0) or 0),
            float(totals.get("pis_credit_initial", 0) or 0),
            float(totals.get("cofins_credit_initial", 0) or 0),
            float(totals.get("cofins_credit_initial", 0) or 0),
            float(totals.get("icms_credit_initial", 0) or 0),
            float(totals.get("icms_credit_initial", 0) or 0),
            float(totals.get("ipi_credit_initial", 0) or 0),
            float(totals.get("ipi_credit_initial", 0) or 0),
            status,
            user_id,
        ),
    )

    for it in items:
        _execute(
            """
            INSERT INTO fiscal_batch_items (
                batch_id, item_code, description, ncm, quantity, unit_product_val, total_product_val,
                participacao_pct, ii_rateado, pis_rateado, cofins_rateado, other_expenses_rateadas,
                ipi_item, icms_item, total_cost_item, unit_cost_colvix, quantity_remaining
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                it.get("item_code", "ITEM-01"),
                it.get("description", "Produto"),
                it.get("ncm", "87116000"),
                float(it.get("quantity", 1) or 1),
                float(it.get("unit_product_val", 0) or 0),
                float(it.get("total_product_val", 0) or 0),
                float(it.get("participacao_pct", 0) or 0),
                float(it.get("ii_rateado", 0) or 0),
                float(it.get("pis_rateado", 0) or 0),
                float(it.get("cofins_rateado", 0) or 0),
                float(it.get("other_expenses_rateadas", 0) or 0),
                float(it.get("ipi_item", 0) or 0),
                float(it.get("icms_item", 0) or 0),
                float(it.get("total_cost_item", 0) or 0),
                float(it.get("unit_cost_colvix", 0) or 0),
                float(it.get("quantity", 1) or 1),
            ),
        )

    return jsonify({
        "success": True,
        "message": f"Lote Fiscal {batch_code} salvo com sucesso!",
        "batch_id": batch_id,
        "batch_code": batch_code,
    })


@fiscal_pricing_bp.route("/fiscal-pricing/api/simulate", methods=["POST"])
@login_required
def api_simulate():
    """Executa a simulação tributária comparativa e gera o espelho de NF-e."""
    payload = request.get_json(silent=True) or {}
    sim = simulate_commercial_sale(payload)
    mirror = generate_nfe_mirror_data(sim)

    user = current_user()
    user_id = user.get("id") if isinstance(user, dict) else None

    sim_id = _insert(
        """
        INSERT INTO fiscal_simulations (
            batch_id, item_id, title, dest_uf, dest_type, margin_pct, unit_sale_price, qty,
            icms_own_pct, icms_own_val, ipi_sale_pct, ipi_sale_val, pis_sale_pct, pis_sale_val,
            cofins_sale_pct, cofins_sale_val, mva_pct, base_st, icms_st_dest_pct, icms_st_val,
            st_cashflow_saving, colvix_net_tax, colvix_tax_status, op_expenses_pct, op_expenses_val,
            gross_profit, taxable_base_ir_csll, ir_csll_val, net_profit, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("batch_id"),
            payload.get("item_id"),
            payload.get("title", f"Simulação {sim.get('dest_type')} - {sim.get('dest_uf')}"),
            sim["dest_uf"],
            sim["dest_type"],
            sim["margin_pct"],
            sim["unit_sale_price"],
            sim["qty"],
            sim["icms_own_pct"],
            sim["icms_own_val"],
            sim["ipi_sale_pct"],
            sim["ipi_sale_val"],
            sim["pis_sale_pct"],
            sim["pis_sale_val"],
            sim["cofins_sale_pct"],
            sim["cofins_sale_val"],
            sim["mva_pct"],
            sim["base_st"],
            sim["icms_st_dest_pct"],
            sim["icms_st_val"],
            sim["st_cashflow_saving"],
            sim["net_tax_balance"],
            sim["colvix_tax_status"],
            sim["op_expenses_pct"],
            sim["op_expenses_val"],
            sim["gross_profit"],
            sim["taxable_base_ir_csll"],
            sim["ir_csll_val"],
            sim["net_profit"],
            user_id,
        ),
    )

    return jsonify({"success": True, "sim": sim, "mirror": mirror, "sim_id": sim_id})


@fiscal_pricing_bp.route("/fiscal-pricing/api/batch-items/<int:batch_id>")
@login_required
def api_batch_items(batch_id: int):
    """Retorna a lista de itens de um lote fiscal cadastrado."""
    items = _fetch_all("SELECT * FROM fiscal_batch_items WHERE batch_id = ?", (batch_id,))
    return jsonify({"success": True, "items": items})
