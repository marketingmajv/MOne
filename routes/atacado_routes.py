"""
M-One MAJ Atacado Blueprint (routes/atacado_routes.py)
Rotas do Catálogo de Atacado (Venda Exclusiva CNPJ) e Painel Administrativo.
Independente do módulo Outlet.
"""

import logging
import os
import re
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from routes.helpers import login_required, roles_required, audit
from services.atacado_service import (
    ensure_atacado_schema,
    get_all_atacado_items,
    get_atacado_item_by_id_or_slug,
    save_atacado_item,
    delete_atacado_item,
    get_atacado_setting,
    set_atacado_setting,
    sync_atacado_catalog
)

atacado_bp = Blueprint("atacado", __name__)
BASE_DIR = Path(__file__).resolve().parent.parent

if os.environ.get("VERCEL"):
    UPLOAD_ATACADO_DIR = Path("/tmp/uploads/atacado")
else:
    UPLOAD_ATACADO_DIR = BASE_DIR / "static" / "img" / "atacado" / "uploads"

try:
    UPLOAD_ATACADO_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    logger.debug("Upload atacado dir mkdir warning: %s", e)


# -------------------------------------------------------------------------
# ROTAS PÚBLICAS DO CATÁLOGO MAJ ATACADO (CNPJ)
# -------------------------------------------------------------------------

@atacado_bp.route("/atacado")
def catalog():
    """Landing Page Pública do Catálogo MAJ Atacado CNPJ."""
    ensure_atacado_schema()
    category = request.args.get("categoria", "").strip()
    search = request.args.get("busca", "").strip()

    items = get_all_atacado_items(status="active", search=search if search else None)
    
    if category and category != "all":
        items = [i for i in items if category.lower() in (i.get("category") or "").lower()]

    raw_wa = get_atacado_setting("whatsapp_number", "5527999999999")
    whatsapp_number = re.sub(r"\D", "", str(raw_wa)) or "5527999999999"
    whatsapp_message = get_atacado_setting(
        "whatsapp_message",
        "Olá! Tenho interesse no modelo {model} no Atacado MAJ Mobilidade (CNPJ) por {price}. Gostaria de solicitar uma cotação/pedido."
    )
    title = get_atacado_setting("atacado_title", "MAJ ATACADO MOBILIDADE")
    total_vehicles = sum(int(i.get("stock_qty") or 0) for i in items)
    subtitle = get_atacado_setting(
        "atacado_subtitle",
        f"Catálogo Oficial de Atacado • {total_vehicles} Veículos Elétricos com Preços Exclusivos para CNPJ"
    )
    urgency_text = get_atacado_setting(
        "atacado_urgency_text",
        "CONDIÇÕES EXCLUSIVAS PARA REVENDEDORES E CNPJ • ESTOQUE À PRONTA ENTREGA"
    )

    all_categories = sorted(list({i.get("category") for i in items if i.get("category")}))

    return render_template(
        "atacado/catalog.html",
        items=items,
        whatsapp_number=whatsapp_number,
        whatsapp_message=whatsapp_message,
        title=title,
        subtitle=subtitle,
        urgency_text=urgency_text,
        all_categories=all_categories,
        total_vehicles=total_vehicles
    )


@atacado_bp.route("/atacado/<identifier>")
def product_detail(identifier):
    """Detalhes de um produto de atacado (JSON ou redirecionamento)."""
    item = get_atacado_item_by_id_or_slug(identifier)
    if not item:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.args.get("format") == "json":
            return jsonify({"success": False, "error": "Produto de atacado não encontrado"}), 404
        flash("Produto não encontrado no Atacado.", "warning")
        return redirect(url_for("atacado.catalog"))

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.args.get("format") == "json":
        return jsonify({"success": True, "item": item})

    return redirect(url_for("atacado.catalog"))


# -------------------------------------------------------------------------
# ROTAS DO PAINEL ADMINISTRATIVO ATACADO (M-ONE)
# -------------------------------------------------------------------------

@atacado_bp.route("/admin/atacado")
@login_required
@roles_required("admin", "support", "finance")
def admin_atacado():
    """Painel de Gerenciamento do Catálogo MAJ Atacado."""
    ensure_atacado_schema()
    status_filter = request.args.get("status", "all")
    search = request.args.get("q", "").strip()

    items = get_all_atacado_items(status=status_filter if status_filter != "all" else None, search=search)
    
    total_qty = sum(int(i.get("stock_qty") or 0) for i in items)
    total_potential_revenue = sum(float(i.get("price_outlet") or 0) * int(i.get("stock_qty") or 0) for i in items)

    settings = {
        "whatsapp_number": get_atacado_setting("whatsapp_number", "5527999999999"),
        "whatsapp_message": get_atacado_setting("whatsapp_message", "Olá! Tenho interesse no modelo {model} no Atacado MAJ por {price}."),
        "atacado_title": get_atacado_setting("atacado_title", "MAJ ATACADO MOBILIDADE"),
        "atacado_subtitle": get_atacado_setting("atacado_subtitle", "Venda Exclusiva CNPJ / Revendedores"),
        "atacado_urgency_text": get_atacado_setting("atacado_urgency_text", "CONDIÇÕES EXCLUSIVAS PARA CNPJ • PARCELAMENTO FACILITADO")
    }

    return render_template(
        "atacado/admin.html",
        items=items,
        settings=settings,
        total_qty=total_qty,
        total_revenue=total_potential_revenue,
        status_filter=status_filter,
        search=search
    )


