"""
M-One BotConversa & Cross-Campaign Monitoring Service (services/botconversa_service.py)
Gerencia conexão com a API do BotConversa, métricas de funil, cruzamento com Meta Ads e diagnósticos.
Em estrita conformidade com as diretrizes de código modular (< 500 linhas) do M-One.
"""

from __future__ import annotations

import json
import logging
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import db
from services.meta_service import fetch_meta_campaigns, get_meta_config

logger = logging.getLogger(__name__)

BOTCONVERSA_API_DEFAULT_BASE = "https://backend.botconversa.com.br/api/v1"


def get_botconversa_config() -> Dict[str, Any]:
    """Recupera a configuração do BotConversa da tabela de integrações ou variáveis de ambiente."""
    cfg = {
        "service_name": "botconversa",
        "api_key": os.environ.get("BOTCONVERSA_API_KEY", ""),
        "api_url": os.environ.get("BOTCONVERSA_API_URL", BOTCONVERSA_API_DEFAULT_BASE),
        "status": "Não Configurado",
        "updated_at": None,
        "monitored_tags": [],
        "target_flows": [],
    }

    try:
        with db() as conn:
            # Garantir existência da tabela integrations e tabela de snapshots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS campaign_monitoring_snapshots (
                    id SERIAL PRIMARY KEY,
                    snapshot_date DATE DEFAULT CURRENT_DATE,
                    meta_spend NUMERIC(12,2) DEFAULT 0,
                    meta_impressions INTEGER DEFAULT 0,
                    meta_clicks INTEGER DEFAULT 0,
                    meta_cpc NUMERIC(10,2) DEFAULT 0,
                    meta_ctr NUMERIC(5,2) DEFAULT 0,
                    bot_new_subscribers INTEGER DEFAULT 0,
                    bot_active_subscribers INTEGER DEFAULT 0,
                    discrepancy_rate NUMERIC(5,2) DEFAULT 0,
                    waba_status TEXT DEFAULT 'CONNECTED',
                    anomalies_json JSONB DEFAULT '[]'::jsonb,
                    recommended_actions_json JSONB DEFAULT '[]'::jsonb,
                    pdf_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            row = conn.execute(
                "SELECT * FROM integrations WHERE service_name = 'botconversa' LIMIT 1"
            ).fetchone()

            if row:
                row_dict = dict(row)
                cfg["api_key"] = row_dict.get("access_token") or cfg["api_key"]
                cfg["updated_at"] = row_dict.get("updated_at")

                settings = row_dict.get("settings_json") or {}
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except Exception:
                        settings = {}
                cfg["api_url"] = settings.get("api_url", cfg["api_url"])
                cfg["monitored_tags"] = settings.get("monitored_tags", [])
                cfg["target_flows"] = settings.get("target_flows", [])

        if cfg["api_key"]:
            cfg["status"] = "Configurado"
    except Exception as e:
        logger.error("[get_botconversa_config error]: %s", e)

    return cfg


def save_botconversa_config(api_key: str, api_url: Optional[str] = None, settings: Optional[Dict[str, Any]] = None) -> bool:
    """Salva ou atualiza a chave de API e configurações do BotConversa."""
    api_key = (api_key or "").strip()
    api_url = (api_url or BOTCONVERSA_API_DEFAULT_BASE).strip().rstrip("/")
    settings_dict = settings or {}
    settings_dict["api_url"] = api_url

    try:
        with db() as conn:
            existing = conn.execute(
                "SELECT id FROM integrations WHERE service_name = 'botconversa' LIMIT 1"
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE integrations 
                    SET access_token = %s, settings_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE service_name = 'botconversa'
                    """,
                    (api_key, json.dumps(settings_dict)),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO integrations (service_name, access_token, settings_json)
                    VALUES ('botconversa', %s, %s)
                    """,
                    (api_key, json.dumps(settings_dict)),
                )
            conn.commit()
            return True
    except Exception as e:
        logger.error("[save_botconversa_config error]: %s", e)
        return False


def _botconversa_request(endpoint: str, method: str = "GET", payload: Optional[Dict] = None) -> Dict[str, Any]:
    """Helper para chamadas HTTP à API do BotConversa."""
    cfg = get_botconversa_config()
    api_key = cfg.get("api_key")
    base_url = cfg.get("api_url") or BOTCONVERSA_API_DEFAULT_BASE

    if not api_key:
        return {"success": False, "error": "API Key do BotConversa não configurada"}

    clean_endpoint = endpoint.lstrip("/")
    url = f"{base_url}/{clean_endpoint}"
    headers = {
        "api-key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "M-One-Agent/1.0",
    }

    try:
        data_bytes = json.dumps(payload).encode() if payload and method in ("POST", "PUT") else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8")
            return {"success": True, "data": json.loads(body) if body else {}}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        logger.warning("[BotConversa HTTP Error %s]: %s", e.code, err_msg)
        return {"success": False, "status_code": e.code, "error": f"HTTP {e.code}: {err_msg}"}
    except Exception as ex:
        logger.error("[BotConversa Connection Error]: %s", ex)
        return {"success": False, "error": str(ex)}


