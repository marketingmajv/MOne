"""
M-One Employee Governance & Edit Requests Service (services/employee_governance_service.py)
Gerencia permissões de edição de ciclos anteriores, solicitações de ajuste dos colaboradores
e liberação em lote das deliberações e feedbacks da Diretoria.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.employee_reports_service import _is_pg, ensure_reports_schema, get_employee_report

logger = logging.getLogger(__name__)


def ensure_governance_schema() -> None:
    """Garante a existência das colunas de governança e solicitação de edição."""
    ensure_reports_schema()
    with db() as conn:
        pg = _is_pg(conn)
        rep_cols = [
            ("is_edit_unlocked", "BOOLEAN DEFAULT FALSE" if pg else "INTEGER DEFAULT 0"),
            ("edit_request_status", "VARCHAR(30) DEFAULT NULL" if pg else "TEXT DEFAULT NULL"),
            ("edit_request_reason", "TEXT DEFAULT ''"),
            ("edit_requested_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL" if pg else "TIMESTAMP DEFAULT NULL"),
        ]
        cycle_cols = [
            ("feedback_released_all", "BOOLEAN DEFAULT FALSE" if pg else "INTEGER DEFAULT 0"),
            ("edit_unlocked_all", "BOOLEAN DEFAULT FALSE" if pg else "INTEGER DEFAULT 0"),
        ]

        if pg:
            for col, ctype in rep_cols:
                try:
                    conn.execute(f"ALTER TABLE maj_employee_reports ADD COLUMN IF NOT EXISTS {col} {ctype};")
                except Exception as e:
                    logger.debug("Schema notice rep col %s: %s", col, e)
            for col, ctype in cycle_cols:
                try:
                    conn.execute(f"ALTER TABLE maj_report_cycles ADD COLUMN IF NOT EXISTS {col} {ctype};")
                except Exception as e:
                    logger.debug("Schema notice cycle col %s: %s", col, e)
        else:
            try:
                cur = conn.execute("PRAGMA table_info(maj_employee_reports);")
                existing = {row[1] for row in cur.fetchall()}
                for col, ctype in rep_cols:
                    if col not in existing:
                        conn.execute(f"ALTER TABLE maj_employee_reports ADD COLUMN {col} {ctype};")
                cur2 = conn.execute("PRAGMA table_info(maj_report_cycles);")
                existing_c = {row[1] for row in cur2.fetchall()}
                for col, ctype in cycle_cols:
                    if col not in existing_c:
                        conn.execute(f"ALTER TABLE maj_report_cycles ADD COLUMN {col} {ctype};")
            except Exception as e:
                logger.debug("SQLite schema notice: %s", e)
        conn.commit()


def request_report_edit(cycle_id: int, employee_key: str, reason: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Registra uma solicitação de edição de ciclo anterior feita pelo colaborador."""
    ensure_governance_schema()
    key = employee_key.lower().strip()
    clean_reason = (reason or "").strip()
    if not clean_reason:
        clean_reason = "Solicitação de ajuste de relatório"

    now = datetime.now()
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        now_val = now if pg else now.strftime("%Y-%m-%d %H:%M:%S")

        # Verifica se o relatório já existe
        cur = conn.execute(
            f"SELECT id, status FROM maj_employee_reports WHERE cycle_id = {ph} AND employee_key = {ph} LIMIT 1",
            (cycle_id, key)
        )
        row = cur.fetchone()

        if row:
            up_sql = f"""
                UPDATE maj_employee_reports
                SET edit_request_status = 'pending',
                    edit_request_reason = {ph},
                    edit_requested_at = {ph},
                    updated_at = {ph}
                WHERE id = {ph}
            """
            conn.execute(up_sql, (clean_reason, now_val, now_val, row["id"]))
        else:
            # Caso ainda não exista linha, cria como rascunho com o pedido pendente
            from services.employee_reports_data import get_reporting_employee_meta
            meta = get_reporting_employee_meta(key) or {"name": key.capitalize(), "role_title": "Colaborador"}
            ins_sql = f"""
                INSERT INTO maj_employee_reports
                (cycle_id, user_id, employee_key, employee_name, role_title, answers_json, status,
                 edit_request_status, edit_request_reason, edit_requested_at, updated_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, '{{}}', 'draft', 'pending', {ph}, {ph}, {ph})
            """
            conn.execute(
                ins_sql,
                (cycle_id, user_id, key, meta["name"], meta["role_title"], clean_reason, now_val, now_val)
            )

        # Registra em audit_log
        try:
            conn.execute(
                f"INSERT INTO audit_log (user_id, action, detail, created_at) VALUES ({ph}, {ph}, {ph}, {ph})",
                (user_id or 0, "relatorio.edit_requested", f"ciclo={cycle_id}; colab={key}; motivo={clean_reason[:80]}", now_val)
            )
        except Exception:
            pass

        conn.commit()

    return {
        "success": True,
        "message": "Solicitação de edição enviada à Gerência com sucesso!",
        "employee_key": key,
        "cycle_id": cycle_id,
        "edit_request_status": "pending",
        "edit_request_reason": clean_reason,
    }


