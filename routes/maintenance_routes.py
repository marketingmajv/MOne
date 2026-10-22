"""
M-One Maintenance Routes (routes/maintenance_routes.py)
Endpoints para consulta e alternância do Modo Manutenção por Módulo e disparo de WhatsApp.
Segregação estrita modular (< 500 linhas).
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request
from routes.helpers import current_user, login_required, roles_required
from services.maintenance_service import (
    build_default_maintenance_message,
    get_all_modules_status,
    get_maintenance_recipients,
    get_module_status,
    toggle_module_maintenance,
)

logger = logging.getLogger(__name__)

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/api/manutencao")


@maintenance_bp.route("/modulos", methods=["GET"])
@login_required
def list_modules():
    """Retorna o status de manutenção de todos os módulos."""
    return jsonify({
        "status": "success",
        "modules": get_all_modules_status(),
    })


@maintenance_bp.route("/status/<slug>", methods=["GET"])
@login_required
def module_status(slug: str):
    """Retorna o status de manutenção de um módulo específico."""
    mod = get_module_status(slug)
    return jsonify({
        "status": "success",
        "module": mod,
    })


@maintenance_bp.route("/recipients/<slug>", methods=["GET"])
@login_required
@roles_required("admin", "support")
def module_recipients(slug: str):
    """Retorna a lista de colaboradores que serão notificados via WhatsApp para o módulo."""
    recipients = get_maintenance_recipients(slug)
    return jsonify({
        "status": "success",
        "slug": slug,
        "total": len(recipients),
        "recipients": recipients,
    })


@maintenance_bp.route("/toggle", methods=["POST"])
@login_required
@roles_required("admin", "support")
def toggle_status():
    """Altera o status de manutenção de um módulo e notifica via WhatsApp se solicitado."""
    data = request.get_json(silent=True) or {}
    slug = (data.get("slug") or "").strip()
    if not slug:
        return jsonify({"status": "error", "message": "Identificador (slug) do módulo é obrigatório."}), 400

    in_maintenance = bool(data.get("in_maintenance"))
    expected_time = str(data.get("expected_time") or "").strip()
    reason = str(data.get("reason") or "").strip()
    notify_whatsapp = bool(data.get("notify_whatsapp"))
    custom_message = data.get("custom_message")
    if custom_message is not None:
        custom_message = str(custom_message).strip()

    user = current_user() or {}
    user_name = user.get("name") or user.get("username") or "Administrador"

    res = toggle_module_maintenance(
        slug=slug,
        in_maintenance=in_maintenance,
        expected_time=expected_time,
        reason=reason,
        updated_by=user_name,
        notify_whatsapp=notify_whatsapp,
        custom_message=custom_message,
    )

    return jsonify(res)
