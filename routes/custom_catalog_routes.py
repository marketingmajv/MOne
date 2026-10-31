"""
M-One Custom Catalog Routes (routes/custom_catalog_routes.py)
Gerenciamento administrativo e visualização pública de catálogos personalizados para parceiros e lojistas.
Em estrita conformidade com o limite anti-monólito (< 500 linhas).
"""

from __future__ import annotations

import json
from functools import wraps
import logging
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for, session

from routes.helpers import audit, current_user, login_required, user_has_permission
from services.custom_catalog_service import (
    delete_custom_catalog,
    ensure_custom_catalogs_schema,
    get_custom_catalog_by_id,
    get_custom_catalog_by_slug,
    get_matrix_raw_items,
    increment_catalog_views,
    increment_catalog_whatsapp_clicks,
    list_custom_catalogs,
    resolve_custom_catalog_products,
    save_or_update_custom_catalog,
    toggle_custom_catalog_status,
)
from services.custom_catalog_requests_service import (
    consume_catalog_invite_token,
    create_catalog_request,
    delete_catalog_request,
    generate_one_time_token,
    get_catalog_consultant_whatsapp,
    get_catalog_invite_code,
    list_catalog_requests,
    set_catalog_consultant_whatsapp,
    set_catalog_invite_code,
    update_catalog_request_status,
    validate_catalog_invite_code,
    validate_catalog_invite_token,
)

logger = logging.getLogger(__name__)

custom_catalog_bp = Blueprint("custom_catalog", __name__)


def catalog_access_required(fn):
    """Exige login e perfil admin/support ou vendedor com permissão 'custom_catalogs'."""
    @wraps(fn)
    @login_required
    def inner(*args, **kwargs):
        u = current_user()
        if not u or not (u.get("role") in ["admin", "support"] or user_has_permission(u, "custom_catalogs", default_for_sales=False)):
            flash("Apenas administradores ou vendedores autorizados podem acessar a Gestão de Catálogos.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return inner


# -------------------------------------------------------------------------
# PAINEL ADMINISTRATIVO (/admin/catalogos)
# -------------------------------------------------------------------------

@custom_catalog_bp.route("/admin/catalogos")
@catalog_access_required
def admin_dashboard():
    """Painel principal de Gestão de Catálogos Personalizados."""
    ensure_custom_catalogs_schema()
    catalogs = list_custom_catalogs()
    requests_list = list_catalog_requests()
    pending_count = sum(1 for r in requests_list if r.get("status") == "pendente")
    invite_code = get_catalog_invite_code()
    consultant_whatsapp = get_catalog_consultant_whatsapp()

    # Métricas consolidadas
    total_views = sum(int(c.get("views_count") or 0) for c in catalogs)
    total_clicks = sum(int(c.get("whatsapp_clicks_count") or 0) for c in catalogs)
    active_count = sum(1 for c in catalogs if c.get("is_active"))

    # Contagem de matrizes disponíveis
    outlet_count = len(get_matrix_raw_items("outlet"))
    atacado_count = len(get_matrix_raw_items("atacado"))

    return render_template(
        "admin/custom_catalogs_dashboard.html",
        catalogs=catalogs,
        requests=requests_list,
        pending_requests_count=pending_count,
        invite_code=invite_code,
        consultant_whatsapp=consultant_whatsapp,
        total_views=total_views,
        total_clicks=total_clicks,
        active_count=active_count,
        outlet_count=outlet_count,
        atacado_count=atacado_count,
        me=current_user(),
    )


@custom_catalog_bp.route("/admin/catalogos/save", methods=["POST"])
@catalog_access_required
def save_catalog():
    """Cria ou atualiza um catálogo personalizado."""
    is_json = request.is_json
    data = request.get_json(silent=True) if is_json else request.form.to_dict()
    if not data:
        data = {}

    catalog_id_raw = data.get("id") or data.get("catalog_id")
    catalog_id = int(catalog_id_raw) if catalog_id_raw else None
    request_id_raw = data.get("request_id")
    request_id = int(request_id_raw) if request_id_raw else None

    # Normalização de booleanos
    sync_stock = data.get("sync_stock") in (True, 1, "1", "true", "on", "True")
    is_white_label = data.get("is_white_label") in (True, 1, "1", "true", "on", "True")
    is_active = data.get("is_active") in (True, 1, "1", "true", "on", "True", None)

    # Tratamento de overrides JSON
    overrides_input = data.get("custom_item_overrides_json")
    if isinstance(overrides_input, str):
        try:
            overrides_json = json.loads(overrides_input)
        except Exception:
            overrides_json = {}
    elif isinstance(overrides_input, dict):
        overrides_json = overrides_input
    else:
        overrides_json = {}

    payload = {
        "title": data.get("title", "").strip().upper(),
        "client_name": data.get("client_name", "").strip().upper(),
        "slug": data.get("slug", "").strip().lower(),
        "source_matrix": data.get("source_matrix", "outlet").strip().lower(),
        "pricing_mode": data.get("pricing_mode", "fixed_matrix").strip().lower(),
        "percentage_markup": float(data.get("percentage_markup") or 0.0),
        "sync_stock": sync_stock,
        "is_white_label": is_white_label,
        "logo_url": data.get("logo_url", "").strip(),
        "whatsapp_number": data.get("whatsapp_number", "").strip(),
        "whatsapp_message_template": data.get("whatsapp_message_template", "").strip(),
        "custom_item_overrides_json": overrides_json,
        "is_active": is_active,
        "expires_at": data.get("expires_at") or None,
        "created_by": (current_user() or {}).get("id"),
    }

    try:
        saved = save_or_update_custom_catalog(payload, catalog_id=catalog_id)
        user_name = (current_user() or {}).get("name", "Sistema")
        if request_id:
            update_catalog_request_status(request_id, "aprovada", catalog_id=saved.get("id"), approved_by=user_name)
        audit("custom_catalog_save", f"Catálogo '{saved.get('title')}' ({saved.get('slug')}) salvo por {user_name}")
        if is_json:
            return jsonify({"success": True, "catalog": saved})
        flash(f"Catálogo '{saved.get('title')}' configurado com sucesso!", "success")
        return redirect(url_for("custom_catalog.admin_dashboard"))
    except Exception as e:
        logger.error("Erro ao salvar catálogo customizado: %s", e, exc_info=True)
        if is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Erro ao salvar catálogo: {e}", "danger")
        return redirect(url_for("custom_catalog.admin_dashboard"))


@custom_catalog_bp.route("/admin/catalogos/toggle/<int:catalog_id>", methods=["POST"])
@catalog_access_required
def toggle_status(catalog_id: int):
    """Ativa ou pausa um catálogo personalizado."""
    ok = toggle_custom_catalog_status(catalog_id)
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": ok})
    flash("Status do catálogo alterado com sucesso.", "success" if ok else "warning")
    return redirect(url_for("custom_catalog.admin_dashboard"))


@custom_catalog_bp.route("/admin/catalogos/delete/<int:catalog_id>", methods=["POST"])
@catalog_access_required
def delete_catalog(catalog_id: int):
    """Exclui permanentemente um catálogo personalizado."""
    ok = delete_custom_catalog(catalog_id)
    user_name = (current_user() or {}).get("name", "Sistema")
    audit("custom_catalog_delete", f"Catálogo ID {catalog_id} excluído por {user_name}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": ok})
    flash("Catálogo excluído com sucesso.", "info")
    return redirect(url_for("custom_catalog.admin_dashboard"))


