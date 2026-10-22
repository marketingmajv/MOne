"""
M-One Prospector Routes (routes/prospector_routes.py)
Rotas do módulo de Prospecção de Leads e Máquina de Vendas MAJ:
- Painel Executivo (/admin/prospeccao)
- Aba 'Leads Qualificados Capturados'
- Disparo de Busca e Polling Assíncrono
- Sincronização Google Sheets e Exportação Meta Lookalike
Acesso restrito à Diretoria ('admin') e Suporte Técnico ('support').
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
from flask import Blueprint, Response, jsonify, render_template, request, redirect, url_for, flash, send_file
from database import db
from routes.helpers import audit, current_user, login_required, roles_required
from services.prospector_service import (
    buscar_google_maps_apify,
    executar_prospeccao_assincrona,
    get_all_nichos,
    get_nicho_by_slug,
    get_prospector_config,
    obter_status_job,
    set_prospector_config,
)
from services.maintenance_service import get_module_status
from services.prospector_export_service import (
    exportar_csv_meta_lookalike,
    gerar_csv_leads,
    gerar_planilha_excel_leads,
    get_google_sheets_url,
    get_sheets_webhook_url,
    listar_leads_capturados,
    obter_metricas_resumo,
    set_google_sheets_url,
    set_sheets_webhook_url,
    sincronizar_com_google_sheets,
)
from services.prospector_sync_service import (
    executar_ciclo_automacao,
    obter_config_automacao,
    salvar_config_automacao,
)

logger = logging.getLogger(__name__)

prospector_bp = Blueprint("prospector", __name__)


@prospector_bp.route("/admin/prospeccao", methods=["GET"])
@prospector_bp.route("/admin/prospeccao/", methods=["GET"])
@prospector_bp.route("/prospeccao", methods=["GET"])
@prospector_bp.route("/prospeccao/", methods=["GET"])
@login_required
@roles_required("admin", "support", "sales")
def index():
    """Painel principal do Módulo de Prospecção de Leads."""
    user = current_user() or {}
    user_role = user.get("role", "sales")
    is_admin = (user_role in ("admin", "support"))
    is_seller = not is_admin

    # Apenas Diretoria e Suporte Técnico têm acesso às configurações e ao radar de busca
    active_tab = "capturados" if not is_admin else request.args.get("tab", "capturados")
    nicho_filtro = request.args.get("nicho", "all")
    classe_filtro = request.args.get("classe", "all")
    status_filtro = request.args.get("status", "all")
    filtro_rapido = request.args.get("filtro_rapido", "all")
    termo_busca = request.args.get("busca", "").strip()
    apenas_wa = request.args.get("whatsapp_only") == "1"

    page = max(1, int(request.args.get("page", 1)))
    per_page = 25
    offset = (page - 1) * per_page

    leads, total_leads = listar_leads_capturados(
        nicho_slug=nicho_filtro if nicho_filtro != "all" else None,
        classe=classe_filtro if classe_filtro != "all" else None,
        status_contato=status_filtro if status_filtro != "all" else None,
        termo_busca=termo_busca if termo_busca else None,
        apenas_com_whatsapp=apenas_wa,
        filtro_rapido=filtro_rapido,
        vendedor_id=user.get("id"),
        limit=per_page,
        offset=offset,
    )

    metricas = obter_metricas_resumo()
    nichos = get_all_nichos(apenas_ativos=False)
    default_nicho = nichos[0]["slug"] if nichos else "revenda-motos"
    sheets_url = get_sheets_webhook_url()
    google_sheets_url = get_google_sheets_url()
    apify_token_configured = bool(get_prospector_config("apify_token"))
    total_pages = max(1, (total_leads + per_page - 1) // per_page)
    automacao_cfg = obter_config_automacao()
    module_maintenance = get_module_status("prospeccao")

    return render_template(
        "admin/prospector.html",
        active_tab=active_tab,
        leads=leads,
        total_leads=total_leads,
        page=page,
        total_pages=total_pages,
        metricas=metricas,
        nichos=nichos,
        default_nicho=default_nicho,
        nicho_filtro=nicho_filtro,
        classe_filtro=classe_filtro,
        status_filtro=status_filtro,
        filtro_rapido=filtro_rapido,
        termo_busca=termo_busca,
        apenas_wa=apenas_wa,
        sheets_url=sheets_url,
        google_sheets_url=google_sheets_url,
        apify_configured=apify_token_configured,
        is_seller=is_seller,
        is_admin=is_admin,
        user_role=user_role,
        vendedor_atual=user,
        automacao=automacao_cfg,
        module_maintenance=module_maintenance,
    )


# -------------------------------------------------------------------------
# APIS OPERACIONAIS (AJAX / ALPINES JS)
# -------------------------------------------------------------------------

@prospector_bp.route("/admin/prospeccao/api/buscar", methods=["POST"])
@login_required
@roles_required("admin", "support")
def iniciar_busca():
    """Dispara o processo de prospecção em segundo plano."""
    data = request.get_json(silent=True) or {}
    nicho = data.get("nicho", "").strip()
    praca = data.get("praca", "").strip()
    limite = int(data.get("limite", 10))

    if not nicho or not praca:
        return jsonify({"status": "error", "message": "Nicho e Praça/Cidade são obrigatórios."}), 400

    job_status = obter_status_job()
    if job_status.get("running"):
        return jsonify({"status": "error", "message": "Já existe uma busca em andamento."}), 409

    try:
        executar_prospeccao_assincrona(nicho, praca, limite=limite)
        audit("PROSPECTOR_SEARCH_STARTED", f"Nicho: {nicho}, Praça: {praca}, Limite: {limite}")
        return jsonify({"status": "success", "message": f"Busca iniciada para {nicho} em {praca}!"})
    except Exception as e:
        logger.error("Erro ao iniciar busca: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@prospector_bp.route("/admin/prospeccao/api/status", methods=["GET"])
@login_required
@roles_required("admin", "support")
def status_busca():
    """Consulta o progresso em tempo real da busca ativa."""
    return jsonify({"status": "success", "job": obter_status_job()})


@prospector_bp.route("/admin/prospeccao/api/sync-sheets", methods=["POST"])
@login_required
@roles_required("admin", "support")
def sync_sheets():
    """Aciona a sincronização com a planilha Google Sheets."""
    data = request.get_json(silent=True) or {}
    apenas_pendentes = data.get("apenas_pendentes", True)
    sucesso, msg, count = sincronizar_com_google_sheets(apenas_pendentes=apenas_pendentes)
    if sucesso:
        audit("PROSPECTOR_SHEETS_SYNC", f"Sincronizados {count} leads com sucesso.")
        return jsonify({"status": "success", "message": msg, "count": count})
    return jsonify({"status": "error", "message": msg}), 500


@prospector_bp.route("/admin/prospeccao/export-meta-lookalike", methods=["GET"])
@login_required
@roles_required("admin", "support")
def export_meta():
    """Download do CSV formatado para públicos semelhantes do Meta Ads."""
    csv_data = exportar_csv_meta_lookalike(classes_permitidas=["A", "B", "C"])
    audit("PROSPECTOR_META_LOOKALIKE_EXPORT", "Exportação CSV gerada.")
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=meta_lookalike_leads_maj.csv"}
    )


@prospector_bp.route("/admin/prospeccao/exportar-planilha", methods=["GET"])
@login_required
@roles_required("admin", "support", "sales")
def exportar_planilha_leads():
    """Download da base completa em formato Excel (.xlsx) ou CSV para uso no Google Sheets."""
    import io
    formato = request.args.get("formato", "xlsx").lower()
    audit("PROSPECTOR_EXPORT_SHEETS", f"Formato: {formato}")
    if formato == "csv":
        csv_data = gerar_csv_leads()
        return Response(
            csv_data,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=leads_maj_mobilidade.csv"}
        )

    excel_bytes = gerar_planilha_excel_leads()
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="leads_maj_mobilidade.xlsx"
    )


@prospector_bp.route("/admin/prospeccao/api/google-sheets", methods=["POST"])
@login_required
@roles_required("admin", "support")
def salvar_google_sheets_config():
    """Atualiza o link oficial da planilha e o Webhook do Google Sheets."""
    data = request.get_json(silent=True) or {}
    sheets_url = data.get("google_sheets_url", "").strip()
    webhook_url = data.get("sheets_webhook_url", "").strip()
    if sheets_url:
        set_google_sheets_url(sheets_url)
    if webhook_url:
        set_sheets_webhook_url(webhook_url)
    audit("PROSPECTOR_SHEETS_CONFIG", "Configurações da Planilha atualizadas.")
    return jsonify({
        "status": "success",
        "message": "Configurações da planilha salvas com sucesso!",
        "google_sheets_url": get_google_sheets_url(),
        "sheets_webhook_url": get_sheets_webhook_url(),
    })


@prospector_bp.route("/admin/prospeccao/api/config", methods=["POST"])
@login_required
@roles_required("admin", "support")
def salvar_configuracoes():
    """Salva credenciais e URLs de integração."""
    data = request.get_json(silent=True) or {}
    apify_token = data.get("apify_token", "").strip()
    sheets_url = data.get("sheets_webhook_url", "").strip()

    if apify_token:
        set_prospector_config("apify_token", apify_token, "Token Oficial Apify")
    if sheets_url:
        set_sheets_webhook_url(sheets_url)

    audit("PROSPECTOR_CONFIG_UPDATED", "Credenciais e Webhooks de Prospecção atualizados.")
    return jsonify({"status": "success", "message": "Configurações salvas com sucesso!"})


@prospector_bp.route("/admin/prospeccao/api/nichos", methods=["POST"])
@login_required
@roles_required("admin", "support")
def salvar_nicho():
    """Cadastra ou atualiza um nicho comercial."""
    data = request.get_json(silent=True) or {}
    slug = data.get("slug", "").strip().lower()
    rotulo = data.get("rotulo", "").strip()
    termos = data.get("termos", [])
    pracas = data.get("pracas_sugeridas", [])
    gancho = data.get("gancho_comercial_padrao", "").strip()

    if not slug or not rotulo:
        return jsonify({"status": "error", "message": "Slug e Rótulo são obrigatórios."}), 400

    if isinstance(termos, str):
        termos = [t.strip() for t in termos.split(",") if t.strip()]
    if isinstance(pracas, str):
        pracas = [p.strip() for p in pracas.split(",") if p.strip()]

    with db() as conn:
        conn.execute(
            """
            INSERT INTO prospeccao.nichos (slug, rotulo, termos, pracas_sugeridas, gancho_comercial_padrao, ativo, updated_at)
            VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                rotulo = EXCLUDED.rotulo,
                termos = EXCLUDED.termos,
                pracas_sugeridas = EXCLUDED.pracas_sugeridas,
                gancho_comercial_padrao = EXCLUDED.gancho_comercial_padrao,
                updated_at = NOW();
            """,
            [slug, rotulo, json.dumps(termos), json.dumps(pracas), gancho]
        )
        conn.commit()

    audit("PROSPECTOR_NICHO_SAVED", f"Nicho salvo: {slug}")
    return jsonify({"status": "success", "message": "Nicho cadastrado/atualizado com sucesso!"})


@prospector_bp.route("/admin/prospeccao/api/lead/<lead_id>", methods=["GET"])
@login_required
@roles_required("admin", "support", "sales")
def detalhe_lead(lead_id: str):
    """Retorna a ficha completa de um lead para exibição no modal."""
    with db() as conn:
        row = conn.execute("SELECT * FROM prospeccao.leads WHERE id = %s::uuid", [lead_id]).fetchone()
        if not row:
            return jsonify({"status": "error", "message": "Lead não encontrado."}), 404
        return jsonify({"status": "success", "lead": dict(row)})


@prospector_bp.route("/admin/prospeccao/api/lead/<lead_id>/status", methods=["POST"])
@login_required
@roles_required("admin", "support", "sales")
def atualizar_status_lead(lead_id: str):
    """Atualiza o status de contato do lead."""
    data = request.get_json(silent=True) or {}
    novo_status = data.get("status_contato", "novo")
    notas = data.get("notas_comerciais")

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


@prospector_bp.route("/admin/prospeccao/api/lead/<lead_id>/prospectar", methods=["POST"])
@login_required
@roles_required("admin", "support", "sales")
def registrar_prospeccao(lead_id: str):
    """Registra que o vendedor abordou o lead via WhatsApp, salvando histórico."""
    user = current_user() or {}
    data = request.get_json(silent=True) or {}
    mensagem = data.get("mensagem", "").strip()
    vendedor_phone = data.get("vendedor_phone", "").strip()

    # Se o vendedor informou ou atualizou seu WhatsApp, salva em users
    if vendedor_phone and user.get("id"):
        with db() as conn:
            conn.execute("UPDATE users SET phone = %s WHERE id = %s", [vendedor_phone, user.get("id")])
            conn.commit()

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

    audit("LEAD_PROSPECTADO", f"Lead {lead_id} prospectado por {vendedor_nome}")
    return jsonify({
        "status": "success",
        "message": f"Lead marcado como prospectado por {vendedor_nome}!",
        "prospectado_por_nome": vendedor_nome,
        "prospectado_em": "Agora"
    })


@prospector_bp.route("/admin/prospeccao/api/vendedor/phone", methods=["POST"])
@login_required
@roles_required("admin", "support", "sales")
def salvar_telefone_vendedor():
    """Permite ao vendedor salvar ou atualizar seu número de WhatsApp no perfil."""
    user = current_user() or {}
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    if not phone:
        return jsonify({"status": "error", "message": "Telefone inválido."}), 400
    with db() as conn:
        conn.execute("UPDATE users SET phone = %s WHERE id = %s", [phone, user.get("id")])
        conn.commit()
    return jsonify({"status": "success", "message": "WhatsApp salvo com sucesso no seu perfil!"})


# -------------------------------------------------------------------------
# CENTRAL DE AUTOMAÇÃO 24/7 & CRON JOBS
# -------------------------------------------------------------------------

@prospector_bp.route("/admin/prospeccao/api/automacao", methods=["GET"])
@login_required
@roles_required("admin", "support")
def get_automacao_api():
    """Retorna a configuração e telemetria da automação 24/7."""
    return jsonify({"status": "success", "config": obter_config_automacao()})


@prospector_bp.route("/admin/prospeccao/api/automacao", methods=["POST"])
@login_required
@roles_required("admin", "support")
def salvar_automacao_api():
    """Salva a configuração do motor de automação (modo, cidades, limites, status)."""
    data = request.get_json(silent=True) or {}
    salvar_config_automacao(data)
    audit("PROSPECTOR_AUTOMACAO_SALVA", f"Modo: {data.get('modo')}, Ativo: {data.get('ativo')}")
    return jsonify({"status": "success", "message": "Diretrizes de automação gravadas com sucesso!", "config": obter_config_automacao()})


@prospector_bp.route("/admin/prospeccao/api/automacao/executar-agora", methods=["POST"])
@login_required
@roles_required("admin", "support")
def executar_agora_automacao_api():
    """Força um ciclo manual imediato no carrossel da automação."""
    res = executar_ciclo_automacao(forcar=True)
    audit("PROSPECTOR_AUTOMACAO_DISPARO_MANUAL", f"Resultado: {res.get('message')}")
    return jsonify(res)


@prospector_bp.route("/cron/prospector-sync", methods=["GET", "POST"])
@prospector_bp.route("/api/cron/prospector-sync", methods=["GET", "POST"])
@prospector_bp.route("/admin/prospeccao/cron-sync", methods=["GET", "POST"])
def cron_prospector_sync():
    """Endpoint chamado automaticamente por Vercel Cron ou cron local."""
    forcar = request.args.get("forcar") == "1"
    res = executar_ciclo_automacao(forcar=forcar)
    return jsonify(res)

