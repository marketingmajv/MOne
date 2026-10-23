"""
M-One Implementation Plan Routes (routes/implementation_plan_routes.py)
Rotas do Painel Executivo do Plano de Implantação, Governança e Relatórios Semanais.
Acesso adaptativo: colaboradores acessam exclusivamente seu formulário semanal;
Diretoria e Gerência (Jam, Geysa, Fauzer, Suporte) possuem visão de dashboard, controle de prazos e consolidação.
"""

from __future__ import annotations

import logging
from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for

from routes.helpers import audit, current_user, login_required
from services.employee_reports_data import get_reporting_employee_meta, is_admin_viewer
from services.employee_reports_service import (
    ensure_reports_schema, get_all_cycles, get_cycle_submissions_summary,
    get_employee_report, get_monday_consolidation_briefing,
    get_or_create_current_cycle, save_or_submit_report, update_cycle_deadline,
)
from services.implementation_plan_data import get_departments_data, get_team_members_data
from services.implementation_plan_service import (
    ensure_implementation_plan_schema, get_all_implementation_phases, get_implementation_summary,
)
from services.employee_doc_importer_service import (
    get_all_doc_links, save_doc_link, sync_single_employee_report, sync_all_configured_docs,
)
from services.internal_analysis_service import (
    ensure_internal_analysis_schema, get_internal_analysis, save_or_init_internal_analysis,
    generate_ai_internal_analysis, seed_demo_simulation_cycle,
)
from services.employee_docx_importer_service import find_docx_file, process_docx_upload

logger = logging.getLogger(__name__)

implementation_plan_bp = Blueprint("implementation_plan", __name__)