@custom_catalog_bp.route("/api/admin/catalogos/matrix-preview/<matrix>")
@catalog_access_required
def matrix_preview(matrix: str):
    """Retorna itens da matriz de origem para o modal de criação/personalização."""
    items = get_matrix_raw_items(matrix)
    simplified = []
    for it in items:
        price = float(it.get("price_outlet") or it.get("price_original") or 0.0)
        simplified.append({
            "id": it.get("id"),
            "name": it.get("name"),
            "category": it.get("category"),
            "price": price,
            "stock_qty": it.get("stock_qty", 0),
            "image_url": it.get("image_url") or it.get("photo_url") or "",
        })
    return jsonify({"success": True, "matrix": matrix, "count": len(simplified), "items": simplified})


# -------------------------------------------------------------------------
# ROTA PÚBLICA DO CLIENTE (/c/<slug>)
# -------------------------------------------------------------------------

@custom_catalog_bp.route("/c/<slug>")
def public_catalog(slug: str):
    """Exibição pública do catálogo personalizado para clientes ou parceiros."""
    ensure_custom_catalogs_schema()
    catalog = get_custom_catalog_by_slug(slug)
    if not catalog:
        return render_template("custom_catalog/not_found.html", slug=slug), 404

    # Verifica se está ativo
    if not catalog.get("is_active"):
        return render_template("custom_catalog/paused.html", catalog=catalog), 403

    # Incrementa contador de visualizações
    increment_catalog_views(catalog["id"])

    # Resolve os produtos com a lógica de preço e WhatsApp do catálogo
    items = resolve_custom_catalog_products(catalog)

    # Filtros opcionais via query param
    category_filter = request.args.get("categoria", "").strip()
    search_filter = request.args.get("busca", "").strip()

    if category_filter and category_filter != "all":
        items = [i for i in items if category_filter.lower() in (i.get("category") or "").lower()]

    if search_filter:
        s = search_filter.lower()
        items = [i for i in items if s in (i.get("name") or "").lower() or s in (i.get("description") or "").lower()]

    # Categorias únicas para tabs de navegação
    categories = sorted(list({i.get("category") for i in items if i.get("category")}))

    # Se a matriz de origem for Atacado, renderiza o template unificado Atacado V3 oficial
    if catalog.get("source_matrix") == "atacado":
        import re
        raw_wa = catalog.get("whatsapp_number") or "5527996051538"
        clean_wa = re.sub(r"\D", "", str(raw_wa)) or "5527996051538"
        if not clean_wa.startswith("55") and len(clean_wa) <= 11:
            clean_wa = f"55{clean_wa}"

        title = catalog.get("title") or "MAJ ATACADO MOBILIDADE"
        subtitle = catalog.get("client_name") or "Catálogo Oficial de Atacado • Condições e Preços Exclusivos CNPJ"
        wa_tpl = (
            f"Olá! Tenho interesse no modelo {{model}} no Catálogo de Atacado {title} (CNPJ). "
            f"Gostaria de solicitar uma cotação/pedido."
        )
        wa_floating = (
            f"Olá! Estou navegando no Catálogo de Atacado {title} (CNPJ) e gostaria de falar com um consultor comercial."
        )
        current_logo = catalog.get("logo_url") or url_for("static", filename="images/custom_catalogs/partner_logo.png")

        return render_template(
            "custom_catalog/atacado_view.html",
            catalog=catalog,
            items=items,
            categories=categories,
            title=title,
            subtitle=subtitle,
            whatsapp_number=clean_wa,
            whatsapp_message=wa_tpl,
            whatsapp_floating_message=wa_floating,
            show_prices=True,
            current_logo=current_logo,
            active_category=category_filter or "all",
            search_query=search_filter,
        )

    return render_template(
        "custom_catalog/view.html",
        catalog=catalog,
        items=items,
        categories=categories,
        active_category=category_filter or "all",
        search_query=search_filter,
    )


