"""
M-One Internal Analysis Routes (routes/internal_analysis_routes.py)
Rotas de API da Análise Interna da Reunião de Diretoria e Histórico Multi-Ciclos Setorizado.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from routes.helpers import audit, current_user, login_required
from services.employee_reports_data import is_admin_viewer
from services.internal_analysis_sectors_service import get_multi_cycle_internal_history
from services.internal_analysis_service import (
    generate_ai_internal_analysis,
    get_internal_analysis,
    save_or_init_internal_analysis,
    seed_demo_simulation_cycle,
)

logger = logging.getLogger(__name__)

internal_analysis_bp = Blueprint("internal_analysis", __name__)


def _require_admin():
    me = current_user() or {}
    username = (me.get("username") or "").lower().strip()
    role = (me.get("role") or "").lower().strip()
    if not is_admin_viewer(username, role):
        return None, (jsonify({"error": "Acesso restrito à Diretoria e Administradores."}), 403)
    return me, None


def _require_curator():
    me = current_user() or {}
    username = (me.get("username") or "").lower().strip()
    if username not in ["fauzer", "support", "admin"]:
        return None, (jsonify({"error": "Acesso restrito ao curador estratégico da Análise Interna."}), 403)
    return me, None


@internal_analysis_bp.route("/admin/plano/api/analise-interna", methods=["GET"])
@login_required
def api_get_analise_interna():
    """Recupera a Análise Interna do ciclo."""
    _, err = _require_admin()
    if err:
        return err

    cycle_id = request.args.get("cycle_id", type=int)
    if not cycle_id:
        return jsonify({"status": "error", "message": "ID do ciclo ausente."}), 400

    analysis = get_internal_analysis(cycle_id)
    return jsonify({"status": "success", "analysis": analysis})


@internal_analysis_bp.route("/admin/plano/api/analise-interna/historico-ciclos", methods=["GET"])
@login_required
def api_get_historico_multi_ciclos():
    """Retorna a linha do tempo consolidada por setor de todos os ciclos e gargalos recorrentes."""
    me, err = _require_admin()
    if err:
        return err

    username = (me.get("username") or "").lower().strip()
    include_curating = username in ["fauzer", "support", "admin"]
    try:
        history = get_multi_cycle_internal_history(include_curating=include_curating)
        return jsonify({"status": "success", "history": history})
    except Exception as e:
        logger.error("Erro ao carregar histórico multi-ciclos da análise interna: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@internal_analysis_bp.route("/admin/plano/api/analise-interna/gerar-ia", methods=["POST"])
@login_required
def api_gerar_ia_analise_interna():
    """Dispara a síntese balanceada por IA (Gemini) dos relatórios do ciclo."""
    me, err = _require_curator()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    analysis = generate_ai_internal_analysis(cycle_id)
    audit("plano.analise_ia_generated", f"Síntese de IA da Análise Interna do Ciclo {cycle_id} gerada por {me.get('username')}")
    return jsonify({"status": "success", "message": "Análise Interna sintetizada com IA com sucesso!", "analysis": analysis})


@internal_analysis_bp.route("/admin/plano/api/analise-interna/salvar-curadoria", methods=["POST"])
@login_required
def api_salvar_curadoria_analise_interna():
    """Salva as edições e observações de curadoria realizadas por Fauzer."""
    me, err = _require_curator()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    curated_data = data.get("curated_data") or {}

    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    saved = save_or_init_internal_analysis(
        cycle_id=cycle_id,
        status="curating",
        curated_data=curated_data,
        curated_by=(me.get("username") or "fauzer").lower(),
        published=False,
    )
    audit("plano.analise_curated", f"Curadoria da Análise Interna do Ciclo {cycle_id} salva por {me.get('username')}")
    return jsonify({"status": "success", "message": "Curadoria salva com sucesso!", "analysis": saved})


@internal_analysis_bp.route("/admin/plano/api/analise-interna/liberar", methods=["POST"])
@login_required
def api_liberar_analise_interna():
    """Homologa e libera a Análise Interna para visualização por Jam e Geysa."""
    me, err = _require_curator()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    curated_data = data.get("curated_data") or None

    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    saved = save_or_init_internal_analysis(
        cycle_id=cycle_id,
        curated_data=curated_data,
        curated_by=(me.get("username") or "fauzer").lower(),
        published=True,
    )
    audit("plano.analise_published", f"Análise Interna do Ciclo {cycle_id} LIBERADA para a Diretoria por {me.get('username')}")
    return jsonify({"status": "success", "message": "🚀 Análise Interna liberada com sucesso para Jam e Geysa!", "analysis": saved})


@internal_analysis_bp.route("/admin/plano/api/analise-interna/salvar-deliberacoes", methods=["POST"])
@login_required
def api_salvar_deliberacoes_reuniao():
    """Registra as resoluções e deliberações de Jam e Geysa durante a reunião ao vivo."""
    me, err = _require_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    meeting_decisions = data.get("meeting_decisions") or []

    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    saved = save_or_init_internal_analysis(
        cycle_id=cycle_id,
        meeting_decisions=meeting_decisions,
    )
    audit("plano.deliberacoes_saved", f"Deliberações da reunião de Diretoria do Ciclo {cycle_id} registradas por {me.get('username')}")
    return jsonify({"status": "success", "message": "Deliberações da reunião salvas com sucesso!", "analysis": saved})


@internal_analysis_bp.route("/admin/plano/api/analise-interna/simular-dados", methods=["POST"])
@login_required
def api_simular_dados_analise_interna():
    """Popula respostas de teste realistas dos colaboradores para validação de fim de semana."""
    me, err = _require_curator()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    cycle_id = int(data.get("cycle_id", 0))
    if cycle_id <= 0:
        return jsonify({"status": "error", "message": "ID do ciclo inválido."}), 400

    analysis = seed_demo_simulation_cycle(cycle_id)
    audit("plano.demo_seeded", f"Dados de simulação do Ciclo {cycle_id} carregados por {me.get('username')}")
    return jsonify({"status": "success", "message": "🧪 Respostas simuladas e Análise Interna geradas com sucesso para teste!", "analysis": analysis})

