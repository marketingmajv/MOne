"""
M-One Internal Analysis Service (services/internal_analysis_service.py)
Gerencia a Análise Interna das entregas semanais dos colaboradores para a reunião de Diretoria.
Fluxo em 2 etapas: Curadoria Estratégica de Fauzer (Staging) -> Liberação Oficial para Jam & Geysa.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.employee_reports_service import _is_pg, ensure_reports_schema, get_cycle_submissions_summary
from services.gemini_client import execute_gemini_payload

logger = logging.getLogger(__name__)
_INTERNAL_ANALYSIS_SCHEMA_READY = False


def ensure_internal_analysis_schema() -> None:
    """Garante a tabela maj_cycle_internal_analyses para persistência da Análise Interna."""
    global _INTERNAL_ANALYSIS_SCHEMA_READY
    if _INTERNAL_ANALYSIS_SCHEMA_READY:
        return
    ensure_reports_schema()
    with db() as conn:
        pg = _is_pg(conn)
        create_sql = """CREATE TABLE IF NOT EXISTS maj_cycle_internal_analyses (
            id SERIAL PRIMARY KEY,
            cycle_id INTEGER NOT NULL UNIQUE,
            status VARCHAR(30) DEFAULT 'curating',
            ai_summary_json TEXT,
            curated_data_json TEXT,
            meeting_decisions_json TEXT,
            curated_by VARCHAR(50),
            published_at TIMESTAMP WITHOUT TIME ZONE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );""" if pg else """CREATE TABLE IF NOT EXISTS maj_cycle_internal_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER NOT NULL UNIQUE,
            status TEXT DEFAULT 'curating',
            ai_summary_json TEXT,
            curated_data_json TEXT,
            meeting_decisions_json TEXT,
            curated_by TEXT,
            published_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        try:
            conn.executescript(create_sql)
            conn.commit()
            _INTERNAL_ANALYSIS_SCHEMA_READY = True
        except Exception as e:
            logger.warning(f"Erro ao criar tabela maj_cycle_internal_analyses: {e}")


def get_internal_analysis(cycle_id: int) -> Dict[str, Any]:
    """Recupera a Análise Interna de um ciclo específico."""
    ensure_internal_analysis_schema()
    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        cur = conn.execute(
            f"SELECT * FROM maj_cycle_internal_analyses WHERE cycle_id = {placeholder} LIMIT 1",
            (cycle_id,)
        )
        row = cur.fetchone()
        if not row:
            return {}
        data = dict(row)
        for key in ["ai_summary_json", "curated_data_json", "meeting_decisions_json"]:
            raw = data.get(key)
            if isinstance(raw, str) and raw:
                try:
                    data[key.replace("_json", "")] = json.loads(raw)
                except Exception:
                    data[key.replace("_json", "")] = {}
            else:
                data[key.replace("_json", "")] = raw if isinstance(raw, (dict, list)) else {}

        # Sincroniza deliberações da reunião ao vivo com curated_data.pauta_decisoes para nunca perder status após reload
        decisions_saved = data.get("meeting_decisions")
        curated = data.get("curated_data")
        if isinstance(decisions_saved, list) and decisions_saved and isinstance(curated, dict):
            base_decs = curated.get("pauta_decisoes") or []
            if isinstance(base_decs, list) and base_decs:
                saved_by_id = {d.get("id"): d for d in decisions_saved if isinstance(d, dict) and d.get("id")}
                for idx, dec in enumerate(base_decs):
                    if not isinstance(dec, dict):
                        continue
                    match = saved_by_id.get(dec.get("id"))
                    if not match and idx < len(decisions_saved) and isinstance(decisions_saved[idx], dict):
                        if decisions_saved[idx].get("title") == dec.get("title"):
                            match = decisions_saved[idx]
                    if match:
                        dec["status"] = match.get("status", dec.get("status", "pending"))
                        dec["deliberacao_texto"] = match.get("deliberacao_texto", dec.get("deliberacao_texto", ""))

        return data


