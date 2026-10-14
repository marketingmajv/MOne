"""
M-One Implementation Plan Routes (routes/implementation_plan_routes.py)
Rotas do Painel Executivo do Plano de Implantação, Governança e Relatórios Semanais.
Acesso adaptativo: colaboradores acessam exclusivamente seu formulário semanal;
Diretoria e Gerência (Jam, Geysa, Fauzer, Suporte) possuem visão de dashboard, controle de prazos e consolidação.
"""

from __future__ import annotations

import logging
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from routes.helpers import audit, current_user, login_required
from services.employee_reports_data import (
    get_reporting_employee_meta,
    is_admin_viewer,
)
from services.employee_reports_service import (
    ensure_reports_schema,
    get_cycle_submissions_summary,
    get_employee_report,
    get_monday_consolidation_briefing,
    get_or_create_current_cycle,
    save_or_submit_report,
    update_cycle_deadline,
)
from services.implementation_plan_data import (
    get_departments_data,
    get_team_members_data,
)
from services.implementation_plan_service import (
    ensure_implementation_plan_schema,
    get_all_implementation_phases,
    get_implementation_summary,
)

logger = logging.getLogger(__name__)

implementation_plan_bp = Blueprint("implementation_plan", __name__)


@implementation_plan_bp.route("/admin/plano", methods=["GET"])
@login_required
def index():
    """Painel do Plano MAJ e Formulário Semanal de Colaboradores."""
    ensure_implementation_plan_schema()
    ensure_reports_schema()

    me = current_user()
    if not me:
        return redirect(url_for("login"))

    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    admin_view = is_admin_viewer(username, role)

    cycle = get_or_create_current_cycle()

    # Se NÃO for administrador/gerência, exibe estritamente o formulário do próprio colaborador
    if not admin_view:
        employee_key = username
        emp_meta = get_reporting_employee_meta(employee_key)
        my_report = get_employee_report(cycle["id"], employee_key) if emp_meta else {}

        return render_template(
            "admin/implementation_plan.html",
            me=me,
            is_admin_viewer=False,
            active_tab="meu_relatorio",
            cycle=cycle,
            employee_meta=emp_meta,
            my_report=my_report,
        )

    # Para Diretoria & Gerência (Jam, Geysa, Fauzer, Suporte)
    active_tab = request.args.get("tab", "dashboard")
    summary = get_cycle_submissions_summary(cycle["id"])
    consolidation = get_monday_consolidation_briefing(cycle["id"])
    team = get_team_members_data()
    departments = get_departments_data()

    # Se for o Fauzer, ele também possui formulário próprio para enviar
    fauzer_meta = get_reporting_employee_meta("fauzer")
    fauzer_report = get_employee_report(cycle["id"], "fauzer")

    return render_template(
        "admin/implementation_plan.html",
        me=me,
        is_admin_viewer=True,
        active_tab=active_tab,
        cycle=cycle,
        summary=summary,
        consolidation=consolidation,
        team=team,
        departments=departments,
        fauzer_meta=fauzer_meta,
        fauzer_report=fauzer_report,
    )


@implementation_plan_bp.route("/admin/plano/submit-report", methods=["POST"])
@login_required
def submit_report():
    """Recebe e processa o envio ou salvamento em rascunho do relatório semanal."""
    ensure_reports_schema()
    me = current_user()
    if not me:
        return redirect(url_for("login"))
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    admin_view = is_admin_viewer(username, role)

    try:
        cycle_id = int(request.form.get("cycle_id", 0))
        target_employee = request.form.get("employee_key", "").lower().strip()
        action = request.form.get("action", "submit").lower().strip()
        is_draft = (action == "draft")

        if cycle_id <= 0:
            flash("Ciclo semanal inválido.", "danger")
            return redirect(url_for("implementation_plan.index"))

        # Trava de Segurança: Colaborador comum só pode alterar seu próprio relatório
        if not admin_view and target_employee != username:
            flash("Permissão negada: você só pode enviar o seu próprio relatório.", "danger")
            return redirect(url_for("implementation_plan.index"))

        meta = get_reporting_employee_meta(target_employee)
        if not meta:
            flash("Perfil de colaborador não localizado.", "danger")
            return redirect(url_for("implementation_plan.index"))

        # Extrai respostas dos campos da cartilha oficial
        answers = {}
        for q in meta.get("questions", []):
            qid = q["id"]
            answers[qid] = request.form.get(qid, "").strip()

        saved = save_or_submit_report(
            cycle_id=cycle_id,
            user_id=me.get("id"),
            employee_key=target_employee,
            answers=answers,
            is_draft=is_draft,
        )

        status_msg = "Rascunho salvo com sucesso!" if is_draft else "Relatório semanal enviado com sucesso para a Diretoria!"
        flash(status_msg, "info" if is_draft else "success")

        audit(
            "relatorio.submit",
            f"Relatório de {meta['name']} ({'Rascunho' if is_draft else 'Oficial'}) submetido por {username} (status: {saved.get('status')})"
        )

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "success": True,
                "message": status_msg,
                "status": saved.get("status"),
                "is_draft": is_draft,
            })

    except Exception as e:
        logger.error("Erro ao submeter relatório semanal: %s", e)
        flash(f"Erro ao processar relatório: {e}", "danger")

    redirect_tab = "meu_relatorio" if not admin_view else request.form.get("redirect_tab", "dashboard")
    return redirect(url_for("implementation_plan.index", tab=redirect_tab))


@implementation_plan_bp.route("/admin/plano/update-deadline", methods=["POST"])
@login_required
def update_deadline():
    """Permite aos administradores alterar o prazo oficial de entrega do ciclo."""
    ensure_reports_schema()
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()

    if not is_admin_viewer(username, role):
        flash("Permissão negada. Apenas a Diretoria pode alterar prazos.", "danger")
        return redirect(url_for("implementation_plan.index"))

    try:
        cycle_id = int(request.form.get("cycle_id", 0))
        new_deadline = request.form.get("deadline", "").strip()

        if cycle_id <= 0 or not new_deadline:
            flash("Dados de prazo incompletos.", "warning")
            return redirect(url_for("implementation_plan.index", tab="dashboard"))

        success = update_cycle_deadline(cycle_id, new_deadline)
        if success:
            audit("plano.deadline_update", f"Prazo do ciclo #{cycle_id} alterado para '{new_deadline}' por {username}")
            flash("Prazo de entrega atualizado com sucesso!", "success")
        else:
            flash("Formato de data/hora inválido para o prazo.", "danger")

    except Exception as e:
        logger.error("Erro ao atualizar prazo de ciclo: %s", e)
        flash(f"Falha ao salvar novo prazo: {e}", "danger")

    return redirect(url_for("implementation_plan.index", tab="dashboard"))


@implementation_plan_bp.route("/api/admin/plano/summary", methods=["GET"])
@login_required
def api_summary():
    """Retorna dados consolidados para consumo assíncrono ou dashboards."""
    ensure_implementation_plan_schema()
    ensure_reports_schema()

    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()

    if not is_admin_viewer(username, role):
        return jsonify({"error": "Acesso negado"}), 403

    cycle = get_or_create_current_cycle()
    summary = get_cycle_submissions_summary(cycle["id"])
    return jsonify({
        "success": True,
        "cycle": cycle,
        "summary": summary,
    })
