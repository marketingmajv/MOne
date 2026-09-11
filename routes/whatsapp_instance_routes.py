"""
M-One WhatsApp Instance Management Blueprint (routes/whatsapp_instance_routes.py)
Controle de pareamento via QR Code para vendedores/pós-venda e gestão master de instâncias.
"""

from __future__ import annotations

import os
from flask import Blueprint, flash, jsonify, redirect, request, url_for

from database import db
from routes.helpers import current_user, login_required
from services.evolution_service import (
    create_or_get_instance,
    get_evolution_config,
    get_instance_connection,
    logout_instance,
    save_evolution_config,
)

whatsapp_instance_bp = Blueprint("whatsapp_instance", __name__)


def _get_system_base_url() -> str:
    """Retorna a URL base do M-One para configuração automática de webhooks."""
    base = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("APP_URL") or "m-one.majmobilidade.com.br"
    if not base.startswith("http://") and not base.startswith("https://"):
        base = f"https://{base}"
    return base.rstrip("/")


@whatsapp_instance_bp.route("/api/whatsapp/my-line/connect", methods=["POST"])
@login_required
def connect_my_line():
    """Gera ou recupera o QR Code para o vendedor parear seu WhatsApp."""
    me = current_user()
    if not me:
        return jsonify({"success": False, "error": "Não autenticado"}), 401

    username = me.get("username", f"user_{me.get('id')}")
    instance_name = f"vendedor_{username}"
    base_url = _get_system_base_url()
    webhook_url = f"{base_url}/webhook/evolution"

    res = create_or_get_instance(instance_name, webhook_target_url=webhook_url)

    # Atualizar ou registrar a linha monitorada no banco de dados
    try:
        with db() as conn:
            row = conn.execute(
                "SELECT id FROM whatsapp_monitored_lines WHERE LOWER(instance_name) = LOWER(%s) LIMIT 1",
                (instance_name,),
            ).fetchone()

            if row:
                conn.execute(
                    """
                    UPDATE whatsapp_monitored_lines
                    SET assigned_seller_name = %s,
                        assigned_user_id = %s,
                        connection_status = %s,
                        qrcode_base64 = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (me.get("name"), me.get("id"), res.get("state", "connecting"), res.get("qrcode"), row["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO whatsapp_monitored_lines 
                    (account_name, instance_name, instance_type, assigned_seller_name, assigned_user_id, connection_status, qrcode_base64, is_monitored)
                    VALUES (%s, %s, 'evolution', %s, %s, %s, %s, TRUE)
                    """,
                    (
                        f"Linha de {me.get('name')}",
                        instance_name,
                        me.get("name"),
                        me.get("id"),
                        res.get("state", "connecting"),
                        res.get("qrcode"),
                    ),
                )
            conn.commit()
    except Exception as e:
        print("[Connect My Line DB Error]:", e)

    return jsonify(res)


@whatsapp_instance_bp.route("/api/whatsapp/my-line/status", methods=["GET"])
@login_required
def my_line_status():
    """Verifica o status atual da linha do vendedor conectado."""
    me = current_user()
    if not me:
        return jsonify({"success": False, "error": "Não autenticado"}), 401

    username = me.get("username", f"user_{me.get('id')}")
    instance_name = f"vendedor_{username}"

    res = get_instance_connection(instance_name)

    # Se estiver aberta (open), sincroniza no banco
    if res.get("state") == "open":
        try:
            with db() as conn:
                conn.execute(
                    """
                    UPDATE whatsapp_monitored_lines 
                    SET connection_status = 'open', is_monitored = TRUE, qrcode_base64 = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE LOWER(instance_name) = LOWER(%s)
                    """,
                    (instance_name,),
                )
                conn.commit()
        except Exception as e:
            print("[Update Line Status DB Error]:", e)

    return jsonify(res)


@whatsapp_instance_bp.route("/api/whatsapp/my-line/disconnect", methods=["POST"])
@login_required
def disconnect_my_line():
    """Desconecta a sessão do WhatsApp do vendedor."""
    me = current_user()
    if not me:
        return jsonify({"success": False, "error": "Não autenticado"}), 401

    username = me.get("username", f"user_{me.get('id')}")
    instance_name = f"vendedor_{username}"

    ok = logout_instance(instance_name)
    try:
        with db() as conn:
            conn.execute(
                """
                UPDATE whatsapp_monitored_lines 
                SET connection_status = 'disconnected', is_monitored = FALSE, qrcode_base64 = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE LOWER(instance_name) = LOWER(%s)
                """,
                (instance_name,),
            )
            conn.commit()
    except Exception as e:
        print("[Disconnect My Line DB Error]:", e)

    return jsonify({"success": ok})


@whatsapp_instance_bp.route("/connections/evolution/save", methods=["POST"])
@login_required
def save_evolution_settings():
    """Salva credenciais da Evolution API a partir do Centro de Conexões."""
    me = current_user()
    if not me or (me.get("role") not in ["admin", "support"] and me.get("username") not in ["jam", "fauzer"]):
        flash("Acesso restrito à Diretoria e Suporte Técnico.", "error")
        return redirect(url_for("dashboard"))

    api_url = request.form.get("evolution_api_url", "")
    api_key = request.form.get("evolution_api_key", "")

    ok = save_evolution_config(api_url, api_key)
    if ok:
        flash("Configurações da Evolution API salvas com sucesso!", "success")
    else:
        flash("Erro ao salvar configurações da Evolution API.", "error")

    return redirect(url_for("connections.connections_hub"))


@whatsapp_instance_bp.route("/api/whatsapp/admin/line/qrcode/<int:line_id>", methods=["GET"])
@login_required
def admin_get_line_qrcode(line_id: int):
    """Jam e Fauzer: Obtém o QR Code ou status de qualquer linha monitorada."""
    me = current_user()
    if not me or (me.get("role") not in ["admin", "support"] and me.get("username") not in ["jam", "fauzer"]):
        return jsonify({"success": False, "error": "Acesso não autorizado"}), 403

    try:
        with db() as conn:
            line = conn.execute(
                "SELECT instance_name, assigned_seller_name FROM whatsapp_monitored_lines WHERE id = %s",
                (line_id,),
            ).fetchone()
            if not line:
                return jsonify({"success": False, "error": "Linha não encontrada"}), 404

            inst_name = line.get("instance_name")
            if not inst_name:
                inst_name = f"instancia_{line_id}"
                conn.execute(
                    "UPDATE whatsapp_monitored_lines SET instance_name = %s WHERE id = %s",
                    (inst_name, line_id),
                )
                conn.commit()

        base_url = _get_system_base_url()
        webhook_url = f"{base_url}/webhook/evolution"
        res = create_or_get_instance(inst_name, webhook_target_url=webhook_url)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