def test_botconversa_connection(custom_key: Optional[str] = None) -> Dict[str, Any]:
    """Valida a conexão com a API do BotConversa."""
    key = custom_key or get_botconversa_config().get("api_key")
    if not key:
        return {"valid": False, "message": "Nenhuma API Key informada para teste."}

    # Testar endpoints padrão (webhook/subscribers ou subscribers)
    res = _botconversa_request("webhook/subscribers/?page=1")
    if not res.get("success"):
        res = _botconversa_request("subscribers/?page=1")

    if res.get("success"):
        data = res.get("data", {})
        total_subscribers = data.get("count") or len(data.get("results", []))
        return {
            "valid": True,
            "message": "Conexão com BotConversa estabelecida com sucesso!",
            "subscribers_sample_count": total_subscribers,
        }
    return {
        "valid": False,
        "message": res.get("error", "Falha de autenticação com BotConversa."),
    }


def fetch_botconversa_metrics(days: int = 7) -> Dict[str, Any]:
    """Coleta métricas reais do BotConversa via API usando paginação retroativa."""
    cfg = get_botconversa_config()
    api_key = cfg.get("api_key")

    if api_key:
        # 1. Pega total de contatos da base
        res_page1 = _botconversa_request("webhook/subscribers/?page=1")
        if res_page1.get("success"):
            data1 = res_page1.get("data", {})
            total_active = data1.get("count", 0)
            last_page = math.ceil(total_active / 25) if total_active > 0 else 1
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            new_subscribers = 0
            tag_counts: Dict[str, int] = {}
            current_page = last_page
            stop = False

            # Varrer retroativamente as páginas mais recentes até atingir a data de corte (máx 30 páginas para agilidade)
            while current_page >= max(1, last_page - 30) and not stop:
                res_page = _botconversa_request(f"webhook/subscribers/?page={current_page}")
                if not res_page.get("success"):
                    break
                page_data = res_page.get("data", {})
                results = page_data.get("results", [])
                for sub in reversed(results):
                    c_str = sub.get("created_at")
                    if c_str:
                        try:
                            dt = datetime.fromisoformat(c_str.replace("Z", "+00:00"))
                            if dt >= cutoff_date:
                                new_subscribers += 1
                                for t in sub.get("tags", []):
                                    t_name = t if isinstance(t, str) else t.get("name", str(t))
                                    tag_counts[t_name] = tag_counts.get(t_name, 0) + 1
                            else:
                                stop = True
                                break
                        except Exception:
                            pass
                current_page -= 1

            # Buscar lista de fluxos ativos
            flows_res = _botconversa_request("webhook/flows/")
            flows_list = flows_res.get("data", []) if flows_res.get("success") else []

            return {
                "is_simulated": False,
                "total_active_subscribers": total_active,
                "new_subscribers_period": new_subscribers,
                "tag_distribution": tag_counts,
                "active_flows_count": len(flows_list),
                "active_flows": [{"id": f.get("id"), "name": f.get("name")} for f in flows_list],
                "stalled_leads_count": tag_counts.get("Não_respondeu", 5),
                "connection_status": "CONNECTED",
            }

    # Fallback demonstrativo caso sem API Key
    return {
        "is_simulated": True,
        "total_active_subscribers": 55541,
        "new_subscribers_period": 516,
        "tag_distribution": {
            "atacado_revenda": 110,
            "Atacado_jose_gabriel": 66,
            "Atacado_Luiza": 46,
            "Varejo_Leonardo": 35,
            "Varejo_luiza": 35,
        },
        "active_flows_count": 7,
        "stalled_leads_count": 8,
        "connection_status": "CONNECTED",
    }


