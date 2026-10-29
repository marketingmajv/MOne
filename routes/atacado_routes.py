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

def _render_atacado_catalog(show_prices=True):
    """Função auxiliar para renderizar o catálogo de atacado (com ou sem preços)."""
    ensure_atacado_schema()
    category = request.args.get("categoria", "").strip()
    search = request.args.get("busca", "").strip()

    items = get_all_atacado_items(status="active", search=search if search else None, only_available=True)
    
    if category and category != "all":
        items = [i for i in items if category.lower() in (i.get("category") or "").lower()]

    raw_wa = get_atacado_setting("whatsapp_number", "5527996051538")
    whatsapp_number = re.sub(r"\D", "", str(raw_wa)) or "5527996051538"
    
    if show_prices:
        whatsapp_message = get_atacado_setting(
            "whatsapp_message",
            "Olá! Tenho interesse no modelo {model} no Atacado MAJ Mobilidade (CNPJ) por {price} (valor a partir de 3 unidades). Gostaria de solicitar uma cotação/pedido."
        )
    else:
        whatsapp_message = "Olá! Tenho interesse no modelo {model} no Catálogo de Atacado MAJ Mobilidade (CNPJ). Gostaria de solicitar uma cotação."

    whatsapp_floating_message = get_atacado_setting(
        "whatsapp_floating_message",
        "Olá! Estou navegando no Catálogo MAJ Atacado (CNPJ) e gostaria de falar com um consultor comercial de vendas no atacado."
    )
    title = get_atacado_setting("atacado_title", "MAJ ATACADO MOBILIDADE")
    total_vehicles = sum(int(i.get("stock_qty") or 0) for i in items)
    
    if show_prices:
        subtitle = get_atacado_setting(
            "atacado_subtitle",
            "Catálogo Oficial de Atacado • Modelos Elétricos com Condições e Preços Exclusivos para CNPJ"
        )
    else:
        subtitle = "Catálogo Oficial de Atacado • Mostruário CNPJ para Revendedores e Frotas"

    urgency_text = get_atacado_setting(
        "atacado_urgency_text",
        "CONDIÇÕES EXCLUSIVAS PARA REVENDEDORES E CNPJ • MODELOS A PRONTA ENTREGA"
    )
    min_qty_text = get_atacado_setting(
        "atacado_min_qty_text",
        "Valor a partir de 3 unidades"
    )

    all_categories = sorted(list({i.get("category") for i in items if i.get("category")}))

    return render_template(
        "atacado/catalog.html",
        items=items,
        whatsapp_number=whatsapp_number,
        whatsapp_message=whatsapp_message,
        whatsapp_floating_message=whatsapp_floating_message,
        title=title,
        subtitle=subtitle,
        urgency_text=urgency_text,
        min_qty_text=min_qty_text,
        all_categories=all_categories,
        total_vehicles=total_vehicles,
        show_prices=show_prices
    )


@atacado_bp.route("/atacado")
def catalog():
    """Landing Page Pública do Catálogo MAJ Atacado CNPJ (Com Preço ou Sem Preço via query param)."""
    sem_preco = request.args.get("sem_preco", "").lower() in ["1", "true", "sim", "yes"] or request.args.get("hide_prices", "").lower() in ["1", "true", "sim", "yes"]
    return _render_atacado_catalog(show_prices=not sem_preco)


@atacado_bp.route("/atacado/sem-preco")
@atacado_bp.route("/atacado-sem-preco")
@atacado_bp.route("/atacado/catalogo-sem-preco")
def catalog_no_prices():
    """Landing Page Pública do Catálogo MAJ Atacado CNPJ sem Exibição de Preços."""
    return _render_atacado_catalog(show_prices=False)



