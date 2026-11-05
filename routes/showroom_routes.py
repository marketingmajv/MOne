"""
Rotas do Showroom & Mostruário de Modelos MAJ Mobilidade
Disponibiliza a API pública de modelos (/api/models) sincronizada 24/7 com o Google Sheets,
endpoint de ativação/inativação de modelos e a rota do mostruário /modelos.
"""

import time
import logging
from flask import Blueprint, jsonify, render_template, request, send_file
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
from services.showroom_crud_service import (
    get_model_full_for_edit,
    save_showroom_model,
    export_models_to_xlsx_bytes,
    get_global_image_mode,
    set_global_image_mode,
    toggle_model_banner_type,
    load_model_overrides,
    save_model_overrides,
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
@showroom_bp.route("/api/models/<slug>/toggle-active", methods=["POST"])
def api_set_model_status(slug):
    """Ativa ou inativa um modelo específico no catálogo e persiste no banco/overrides."""
    body = request.get_json(silent=True) or {}
    is_active = bool(body["is_active"]) if "is_active" in body else bool(body.get("active", True))
    clean_slug = slug.strip().lower()
    overrides = load_model_overrides()
    if clean_slug in overrides and isinstance(overrides[clean_slug], dict):
        overrides[clean_slug]["is_active"] = is_active
    else:
        m = get_model_by_slug(clean_slug) or {}
        overrides[clean_slug] = {
            "slug": clean_slug,
            "modelo": m.get("modelo", clean_slug.upper()),
            "categoria": m.get("categoria", "Scooter"),
            "is_active": is_active,
        }
    save_model_overrides(overrides)
    set_model_active_status(clean_slug, is_active)
    return jsonify({
        "status": "success",
        "slug": clean_slug,
        "is_active": is_active,
        "message": f"Modelo {clean_slug} {'ativado' if is_active else 'inativado'} com sucesso.",
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


@showroom_bp.route("/api/models/promo-banner/toggle", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_toggle_promo_banner():
    """Alterna imediatamente o status de ativação do banner promocional."""
    from services.showroom_promo_service import toggle_promo_banner_status
    body = request.get_json(silent=True) or {}
    new_state = toggle_promo_banner_status(body.get("enabled"))
    return jsonify({
        "status": "success",
        "enabled": new_state,
        "message": f"Banner promocional {'ativado' if new_state else 'desativado'} com sucesso."
    }), 200


@showroom_bp.route("/api/models/<slug>/full", methods=["GET"])
@login_required
@roles_required("admin", "support")
def api_get_model_full(slug):
    """Retorna dados completos para preenchimento do modal de edição."""
    data = get_model_full_for_edit(slug)
    if not data:
        return jsonify({"error": "Modelo não encontrado", "slug": slug}), 404
    return jsonify(data), 200


@showroom_bp.route("/api/models/save", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_save_model():
    """Cria ou edita um modelo com dados técnicos e upload de banners de topo (atemporal e promocional)."""
    try:
        banner_atemp = request.files.get("banner_atemporal") or request.files.get("photo_atemporal") or request.files.get("photo")
        banner_promo = request.files.get("banner_promocional") or request.files.get("photo_promocional") or request.files.get("photo_promo")
        if request.form:
            data = request.form.to_dict()
        elif request.is_json:
            data = request.get_json(silent=True) or {}
        else:
            data = request.form.to_dict() or request.get_json(silent=True) or {}

        result = save_showroom_model(data, banner_atemporal=banner_atemp, banner_promocional=banner_promo)
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Erro ao salvar modelo do showroom: {e}", exc_info=True)
        return jsonify({"error": f"Falha ao salvar modelo: {str(e)}"}), 500


@showroom_bp.route("/api/models/global-image-mode", methods=["GET"])
def api_get_global_image_mode():
    """Retorna o modo global de imagem ativo no mostruário."""
    return jsonify({"mode": get_global_image_mode()}), 200


@showroom_bp.route("/api/models/global-image-mode", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_set_global_image_mode():
    """Altera a chave mestra do modo de imagens do showroom ('atemporal' vs 'promocional') em massa."""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "atemporal")
    updated = set_global_image_mode(mode)
    return jsonify({
        "status": "success",
        "mode": updated,
        "message": f"Todos os banners foram alterados para '{updated}' com sucesso.",
    }), 200


@showroom_bp.route("/api/models/<slug>/toggle-banner-type", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_toggle_model_banner_type(slug):
    """Alterna individualmente o tipo de banner ativo ('atemporal' vs 'promocional') de um modelo."""
    try:
        body = request.get_json(silent=True) or {}
        target_type = body.get("type")
        result = toggle_model_banner_type(slug, target_type=target_type)
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Erro ao alternar banner do modelo %s: %s", slug, e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@showroom_bp.route("/admin/models/export-xlsx", methods=["GET"])
@login_required
@roles_required("admin", "support")
def admin_models_export_xlsx():
    """Gera e faz download da planilha consolidada XLSX de modelos do Showroom."""
    models = get_all_models(include_inactive=True)
    buf = export_models_to_xlsx_bytes(models)
    return send_file(
        buf,
        as_attachment=True,
        download_name="catalogo_modelos_maj.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
    global_image_mode = get_global_image_mode()
    return render_template(
        "showroom/admin_models.html",
        me=me,
        models=models,
        kiosk_settings=kiosk_settings,
        menu_config=menu_config,
        promo_banner=promo_banner,
        global_image_mode=global_image_mode,
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
    global_image_mode = get_global_image_mode()
    return render_template(
        "showroom/models.html",
        models=models,
        active_model=active_model,
        initial_slug=slug or (active_model.get("slug") if active_model else None),
        kiosk_settings=kiosk_settings,
        cache_id=cache_id,
        promo_banner=promo_banner,
        global_image_mode=global_image_mode,
    )