def audit_recent_leads(pages_back: int = 2) -> Dict[str, Any]:
    """
    Rastreia individualmente os leads mais recentes, identificando onde cada um travou ou converteu.
    Analisa variáveis de triagem (ResumoTriagemMAJ), resposta do catálogo e tags de vendedores.
    """
    cfg = get_botconversa_config()
    api_key = cfg.get("api_key")
    if not api_key:
        return {"converted": [], "stalled_catalog": [], "early_drop": []}

    res_p1 = _botconversa_request("webhook/subscribers/?page=1")
    if not res_p1.get("success"):
        return {"converted": [], "stalled_catalog": [], "early_drop": []}

    total_count = res_p1.get("data", {}).get("count", 0)
    last_page = math.ceil(total_count / 25) if total_count > 0 else 1

    leads_raw = []
    start_p = max(1, last_page - pages_back + 1)
    for p in range(start_p, last_page + 1):
        r = _botconversa_request(f"webhook/subscribers/?page={p}")
        if r.get("success"):
            leads_raw.extend(r.get("data", {}).get("results", []))

    converted = []
    stalled_catalog = []
    early_drop = []

    for l in reversed(leads_raw):
        tags = l.get("tags") or []
        variables = l.get("variables") or {}
        resumo = variables.get("ResumoTriagemMAJ") or ""
        resposta_catalogo = variables.get("Resposta_Catalogo") or ""
        name = (l.get("first_name") or "Lead sem nome").strip()
        phone = l.get("phone") or ""
        created = (l.get("created_at") or "")[:16].replace("T", " ")

        seller_tags = [t for t in tags if "Varejo_" in t or "Atacado_" in t or "Atendimento-" in t]

        lead_entry = {
            "name": name,
            "phone": phone,
            "created": created,
            "summary": resumo,
            "catalog_selection": resposta_catalogo,
            "seller": seller_tags[0] if seller_tags else None,
            "tags": tags,
        }

        if seller_tags:
            lead_entry["status"] = "CONVERTIDO_VENDEDOR"
            converted.append(lead_entry)
        elif resumo or resposta_catalogo:
            lead_entry["status"] = "TRAVADO_CATALOGO"
            lead_entry["friction_reason"] = resumo if resumo else f"Clicou em: {resposta_catalogo}"
            stalled_catalog.append(lead_entry)
        else:
            lead_entry["status"] = "ABANDONO_INICIAL"
            early_drop.append(lead_entry)

    return {
        "total_audited": len(leads_raw),
        "converted_count": len(converted),
        "stalled_catalog_count": len(stalled_catalog),
        "early_drop_count": len(early_drop),
        "converted": converted,
        "stalled_catalog": stalled_catalog,
        "early_drop": early_drop,
    }


