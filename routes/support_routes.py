"""
M-One Support Routes (routes/support_routes.py)
Rotas da Central de Suporte: portal do colaborador (/suporte),
painel executivo do Fauzer (/admin/suporte), endpoints REST e upload de prints (Ctrl+V).
Anti-monólito: < 500 linhas.
"""

from __future__ import annotations

import logging
from flask import Blueprint, abort, jsonify, redirect, render_template, request, send_from_directory, url_for
from routes.helpers import current_user, login_required, roles_required
from services.support_service import (
    SUPPORT_UPLOAD_DIR,
    add_ticket_reply,
    create_ticket,
    get_available_modules_for_user,
    get_support_badges,
    get_ticket_details,
    is_fauzer_user,
    list_all_tickets_for_admin,
    list_tickets_for_user,
    save_support_attachment,
)

logger = logging.getLogger(__name__)

support_bp = Blueprint("support", __name__)


@support_bp.route("/suporte", methods=["GET"])
@login_required
def support_user_page():
    """Portal do Colaborador: abertura e acompanhamento de chamados de suporte."""
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    tickets = list_tickets_for_user(me["id"])
    available_modules = get_available_modules_for_user(me)
    return render_template(
        "support/user_tickets.html",
        me=me,
        tickets=tickets,
        available_modules=available_modules,
    )


@support_bp.route("/admin/suporte", methods=["GET"])
@login_required
def support_admin_page():
    """Painel Executivo de Triagem e Resolução do Fauzer (exclusivo para o Fauzer)."""
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    if not is_fauzer_user(me):
        return redirect(url_for("support.support_user_page"))
    status_filter = request.args.get("status", "todos")
    tickets = list_all_tickets_for_admin(status_filter=status_filter)
    badges = get_support_badges(me)
    return render_template(
        "support/admin_tickets.html",
        me=me,
        tickets=tickets,
        current_status=status_filter,
        badges=badges,
    )


@support_bp.route("/api/suporte/badges", methods=["GET"])
@login_required
def api_support_badges():
    """Endpoint leve para badge na sidebar e banner superior pulsante."""
    me = current_user()
    data = get_support_badges(me)
    return jsonify({"success": True, **data}), 200


@support_bp.route("/api/suporte/upload", methods=["POST"])
@login_required
def api_support_upload():
    """Recebe prints de tela via upload tradicional ou Base64 (Ctrl+V)."""
    # 1. Checa Base64 JSON (Ctrl+V)
    json_data = request.get_json(silent=True) or {}
    b64_image = json_data.get("image_base64")
    if b64_image:
        url = save_support_attachment(b64_image)
        if url:
            return jsonify({"success": True, "url": url}), 200
        return jsonify({"success": False, "error": "Falha ao processar print colado"}), 400

    # 2. Checa arquivo via multipart/form-data
    if "file" in request.files:
        file_obj = request.files["file"]
        if file_obj.filename:
            url = save_support_attachment(file_obj)
            if url:
                return jsonify({"success": True, "url": url}), 200
        return jsonify({"success": False, "error": "Arquivo inválido"}), 400

    return jsonify({"success": False, "error": "Nenhuma imagem recebida"}), 400


@support_bp.route("/api/suporte/tickets", methods=["POST"])
@login_required
def api_create_ticket():
    """Cria um novo chamado com anexos e aciona notificação no WhatsApp."""
    me = current_user()
    body = request.get_json(silent=True) or {}

    module_key = body.get("module_key", "").strip()
    module_label = body.get("module_label", "").strip() or module_key
    title = body.get("title", "").strip()
    description = body.get("description", "").strip()
    urgency = body.get("urgency", "urgente").strip()
    attachments = body.get("attachments", [])

    if not title or not description or not module_key:
        return jsonify({"success": False, "error": "Preencha a área, o título e o relato detalhado do problema."}), 400

    res = create_ticket(
        user=me,
        module_key=module_key,
        module_label=module_label,
        title=title,
        description=description,
        urgency=urgency,
        attachments=attachments,
    )
    return jsonify(res), 201


@support_bp.route("/api/suporte/tickets/<int:ticket_id>", methods=["GET"])
@login_required
def api_get_ticket_details(ticket_id: int):
    """Retorna detalhes e timeline do chamado com marcação de leitura (Fauzer vê todos, solicitante vê o seu)."""
    me = current_user()
    is_staff = is_fauzer_user(me)
    ticket = get_ticket_details(ticket_id=ticket_id, current_user_id=me["id"], is_admin=is_staff)
    if not ticket:
        return jsonify({"success": False, "error": "Chamado não encontrado ou acesso não autorizado."}), 404

    return jsonify({"success": True, "ticket": ticket}), 200


@support_bp.route("/api/suporte/tickets/<int:ticket_id>/reply", methods=["POST"])
@login_required
def api_reply_ticket(ticket_id: int):
    """Adiciona resposta à timeline, permitindo exclusivamente ao Fauzer alterar status ou concluir com nota."""
    me = current_user()
    is_staff = is_fauzer_user(me)
    body = request.get_json(silent=True) or {}

    # Solicitantes só podem responder ao próprio chamado
    if not is_staff:
        ticket = get_ticket_details(ticket_id=ticket_id, current_user_id=me["id"], is_admin=False)
        if not ticket:
            return jsonify({"success": False, "error": "Acesso não autorizado a este chamado."}), 403

    message_text = body.get("message_text", "").strip()
    attachments = body.get("attachments", [])
    new_status = body.get("new_status") if is_staff else None
    resolution_notes = body.get("resolution_notes") if is_staff else None

    # Se for solicitante reabrindo chamado resolvido
    if not is_staff and body.get("reopen"):
        new_status = "pendente"

    if not message_text and not resolution_notes and not new_status:
        return jsonify({"success": False, "error": "Informe uma mensagem ou nota de resolução."}), 400

    res = add_ticket_reply(
        ticket_id=ticket_id,
        sender_id=me["id"],
        is_staff=is_staff,
        message_text=message_text or "Status atualizado.",
        attachments=attachments,
        new_status=new_status,
        resolution_notes=resolution_notes,
    )
    return jsonify(res), 200


@support_bp.route("/uploads/support/<path:filename>", methods=["GET"])
@login_required
def serve_support_upload(filename: str):
    """Serve arquivos e prints de suporte com segurança para usuários autenticados."""
    target_path = SUPPORT_UPLOAD_DIR / filename
    if not target_path.exists():
        abort(404)
    return send_from_directory(SUPPORT_UPLOAD_DIR, filename, as_attachment=False)