@custom_catalog_bp.route("/api/c/<slug>/track-click", methods=["POST"])
def track_whatsapp_click(slug: str):
    """Registra telemetria quando o usuário clica em qualquer CTA de WhatsApp."""
    catalog = get_custom_catalog_by_slug(slug)
    if catalog:
        increment_catalog_whatsapp_clicks(catalog["id"])
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Catálogo não encontrado"}), 404


# -------------------------------------------------------------------------
# SOLICITAÇÃO PÚBLICA DE CATÁLOGO (VENDEDORES EXTERNOS & LOJISTAS)
# -------------------------------------------------------------------------

@custom_catalog_bp.route("/solicitar-catalogo", methods=["GET", "POST"])
@custom_catalog_bp.route("/quero-meu-catalogo", methods=["GET", "POST"])
def request_catalog_form():
    """Página pública de solicitação com token randômico descartável a cada abertura."""
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        code = (data.get("invite_code") or "").strip().upper()

        check = validate_catalog_invite_token(code)
        if not check.get("valid"):
            return jsonify({
                "success": False,
                "error": check.get("reason") or "Código de convite ou token inválido ou expirado."
            }), 400

        applicant_name = (data.get("applicant_name") or "").strip().upper()
        store_name = (data.get("store_name") or "").strip().upper()
        whatsapp = (data.get("whatsapp_number") or "").strip()

        if not applicant_name or not whatsapp:
            return jsonify({
                "success": False,
                "error": "Preencha todos os campos obrigatórios (Nome do Vendedor e WhatsApp)."
            }), 400

        try:
            req_id = create_catalog_request(data)
            display_target = store_name if store_name else f"VENDEDOR {applicant_name}"
            audit("custom_catalog_request_submitted", f"Nova solicitação de catálogo #{req_id} para '{display_target}' ({applicant_name}) com token {code}")
            return jsonify({"success": True, "request_id": req_id})
        except Exception as e:
            logger.error("Erro ao registrar solicitação de catálogo: %s", e, exc_info=True)
            return jsonify({"success": False, "error": "Falha ao gravar solicitação. Tente novamente."}), 500

    # GET: Exige obrigatoriamente um link com token gerado pelo consultor
    param_token = (request.args.get("convite") or request.args.get("token") or "").strip().upper()
    consultant_whatsapp = get_catalog_consultant_whatsapp()
    if not param_token:
        return render_template(
            "custom_catalog/request_form.html",
            has_valid_token=False,
            token_error="missing",
            consultant_whatsapp=consultant_whatsapp,
            token_message="Esta página é exclusiva para parceiros e exige um link de convite oficial enviado por um consultor MAJ."
        )

    check = validate_catalog_invite_token(param_token)
    if not check.get("valid"):
        return render_template(
            "custom_catalog/request_form.html",
            has_valid_token=False,
            token_error="expired",
            expired_token=param_token,
            consultant_whatsapp=consultant_whatsapp,
            token_message=check.get("reason") or "Este link de convite já foi utilizado ou expirou. Solicite um novo link ao seu consultor comercial."
        )

    return render_template(
        "custom_catalog/request_form.html",
        has_valid_token=True,
        initial_token=param_token,
        consultant_whatsapp=consultant_whatsapp,
    )


