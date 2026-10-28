"""
M-One Radar de Mercado Routes (routes/radar_routes.py)
Endpoints para operação e gestão de Missões Táticas / Lotes de Prospecção Georreferenciada.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations
import csv, io, logging
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request, Response
from routes.helpers import audit, current_user, login_required, roles_required
from services.prospector_service import (
    executar_prospeccao_assincrona,
    get_all_nichos,
    obter_status_job,
)
from services.radar_service import (
    CIDADES_SUGERIDAS_ES,
    criar_lote,
    excluir_lote,
    listar_leads_radar,
    obter_cidades_rastreadas,
    obter_metricas_radar,
)
from services.radar_excel_service import gerar_planilha_radar_multi_abas
from database import db

logger = logging.getLogger(__name__)

radar_bp = Blueprint("radar", __name__)


@radar_bp.route("/radar", methods=["GET"])
@radar_bp.route("/radar/", methods=["GET"])
@radar_bp.route("/admin/radar", methods=["GET"])
@radar_bp.route("/admin/radar/", methods=["GET"])
@login_required
@roles_required("admin", "support", "sales")
def index():
    """Painel Direto do Radar de Mercado por Cidade."""
    user = current_user() or {}
    user_role = user.get("role", "sales")
    is_admin = (user_role in ("admin", "support"))

    cidades_rastreadas = obter_cidades_rastreadas()
    cidade_filtro = request.args.get("cidade", "all")
    status_filtro = request.args.get("status", "all")
    apenas_wa = request.args.get("whatsapp_only") == "1"
    busca = request.args.get("busca", "").strip()

    leads = listar_leads_radar(
        cidade=cidade_filtro if cidade_filtro != "all" else None,
        status_contato=status_filtro if status_filtro != "all" else None,
        apenas_wa=apenas_wa,
        busca=busca if busca else None
    )

    total_leads = len(leads)
    total_wa = sum(1 for l in leads if l.get("whatsapp"))
    metricas = obter_metricas_radar()
    nichos = get_all_nichos(apenas_ativos=True)
    default_nicho = nichos[0]["slug"] if nichos else "revenda-motos"
    job_status = obter_status_job()

    return render_template(
        "admin/radar.html",
        leads=leads,
        total_leads=total_leads,
        total_wa=total_wa,
        cidades_rastreadas=cidades_rastreadas,
        cidade_filtro=cidade_filtro,
        metricas=metricas,
        nichos=nichos,
        default_nicho=default_nicho,
        cidades_sugeridas=CIDADES_SUGERIDAS_ES,
        job_status=job_status,
        status_filtro=status_filtro,
        apenas_wa=apenas_wa,
        busca=busca,
        is_admin=is_admin,
        user=user,
    )


@radar_bp.route("/radar/api/disparar", methods=["POST"])
@login_required
@roles_required("admin", "support", "sales")
def disparar_missao():
    """Cria um novo Lote/Missão e aciona o robô georreferenciado."""
    data = request.get_json(silent=True) or {}
    praca = data.get("praca", "").strip()
    nicho = data.get("nicho", "").strip()
    limite = int(data.get("limite", 25))

    if not praca or not nicho:
        return jsonify({"status": "error", "message": "Praça/Cidade e Nicho são obrigatórios."}), 400

    job_status = obter_status_job()
    if job_status.get("running"):
        return jsonify({"status": "error", "message": "Já existe uma varredura em andamento. Aguarde a conclusão."}), 409

    try:
        user = current_user() or {}
        lote = criar_lote(praca, nicho, limite=limite, user=user)
        executar_prospeccao_assincrona(nicho, praca, limite=limite, lote_id=lote["id"])
        audit("RADAR_MISSAO_DISPARADA", f"Lote {lote.get('id')}: Praça {praca}, Nicho {nicho}, Limite {limite}")
        return jsonify({
            "status": "success",
            "message": f"Missão disparada com sucesso para {praca}!",
            "lote_id": str(lote.get("id"))
        })
    except Exception as e:
        logger.error("Erro ao disparar missão no Radar: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@radar_bp.route("/radar/api/status", methods=["GET"])
@login_required
@roles_required("admin", "support", "sales")
def status_radar():
    """Retorna telemetria da thread em tempo real."""
    return jsonify({"status": "success", "job": obter_status_job()})


@radar_bp.route("/radar/api/lote/<lote_id>", methods=["GET"])
@login_required
@roles_required("admin", "support", "sales")
def obter_dados_lote(lote_id: str):
    """Consulta detalhes e leads de um lote específico."""
    lote = obter_lote_por_id(lote_id)
    if not lote:
        return jsonify({"status": "error", "message": "Lote não encontrado."}), 404
    leads = listar_leads_do_lote(lote_id)
    return jsonify({"status": "success", "lote": lote, "leads": leads})


@radar_bp.route("/radar/api/lote/<lote_id>/excluir", methods=["POST"])
@login_required
@roles_required("admin", "support")
def deletar_lote(lote_id: str):
    """Exclui um lote e remove o vínculo dos leads."""
    ok = excluir_lote(lote_id)
    if ok:
        audit("RADAR_LOTE_EXCLUIDO", f"Lote {lote_id} excluído.")
        return jsonify({"status": "success", "message": "Lote removido com sucesso!"})
    return jsonify({"status": "error", "message": "Não foi possível remover o lote."}), 500


@radar_bp.route("/radar/api/lead/<lead_id>/prospectar", methods=["POST"])
@login_required
@roles_required("admin", "support", "sales")
def prospectar_lead_radar(lead_id: str):
    """Registra abordagem de WhatsApp em um lead da missão."""
    user = current_user() or {}
    data = request.get_json(silent=True) or {}
    mensagem = data.get("mensagem", "").strip()
    vendedor_nome = user.get("name") or user.get("username") or "Vendedor"

    with db() as conn:
        conn.execute(
            """
            UPDATE prospeccao.leads
            SET status_contato = 'prospectado',
                prospectado_por_id = %s,
                prospectado_por_nome = %s,
                prospectado_em = NOW(),
                mensagem_enviada = COALESCE(NULLIF(%s, ''), mensagem_enviada),
                updated_at = NOW()
            WHERE id = %s::uuid;
            """,
            [user.get("id"), vendedor_nome, mensagem, lead_id]
        )
        conn.commit()

    audit("RADAR_LEAD_PROSPECTADO", f"Lead {lead_id} abordado por {vendedor_nome}")
    return jsonify({"status": "success", "message": f"Lead marcado como prospectado por {vendedor_nome}!"})


@radar_bp.route("/radar/api/lead/<lead_id>/status", methods=["POST"])
@login_required
@roles_required("admin", "support", "sales")
def alterar_status_lead_radar(lead_id: str):
    """Atualiza o funil de um lead de missão do Radar."""
    data = request.get_json(silent=True) or {}
    novo_status = data.get("status", "novo")
    notas = data.get("notas")

    with db() as conn:
        conn.execute(
            """
            UPDATE prospeccao.leads
            SET status_contato = %s,
                notas_comerciais = COALESCE(%s, notas_comerciais),
                updated_at = NOW()
            WHERE id = %s::uuid;
            """,
            [novo_status, notas, lead_id]
        )
        conn.commit()

    return jsonify({"status": "success", "message": "Status atualizado com sucesso!"})


@radar_bp.route("/radar/exportar", methods=["GET"])
@login_required
@roles_required("admin", "support", "sales")
def exportar_radar_csv():
    """Exporta os leads filtrados da tela em formato CSV compatível com Excel."""
    cidade = request.args.get("cidade", "all")
    leads = listar_leads_radar(cidade=cidade if cidade != "all" else None, limit=500)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Classe", "Score", "Nome Comercial", "Razao Social", "CNPJ", "Decisor", "Telefone", "WhatsApp", "Email", "Cidade", "UF", "Site", "Instagram", "Gancho Comercial", "Status"])
    for l in leads:
        writer.writerow([
            l.get("classificacao", ""), l.get("score", 0), l.get("nome", ""), l.get("razao_social", ""),
            l.get("cnpj", ""), l.get("decisor_nome", ""), l.get("telefone_google", ""), l.get("whatsapp", ""),
            l.get("email", ""), l.get("cidade", ""), l.get("uf", ""), l.get("site", ""), l.get("instagram", ""),
            l.get("gancho_comercial", ""), l.get("status_contato", "novo"),
        ])
    csv_data = "\ufeff" + output.getvalue()
    slug_cidade = (cidade if cidade != "all" else "geral").lower().replace(" ", "_")
    return Response(csv_data, mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=radar_{slug_cidade}.csv"})


@radar_bp.route("/radar/exportar-excel", methods=["GET", "POST"])
@login_required
@roles_required("admin", "support", "sales")
def exportar_radar_excel():
    """Gera e exporta planilha Excel (.xlsx) executiva multi-abas por cidade."""
    # Coleta cidades selecionadas (via POST json/form ou GET query string)
    cidades: List[str] = []
    if request.method == "POST":
        if request.is_json:
            cidades = request.json.get("cidades") or []
        else:
            cidades = request.form.getlist("cidades") or request.form.getlist("cidades[]")
    
    if not cidades:
        cidades_param = request.args.get("cidades", "").strip()
        if cidades_param:
            cidades = [c.strip() for c in cidades_param.split(",") if c.strip()]

    # Fallback: se nenhuma cidade informada, exporta todas as cidades já prospectadas
    if not cidades:
        cidades_rastreadas = obter_cidades_rastreadas()
        cidades = [cr["cidade"] for cr in cidades_rastreadas if cr.get("cidade")]

    apenas_wa = (
        request.args.get("whatsapp_only") == "1"
        or request.form.get("whatsapp_only") == "1"
        or (request.is_json and request.json.get("whatsapp_only") is True)
    )
    status_filtro = (
        request.args.get("status")
        or request.form.get("status")
        or (request.is_json and request.json.get("status"))
        or "all"
    )

    buf = gerar_planilha_radar_multi_abas(
        cidades_selecionadas=cidades,
        apenas_wa=apenas_wa,
        status_filtro=status_filtro
    )
    
    audit("radar_exportar_excel", f"Exportação multi-abas de {len(cidades)} cidades em Excel (.xlsx)")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"radar_leads_multi_abas_{timestamp}.xlsx"
    
    return Response(
        buf.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
