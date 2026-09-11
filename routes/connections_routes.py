"""
M-One Connections Hub Blueprint (routes/connections_routes.py)
Central de conexões para Meta Ads, WhatsApp Cloud API, Instagram, Bling ERP e Webhooks.
"""

from __future__ import annotations

import os
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from database import db
from routes.helpers import current_user, login_required
from services.evolution_service import get_evolution_config
from services.meta_service import fetch_meta_campaigns, get_meta_config, save_meta_config, test_meta_connection
from services.whatsapp_service import get_whatsapp_config

connections_bp = Blueprint("connections", __name__)


@connections_bp.route("/connections", methods=["GET"])
@login_required
def connections_hub():
    me = current_user()
    if not me or (me.get("role") not in ["admin", "support"] and me.get("username") not in ["jam", "fauzer"]):
        flash("Acesso restrito à Diretoria e Suporte Técnico.", "error")
        return redirect(url_for("dashboard"))

    meta_cfg = get_meta_config()
    whatsapp_cfg = get_whatsapp_config()
    evolution_cfg = get_evolution_config()

    # Informações do Bling
    bling_cfg = {}
    try:
        with db() as conn:
            b_row = conn.execute("SELECT * FROM integrations WHERE service_name = 'bling' LIMIT 1").fetchone()
            if b_row:
                bling_cfg = dict(b_row)
    except Exception:
        bling_cfg = {}

    # Logs recentes de webhook
    webhook_logs = []
    try:
        with db() as conn:
            logs = conn.execute(
                "SELECT * FROM webhook_event_logs ORDER BY id DESC LIMIT 15"
            ).fetchall()
            webhook_logs = [dict(r) for r in logs]
    except Exception:
        webhook_logs = []

    # URLs oficiais de webhook para exibição e cópia
    base_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or "m-one.majmobilidade.com.br"
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    webhook_url = f"{base_url}/webhook/whatsapp"
    evolution_webhook_url = f"{base_url}/webhook/evolution"

    return render_template(
        "connections.html",
        me=me,
        meta_cfg=meta_cfg,
        whatsapp_cfg=whatsapp_cfg,
        evolution_cfg=evolution_cfg,
        evolution_webhook_url=evolution_webhook_url,
        bling_cfg=bling_cfg,
        webhook_logs=webhook_logs,
        webhook_url=webhook_url,
    )


@connections_bp.route("/connections/meta/save", methods=["POST"])
@login_required
def save_meta():
    me = current_user()
    if not me or (me.get("role") not in ["admin", "support"] and me.get("username") not in ["jam", "fauzer"]):
        return jsonify({"success": False, "error": "Sem permissão"}), 403

    form_data = {
        "access_token": request.form.get("access_token", ""),
        "ad_account_id": request.form.get("ad_account_id", ""),
        "pixel_id": request.form.get("pixel_id", ""),
        "page_id": request.form.get("page_id", ""),
        "app_id": request.form.get("app_id", ""),
        "app_secret": request.form.get("app_secret", ""),
        "waba_id": request.form.get("waba_id", ""),
        "phone_number_id": request.form.get("phone_number_id", ""),
    }

    ok = save_meta_config(form_data)
    if ok:
        flash("Configurações da Meta atualizadas com sucesso!", "success")
    else:
        flash("Erro ao salvar configurações da Meta.", "error")

    return redirect(url_for("connections.connections_hub"))


@connections_bp.route("/connections/meta/test", methods=["POST"])
@login_required
def test_meta():
    me = current_user()
    if not me or (me.get("role") not in ["admin", "support"] and me.get("username") not in ["jam", "fauzer"]):
        return jsonify({"success": False, "error": "Sem permissão"}), 403

    payload = request.get_json(silent=True) or {}
    token = payload.get("token") or request.form.get("access_token")

    diagnosis = test_meta_connection(custom_token=token)
    return jsonify({"success": True, "diagnosis": diagnosis})


@connections_bp.route("/connections/meta/campaigns", methods=["GET"])
@login_required
def get_campaigns():
    me = current_user()
    if not me or (me.get("role") not in ["admin", "support"] and me.get("username") not in ["jam", "fauzer"]):
        return jsonify({"success": False, "error": "Sem permissão"}), 403

    campaigns = fetch_meta_campaigns()
    return jsonify({"success": True, "campaigns": campaigns})
