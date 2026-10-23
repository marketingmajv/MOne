"""
M-One Employee Portal Routes (routes/employee_portal_routes.py)
Página dedicada para preenchimento individual de relatórios semanais,
visualização de prazos com cronômetro, histórico de submissões e gamificação.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import logging
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request, session, url_for, redirect

from routes.helpers import current_user, login_required
from services.employee_docx_importer_service import process_docx_upload
from services.employee_gamification_service import (
    award_report_points,
    ensure_gamification_schema,
    get_employee_gamification_profile,
)
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.employee_reports_service import (
    get_employee_report,
    get_or_create_current_cycle,
    save_or_submit_report,
)

logger = logging.getLogger(__name__)

employee_portal_bp = Blueprint("employee_portal", __name__)


def resolve_employee_key_for_user(user: dict) -> str:
    """Resolve a chave de colaborador associada ao usuário autenticado."""
    username = (user.get("username") or "").lower().strip()
    if username in REPORTING_EMPLOYEES:
        return username
    # Busca por nome caso o username seja diferente
    for key, meta in REPORTING_EMPLOYEES.items():
        if meta.get("username", "").lower() == username:
            return key
    return username


@employee_portal_bp.route("/meu-relatorio")
@login_required
def meu_relatorio():
    """Página dedicada do colaborador para preenchimento e acompanhamento do relatório semanal."""
    ensure_gamification_schema()
    me = current_user()
    if not me:
        return redirect(url_for("login"))

    emp_key = resolve_employee_key_for_user(me)
    meta = get_reporting_employee_meta(emp_key)

    # Se for admin sem perguntas diretas na cartilha, usa visão de simulação ou cargo padrão
    if not meta:
        emp_key = "fauzer"
        meta = get_reporting_employee_meta(emp_key)

    current_cycle = get_or_create_current_cycle()
    report = get_employee_report(current_cycle["id"], emp_key)
    profile = get_employee_gamification_profile(emp_key)

    # Calcula se o prazo está aberto para edição
    deadline_val = current_cycle.get("deadline")
    deadline_dt = deadline_val
    if isinstance(deadline_val, str):
        try:
            deadline_dt = datetime.fromisoformat(deadline_val.replace("T", " "))
        except Exception:
            deadline_dt = datetime.now()

    is_editable = True
    now = datetime.now()
    if now > deadline_dt and report.get("status") in ("submitted_on_time", "submitted_late"):
        is_editable = False
    if report.get("reviewed_at"):
        is_editable = False

    return render_template(
        "employee_portal.html",
        me=me,
        meta=meta,
        cycle=current_cycle,
        report=report,
        profile=profile,
        is_editable=is_editable,
        now_iso=now.isoformat(),
        deadline_iso=deadline_dt.isoformat() if hasattr(deadline_dt, "isoformat") else str(deadline_dt),
    )


@employee_portal_bp.route("/api/meu-relatorio/status", methods=["GET"])
@login_required
def api_meu_relatorio_status():
    """Retorna o estado atualizado do ciclo, relatório e pontuação do colaborador logado."""
    me = current_user()
    emp_key = resolve_employee_key_for_user(me)
    meta = get_reporting_employee_meta(emp_key) or get_reporting_employee_meta("fauzer")

    current_cycle = get_or_create_current_cycle()
    report = get_employee_report(current_cycle["id"], emp_key)
    profile = get_employee_gamification_profile(emp_key)

    return jsonify({
        "status": "success",
        "employee_key": emp_key,
        "cycle": current_cycle,
        "meta": meta,
        "report": report,
        "profile": profile,
    })


@employee_portal_bp.route("/api/meu-relatorio/salvar", methods=["POST"])
@login_required
def api_meu_relatorio_salvar():
    """Salva rascunho ou submete oficialmente o relatório do colaborador."""
    me = current_user()
    emp_key = resolve_employee_key_for_user(me)
    meta = get_reporting_employee_meta(emp_key) or get_reporting_employee_meta("fauzer")

    data = request.get_json(silent=True) or {}
    try:
        cycle_id = int(data.get("cycle_id") or 0)
    except (ValueError, TypeError):
        cycle_id = 0
    if cycle_id <= 0:
        current_cycle = get_or_create_current_cycle()
        cycle_id = current_cycle["id"]

    answers = data.get("answers") or {}
    is_draft = bool(data.get("is_draft", False))

    try:
        saved = save_or_submit_report(
            cycle_id=cycle_id,
            user_id=me.get("id"),
            employee_key=emp_key,
            answers=answers,
            is_draft=is_draft,
        )

        points = 0
        if not is_draft:
            report_status = saved.get("status") or "submitted_on_time"
            points = award_report_points(cycle_id, emp_key, report_status)

        profile = get_employee_gamification_profile(emp_key)

        msg = "💾 Rascunho salvo com sucesso na nuvem." if is_draft else f"🎉 Relatório oficial entregue com sucesso! Você ganhou +{points} pontos!"
        return jsonify({
            "status": "success",
            "message": msg,
            "is_draft": is_draft,
            "points_awarded": points,
            "report": saved,
            "profile": profile,
        })
    except Exception as ex:
        logger.error("Erro ao salvar relatório do colaborador: %s", ex, exc_info=True)
        return jsonify({"status": "error", "message": f"Erro ao salvar: {str(ex)}"}), 500


@employee_portal_bp.route("/api/meu-relatorio/upload", methods=["POST"])
@login_required
def api_meu_relatorio_upload():
    """Recebe upload de relatório Word (.docx) ou texto (.txt) do próprio colaborador e extrai respostas."""
    me = current_user()
    emp_key = resolve_employee_key_for_user(me)

    current_cycle = get_or_create_current_cycle()
    cycle_id = request.form.get("cycle_id", type=int) or current_cycle["id"]
    force = request.form.get("force", "").lower() in ("true", "1")
    file = request.files.get("file")

    if not file:
        return jsonify({"status": "error", "message": "Nenhum arquivo enviado."}), 400

    try:
        file_bytes = file.read()
        result = process_docx_upload(
            cycle_id=cycle_id,
            employee_key=emp_key,
            file_bytes=file_bytes,
            original_filename=file.filename or f"{emp_key}.docx",
            user_id=me.get("id"),
            force=force,
        )

        if result.get("status") == "success":
            points = award_report_points(cycle_id, emp_key, "submitted_on_time")
            result["points_awarded"] = points
            result["profile"] = get_employee_gamification_profile(emp_key)

        return jsonify(result)
    except Exception as ex:
        logger.error("Erro no upload do portal do colaborador: %s", ex, exc_info=True)
        return jsonify({"status": "error", "message": f"Falha no processamento: {str(ex)}"}), 500


@employee_portal_bp.route("/api/meu-relatorio/historico", methods=["GET"])
@login_required
def api_meu_relatorio_historico():
    """Retorna o histórico pessoal de relatórios do colaborador autenticado."""
    me = current_user()
    emp_key = resolve_employee_key_for_user(me)
    profile = get_employee_gamification_profile(emp_key)
    return jsonify({
        "status": "success",
        "employee_key": emp_key,
        "profile": profile,
    })
