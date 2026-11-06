"""
M-One Employee Alignment & Evaluation Routes (routes/employee_alignment_routes.py)
Rotas de API para aferição, governança de prazos, deliberações e ausências justificadas.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from routes.helpers import current_user, login_required
from services.employee_alignment_service import (
    evaluate_all_employees_with_gemini,
    evaluate_employee_with_gemini,
    get_employee_evaluation_data,
    save_desired_answers,
    save_director_alignment,
    suggest_comment_with_ai,
    toggle_feedback_release,
)
from services.employee_governance_service import (
    decide_report_edit_request,
    get_cycle_governance_status,
    remove_employee_exemption,
    set_employee_exemption,
    toggle_cycle_edit_unlock_all,
    toggle_cycle_feedback_release_all,
    toggle_report_edit_unlock,
)
from services.employee_reports_data import is_admin_viewer

logger = logging.getLogger(__name__)

employee_alignment_bp = Blueprint("employee_alignment", __name__)


def _is_admin() -> bool:
    me = current_user() or {}
    return is_admin_viewer((me.get("username") or "").lower().strip(), (me.get("role") or "").lower().strip())


@employee_alignment_bp.route("/api/relatorio/detalhes/<int:cycle_id>/<employee_key>", methods=["GET"])
@login_required
def api_get_evaluation_details(cycle_id: int, employee_key: str):
    """Retorna os dados completos da tríade (perguntas, fornecidas, desejadas, notas e gaps)."""
    me = current_user()
    username = (me.get("username") or "").lower().strip()
    is_admin = _is_admin()

    # Se não for admin, só pode acessar seu próprio relatório se o feedback estiver liberado
    if not is_admin and username != employee_key.lower().strip():
        return jsonify({"success": False, "error": "Acesso não autorizado."}), 403

    try:
        data = get_employee_evaluation_data(cycle_id, employee_key)
        # Se for o próprio colaborador e o feedback NÃO foi liberado pela diretoria, oculta respostas desejadas e notas internas
        if not is_admin and not data.get("is_feedback_released"):
            return jsonify({
                "success": False,
                "error": "A avaliação deste ciclo ainda está em fase de alinhamento pela Diretoria.",
                "is_feedback_released": False,
            }), 403

        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Erro ao carregar detalhes de avaliação ({employee_key}, ciclo {cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/salvar-desejadas", methods=["POST"])
@login_required
def api_save_desired_answers():
    """Salva as respostas desejadas customizadas pela Diretoria para um colaborador no ciclo."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")
    desired_answers = payload.get("desired_answers") or {}

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        updated = save_desired_answers(int(cycle_id), employee_key, desired_answers)
        return jsonify({
            "success": True,
            "message": f"Respostas desejadas de {updated.get('employee_name')} salvas com sucesso!",
            "data": updated,
        })
    except Exception as e:
        logger.error(f"Erro ao salvar respostas desejadas: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/salvar-alinhamento", methods=["POST"])
@login_required
def api_save_director_alignment():
    """Salva os pareceres de alinhamento por pergunta e os acordos para Jam/Geysa e Fauzer."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")
    director_comments = payload.get("director_comments") or {}
    agreements_jam_geysa = payload.get("agreements_jam_geysa", "")
    agreements_fauzer = payload.get("agreements_fauzer", "")

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        updated = save_director_alignment(
            cycle_id=int(cycle_id),
            employee_key=employee_key,
            director_comments=director_comments,
            agreements_jam_geysa=agreements_jam_geysa,
            agreements_fauzer=agreements_fauzer,
        )
        return jsonify({
            "success": True,
            "message": f"Pareceres e combinados de {updated.get('employee_name')} salvos com sucesso!",
            "data": updated,
        })
    except Exception as e:
        logger.error(f"Erro ao salvar alinhamento de diretoria ({employee_key}, ciclo {cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/sugerir-comentario", methods=["POST"])
@login_required
def api_suggest_comment_ai():
    """Gera uma sugestão de comentário construtivo sob demanda com IA para inspirar a Diretoria."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    question_label = payload.get("question_label", "")
    provided_answer = payload.get("provided_answer", "")
    role_title = payload.get("role_title", "")
    employee_name = payload.get("employee_name", "")

    try:
        suggestion = suggest_comment_with_ai(
            question_label=question_label,
            provided_answer=provided_answer,
            role_title=role_title,
            employee_name=employee_name,
        )
        return jsonify({"success": True, "suggestion": suggestion})
    except Exception as e:
        logger.error(f"Erro ao gerar sugestão de comentário: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/analisar-ia", methods=["POST"])