@implementation_plan_bp.route("/gestao-interna", methods=["GET"])
@implementation_plan_bp.route("/admin/gestao-interna", methods=["GET"])
@implementation_plan_bp.route("/admin/plano", methods=["GET"])
@login_required
def index():
    """Painel Executivo de Gestão Interna e Governança MAJ (Exclusivo para Diretoria e Administradores)."""
    ensure_implementation_plan_schema()
    ensure_reports_schema()
    ensure_internal_analysis_schema()

    me = current_user()
    if not me:
        return redirect(url_for("login"))

    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    admin_view = is_admin_viewer(username, role)
    is_curator = username in ["fauzer", "support", "admin"]

    # Se NÃO for administrador/gerência, bloqueia acesso e redireciona para a dashboard
    if not admin_view:
        flash("Acesso restrito à Diretoria e Administradores da MAJ Mobilidade.", "error")
        return redirect(url_for("dashboard"))

    all_cycles = get_all_cycles()
    selected_cycle_id = request.args.get("cycle_id", type=int)
    cycle = None
    if selected_cycle_id:
        cycle = next((c for c in all_cycles if c["id"] == selected_cycle_id), None)
    if not cycle:
        cycle = get_or_create_current_cycle()

    # Para Diretoria & Gerência (Jam, Geysa, Fauzer, Suporte)
    active_tab = request.args.get("tab", "dashboard")
    summary = get_cycle_submissions_summary(cycle["id"])
    consolidation = get_monday_consolidation_briefing(cycle["id"])
    team = get_team_members_data()
    departments = get_departments_data()
    internal_analysis = get_internal_analysis(cycle["id"])

    # Se for o Fauzer, ele também possui formulário próprio para enviar
    fauzer_meta = get_reporting_employee_meta("fauzer")
    fauzer_report = get_employee_report(cycle["id"], "fauzer")
    doc_links = get_all_doc_links()

    return render_template(
        "admin/implementation_plan.html",
        me=me,
        is_admin_viewer=True,
        is_curator=is_curator,
        active_tab=active_tab,
        cycle=cycle,
        all_cycles=all_cycles,
        summary=summary,
        consolidation=consolidation,
        internal_analysis=internal_analysis,
        team=team,
        departments=departments,
        fauzer_meta=fauzer_meta,
        fauzer_report=fauzer_report,
        doc_links=doc_links,
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

        # Trava de Segurança: Apenas administradores/diretoria podem submeter pelo painel
        if not admin_view:
            flash("Permissão negada: acesso restrito à Diretoria e Administradores.", "danger")
            return redirect(url_for("dashboard"))

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

    redirect_tab = request.form.get("redirect_tab", "dashboard")
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


@implementation_plan_bp.route("/admin/plano/api/doc-links", methods=["GET", "POST"])
@login_required
def api_doc_links():
    """Retorna ou salva os links oficiais do Google Docs de cada colaborador."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        return jsonify({"error": "Acesso negado"}), 403

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        emp_key = data.get("employee_key", "").lower().strip()
        url = data.get("google_doc_url", "").strip()

        if not emp_key or not url:
            return jsonify({"status": "error", "message": "Colaborador e URL do documento são obrigatórios."}), 400

        ok = save_doc_link(emp_key, url)
        if ok:
            audit("plano.doc_link_saved", f"Link do Google Doc de {emp_key} atualizado por {username}")
            return jsonify({"status": "success", "message": f"Link do Google Doc de {emp_key} salvo com sucesso!", "links": get_all_doc_links()})
        return jsonify({"status": "error", "message": "Link inválido. Certifique-se de que é uma URL válida do Google Docs."}), 400

    return jsonify({"status": "success", "links": get_all_doc_links()})


@implementation_plan_bp.route("/admin/plano/api/sync-doc", methods=["POST"])
@login_required
def api_sync_single_doc():
    """Sincroniza e extrai via IA as respostas de um colaborador específico."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        return jsonify({"error": "Acesso negado"}), 403

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    emp_key = data.get("employee_key", "").lower().strip()
    force = bool(data.get("force", False))
    custom_url = data.get("custom_url", "").strip() or None

    if cycle_id <= 0 or not emp_key:
        return jsonify({"status": "error", "message": "Dados incompletos (ciclo ou colaborador ausente)."}), 400

    result = sync_single_employee_report(
        cycle_id=cycle_id,
        employee_key=emp_key,
        custom_url=custom_url,
        force=force,
        user_id=me.get("id")
    )

    if result.get("status") == "success":
        audit("plano.doc_synced", f"Relatório de {emp_key} sincronizado via Google Doc por {username}")

    return jsonify(result)


@implementation_plan_bp.route("/admin/plano/api/sync-all-docs", methods=["POST"])
@login_required
def api_sync_all_docs():
    """Sincroniza em lote todos os colaboradores com Google Docs cadastrados."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        return jsonify({"error": "Acesso negado"}), 403

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID de ciclo inválido."}), 400

    result = sync_all_configured_docs(cycle_id=cycle_id, user_id=me.get("id"))
    audit("plano.all_docs_synced", f"Lote de Google Docs disparado por {username}: {result['sucessos']} sucessos, {result['divergencias']} divergências")
    return jsonify(result)


# =========================================================================
# ENDPOINTS DA ANÁLISE INTERNA (CURADORIA DE FAUZER & REUNIÃO DE DIRETORIA)
# =========================================================================

@implementation_plan_bp.route("/admin/plano/api/analise-interna", methods=["GET"])
@login_required
def api_get_analise_interna():
    """Recupera a Análise Interna do ciclo."""
    me = current_user()
    if not is_admin_viewer((me.get("username") or "").lower(), (me.get("role") or "").lower()):
        return jsonify({"error": "Acesso negado"}), 403

    cycle_id = request.args.get("cycle_id", type=int)
    if not cycle_id:
        return jsonify({"status": "error", "message": "ID do ciclo ausente."}), 400

    analysis = get_internal_analysis(cycle_id)
    return jsonify({"status": "success", "analysis": analysis})


@implementation_plan_bp.route("/admin/plano/api/analise-interna/gerar-ia", methods=["POST"])
@login_required
def api_gerar_ia_analise_interna():
    """Dispara a síntese balanceada por IA (Gemini) dos relatórios do ciclo."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    if username not in ["fauzer", "support", "admin"]:
        return jsonify({"error": "Apenas o curador estratégico pode disparar a síntese de IA."}), 403

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    analysis = generate_ai_internal_analysis(cycle_id)
    audit("plano.analise_ia_generated", f"Síntese de IA da Análise Interna do Ciclo {cycle_id} gerada por {username}")
    return jsonify({"status": "success", "message": "Análise Interna sintetizada com IA com sucesso!", "analysis": analysis})


@implementation_plan_bp.route("/admin/plano/api/analise-interna/salvar-curadoria", methods=["POST"])
@login_required
def api_salvar_curadoria_analise_interna():
    """Salva as edições e observações de curadoria realizadas por Fauzer."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    if username not in ["fauzer", "support", "admin"]:
        return jsonify({"error": "Acesso restrito ao curador da Análise Interna."}), 403

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    curated_data = data.get("curated_data") or {}

    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    saved = save_or_init_internal_analysis(
        cycle_id=cycle_id,
        status="curating",
        curated_data=curated_data,
        curated_by=username,
        published=False
    )
    audit("plano.analise_curated", f"Curadoria da Análise Interna do Ciclo {cycle_id} salva por {username}")
    return jsonify({"status": "success", "message": "Curadoria salva com sucesso!", "analysis": saved})


@implementation_plan_bp.route("/admin/plano/api/analise-interna/liberar", methods=["POST"])
@login_required
def api_liberar_analise_interna():
    """Homologa e libera a Análise Interna para visualização por Jam e Geysa."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    if username not in ["fauzer", "support", "admin"]:
        return jsonify({"error": "Apenas o curador pode liberar a Análise Interna para a Diretoria."}), 403

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    curated_data = data.get("curated_data") or None

    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    saved = save_or_init_internal_analysis(
        cycle_id=cycle_id,
        curated_data=curated_data,
        curated_by=username,
        published=True
    )
    audit("plano.analise_published", f"Análise Interna do Ciclo {cycle_id} LIBERADA para a Diretoria por {username}")
    return jsonify({"status": "success", "message": "🚀 Análise Interna liberada com sucesso para Jam e Geysa!", "analysis": saved})


@implementation_plan_bp.route("/admin/plano/api/analise-interna/salvar-deliberacoes", methods=["POST"])
@login_required
def api_salvar_deliberacoes_reuniao():
    """Registra as resoluções e deliberações de Jam e Geysa durante a reunião ao vivo."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        return jsonify({"error": "Acesso restrito à Diretoria e Administradores."}), 403

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    meeting_decisions = data.get("meeting_decisions") or []

    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    saved = save_or_init_internal_analysis(
        cycle_id=cycle_id,
        meeting_decisions=meeting_decisions
    )
    audit("plano.deliberacoes_saved", f"Deliberações da reunião de Diretoria do Ciclo {cycle_id} registradas por {username}")
    return jsonify({"status": "success", "message": "Deliberações da reunião salvas com sucesso!", "analysis": saved})


@implementation_plan_bp.route("/admin/plano/api/analise-interna/simular-dados", methods=["POST"])
@login_required
def api_simular_dados_analise_interna():
    """Popula respostas de teste realistas para os 7 colaboradores no ciclo para validação de fim de semana."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    if username not in ["fauzer", "support", "admin"]:
        return jsonify({"error": "Acesso negado."}), 403

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    analysis = seed_demo_simulation_cycle(cycle_id)
    audit("plano.demo_seeded", f"Dados de simulação do Ciclo {cycle_id} carregados por {username}")
    return jsonify({"status": "success", "message": "🧪 Respostas simuladas e Análise Interna geradas com sucesso para teste!", "analysis": analysis})


@implementation_plan_bp.route("/admin/plano/api/upload-docx", methods=["POST"])
@login_required
def api_upload_docx():
    """Recebe upload de relatório Word (.docx) de um colaborador e extrai respostas via IA."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        return jsonify({"error": "Acesso negado"}), 403

    cycle_id = request.form.get("cycle_id", type=int) or 0
    emp_key = (request.form.get("employee_key") or "").lower().strip()
    force = request.form.get("force", "").lower() in ("true", "1")
    file = request.files.get("file")

    if cycle_id <= 0 or not emp_key or not file:
        return jsonify({"status": "error", "message": "Ciclo, colaborador ou arquivo ausente."}), 400

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
        audit("plano.docx_uploaded", f"Relatório .docx de {emp_key} enviado por {username}")
    return jsonify(result)


@implementation_plan_bp.route("/admin/plano/download-docx", methods=["GET"])
@login_required
def download_docx():
    """Disponibiliza o download do arquivo DOCX original submetido."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        return jsonify({"error": "Acesso negado"}), 403

    filename = request.args.get("file", "").strip()
    cycle_code = request.args.get("cycle_code", "").strip()
    target_path = find_docx_file(cycle_code, filename)
    if not target_path or not target_path.exists():
        return jsonify({"status": "error", "message": "Arquivo DOCX não encontrado."}), 404

    return send_file(str(target_path), as_attachment=True, download_name=target_path.name)


