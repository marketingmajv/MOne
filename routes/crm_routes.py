"""
M-One CRM & WhatsApp Blueprint (routes/crm_routes.py)
Rotas do Funil Kanban, Chat WhatsApp, Gestão de Leads e Configurações da Meta Cloud API.
"""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from database import db
from routes.helpers import audit, crm_pilot_required, login_required
from services.whatsapp_service import get_whatsapp_config, send_whatsapp_message

crm_bp = Blueprint("crm", __name__)


@crm_bp.route("/api/whatsapp/send", methods=["POST"])
@login_required
@crm_pilot_required
def api_send_whatsapp():
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    text = data.get("text", "").strip()
    if not phone or not text:
        return jsonify({"success": False, "error": "Telefone e texto são obrigatórios."}), 400
    res = send_whatsapp_message(phone, text)
    return jsonify(res)


@crm_bp.route("/integrations/whatsapp", methods=["GET", "POST"])
@login_required
@crm_pilot_required
def integrations_whatsapp():
    cfg_dict = get_whatsapp_config()

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        waba_id = request.form.get("waba_id", "").strip()
        phone_number_id = request.form.get("phone_number_id", "").strip()
        token = request.form.get("token", "").strip()
        verify_token = request.form.get("verify_token", "").strip()
        welcome_message = request.form.get("welcome_message", "").strip()
        default_response = request.form.get("default_response", "").strip()
        media_response = request.form.get("media_response", "").strip()
        support_flow = request.form.get("support_flow", "").strip()
        profile_description = request.form.get("profile_description", "").strip()
        profile_sector = request.form.get("profile_sector", "").strip()
        profile_email = request.form.get("profile_email", "").strip()
        profile_website = request.form.get("profile_website", "").strip()
        profile_address = request.form.get("profile_address", "").strip()
        action_type = request.form.get("action_type", "save")

        with db() as conn:
            if action_type == "disconnect":
                conn.execute(
                    """UPDATE whatsapp_config SET number_status='Desconectado', account_status='Inativo', updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
                    (cfg_dict.get("id"),)
                )
                conn.commit()
                flash("Conta do WhatsApp desconectada.", "warning")
            else:
                conn.execute(
                    """UPDATE whatsapp_config SET display_name=%s, phone_number=%s, waba_id=%s, phone_number_id=%s, token=%s,
                       verify_token=%s, welcome_message=%s, default_response=%s, media_response=%s, support_flow=%s,
                       profile_description=%s, profile_sector=%s, profile_email=%s, profile_website=%s, profile_address=%s,
                       number_status='Conectado', account_status='Ativo', updated_at=CURRENT_TIMESTAMP
                       WHERE id=%s""",
                    (
                        display_name or cfg_dict.get("display_name"),
                        phone_number or cfg_dict.get("phone_number"),
                        waba_id or cfg_dict.get("waba_id"),
                        phone_number_id or cfg_dict.get("phone_number_id"),
                        token or cfg_dict.get("token"),
                        verify_token or cfg_dict.get("verify_token"),
                        welcome_message or cfg_dict.get("welcome_message"),
                        default_response or cfg_dict.get("default_response"),
                        media_response or cfg_dict.get("media_response"),
                        support_flow or cfg_dict.get("support_flow"),
                        profile_description or cfg_dict.get("profile_description"),
                        profile_sector or cfg_dict.get("profile_sector"),
                        profile_email or cfg_dict.get("profile_email"),
                        profile_website or cfg_dict.get("profile_website"),
                        profile_address or cfg_dict.get("profile_address"),
                        cfg_dict.get("id")
                    )
                )
                conn.commit()
                flash("Configurações do WhatsApp Business salvas e atualizadas com sucesso!", "success")

        return redirect(url_for("integrations_whatsapp"))

    webhook_url = url_for("whatsapp_webhook", _external=True)
    return render_template("integrations_whatsapp.html", cfg=cfg_dict, webhook_url=webhook_url)


@crm_bp.route("/crm", methods=["GET"])
@login_required
@crm_pilot_required
def crm():
    with db() as conn:
        leads_rows = conn.execute(
            """
            SELECT l.*, p.name AS product_name, u.name AS assigned_name,
                   (SELECT body FROM whatsapp_messages WHERE phone=l.phone ORDER BY id DESC LIMIT 1) AS last_message,
                   (SELECT sent_at FROM whatsapp_messages WHERE phone=l.phone ORDER BY id DESC LIMIT 1) AS last_activity
            FROM crm_leads l
            LEFT JOIN products p ON p.name = l.product_interest
            LEFT JOIN users u ON u.id = l.assigned_to
            ORDER BY l.updated_at DESC
            """
        ).fetchall()

        conversations_rows = conn.execute(
            """
            SELECT m.phone,
                   MAX(m.sent_at) AS last_activity,
                   (SELECT body FROM whatsapp_messages WHERE phone=m.phone ORDER BY id DESC LIMIT 1) AS last_message,
                   (SELECT direction FROM whatsapp_messages WHERE phone=m.phone ORDER BY id DESC LIMIT 1) AS last_direction,
                   (SELECT message_type FROM whatsapp_messages WHERE phone=m.phone ORDER BY id DESC LIMIT 1) AS last_type,
                   l.id AS lead_id, l.name AS lead_name, l.status AS lead_status, l.product_interest
            FROM whatsapp_messages m
            LEFT JOIN crm_leads l ON l.phone = m.phone
            GROUP BY m.phone, l.id, l.name, l.status, l.product_interest
            ORDER BY MAX(m.sent_at) DESC
            """
        ).fetchall()

        products_list = conn.execute("SELECT id, name, wholesale_price, retail_price FROM products ORDER BY name").fetchall()
        users_list = conn.execute("SELECT id, name, role FROM users WHERE active=TRUE ORDER BY name").fetchall()

    leads_by_status = {
        "novo": [],
        "qualificacao": [],
        "proposta": [],
        "negociacao": [],
        "fechado": [],
        "perdido": [],
    }

    total_leads = len(leads_rows)
    new_count = 0

    for l in leads_rows:
        ld = dict(l)
        st = ld.get("status") or "novo"
        if st not in leads_by_status:
            st = "novo"
        leads_by_status[st].append(ld)
        if st == "novo":
            new_count += 1

    conversations = [dict(c) for c in conversations_rows]

    return render_template(
        "crm.html",
        leads_by_status=leads_by_status,
        conversations=conversations,
        products=products_list,
        users=users_list,
        total_leads=total_leads,
        new_count=new_count,
    )


@crm_bp.route("/api/crm/conversations", methods=["GET"])
@login_required
@crm_pilot_required
def api_crm_conversations():
    with db() as conn:
        rows = conn.execute(
            """
            SELECT m.phone,
                   MAX(m.sent_at) AS last_activity,
                   (SELECT body FROM whatsapp_messages WHERE phone=m.phone ORDER BY id DESC LIMIT 1) AS last_message,
                   (SELECT direction FROM whatsapp_messages WHERE phone=m.phone ORDER BY id DESC LIMIT 1) AS last_direction,
                   (SELECT message_type FROM whatsapp_messages WHERE phone=m.phone ORDER BY id DESC LIMIT 1) AS last_type,
                   l.id AS lead_id, l.name AS lead_name, l.status AS lead_status, l.product_interest
            FROM whatsapp_messages m
            LEFT JOIN crm_leads l ON l.phone = m.phone
            GROUP BY m.phone, l.id, l.name, l.status, l.product_interest
            ORDER BY MAX(m.sent_at) DESC
            """
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@crm_bp.route("/api/crm/messages/<phone>", methods=["GET"])
@login_required
@crm_pilot_required
def api_crm_messages(phone):
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM whatsapp_messages WHERE phone=%s ORDER BY sent_at ASC, id ASC",
            (clean_phone,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@crm_bp.route("/crm/lead/new", methods=["POST"])
@login_required
@crm_pilot_required
def crm_lead_new():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    product_interest = request.form.get("product_interest", "").strip()
    status = request.form.get("status", "novo").strip()
    notes = request.form.get("notes", "").strip()
    assigned_to = request.form.get("assigned_to") or None

    if not name or not phone:
        flash("Nome e telefone do Lead são obrigatórios.", "danger")
        return redirect(url_for("crm"))

    clean_phone = "".join(ch for ch in phone if ch.isdigit())
    if not clean_phone.startswith("55") and len(clean_phone) <= 11:
        clean_phone = f"55{clean_phone}"

    with db() as conn:
        existing = conn.execute("SELECT id FROM crm_leads WHERE phone=%s", (clean_phone,)).fetchone()
        if existing:
            flash(f"Este número de telefone ({clean_phone}) já possui um Lead cadastrado.", "warning")
            return redirect(url_for("crm"))

        conn.execute(
            "INSERT INTO crm_leads(name, phone, email, product_interest, status, notes, assigned_to, channel) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (name, clean_phone, email, product_interest, status, notes, assigned_to, "Manual"),
        )
        conn.commit()

    audit("crm.lead_created", f"lead_phone={clean_phone}; name={name}")
    flash("Novo Lead cadastrado no CRM com sucesso!", "success")
    return redirect(url_for("crm"))


@crm_bp.route("/crm/lead/<int:lid>/status", methods=["POST"])
@login_required
@crm_pilot_required
def crm_lead_status(lid: int):
    new_status = request.form.get("status", "novo")
    with db() as conn:
        conn.execute("UPDATE crm_leads SET status=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (new_status, lid))
        conn.commit()
    audit("crm.lead_status_updated", f"lead_id={lid}; status={new_status}")
    flash("Status do Lead atualizado.", "success")
    return redirect(url_for("crm"))


@crm_bp.route("/crm/chat/<phone>", methods=["GET", "POST"])
@login_required
@crm_pilot_required
def crm_chat(phone):
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())

    if request.method == "POST":
        text = request.form.get("message", "").strip()
        if text:
            send_whatsapp_message(clean_phone, text)
            with db() as conn:
                conn.execute("UPDATE crm_leads SET bot_paused=1 WHERE phone=%s", (clean_phone,))
                conn.commit()
            flash("Mensagem enviada via WhatsApp! (Bot pausado para este atendimento)", "success")
        return redirect(url_for("crm_chat", phone=clean_phone))

    with db() as conn:
        lead = conn.execute("SELECT * FROM crm_leads WHERE phone=%s", (clean_phone,)).fetchone()
        messages = conn.execute("SELECT * FROM whatsapp_messages WHERE phone=%s ORDER BY sent_at ASC, id ASC", (clean_phone,)).fetchall()
        products = conn.execute("SELECT id, name FROM products ORDER BY name").fetchall()

    return render_template("crm_chat.html", phone=clean_phone, lead=lead or {}, messages=messages, products=products)
