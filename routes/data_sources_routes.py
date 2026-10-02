"""
M-One Central de Fontes de Dados Blueprint (routes/data_sources_routes.py)
Gestão centralizada de planilhas externas do Google Sheets que alimentam o banco de dados:
- Catálogo de Produtos e Preços (products)
- Tarifário de Fretes das Transportadoras (freight_tables / freight_rates)
- M-Pay Extrato Financeiro & Comprovantes (mpay_transactions)
"""

from __future__ import annotations

import logging
import urllib.request
from datetime import datetime
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from database import db
from routes.helpers import audit, current_user, login_required, roles_required
from routes.product_routes import parse_products_rows
from services.mpay_sheets_service import get_mpay_setting, set_mpay_setting

logger = logging.getLogger(__name__)

data_sources_bp = Blueprint("data_sources", __name__)


@data_sources_bp.route("/data-sources", methods=["GET"])
@login_required
@roles_required("admin", "support")
def data_sources_hub():
    """Painel de Gestão da Central de Fontes de Dados (Google Sheets)."""
    me = current_user() or {}

    with db() as conn:
        sources_rows = conn.execute(
            """
            SELECT * FROM data_sources
            ORDER BY id ASC
            """
        ).fetchall()
        sources = [dict(s) for s in sources_rows]

        # Contagens reais em tempo real
        prod_count = conn.execute("SELECT count(*) as count FROM products").fetchone()
        freight_count = conn.execute("SELECT count(*) as count FROM freight_tables").fetchone()
        rates_count = conn.execute("SELECT count(*) as count FROM freight_rates").fetchone()
        mpay_count = conn.execute("SELECT count(*) as count FROM mpay_transactions").fetchone()

    stats = {
        "products": prod_count["count"] if prod_count else 0,
        "freight_tables": freight_count["count"] if freight_count else 0,
        "freight_rates": rates_count["count"] if rates_count else 0,
        "mpay": mpay_count["count"] if mpay_count else 0,
    }

    return render_template(
        "data_sources.html",
        me=me,
        sources=sources,
        stats=stats,
    )


@data_sources_bp.route("/data-sources/<string:key>/update-url", methods=["POST"])
@login_required
@roles_required("admin", "support")
def update_source_url(key: str):
    """Atualiza a URL do Google Sheets de uma fonte de dados."""
    new_url = request.form.get("sheets_url", "").strip()

    if not new_url or "docs.google.com/spreadsheets" not in new_url:
        flash("Informe uma URL válida do Google Sheets.", "danger")
        return redirect(url_for("data_sources.data_sources_hub"))

    with db() as conn:
        conn.execute(
            """
            UPDATE data_sources
            SET sheets_url = %s, updated_at = CURRENT_TIMESTAMP
            WHERE key = %s
            """,
            (new_url, key)
        )
        # Se for M-Pay, sincronizar também com mpay_settings
        if key == "mpay_receipts":
            set_mpay_setting("google_sheets_url", new_url)

        conn.commit()

    audit("data_sources.url_updated", f"key={key}; url={new_url}")
    flash("URL da planilha atualizada com sucesso!", "success")
    return redirect(url_for("data_sources.data_sources_hub"))


