"""
M-One WhatsApp Automation Blueprint (routes/automation_routes.py)
Rotas do Estúdio Visual de Automação, Editor de Fluxos, Simulador, Inbox Multi-atendente e APIs.
Acesso restrito exclusivamente aos usuários autorizados (Jam e Fauzer).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import db
from services.automation.schema import (
    ensure_automation_schema,
    seed_default_flows_if_empty,
)

automation_bp = Blueprint("automation", __name__)


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with db() as conn:
        u = conn.execute("SELECT id, username, role FROM users WHERE id=?", (uid,)).fetchone()
        return dict(u) if u else None


def crm_pilot_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        u = current_user()
        if not u or str(u.get("username", "")).strip().lower() not in ["jam", "fauzer"]:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Acesso restrito a Jam e Fauzer."}), 403
            flash("O módulo de Automações é restrito a Jam e Fauzer.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return inner


# ==========================================
# STUDIO VISUAL & FLOW BUILDER ROUTES
# ==========================================

@automation_bp.route("/automation", methods=["GET"])
@automation_bp.route("/automation/studio", methods=["GET"])
@crm_pilot_required
def automation_studio():
    ensure_automation_schema()
    seed_default_flows_if_empty()
    with db() as conn:
        flows = conn.execute("SELECT * FROM automation_flows ORDER BY updated_at DESC").fetchall()
        flows_list = [dict(f) for f in flows]

    return render_template("automation_studio.html", flows=flows_list)



@automation_bp.route("/api/automation/flows", methods=["GET"])
@crm_pilot_required
def api_get_flows():
    ensure_automation_schema()
    with db() as conn:
        flows = conn.execute("SELECT * FROM automation_flows ORDER BY updated_at DESC").fetchall()
    return jsonify([dict(f) for f in flows])


SUPPORTED_NODE_TYPES = {
    "trigger", "send_message", "send_media", "send_menu", "interactive", "ask_question",
    "condition", "delay", "webhook", "action", "crm_action", "transfer",
    "transfer_agent", "ai_reply", "end"
}


def validate_flow_graph(graph_data: dict) -> list:
    """Valida tipos de nós, IDs, edges, configs obrigatórias e alcance a partir do gatilho."""
    errors = []
    if not isinstance(graph_data, dict):
        return ["O formato do grafo é inválido."]

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    if not nodes:
        return ["O fluxo deve possuir pelo menos um nó."]

    triggers = [n for n in nodes if n.get("type") == "trigger"]
    if len(triggers) != 1:
        errors.append("O fluxo deve conter exatamente um nó de Gatilho (Trigger).")

    node_ids = set()
    for n in nodes:
        nid = n.get("id")
        ntype = n.get("type")

        if not nid:
            errors.append("Existe um bloco no fluxo sem ID válido.")
            continue
        if nid in node_ids:
            errors.append(f"O ID de nó '{nid}' está duplicado no fluxo.")
        node_ids.add(nid)

        if ntype not in SUPPORTED_NODE_TYPES:
            errors.append(f"O nó '{nid}' possui o tipo não suportado '{ntype}'.")

        cfg = n.get("config", {})
        if ntype == "send_message" and not (cfg.get("text") or cfg.get("title")):
            errors.append(f"O nó de mensagem '{nid}' precisa de um texto configurado.")
        elif ntype == "send_media":
            m_url = cfg.get("media_url")
            m_type = cfg.get("media_type", "image")
            if not m_url or not isinstance(m_url, str) or not m_url.startswith(("http://", "https://")):
                errors.append(f"O nó de mídia '{nid}' precisa de uma URL pública válida (http:// ou https://).")
            if m_type not in ["image", "document", "audio", "video"]:
                errors.append(f"O nó de mídia '{nid}' possui tipo de mídia inválido '{m_type}'.")
        elif ntype in ["send_menu", "interactive"] and not cfg.get("options"):
            errors.append(f"O nó de menu '{nid}' precisa de pelo menos uma opção configurada.")
        elif ntype == "ask_question" and not (cfg.get("text") or cfg.get("question")):
            errors.append(f"O nó de pergunta '{nid}' precisa de um texto de pergunta.")
        elif ntype == "webhook" and not cfg.get("url"):
            errors.append(f"O nó de webhook '{nid}' precisa de uma URL configurada.")

    for idx, e in enumerate(edges):
        src = e.get("source")
        tgt = e.get("target")
        if not src or src not in node_ids:
            errors.append(f"A conexão #{idx+1} possui a origem (source) '{src}' inválida.")
        if not tgt or tgt not in node_ids:
            errors.append(f"A conexão #{idx+1} possui o destino (target) '{tgt}' inválido.")

    if triggers:
        start_id = triggers[0]["id"]
        reachable = set()
        queue = [start_id]
        while queue:
            curr = queue.pop(0)
            if curr in reachable:
                continue
            reachable.add(curr)
            out_targets = [e["target"] for e in edges if e.get("source") == curr and e.get("target") in node_ids]
            queue.extend(out_targets)

        unreachable = node_ids - reachable
        if unreachable:
            errors.append(f"Existem blocos isolados desconectados no fluxo: {', '.join(unreachable)}")

    return errors


@automation_bp.route("/api/automation/flows/save", methods=["POST"])
@crm_pilot_required
def api_save_flow():
    ensure_automation_schema()
    data = request.get_json(silent=True) or {}
    flow_id = data.get("id")
    name = data.get("name", "").strip() or "Novo Fluxo de Automação"
    description = data.get("description", "").strip()
    graph_data = data.get("graph_data") or {}
    trigger_type = data.get("trigger_type", "keyword")
    trigger_config = data.get("trigger_config") or {}

    graph_str = json.dumps(graph_data) if isinstance(graph_data, dict) else str(graph_data)
    trg_cfg_str = json.dumps(trigger_config) if isinstance(trigger_config, dict) else str(trigger_config)

    u = current_user()
    user_id = u["id"] if u else 17

    with db() as conn:
        if flow_id:
            conn.execute(
                """
                UPDATE automation_flows 
                SET name=?, description=?, draft_version_data=?, draft_trigger_type=?, draft_trigger_config=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (name, description, graph_str, trigger_type, trg_cfg_str, flow_id)
            )
            saved_id = flow_id
        else:
            cur = conn.execute(
                """
                INSERT INTO automation_flows (name, description, status, version, draft_version_data, draft_trigger_type, draft_trigger_config, created_by)
                VALUES (?, ?, 'draft', 1, ?, ?, ?, ?)
                """,
                (name, description, graph_str, trigger_type, trg_cfg_str, user_id)
            )
            saved_id = cur.lastrowid

        conn.commit()

    return jsonify({"success": True, "id": saved_id, "message": "Rascunho do fluxo salvo com sucesso!"})


