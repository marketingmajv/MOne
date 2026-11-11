"""
M-One Cycle Dossier Service (services/cycle_dossier_service.py)
Consolida o diretório executivo de todos os ciclos e metadados de navegação entre ciclos.
Mantém carregamento em lote (O(1) queries) e segregação modular (< 500 linhas).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.employee_reports_data import REPORTING_EMPLOYEES
from services.employee_reports_service import (
    ensure_reports_schema,
    get_all_cycles,
    get_or_create_current_cycle,
)
from services.internal_analysis_sectors_service import extract_normalized_cycle_sectors
from services.internal_analysis_service import ensure_internal_analysis_schema


def _format_deadline(val: Any) -> str:
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y às %H:%M")
    if val:
        return str(val)[:16]
    return "Sexta-feira 18h"


def get_cycle_neighbors(all_cycles: List[Dict[str, Any]], cycle_id: int) -> Dict[str, Any]:
    """Retorna o ciclo cronologicamente anterior (mais antigo) e próximo (mais recente)."""
    idx = next((i for i, c in enumerate(all_cycles) if int(c.get("id", 0)) == int(cycle_id)), -1)
    if idx < 0:
        return {"prev_cycle": None, "next_cycle": None}
    # all_cycles é ordenado do mais recente (índice 0) para o mais antigo
    next_cycle = all_cycles[idx - 1] if idx > 0 else None
    prev_cycle = all_cycles[idx + 1] if (idx + 1) < len(all_cycles) else None
    return {"prev_cycle": prev_cycle, "next_cycle": next_cycle}


def get_all_cycles_overview(include_curating: bool = False) -> List[Dict[str, Any]]:
    """Retorna lista executiva de todos os ciclos com adesão de entregas e status da análise."""
    ensure_reports_schema()
    ensure_internal_analysis_schema()

    all_cycles = get_all_cycles()
    current_cycle = get_or_create_current_cycle()
    current_id = int(current_cycle.get("id") or 0)

    with db() as conn:
        rep_rows = conn.execute(
            "SELECT cycle_id, employee_key, status FROM maj_employee_reports"
        ).fetchall() or []
        ana_rows = conn.execute(
            "SELECT * FROM maj_cycle_internal_analyses"
        ).fetchall() or []

    reports_by_cycle: Dict[int, Dict[str, str]] = {}
    for row in rep_rows:
        d = dict(row)
        cid = int(d.get("cycle_id") or 0)
        ekey = str(d.get("employee_key") or "").lower().strip()
        if cid and ekey in REPORTING_EMPLOYEES:
            reports_by_cycle.setdefault(cid, {})[ekey] = str(d.get("status") or "pending")

    analyses_by_cycle: Dict[int, Dict[str, Any]] = {
        int(dict(r).get("cycle_id") or 0): dict(r) for r in ana_rows
    }

    total_employees = len(REPORTING_EMPLOYEES)
    overview: List[Dict[str, Any]] = []

    for c in all_cycles:
        cid = int(c["id"])
        rep_map = reports_by_cycle.get(cid, {})

        submitted = 0
        exempt = 0
        draft = 0
        for ek in REPORTING_EMPLOYEES:
            st = rep_map.get(ek, "pending")
            if st in ("submitted_on_time", "submitted_late"):
                submitted += 1
            elif st == "exempt":
                exempt += 1
            elif st == "draft":
                draft += 1

        active_total = max(total_employees - exempt, 0)
        completion_pct = int((submitted / active_total) * 100) if active_total else 100

        ana_row = analyses_by_cycle.get(cid)
        ana_status = (ana_row.get("status") if ana_row else None) or "none"
        can_view_analysis = (ana_status == "published") or (include_curating and ana_row is not None)

        gargalos_cnt = 0
        high_gargalos_cnt = 0
        obs_cnt = 0
        decisoes_cnt = 0
        pending_dec_cnt = 0
        destaques_cnt = 0
        exec_summary = ""

        if ana_row and can_view_analysis:
            norm = extract_normalized_cycle_sectors(ana_row)
            exec_summary = norm.get("executive_summary", "")
            for sec in (norm.get("sectors") or {}).values():
                g_list = sec.get("gargalos") or []
                d_list = sec.get("decisoes") or []
                gargalos_cnt += len(g_list)
                high_gargalos_cnt += sum(1 for g in g_list if g.get("severity") == "high")
                obs_cnt += len(sec.get("observacoes") or [])
                destaques_cnt += len(sec.get("destaques") or [])
                decisoes_cnt += len(d_list)
                pending_dec_cnt += sum(
                    1 for d in d_list if (d.get("status") or "pending") in ("pending", "postponed")
                )

        raw_title = c.get("title") or c.get("cycle_code") or f"Ciclo {cid}"
        if "—" in raw_title:
            parts = raw_title.split("—", 1)
            short_title = parts[0].strip()
            week_subtitle = parts[1].strip()
        else:
            short_title = raw_title
            week_subtitle = c.get("cycle_code") or ""

        overview.append({
            "id": cid,
            "cycle_code": c.get("cycle_code") or "",
            "title": raw_title,
            "short_title": short_title,
            "week_subtitle": week_subtitle,
            "start_date": c.get("start_date") or "",
            "deadline_str": _format_deadline(c.get("deadline")),
            "is_current": cid == current_id,
            "total_employees": total_employees,
            "submitted_count": submitted,
            "exempt_count": exempt,
            "draft_count": draft,
            "pending_count": max(active_total - submitted - draft, 0),
            "active_total": active_total,
            "completion_percent": completion_pct,
            "analysis_status": ana_status,
            "can_view_analysis": can_view_analysis,
            "executive_summary": exec_summary,
            "gargalos_count": gargalos_cnt,
            "high_gargalos_count": high_gargalos_cnt,
            "observacoes_count": obs_cnt,
            "decisoes_count": decisoes_cnt,
            "pending_decisoes_count": pending_dec_cnt,
            "destaques_count": destaques_cnt,
        })

    return overview