def _enrich_atacado_v2_items(items):
    """Enriquece itens com margem estimada, enquadramento em trilhas, métricas Wh e diferenciais técnicos."""
    CAMPEOES_SLUGS = {"max-12", "flow-one", "m2", "classic-1000", "gp1000", "classic"}
    ENTRADA_SLUGS = {"v8-mini-ultra", "ride-on", "v20-ultra", "v80-pro", "m9-pro", "m50-pro"}
    AUTONOMIA_SLUGS = {"rz-110", "vittoria", "nova", "x15-pro", "db-zero", "sport-701-short"}

    DIFFERENTIATORS_DEFAULT = {
        "max-12": "🎁 Baú Incluso de Fábrica",
        "v20-ultra": "🛞 Pneus Fat Tire 20x4.0",
        "m9-pro": "☕ Estilo Café Racer Vintage",
        "flow-one": "🎁 Baú Porta-Capacete Espaçoso",
        "ride-on": "⚡ Chassi Ultraleve e Ágil",
        "m2": "🎁 Baú Incluso de Fábrica",
        "vittoria": "🎁 Baú Clássico Incluso",
        "gp1000": "⚡ Sistema 72V 30Ah",
        "v80-pro": "🛡️ Quadro Reforçado Ergonômico",
        "jm-125": "🚀 Super Motor 3000W",
        "nova": "🔑 Partida Keyless + Alarme",
        "x15-pro": "🏎️ Duplo Amortecedor Reforçado",
        "mantis": "🏁 Chassi Esportivo Firme",
        "classic-1000": "🎁 Baú Retrô Incluso",
        "v8-mini-ultra": "🚲 Quadro Baixo Step-Through",
        "rz-110": "💡 Faróis Ultra Potentes",
        "m50-pro": "✈️ Alumínio Aeroespacial",
        "db-zero": "🛸 Design Futurista Silver Black",
        "sport-701-short": "🏁 Suspensão Invertida Esportiva",
        "q8": "🧺 Quadro Rebaixado Conforto",
    }
    
    WH_LOOKUP = {
        "flow-one": 1440, "m2": 1440, "gp1000": 2160, "vittoria": 1440, "classic-1000": 1440,
        "rz-110": 1440, "max-12": 1200, "nova": 1200, "x15-pro": 1200, "db-zero": 1200,
        "v20-ultra": 960, "ride-on": 960, "m9-pro": 960, "v80-pro": 960, "v8-mini-ultra": 720, "m50-pro": 960,
        "mantis": 1200, "jm-125": 1440
    }

    for item in items:
        slug = (item.get("slug") or "").lower().strip()
        p_out = float(item.get("price_outlet") or 0)
        p_orig = float(item.get("price_original") or 0)
        
        # Patamares de desconto escalonado por volume
        item["price_tier_1"] = p_out
        item["price_tier_2"] = max(0.0, round(p_out - 100.0, 2))
        item["price_tier_3"] = max(0.0, round(p_out - 200.0, 2))

        if p_orig > p_out and p_out > 0:
            margin_reais = round(p_orig - p_out, 2)
            # Margem Bruta Real calculada sobre o preço de venda sugerido (varejo)
            margin_pct = int(round((margin_reais / p_orig) * 100))
        else:
            margin_pct = 30 if p_out > 0 else 0
            p_orig = round(p_out / 0.70, 2) if p_out > 0 else 0
            margin_reais = round(p_orig - p_out, 2) if p_out > 0 else 0
            
        item["margin_reais"] = margin_reais
        item["margin_percent"] = margin_pct
        item["price_retail_suggested"] = p_orig
        
        if slug in CAMPEOES_SLUGS:
            item["track"] = "campeoes"
        elif slug in ENTRADA_SLUGS:
            item["track"] = "entrada"
        elif slug in AUTONOMIA_SLUGS:
            item["track"] = "autonomia"
        else:
            if p_out <= 5500:
                item["track"] = "entrada"
            elif p_out <= 7700:
                item["track"] = "campeoes"
            else:
                item["track"] = "autonomia"
                
        raw_badge = (item.get("badge") or "").strip()
        if raw_badge and raw_badge not in ["VENDA ATACADO CNPJ", "EXCLUSIVO CNPJ", "NOVO"]:
            item["differentiator"] = raw_badge
        else:
            item["differentiator"] = DIFFERENTIATORS_DEFAULT.get(slug, "⚡ Pronta Entrega Brasil")

        item["has_trunk"] = any(w in item["differentiator"].lower() for w in ["baú", "bau", "porta-capacete"])
        item["battery_wh"] = WH_LOOKUP.get(slug, 1200)

        # Mapeamento do tipo de veículo (Scooter vs Bike)
        BIKE_SLUGS = {"m9-pro", "m50-pro", "v20-ultra", "v8-mini-ultra", "v80-pro"}
        if slug in BIKE_SLUGS or "bike" in (item.get("category") or "").lower() or "bike" in slug:
            item["vehicle_type"] = "bike"
            item["category_display"] = "Bike Elétrica"
        else:
            item["vehicle_type"] = "scooter"
            item["category_display"] = "Scooter Elétrica"

        item["is_best_seller"] = bool(item.get("is_best_seller"))

        # Garantir fotos limpas (evitar base64 pesado no DOM) e galeria íntegra
        main_img = item.get("image_main")
        if not main_img or str(main_img).startswith("data:"):
            main_img = f"https://raw.githubusercontent.com/marketingmajv/MOne/main/public/images/{slug}/{slug}-01.jpg"
            item["image_main"] = main_img

        gal = item.get("images_gallery")
        if isinstance(gal, str):
            try: gal = json.loads(gal)
            except Exception: gal = []
        if not isinstance(gal, list): gal = []
        # Limpar fotos base64 da galeria substituindo pela foto principal limpa
        gal = [img for img in gal if img and not str(img).startswith("data:")]
        if main_img and main_img not in gal:
            gal = [main_img] + gal
        item["images_gallery"] = gal

    return items


