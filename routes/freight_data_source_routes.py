"""
M-One Freight Data Source Blueprint (routes/freight_data_source_routes.py)
Rotas de sincronização, atualização de link e ajuste manual da fonte de dados de veículos e dimensões.
"""

from __future__ import annotations

import logging
from pathlib import Path
from flask import Blueprint, flash, jsonify, redirect, request, send_from_directory, url_for

from database import db
from routes.helpers import UPLOAD_DIR, audit, login_required, roles_required
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
        r_price_raw = request.form.get("retail_price")
        r_price = float(r_price_raw) if r_price_raw not in (None, "") else None

        with db() as conn:
            update_product_specs(conn, pid, w_kg, l_cm, wi_cm, h_cm, w_price, r_price)
            audit("freight.product_specs_updated", f"id={pid}; w={w_kg}; {wi_cm}x{h_cm}x{l_cm}; w_price={w_price}; r_price={r_price}")
            flash("Medidas e preço do veículo atualizados com sucesso!", "success")
    except Exception as e:
        logger.error("Erro ao atualizar especificações do produto %s: %s", pid, e)
        flash(f"Erro ao salvar alterações: {e}", "danger")

    return redirect(url_for("freight", tab="data-sources"))


@freight_data_source_bp.route("/freight/tables/<int:table_id>/download")
@login_required
def freight_table_download(table_id: int):
    """Download seguro da planilha oficial de frete vinculada à tabela."""
    with db() as conn:
        row = conn.execute("SELECT file_url, name FROM freight_tables WHERE id = %s", (table_id,)).fetchone()
    
    if not row or not row["file_url"]:
        flash("Planilha oficial não vinculada a esta tabela.", "warning")
        return redirect(url_for("freight", tab="carriers"))
    
    filename = str(row["file_url"]).strip()
    if filename.startswith("http://") or filename.startswith("https://"):
        return redirect(filename)
    file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        # Fallback para pasta local do Google Drive
        drive_base = Path("/Users/macstudio-maj/Library/CloudStorage/GoogleDrive-marketingmajv@gmail.com/Meu Drive/M-ONE/FRETE")
        for sub in ["TRASPORTADORAS CADASTRADAS", "PARA CADASTRAR", ""]:
            cand = drive_base / sub / filename
            if cand.exists():
                file_path = cand
                break
    
    if not file_path.exists():
        flash("Arquivo da planilha não encontrado no servidor.", "danger")
        return redirect(url_for("freight", tab="carriers"))
    
    clean_name = "".join(c for c in str(row["name"]) if c.isalnum() or c in ("-", "_")).strip() or f"tabela_{table_id}"
    download_filename = f"{clean_name}{file_path.suffix}"
    
    return send_from_directory(
        directory=file_path.parent,
        path=file_path.name,
        as_attachment=True,
        download_name=download_filename
    )


@freight_data_source_bp.route("/freight/tables/<int:table_id>/generate-google-sheet", methods=["POST"])
@login_required
@roles_required("admin", "support")
def freight_table_generate_sheet(table_id: int):
    """Gera e sincroniza a planilha oficial no Google Planilhas sob demanda."""
    try:
        with db() as conn:
            t_row = conn.execute(
                """SELECT t.id, t.name AS table_name, c.name AS carrier_name 
                   FROM freight_tables t 
                   JOIN carriers c ON c.id = t.carrier_id 
                   WHERE t.id = %s""",
                (table_id,)
            ).fetchone()
        if not t_row:
            return jsonify({"success": False, "message": "Tabela não encontrada."}), 404

        from services.freight_google_drive_sync_service import auto_create_and_link_google_sheet
        sheet_url = auto_create_and_link_google_sheet(table_id, t_row["carrier_name"], t_row["table_name"])
        if sheet_url:
            audit("freight.sheet_generated", f"table_id={table_id}; url={sheet_url}")
            return jsonify({"success": True, "message": "Google Planilha gerada com sucesso!", "sheet_url": sheet_url})
        return jsonify({"success": False, "message": "Não foi possível gerar a planilha no Google Drive."}), 500
    except Exception as e:
        logger.error("Erro ao gerar Google Planilha sob demanda: %s", e)
        return jsonify({"success": False, "message": str(e)}), 500