def decide_report_edit_request(
    cycle_id: int,
    employee_key: str,
    approved: bool,
    decider_username: str = "gerencia"
) -> Dict[str, Any]:
    """Aprova ou recusa a solicitação de edição de um colaborador na Gestão Interna."""
    ensure_governance_schema()
    key = employee_key.lower().strip()
    status = "approved" if approved else "rejected"
    is_unlocked = bool(approved)
    now = datetime.now()

    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        now_val = now if pg else now.strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            f"""UPDATE maj_employee_reports
                SET edit_request_status = {ph},
                    is_edit_unlocked = {ph},
                    updated_at = {ph}
                WHERE cycle_id = {ph} AND employee_key = {ph}""",
            (status, is_unlocked, now_val, cycle_id, key)
        )

        try:
            act = "relatorio.edit_approved" if approved else "relatorio.edit_rejected"
            conn.execute(
                f"INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (0, {ph}, {ph}, {ph})",
                (act, f"ciclo={cycle_id}; colab={key}; decider={decider_username}", now_val)
            )
        except Exception:
            pass

        conn.commit()

    action_label = "liberada para edição" if approved else "recusada"
    return {
        "success": True,
        "message": f"Edição de {key.capitalize()} {action_label} com sucesso.",
        "employee_key": key,
        "cycle_id": cycle_id,
        "is_edit_unlocked": is_unlocked,
        "edit_request_status": status,
    }


def toggle_report_edit_unlock(cycle_id: int, employee_key: str, is_unlocked: bool) -> bool:
    """Ativa ou desativa diretamente a permissão de edição para um colaborador em um ciclo."""
    ensure_governance_schema()
    key = employee_key.lower().strip()
    now = datetime.now()

    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        now_val = now if pg else now.strftime("%Y-%m-%d %H:%M:%S")
        status_val = "approved" if is_unlocked else None

        conn.execute(
            f"""UPDATE maj_employee_reports
                SET is_edit_unlocked = {ph},
                    edit_request_status = {ph},
                    updated_at = {ph}
                WHERE cycle_id = {ph} AND employee_key = {ph}""",
            (is_unlocked, status_val, now_val, cycle_id, key)
        )
        conn.commit()
    return is_unlocked


def toggle_cycle_feedback_release_all(cycle_id: int, is_released: bool) -> bool:
    """Libera ou bloqueia as deliberações e feedbacks de diretoria para TODOS os colaboradores do ciclo."""
    ensure_governance_schema()
    now = datetime.now()

    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        now_val = now if pg else now.strftime("%Y-%m-%d %H:%M:%S")

        # Atualiza o ciclo
        conn.execute(
            f"UPDATE maj_report_cycles SET feedback_released_all = {ph} WHERE id = {ph}",
            (is_released, cycle_id)
        )
        # Atualiza todos os relatórios daquele ciclo
        conn.execute(
            f"UPDATE maj_employee_reports SET is_feedback_released = {ph}, updated_at = {ph} WHERE cycle_id = {ph}",
            (is_released, now_val, cycle_id)
        )
        conn.commit()
    return is_released


def toggle_cycle_edit_unlock_all(cycle_id: int, is_unlocked: bool) -> bool:
    """Libera ou bloqueia a edição para TODOS os colaboradores do ciclo em lote."""
    ensure_governance_schema()
    now = datetime.now()

    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        now_val = now if pg else now.strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            f"UPDATE maj_report_cycles SET edit_unlocked_all = {ph} WHERE id = {ph}",
            (is_unlocked, cycle_id)
        )
        conn.execute(
            f"UPDATE maj_employee_reports SET is_edit_unlocked = {ph}, updated_at = {ph} WHERE cycle_id = {ph}",
            (is_unlocked, now_val, cycle_id)
        )
        conn.commit()
    return is_unlocked


def get_cycle_governance_status(cycle_id: int) -> Dict[str, Any]:
    """Retorna os dados consolidados de governança e solicitações pendentes de um ciclo."""
    ensure_governance_schema()
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"

        c_row = conn.execute(
            f"SELECT feedback_released_all, edit_unlocked_all FROM maj_report_cycles WHERE id = {ph} LIMIT 1",
            (cycle_id,)
        ).fetchone()

        f_all = bool(c_row.get("feedback_released_all")) if c_row else False
        e_all = bool(c_row.get("edit_unlocked_all")) if c_row else False

        # Busca pendências de solicitação de edição
        cur_reqs = conn.execute(
            f"""SELECT id, employee_key, employee_name, role_title, edit_request_reason, edit_requested_at
                FROM maj_employee_reports
                WHERE cycle_id = {ph} AND edit_request_status = 'pending'
                ORDER BY edit_requested_at ASC""",
            (cycle_id,)
        ).fetchall() or []

        pending_requests = []
        for r in cur_reqs:
            d = dict(r)
            req_at = d.get("edit_requested_at")
            d["edit_requested_at_fmt"] = req_at.strftime("%d/%m às %H:%M") if hasattr(req_at, "strftime") else str(req_at)[:16]
            pending_requests.append(d)

        return {
            "cycle_id": cycle_id,
            "feedback_released_all": f_all,
            "edit_unlocked_all": e_all,
            "pending_requests": pending_requests,
            "pending_requests_count": len(pending_requests),
            "pending_edit_requests_count": len(pending_requests),
        }

