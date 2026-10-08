"""
Rotas do Showroom & Mostruário de Modelos MAJ Mobilidade
Disponibiliza a API pública de modelos (/api/models) sincronizada 24/7 com o Google Sheets,
endpoint de ativação/inativação de modelos e a rota do mostruário /modelos.
"""

import time
import logging
from flask import Blueprint, jsonify, render_template, request
from routes.helpers import current_user, login_required
from services.maj_models_sync_service import (
    sync_models_from_sheets,
    get_all_models,
    get_model_by_slug,
    set_model_active_status,
    save_models_order,
    load_models_order,
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

    return jsonify({
        "total_models": len(models),
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
    """Salva a nova ordem de exibição dos modelos enviada pelo painel administrativo."""
    body = request.get_json(silent=True) or {}
    order = body.get("order", [])
    if not isinstance(order, list):
        return jsonify({"error": "Formato inválido. 'order' deve ser uma lista de slugs."}), 400

    save_models_order(order)
    return jsonify({
        "status": "success",
        "message": "Ordem dos produtos atualizada com sucesso.",
        "order": order,
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


@showroom_bp.route("/admin/models", methods=["GET"])
@login_required
def admin_models_page():
    """Painel de Gestão e Ordenação de Produtos no Mostruário da MAJ."""
    me = current_user()
    models = get_all_models(include_inactive=True)
    return render_template("showroom/admin_models.html", me=me, models=models)


@showroom_bp.route("/modelos", methods=["GET"])
def showroom_models_page():
    """Mostruário e showroom imersivo de todos os modelos MAJ no estilo Gogoro Pulse."""
    models = get_all_models(include_inactive=False)
    cache_id = int(time.time())
    return render_template("showroom/models.html", models=models, cache_id=cache_id)
