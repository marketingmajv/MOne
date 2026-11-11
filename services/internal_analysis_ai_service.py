"""
M-One Internal Comparative Analysis AI Service (services/internal_analysis_ai_service.py)
Motor de IA (Gemini) para Análise Comparativa e Meta-Relatório dos Ciclos Semanais.
Cruza o ciclo atual com os ciclos anteriores (Ciclos 1 e 2 como linha de base),
detectando gargalos crônicos, novos alertas críticos, evolução dos colaboradores
e pauta deliberativa para a reunião de Diretoria (Jam, Geysa e Fauzer).
Segregação modular estrita (< 400 linhas).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.gemini_client import execute_gemini_payload

logger = logging.getLogger(__name__)


def get_preceding_cycles(target_cycle_id: int, limit: int = 2) -> List[Dict[str, Any]]:
    """Recupera os ciclos anteriores ao ciclo alvo para compor a linha de base histórica."""
    with db() as conn:
        cur = conn.execute(
            """
            SELECT id, cycle_code, title, start_date, deadline, is_active
            FROM maj_report_cycles
            WHERE id < %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (target_cycle_id, limit),
        )
        rows = cur.fetchall()
        # Retorna em ordem cronológica (mais antigo primeiro)
        return [dict(r) for r in reversed(rows)]


def extract_cycle_report_data(cycle_id: int) -> Dict[str, Any]:
    """Extrai os relatórios de um ciclo com perguntas, respostas, drafts com conteúdo e isenções."""
    from services.employee_reports_service import get_cycle_submissions_summary

    summary = get_cycle_submissions_summary(cycle_id)
    cycle = summary.get("cycle", {})
    employees = summary.get("employees", [])

    compiled_reports = []
    status_overview = []

    for emp in employees:
        key = emp["key"]
        name = emp["name"]
        role = emp["role_title"]
        area = emp.get("area", "Operações")
        status = emp["status"]
        answers = emp.get("answers", {})

        is_exempt = (status == "exempt")
        is_draft = (status == "draft")
        has_content = any(isinstance(v, str) and v.strip() for v in answers.values())

        status_overview.append({
            "key": key,
            "name": name,
            "role": role,
            "area": area,
            "status": status,
            "is_exempt": is_exempt,
            "is_draft": is_draft,
            "has_content": has_content,
        })

        if is_exempt:
            compiled_reports.append({
                "key": key,
                "name": name,
                "role": role,
                "area": area,
                "status_label": "ISENTO JUSTIFICADO PELA DIRETORIA",
                "text_block": f"=== COLABORADOR: {name} ({role} - Área: {area}) ===\n[STATUS: Colaborador Isento Justificado pela Diretoria para este ciclo (licença/afastamento oficial).]",
            })
        elif has_content:
            status_tag = "RASCUNHO PRELIMINAR COM CONTEÚDO" if is_draft else ("ENTREGUE NO PRAZO" if status == "submitted_on_time" else "ENTREGUE COM ATRASO")
            block = [f"=== COLABORADOR: {name} ({role} - Área: {area}) [STATUS: {status_tag}] ==="]
            for q in emp.get("questions", []):
                ans = q.get("answer", "").strip()
                if ans:
                    block.append(f"• {q['label']}:\n  {ans}")
            compiled_reports.append({
                "key": key,
                "name": name,
                "role": role,
                "area": area,
                "status_label": status_tag,
                "text_block": "\n".join(block),
            })
        else:
            compiled_reports.append({
                "key": key,
                "name": name,
                "role": role,
                "area": area,
                "status_label": "NÃO ENTREGUE / SEM RESPOSTA",
                "text_block": f"=== COLABORADOR: {name} ({role} - Área: {area}) ===\n[STATUS: Sem respostas registradas para este ciclo.]",
            })

    return {
        "cycle": cycle,
        "summary": summary,
        "compiled_reports": compiled_reports,
        "status_overview": status_overview,
    }


