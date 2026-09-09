from flask import Blueprint, render_template, request, jsonify
from database import db
from gemini_service import get_gemini_api_key, ask_gemini_copilot
from routes.helpers import (
    login_required,
    current_user,
    audit
)

copilot_bp = Blueprint("copilot", __name__)


@copilot_bp.route("/copilot")
@login_required
def copilot():
    has_key = bool(get_gemini_api_key())
    return render_template("copilot.html", has_key=has_key)


@copilot_bp.route("/api/copilot/chat", methods=["POST"])
@login_required
def copilot_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    if not message:
        return jsonify({"success": False, "message": "Mensagem não informada."}), 400
    audit("copilot.chat", f"prompt={message[:50]}")

    u = current_user()
    if not u:
        return jsonify({"success": False, "message": "Sessão expirada. Faça login novamente."}), 401

    with db() as conn:
        result = ask_gemini_copilot(
            user_message=message,
            history=history,
            db_conn=conn,
            user_role=u["role"],
            user_name=u["name"],
        )
    return jsonify(result)
