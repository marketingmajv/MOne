"""
M-One WhatsApp Automation Workers (services/automation/workers.py)
Workers duráveis para reprocessamento de WAMs pendentes/falhos, delays cronometrados e timeouts de pergunta,
com reivindicação atômica de sessão (session claim) e lock de contato contra execuções concorrentes.
"""

from __future__ import annotations

import json
import time

from database import db
from services.automation.engine import (
    execute_flow_step,
    get_next_node_id,
    process_inbound_automation,
)
from services.automation.schema import acquire_contact_lock, release_contact_lock


def process_pending_wams_worker(worker_id: str = "worker_wams_1", now_ts: int | None = None) -> list:
    """Workers durável para WAMs com status 'pending' ou 'failed' (com tentativas < 5) e lease expirada."""
    now_ts = now_ts or int(time.time())
    results = []

    with db() as conn:
        pending_wams = conn.execute(
            """
            SELECT * FROM automation_processed_wams 
            WHERE (status IN ('pending', 'failed') AND attempts < 5)
               OR (status = 'processing' AND lease_expires_at <= ?)
            ORDER BY created_at ASC LIMIT 20
            """,
            (now_ts,)
        ).fetchall()

        wams_list = [dict(w) for w in pending_wams]

    for w in wams_list:
        wam_id = w["wam_id"]
        phone = w["phone"]
        payload_str = w.get("payload") or "{}"
        try:
            payload = json.loads(payload_str)
        except (json.JSONDecodeError, TypeError, ValueError):
            payload = {}

        msg_body = payload.get("body", "olá")

        if acquire_contact_lock(phone, worker_id, lock_ttl_seconds=30):
            try:
                # Passar lock_id=worker_id para evitar auto-bloqueio no processamento de entrada
                res = process_inbound_automation(phone, msg_body, wam_id=wam_id, lock_id=worker_id)
                results.append({"wam_id": wam_id, "phone": phone, "result": res})
            finally:
                release_contact_lock(phone, worker_id)
        else:
            results.append({"wam_id": wam_id, "phone": phone, "result": {"status": "contact_locked_by_other"}})

    return results


def process_delays_worker(worker_id: str = "worker_delays_1", now_ts: int | None = None) -> list:
    """Worker durável para retomada de sessões em 'waiting_delay' que atingiram a data limite (resume_due_at <= now_ts)."""
    now_ts = now_ts or int(time.time())
    results = []

    with db() as conn:
        due_sessions = conn.execute(
            """
            SELECT * FROM automation_sessions 
            WHERE status = 'waiting_delay' AND resume_due_at IS NOT NULL AND resume_due_at <= ?
            ORDER BY id ASC LIMIT 50
            """,
            (now_ts,)
        ).fetchall()

        sessions_list = [dict(s) for s in due_sessions]

    for s in sessions_list:
        sid = s["id"]
        fid = s["flow_id"]
        phone = s["phone"]
        target_node_id = s["current_node_id"]
        graph_data = json.loads(s["flow_snapshot"] or "{}")

        # Tentar reivindicação atômica do contato para o worker
        if acquire_contact_lock(phone, worker_id, lock_ttl_seconds=30):
            try:
                # Re-validar estado da sessão dentro da transação conferindo rowcount antes de executar
                updated = False
                with db() as conn:
                    cur = conn.execute(
                        """
                        UPDATE automation_sessions 
                        SET status='running', claimed_by=?, updated_at=CURRENT_TIMESTAMP 
                        WHERE id=? AND status='waiting_delay' AND resume_due_at IS NOT NULL AND resume_due_at <= ?
                        """,
                        (worker_id, sid, now_ts)
                    )
                    conn.commit()
                    if cur.rowcount and cur.rowcount > 0:
                        updated = True

                if not updated:
                    results.append({"session_id": sid, "phone": phone, "result": {"status": "session_already_processed_or_invalid_state"}})
                    continue

                res = execute_flow_step(sid, fid, graph_data, target_node_id, phone, depth=0)
                results.append({"session_id": sid, "phone": phone, "result": res})
            finally:
                release_contact_lock(phone, worker_id)
        else:
            results.append({"session_id": sid, "phone": phone, "result": {"status": "contact_locked_by_other"}})

    return results


def process_timeouts_worker(worker_id: str = "worker_timeouts_1", now_ts: int | None = None) -> list:
    """Worker durável para expiração de perguntas (timeout_seconds) direcionando a conversa para a porta 'timeout'."""
    now_ts = now_ts or int(time.time())
    results = []

    with db() as conn:
        timeout_sessions = conn.execute(
            """
            SELECT * FROM automation_sessions 
            WHERE status = 'waiting_input' 
              AND question_asked_at IS NOT NULL 
              AND (question_asked_at + timeout_seconds) <= ?
            ORDER BY id ASC LIMIT 50
            """,
            (now_ts,)
        ).fetchall()

        sessions_list = [dict(s) for s in timeout_sessions]

    for s in sessions_list:
        sid = s["id"]
        fid = s["flow_id"]
        phone = s["phone"]
        curr_node_id = s["current_node_id"]
        graph_data = json.loads(s["flow_snapshot"] or "{}")

        if acquire_contact_lock(phone, worker_id, lock_ttl_seconds=30):
            try:
                # Re-validar estado da sessão dentro da transação conferindo rowcount antes de executar
                updated = False
                with db() as conn:
                    cur = conn.execute(
                        """
                        UPDATE automation_sessions 
                        SET status='running', claimed_by=?, updated_at=CURRENT_TIMESTAMP 
                        WHERE id=? AND status='waiting_input' AND question_asked_at IS NOT NULL AND (question_asked_at + timeout_seconds) <= ?
                        """,
                        (worker_id, sid, now_ts)
                    )
                    conn.commit()
                    if cur.rowcount and cur.rowcount > 0:
                        updated = True

                if not updated:
                    results.append({"session_id": sid, "phone": phone, "result": {"status": "session_already_processed_or_invalid_state"}})
                    continue

                next_timeout_node_id = get_next_node_id(graph_data, curr_node_id, port="timeout")
                res = execute_flow_step(sid, fid, graph_data, next_timeout_node_id or "", phone, depth=0)
                results.append({"session_id": sid, "phone": phone, "result": res})
            finally:
                release_contact_lock(phone, worker_id)
        else:
            results.append({"session_id": sid, "phone": phone, "result": {"status": "contact_locked_by_other"}})

    return results


def run_all_automation_workers(worker_id: str = "worker_master_1", now_ts: int | None = None) -> dict:
    """Executa sequencialmente todos os workers duráveis de automação."""
    now_ts = now_ts or int(time.time())
    wams_res = process_pending_wams_worker(worker_id, now_ts)
    delays_res = process_delays_worker(worker_id, now_ts)
    timeouts_res = process_timeouts_worker(worker_id, now_ts)

    return {
        "status": "ok",
        "processed_wams": len(wams_res),
        "processed_delays": len(delays_res),
        "processed_timeouts": len(timeouts_res),
        "wams_details": wams_res,
        "delays_details": delays_res,
        "timeouts_details": timeouts_res
    }