@atacado_bp.route("/atacado/v2")
@atacado_bp.route("/catalogo-cnpj/v2")
@atacado_bp.route("/atacado/v2-preview")
def catalog_v2():
    """Visualização da V2 para consulta interna/local (?preview=1 ou /atacado/v2-preview)."""
    if not request.args.get("preview") and request.path != "/atacado/v2-preview":
        return redirect(url_for("atacado.catalog"), code=302)
    ensure_atacado_schema()
    items = _enrich_atacado_v2_items([i for i in get_all_atacado_items(status="active", only_available=True) if float(i.get("price_outlet") or 0) > 0])
    raw_wa = get_atacado_setting("whatsapp_number", "5527996051538")
    return render_template(
        "atacado/catalog_v2.html", items=items,
        track_campeoes=[i for i in items if i.get("track") == "campeoes"],
        track_entrada=[i for i in items if i.get("track") == "entrada"],
        track_autonomia=[i for i in items if i.get("track") == "autonomia"],
        whatsapp_number=re.sub(r"\D", "", str(raw_wa)) or "5527996051538",
        min_qty_text=get_atacado_setting("atacado_min_qty_text", "Valor a partir de 3 unidades"),
        title="MAJ ATACADO B2B • CONSULTA V2",
        subtitle="Condições Exclusivas para Revendedores & Lojistas CNPJ",
        total_vehicles=sum(int(i.get("stock_qty") or 0) for i in items)
    )