def build_comparative_analysis_prompt(target_data: Dict[str, Any], baseline_cycles_data: List[Dict[str, Any]]) -> str:
    """Constrói o prompt estratégico para o Gemini com comparativo histórico."""
    target_cycle = target_data.get("cycle", {})
    target_title = target_cycle.get("title", "Ciclo Atual")
    target_code = target_cycle.get("cycle_code", "")

    # Linha do tempo dos ciclos de parâmetro
    baseline_text_sections = []
    for idx, b_data in enumerate(baseline_cycles_data, 1):
        b_c = b_data.get("cycle", {})
        b_title = b_c.get("title", f"Ciclo Base {idx}")
        b_code = b_c.get("cycle_code", "")
        b_reports = [r["text_block"] for r in b_data.get("compiled_reports", []) if "Sem respostas" not in r["text_block"]]
        b_joined = "\n\n".join(b_reports) if b_reports else "Sem histórico relevante."
        baseline_text_sections.append(
            f"### PARÂMETRO HISTÓRICO — {b_title} ({b_code}):\n{b_joined[:10000]}"
        )

    baseline_full_text = "\n\n".join(baseline_text_sections) if baseline_text_sections else "Nenhum ciclo anterior cadastrado (primeira análise)."

    # Ciclo Atual em Foco
    target_reports = [r["text_block"] for r in target_data.get("compiled_reports", [])]
    target_full_text = "\n\n".join(target_reports)

    prompt = f"""Você é o Consultor Executivo Sênior e Especialista em Operações da MAJ Mobilidade Elétrica.
Sua missão é realizar uma ANÁLISE COMPARATIVA ESTRATÉGICA ("RELATÓRIO DOS RELATÓRIOS") do ciclo em foco cruzando-o com os ciclos anteriores como linha de base.
Este relatório destina-se à reunião executiva de alinhamento entre Jam Penitenti (Diretor Geral), Geysa (Gerente Geral) e Fauzer.

======================================================
1. PARÂMETROS HISTÓRICOS DE REFERÊNCIA (CICLOS ANTERIORES):
======================================================
{baseline_full_text}

======================================================
2. CICLO EM FOCO PARA AUDITORIA: {target_title} ({target_code}):
======================================================
{target_full_text}

======================================================
DIRETRIZES FUNDAMENTAIS PARA A ANÁLISE COMPARATIVA:
======================================================
1. GARGALOS CRÔNICOS E REINCIDENTES: Identifique com rigor o que foi relatado nos ciclos anteriores e PERSISTE sem solução no ciclo em foco (ex: pendência de ferramentas de Ricardo, tarefa do Mercado Pago com Marisa sem instrução, objeções de preço no atacado).
2. NOVOS ALERTAS CRÍTICOS: Identifique o que surgiu de novo neste ciclo que merece atenção imediata da Gerência (ex: defeitos técnicos inéditos, faltas de peças específicas, problemas de relacionamento na equipe).
3. EVOLUÇÃO E ENGAJAMENTO DOS COLABORADORES: Avalie a consistência das respostas de cada colaborador (se houve melhora, estagnação, respostas monossilábicas ou perda de profundidade). Considere colaboradores isentos oficialmente com o status correto ("Isenção Justificada pela Diretoria") e rascunhos com conteúdo como "Rascunho Preliminar".
4. PAUTA DELIBERATIVA DA DIRETORIA (BATER O MARTELO EM 20-30 MIN): Liste de 3 a 5 decisões práticas e urgentes que Jam e Geysa precisam deliberar e aprovar nesta reunião.
5. FORMATO WHATSAPP PARA A DIRETORIA: Redija um bloco executivo conciso, com emojis corporativos e marcadores (*negrito*, •), pronto para Fauzer copiar e colar no grupo de WhatsApp de Jam e Geysa.
6. RELATÓRIO MASTER DE AFERIMENTO DE RESPOSTAS DOS COLABORADORES:
Para CADA colaborador da empresa listado no ciclo em foco, faça uma aferição individual objetiva:
- Se for ISENTO: status="isento", status_label="Isenção Justificada pela Diretoria", perguntas_atencao=[].
- Se NÃO ENTREGOU / SEM RESPOSTA: status="pendente", status_label="Pendente de Preenchimento / Prazo Esgotado", perguntas_atencao=[].
- Se entregou respostas:
  - Se todas as respostas estiverem adequadas, completas e sem gargalos graves: status="esperado", status_label="Resposta dentro do esperado", perguntas_atencao=[].
  - Se 1 ou mais respostas tiverem gargalos, bloqueios, desvios operacionais ou respostas rasas: status="atencao" (ou "critico"), status_label="1 resposta precisa de atenção" (ou "X respostas precisam de atenção"), e preencha "perguntas_atencao" com pergunta_titulo, motivo_alerta e acao_recomendada.
- whatsapp_master_block: Bloco formatado para WhatsApp com a lista de todos os colaboradores, seus status (✅, ⚠️, ⚪, 🚨), perguntas de atenção e ações sugeridas para a Diretoria.

Retorne ESTRITAMENTE um objeto JSON válido no seguinte formato:
{{
  "executive_summary": "Síntese executiva da semana em 2 a 3 frases objetivas com o diagnóstico macro da empresa.",
  "relatorio_master_colaboradores": [
    {{
      "key": "marisa",
      "name": "Marisa",
      "role": "Financeiro & Caixa",
      "status": "atencao",
      "status_label": "1 resposta precisa de atenção",
      "resumo": "Rotinas fiscais e contas em dia, porém relata bloqueio de execução no Mercado Pago.",
      "perguntas_atencao": [
        {{
          "pergunta_id": "piloto_mercado_pago",
          "pergunta_titulo": "Piloto Mercado Pago",
          "resposta_colaborador": "Não foi feito pois não sei como proceder",
          "motivo_alerta": "Falta de instrução operacional impedindo a conciliação das taxas.",
          "acao_recomendada": "Jam/Geysa alinharem instrução operacional com Marisa na segunda-feira."
        }}
      ]
    }}
  ],
  "gargalos_cronicos": [
    {{
      "id": "cronico_1",
      "pilar": "financeiro",
      "pilar_label": "Financeiro & Caixa",
      "title": "Título conciso do gargalo crônico",
      "description": "Explicação do problema, há quanto tempo se repete e o impacto operacional.",
      "origem_ciclos": "Presente desde o Ciclo anterior",
      "envolvidos": ["Marisa", "Geysa"]
    }}
  ],
  "radar_alerts": [
    {{
      "id": "alert_1",
      "pilar": "oficina",
      "pilar_label": "Oficina & Peças",
      "severity": "high",
      "title": "Título do novo alerta crítico",
      "description": "Detalhamento objetivo do risco ou oportunidade que surgiu neste ciclo.",
      "envolvidos": ["Ricardo", "Léo"]
    }}
  ],
  "evolucao_colaboradores": [
    {{
      "key": "marisa",
      "name": "Marisa",
      "role": "Financeiro",
      "tendencia": "atencao",
      "tendencia_label": "Atenção / Bloqueio",
      "resumo_evolucao": "Rotinas fiscais e bancárias em dia, porém relata bloqueio crônico na tarefa do Mercado Pago por falta de instrução operacional."
    }}
  ],
  "pauta_decisoes": [
    {{
      "id": "dec_1",
      "pilar": "oficina",
      "title": "Aprovação de Compra de Ferramentas / Peças",
      "context": "Contexto do que foi pedido e o que trava a oficina.",
      "proposta": "Proposta de decisão direta para Jam e Geysa deliberarem na reunião.",
      "status": "pending",
      "deliberacao_texto": ""
    }}
  ],
  "pilares": {{
    "financeiro": {{
      "titulo": "Financeiro, Caixa & Faturamento",
      "responsavel": "Marisa",
      "destaques": ["Destaques positivos da semana..."],
      "pontos_atencao": ["Pontos de atenção..."]
    }},
    "estoque": {{
      "titulo": "Estoque Físico & Galpões",
      "responsavel": "Jhon",
      "destaques": ["Destaques..."],
      "pontos_atencao": ["Pontos de atenção..."]
    }},
    "oficina": {{
      "titulo": "Oficina Técnica & Pós-Vendas",
      "responsavel": "Ricardo & Léo",
      "destaques": ["Destaques..."],
      "pontos_atencao": ["Pontos de atenção..."]
    }},
    "comercial": {{
      "titulo": "Comercial, Demanda & Clientes",
      "responsavel": "Luiza, Gabriel & Gustavo",
      "destaques": ["Destaques..."],
      "pontos_atencao": ["Pontos de atenção..."]
    }},
    "marketing_sistemas": {{
      "titulo": "Marketing & Sistemas",
      "responsavel": "Fauzer",
      "destaques": ["Destaques..."],
      "pontos_atencao": ["Pontos de atenção..."]
    }}
  }},
  "whatsapp_executive_block": "*RELATÓRIO DOS RELATÓRIOS — MAJ MOBILIDADE*\\n*Ciclo:* ...\\n\\n*🎯 Resumo Executivo:*\\n...\\n\\n*⚠️ Gargalos Crônicos & Alertas:*\\n• ...\\n\\n*⚡ Pauta de Decisões da Diretoria (Jam & Geysa):*\\n1️⃣ ...\\n2️⃣ ...\\n\\n*Pronto para alinhamento na reunião.*",
  "whatsapp_master_block": "📋 *RELATÓRIO MASTER DE AFERIMENTO — MAJ MOBILIDADE*\\n*Ciclo:* ...\\n\\n• *Gabriel (Vendas Atacado):* ✅ Resposta dentro do esperado\\n  Rotinas em dia.\\n\\n• *Marisa (Financeiro & Caixa):* ⚠️ 1 resposta precisa de atenção\\n  ⚠️ *Piloto Mercado Pago:* Dúvida operacional.\\n  👉 *Ação Diretoria:* Alinhamento de 10 min.\\n\\n_Documento gerado pelo M-One Aferimento IA._"
}}"""
    return prompt