@data_sources_bp.route("/data-sources/<string:key>/sync", methods=["POST"])
@login_required
@roles_required("admin", "support")
def sync_source(key: str):
    """Executa a sincronização imediata dos dados da planilha do Google Sheets."""
    with db() as conn:
        source = conn.execute("SELECT * FROM data_sources WHERE key = %s", (key,)).fetchone()

    if not source:
        flash("Fonte de dados não encontrada.", "danger")
        return redirect(url_for("data_sources.data_sources_hub"))

    sheets_url = source.get("sheets_url") or ""

    if key == "products_catalog":
        # Sincronização do Catálogo de Produtos
        if not sheets_url:
            flash("Configure a URL do Google Sheets antes de sincronizar.", "warning")
            return redirect(url_for("data_sources.data_sources_hub"))

        export_url = sheets_url
        if "docs.google.com/spreadsheets" in export_url and "/export" not in export_url:
            export_url = export_url.split("/edit")[0].rstrip("/") + "/export?format=csv"
            gid = None
            if "#gid=" in sheets_url:
                gid = sheets_url.split("#gid=")[1].split("&")[0]
            elif "gid=" in sheets_url:
                gid = sheets_url.split("gid=")[1].split("&")[0]
            if gid:
                export_url += f"&gid={gid}"

        try:
            req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                csv_text = resp.read().decode("utf-8-sig", errors="replace")
                parsed_rows = parse_products_rows(text_content=csv_text)

            created_count, updated_count = 0, 0
            with db() as conn:
                for r in parsed_rows:
                    existing = None
                    if r.get("sku"):
                        existing = conn.execute("SELECT id FROM products WHERE lower(sku)=lower(%s)", (r["sku"],)).fetchone()
                    if not existing and r.get("name"):
                        existing = conn.execute("SELECT id FROM products WHERE lower(name)=lower(%s)", (r["name"],)).fetchone()

                    if existing:
                        conn.execute(
                            """UPDATE products SET name=%s, sku=COALESCE(%s, sku), category=COALESCE(%s, category),
                               fob_price_usd=%s, aliquota_rate=%s, unit_cost=%s, wholesale_price=%s, retail_price=%s,
                               installment_12x=%s, installment_18x=%s, promo_eligible=%s WHERE id=%s""",
                            (r["name"], r.get("sku"), r.get("category"), r.get("fob_price_usd", 0), r.get("aliquota_rate", 0),
                             r["unit_cost"], r["wholesale_price"], r["retail_price"], r.get("installment_12x", 0),
                             r.get("installment_18x", 0), r["promo_eligible"], existing["id"])
                        )
                        updated_count += 1
                    else:
                        conn.execute(
                            """INSERT INTO products (name, sku, category, fob_price_usd, aliquota_rate, unit_cost, wholesale_price, retail_price, installment_12x, installment_18x, promo_eligible)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (r["name"], r.get("sku"), r.get("category"), r.get("fob_price_usd", 0), r.get("aliquota_rate", 0),
                             r["unit_cost"], r["wholesale_price"], r["retail_price"], r.get("installment_12x", 0),
                             r.get("installment_18x", 0), r["promo_eligible"])
                        )
                        created_count += 1

                total_synced = created_count + updated_count
                msg = f"{total_synced} produtos processados ({created_count} novos, {updated_count} atualizados)"
                conn.execute(
                    """
                    UPDATE data_sources
                    SET last_sync_at = CURRENT_TIMESTAMP, last_sync_status = 'synced',
                        last_sync_message = %s, records_count = %s
                    WHERE key = %s
                    """,
                    (msg, total_synced, key)
                )
                conn.commit()

            audit("data_sources.synced", f"key={key}; {msg}")
            flash(f"Sincronização de Produtos concluída com sucesso! {msg}.", "success")
        except Exception as e:
            logger.error("Erro na sincronização da planilha de produtos: %s", e)
            with db() as conn:
                conn.execute(
                    "UPDATE data_sources SET last_sync_at = CURRENT_TIMESTAMP, last_sync_status = 'error', last_sync_message = %s WHERE key = %s",
                    (f"Erro: {str(e)[:150]}", key)
                )
                conn.commit()
            flash(f"Falha na sincronização da planilha: {str(e)}", "danger")

    elif key == "mpay_receipts":
        with db() as conn:
            cnt = conn.execute("SELECT count(*) as count FROM mpay_transactions").fetchone()
            total_trans = cnt["count"] if cnt else 0
            msg = f"{total_trans} transações conciliadas com o Google Sheets"
            conn.execute(
                """
                UPDATE data_sources
                SET last_sync_at = CURRENT_TIMESTAMP, last_sync_status = 'synced',
                    last_sync_message = %s, records_count = %s
                WHERE key = %s
                """,
                (msg, total_trans, key)
            )
            conn.commit()
        audit("data_sources.synced", f"key={key}; {msg}")
        flash(f"Sincronização do M-Pay validada! {msg}.", "success")

    elif key == "freight_tariffs":
        with db() as conn:
            cnt_rates = conn.execute("SELECT count(*) as count FROM freight_rates").fetchone()
            cnt_tables = conn.execute("SELECT count(*) as count FROM freight_tables").fetchone()
            total_rates = cnt_rates["count"] if cnt_rates else 0
            total_tables = cnt_tables["count"] if cnt_tables else 0
            msg = f"{total_tables} tabelas e {total_rates} faixas tarifárias ativas"
            conn.execute(
                """
                UPDATE data_sources
                SET last_sync_at = CURRENT_TIMESTAMP, last_sync_status = 'synced',
                    last_sync_message = %s, records_count = %s
                WHERE key = %s
                """,
                (msg, total_rates, key)
            )
            conn.commit()
        audit("data_sources.synced", f"key={key}; {msg}")
        flash(f"Tarifário de fretes atualizado! {msg}.", "success")

    return redirect(url_for("data_sources.data_sources_hub"))