@atacado_bp.route("/admin/atacado/sync", methods=["POST"])
@login_required
@roles_required("admin", "support", "finance")
def admin_atacado_sync():
    """Sincroniza automaticamente os estoques COLVIX + MAJ e Preços Atacado."""
    try:
        res = sync_atacado_catalog()
        audit("atacado.sync", f"Sincronização de Atacado executada: {res['total_models']} modelos, {res['total_stock']} unidades no estoque.")
        flash(f"Sincronização do Atacado concluída! {res['total_models']} modelos atualizados ({res['total_stock']} veículos em estoque). {res['colvix_sold_units_excluded']} unidades vendidas foram desconsideradas.", "success")
    except Exception as e:
        flash(f"Erro ao sincronizar planilhas de atacado: {str(e)}", "danger")
    return redirect(url_for("atacado.admin_atacado"))


@atacado_bp.route("/admin/atacado/save", methods=["POST"])
@login_required
@roles_required("admin", "support", "finance")
def admin_atacado_save():
    """Cria ou edita um produto no catálogo de atacado."""
    try:
        item_id = request.form.get("item_id")
        item_id = int(item_id) if item_id and item_id.isdigit() else None

        gallery_input = request.form.get("images_gallery")
        if gallery_input and isinstance(gallery_input, str) and gallery_input.strip().startswith("["):
            try:
                gallery_imgs = json.loads(gallery_input)
            except Exception:
                gallery_imgs = request.form.getlist("images_gallery_existing")
        else:
            gallery_imgs = request.form.getlist("images_gallery_existing")

        uploaded_files = request.files.getlist("gallery_files")
        if uploaded_files:
            for file in uploaded_files:
                if file and file.filename:
                    safe_name = f"{slugify(Path(file.filename).stem)}_{int(request.form.get('price_outlet') or 0)}.{file.filename.rsplit('.', 1)[-1].lower()}"
                    dest = UPLOAD_ATACADO_DIR / safe_name
                    file.save(dest)
                    rel_path = f"/static/img/atacado/uploads/{safe_name}"
                    gallery_imgs.append(rel_path)

        main_img = request.form.get("image_main") or request.form.get("image_main_selected")
        if not main_img and gallery_imgs:
            main_img = gallery_imgs[0]

        data = {
            "name": request.form.get("name"),
            "slug": request.form.get("slug"),
            "category": request.form.get("category", "Atacado CNPJ"),
            "condition": request.form.get("condition", "Novo"),
            "color": request.form.get("color", ""),
            "price_original": request.form.get("price_original"),
            "price_outlet": request.form.get("price_outlet"),
            "price_atacado_plus": request.form.get("price_atacado_plus"),
            "installment_12": request.form.get("installment_12"),
            "installment_18": request.form.get("installment_18"),
            "stock_qty": request.form.get("stock_qty"),
            "location": request.form.get("location"),
            "badge": request.form.get("badge"),
            "description": request.form.get("description"),
            "image_main": main_img,
            "images_gallery": gallery_imgs,
            "status": request.form.get("status", "active"),
            "notes": request.form.get("notes")
        }

        saved_id = save_atacado_item(data, item_id=item_id)
        audit("save_atacado_item", f"Item Atacado ID={saved_id} ({data['name']}) salvo com sucesso")
        flash(f"Produto Atacado '{data['name']}' salvo com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao salvar produto de atacado: {str(e)}", "danger")

    return redirect(url_for("atacado.admin_atacado"))


@atacado_bp.route("/admin/atacado/status/<int:item_id>", methods=["POST"])
@login_required
@roles_required("admin", "support")
def admin_atacado_status(item_id):
    """Alterna o status do produto (active, out_of_stock, inactive)."""
    item = get_atacado_item_by_id_or_slug(item_id)
    if item:
        new_status = "inactive" if item["status"] == "active" else "active"
        item["status"] = new_status
        save_atacado_item(item, item_id=item_id)
        audit("toggle_atacado_status", f"Item Atacado ID={item_id} status alterado para {new_status}")
        flash(f"Status de '{item['name']}' alterado para {new_status}.", "info")
    return redirect(url_for("atacado.admin_atacado"))


@atacado_bp.route("/admin/atacado/delete/<int:item_id>", methods=["POST"])
@login_required
@roles_required("admin")
def admin_atacado_delete(item_id):
    """Exclui um produto do catálogo de atacado."""
    item = get_atacado_item_by_id_or_slug(item_id)
    if item:
        delete_atacado_item(item_id)
        audit("delete_atacado_item", f"Item Atacado ID={item_id} ({item['name']}) excluído")
        flash(f"Produto Atacado '{item['name']}' excluído.", "success")
    return redirect(url_for("atacado.admin_atacado"))


@atacado_bp.route("/admin/atacado/settings", methods=["POST"])
@login_required
@roles_required("admin", "support")
def admin_atacado_settings():
    """Salva configurações gerais do catálogo de atacado."""
    set_atacado_setting("whatsapp_number", request.form.get("whatsapp_number", "").strip())
    set_atacado_setting("whatsapp_message", request.form.get("whatsapp_message", "").strip())
    set_atacado_setting("atacado_title", request.form.get("atacado_title", "").strip())
    set_atacado_setting("atacado_subtitle", request.form.get("atacado_subtitle", "").strip())
    set_atacado_setting("atacado_urgency_text", request.form.get("atacado_urgency_text", "").strip())

    flash("Configurações do Atacado salvas com sucesso.", "success")
    return redirect(url_for("atacado.admin_atacado"))