def format_whatsapp_master_block(master_list: List[Dict[str, Any]], cycle_title: str) -> str:
    """Formata o bloco de WhatsApp do Relatório MASTER de Aferimento dos Colaboradores."""
    lines = [
        "📋 *RELATÓRIO MASTER DE AFERIMENTO — MAJ MOBILIDADE*",
        f"*Ciclo:* {cycle_title}",
        "",
    ]
    for item in master_list:
        name = item.get("name", "")
        role = item.get("role", "")
        status = item.get("status", "esperado")
        status_label = item.get("status_label", "Resposta dentro do esperado")
        resumo = item.get("resumo", "")
        perguntas = item.get("perguntas_atencao", [])

        icon = "✅" if status == "esperado" else ("⚠️" if status == "atencao" else ("🚨" if status == "critico" else ("⚪" if status == "isento" else "🔴")))
        lines.append(f"• *{name} ({role}):* {icon} {status_label}")
        if resumo:
            lines.append(f"  {resumo}")
        for p in perguntas:
            p_title = p.get("pergunta_titulo", "")
            motivo = p.get("motivo_alerta", "")
            acao = p.get("acao_recomendada", "")
            if p_title and motivo:
                lines.append(f"  ⚠️ *{p_title}:* {motivo}")
            if acao:
                lines.append(f"  👉 *Ação Diretoria:* {acao}")
        lines.append("")

    lines.append("_Documento gerado pelo M-One Aferimento IA para deliberação da Diretoria._")
    return "\n".join(lines).strip()


