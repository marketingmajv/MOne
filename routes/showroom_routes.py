"""
Rotas do Showroom & Mostruário de Modelos MAJ Mobilidade
Disponibiliza a API pública de modelos (/api/models) sincronizada 24/7 com o Google Sheets,
endpoint de ativação/inativação de modelos e a rota do mostruário /modelos.
"""

import time
import logging
from flask import Blueprint, jsonify, render_template, request
from routes.helpers import current_user, login_required, roles_required
from services.maj_models_sync_service import (
    sync_models_from_sheets,
    get_all_models,
    get_model_by_slug,
    set_model_active_status,
    save_models_order,
    load_models_order,
    load_menu_config,
    save_menu_config,
    load_kiosk_settings,
    save_kiosk_settings,
)
from services.showroom_promo_service import (
    load_promo_banner_settings,
    save_promo_banner_settings,
)

logger = logging.getLogger(__name__)

showroom_bp = Blueprint("showroom", __name__)


@showroom_bp.route("/api/models", methods=["GET"])
def api_list_models():
    """Retorna os modelos consolidados (apenas ativos por padrão; use ?all=true para todos)."""
    force = request.args.get("force", "").lower() in ["true", "1", "yes"]
    include_inactive = request.args.get("all", "").lower() in ["true", "1", "yes"]

    if force:
        sync_models_from_sheets(force=True)

    models = get_all_models(include_inactive=include_inactive)
    categories = list(dict.fromkeys(m["categoria"] for m in models if m.get("categoria")))
    menu_cfg = load_menu_config()

    return jsonify({
        "total_models": len(models),
        "menu_mode": menu_cfg.get("mode", "category"),
        "category_order": menu_cfg.get("category_order", ["Scooter", "Bike"]),
        "categories": categories,
        "models": models,
    }), 200


@showroom_bp.route("/api/models/<slug>", methods=["GET"])
def api_get_model(slug):
    """Retorna dados detalhados e seções técnicas de um modelo específico."""
    model = get_model_by_slug(slug)
    if not model:
        return jsonify({"error": "Modelo não encontrado", "slug": slug}), 404
    return jsonify(model), 200


@showroom_bp.route("/api/models/<slug>/status", methods=["POST"])
def api_set_model_status(slug):
    """Ativa ou inativa um modelo específico no catálogo."""
    body = request.get_json(silent=True) or {}
    is_active = body.get("active", True)
    set_model_active_status(slug, is_active)
    return jsonify({
        "status": "success",
        "slug": slug,
        "is_active": bool(is_active),
        "message": f"Modelo {slug} {'ativado' if is_active else 'inativado'} com sucesso.",
    }), 200


@showroom_bp.route("/api/models/order", methods=["POST"])
def api_save_models_order():
    """Salva a nova ordem e modo de exibição dos modelos (menu por categoria vs livre)."""
    body = request.get_json(silent=True) or {}
    success = save_menu_config(body)
    if not success:
        return jsonify({"error": "Formato inválido ao salvar configuração do menu."}), 400

    cfg = load_menu_config()
    return jsonify({
        "status": "success",
        "message": "Configurações e ordenação do menu atualizadas com sucesso.",
        "menu_config": cfg,
    }), 200


@showroom_bp.route("/api/models/sync", methods=["POST"])
def api_sync_models():
    """Endpoint para forçar sincronização com o Google Sheets."""
    data = sync_models_from_sheets(force=True)
    return jsonify({
        "status": "success",
        "message": "Modelos sincronizados com o Google Sheets.",
        "total_models": data.get("total_models", 0),
        "updated_at": data.get("updated_at"),
    }), 200


@showroom_bp.route("/api/models/kiosk-settings", methods=["GET"])
def api_get_kiosk_settings():
    """Retorna configurações do Modo TV / Kiosk do showroom."""
    return jsonify(load_kiosk_settings()), 200


@showroom_bp.route("/api/models/kiosk-settings", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_save_kiosk_settings():
    """Atualiza configurações do Modo TV / Kiosk do showroom."""
    body = request.get_json(silent=True) or {}
    updated = save_kiosk_settings(body)
    return jsonify({
        "status": "success",
        "message": "Configurações do Modo TV atualizadas com sucesso.",
        "settings": updated,
    }), 200


@showroom_bp.route("/api/models/promo-banner", methods=["GET"])
def api_get_promo_banner():
    """Retorna configurações do Banner Promocional do showroom."""
    return jsonify(load_promo_banner_settings()), 200


@showroom_bp.route("/api/models/promo-banner", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_save_promo_banner():
    """Atualiza configurações do Banner Promocional do showroom."""
    body = request.get_json(silent=True) or {}
    updated = save_promo_banner_settings(body)
    return jsonify({
        "status": "success",
        "message": "Configurações da promoção atualizadas com sucesso.",
        "promo_banner": updated,
    }), 200


@showroom_bp.route("/admin/models", methods=["GET"])
@showroom_bp.route("/admin/modelos", methods=["GET"])
@login_required
@roles_required("admin", "support")
def admin_models_page():
    """Painel de Gestão e Ordenação de Produtos no Mostruário da MAJ."""
    me = current_user()
    models = get_all_models(include_inactive=True)
    kiosk_settings = load_kiosk_settings()
    menu_config = load_menu_config()
    promo_banner = load_promo_banner_settings()
    return render_template(
        "showroom/admin_models.html",
        me=me,
        models=models,
        kiosk_settings=kiosk_settings,
        menu_config=menu_config,
        promo_banner=promo_banner,
    )


@showroom_bp.route("/show-room", methods=["GET"])
@showroom_bp.route("/show-room/<slug>", methods=["GET"])
@showroom_bp.route("/showroom", methods=["GET"])
@showroom_bp.route("/showroom/<slug>", methods=["GET"])
@showroom_bp.route("/modelos", methods=["GET"])
@showroom_bp.route("/modelos/<slug>", methods=["GET"])
def showroom_models_page(slug=None):
    """Mostruário e showroom imersivo de todos os modelos MAJ no estilo Gogoro Pulse."""
    models = get_all_models(include_inactive=False)
    cache_id = int(time.time())
    active_model = None
    if slug:
        active_model = next((m for m in models if m.get("slug") == slug), None)
    if not active_model and models:
        active_model = models[0]
    kiosk_settings = load_kiosk_settings()
    promo_banner = load_promo_banner_settings()
    return render_template(
        "showroom/models.html",
        models=models,
        active_model=active_model,
        initial_slug=slug or (active_model.get("slug") if active_model else None),
        kiosk_settings=kiosk_settings,
        cache_id=cache_id,
        promo_banner=promo_banner,
    )
