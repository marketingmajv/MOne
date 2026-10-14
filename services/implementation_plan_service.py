"""
M-One Implementation Plan Service (services/implementation_plan_service.py)
Gerencia o Plano de Implantação de Processos, Governança, Equipe e Cronograma da MAJ Mobilidade.
Estruturado a partir do diagnóstico corporativo com persistência segura no PostgreSQL/SQLite.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List
from database import db
from services.implementation_plan_data import (
    get_default_phases_data,
    get_team_members_data,
    get_departments_data,
)

logger = logging.getLogger(__name__)

_plan_schema_ensured = False


def run_exec(conn, sql: str, params=()):
    """Executa SQL adaptando placeholders para PostgreSQL ou SQLite."""
    is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
    if is_pg:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def ensure_implementation_plan_schema():
    """Garante a existência das tabelas do plano de implantação."""
    global _plan_schema_ensured
    if _plan_schema_ensured:
        return

    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            statements = [
                """CREATE TABLE IF NOT EXISTS maj_implementation_phases (
                    id SERIAL PRIMARY KEY,
                    phase_number INTEGER UNIQUE NOT NULL,
                    title VARCHAR(150) NOT NULL,
                    period VARCHAR(100) NOT NULL,
                    description TEXT NOT NULL,
                    tasks_json TEXT NOT NULL,
                    responsibles_json TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'Planejada',
                    progress_percent INTEGER NOT NULL DEFAULT 0,
                    start_date VARCHAR(50) DEFAULT '',
                    end_date VARCHAR(50) DEFAULT '',
                    notes TEXT DEFAULT '',
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS maj_implementation_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT
                )"""
            ]
            for stmt in statements:
                try:
                    conn.executescript(stmt)
                    conn.commit()
                except Exception as e:
                    logger.debug("Schema stmt error: %s", e)
        else:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS maj_implementation_phases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_number INTEGER UNIQUE NOT NULL,
                title TEXT NOT NULL,
                period TEXT NOT NULL,
                description TEXT NOT NULL,
                tasks_json TEXT NOT NULL,
                responsibles_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Planejada',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                start_date TEXT DEFAULT '',
                end_date TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS maj_implementation_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
            try:
                conn.executescript(schema_sql)
                conn.commit()
            except Exception as e:
                logger.warning("Aviso ao criar schema do plano de implantação: %s", e)

        _plan_schema_ensured = True
        seed_default_phases(conn)


def seed_default_phases(conn):
    """Insere as fases padrão caso a tabela esteja vazia."""
    count_row = run_exec(conn, "SELECT COUNT(*) AS total FROM maj_implementation_phases").fetchone()
    if not count_row:
        count = 0
    elif isinstance(count_row, dict):
        count = count_row.get("total", 0)
    else:
        count = count_row[0]

    if count == 0:
        phases = get_default_phases_data()
        for p in phases:
            run_exec(
                conn,
                """INSERT INTO maj_implementation_phases 
                (phase_number, title, period, description, tasks_json, responsibles_json, status, progress_percent, start_date, end_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p["phase_number"],
                    p["title"],
                    p["period"],
                    p["description"],
                    json.dumps(p["tasks"], ensure_ascii=False),
                    json.dumps(p["responsibles"], ensure_ascii=False),
                    p["status"],
                    p["progress_percent"],
                    p["start_date"],
                    p["end_date"],
                    p["notes"],
                )
            )
        conn.commit()


def get_all_implementation_phases() -> List[Dict[str, Any]]:
    """Recupera todas as fases do plano cadastradas no banco."""
    ensure_implementation_plan_schema()
    with db() as conn:
        rows = run_exec(conn, "SELECT * FROM maj_implementation_phases ORDER BY phase_number ASC").fetchall()
        phases = []
        for r in rows:
            p = dict(r)
            if p.get("tasks_json") and isinstance(p["tasks_json"], str):
                try:
                    p["tasks"] = json.loads(p["tasks_json"])
                except Exception:
                    p["tasks"] = []
            else:
                p["tasks"] = []

            if p.get("responsibles_json") and isinstance(p["responsibles_json"], str):
                try:
                    p["responsibles"] = json.loads(p["responsibles_json"])
                except Exception:
                    p["responsibles"] = []
            else:
                p["responsibles"] = []

            phases.append(p)
        return phases


def update_implementation_phase(
    phase_id: int,
    status: str,
    progress_percent: int,
    start_date: str = "",
    end_date: str = "",
    notes: str = ""
) -> bool:
    """Atualiza o status, datas e progresso de uma fase pelo administrador."""
    ensure_implementation_plan_schema()
    with db() as conn:
        run_exec(
            conn,
            """UPDATE maj_implementation_phases 
            SET status = ?, progress_percent = ?, start_date = ?, end_date = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (status, int(progress_percent), start_date.strip(), end_date.strip(), notes.strip(), int(phase_id))
        )
        conn.commit()
        return True


def get_implementation_summary() -> Dict[str, Any]:
    """Calcula estatísticas de progresso do plano de implantação."""
    phases = get_all_implementation_phases()
    total_phases = len(phases)
    completed_phases = sum(1 for p in phases if p.get("status") == "Concluída")
    in_progress_phases = sum(1 for p in phases if p.get("status") == "Em Andamento")
    planned_phases = sum(1 for p in phases if p.get("status") == "Planejada")

    if total_phases > 0:
        avg_progress = round(sum(int(p.get("progress_percent") or 0) for p in phases) / total_phases)
    else:
        avg_progress = 0

    return {
        "total_phases": total_phases,
        "completed_phases": completed_phases,
        "in_progress_phases": in_progress_phases,
        "planned_phases": planned_phases,
        "overall_progress_percent": avg_progress,
        "total_team_members": 11,
        "total_departments": 6
    }