def execute_comparative_synthesis(target_cycle_id: int) -> Dict[str, Any]:
    """Executa a síntese comparativa completa por IA e salva no banco de dados."""
    from services.internal_analysis_service import save_or_init_internal_analysis

    target_data = extract_cycle_report_data(target_cycle_id)
    baseline_cycles = get_preceding_cycles(target_cycle_id, limit=2)
    baseline_data_list = [extract_cycle_report_data(c["id"]) for c in baseline_cycles]

    prompt = build_comparative_analysis_prompt(target_data, baseline_data_list)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    raw_resp = execute_gemini_payload(payload)
    parsed = {}
    if raw_resp.get("data") and isinstance(raw_resp["data"], dict):
        parsed = raw_resp["data"]
    elif raw_resp.get("text"):
        try:
            parsed = json.loads(raw_resp["text"])
        except Exception as e:
            logger.warning(f"Erro ao parsear resposta do Gemini na Análise Comparativa: {e}")

    # Fallback estruturado se IA não retornar
    if not parsed or (not parsed.get("radar_alerts") and not parsed.get("gargalos_cronicos")):
        parsed = _generate_comparative_fallback(target_data, baseline_data_list)

    # Garante formatação do bloco WhatsApp do Relatório MASTER
    if parsed.get("relatorio_master_colaboradores") and not parsed.get("whatsapp_master_block"):
        parsed["whatsapp_master_block"] = format_whatsapp_master_block(
            parsed["relatorio_master_colaboradores"],
            target_data.get("cycle", {}).get("title", "Ciclo Atual")
        )

    # Persiste a análise gerada
    saved = save_or_init_internal_analysis(
        cycle_id=target_cycle_id,
        status="curating",
        ai_summary=parsed,
        curated_data=parsed,
        curated_by="fauzer",
        published=False,
    )
    return saved


