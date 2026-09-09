"""
M-One WhatsApp Automation Engine & Flow Runner (services/automation/engine.py)
Máquina de estados estrita, travamento por contato, travamento de delay, ledger com suporte a efeito incerto.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from database import db
from services.automation.adapters import (
    AIProviderAdapterManager,
    execute_webhook_adapter,
    send_meta_button_message,
    send_meta_media_message,
    send_meta_text_message,
)
from services.automation.schema import (
    acquire_contact_lock,
    record_node_effect,
    release_contact_lock,
    reserve_wam_id_atomically,
    update_node_effect_status,
)

# ==========================================
# TEMPLATE RENDERING & CONDITION EVALUATION
# ==========================================

def render_template_text(text: str, variables: dict) -> str:
    """Substitui marcadores {{variavel}} com os valores do dicionário de variáveis."""
    if not text or not isinstance(text, str):
        return text or ""
    variables = variables or {}
    def replacer(match):
        var_name = match.group(1).strip()
        val = variables.get(var_name)
        if val is None:
            return match.group(0)
        return str(val)
    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replacer, text)


def render_webhook_payload(payload_template: str, variables: dict, phone: str | None = None) -> str:
    """
    Interpola variáveis no payload do Webhook e garante serialização JSON segura.
    Se o payload for JSON válido, realiza a substituição nos campos mantendo a estrutura JSON segura contra aspas.
    """
    variables = dict(variables or {})
    if phone and "phone" not in variables:
        variables["phone"] = phone

    if not payload_template or not isinstance(payload_template, str):
        return json.dumps(variables, ensure_ascii=False)

    try:
        data = json.loads(payload_template)
        def _replace_in_obj(obj):
            if isinstance(obj, str):
                return render_template_text(obj, variables)
            elif isinstance(obj, dict):
                return {k: _replace_in_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_replace_in_obj(i) for i in obj]
            return obj

        return json.dumps(_replace_in_obj(data), ensure_ascii=False)
    except (TypeError, ValueError, AttributeError, json.JSONDecodeError):
        return render_template_text(payload_template, variables)


def evaluate_condition_match(op: str, var_val, val) -> bool:
    """Avalia operadores de condição: equals, not_equals, contains, not_empty, is_set, greater_than, less_than."""
    op = (op or "equals").lower()
    str_var = str(var_val) if var_val is not None else ""
    str_val = str(val) if val is not None else ""

    if op in ["is_set", "not_empty", "is_filled", "exists"]:
        return len(str_var.strip()) > 0
    elif op in ["is_empty", "not_set"]:
        return len(str_var.strip()) == 0
    elif op in ["equals", "equal", "=="]:
        return str_var == str_val
    elif op in ["not_equals", "not_equal", "!="]:
        return str_var != str_val
    elif op == "contains":
        return str_val.lower() in str_var.lower()
    elif op == "greater_than":
        try:
            return float(str_var) > float(str_val)
        except (ValueError, TypeError):
            return False
    elif op == "less_than":
        try:
            return float(str_var) < float(str_val)
        except (ValueError, TypeError):
            return False
    return False


# ==========================================
# INPUT FORMAT & SELLER VALIDATIONS
# ==========================================

def resolve_seller_info(agent_val: str | None = None, explicit_seller_id: int | None = None) -> tuple[str, int]:
    """
    Resolve o agente/vendedor para (assigned_to_name, seller_id).
    Default oficial do M-One: Fauzer.
    """
    if explicit_seller_id is not None:
        try:
            return (str(agent_val or "fauzer").strip(), int(explicit_seller_id))
        except (ValueError, TypeError):
            pass

    clean = str(agent_val or "fauzer").strip().lower()
    
    try:
        with db() as conn:
            user_row = conn.execute("SELECT id, username FROM users WHERE LOWER(username)=? OR LOWER(name) LIKE ?", (clean, f"%{clean}%")).fetchone()
            if user_row:
                return (str(user_row["username"]), int(user_row["id"]))
    except (AttributeError, TypeError, KeyError, RuntimeError, ValueError):
        pass

    if "jam" in clean:
        return ("jam", 17)
    elif "fauzer" in clean:
        return ("fauzer", 16)
    else:
        return (str(agent_val or "fauzer").strip(), 16)


def validate_input_format(rule: str, val: str) -> bool:
    """Valida o formato do input do usuário conforme a regra configurada no nó."""
    if not val:
        return False
    val = val.strip()

    if rule == "email":
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return bool(re.match(pattern, val))
    elif rule == "number":
        try:
            float(val.replace(",", "."))
            return True
        except ValueError:
            return False
    elif rule == "phone":
        digits = "".join(ch for ch in val if ch.isdigit())
        return len(digits) >= 8
    elif rule == "menu":
        return bool(val)
    elif rule == "text":
        return len(val) > 0
    return True


# ==========================================
# TRIGGER MATCHING & SESSION LOOKUP
# ==========================================

def find_active_matching_flow(phone: str, message_body: str) -> dict | None:
    """Localiza o fluxo ativo que possui gatilho compatível com a mensagem."""
    message_clean = message_body.strip().lower()

    with db() as conn:
        active_flows = conn.execute("SELECT * FROM automation_flows WHERE status='active' ORDER BY id DESC").fetchall()
        if not active_flows:
            return None

        for f in active_flows:
            flow_dict = dict(f)
            trg_cfg_str = flow_dict.get("active_trigger_config") or flow_dict.get("trigger_config") or "{}"
            try:
                trg_cfg = json.loads(trg_cfg_str)
            except (json.JSONDecodeError, TypeError, ValueError):
                trg_cfg = {}

            kws = trg_cfg.get("keywords") or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",") if k.strip()]

            if kws:
                for kw in kws:
                    if kw.strip().lower() and kw.strip().lower() in message_clean:
                        return flow_dict
            else:
                graph_data = json.loads(flow_dict.get("active_version_data") or "{}")
                trigger_nodes = [n for n in graph_data.get("nodes", []) if n.get("type") == "trigger"]
                if not trigger_nodes:
                    return flow_dict
                for node in trigger_nodes:
                    nkws = node.get("config", {}).get("keywords") or []
                    if isinstance(nkws, str):
                        nkws = [k.strip() for k in nkws.split(",") if k.strip()]
                    if not nkws:
                        return flow_dict
                    for kw in nkws:
                        if kw.strip().lower() and kw.strip().lower() in message_clean:
                            return flow_dict

        if len(active_flows) == 1:
            f_dict = dict(active_flows[0])
            trg_cfg_str = f_dict.get("active_trigger_config") or "{}"
            try:
                kws = json.loads(trg_cfg_str).get("keywords") or []
            except (json.JSONDecodeError, TypeError, ValueError):
                kws = []
            if not kws:
                return f_dict

    return None


def get_active_session_for_contact(phone: str) -> dict | None:
    """Busca a sessão em andamento do contato."""
    with db() as conn:
        session = conn.execute(
            """
            SELECT * FROM automation_sessions 
            WHERE phone=? AND status IN ('running', 'waiting_input', 'waiting_delay', 'paused_human')
            ORDER BY id DESC LIMIT 1
            """,
            (phone,)
        ).fetchone()
        return dict(session) if session else None


# ==========================================
# INBOUND PROCESSOR & STRICT STATE MACHINE
# ==========================================

def process_inbound_automation(phone: str, message_body: str, wam_id: str | None = None, lock_id: str | None = None) -> dict:
    """
    Processador principal de automação no recebimento de mensagem via WhatsApp.
    """
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
    if not clean_phone:
        return {"status": "invalid_phone"}

    acquired_here = False
    if not lock_id:
        lock_id = f"inbound_{wam_id or time.time()}"
        if not acquire_contact_lock(clean_phone, lock_id, lock_ttl_seconds=30):
            return {"status": "contact_locked"}
        acquired_here = True

    try:
        with db() as conn:
            lead = conn.execute("SELECT id FROM crm_leads WHERE phone=?", (clean_phone,)).fetchone()
            if not lead:
                conn.execute(
                    "INSERT INTO crm_leads (name, phone, channel, status) VALUES (?, ?, 'WhatsApp', 'novo')",
                    (clean_phone, clean_phone)
                )
                conn.commit()

        wam_reservation = reserve_wam_id_atomically(wam_id, clean_phone, {"body": message_body})
        if wam_reservation == "completed_duplicate":
            return {"status": "duplicate_wam_id_ignored", "wam_id": wam_id}
        if wam_reservation == "processing_locked":
            return {"status": "wam_processing_concurrent", "wam_id": wam_id}

        existing_session = get_active_session_for_contact(clean_phone)
        if existing_session:
            res = resume_session_with_input(existing_session, clean_phone, message_body, wam_id=wam_id)
        else:
            flow_row = find_active_matching_flow(clean_phone, message_body)
            if not flow_row:
                res = {"status": "no_matching_trigger"}
            else:
                res = start_new_flow_session(flow_row, clean_phone, wam_id=wam_id)

        if wam_id:
            with db() as conn:
                conn.execute(
                    "UPDATE automation_processed_wams SET status='completed', updated_at=CURRENT_TIMESTAMP WHERE wam_id=?",
                    (wam_id,)
                )
                conn.commit()

        return res
    except Exception as ex:
        if wam_id:
            with db() as conn:
                conn.execute("UPDATE automation_processed_wams SET status='failed', last_error=? WHERE wam_id=?", (str(ex), wam_id))
                conn.commit()
        raise
    finally:
        if acquired_here:
            release_contact_lock(clean_phone, lock_id)


def start_new_flow_session(flow_row, phone: str, lead_id: int | None = None, wam_id: str | None = None) -> dict:
    """Inicia uma nova execução de fluxo congelando o snapshot do grafo na sessão."""
    fdict = dict(flow_row)
    graph_str = fdict.get("active_version_data") or fdict.get("draft_version_data") or "{}"
    try:
        graph_data = json.loads(graph_str)
    except (json.JSONDecodeError, TypeError, ValueError):
        graph_data = {}

    nodes = graph_data.get("nodes", [])
    if not nodes and fdict.get("draft_version_data"):
        try:
            graph_data = json.loads(fdict.get("draft_version_data") or "{}")
            nodes = graph_data.get("nodes", [])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    if not nodes:
        return {"status": "empty_graph"}

    trigger_node = next((n for n in nodes if n.get("type") == "trigger"), nodes[0])
    graph_snapshot = json.dumps(graph_data)

    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO automation_sessions (flow_id, phone, lead_id, status, current_node_id, variables, flow_snapshot, execution_log)
            VALUES (?, ?, ?, 'running', ?, '{}', ?, '[]')
            """,
            (fdict["id"], phone, lead_id, trigger_node["id"], graph_snapshot)
        )
        session_id = cur.lastrowid
        conn.commit()

    return execute_flow_step(session_id, fdict["id"], graph_data, trigger_node["id"], phone, depth=0)


