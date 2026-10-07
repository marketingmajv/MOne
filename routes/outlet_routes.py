"""
M-One Outlet Blueprint (routes/outlet_routes.py)
Rotas do Catálogo Promocional Outlet MAJ Mobilidade e Painel Administrativo.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from routes.helpers import audit, login_required, roles_required
from services.outlet_service import (
    delete_outlet_item,
    ensure_outlet_schema,
    get_all_outlet_items,
    get_outlet_item_by_id_or_slug,
    get_outlet_setting,
    save_outlet_item,
    set_outlet_setting,
    slugify,
)

logger = logging.getLogger(__name__)

outlet_bp = Blueprint("outlet", __name__)
BASE_DIR = Path(__file__).resolve().parent.parent

if os.environ.get("VERCEL"):
    UPLOAD_OUTLET_DIR = Path("/tmp/uploads/outlet")
else:
    UPLOAD_OUTLET_DIR = BASE_DIR / "static" / "img" / "outlet" / "uploads"

try:
    UPLOAD_OUTLET_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    logger.debug("Upload outlet dir mkdir warning: %s", e)


# -------------------------------------------------------------------------
# ROTAS PÚBLICAS DO CATÁLOGO OUTLET
# -------------------------------------------------------------------------

@outlet_bp.route("/outlet")
def catalog():
    """Landing Page Pública do Outlet MAJ Mobilidade."""
    ensure_outlet_schema()
    category = request.args.get("categoria", "").strip()
    search = request.args.get("busca", "").strip()

    items = get_all_outlet_items(status="active", search=search if search else None)
    
    if category and category != "all":
        items = [i for i in items if category.lower() in (i.get("category") or "").lower()]

    # Totalizadores para badges
    total_vehicles = sum(int(i.get("stock_qty") or 0) for i in items)

    raw_wa = get_outlet_setting("whatsapp_number", "5527996051538")
    whatsapp_number = re.sub(r"\D", "", str(raw_wa)) or "5527996051538"
    whatsapp_message = get_outlet_setting(
        "whatsapp_message",
        "Olá! Vi o modelo {model} no Outlet MAJ Mobilidade por {price} e tenho interesse. Ainda está disponível?"
    )
    whatsapp_floating_message = get_outlet_setting(
        "whatsapp_floating_message",
        "Olá! Estou navegando no Outlet MAJ Mobilidade e gostaria de falar com um consultor."
    )
    title = get_outlet_setting("outlet_title", "OUTLET MAJ MOBILIDADE")
    subtitle = get_outlet_setting("outlet_subtitle", f"Queima de Estoque Oficial • Mais de {total_vehicles} Veículos Elétricos com Descontos Exclusivos")
    urgency_text = get_outlet_setting("outlet_urgency_text", "ÚLTIMAS UNIDADES A PRONTA ENTREGA • PARCELAMENTO EM ATÉ 18X")

    # Extrair categorias únicas para filtros
    all_categories = sorted(list({i.get("category") for i in items if i.get("category")}))

    return render_template(
        "outlet/catalog.html",
        items=items,
        whatsapp_number=whatsapp_number,
        whatsapp_message=whatsapp_message,
        whatsapp_floating_message=whatsapp_floating_message,
        title=title,
        subtitle=subtitle,
        urgency_text=urgency_text,
        categories=all_categories,
        current_category=category,
        search_query=search,
        total_vehicles=total_vehicles,
    )


@outlet_bp.route("/outlet/<identifier>")
def product_detail(identifier):
    """Detalhes de um produto específico (retorna JSON para o modal ou página individual)."""
    item = get_outlet_item_by_id_or_slug(identifier)
    if not item:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.args.get("format") == "json":
            return jsonify({"success": False, "error": "Produto não encontrado"}), 404
        flash("Produto não encontrado no Outlet.", "warning")
        return redirect(url_for("outlet.catalog"))

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.args.get("format") == "json":
        return jsonify({"success": True, "item": item})

    return redirect(url_for("outlet.catalog"))


# -------------------------------------------------------------------------
# ROTAS DO PAINEL ADMINISTRATIVO (M-ONE)
# -------------------------------------------------------------------------

@outlet_bp.route("/admin/outlet")
@login_required
@roles_required("admin", "support")
def admin_outlet():
    """Painel de Gestão do Outlet dentro do M-One."""
    ensure_outlet_schema()
    status_filter = request.args.get("status", "all")
    search = request.args.get("q", "").strip()

    items = get_all_outlet_items(status=status_filter if status_filter != "all" else None, search=search)

    # Estatísticas rápidas (Estoque ativo de pronta entrega)
    active_items = [i for i in items if i.get("status") == "active"] if status_filter == "all" else items
    total_qty = sum(int(i.get("stock_qty") or 0) for i in active_items)
    total_active = sum(1 for i in items if i.get("status") == "active")
    total_potential_revenue = sum(float(i.get("price_outlet") or 0) * int(i.get("stock_qty") or 0) for i in active_items)

    settings = {
        "whatsapp_number": get_outlet_setting("whatsapp_number", "5527999999999"),
        "whatsapp_message": get_outlet_setting("whatsapp_message", "Olá! Vi o modelo {model} no Outlet MAJ Mobilidade por {price} e tenho interesse. Ainda está disponível?"),
        "whatsapp_floating_message": get_outlet_setting("whatsapp_floating_message", "Olá! Estou navegando no Outlet MAJ Mobilidade e gostaria de tirar algumas dúvidas com um consultor."),
        "outlet_title": get_outlet_setting("outlet_title", "OUTLET MAJ MOBILIDADE"),
        "outlet_subtitle": get_outlet_setting("outlet_subtitle", "Queima de Estoque Oficial • Mais de 440 Veículos Elétricos"),
        "outlet_urgency_text": get_outlet_setting("outlet_urgency_text", "ÚLTIMAS UNIDADES A PRONTA ENTREGA • PARCELAMENTO EM ATÉ 18X"),
        "outlet_last_sync_at": get_outlet_setting("outlet_last_sync_at", ""),
        "outlet_last_sync_summary": get_outlet_setting("outlet_last_sync_summary", ""),
    }

    return render_template(
        "outlet/admin.html",
        items=items,
        total_qty=total_qty,
        total_active=total_active,
        total_revenue=total_potential_revenue,
        settings=settings,
        current_status=status_filter,
        search_query=search,
    )




@outlet_bp.route("/admin/outlet/save", methods=["POST"])
@login_required
@roles_required("admin", "support")
def save_item():
    """Salva ou atualiza um item no catálogo do Outlet."""
    try:
        item_id = request.form.get("item_id")
        item_id = int(item_id) if item_id and item_id.isdigit() else None

        # Galeria de fotos adicionais
        gallery_raw = request.form.get("images_gallery", "[]")
        try:
            gallery = json.loads(gallery_raw) if gallery_raw else []
        except Exception:
            gallery = [img.strip() for img in gallery_raw.split("\n") if img.strip()]

        # Ficha técnica JSON
        specs_raw = request.form.get("specs_json", "{}")
        try:
            specs = json.loads(specs_raw) if specs_raw else {}
        except Exception:
            specs = {}

        data = {
            "name": request.form.get("name"),
            "slug": slugify(request.form.get("slug") or request.form.get("name")),
            "category": request.form.get("category"),
            "condition": request.form.get("condition"),
            "color": request.form.get("color"),
            "price_original": request.form.get("price_original"),
            "price_outlet": request.form.get("price_outlet"),
            "installment_12": request.form.get("installment_12"),
            "installment_18": request.form.get("installment_18"),
            "installments_text": request.form.get("installments_text"),
            "stock_qty": request.form.get("stock_qty"),
            "location": request.form.get("location"),
            "badge": request.form.get("badge"),
            "description": request.form.get("description"),
            "image_main": request.form.get("image_main"),
            "images_gallery": gallery,
            "specs_json": specs,
            "status": request.form.get("status", "active"),
            "sort_order": request.form.get("sort_order", 0),
            "notes": request.form.get("notes"),
        }

        # Upload de foto principal se enviada via arquivo
        if "main_image_file" in request.files:
            f = request.files["main_image_file"]
            if f and f.filename:
                try:
                    UPLOAD_OUTLET_DIR.mkdir(parents=True, exist_ok=True)
                    safe_name = f"main_{slugify(data['name'])}_{secure_filename(f.filename)}"
                    f.save(UPLOAD_OUTLET_DIR / safe_name)
                    data["image_main"] = f"/static/img/outlet/uploads/{safe_name}"
                except Exception as upload_err:
                    logger.warning("Falha ao salvar no disco (%s). Convertendo para Base64 Data URL.", upload_err)
                    try:
                        f.seek(0)
                        raw_bytes = f.read()
                        mime = f.mimetype or "image/jpeg"
                        b64_str = base64.b64encode(raw_bytes).decode("utf-8")
                        data["image_main"] = f"data:{mime};base64,{b64_str}"
                    except Exception as b64_err:
                        logger.error("Erro ao converter arquivo para Base64 Data URL: %s", b64_err)

        saved_id = save_outlet_item(data, item_id=item_id)
        audit("save_outlet_item", f"Item Outlet ID={saved_id} ({data['name']}) salvo com sucesso")
        flash(f"Produto '{data['name']}' salvo com sucesso no Outlet!", "success")
    except Exception as e:
        logger.exception("Erro ao salvar item no Outlet: %s", e)
        flash(f"Ocorreu um erro ao salvar o produto: {str(e)}", "danger")

    return redirect(url_for("outlet.admin_outlet"))


@outlet_bp.route("/admin/outlet/status/<int:item_id>", methods=["POST"])
@login_required
@roles_required("admin", "support")
def toggle_status(item_id):
    """Altera rapidamente o status do item (active, sold_out, hidden)."""
    new_status = request.form.get("status") or request.json.get("status") if request.is_json else None
    item = get_outlet_item_by_id_or_slug(item_id)
    if not item:
        return jsonify({"success": False, "error": "Item não encontrado"}), 404

    if not new_status:
        new_status = "sold_out" if item.get("status") == "active" else "active"

    item["status"] = new_status
    save_outlet_item(item, item_id=item_id)
    audit("toggle_outlet_status", f"Item ID={item_id} status alterado para {new_status}")
    
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "new_status": new_status})
    flash(f"Status atualizado para '{new_status}'!", "success")
    return redirect(url_for("outlet.admin_outlet"))


@outlet_bp.route("/admin/outlet/delete/<int:item_id>", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_item(item_id):
    """Exclui um item do Outlet."""
    item = get_outlet_item_by_id_or_slug(item_id)
    name = item.get("name") if item else str(item_id)
    delete_outlet_item(item_id)
    audit("delete_outlet_item", f"Item Outlet ID={item_id} ({name}) excluído")
    flash(f"Item '{name}' removido do Outlet com sucesso.", "info")
    return redirect(url_for("outlet.admin_outlet"))


@outlet_bp.route("/admin/outlet/settings", methods=["POST"])
@login_required
@roles_required("admin", "support")
def update_settings():
    """Atualiza as configurações do WhatsApp e textos do Outlet."""
    set_outlet_setting("whatsapp_number", request.form.get("whatsapp_number", "").strip())
    set_outlet_setting("whatsapp_message", request.form.get("whatsapp_message", "").strip())
    set_outlet_setting("whatsapp_floating_message", request.form.get("whatsapp_floating_message", "").strip())
    set_outlet_setting("outlet_title", request.form.get("outlet_title", "").strip())
    set_outlet_setting("outlet_subtitle", request.form.get("outlet_subtitle", "").strip())
    set_outlet_setting("outlet_urgency_text", request.form.get("outlet_urgency_text", "").strip())

    audit("update_outlet_settings", "Configurações gerais do Outlet MAJ atualizadas")
    flash("Configurações do Outlet salvas com sucesso!", "success")
    return redirect(url_for("outlet.admin_outlet"))


@outlet_bp.route("/admin/outlet/sync", methods=["POST"])
@login_required
@roles_required("admin", "support")
def sync_outlet():
    """Dispara a sincronização entre a tabela CSV e o banco de dados Supabase."""
    try:
        from services.outlet_service import sync_outlet_from_csv
        result = sync_outlet_from_csv()
        audit(
            "sync_outlet_catalog",
            f"Sincronização manual do catálogo de Outlet: {result.get('synced_count', 0)} modelos, estoque {result.get('total_stock', 0)}"
        )
        flash(
            f"Catálogo do Outlet sincronizado com sucesso! {result.get('synced_count', 0)} modelos atualizados ({result.get('total_stock', 0)} veículos em estoque).",
            "success"
        )
    except Exception as e:
        logger.exception("Erro ao sincronizar outlet: %s", e)
        flash(f"Erro ao sincronizar catálogo do Outlet: {e}", "danger")
    return redirect(url_for("outlet.admin_outlet"))


@outlet_bp.route("/admin/outlet/spreadsheet")
@login_required
@roles_required("admin", "support", "finance")
def view_spreadsheet():
    """Retorna a planilha/tabela CSV oficial do Outlet para visualização direta no navegador."""
    from flask import Response, send_file
    import urllib.request

    csv_path = BASE_DIR / "uploads" / "outlet" / "tabela_precos_outlet.csv"
    if csv_path.exists():
        return send_file(
            str(csv_path),
            mimetype="text/csv; charset=utf-8",
            as_attachment=False,
            download_name="tabela_precos_outlet.csv"
        )

    # Fallback seguro para Vercel Serverless buscando diretamente do repositório
    try:
        url = "https://raw.githubusercontent.com/marketingmajv/MOne/main/uploads/outlet/tabela_precos_outlet.csv"
        with urllib.request.urlopen(url, timeout=10) as resp:
            content = resp.read()
        return Response(
            content,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "inline; filename=tabela_precos_outlet.csv"}
        )
    except Exception as e:
        logger.warning("Não foi possível carregar o CSV do Outlet: %s", e)
        flash("Arquivo de planilha oficial do Outlet não encontrado no momento.", "warning")
        return redirect(url_for("outlet.admin_outlet"))


@outlet_bp.route("/cron/outlet-sync", methods=["GET", "POST"])
@outlet_bp.route("/admin/outlet/cron-sync", methods=["GET", "POST"])
@outlet_bp.route("/api/cron/outlet-sync", methods=["GET", "POST"])
def cron_sync_outlet():
    """
    Endpoint executado automaticamente a cada hora via Vercel Cron (0 * * * *).
    Executa a mesma rotina de sincronização do botão 'Sync CSV',
    atualizando estoques e preços sem resetar o banco de dados.
    """
    try:
        from services.outlet_service import sync_outlet_from_csv
        result = sync_outlet_from_csv()
        logger.info("[Vercel Cron Outlet] Sincronização horária executada com sucesso: %s", result)
        audit(
            "cron_sync_outlet",
            f"Sincronização automática horária do Outlet: {result.get('synced_count', 0)} modelos, estoque {result.get('total_stock', 0)}"
        )
        return jsonify({
            "status": "success",
            "message": "Outlet sincronizado com sucesso",
            "synced_count": result.get("synced_count", 0),
            "total_stock": result.get("total_stock", 0)
        }), 200
    except Exception as e:
        logger.exception("[Vercel Cron Outlet] Erro na sincronização horária: %s", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500