def save_or_init_internal_analysis(
    cycle_id: int,
    status: str = "curating",
    ai_summary: Optional[Dict[str, Any]] = None,
    curated_data: Optional[Dict[str, Any]] = None,
    meeting_decisions: Optional[List[Dict[str, Any]]] = None,
    curated_by: Optional[str] = None,
    published: bool = False
) -> Dict[str, Any]:
    """Salva ou atualiza a Análise Interna de um ciclo."""
    ensure_internal_analysis_schema()
    now = datetime.now()
    existing = get_internal_analysis(cycle_id)

    final_status = "published" if published else (status or existing.get("status") or "curating")
    final_curated_by = curated_by or existing.get("curated_by") or "fauzer"
    final_published_at = now if (published and not existing.get("published_at")) else existing.get("published_at")

    final_ai = ai_summary if ai_summary is not None else existing.get("ai_summary", {})
    final_curated = curated_data if curated_data is not None else existing.get("curated_data", final_ai)
    final_decisions = meeting_decisions if meeting_decisions is not None else existing.get("meeting_decisions", [])

    ai_json = json.dumps(final_ai, ensure_ascii=False) if final_ai else "{}"
    curated_json = json.dumps(final_curated, ensure_ascii=False) if final_curated else "{}"
    decisions_json = json.dumps(final_decisions, ensure_ascii=False) if final_decisions else "[]"

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        if existing and existing.get("id"):
            sql = f"""
                UPDATE maj_cycle_internal_analyses
                SET status = {placeholder},
                    ai_summary_json = {placeholder},
                    curated_data_json = {placeholder},
                    meeting_decisions_json = {placeholder},
                    curated_by = {placeholder},
                    published_at = {placeholder},
                    updated_at = {placeholder}
                WHERE cycle_id = {placeholder}
            """
            conn.execute(sql, (final_status, ai_json, curated_json, decisions_json, final_curated_by, final_published_at, now, cycle_id))
        else:
            sql = f"""
                INSERT INTO maj_cycle_internal_analyses
                (cycle_id, status, ai_summary_json, curated_data_json, meeting_decisions_json, curated_by, published_at, created_at, updated_at)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """
            conn.execute(sql, (cycle_id, final_status, ai_json, curated_json, decisions_json, final_curated_by, final_published_at, now, now))
        conn.commit()

    return get_internal_analysis(cycle_id)


def generate_ai_internal_analysis(cycle_id: int) -> Dict[str, Any]:
    """
    Executa a síntese de IA (Gemini) cruzando os relatórios do ciclo em foco
    com os ciclos anteriores como linha de base (Relatório dos Relatórios Comparativo).
    """
    from services.internal_analysis_ai_service import execute_comparative_synthesis
    return execute_comparative_synthesis(cycle_id)


