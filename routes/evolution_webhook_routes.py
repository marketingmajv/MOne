"""
M-One Evolution API Webhook Blueprint (routes/evolution_webhook_routes.py)
Recepção de eventos em tempo real da Evolution API: espelhamento de mensagens (inbound/outbound),
transcrição de áudios via IA e atualização automática do CRM e Analisador de Chats.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from database import db
from services.audio_transcription_service import transcribe_audio

logger = logging.getLogger(__name__)

evolution_webhook_bp = Blueprint("evolution_webhook", __name__)


def _clean_phone(raw_jid: str) -> str:
    """Extrai apenas os dígitos do telefone a partir de um JID do WhatsApp."""
    if not raw_jid:
        return ""
    phone_part = raw_jid.split("@")[0]
    digits = "".join(c for c in phone_part if c.isdigit())
    if not digits.startswith("55") and len(digits) in (10, 11):
        digits = f"55{digits}"
    return digits


@evolution_webhook_bp.route("/webhook/evolution", methods=["POST"])
def evolution_webhook():
    """Endpoint receptor de webhooks da Evolution API (open-source)."""
    payload = request.get_json(silent=True) or {}
    event_type = payload.get("event") or payload.get("type", "")
    instance_name = payload.get("instance") or payload.get("instanceName", "")

    # Normalizar nomes de eventos (ex: messages.upsert -> MESSAGES_UPSERT)
    norm_event = event_type.upper().replace(".", "_")

    # Registrar log de auditoria no Centro de Conexões
    try:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO webhook_event_logs (service, event_type, sender, summary, payload)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    "evolution_api",
                    norm_event,
                    instance_name,
                    f"Evento {norm_event} da instância {instance_name}",
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
    except Exception as log_err:
        logger.debug("Falha ao gravar webhook_event_log: %s", log_err)

    # 1. Tratar atualização de conexão (CONNECTION_UPDATE)
    if norm_event == "CONNECTION_UPDATE":
        return _handle_connection_update(instance_name, payload)

    # 2. Tratar novas mensagens (MESSAGES_UPSERT)
    if norm_event == "MESSAGES_UPSERT":
        return _handle_messages_upsert(instance_name, payload)

    return jsonify({"status": "ignored", "event": norm_event}), 200


def _handle_connection_update(instance_name: str, payload: dict):
    """Atualiza o estado de conexão e bateria da linha monitorada."""
    data = payload.get("data") or {}
    state = (data.get("state") or "disconnected").lower()
    battery = data.get("battery") or data.get("batteryLevel")

    is_monitored = state in ("open", "connected")
    try:
        with db() as conn:
            conn.execute(
                """
                UPDATE whatsapp_monitored_lines
                SET connection_status = %s,
                    is_monitored = %s,
                    battery_level = COALESCE(%s, battery_level),
                    updated_at = CURRENT_TIMESTAMP
                WHERE LOWER(instance_name) = LOWER(%s)
                """,
                (state, is_monitored, battery, instance_name),
            )
            conn.commit()
    except Exception as e:
        logger.error("[Evolution Webhook] Erro ao atualizar status de conexão: %s", e)

    return jsonify({"status": "updated", "state": state}), 200


def _handle_messages_upsert(instance_name: str, payload: dict):
    """Processa mensagens recebidas ou enviadas pelo vendedor via WhatsApp."""
    data = payload.get("data") or {}
    key = data.get("key") or {}
    remote_jid = key.get("remoteJid", "")

    # Ignorar mensagens de grupos (@g.us), canais (@newsletter) e status (@broadcast)
    if "@g.us" in remote_jid or "@broadcast" in remote_jid or "@newsletter" in remote_jid:
        return jsonify({"status": "ignored_group_or_broadcast"}), 200

    phone = _clean_phone(remote_jid)
    if not phone:
        return jsonify({"status": "invalid_phone"}), 200

    from_me = bool(key.get("fromMe"))
    direction = "outbound" if from_me else "inbound"
    wam_id = key.get("id") or f"evo_{datetime.now().timestamp()}"
    push_name = data.get("pushName") or "Cliente WhatsApp"

    # Buscar vendedor vinculado à instância
    seller_name = None
    seller_id = None
    try:
        with db() as conn:
            line_row = conn.execute(
                "SELECT assigned_seller_name, assigned_user_id, is_monitored FROM whatsapp_monitored_lines WHERE LOWER(instance_name) = LOWER(%s) LIMIT 1",
                (instance_name,),
            ).fetchone()
            if line_row:
                seller_name = line_row.get("assigned_seller_name")
                seller_id = line_row.get("assigned_user_id")
                # Se linha estiver explicitamente desplugada, ignorar
                if not line_row.get("is_monitored", True):
                    return jsonify({"status": "line_unplugged"}), 200
    except Exception as fetch_err:
        logger.debug("Falha ao buscar vendedor da instância: %s", fetch_err)

    # Extrair corpo e tipo da mensagem
    message_obj = data.get("message") or {}
    message_type = (data.get("messageType") or "conversation").lower()
    body_text = ""
    media_url = None

    if "conversation" in message_obj:
        body_text = message_obj.get("conversation", "")
    elif "extendedTextMessage" in message_obj:
        body_text = message_obj.get("extendedTextMessage", {}).get("text", "")
    elif "audioMessage" in message_obj:
        message_type = "audio"
        audio_info = message_obj.get("audioMessage", {})
        media_url = audio_info.get("url")
        base64_audio = data.get("base64")

        # Acionar transcrição de áudio inteligente com Groq Whisper
        transcription = None
        if base64_audio:
            transcription = transcribe_audio(base64_audio, filename="voice_note.ogg", mimetype="audio/ogg")
        elif media_url:
            transcription = transcribe_audio(media_url, filename="voice_note.ogg", mimetype="audio/ogg")

        if transcription:
            body_text = f'🗣️ [Áudio Transcrito]: "{transcription}"'
        else:
            body_text = "🎙️ [Mensagem de Áudio]"

    elif "imageMessage" in message_obj:
        message_type = "image"
        caption = message_obj.get("imageMessage", {}).get("caption", "")
        body_text = f"📷 [Imagem] {caption}".strip()
    elif "documentMessage" in message_obj:
        message_type = "document"
        title = message_obj.get("documentMessage", {}).get("title", "")
        body_text = f"📄 [Documento] {title}".strip()
    elif "videoMessage" in message_obj:
        message_type = "video"
        body_text = "🎥 [Vídeo]"
    else:
        body_text = f"[{message_type.upper()}]"

    if not body_text:
        body_text = f"[{message_type}]"

    # Inserir no histórico de mensagens (whatsapp_messages)
    try:
        with db() as conn:
            # Prevenção contra duplicidade de wam_id
            existing = conn.execute(
                "SELECT id FROM whatsapp_messages WHERE wam_id = %s LIMIT 1",
                (wam_id,),
            ).fetchone()

            if not existing:
                conn.execute(
                    """
                    INSERT INTO whatsapp_messages 
                    (wam_id, phone, direction, message_type, body, media_url, status, sent_at, seller_id, seller_name, instance_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s)
                    """,
                    (
                        wam_id,
                        phone,
                        direction,
                        message_type,
                        body_text,
                        media_url,
                        "delivered" if direction == "outbound" else "received",
                        seller_id,
                        seller_name,
                        instance_name,
                    ),
                )

            # Atualizar ou criar Lead no CRM
            lead = conn.execute(
                "SELECT id, name, assigned_to FROM crm_leads WHERE phone = %s LIMIT 1",
                (phone,),
            ).fetchone()

            if lead:
                # Atualizar data do último contato e vendedor se ainda não atribuído
                update_sql = "UPDATE crm_leads SET updated_at = CURRENT_TIMESTAMP"
                params = []
                if not lead.get("assigned_to") and seller_id:
                    update_sql += ", assigned_to = %s"
                    params.append(seller_id)
                update_sql += " WHERE id = %s"
                params.append(lead["id"])
                conn.execute(update_sql, tuple(params))
            else:
                # Criar novo lead orgânico/WhatsApp
                display_name = push_name if (push_name and push_name != "Cliente WhatsApp") else f"WhatsApp {phone[-4:]}"
                conn.execute(
                    """
                    INSERT INTO crm_leads (name, phone, status, channel, assigned_to, traffic_source, created_at, updated_at)
                    VALUES (%s, %s, 'lead', 'whatsapp', %s, 'whatsapp_direct', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (display_name, phone, seller_id),
                )

            conn.commit()
    except Exception as db_err:
        logger.error("[Evolution Webhook] Falha ao persistir mensagem e lead: %s", db_err)
        return jsonify({"status": "error", "message": str(db_err)}), 500

    return jsonify({"status": "success", "phone": phone, "direction": direction}), 200