@custom_catalog_bp.route("/api/solicitar-catalogo/validar-convite", methods=["POST"])
def api_validate_invite():
    """Valida em tempo real se o código de convite ou token de uso único é válido."""
    data = request.get_json(silent=True) or {}
    code = (data.get("invite_code") or "").strip().upper()
    res = validate_catalog_invite_token(code)
    return jsonify({"valid": res.get("valid"), "reason": res.get("reason", "")})


@custom_catalog_bp.route("/admin/catalogos/generate-token", methods=["POST"])
@catalog_access_required
def admin_generate_token():
    """Gera sob demanda um novo token randômico descartável de uso único."""
    user_name = (current_user() or {}).get("name", "Admin")
    tok = generate_one_time_token(created_by=user_name)
    return jsonify({"success": True, "token": tok})


# -------------------------------------------------------------------------
# GESTÃO ADMINISTRATIVA DE SOLICITAÇÕES (/admin/catalogos/requests)
# -------------------------------------------------------------------------

@custom_catalog_bp.route("/admin/catalogos/requests/<int:req_id>/status", methods=["POST"])
@catalog_access_required
def update_request_status_route(req_id: int):
    """Atualiza o status de uma solicitação (ex: recusada, pendente)."""
    data = request.get_json(silent=True) or request.form.to_dict()
    status = (data.get("status") or "").strip().lower()
    if status not in ["pendente", "aprovada", "recusada"]:
        return jsonify({"success": False, "error": "Status inválido"}), 400

    user_name = (current_user() or {}).get("name", "Admin")
    update_catalog_request_status(req_id, status, approved_by=user_name if status == "aprovada" else None)
    audit("custom_catalog_request_status", f"Solicitação #{req_id} alterada para '{status}' por {user_name}")

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.accept_json:
        return jsonify({"success": True, "ok": True, "status": status})
    flash(f"Status da solicitação #{req_id} alterado para {status}.", "success")
    return redirect(url_for("custom_catalog.admin_dashboard"))


@custom_catalog_bp.route("/admin/catalogos/requests/<int:req_id>/delete", methods=["POST"])
@catalog_access_required
def delete_request_route(req_id: int):
    """Exclui uma solicitação de catálogo."""
    ok = delete_catalog_request(req_id)
    user_name = (current_user() or {}).get("name", "Admin")
    audit("custom_catalog_request_delete", f"Solicitação #{req_id} excluída por {user_name}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.accept_json:
        return jsonify({"success": ok, "ok": ok})
    flash("Solicitação excluída com sucesso.", "success")
    return redirect(url_for("custom_catalog.admin_dashboard"))


@custom_catalog_bp.route("/admin/catalogos/settings/invite-code", methods=["POST"])
@catalog_access_required
def update_invite_code_route():
    """Atualiza a chave de convite comercial para solicitações de vendedores."""
    data = request.get_json(silent=True) or request.form.to_dict()
    new_code = (data.get("invite_code") or "").strip().upper()
    saved_code = set_catalog_invite_code(new_code)
    user_name = (current_user() or {}).get("name", "Admin")
    audit("custom_catalog_invite_code_update", f"Código de convite atualizado para '{saved_code}' por {user_name}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "invite_code": saved_code})
    flash(f"Código de convite atualizado para: {saved_code}", "success")
    return redirect(url_for("custom_catalog.admin_dashboard"))


@custom_catalog_bp.route("/admin/catalogos/settings/consultant-whatsapp", methods=["POST"])
@catalog_access_required
def update_consultant_whatsapp_route():
    """Atualiza o número de WhatsApp do consultor para solicitações de catálogo."""
    data = request.get_json(silent=True) or request.form.to_dict()
    new_num = (data.get("consultant_whatsapp") or "").strip()
    saved = set_catalog_consultant_whatsapp(new_num)
    user_name = (current_user() or {}).get("name", "Admin")
    audit("custom_catalog_consultant_whatsapp_update", f"WhatsApp do Consultor atualizado para '{saved}' por {user_name}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.accept_json:
        return jsonify({"success": True, "ok": True, "consultant_whatsapp": saved})
    flash(f"WhatsApp do Consultor atualizado para: {saved}", "success")
    return redirect(url_for("custom_catalog.admin_dashboard"))