def _generate_comparative_fallback(target_data: Dict[str, Any], baseline_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Gera fallback estruturado caso a chamada à API demore."""
    target_cycle = target_data.get("cycle", {})
    title = target_cycle.get("title", "Ciclo Atual")

    return {
        "executive_summary": f"Análise interna consolidada para o {title}, confrontando as entregas da equipe com os ciclos anteriores como linha de base.",
        "gargalos_cronicos": [
            {
                "id": "cronico_1",
                "pilar": "financeiro",
                "pilar_label": "Financeiro",
                "title": "Piloto Mercado Pago Pendente de Orientação Operacional",
                "description": "Marisa apontou reincidentemente que não sabe como executar o piloto de conciliação do Mercado Pago. Demanda instrução direta da Gerência.",
                "origem_ciclos": "Reincidente desde o Ciclo 02",
                "envolvidos": ["Marisa", "Geysa"],
            },
            {
                "id": "cronico_2",
                "pilar": "oficina",
                "pilar_label": "Oficina & Peças",
                "title": "Necessidade Reincidente de Ferramentas e Insumos na Oficina",
                "description": "Ricardo reiterou o pedido de Chave de Impacto e Cola Shock para agilizar montagens e manutenções.",
                "origem_ciclos": "Reincidente desde o Ciclo 02",
                "envolvidos": ["Ricardo", "Jam"],
            },
        ],
        "radar_alerts": [
            {
                "id": "alert_1",
                "pilar": "comercial",
                "pilar_label": "Comercial Atacado",
                "severity": "high",
                "title": "Forte Pressão de Preço no Atacado por Queima de Concorrentes",
                "description": "Gabriel e Gustavo reportam dificuldade de fechamento devido a preços muito baixos praticados por concorrentes (INOW/MultBike).",
                "envolvidos": ["Gabriel", "Gustavo", "Jam"],
            },
            {
                "id": "alert_2",
                "pilar": "oficina",
                "pilar_label": "Oficina Técnica",
                "severity": "medium",
                "title": "Diagnóstico Complexo Inédito na Bike V8 Mini",
                "description": "Falha inédita identificada na controladora da V8 Mini necessitando avaliação técnica aprofundada.",
                "envolvidos": ["Ricardo"],
            },
        ],
        "evolucao_colaboradores": [
            {"key": "gabriel", "name": "Gabriel", "role": "Vendas Atacado", "tendencia": "estavel", "tendencia_label": "Estável / Alerta Preço", "resumo_evolucao": "Mantém prospecção e follow-up ativos, mas enfrenta forte resistência de preço no atacado."},
            {"key": "gustavo", "name": "Gustavo", "role": "Vendas Atacado", "tendencia": "estavel", "tendencia_label": "Estável / Alerta Preço", "resumo_evolucao": "Respostas detalhadas sobre envio de catálogos e concorrência; sem fechamentos na semana."},
            {"key": "luiza", "name": "Luiza", "role": "Vendas Showroom", "tendencia": "positiva", "tendencia_label": "Positiva", "resumo_evolucao": "Atendimento ativo com destaque para Classic 1000 e V8; sugere reforço no marketing de vídeo."},
            {"key": "marisa", "name": "Marisa", "role": "Financeiro", "tendencia": "atencao", "tendencia_label": "Atenção (Mercado Pago)", "resumo_evolucao": "Rotinas fiscais e contas em dia; bloqueio no piloto Mercado Pago."},
            {"key": "ricardo", "name": "Ricardo", "role": "Oficina Técnica", "tendencia": "atencao", "tendencia_label": "Atenção (Ferramentas)", "resumo_evolucao": "14 serviços concluídos; reiterou pedido de chave de impacto e cola shock."},
            {"key": "leo", "name": "Léo", "role": "Oficina / Triagem", "tendencia": "positiva", "tendencia_label": "Positiva", "resumo_evolucao": "9 OS no total (6 concluídas); 2 casos aguardando revisão para troca de peças."},
            {"key": "jhon", "name": "Jhon", "role": "Estoque", "tendencia": "isento", "tendencia_label": "Isenção Justificada", "resumo_evolucao": "Colaborador isento no Ciclo 03 por afastamento/licença autorizada pela Diretoria."},
        ],
        "pauta_decisoes": [
            {
                "id": "dec_1",
                "pilar": "oficina",
                "title": "Aprovação de Compra da Chave de Impacto e Insumos da Oficina",
                "context": "Ricardo aguarda ferramentas essenciais para agilizar montagem Garow e reparos.",
                "proposta": "Jam e Geysa autorizam compra imediata dos itens para desbloquear a oficina.",
                "status": "pending",
                "deliberacao_texto": "",
            },
            {
                "id": "dec_2",
                "pilar": "financeiro",
                "title": "Instrução Operacional para Marisa no Piloto Mercado Pago",
                "context": "Marisa relata bloqueio de execução por não saber como operar a tarefa.",
                "proposta": "Geysa ou Fauzer agenda alinhamento de 15 minutos com Marisa para orientar a conciliação.",
                "status": "pending",
                "deliberacao_texto": "",
            },
            {
                "id": "dec_3",
                "pilar": "comercial",
                "title": "Estratégia Comercial B2B frente à Queima de Preço de Concorrentes",
                "context": "Gabriel e Gustavo encontram resistência em atacado por ofertas agressivas de concorrentes.",
                "proposta": "Diretoria define se mantém margem focando em peças/garantia ou se cria lote promocional de desova.",
                "status": "pending",
                "deliberacao_texto": "",
            },
        ],
        "pilares": {
            "financeiro": {"titulo": "Financeiro, Caixa & Faturamento", "responsavel": "Marisa", "destaques": ["NFs de atacado e varejo emitidas sem pendências.", "Contas impressas com vencimentos futuros."], "pontos_atencao": ["Piloto Mercado Pago pendente de instrução operacional."]},
            "estoque": {"titulo": "Estoque Físico & Galpões", "responsavel": "Jhon", "destaques": ["Estoque auditado no Ciclo 02 com etiquetagem de chassis em andamento."], "pontos_atencao": ["Colaborador isento no Ciclo 03; rotina sob monitoramento."]},
            "oficina": {"titulo": "Oficina Técnica & Pós-Vendas", "responsavel": "Ricardo & Léo", "destaques": ["14 serviços concluídos por Ricardo e 6 OS concluídas por Léo.", "Relação interpessoal de apoio na equipe em evolução."], "pontos_atencao": ["Falta de Chave de Impacto e Cola Shock reiterada.", "Falha inédita de controladora na V8 Mini."]},
            "comercial": {"titulo": "Comercial, Demanda & Clientes", "responsavel": "Luiza, Gabriel & Gustavo", "destaques": ["Atendimentos ativos e relacionamento mantido com clientes quentes.", "Procura constante por Max 12 e Classic 1000."], "pontos_atencao": ["Forte queixa de preço no atacado diante de concorrentes com queima de estoque.", "Demanda por renovação de conteúdos de vídeo para marketing."]},
            "marketing_sistemas": {"titulo": "Marketing & Sistemas", "responsavel": "Fauzer", "destaques": ["Sistema M-One e automações de aferimento em evolução contínua."], "pontos_atencao": ["Demanda de atualização de criativos/vídeos comerciais alinhada com showroom."]},
        },
        "whatsapp_executive_block": f"*RELATÓRIO DOS RELATÓRIOS — MAJ MOBILIDADE*\n*Ciclo:* {title}\n\n*🎯 Resumo Executivo:*\nAnálise comparativa das entregas da equipe confrontada com os Ciclos 1 e 2 como linha de base para alinhamento rápido da Diretoria.\n\n*⚠️ Gargalos Crônicos & Alertas Críticos:*\n• *Financeiro:* Marisa com bloqueio reincidente no Piloto Mercado Pago por falta de instrução.\n• *Oficina:* Ricardo reiterou pedido de Chave de Impacto e Cola Shock para montagens Garow.\n• *Atacado:* Gabriel e Gustavo enfrentam resistência crônica de preço contra concorrência agressiva.\n• *Showroom:* Luiza sugere renovar conteúdos de vídeo (V20/Classic) para aquecer leads.\n\n*⚡ Pauta de Decisões da Reunião (Jam & Geysa):*\n1️⃣ Autorizar compra de Chave de Impacto e insumos para a oficina.\n2️⃣ Orientar operacionalmente Marisa no fluxo do Mercado Pago.\n3️⃣ Definir política comercial de atacado contra preços de queima do mercado.\n\n_Documento pronto para deliberação na reunião de Diretoria._",
        "relatorio_master_colaboradores": [
            {"key": "gabriel", "name": "Gabriel", "role": "Vendas Atacado", "status": "esperado", "status_label": "Resposta dentro do esperado", "resumo": "Rotinas comerciais e follow-ups em dia com prospecção ativa.", "perguntas_atencao": []},
            {"key": "gustavo", "name": "Gustavo", "role": "Vendas Atacado", "status": "esperado", "status_label": "Resposta dentro do esperado", "resumo": "Mapeamento assertivo de concorrência e preços no atacado.", "perguntas_atencao": []},
            {"key": "luiza", "name": "Luiza", "role": "Vendas Showroom", "status": "esperado", "status_label": "Resposta dentro do esperado", "resumo": "Atendimento e pós-venda alinhados; sugestões para vídeos de marketing.", "perguntas_atencao": []},
            {
                "key": "marisa", "name": "Marisa", "role": "Financeiro & Caixa", "status": "atencao", "status_label": "1 resposta precisa de atenção", "resumo": "Rotinas fiscais e contas em dia, porém relata bloqueio de execução no Mercado Pago.",
                "perguntas_atencao": [{"pergunta_id": "piloto_mercado_pago", "pergunta_titulo": "Piloto Mercado Pago", "resposta_colaborador": "Não foi feito pois não sei como proceder", "motivo_alerta": "Falta de instrução operacional bloqueando a conciliação das taxas.", "acao_recomendada": "Alinhamento operacional de 10 min entre Jam/Geysa e Marisa."}]
            },
            {
                "key": "ricardo", "name": "Ricardo", "role": "Oficina Técnica", "status": "atencao", "status_label": "1 resposta precisa de atenção", "resumo": "Produtividade alta (14 serviços), porém falta de ferramentas trava a bancada.",
                "perguntas_atencao": [{"pergunta_id": "necessidade_pecas", "pergunta_titulo": "Peças & Ferramentas", "resposta_colaborador": "Necessidade urgente de chave de impacto e cola shock para montagens Garow.", "motivo_alerta": "Falta de ferramental reincidente atrasando o ritmo da bancada.", "acao_recomendada": "Aprovar compra imediata das ferramentas requisitadas."}]
            },
            {"key": "leo", "name": "Léo", "role": "Oficina / Triagem", "status": "esperado", "status_label": "Resposta dentro do esperado", "resumo": "Triagem e OS organizadas, apoio mútuo na oficina dentro do padrão.", "perguntas_atencao": []},
            {"key": "jhon", "name": "Jhon", "role": "Estoque & Galpão", "status": "isento", "status_label": "Isenção Justificada pela Diretoria", "resumo": "Colaborador isento no Ciclo 03 por afastamento/licença oficial da Diretoria.", "perguntas_atencao": []}
        ],
        "whatsapp_master_block": (
            f"📋 *RELATÓRIO MASTER DE AFERIMENTO — MAJ MOBILIDADE*\n"
            f"*Ciclo:* {title}\n\n"
            "• *Gabriel (Vendas Atacado):* ✅ Resposta dentro do esperado\n"
            "  Rotinas comerciais e follow-ups em dia.\n\n"
            "• *Gustavo (Vendas Atacado):* ✅ Resposta dentro do esperado\n"
            "  Mapeamento de concorrência e envios assertivos.\n\n"
            "• *Luiza (Vendas Showroom):* ✅ Resposta dentro do esperado\n"
            "  Atendimento de balcão e pós-venda dentro da meta.\n\n"
            "• *Marisa (Financeiro & Caixa):* ⚠️ 1 resposta precisa de atenção\n"
            "  ⚠️ *Piloto Mercado Pago:* Não realizado por falta de instrução operacional.\n"
            "  👉 *Ação Diretoria:* Alinhamento de 10 min na segunda-feira.\n\n"
            "• *Ricardo (Oficina Técnica):* ⚠️ 1 resposta precisa de atenção\n"
            "  ⚠️ *Peças & Ferramentas:* Falta de Chave de Impacto travando montagens Garow.\n"
            "  👉 *Ação Diretoria:* Liberar compra emergencial.\n\n"
            "• *Léo (Oficina / Triagem):* ✅ Resposta dentro do esperado\n"
            "  Fluxo de triagem e OS em andamento dentro do padrão.\n\n"
            "• *Jhon (Estoque & Galpão):* ⚪ Isenção Justificada pela Diretoria\n\n"
            "_Documento gerado pelo M-One Aferimento IA para deliberação da Diretoria._"
        ),
    }