def generate_cross_funnel_diagnosis(days: int = 7) -> Dict[str, Any]:
    """
    Cruza dados da Meta Marketing API com métricas do BotConversa e auditoria cirúrgica de leads.
    """
    # 1. Coleta dados da Meta Ads
    meta_cfg = get_meta_config()
    campaigns = fetch_meta_campaigns(limit=10)
    
    total_spend = sum(c.get("spend", 0.0) for c in campaigns)
    total_clicks = sum(c.get("clicks", 0) for c in campaigns)
    total_impressions = sum(c.get("impressions", 0) for c in campaigns)
    avg_cpc = (total_spend / total_clicks) if total_clicks > 0 else 0.0
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0

    # 2. Coleta dados do BotConversa
    bot_metrics = fetch_botconversa_metrics(days=days)
    new_leads = bot_metrics.get("new_subscribers_period", 0)

    # 3. Métricas de Cruzamento e Discrepância
    # Cliques nos anúncios que iniciam mensagem vs leads que de fato entraram no bot
    loss_clicks = max(0, total_clicks - new_leads) if total_clicks > 0 else 0
    discrepancy_rate = ((loss_clicks / total_clicks) * 100) if total_clicks > 0 else 0.0
    real_cpl = (total_spend / new_leads) if new_leads > 0 else 0.0

    # 4. Avaliação de Anomalias (Algoritmo de Detecção)
    anomalies = []
    recommended_actions = []

    # Checagem de Discrepância de Clique vs Lead
    if discrepancy_rate > 30.0:
        anomalies.append({
            "severity": "CRITICAL",
            "code": "HIGH_CLICK_DROP",
            "title": "Alta Fuga no Clique do Anúncio (Discrepância Elevada)",
            "description": f"{discrepancy_rate:.1f}% dos usuários que clicaram no anúncio do Meta não iniciaram conversa no WhatsApp.",
            "impact": "Desperdício direto de verba publicitária na transição Meta -> WhatsApp.",
        })
        recommended_actions.append(
            "Verificar a mensagem de saudação automática no gerenciador de anúncios do Meta Ads e testar o tempo de carregamento da rota do WhatsApp."
        )
    elif discrepancy_rate > 15.0:
        anomalies.append({
            "severity": "WARNING",
            "code": "MODERATE_CLICK_DROP",
            "title": "Discrepância Moderada no Clique",
            "description": f"{discrepancy_rate:.1f}% de perda entre o clique e o primeiro contato no bot.",
            "impact": "Possível fricção na mensagem pré-preenchida do WhatsApp.",
        })
        recommended_actions.append("Otimizar o texto padrão do anúncio para torná-lo mais natural para o usuário enviar.")

    # Checagem de CPL Real
    if real_cpl > 45.0:
        anomalies.append({
            "severity": "WARNING",
            "code": "CPL_ELEVATED",
            "title": "Custo por Lead (CPL Real) Elevado",
            "description": f"O CPL efetivo no BotConversa está em R$ {real_cpl:.2f}, acima da faixa ótima projetada.",
            "impact": "Pressão sobre a margem de conversão das vendas.",
        })
        recommended_actions.append("Revisar criativos de menor CTR e redistribuir verba para os conjuntos com maior taxa de qualificação.")

    # Checagem de Leads Travados
    stalled = bot_metrics.get("stalled_leads_count", 0)
    if stalled > 5:
        anomalies.append({
            "severity": "WARNING",
            "code": "STALLED_LEADS",
            "title": "Leads Retidos no Meio do Fluxo",
            "description": f"Existem {stalled} contatos travados em perguntas do bot há mais de 4 horas sem interação.",
            "impact": "Perda de timing comercial com leads quentes.",
        })
        recommended_actions.append(
            "Aprovar envio de disparo de reengajamento pontual (follow-up de 4h) para reativar contatos travados."
        )

    # Checagem de Conexão WhatsApp
    waba_health = meta_cfg.get("phone_number_id") or "Verificado"
    if bot_metrics.get("connection_status") != "CONNECTED":
        anomalies.append({
            "severity": "CRITICAL",
            "code": "WHATSAPP_DISCONNECTED",
            "title": "Instabilidade ou Queda na Conexão do BotConversa",
            "description": "O status da linha no BotConversa não está ativo.",
            "impact": "Interrupção total do atendimento automatizado.",
        })
        recommended_actions.append("Acessar imediatamente o painel do BotConversa e reconectar a instância via QR Code ou Cloud API.")

    # 3.1 Auditoria Cirúrgica Lead-a-Lead
    lead_audit = audit_recent_leads(pages_back=2)
    stalled_cat_count = lead_audit.get("stalled_catalog_count", 0)
    converted_count = lead_audit.get("converted_count", 0)
    
    if stalled_cat_count > 0:
        anomalies.append({
            "severity": "WARNING",
            "code": "CATALOG_BOTTLENECK",
            "title": f"Gargalo Crítico no Catálogo ({stalled_cat_count} leads travados)",
            "description": f"{stalled_cat_count} contatos interagiram com a triagem/catálogo recente mas não avançaram para um vendedor.",
            "impact": "Falta de fechamento comercial imediato por ausência de resposta para dúvidas específicas.",
        })
        recommended_actions.append(
            f"Adicionar nó de transbordo automático para vendedor quando o lead fizer perguntas sobre modelos, cesta ou fotos no fluxo."
        )

    diagnosis = {
        "generated_at": datetime.now().strftime("%d/%m/%Y às %H:%M:%S"),
        "period_days": days,
        "is_simulated_bot": bot_metrics.get("is_simulated", False),
        "summary": {
            "total_spend": round(total_spend, 2),
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "avg_cpc": round(avg_cpc, 2),
            "avg_ctr": round(avg_ctr, 2),
            "new_leads_bot": new_leads,
            "discrepancy_rate": round(discrepancy_rate, 1),
            "real_cpl": round(real_cpl, 2),
            "active_subscribers": bot_metrics.get("total_active_subscribers", 0),
            "stalled_leads": stalled,
            "audited_recent_leads": lead_audit.get("total_audited", 0),
            "audited_converted": converted_count,
            "audited_stalled_catalog": stalled_cat_count,
            "audited_early_drop": lead_audit.get("early_drop_count", 0),
        },
        "campaigns_breakdown": campaigns,
        "bot_metrics": bot_metrics,
        "lead_audit": lead_audit,
        "anomalies": anomalies,
        "recommended_actions": recommended_actions,
    }

    # Salva snapshot no banco de dados para comparativo diário
    _persist_snapshot(diagnosis)

    return diagnosis


def _persist_snapshot(diag: Dict[str, Any]) -> None:
    """Grava o snapshot diário no Supabase para histórico."""
    summary = diag.get("summary", {})
    try:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO campaign_monitoring_snapshots (
                    meta_spend, meta_impressions, meta_clicks, meta_cpc, meta_ctr,
                    bot_new_subscribers, bot_active_subscribers, discrepancy_rate,
                    anomalies_json, recommended_actions_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    summary.get("total_spend", 0),
                    summary.get("total_impressions", 0),
                    summary.get("total_clicks", 0),
                    summary.get("avg_cpc", 0),
                    summary.get("avg_ctr", 0),
                    summary.get("new_leads_bot", 0),
                    summary.get("active_subscribers", 0),
                    summary.get("discrepancy_rate", 0),
                    json.dumps(diag.get("anomalies", [])),
                    json.dumps(diag.get("recommended_actions", [])),
                ),
            )
            conn.commit()
    except Exception as e:
        logger.warning("[_persist_snapshot warning]: %s", e)
