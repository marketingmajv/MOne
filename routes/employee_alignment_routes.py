"""
M-One Employee Alignment & Evaluation Routes (routes/employee_alignment_routes.py)
Rotas de API para o novo sistema de aferição e confronto de respostas:
- Consulta da tríade (Pergunta, Fornecida, Desejada)
- Configuração de respostas desejadas por funcionário
- Aferição com IA (Gemini) individual e em lote
- Liberação deliberada de gabarito/feedback para colaboradores
Segregação modular estrita (< 500 linhas).
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
from services.employee_reports_data import is_admin_viewer

logger = logging.getLogger(__name__)

employee_alignment_bp = Blueprint("employee_alignment", __name__)


def _is_admin() -> bool:
    me = current_user()
    if not me:
        return False
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    return is_admin_viewer(username, role)


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