def _generate_fallback_synthesis(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Gera síntese estruturada caso o modelo demore ou falhe."""
    cycle = summary.get("cycle", {})
    return {
        "executive_summary": f"Análise interna das entregas do {cycle.get('title', 'Ciclo Semanal')}. Total de {summary.get('total_submitted', 0)} relatórios recebidos com foco em alinhamento de diretoria.",
        "radar_alerts": [
            {
                "id": "alert_fallback_1",
                "pilar": "oficina",
                "pilar_label": "Oficina & Peças",
                "severity": "high",
                "title": "Necessidade de Peças e Liberação de OS na Oficina",
                "description": "Ricardo reportou necessidade de reposição de componentes críticos para evitar acúmulo de motos paradas no pátio.",
                "envolvidos": ["Ricardo", "Jhon"]
            },
            {
                "id": "alert_fallback_2",
                "pilar": "estoque",
                "pilar_label": "Estoque & Pátio",
                "severity": "medium",
                "title": "Auditoria da Contagem Rotativa de Sexta-feira",
                "description": "Conferência semanal física no Galpão MAJ para saneamento de divergências de chassis e baterias.",
                "envolvidos": ["Jhon"]
            }
        ],
        "pauta_decisoes": [
            {
                "id": "dec_fallback_1",
                "pilar": "oficina",
                "title": "Aprovação de Compra Emergencial de Peças",
                "context": "Peças faltantes atrasando prazos de entrega acordados com clientes finais.",
                "proposta": "Jam e Geysa deliberam se aprovam compra pontual no fornecedor local ou se aguardam remessa de fábrica.",
                "status": "pending",
                "deliberacao_texto": ""
            },
            {
                "id": "dec_fallback_2",
                "pilar": "financeiro",
                "title": "Validação das Contas Operacionais da Semana",
                "context": "Marisa repassou as contas vencidas e a vencer para liberação pela Gerência Geral.",
                "proposta": "Geysa autoriza os pagamentos prioritários da semana.",
                "status": "pending",
                "deliberacao_texto": ""
            }
        ],
        "pilares": {
            "financeiro": {
                "titulo": "Financeiro & Faturamento",
                "responsavel": "Marisa",
                "destaques": ["Emissão de notas fiscais regulares e fechamento de caixa diário."],
                "pontos_atencao": ["Canhotos e comprovantes pendentes de retorno."]
            },
            "estoque": {
                "titulo": "Estoque & Galpões",
                "responsavel": "Jhon",
                "destaques": ["Contagem de estoque realizada às sextas-feiras."],
                "pontos_atencao": ["Divergências pontuais sob investigação."]
            },
            "oficina": {
                "titulo": "Oficina & Pós-Venda",
                "responsavel": "Ricardo & Léo",
                "destaques": ["Manutenções preventivas e triagem de pós-venda em andamento."],
                "pontos_atencao": ["Aguardando peças de reposição específicas."]
            },
            "comercial": {
                "titulo": "Comercial & Atacado",
                "responsavel": "Luiza, Gabriel & Gustavo",
                "destaques": ["Atendimentos ativos na loja, WhatsApp e prospecção B2B."],
                "pontos_atencao": ["Objeções sobre formas de parcelamento e frete."]
            },
            "marketing_sistemas": {
                "titulo": "Marketing & Sistemas",
                "responsavel": "Fauzer",
                "destaques": ["Operação de tráfego pago, GMB e atualizações do M-One em dia."],
                "pontos_atencao": ["Monitoramento de tempo de 1ª resposta no funil."]
            }
        }
    }


def seed_demo_simulation_cycle(cycle_id: int) -> Dict[str, Any]:
    """Popula respostas de teste realistas para os 7 colaboradores no ciclo para Fauzer validar no fim de semana."""
    from services.employee_reports_service import save_or_submit_report

    demo_answers = {
        "marisa": {
            "faturamento_nfs": "Faturamento de R$ 184.200,00 na semana (14 NFs no atacado para revendas de Linhares e Cachoeiro; 7 vendas de varejo showroom).",
            "entradas_pendentes": "2 boletos de atacado vencidos na quinta (Revenda Capixaba), cliente prometeu pagar até segunda 12h. Caixa físico diário com Jhon fechado sem divergências.",
            "contas_vencimentos": "Encaminhadas 7 contas para Geysa (internet, energia do galpão M-One, frete e embalagens) totalizando R$ 11.230,00.",
            "docs_faltantes": "Falta canhoto de frete da transportadora referente ao lote de São Mateus.",
            "recibos_pendentes": "Todos os recibos da semana foram anexados na pasta financeira.",
            "piloto_mercado_pago": "Semana com R$ 42.600,00 transacionados na maquininha Point Pro da loja. Taxa líquida média em 3.2%. Jam precisa aprovar expansão.",
            "prioridades_proxima_semana": "Fechamento mensal e conciliação de extrato com Bling."
        },
        "jhon": {
            "contagem_rotativa": "Contagem física de sexta-feira concluída no Galpão MAJ e Galpão M-One: 218 motos em estoque físico.",
            "divergencias": "Detectada divergência de 1 unidade modelo X15 Pro (estava no sistema como pronta entrega, mas estava na oficina em teste com Ricardo). Já alinhado com Ricardo.",
            "nfs_demonstracao": "Emitida NF de remessa para feira de eventos em Vitória (2 motos).",
            "codigo_barras": "100% dos novos lotes de peças e motos etiquetados com código de barras.",
            "organizacao_galpao": "Setor A (pronta entrega) e Setor B (motos aguardando PDI) devidamente sinalizados.",
            "prioridades_proxima_semana": "Recebimento do novo caminhão de peças previsto para quarta-feira."
        },
        "ricardo": {
            "servicos_concluidos": "Liberadas 14 motos na semana (9 revisões de 1000km, 3 manutenções elétricas e 2 trocas de controladora).",
            "os_pendentes": "4 motos paradas no pátio com OS atrasada há mais de 4 dias por falta de baterias 60V e cabos conectores no estoque.",
            "retrabalhos": "1 retrabalho de freio a disco traseiro resolvido sem custo adicional ao cliente.",
            "defeitos_recorrentes": "Conector do display da Max 12 tem apresentado oxidação rápida em uso com chuva intensa.",
            "necessidade_pecas": "Urgente pedido de 10 baterias 60V 20Ah e 15 manetes de freio.",
            "prioridades_proxima_semana": "Zerar a fila das 4 motos paradas assim que as peças chegarem."
        },
        "luiza": {
            "modelos_procurados": "Maior procura da semana: Max 12 (70% dos contatos) e Citycoco 2000W.",
            "objecoes_perdas": "Principal motivo de perda: cliente achando a taxa de parcelamento em 12x alta ou pedindo entrada parcelada.",
            "precos_altos": "Clientes comparando preço da X15 com concorrentes de entrada no Mercado Livre.",
            "sugestao_comercial": "Criar campanha de entrada facilitada no cartão para o final de semana.",
            "prioridades_proxima_semana": "Follow-up na base de 45 leads mornos do WhatsApp."
        },
        "leo": {
            "atendimentos_realizados": "82 atendimentos pelo WhatsApp e 16 presenciais na loja Consolação.",
            "vendas_fechadas": "Fechadas 6 vendas de varejo e 2 no atacado.",
            "modelos_mais_procurados": "Max 12 branca e cinza nardo.",
            "objecoes_e_desistencias": "Dúvida sobre suporte e facilidade de achar peças de reposição em caso de quebra.",
            "clientes_em_negociacao": "8 clientes com proposta enviada aguardando fechamento até terça.",
            "sugestoes_comerciais": "Disponibilizar vídeo institucional de 30 segundos mostrando o estoque de peças da oficina para passar segurança aos clientes indecisos.",
            "prioridades_proxima_semana": "Fechamento dos 8 clientes quentes da carteira."
        },
        "gabriel": {
            "lojistas_contatados": "34 revendas e lojistas contatados no interior do RJ e Minas Gerais.",
            "pedidos_fechados": "2 pedidos fechados de 5 unidades cada (Revenda Juiz de Fora e Campos).",
            "objecoes_b2b": "Lojistas solicitando prazo de 30/60 dias para pagamento no boleto.",
            "modelos_mais_pedidos_b2b": "Max 12 e scooter de carga.",
            "feedbacks_concorrencia": "Concorrentes dando frete grátis acima de 10 unidades para capitais.",
            "prioridades_proxima_semana": "Viagem para prospecção presencial de 6 lojas no sul do ES."
        },
        "fauzer": {
            "marketing_investimento": "Investimento de R$ 3.850,00 no Meta Ads. CPL médio atingiu R$ 6,80 (ótima performance). 566 leads gerados.",
            "processos_sistemas": "M-One atualizado com novo módulo de Gestão Interna, Análise Interna automatizada e catálogos customizados para atacado.",
            "falhas_desvios": "Identificada lentidão no primeiro contato do comercial pelo BotConversa em horários de pico (meio-dia).",
            "pontos_decisao_diretoria": "1) Aprovação da compra emergencial de baterias para a oficina; 2) Decisão sobre frete bonificado para atacado acima de 10 motos; 3) Validação do piloto Mercado Pago.",
            "prioridades_proxima_semana": "Otimizar funil do BotConversa e consolidar o painel de vendas no M-One."
        }
    }

    for key, ans in demo_answers.items():
        save_or_submit_report(
            cycle_id=cycle_id,
            user_id=1,
            employee_key=key,
            answers=ans,
            is_draft=False
        )

    # Executa a síntese de IA sobre os dados simulados
    return generate_ai_internal_analysis(cycle_id)