def resume_session_with_input(session_row, phone: str, message_body: str, wam_id: str | None = None) -> dict:
    """Retoma uma sessão aguardando resposta. Trata timeout e valida portas valid/invalid/timeout."""
    session_id = session_row["id"]
    flow_id = session_row["flow_id"]
    var_name = session_row["waiting_variable"]
    val_rule = session_row["waiting_validation"] or "text"

    now_ts = int(time.time())
    asked_at = session_row["question_asked_at"] or now_ts
    timeout_sec = session_row["timeout_seconds"] or 300

    graph_data = json.loads(session_row["flow_snapshot"] or "{}")
    current_node_id = session_row["current_node_id"]
    nodes_list = graph_data.get("nodes", [])
    curr_node = next((n for n in nodes_list if n["id"] == current_node_id), None)

    if (now_ts - asked_at) > timeout_sec:
        next_node_id = get_next_node_id(graph_data, current_node_id, port="timeout")
        return execute_flow_step(session_id, flow_id, graph_data, next_node_id or "", phone, depth=0)

    user_choice = message_body.strip()

    if curr_node and curr_node.get("type") in ["send_menu", "interactive"]:
        opts = curr_node.get("config", {}).get("options", [])
        matched_opt = None

        if user_choice.isdigit():
            idx = int(user_choice) - 1
            if 0 <= idx < len(opts):
                matched_opt = opts[idx]

        if not matched_opt:
            for o in opts:
                if user_choice.lower() in [str(o.get("id", "")).lower(), str(o.get("text", "")).lower()]:
                    matched_opt = o
                    break

        if matched_opt:
            user_choice = matched_opt.get("text") or matched_opt.get("id")
        else:
            next_invalid = get_next_node_id(graph_data, current_node_id, port="invalid_answer")
            if next_invalid:
                return execute_flow_step(session_id, flow_id, graph_data, next_invalid, phone, depth=0)

            send_meta_text_message(phone, "⚠️ Opção inválida. Por favor, escolha um dos números do menu.")
            return {"status": "validation_failed", "node_id": current_node_id}

    is_valid = validate_input_format(val_rule, user_choice)
    if not is_valid:
        next_invalid = get_next_node_id(graph_data, current_node_id, port="invalid_answer")
        if next_invalid:
            return execute_flow_step(session_id, flow_id, graph_data, next_invalid, phone, depth=0)

        send_meta_text_message(phone, f"⚠️ Formato inválido ({val_rule}). Por favor digite uma informação válida.")
        return {"status": "validation_failed", "node_id": current_node_id}

    with db() as conn:
        variables = json.loads(session_row["variables"] or "{}")
        if var_name:
            variables[var_name] = user_choice

        conn.execute(
            """
            UPDATE automation_sessions 
            SET status='running', waiting_variable=NULL, waiting_validation=NULL, variables=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (json.dumps(variables), session_id)
        )
        conn.commit()

    next_node_id = get_next_node_id(graph_data, current_node_id, branch_choice=user_choice, port="valid_answer", variables=variables)
    return execute_flow_step(session_id, flow_id, graph_data, next_node_id or "", phone, depth=0)


def get_next_node_id(graph_data: dict, current_node_id: str, branch_choice: str | None = None, port: str | None = None, variables: dict | None = None) -> str | None:
    """Determina o próximo nó no grafo avaliando condições, escolhas de menu, portas e edges."""
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    variables = variables or {}

    curr_node = next((n for n in nodes if n["id"] == current_node_id), None)
    if not curr_node:
        return None

    if port:
        port_edge = next((e for e in edges if e.get("source") == current_node_id and (e.get("source_handle") == port or e.get("port") == port)), None)
        if port_edge:
            return str(port_edge["target"])

    if branch_choice:
        option_edge = next((e for e in edges if e.get("source") == current_node_id and (e.get("source_handle") == branch_choice or e.get("option_id") == branch_choice)), None)
        if option_edge:
            return str(option_edge["target"])

    if curr_node.get("type") == "condition":
        cfg = curr_node.get("config", {})
        target_var = cfg.get("variable")
        
        var_val = None
        if variables and target_var in variables:
            var_val = variables[target_var]
        elif branch_choice:
            var_val = branch_choice
        else:
            var_val = ""

        conds = cfg.get("conditions", [])
        if conds:
            for c in conds:
                op = c.get("operator", "equals")
                val = c.get("value")
                target = c.get("target_node")
                if evaluate_condition_match(op, var_val, val):
                    return str(target) if target else None
            fallback = cfg.get("fallback_target_node") or next((e["target"] for e in edges if e.get("source") == current_node_id and e.get("source_handle") in ["false", "else"]), None)
            return str(fallback) if fallback else None

        op = cfg.get("operator", "equals")
        val = cfg.get("value")
        match = evaluate_condition_match(op, var_val, val)

        if match:
            true_edge = next((e for e in edges if e.get("source") == current_node_id and e.get("source_handle") in ["true", "valid", "yes"]), None)
            if true_edge:
                return str(true_edge["target"])
            direct_edge = next((e for e in edges if e.get("source") == current_node_id), None)
            return str(direct_edge["target"]) if direct_edge else None
        else:
            false_edge = next((e for e in edges if e.get("source") == current_node_id and e.get("source_handle") in ["false", "invalid", "no", "else"]), None)
            return str(false_edge["target"]) if false_edge else None

    direct_edge = next((e for e in edges if e["source"] == current_node_id), None)
    return str(direct_edge["target"]) if direct_edge else None


def execute_flow_step(session_id: int, flow_id: int, graph_data: dict, node_id: str, phone: str, depth: int = 0) -> dict:
    """
    Executa sequencialmente os nós do fluxo com ledger de efeitos contra duplicatas.
    Suporta rastreamento de status de envio ('pending', 'completed', 'failed', 'uncertain').
    Unifica envios no transportador Meta Cloud API e bloqueia avanço em caso de falha.
    """
    if depth > 25:
        with db() as conn:
            conn.execute("UPDATE automation_sessions SET status='error_depth_limit' WHERE id=?", (session_id,))
            conn.commit()
        return {"status": "max_depth_exceeded"}

    if not node_id:
        with db() as conn:
            conn.execute("UPDATE automation_sessions SET status='completed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))
            conn.commit()
        return {"status": "flow_completed"}

    with db() as conn:
        sess_row = conn.execute("SELECT variables FROM automation_sessions WHERE id=?", (session_id,)).fetchone()
        variables = json.loads(sess_row["variables"] or "{}") if sess_row and sess_row["variables"] else {}

    nodes = graph_data.get("nodes", [])
    node = next((n for n in nodes if n["id"] == node_id), None)
    if not node:
        return {"status": "node_not_found"}

    node_type = node.get("type")
    cfg = node.get("config", {})

    if node_type == "send_message":
        raw_msg_text = cfg.get("text", "Mensagem da Automação")
        msg_text = render_template_text(raw_msg_text, variables)
        can_exec, eff_status = record_node_effect(session_id, node_id, "send_message", msg_text, status="pending")

        if can_exec:
            res_send = send_meta_text_message(phone, msg_text)
            if res_send.get("status") in ["sent", "simulated", "mock"]:
                update_node_effect_status(session_id, node_id, "send_message", "completed")
            else:
                err_msg = res_send.get("error") or res_send.get("status") or "Falha no envio de mensagem"
                update_node_effect_status(session_id, node_id, "send_message", "failed", last_error=str(err_msg))
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (str(err_msg), session_id))
                    conn.commit()
                return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": str(err_msg)}
        elif eff_status != "completed":
            err_msg = f"Efeito com status {eff_status}"
            with db() as conn:
                conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                conn.commit()
            return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

    elif node_type == "send_media":
        m_type = cfg.get("media_type", "image")
        m_url = cfg.get("media_url", "")
        raw_caption = cfg.get("caption", "")
        caption = render_template_text(raw_caption, variables)
        eff_details = f"[{m_type.upper()}] {m_url} - {caption}".strip()
        can_exec, eff_status = record_node_effect(session_id, node_id, "send_media", eff_details, status="pending")

        if can_exec:
            res_send = send_meta_media_message(phone, m_type, m_url, caption)
            if res_send.get("status") in ["sent", "simulated", "mock"]:
                update_node_effect_status(session_id, node_id, "send_media", "completed")
            else:
                err_msg = res_send.get("error") or res_send.get("status") or "Falha no envio de mídia"
                update_node_effect_status(session_id, node_id, "send_media", "failed", last_error=str(err_msg))
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (str(err_msg), session_id))
                    conn.commit()
                return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": str(err_msg)}
        elif eff_status != "completed":
            err_msg = f"Efeito com status {eff_status}"
            with db() as conn:
                conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                conn.commit()
            return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

    elif node_type in ["send_menu", "interactive"]:
        raw_title = cfg.get("title") or cfg.get("text") or "Escolha uma opção:"
        msg_title = render_template_text(raw_title, variables)
        opts = cfg.get("options", [])
        msg_text = msg_title
        if opts:
            msg_text += "\n" + "\n".join([f"{o.get('text')}" for o in opts])

        can_exec, eff_status = record_node_effect(session_id, node_id, "send_menu", msg_text, status="pending")
        if can_exec:
            res_send = send_meta_button_message(phone, msg_title, opts)
            if res_send.get("status") in ["sent", "simulated", "mock"]:
                update_node_effect_status(session_id, node_id, "send_menu", "completed")
            else:
                err_msg = res_send.get("error") or res_send.get("status") or "Falha no envio do menu"
                update_node_effect_status(session_id, node_id, "send_menu", "failed", last_error=str(err_msg))
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (str(err_msg), session_id))
                    conn.commit()
                return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": str(err_msg)}
        elif eff_status != "completed":
            err_msg = f"Efeito com status {eff_status}"
            with db() as conn:
                conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                conn.commit()
            return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

        with db() as conn:
            conn.execute(
                """
                UPDATE automation_sessions 
                SET current_node_id=?, status='waiting_input', waiting_variable=?, waiting_validation='menu', updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (node_id, cfg.get("save_variable", "menu_choice"), session_id)
            )
            conn.commit()
        return {"status": "waiting_user_input", "node_id": node_id}

    elif node_type == "ask_question":
        raw_prompt = cfg.get("text") or cfg.get("question") or "Por favor responda à pergunta:"
        prompt = render_template_text(raw_prompt, variables)
        val_type = cfg.get("validation", "text")
        save_var = cfg.get("save_variable", "question_answer")
        timeout_sec = int(cfg.get("timeout_seconds", 300))
        now_ts = int(time.time())

        can_exec, eff_status = record_node_effect(session_id, node_id, "ask_question", prompt, status="pending")
        if can_exec:
            res_send = send_meta_text_message(phone, prompt)
            if res_send.get("status") in ["sent", "simulated", "mock"]:
                update_node_effect_status(session_id, node_id, "ask_question", "completed")
            else:
                err_msg = res_send.get("error") or res_send.get("status") or "Falha no envio da pergunta"
                update_node_effect_status(session_id, node_id, "ask_question", "failed", last_error=str(err_msg))
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (str(err_msg), session_id))
                    conn.commit()
                return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": str(err_msg)}
        elif eff_status != "completed":
            err_msg = f"Efeito com status {eff_status}"
            with db() as conn:
                conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                conn.commit()
            return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

        with db() as conn:
            conn.execute(
                """
                UPDATE automation_sessions 
                SET current_node_id=?, status='waiting_input', waiting_variable=?, waiting_validation=?, question_asked_at=?, timeout_seconds=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (node_id, save_var, val_type, now_ts, timeout_sec, session_id)
            )
            conn.commit()
        return {"status": "waiting_user_input", "node_id": node_id}

    elif node_type == "delay":
        delay_sec = int(cfg.get("seconds") or cfg.get("delay_seconds") or 5)
        now_ts = int(time.time())
        resume_due_at = now_ts + delay_sec
        next_target_id = get_next_node_id(graph_data, node_id, variables=variables)

        with db() as conn:
            conn.execute(
                """
                UPDATE automation_sessions 
                SET current_node_id=?, status='waiting_delay', resume_due_at=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (next_target_id, resume_due_at, session_id)
            )
            conn.commit()
        return {"status": "waiting_delay", "resume_due_at": resume_due_at, "next_node_id": next_target_id}

    elif node_type == "webhook":
        raw_url = cfg.get("url", "").strip()
        url = render_template_text(raw_url, variables)
        method = cfg.get("method", "POST").upper()
        raw_payload = cfg.get("payload", "{}")
        payload = render_webhook_payload(raw_payload, variables, phone)

        can_exec, eff_status = record_node_effect(session_id, node_id, "webhook_call", url, status="pending")
        if can_exec:
            res_code, res_body = execute_webhook_adapter(url, method, payload, phone)
            is_ok = res_code in [200, 201]
            status_val = "completed" if is_ok else "failed"
            update_node_effect_status(session_id, node_id, "webhook_call", status_val, last_error=None if is_ok else f"HTTP {res_code}")

            with db() as conn:
                conn.execute(
                    """
                    INSERT INTO automation_logs (session_id, flow_id, phone, node_id, event_type, detail, response_code, response_body)
                    VALUES (?, ?, ?, ?, 'webhook_execution', ?, ?, ?)
                    """,
                    (session_id, flow_id, phone, node_id, f"HTTP {method} -> {url}", res_code, res_body)
                )
                conn.commit()

            save_var = cfg.get("save_variable") or cfg.get("save_response_var") or cfg.get("response_variable") or cfg.get("variable")
            if is_ok and save_var:
                try:
                    resp_data = json.loads(res_body)
                except (json.JSONDecodeError, TypeError, ValueError):
                    resp_data = res_body
                variables[save_var] = resp_data
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET variables=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(variables), session_id))
                    conn.commit()

            if not is_ok:
                err_msg = f"Webhook falhou com HTTP {res_code}"
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                    conn.commit()
                return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}
        elif eff_status != "completed":
            err_msg = f"Efeito com status {eff_status}"
            with db() as conn:
                conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                conn.commit()
            return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

    elif node_type in ["action", "crm_action"]:
        action_type = cfg.get("action_type")
        can_exec, eff_status = record_node_effect(session_id, node_id, f"crm_{action_type}", str(cfg), status="completed")
        if can_exec:
            with db() as conn:
                if action_type == "create_lead":
                    raw_lead_name = cfg.get("name") or cfg.get("lead_name") or "Novo Lead Bot"
                    lead_name = render_template_text(raw_lead_name, variables)
                    conn.execute(
                        "INSERT OR IGNORE INTO crm_leads (name, phone, channel, status) VALUES (?, ?, 'WhatsApp', 'novo')",
                        (lead_name, phone)
                    )
                elif action_type in ["update_lead_status", "update_stage"]:
                    new_status = cfg.get("status") or cfg.get("stage") or "em_atendimento"
                    conn.execute("UPDATE crm_leads SET status=? WHERE phone=?", (new_status, phone))
                elif action_type in ["assign_seller", "assign_agent"]:
                    assigned_raw = cfg.get("assigned_to") or cfg.get("agent") or cfg.get("seller") or "fauzer"
                    assigned_name, seller_id = resolve_seller_info(assigned_raw, cfg.get("seller_id"))
                    conn.execute("UPDATE crm_leads SET assigned_to=?, seller_id=? WHERE phone=?", (assigned_name, seller_id, phone))
                elif action_type in ["create_task", "follow_up"]:
                    raw_task_title = cfg.get("task_title") or cfg.get("title") or cfg.get("note") or "Tarefa de Follow-up do Bot"
                    task_title = render_template_text(raw_task_title, variables)
                    assigned_raw = cfg.get("assigned_to") or cfg.get("agent") or cfg.get("seller") or "fauzer"
                    assigned_name, seller_id = resolve_seller_info(assigned_raw, cfg.get("seller_id"))
                    
                    if cfg.get("due_days") is not None:
                        try:
                            days = int(cfg.get("due_days"))
                            due_date = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")
                        except (ValueError, TypeError):
                            due_date = cfg.get("due_date") or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
                    else:
                        due_date = cfg.get("due_date") or (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

                    lead_row = conn.execute("SELECT id FROM crm_leads WHERE phone=?", (phone,)).fetchone()
                    lead_id = lead_row["id"] if lead_row else None

                    conn.execute(
                        "INSERT INTO crm_tasks (lead_id, phone, title, due_date, assigned_to, status) VALUES (?, ?, ?, ?, ?, 'pending')",
                        (lead_id, phone, task_title, due_date, assigned_name)
                    )
                elif action_type == "update_lead":
                    raw_notes = cfg.get("notes") or cfg.get("lead_notes")
                    notes = render_template_text(raw_notes, variables) if raw_notes else None
                    new_status = cfg.get("status") or cfg.get("stage")
                    assigned_raw = cfg.get("assigned_to") or cfg.get("agent") or cfg.get("seller")

                    query_parts = ["updated_at=CURRENT_TIMESTAMP"]
                    params: list[Any] = []
                    if notes is not None:
                        query_parts.append("notes=?")
                        params.append(notes)
                    if new_status is not None:
                        query_parts.append("status=?")
                        params.append(new_status)
                    if assigned_raw is not None:
                        assigned_name, seller_id = resolve_seller_info(assigned_raw, cfg.get("seller_id"))
                        query_parts.append("assigned_to=?")
                        params.append(assigned_name)
                        query_parts.append("seller_id=?")
                        params.append(seller_id)

                    params.append(phone)
                    sql = f"UPDATE crm_leads SET {', '.join(query_parts)} WHERE phone=?"
                    conn.execute(sql, params)
                conn.commit()
        elif eff_status != "completed":
            err_msg = f"Efeito com status {eff_status}"
            with db() as conn:
                conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                conn.commit()
            return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

    elif node_type in ["transfer", "transfer_agent"]:
        assigned_raw = cfg.get("assigned_to") or cfg.get("agent") or cfg.get("seller") or "fauzer"
        assigned_name, seller_id = resolve_seller_info(assigned_raw, cfg.get("seller_id"))
        raw_msg = cfg.get("message") or f"👨‍💼 Transferindo atendimento para {assigned_name.capitalize()}..."
        msg = render_template_text(raw_msg, variables)
        can_exec, eff_status = record_node_effect(session_id, node_id, "transfer_human", msg, status="pending")
        if can_exec:
            res_send = send_meta_text_message(phone, msg)
            if res_send.get("status") in ["sent", "simulated", "mock"]:
                update_node_effect_status(session_id, node_id, "transfer_human", "completed")
            else:
                err_msg = res_send.get("error") or res_send.get("status") or "Falha na transferência"
                update_node_effect_status(session_id, node_id, "transfer_human", "failed", last_error=str(err_msg))
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (str(err_msg), session_id))
                    conn.commit()
                return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": str(err_msg)}
        elif eff_status != "completed":
            err_msg = f"Efeito com status {eff_status}"
            with db() as conn:
                conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                conn.commit()
            return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

        with db() as conn:
            conn.execute("UPDATE crm_leads SET bot_paused=1, ticket_status='claimed', assigned_to=?, seller_id=? WHERE phone=?", (assigned_name, seller_id, phone))
            conn.execute("UPDATE automation_sessions SET status='paused_human', updated_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))
            conn.commit()
        return {"status": "transferred_to_human"}

    elif node_type == "ai_reply":
        prompt_instruction = cfg.get("prompt") or cfg.get("instruction") or "Atendimento inteligente"
        prompt_instruction = render_template_text(prompt_instruction, variables)
        ai_manager = AIProviderAdapterManager()
        success, ai_output = ai_manager.generate_ai_reply(prompt_instruction)

        if not success:
            can_exec, eff_status = record_node_effect(session_id, node_id, "ai_not_configured", ai_output, status="pending")
            if can_exec:
                send_meta_text_message(phone, ai_output)
                update_node_effect_status(session_id, node_id, "ai_not_configured", "completed")
            with db() as conn:
                conn.execute("UPDATE crm_leads SET bot_paused=1 WHERE phone=?", (phone,))
                conn.execute("UPDATE automation_sessions SET status='paused_human', updated_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))
                conn.commit()
            return {"status": "ai_not_configured_transferred"}
        else:
            can_exec, eff_status = record_node_effect(session_id, node_id, "ai_reply_sent", ai_output, status="pending")
            if can_exec:
                res_send = send_meta_text_message(phone, ai_output)
                if res_send.get("status") in ["sent", "simulated", "mock"]:
                    update_node_effect_status(session_id, node_id, "ai_reply_sent", "completed")
                else:
                    err_msg = res_send.get("error") or res_send.get("status") or "Falha no envio da resposta IA"
                    update_node_effect_status(session_id, node_id, "ai_reply_sent", "failed", last_error=str(err_msg))
                    with db() as conn:
                        conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (str(err_msg), session_id))
                        conn.commit()
                    return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": str(err_msg)}
            elif eff_status != "completed":
                err_msg = f"Efeito com status {eff_status}"
                with db() as conn:
                    conn.execute("UPDATE automation_sessions SET status='failed', last_error=? WHERE id=?", (err_msg, session_id))
                    conn.commit()
                return {"status": "failed_needs_review", "session_id": session_id, "node_id": node_id, "error": err_msg}

    elif node_type == "condition":
        next_id = get_next_node_id(graph_data, node_id, variables=variables)
        return execute_flow_step(session_id, flow_id, graph_data, next_id or "", phone, depth=depth + 1)

    elif node_type == "end":
        with db() as conn:
            conn.execute("UPDATE automation_sessions SET status='completed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))
            conn.commit()
        return {"status": "flow_completed"}

    # Avançar para o próximo nó
    next_id = get_next_node_id(graph_data, node_id, variables=variables)
    return execute_flow_step(session_id, flow_id, graph_data, next_id or "", phone, depth=depth + 1)
