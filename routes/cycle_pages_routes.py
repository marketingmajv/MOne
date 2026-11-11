"""
M-One Cycle Pages Routes (routes/cycle_pages_routes.py)
Páginas dedicadas: Diretório de Todos os Ciclos (/admin/plano/ciclos)
e Dossiê Completo de cada Ciclo (/admin/plano/ciclo/<cycle_id>).
"""

from __future__ import annotations

import logging
from flask import Blueprint, flash, redirect, render_template, request, url_for

from routes.helpers import current_user, login_required
from services.cycle_dossier_service import get_all_cycles_overview, get_cycle_neighbors
from services.employee_doc_importer_service import get_all_doc_links
from services.employee_governance_service import get_cycle_governance_status
from services.employee_reports_data import is_admin_viewer
from services.employee_reports_service import (
    ensure_reports_schema,
    get_all_cycles,
    get_cycle_submissions_summary,
    get_monday_consolidation_briefing,
)
from services.implementation_plan_service import ensure_implementation_plan_schema
from services.internal_analysis_service import (
    ensure_internal_analysis_schema,
    get_internal_analysis,
)

logger = logging.getLogger(__name__)

cycle_pages_bp = Blueprint("cycle_pages", __name__)


def _check_director_access():
    me = current_user()
    if not me:
        return None, redirect(url_for("login"))
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        flash("Acesso restrito à Diretoria e Administradores da MAJ Mobilidade.", "error")
        return None, redirect(url_for("dashboard"))
    return me, None


@cycle_pages_bp.route("/admin/plano/ciclos", methods=["GET"])
@cycle_pages_bp.route("/admin/internal/plan/cycles", methods=["GET"])
@login_required
def cycles_index():
    """Diretório executivo em cards com todos os ciclos semanais da MAJ Mobilidade."""
    me, err_resp = _check_director_access()
    if err_resp:
        return err_resp

    username = (me.get("username") or "").lower().strip()
    is_curator = username in ["fauzer", "support", "admin"]
    cycles = get_all_cycles_overview(include_curating=is_curator)

    return render_template(
        "admin/cycles_index.html",
        me=me,
        is_curator=is_curator,
        cycles=cycles,
    )


@cycle_pages_bp.route("/admin/plano/ciclo/<int:cycle_id>", methods=["GET"])
@cycle_pages_bp.route("/admin/internal/plan/ciclo/<int:cycle_id>", methods=["GET"])
@login_required
def cycle_detail(cycle_id: int):
    """Página dedicada e completa (Dossiê) de um ciclo específico."""
    ensure_implementation_plan_schema()
    ensure_reports_schema()
    ensure_internal_analysis_schema()

    me, err_resp = _check_director_access()
    if err_resp:
        return err_resp

    username = (me.get("username") or "").lower().strip()
    is_curator = username in ["fauzer", "support", "admin"]

    all_cycles = get_all_cycles()
    cycle = next((c for c in all_cycles if int(c["id"]) == int(cycle_id)), None)
    if not cycle:
        flash(f"Ciclo #{cycle_id} não encontrado.", "error")
        return redirect(url_for("cycle_pages.cycles_index"))

    neighbors = get_cycle_neighbors(all_cycles, cycle_id)
    is_current_cycle = bool(all_cycles and int(all_cycles[0]["id"]) == int(cycle["id"]))

    requested_tab = (request.args.get("tab") or "consolidation").strip()
    active_tab = requested_tab if requested_tab in ("consolidation", "dashboard") else "consolidation"

    summary = get_cycle_submissions_summary(cycle["id"])
    consolidation = get_monday_consolidation_briefing(cycle["id"])
    internal_analysis = get_internal_analysis(cycle["id"])
    governance_status = get_cycle_governance_status(cycle["id"])
    doc_links = get_all_doc_links()

    return render_template(
        "admin/cycle_detail.html",
        me=me,
        is_admin_viewer=True,
        is_curator=is_curator,
        active_tab=active_tab,
        cycle=cycle,
        all_cycles=all_cycles,
        prev_cycle=neighbors["prev_cycle"],
        next_cycle=neighbors["next_cycle"],
        is_current_cycle=is_current_cycle,
        summary=summary,
        consolidation=consolidation,
        internal_analysis=internal_analysis,
        governance_status=governance_status,
        doc_links=doc_links,
    )