@login_required
def api_evaluate_employee_ai():
    """Dispara a aferição com IA via Gemini comparando o desejado com o fornecido."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        result = evaluate_employee_with_gemini(int(cycle_id), employee_key)
        return jsonify({
            "success": True,
            "message": f"Aferição de {result.get('employee_name')} concluída com sucesso! Score: {result.get('score_total')}/100",
            "data": result,
        })
    except Exception as e:
        logger.error(f"Erro ao executar aferição com IA ({employee_key}, ciclo {cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/analisar-todos", methods=["POST"])
@login_required
def api_evaluate_all_ai():
    """Dispara a aferição com IA de todos os colaboradores do ciclo em lote."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")

    if not cycle_id:
        return jsonify({"success": False, "error": "cycle_id é obrigatório."}), 400

    try:
        results = evaluate_all_employees_with_gemini(int(cycle_id))
        return jsonify({
            "success": True,
            "message": f"Aferição em lote concluída para {len(results)} colaboradores!",
            "results": results,
        })
    except Exception as e:
        logger.error(f"Erro ao executar aferição em lote (ciclo {cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/toggle-liberacao", methods=["POST"])
@login_required
def api_toggle_feedback_release():
    """Ativa ou desativa a liberação da visualização das respostas desejadas no portal do colaborador."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")
    is_released = bool(payload.get("is_released"))

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        new_val = toggle_feedback_release(int(cycle_id), employee_key, is_released)
        status_msg = "liberada para visualização do colaborador" if new_val else "bloqueada (modo confidencial da diretoria)"
        return jsonify({
            "success": True,
            "message": f"Avaliação de {employee_key.capitalize()} agora está {status_msg}.",
            "is_feedback_released": new_val,
        })
    except Exception as e:
        logger.error(f"Erro ao alternar liberação de feedback: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/demandas-consolidadas/<int:cycle_id>", methods=["GET"])
@login_required
def api_get_consolidated_demands(cycle_id: int):
    """Retorna todas as demandas de Jam, Geysa e Fauzer agregadas para toda a equipe no ciclo."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403
    try:
        from services.employee_report_dispatch_service import get_consolidated_cycle_demands
        data = get_consolidated_cycle_demands(cycle_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Erro ao consolidar demandas do ciclo {cycle_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/salvar-status-gestores", methods=["POST"])
@login_required
def api_save_manager_status():
    """Salva a avaliação de status (badge e parecer) de Jam, Geysa e Fauzer para um colaborador."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")
    evaluations = payload.get("evaluations") or {}

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        from services.manager_status_service import save_employee_manager_evaluations
        updated = save_employee_manager_evaluations(int(cycle_id), employee_key, evaluations)
        return jsonify({"success": True, "message": "Status da liderança salvo com sucesso!", "data": updated})
    except Exception as e:
        logger.error(f"Erro ao salvar status dos gestores ({employee_key}, ciclo {cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/salvar-lote-status-gestor", methods=["POST"])
@login_required
def api_save_batch_manager_status():
    """Salva o status de vários colaboradores em lote para um gestor específico (Jam, Geysa ou Fauzer)."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    manager_key = (payload.get("manager_key") or "").lower().strip()
    evaluations_map = payload.get("evaluations_map") or {}

    if not cycle_id or not manager_key:
        return jsonify({"success": False, "error": "cycle_id e manager_key são obrigatórios."}), 400

    try:
        from services.manager_status_service import save_batch_manager_status
        updated = save_batch_manager_status(int(cycle_id), manager_key, evaluations_map)
        return jsonify({"success": True, "message": f"Status da equipe atualizado para {manager_key.upper()}!", "data": updated})
    except Exception as e:
        logger.error(f"Erro ao salvar lote de status ({manager_key}, ciclo {cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/relatorio/sugerir-status-gestores-ia", methods=["POST"])
@login_required
def api_suggest_manager_status_ai():
    """Gera sugestões automáticas com IA para Jam, Geysa e Fauzer com base nas respostas do colaborador."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        from services.manager_status_service import suggest_manager_evaluations_ai
        suggestions = suggest_manager_evaluations_ai(int(cycle_id), employee_key)
        return jsonify({"success": True, "data": suggestions})
    except Exception as e:
        logger.error(f"Erro ao gerar sugestão de status com IA ({employee_key}, ciclo {cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/gestao-interna/decidir-solicitacao-edicao", methods=["POST"])
@login_required
def api_decide_edit_request():
    """Aprova ou recusa solicitação de edição de relatório na Gestão Interna."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")
    approved = bool(payload.get("approved"))

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        me = current_user() or {}
        res = decide_report_edit_request(int(cycle_id), employee_key, approved, me.get("username", "gerencia"))
        return jsonify(res)
    except Exception as e:
        logger.error(f"Erro ao decidir solicitação de edição: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/gestao-interna/toggle-edicao-colaborador", methods=["POST"])
@login_required
def api_toggle_edit_unlocked():
    """Ativa ou desativa a liberação de edição para um colaborador específico no ciclo."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")
    is_unlocked = bool(payload.get("is_unlocked"))

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        res_val = toggle_report_edit_unlock(int(cycle_id), employee_key, is_unlocked)
        action_msg = "liberado para edição" if res_val else "bloqueado contra edições"
        return jsonify({
            "success": True,
            "message": f"Relatório de {employee_key.capitalize()} agora está {action_msg}.",
            "is_edit_unlocked": res_val,
        })
    except Exception as e:
        logger.error(f"Erro ao alterar trava de edição: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/gestao-interna/toggle-feedback-ciclo", methods=["POST"])
@login_required
def api_toggle_cycle_feedback():
    """Libera ou bloqueia as deliberações e feedbacks para todos os colaboradores do ciclo."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    is_released = bool(payload.get("is_released"))

    if not cycle_id:
        return jsonify({"success": False, "error": "cycle_id é obrigatório."}), 400

    try:
        res_val = toggle_cycle_feedback_release_all(int(cycle_id), is_released)
        msg = "Deliberações e feedbacks liberados para toda a equipe no ciclo!" if res_val else "Deliberações bloqueadas (modo confidencial) para todo o ciclo."
        return jsonify({"success": True, "message": msg, "feedback_released_all": res_val})
    except Exception as e:
        logger.error(f"Erro ao alterar liberação de feedback em lote: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/gestao-interna/toggle-edicao-ciclo", methods=["POST"])
@login_required
def api_toggle_cycle_edit():
    """Libera ou bloqueia a edição para todos os colaboradores do ciclo em lote."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    is_unlocked = bool(payload.get("is_unlocked"))

    if not cycle_id:
        return jsonify({"success": False, "error": "cycle_id é obrigatório."}), 400

    try:
        res_val = toggle_cycle_edit_unlock_all(int(cycle_id), is_unlocked)
        msg = "Edição liberada para todos os colaboradores no ciclo!" if res_val else "Edição bloqueada para todos os colaboradores no ciclo."
        return jsonify({"success": True, "message": msg, "edit_unlocked_all": res_val})
    except Exception as e:
        logger.error(f"Erro ao alterar trava de edição em lote: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/gestao-interna/governance-status/<int:cycle_id>", methods=["GET"])
@login_required
def api_get_governance_status(cycle_id: int):
    """Retorna o estado das travas e pendências de solicitação de edição para o ciclo."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403
    try:
        data = get_cycle_governance_status(cycle_id)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Erro ao buscar status de governança ({cycle_id}): {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/gestao-interna/set-exemption", methods=["POST"])
@login_required
def api_set_employee_exemption():
    """Registra ausência justificada ou licença (paternidade, saúde, férias)."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")
    exemption_type = payload.get("exemption_type") or "licenca"
    exemption_reason = payload.get("exemption_reason") or ""

    if not cycle_id or not employee_key or not exemption_reason.strip():
        return jsonify({"success": False, "error": "Ciclo, colaborador e motivo são obrigatórios."}), 400

    try:
        me = current_user() or {}
        res = set_employee_exemption(
            int(cycle_id),
            employee_key,
            exemption_type,
            exemption_reason,
            operator_username=me.get("username", "gerencia")
        )
        return jsonify(res)
    except Exception as e:
        logger.error(f"Erro ao registrar ausência/licença: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@employee_alignment_bp.route("/api/gestao-interna/remove-exemption", methods=["POST"])
@login_required
def api_remove_employee_exemption():
    """Remove ausência justificada ou licença."""
    if not _is_admin():
        return jsonify({"success": False, "error": "Acesso restrito à Diretoria e Administradores."}), 403

    payload = request.get_json(silent=True) or {}
    cycle_id = payload.get("cycle_id")
    employee_key = payload.get("employee_key")

    if not cycle_id or not employee_key:
        return jsonify({"success": False, "error": "cycle_id e employee_key são obrigatórios."}), 400

    try:
        me = current_user() or {}
        res = remove_employee_exemption(
            int(cycle_id),
            employee_key,
            operator_username=me.get("username", "gerencia")
        )
        return jsonify(res)
    except Exception as e:
        logger.error(f"Erro ao remover ausência/licença: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500