@automation_bp.route("/api/automation/flows/<int:fid>/activate", methods=["POST"])
@crm_pilot_required
def api_activate_flow(fid):
    ensure_automation_schema()
    with db() as conn:
        flow = conn.execute("SELECT * FROM automation_flows WHERE id=?", (fid,)).fetchone()
        if not flow:
            return jsonify({"success": False, "error": "Fluxo não encontrado."}), 404

        draft_data = flow["draft_version_data"]
        graph_obj = json.loads(draft_data or "{}") if isinstance(draft_data, str) else draft_data

        errors = validate_flow_graph(graph_obj)
        if errors:
            return jsonify({"success": False, "error": "O fluxo possui erros de validação.", "validation_errors": errors}), 400

        conn.execute(
            """
            UPDATE automation_flows 
            SET status='active', 
                active_version_data=draft_version_data, 
                active_trigger_type=COALESCE(draft_trigger_type, trigger_type),
                active_trigger_config=COALESCE(draft_trigger_config, trigger_config),
                version=version+1, 
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (fid,)
        )
        conn.commit()

    return jsonify({"success": True, "message": "Versão do fluxo validada e ativada com sucesso!"})


@automation_bp.route("/api/automation/flows/<int:fid>/duplicate", methods=["POST"])
@crm_pilot_required
def api_duplicate_flow(fid):
    ensure_automation_schema()
    with db() as conn:
        flow = conn.execute("SELECT * FROM automation_flows WHERE id=?", (fid,)).fetchone()
        if not flow:
            return jsonify({"success": False, "error": "Fluxo não encontrado."}), 404

        new_name = f"{flow['name']} (Cópia)"
        cur = conn.execute(
            """
            INSERT INTO automation_flows (name, description, status, version, draft_version_data, active_version_data, draft_trigger_type, draft_trigger_config, created_by)
            VALUES (?, ?, 'draft', 1, ?, ?, ?, ?, ?)
            """,
            (new_name, flow["description"], flow["draft_version_data"], flow["active_version_data"], flow["draft_trigger_type"], flow["draft_trigger_config"], session.get("user_id", 17))
        )
        new_id = cur.lastrowid
        conn.commit()

    return jsonify({"success": True, "id": new_id, "message": "Fluxo duplicado com sucesso!"})


@automation_bp.route("/api/automation/simulate", methods=["POST"])
@crm_pilot_required
def api_simulate_flow():
    ensure_automation_schema()
    """
    Simulador de conversa completo em memória com suporte a opções clicáveis e resumo final.
    """
    data = request.get_json(silent=True) or {}
    graph_data = data.get("graph_data") or {}
    user_input = data.get("input", "").strip()
    current_node_id = data.get("current_node_id")
    variables = data.get("variables") or {}

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    if not nodes:
        return jsonify({"success": False, "error": "O fluxo não possui nós."})

    visited_path = []
    responses = []
    completed = False

    # Inicializar simulador a partir do gatilho se current_node_id não for informado
    if not current_node_id:
        trigger_node = next((n for n in nodes if n.get("type") == "trigger"), nodes[0])
        current_node_id = trigger_node["id"]
        visited_path.append(current_node_id)

    curr_node = next((n for n in nodes if n["id"] == current_node_id), None)

    # Se estivermos em um nó aguardando entrada e o usuário enviou input
    if curr_node and user_input and curr_node.get("type") in ["ask_question", "send_menu", "interactive"]:
        cfg = curr_node.get("config", {})
        val_rule = cfg.get("validation", "text")
        save_var = cfg.get("save_variable", "user_input")

        # Tratar simulação de Timeout
        if user_input in ["__timeout__", "[TIMEOUT]", "timeout"]:
            responses.append({"type": "system_event", "text": f"⏳ Timeout esgotado ({cfg.get('timeout_seconds', 300)}s)"})
            timeout_edge = next((e for e in edges if e.get("source") == current_node_id and (e.get("source_handle") == "timeout" or e.get("port") == "timeout")), None)
            if timeout_edge:
                current_node_id = timeout_edge["target"]
                visited_path.append(current_node_id)
            else:
                completed = True
        else:
            # Se for menu, checar se casou com alguma opção
            matched_option_id = None
            if curr_node.get("type") in ["send_menu", "interactive"]:
                opts = cfg.get("options", [])
                matched_opt = None
                for idx, o in enumerate(opts):
                    opt_id_val = str(o.get("id", "")).lower()
                    opt_text_val = str(o.get("text", "")).lower()
                    opt_num_val = str(idx + 1)
                    if user_input.lower() in [opt_id_val, opt_text_val, opt_num_val] or user_input.lower() == f"{opt_num_val}.":
                        matched_opt = o
                        matched_option_id = o.get("id") or f"opt_{idx}"
                        break
                if matched_opt:
                    user_input = matched_opt.get("text") or matched_opt.get("id")

            from services.automation.engine import (
                get_next_node_id,
                render_template_text,
                render_webhook_payload,
                validate_input_format,
            )
            is_valid = validate_input_format(val_rule, user_input)

            if is_valid:
                variables[save_var] = user_input
                responses.append({"type": "user_text", "text": user_input})
                
                # Buscar se há edge específica vinculada ao handle de opção ou 'valid'
                branch_choice = matched_option_id or user_input
                next_id = get_next_node_id(graph_data, current_node_id, branch_choice=branch_choice, port="valid", variables=variables)
                if not next_id:
                    next_id = get_next_node_id(graph_data, current_node_id, branch_choice=branch_choice, port="valid_answer", variables=variables)
                if next_id:
                    current_node_id = next_id
                    visited_path.append(current_node_id)
            else:
                responses.append({"type": "user_text", "text": user_input})
                invalid_edge = next((e for e in edges if e.get("source") == current_node_id and (e.get("source_handle") == "invalid" or e.get("port") == "invalid_answer")), None)
                if invalid_edge:
                    responses.append({"type": "bot_text", "text": f"⚠️ Formato inválido ({val_rule}). Transicionando para ramo de erro."})
                    current_node_id = invalid_edge["target"]
                    visited_path.append(current_node_id)
                else:
                    responses.append({"type": "bot_text", "text": f"⚠️ Formato inválido ({val_rule}). Por favor tente novamente."})
                    return jsonify({
                        "success": True,
                        "completed": False,
                        "current_node_id": current_node_id,
                        "visited_path": visited_path,
                        "responses": responses,
                        "variables": variables
                    })

    # Avançar nós consecutivamente (loop de execução em memória)
    from services.automation.adapters import execute_webhook_adapter
    from services.automation.engine import (
        get_next_node_id,
        render_template_text,
        render_webhook_payload,
    )
    steps = 0
    while current_node_id and steps < 20:
        steps += 1
        curr_node = next((n for n in nodes if n["id"] == current_node_id), None)
        if not curr_node:
            completed = True
            break

        node_type = curr_node.get("type")
        cfg = curr_node.get("config", {})

        if node_type == "trigger":
            direct_edge = next((e for e in edges if e["source"] == current_node_id), None)
            if direct_edge:
                current_node_id = direct_edge["target"]
                visited_path.append(current_node_id)
                continue

        elif node_type == "send_message":
            raw_text = cfg.get("text") or cfg.get("title") or "Mensagem da Automação"
            msg_text = render_template_text(raw_text, variables)
            responses.append({"type": "bot_text", "text": msg_text, "node_id": current_node_id})

        elif node_type in ["send_menu", "interactive"]:
            raw_text = cfg.get("title") or cfg.get("text") or "Escolha uma opção:"
            msg_text = render_template_text(raw_text, variables)
            opts = cfg.get("options", [])
            responses.append({"type": "bot_text", "text": msg_text, "node_id": current_node_id})
            if opts:
                responses.append({"type": "menu_options", "options": opts, "node_id": current_node_id})
            break  # Pausa no menu aguardando resposta

        elif node_type == "ask_question":
            raw_text = cfg.get("text") or cfg.get("question") or "Por favor responda à pergunta:"
            q_text = render_template_text(raw_text, variables)
            responses.append({"type": "bot_text", "text": q_text, "node_id": current_node_id})
            break  # Pausa na pergunta aguardando resposta

        elif node_type == "condition":
            branch_target = get_next_node_id(graph_data, current_node_id, variables=variables)
            if branch_target:
                current_node_id = branch_target
                visited_path.append(current_node_id)
                continue

        elif node_type == "webhook":
            raw_url = cfg.get("url", "").strip()
            url = render_template_text(raw_url, variables)
            method = cfg.get("method", "POST").upper()
            raw_payload = cfg.get("payload", "{}")
            payload = render_webhook_payload(raw_payload, variables)
            _res_code, res_body = execute_webhook_adapter(url, method, payload, "5527999990000", is_simulation=True)
            save_var = cfg.get("save_variable") or cfg.get("save_response_var") or cfg.get("response_variable") or cfg.get("variable")
            if save_var:
                try:
                    resp_data = json.loads(res_body)
                except (json.JSONDecodeError, TypeError, ValueError):
                    resp_data = res_body
                variables[save_var] = resp_data
            responses.append({"type": "system_event", "text": f"🌐 Webhook HTTP {method} -> {url} (Payload: {payload})", "node_id": current_node_id})

        elif node_type in ["action", "crm_action"]:
            act_type = cfg.get("action_type", "update_stage")
            assigned_name = str(cfg.get("assigned_to") or cfg.get("agent") or "fauzer").capitalize()
            if act_type in ["create_task", "follow_up"]:
                raw_task_title = cfg.get("task_title") or cfg.get("title") or cfg.get("note") or "Follow-up Lead WhatsApp"
                task_title = render_template_text(raw_task_title, variables)
                due_days = cfg.get("due_days", 1)
                responses.append({"type": "system_event", "text": f"📋 CRM: Tarefa '{task_title}' criada para {assigned_name} (+{due_days} dias)", "node_id": current_node_id})
            elif act_type in ["assign_seller", "assign_agent"]:
                responses.append({"type": "system_event", "text": f"👤 CRM: Atendimento atribuído ao vendedor '{assigned_name}'", "node_id": current_node_id})
            elif act_type in ["update_stage", "update_lead_status"]:
                responses.append({"type": "system_event", "text": f"📌 CRM: Etapa do funil alterada para '{cfg.get('status', 'em_atendimento')}'", "node_id": current_node_id})
            elif act_type == "update_lead":
                responses.append({"type": "system_event", "text": f"👤 CRM: Lead atualizado (Responsável: {assigned_name})", "node_id": current_node_id})
            else:
                responses.append({"type": "system_event", "text": f"🛠️ CRM: Ação {act_type} executada", "node_id": current_node_id})

        elif node_type in ["transfer", "transfer_agent"]:
            agent_name = str(cfg.get("assigned_to") or cfg.get("agent") or "fauzer").capitalize()
            raw_msg = cfg.get("message") or f"👨‍💼 Transferindo para o consultor {agent_name}..."
            msg_text = render_template_text(raw_msg, variables)
            responses.append({"type": "bot_text", "text": msg_text, "node_id": current_node_id})
            responses.append({"type": "system_event", "text": f"🟢 Atendimento transferido para {agent_name} (Bot pausado)", "node_id": current_node_id})
            completed = True
            break

        elif node_type == "end":
            responses.append({"type": "system_event", "text": "🏁 Fluxo finalizado com sucesso.", "node_id": current_node_id})
            completed = True
            break

        # Próximo nó
        next_id = get_next_node_id(graph_data, current_node_id, variables=variables)
        if not next_id:
            completed = True
            break
        current_node_id = next_id
        visited_path.append(current_node_id)

    return jsonify({
        "success": True,
        "completed": completed,
        "current_node_id": current_node_id,
        "visited_path": visited_path,
        "responses": responses,
        "variables": variables
    })


# ==========================================
# INBOX MULTI-ATENDENTE & CRM INTEGRATION
# ==========================================

@automation_bp.route("/automation/inbox", methods=["GET"])
@crm_pilot_required
def inbox():
    ensure_automation_schema()
    selected_phone = request.args.get("phone", "").strip()
    clean_selected = "".join(ch for ch in str(selected_phone) if ch.isdigit())

    with db() as conn:
        raw_leads = conn.execute(
            """
            SELECT l.*, 
                   (SELECT body FROM whatsapp_messages WHERE phone=l.phone ORDER BY id DESC LIMIT 1) AS last_message,
                   (SELECT sent_at FROM whatsapp_messages WHERE phone=l.phone ORDER BY id DESC LIMIT 1) AS last_activity,
                   (SELECT COUNT(*) FROM whatsapp_messages WHERE phone=l.phone AND direction='inbound' AND status='received') AS unread_count
            FROM crm_leads l
            ORDER BY l.updated_at DESC, l.id DESC
            """
        ).fetchall()

        conversations = [dict(l) for l in raw_leads]

        if not clean_selected and conversations:
            clean_selected = conversations[0]["phone"]

        lead = None
        messages = []
        tasks = []
        logs = []
        tags_list = []
        custom_fields_dict = {}

        if clean_selected:
            raw_lead = conn.execute("SELECT * FROM crm_leads WHERE phone=?", (clean_selected,)).fetchone()
            if raw_lead:
                lead = dict(raw_lead)
                try:
                    tags_list = json.loads(lead.get("tags") or "[]")
                except (json.JSONDecodeError, TypeError, ValueError):
                    tags_list = []
                try:
                    custom_fields_dict = json.loads(lead.get("custom_fields") or "{}")
                except (json.JSONDecodeError, TypeError, ValueError):
                    custom_fields_dict = {}

            raw_messages = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE phone=? ORDER BY sent_at ASC, id ASC", (clean_selected,)
            ).fetchall()
            messages = [dict(m) for m in raw_messages]

            raw_tasks = conn.execute("SELECT * FROM crm_tasks WHERE phone=? ORDER BY id DESC", (clean_selected,)).fetchall()
            tasks = [dict(t) for t in raw_tasks]

            raw_logs = conn.execute("SELECT * FROM automation_logs WHERE phone=? ORDER BY id DESC LIMIT 15", (clean_selected,)).fetchall()
            logs = [dict(lg) for lg in raw_logs]

        raw_canned = conn.execute("SELECT * FROM automation_canned_responses ORDER BY id ASC").fetchall()
        canned_responses = [dict(r) for r in raw_canned]
        if not canned_responses:
            default_canned = [
                ("Boas-vindas Padrão", "Olá! Seja bem-vindo à MAJ Mobilidade. Como posso te ajudar hoje?"),
                ("Modelos & Garantia", "Nossos veículos contam com garantia oficial MAJ e entrega rápida."),
                ("Solicitar Localização / CEP", "Qual a sua localização/CEP para calcularmos a melhor opção de frete?"),
                ("Transferência Humana", "Um de nossos consultores de vendas vai assumir seu atendimento agora.")
            ]
            for title, msg in default_canned:
                conn.execute("INSERT INTO automation_canned_responses (title, message) VALUES (?, ?)", (title, msg))
            conn.commit()
            canned_responses = [dict(r) for r in conn.execute("SELECT * FROM automation_canned_responses ORDER BY id ASC").fetchall()]

        wams_count = conn.execute("SELECT COUNT(*) FROM automation_processed_wams").fetchone()[0]
        active_sessions_count = conn.execute("SELECT COUNT(*) FROM automation_sessions WHERE status IN ('running', 'waiting_input', 'waiting_delay')").fetchone()[0]
        open_tickets_count = conn.execute("SELECT COUNT(*) FROM crm_leads WHERE COALESCE(ticket_status, 'open') != 'closed'").fetchone()[0]
        closed_tickets_count = conn.execute("SELECT COUNT(*) FROM crm_leads WHERE ticket_status = 'closed'").fetchone()[0]

        analytics = {
            "processed_wams": wams_count,
            "active_sessions": active_sessions_count,
            "open_tickets": open_tickets_count,
            "closed_tickets": closed_tickets_count
        }

    return render_template(
        "automation_inbox.html",
        conversations=conversations,
        selected_phone=clean_selected,
        lead=lead or {},
        tags_list=tags_list,
        custom_fields_dict=custom_fields_dict,
        messages=messages,
        tasks=tasks,
        logs=logs,
        canned_responses=canned_responses,
        analytics=analytics
    )


@automation_bp.route("/api/automation/inbox/toggle-bot", methods=["POST"])
@crm_pilot_required
def api_toggle_bot():
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())

    with db() as conn:
        lead = conn.execute("SELECT bot_paused FROM crm_leads WHERE phone=?", (clean_phone,)).fetchone()
        new_state = 0 if (lead and lead["bot_paused"]) else 1
        conn.execute("UPDATE crm_leads SET bot_paused=? WHERE phone=?", (new_state, clean_phone))
        conn.commit()

    status_txt = "pausado" if new_state else "retomado"
    return jsonify({"status": "ok", "paused": new_state, "message": f"Bot {status_txt} com sucesso!"})


@automation_bp.route("/api/automation/inbox/action", methods=["POST"])
@crm_pilot_required
def api_inbox_action():
    data = request.get_json(silent=True) or {}
    action = data.get("action", "").strip()
    phone = data.get("phone", "").strip()
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())

    if not clean_phone:
        return jsonify({"status": "error", "message": "Telefone inválido."}), 400

    with db() as conn:
        if action == "assign":
            agent = data.get("agent", "").strip()
            conn.execute("UPDATE crm_leads SET assigned_to=? WHERE phone=?", (agent, clean_phone))
            conn.commit()
            return jsonify({"status": "ok", "message": f"Atendimento atribuído a {agent or 'ninguém'}."})

        elif action == "close":
            conn.execute("UPDATE crm_leads SET ticket_status='closed' WHERE phone=?", (clean_phone,))
            conn.commit()
            return jsonify({"status": "ok", "message": "Atendimento encerrado."})

        elif action == "reopen":
            conn.execute("UPDATE crm_leads SET ticket_status='open' WHERE phone=?", (clean_phone,))
            conn.commit()
            return jsonify({"status": "ok", "message": "Atendimento reaberto com sucesso."})

        elif action == "mark_unread":
            conn.execute("UPDATE whatsapp_messages SET status='received' WHERE phone=? AND direction='inbound'", (clean_phone,))
            conn.commit()
            return jsonify({"status": "ok", "message": "Conversa marcada como não lida."})

        elif action == "mark_read":
            conn.execute("UPDATE whatsapp_messages SET status='read' WHERE phone=? AND direction='inbound'", (clean_phone,))
            conn.commit()
            return jsonify({"status": "ok", "message": "Conversa marcada como lida."})

        elif action == "save_notes":
            notes = data.get("notes", "").strip()
            conn.execute("UPDATE crm_leads SET notes=? WHERE phone=?", (notes, clean_phone))
            conn.commit()
            return jsonify({"status": "ok", "message": "Notas atualizadas."})

        elif action == "add_tag":
            tag = data.get("tag", "").strip()
            if tag:
                lead = conn.execute("SELECT tags FROM crm_leads WHERE phone=?", (clean_phone,)).fetchone()
                try:
                    tags_list = json.loads(lead["tags"] or "[]") if (lead and lead["tags"]) else []
                except (json.JSONDecodeError, TypeError, ValueError):
                    tags_list = []
                if tag not in tags_list:
                    tags_list.append(tag)
                    conn.execute("UPDATE crm_leads SET tags=? WHERE phone=?", (json.dumps(tags_list), clean_phone))
                    conn.commit()
                    return jsonify({"status": "ok", "tags": tags_list, "message": f"Tag '{tag}' adicionada com sucesso."})

        elif action == "remove_tag":
            tag = data.get("tag", "").strip()
            if tag:
                lead = conn.execute("SELECT tags FROM crm_leads WHERE phone=?", (clean_phone,)).fetchone()
                try:
                    tags_list = json.loads(lead["tags"] or "[]") if (lead and lead["tags"]) else []
                except (json.JSONDecodeError, TypeError, ValueError):
                    tags_list = []
                tags_list = [t for t in tags_list if t != tag]
                conn.execute("UPDATE crm_leads SET tags=? WHERE phone=?", (json.dumps(tags_list), clean_phone))
                conn.commit()
                return jsonify({"status": "ok", "tags": tags_list, "message": f"Tag '{tag}' removida com sucesso."})

        elif action in ["set_custom_field", "save_custom_field"]:
            key = data.get("key", "").strip()
            value = data.get("value")
            if key:
                lead = conn.execute("SELECT custom_fields FROM crm_leads WHERE phone=?", (clean_phone,)).fetchone()
                try:
                    fields_dict = json.loads(lead["custom_fields"] or "{}") if (lead and lead["custom_fields"]) else {}
                except (json.JSONDecodeError, TypeError, ValueError):
                    fields_dict = {}
                if value:
                    fields_dict[key] = value
                else:
                    fields_dict.pop(key, None)
                conn.execute("UPDATE crm_leads SET custom_fields=? WHERE phone=?", (json.dumps(fields_dict), clean_phone))
                conn.commit()
                return jsonify({"status": "ok", "custom_fields": fields_dict, "message": "Campo personalizado atualizado."})

        elif action == "create_task":
            title = data.get("title", "").strip() or "Tarefa de Acompanhamento"
            due_date = data.get("due_date", "").strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            assigned = data.get("assigned_to", "jam").strip()
            lead_row = conn.execute("SELECT id FROM crm_leads WHERE phone=?", (clean_phone,)).fetchone()
            lead_id = lead_row["id"] if lead_row else None

            conn.execute(
                "INSERT INTO crm_tasks (lead_id, phone, title, due_date, assigned_to, status) VALUES (?, ?, ?, ?, ?, 'pending')",
                (lead_id, clean_phone, title, due_date, assigned)
            )
            conn.commit()
            return jsonify({"status": "ok", "message": "Tarefa registrada com sucesso no CRM."})

    return jsonify({"status": "error", "message": "Ação desconhecida."}), 400


@automation_bp.route("/api/automation/inbox/canned-responses", methods=["GET", "POST"])
@crm_pilot_required
def api_canned_responses():
    ensure_automation_schema()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        message = data.get("message", "").strip()
        if not title or not message:
            return jsonify({"status": "error", "message": "Título e mensagem são obrigatórios."}), 400
        with db() as conn:
            conn.execute("INSERT INTO automation_canned_responses (title, message) VALUES (?, ?)", (title, message))
            conn.commit()
        return jsonify({"status": "ok", "message": "Resposta rápida criada com sucesso!"})
    else:
        with db() as conn:
            raw = conn.execute("SELECT * FROM automation_canned_responses ORDER BY id ASC").fetchall()
        return jsonify([dict(r) for r in raw])


@automation_bp.route("/api/automation/inbox/analytics", methods=["GET"])
@crm_pilot_required
def api_inbox_analytics():
    ensure_automation_schema()
    with db() as conn:
        wams_count = conn.execute("SELECT COUNT(*) FROM automation_processed_wams").fetchone()[0]
        active_sessions_count = conn.execute("SELECT COUNT(*) FROM automation_sessions WHERE status IN ('running', 'waiting_input', 'waiting_delay')").fetchone()[0]
        open_tickets_count = conn.execute("SELECT COUNT(*) FROM crm_leads WHERE status != 'encerrado'").fetchone()[0]
        closed_tickets_count = conn.execute("SELECT COUNT(*) FROM crm_leads WHERE status = 'encerrado'").fetchone()[0]

    return jsonify({
        "status": "ok",
        "analytics": {
            "processed_wams": wams_count,
            "active_sessions": active_sessions_count,
            "open_tickets": open_tickets_count,
            "closed_tickets": closed_tickets_count
        }
    })
