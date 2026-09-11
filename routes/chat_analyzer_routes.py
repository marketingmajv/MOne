"""
M-One Chat Analyzer Blueprint (routes/chat_analyzer_routes.py)
Rotas do Analisador de Chats por período e IA Copilot de auditoria comercial.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from database import db
from routes.helpers import current_user, login_required, user_has_permission
from services.chat_analyzer_service import (
    analyze_chats_with_gemini,
    get_chats_by_period,
    import_external_chat_log,
)
from services.meta_service import (
    get_monitored_lines,
    sync_meta_lines,
    toggle_monitored_line,
)

chat_analyzer_bp = Blueprint("chat_analyzer", __name__)


@chat_analyzer_bp.route("/crm/chat-analyzer", methods=["GET"])
@login_required
def chat_analyzer():
    me = current_user()
    if not me:
        return redirect(url_for("login"))

    if not user_has_permission(me, "chat_analyzer", default_for_sales=False):
        flash("Acesso restrito aos Gestores e colaboradores autorizados.", "danger")
        return redirect(url_for("dashboard"))

    username = (me.get("username") or "").strip().lower()
    can_manage_lines = me.get("role") == "admin" or username in ["jam", "fauzer"]

    period = request.args.get("period", "7d").lower()
    if period not in ["1d", "7d", "30d", "all"]:
        period = "7d"

    status_filter = request.args.get("status")
    seller_id = request.args.get("seller")

    chats_data = get_chats_by_period(
        period=period,
        status_filter=status_filter,
        seller_id=seller_id,
    )

    # Obter lista de vendedores para o filtro
    sellers = []
    try:
        with db() as conn:
            rows = conn.execute(
                "SELECT id, name FROM users WHERE role IN ('sales', 'admin', 'support') AND active = TRUE ORDER BY name ASC"
            ).fetchall()
            sellers = [dict(r) for r in rows]
    except Exception:
        sellers = []

    # Obter linhas monitoradas apenas se for Jam ou Fauzer
    monitored_lines = get_monitored_lines() if can_manage_lines else []

    return render_template(
        "chat_analyzer.html",
        me=me,
        can_manage_lines=can_manage_lines,
        monitored_lines=monitored_lines,
        period=period,
        period_label=chats_data["period_label"],
        chats_data=chats_data,
        sellers=sellers,
        current_status_filter=status_filter or "",
        current_seller_filter=seller_id or "",
    )


@chat_analyzer_bp.route("/api/chat-analyzer/ask", methods=["POST"])
@login_required
def ask_chat_analyzer():
    payload = request.get_json(silent=True) or {}
    user_prompt = (payload.get("prompt") or "").strip()
    period = payload.get("period", "7d").lower()
    status_filter = payload.get("status")
    seller_id = payload.get("seller")

    if not user_prompt:
        return jsonify({"success": False, "message": "Pergunta não informada."}), 400

    chats_data = get_chats_by_period(
        period=period,
        status_filter=status_filter,
        seller_id=seller_id,
    )

    analysis_markdown = analyze_chats_with_gemini(chats_data, user_prompt)
    return jsonify({"success": True, "analysis": analysis_markdown})


@chat_analyzer_bp.route("/api/chat-analyzer/import", methods=["POST"])
@login_required
def import_chat():
    payload = request.get_json(silent=True) or {}
    text_content = payload.get("text") or request.form.get("text", "")
    phone = payload.get("phone") or request.form.get("phone", "")
    lead_name = payload.get("lead_name") or request.form.get("lead_name", "")

    result = import_external_chat_log(text_content, phone, lead_name)
    return jsonify(result)


@chat_analyzer_bp.route("/api/chat-analyzer/chat-detail/<phone>", methods=["GET"])
@login_required
def chat_detail(phone: str):
    clean_phone = "".join(ch for ch in phone if ch.isdigit())
    messages = []
    lead_info = {}

    try:
        with db() as conn:
            lead = conn.execute(
                "SELECT * FROM crm_leads WHERE phone = %s OR phone = %s LIMIT 1",
                (clean_phone, clean_phone.replace("55", "")),
            ).fetchone()
            if lead:
                lead_info = dict(lead)

            rows = conn.execute(
                """
                SELECT id, direction, message_type, body, sent_at 
                FROM whatsapp_messages 
                WHERE phone = %s OR phone = %s 
                ORDER BY sent_at ASC
                """,
                (clean_phone, clean_phone.replace("55", "")),
            ).fetchall()

            for r in rows:
                messages.append({
                    "id": r["id"],
                    "direction": r["direction"],
                    "body": r["body"],
                    "sent_at": r["sent_at"].strftime("%d/%m/%Y %H:%M") if r["sent_at"] else "",
                })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "lead": lead_info, "messages": messages})


@chat_analyzer_bp.route("/api/chat-analyzer/toggle-line", methods=["POST"])
@login_required
def api_toggle_line():
    """Ativa (pluga) ou desativa (despluga) uma linha WhatsApp. Restrito a Jam e Fauzer."""
    me = current_user()
    if not me:
        return jsonify({"success": False, "error": "Não autenticado"}), 401

    username = (me.get("username") or "").strip().lower()
    if username not in ["jam", "fauzer"]:
        return jsonify({"success": False, "error": "Acesso negado. Restrito a Jam e Fauzer."}), 403

    payload = request.get_json(silent=True) or {}
    line_id = payload.get("line_id")
    enable = bool(payload.get("enable", False))

    if not line_id:
        return jsonify({"success": False, "error": "ID da linha não informado"}), 400

    result = toggle_monitored_line(int(line_id), enable)
    return jsonify(result)


@chat_analyzer_bp.route("/api/chat-analyzer/sync-lines", methods=["POST"])
@login_required
def api_sync_lines():
    """Sincroniza números e contas WABA da Meta Graph API. Restrito a Jam e Fauzer."""
    me = current_user()
    if not me:
        return jsonify({"success": False, "error": "Não autenticado"}), 401

    username = (me.get("username") or "").strip().lower()
    if username not in ["jam", "fauzer"]:
        return jsonify({"success": False, "error": "Acesso negado. Restrito a Jam e Fauzer."}), 403

    result = sync_meta_lines()
    return jsonify(result)