@atacado_bp.route("/atacado/v3")
@atacado_bp.route("/catalogo-cnpj/v3")
def catalog_v3():
    """Nova Versão Atacado B2B v3: Base sólida do Atacado original com evolução progressiva de elementos da V2."""
    ensure_atacado_schema()
    items = _enrich_atacado_v2_items(get_all_atacado_items(status="active", only_available=True))
    raw_wa = get_atacado_setting("whatsapp_number", "5527996051538")
    whatsapp_number = re.sub(r"\D", "", str(raw_wa)) or "5527996051538"
    whatsapp_message = get_atacado_setting("whatsapp_message", "Olá! Tenho interesse no modelo {model} no Atacado MAJ Mobilidade (CNPJ) por {price} (valor a partir de 3 unidades). Gostaria de solicitar uma cotação/pedido.")
    whatsapp_floating_message = get_atacado_setting("whatsapp_floating_message", "Olá! Estou navegando no Catálogo MAJ Atacado (CNPJ) e gostaria de falar com um consultor comercial de vendas no atacado.")
    return render_template(
        "atacado/catalog_v3.html", items=items, whatsapp_number=whatsapp_number,
        whatsapp_message=whatsapp_message, whatsapp_floating_message=whatsapp_floating_message,
        title=get_atacado_setting("atacado_title", "MAJ ATACADO MOBILIDADE"),
        subtitle=get_atacado_setting("atacado_subtitle", "Catálogo Oficial de Atacado • Modelos Elétricos com Condições e Preços Exclusivos para CNPJ"),
        urgency_text=get_atacado_setting("atacado_urgency_text", "CONDIÇÕES EXCLUSIVAS PARA REVENDEDORES E CNPJ • MODELOS A PRONTA ENTREGA"),
        min_qty_text=get_atacado_setting("atacado_min_qty_text", "Valor a partir de 3 unidades"),
        all_categories=sorted(list({i.get("category") for i in items if i.get("category")})),
        show_prices=True,
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
    items = _enrich_atacado_v2_items(items)
    
    total_qty = sum(int(i.get("stock_qty") or 0) for i in items)
    total_potential_revenue = sum(float(i.get("price_outlet") or 0) * int(i.get("stock_qty") or 0) for i in items)

    settings = {
        "whatsapp_number": get_atacado_setting("whatsapp_number", "5527996051538"),
        "whatsapp_message": get_atacado_setting("whatsapp_message", "Olá! Tenho interesse no modelo {model} no Atacado MAJ Mobilidade (CNPJ) por {price} (valor a partir de 3 unidades). Gostaria de solicitar uma cotação/pedido."),
        "whatsapp_floating_message": get_atacado_setting("whatsapp_floating_message", "Olá! Estou navegando no Catálogo MAJ Atacado (CNPJ) e gostaria de falar com um consultor comercial de vendas no atacado."),
        "atacado_title": get_atacado_setting("atacado_title", "MAJ ATACADO MOBILIDADE"),
        "atacado_subtitle": get_atacado_setting("atacado_subtitle", "Catálogo Oficial de Atacado • Veículos Elétricos com Preços Exclusivos para CNPJ"),
        "atacado_urgency_text": get_atacado_setting("atacado_urgency_text", "CONDIÇÕES EXCLUSIVAS PARA REVENDEDORES E CNPJ • ESTOQUE À PRONTA ENTREGA"),
        "atacado_min_qty_text": get_atacado_setting("atacado_min_qty_text", "Valor a partir de 3 unidades")
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
            "show_on_demand": request.form.get("show_on_demand") in ["1", "true", "on", True],
            "is_best_seller": request.form.get("is_best_seller") in ["1", "true", "on", True],
            "location": request.form.get("location"),
            "badge": request.form.get("badge") or request.form.get("differentiator"),
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


@atacado_bp.route("/admin/atacado/toggle-on-demand/<int:item_id>", methods=["POST"])
@login_required
@roles_required("admin", "support")
def admin_atacado_toggle_on_demand(item_id):
    """Ativa ou desativa a exibição do produto como Sob Encomenda se o estoque estiver zerado."""
    from services.atacado_service import toggle_atacado_show_on_demand
    new_val = toggle_atacado_show_on_demand(item_id)
    audit("toggle_atacado_on_demand", f"Item Atacado ID={item_id} show_on_demand alterado para {new_val}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "show_on_demand": new_val})
    flash("Disponibilidade sob encomenda atualizada com sucesso!", "success")
    return redirect(url_for("atacado.admin_atacado"))


@atacado_bp.route("/admin/atacado/toggle-best-seller/<int:item_id>", methods=["POST"])
@login_required
@roles_required("admin", "support")
def admin_atacado_toggle_best_seller(item_id):
    """Alterna o destaque de Mais Vendido do produto no catálogo de atacado."""
    from services.atacado_service import toggle_atacado_best_seller
    new_val = toggle_atacado_best_seller(item_id)
    audit("toggle_atacado_best_seller", f"Item Atacado ID={item_id} is_best_seller alterado para {new_val}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "is_best_seller": new_val})
    flash("Destaque Mais Vendido atualizado!", "success")
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
    raw_wa = request.form.get("whatsapp_number", "").strip()
    clean_wa = re.sub(r"\D", "", raw_wa) or "5527996051538"
    
    set_atacado_setting("whatsapp_number", clean_wa)
    set_atacado_setting("whatsapp_message", request.form.get("whatsapp_message", "").strip())
    set_atacado_setting("whatsapp_floating_message", request.form.get("whatsapp_floating_message", "").strip())
    set_atacado_setting("atacado_title", request.form.get("atacado_title", "").strip())
    set_atacado_setting("atacado_subtitle", request.form.get("atacado_subtitle", "").strip())
    set_atacado_setting("atacado_urgency_text", request.form.get("atacado_urgency_text", "").strip())
    set_atacado_setting("atacado_min_qty_text", request.form.get("atacado_min_qty_text", "").strip() or "Valor a partir de 3 unidades")

    audit("update_atacado_settings", f"Configurações de Atacado salvas. WhatsApp: {clean_wa}")
    flash("Configurações do WhatsApp e Catálogo de Atacado salvas com sucesso.", "success")
    return redirect(url_for("atacado.admin_atacado"))
