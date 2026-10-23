"""
M-One Employee Gamification & Timeline Service (services/employee_gamification_service.py)
Gerencia o sistema de pontuação, streaks de pontualidade, badges e a linha do tempo
de confirmação de recebimento pela diretoria dos relatórios semanais.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.employee_reports_service import _is_pg, ensure_reports_schema

logger = logging.getLogger(__name__)

_gamification_schema_ensured = False


def ensure_gamification_schema() -> None:
    """Garante as colunas de pontuação e carimbo da diretoria em maj_employee_reports."""
    global _gamification_schema_ensured
    if _gamification_schema_ensured:
        return
    ensure_reports_schema()
    with db() as conn:
        for col_def in [
            "points_awarded INT DEFAULT 0",
            "reviewed_at TIMESTAMP",
            "reviewed_by TEXT",
        ]:
            try:
                conn.execute(f"ALTER TABLE maj_employee_reports ADD COLUMN {col_def};")
                conn.commit()
            except Exception:
                pass
    _gamification_schema_ensured = True


def calculate_badge_tier(total_points: int) -> Dict[str, str]:
    """Calcula o nível, medalha e cor do colaborador baseado na pontuação acumulada."""
    if total_points >= 1200:
        return {
            "tier": "Elite MAJ",
            "badge": "💎 Diamante",
            "color": "cyan",
            "next_goal": 2000,
            "desc": "Excelência absoluta em entregas pontuais e consistência."
        }
    elif total_points >= 700:
        return {
            "tier": "Ouro MAJ",
            "badge": "🥇 Ouro",
            "color": "amber",
            "next_goal": 1200,
            "desc": "Alto padrão de comprometimento semanal com a gestão."
        }
    elif total_points >= 300:
        return {
            "tier": "Prata MAJ",
            "badge": "🥈 Prata",
            "color": "slate",
            "next_goal": 700,
            "desc": "Consistência e pontualidade comprovada nas entregas."
        }
    else:
        return {
            "tier": "Bronze MAJ",
            "badge": "🥉 Bronze",
            "color": "orange",
            "next_goal": 300,
            "desc": "Iniciando jornada de consistência e pontualidade."
        }


def award_report_points(cycle_id: int, employee_key: str, status: str) -> int:
    """
    Atribui e atualiza a pontuação de uma submissão:
    - submitted_on_time: 100 pontos base
    - submitted_late: 20 pontos
    - draft: 0 pontos
    """
    ensure_gamification_schema()
    points = 0
    if status == "submitted_on_time":
        points = 100
    elif status == "submitted_late":
        points = 20

    if points > 0:
        with db() as conn:
            ph = "%s" if _is_pg(conn) else "?"
            try:
                conn.execute(
                    f"UPDATE maj_employee_reports SET points_awarded = {ph} WHERE cycle_id = {ph} AND employee_key = {ph}",
                    (points, cycle_id, employee_key.lower().strip())
                )
                conn.commit()
            except Exception as ex:
                logger.error("Erro ao atribuir pontos ao relatório: %s", ex)
    return points


def mark_report_reviewed(cycle_id: int, employee_key: str, reviewer_name: str) -> bool:
    """Registra o carimbo de confirmação e análise da diretoria/moderador."""
    ensure_gamification_schema()
    now = datetime.now()
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        now_val = now if pg else now.strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn.execute(
                f"""UPDATE maj_employee_reports
                    SET reviewed_at = COALESCE(reviewed_at, {ph}),
                        reviewed_by = COALESCE(reviewed_by, {ph})
                    WHERE cycle_id = {ph} AND employee_key = {ph}""",
                (now_val, reviewer_name.strip(), cycle_id, employee_key.lower().strip())
            )
            conn.commit()
            return True
        except Exception as ex:
            logger.error("Erro ao marcar relatório como lido pela diretoria: %s", ex)
            return False


def get_employee_gamification_profile(employee_key: str) -> Dict[str, Any]:
    """
    Gera o perfil completo de gamificação do colaborador:
    - Total de relatórios submetidos
    - Total de pontos acumulados
    - Sequência atual de semanas consecutivas no prazo (Streak 🔥)
    - Nível/Badge atual
    - Linha do tempo dos ciclos passados com os 3 estágios
    """
    ensure_gamification_schema()
    emp_key = employee_key.lower().strip()
    meta = get_reporting_employee_meta(emp_key) or {}

    with db() as conn:
        ph = "%s" if _is_pg(conn) else "?"
        sql = f"""
            SELECT r.*, c.cycle_code, c.title as cycle_title, c.deadline, c.start_date
            FROM maj_employee_reports r
            JOIN maj_report_cycles c ON r.cycle_id = c.id
            WHERE r.employee_key = {ph}
            ORDER BY c.start_date DESC, c.id DESC
        """
        rows = conn.execute(sql, (emp_key,)).fetchall()

    timeline = []
    total_points = 0
    submitted_count = 0
    on_time_count = 0
    streak = 0
    streak_active = True

    for r in rows:
        d = dict(r)
        status = d.get("status") or "draft"
        points = d.get("points_awarded") or 0
        if points == 0 and status == "submitted_on_time":
            points = 100
        elif points == 0 and status == "submitted_late":
            points = 20

        total_points += points

        is_submitted = status in ("submitted_on_time", "submitted_late")
        if is_submitted:
            submitted_count += 1

        if status == "submitted_on_time":
            on_time_count += 1
            if streak_active:
                streak += 1
        elif is_submitted:
            streak_active = False

        # Etapas da linha do tempo:
        # Estágio 1: Rascunho / Em Preenchimento
        # Estágio 2: Enviado / Protocolado (No Prazo ou Atrasado)
        # Estágio 3: Recebido & Analisado pela Diretoria
        stage = 1
        if is_submitted:
            stage = 2
        if d.get("reviewed_at"):
            stage = 3

        rev_at = d.get("reviewed_at")
        rev_at_fmt = rev_at.strftime("%d/%m às %H:%M") if hasattr(rev_at, "strftime") else (str(rev_at)[:16] if rev_at else "")
        sub_at = d.get("submitted_at")
        sub_at_fmt = sub_at.strftime("%d/%m às %H:%M") if hasattr(sub_at, "strftime") else (str(sub_at)[:16] if sub_at else "")

        timeline.append({
            "cycle_id": d.get("cycle_id"),
            "cycle_code": d.get("cycle_code"),
            "cycle_title": d.get("cycle_title"),
            "status": status,
            "points": points,
            "stage": stage,
            "submitted_at_fmt": sub_at_fmt,
            "reviewed_at_fmt": rev_at_fmt,
            "reviewed_by": d.get("reviewed_by") or "Diretoria MAJ",
            "docx_filename": d.get("docx_filename") or "",
        })

    badge_info = calculate_badge_tier(total_points)

    return {
        "employee_key": emp_key,
        "employee_name": meta.get("name") or emp_key.capitalize(),
        "role_title": meta.get("role_title") or "",
        "area": meta.get("area") or "",
        "total_points": total_points,
        "submitted_count": submitted_count,
        "on_time_count": on_time_count,
        "on_time_pct": round((on_time_count / submitted_count * 100), 0) if submitted_count > 0 else 0,
        "current_streak": streak,
        "badge_info": badge_info,
        "timeline": timeline,
    }
