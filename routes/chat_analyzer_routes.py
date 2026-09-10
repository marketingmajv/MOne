"""
M-One Chat Analyzer Blueprint (routes/chat_analyzer_routes.py)
Rotas do Analisador de Chats por período e IA Copilot de auditoria comercial.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from database import db
from routes.helpers import current_user, login_required
from services.chat_analyzer_service import (
    analyze_chats_with_gemini,
    get_chats_by_period,
    import_external_chat_log,
)

chat_analyzer_bp = Blueprint("chat_analyzer", __name__)


@chat_analyzer_bp.route("/crm/chat-analyzer", methods=["GET"])
@login_required
def chat_analyzer():
    me = current_user()
    if not me:
        return redirect(url_for("login"))

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

    return render_template(
        "chat_analyzer.html",
        me=me,
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
