"""
M-One Freight Data Source Blueprint (routes/freight_data_source_routes.py)
Rotas de sincronização, atualização de link e ajuste manual da fonte de dados de veículos e dimensões.
"""

from __future__ import annotations

import logging
from flask import Blueprint, flash, redirect, request, url_for

from database import db
from routes.helpers import audit, login_required, roles_required
from services.freight_data_source_service import (
    sync_products_sheets,
    update_product_specs,
)

logger = logging.getLogger(__name__)

freight_data_source_bp = Blueprint("freight_data_source", __name__)


@freight_data_source_bp.route("/freight/data-sources/sync", methods=["POST"])
@login_required
@roles_required("admin", "support", "stock")
def sync_products_data_source():
    """Dispara a sincronização mestre da planilha de produtos e dimensões do Google Sheets."""
    with db() as conn:
        try:
            res = sync_products_sheets(conn)
            audit("freight.products_synced", res.get("message", ""))
            flash(f"Sincronização concluída com sucesso! {res.get('message', '')}", "success")
        except Exception as e:
            logger.error("Erro na sincronização de fretes/produtos: %s", e)
            flash(f"Falha na sincronização da planilha: {e}", "danger")

    return redirect(url_for("freight", tab="data-sources"))


@freight_data_source_bp.route("/freight/data-sources/update-url", methods=["POST"])
@login_required
@roles_required("admin", "support")
def update_products_sheets_url():
    """Atualiza a URL do Google Sheets vinculada ao catálogo de produtos/dimensões."""
    new_url = (request.form.get("sheets_url") or "").strip()
    if not new_url or "docs.google.com/spreadsheets" not in new_url:
        flash("Informe uma URL válida do Google Sheets.", "danger")
    else:
        with db() as conn:
            conn.execute(
                """
                UPDATE data_sources
                SET sheets_url = %s, updated_at = CURRENT_TIMESTAMP
                WHERE key = 'products_catalog'
                """,
                (new_url,)
            )
            conn.commit()
            audit("freight.sheets_url_updated", new_url)
            flash("Link da planilha oficial atualizado com sucesso!", "success")

    return redirect(url_for("freight", tab="data-sources"))


@freight_data_source_bp.route("/freight/products/<int:pid>/quick-edit", methods=["POST"])
@login_required
@roles_required("admin", "support", "stock")
def quick_edit_product_specs(pid: int):
    """Ajuste rápido manual de medidas de caixa e peso de um produto."""
    try:
        w_kg = float(request.form.get("weight_kg") or 0)
        l_cm = float(request.form.get("length_cm") or 0)
        wi_cm = float(request.form.get("width_cm") or 0)
        h_cm = float(request.form.get("height_cm") or 0)
        w_price = float(request.form.get("wholesale_price") or 0)

        with db() as conn:
            update_product_specs(conn, pid, w_kg, l_cm, wi_cm, h_cm, w_price)
            audit("freight.product_specs_updated", f"id={pid}; w={w_kg}; {wi_cm}x{h_cm}x{l_cm}; w_price={w_price}")
            flash("Medidas e preço do veículo atualizados com sucesso!", "success")
    except Exception as e:
        logger.error("Erro ao atualizar especificações do produto %s: %s", pid, e)
        flash(f"Erro ao salvar alterações: {e}", "danger")

    return redirect(url_for("freight", tab="data-sources"))
