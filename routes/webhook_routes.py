"""
M-One Meta WhatsApp Webhook Blueprint (routes/webhook_routes.py)
Recepção oficial de webhooks da Meta Cloud API (subscrição e mensagens inbound).
"""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from database import db
from services.whatsapp_service import get_whatsapp_config

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/webhook/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        verify_token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        cfg = get_whatsapp_config()
        expected_token = os.environ.get("WHATSAPP_VERIFY_TOKEN") or cfg.get("verify_token") or "mone_whatsapp_verify_token_2026"
        if mode == "subscribe" and verify_token == expected_token:
            print("[WhatsApp Webhook Verified Successfully!]")
            return challenge, 200
        return "Verification failed", 403

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        try:
            entries = data.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    contacts = value.get("contacts", [])
                    messages = value.get("messages", [])

                    sender_name = contacts[0].get("profile", {}).get("name", "Cliente WhatsApp") if contacts else "Cliente WhatsApp"

                    for msg in messages:
                        wam_id = msg.get("id")
                        from_phone = msg.get("from")
                        msg_type = msg.get("type", "text")
                        body = ""

                        if msg_type == "text":
                            body = msg.get("text", {}).get("body", "")
                        elif msg_type == "interactive":
                            inter = msg.get("interactive", {})
                            itype = inter.get("type")
                            if itype == "button_reply":
                                body = inter.get("button_reply", {}).get("id") or inter.get("button_reply", {}).get("title", "")
                            elif itype == "list_reply":
                                body = inter.get("list_reply", {}).get("id") or inter.get("list_reply", {}).get("title", "")
                            else:
                                body = "[Resposta Interativa]"
                        elif msg_type in ["image", "video", "document", "audio"]:
                            body = f"[{msg_type.upper()} recebido]"

                        if from_phone:
                            with db() as conn:
                                conn.execute(
                                    "INSERT INTO whatsapp_messages(wam_id, phone, direction, message_type, body, status) VALUES(%s,%s,%s,%s,%s,%s)",
                                    (wam_id, from_phone, "inbound", msg_type, body, "received"),
                                )
                                lead = conn.execute("SELECT id FROM crm_leads WHERE phone=%s", (from_phone,)).fetchone()
                                if not lead:
                                    conn.execute(
                                        "INSERT INTO crm_leads(name, phone, channel, status) VALUES(%s,%s,%s,%s)",
                                        (sender_name, from_phone, "WhatsApp", "novo"),
                                    )
                                conn.commit()
        except Exception as e:
            print("[WhatsApp Webhook POST Error]:", e)

        return jsonify({"status": "ok"}), 200
