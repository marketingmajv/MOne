"""
M-One Employee Reports Briefing Service (services/employee_reports_briefing_service.py)
Monta o briefing executivo consolidado para a reunião de diretoria da MAJ Mobilidade (Jam + Geysa + Fauzer).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def get_monday_consolidation_briefing(cycle_id: int, summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Monta o briefing executivo consolidado para a reunião de segunda-feira (Jam + Geysa + Fauzer)."""
    if summary is None:
        from services.employee_reports_service import get_cycle_submissions_summary
        summary = get_cycle_submissions_summary(cycle_id)

    emp_map = {e["key"]: e for e in summary.get("employees", [])}

    # Organização por frentes críticas da reunião
    front_defs = [
        ("1. Faturamento, Caixa & Conciliação", "Marisa", "FINANCEIRO", "green", "marisa", [
            ("Faturamento Relevante", "faturamento_nfs"), ("Entradas Pendentes", "entradas_pendentes"),
            ("Contas para Geysa", "contas_vencimentos"), ("Piloto Mercado Pago", "piloto_mercado_pago")
        ]),
        ("2. Estoque Físico, Galpões & Divergências", "Jhon", "ESTOQUE", "amber", "jhon", [
            ("Contagem de Sexta", "contagem_rotativa"), ("Divergências Investigadas", "divergencias"),
            ("NFs de Demonstração", "nfs_demonstracao"), ("Código de Barras", "codigo_barras")
        ]),
        ("3. Oficina Técnica, Produtividade & Falhas", "Ricardo", "OFICINA", "cyan", "ricardo", [
            ("Serviços Liberados", "servicos_concluidos"), ("OS Atrasadas / Pendentes", "os_pendentes"),
            ("Retrabalhos", "retrabalhos"), ("Defeitos Recorrentes", "defeitos_recorrentes"), ("Peças & Ferramentas", "necessidade_pecas")
        ]),
        ("4. Voz do Cliente, Vendas & Objeções", "Luiza, Gabriel & Gustavo", "COMERCIAL", "emerald", "luiza", [
            ("Modelos Mais Procurados", "modelos_procurados"), ("Objeções Comerciais", "objecoes_perdas"),
            ("Preços Considerados Altos", "precos_altos"), ("Sugestão da Semana", "sugestao_comercial")
        ]),
        ("5. Vendas, Atendimentos & Negociações", "Léo", "VENDAS & ATENDIMENTO", "emerald", "leo", [
            ("Atendimentos Realizados", "atendimentos_realizados"), ("Vendas Concluídas", "vendas_fechadas"),
            ("Modelos Procurados", "modelos_mais_procurados"), ("Objeções / Desistências", "objecoes_e_desistencias"),
            ("Clientes em Negociação", "clientes_em_negociacao"), ("Sugestões Comerciais", "sugestoes_comerciais")
        ]),
        ("6. Sistemas, Marketing & Desvios de Processo", "Fauzer", "SISTEMAS", "purple", "fauzer", [
            ("Marketing & CPL", "marketing_investimento"), ("Sistemas & Bling/M-One", "processos_sistemas"),
            ("Falhas & Desvios", "falhas_desvios"), ("Decisões para Jam & Geysa", "pontos_decisao_diretoria")
        ]),
    ]
    critical_fronts = []
    for title, owner, badge, color, emp_key, fields in front_defs:
        emp = emp_map.get(emp_key, {})
        ans = emp.get("answers", {})
        critical_fronts.append({
            "front_title": title, "owner": owner, "badge": badge, "badge_color": color,
            "employee_data": emp_map.get(emp_key),
            "key_highlights": [{"label": lbl, "answer": ans.get(fld)} for lbl, fld in fields]
        })

    return {
        "cycle": summary["cycle"],
        "deadline_str": summary["deadline_str"],
        "summary": summary,
        "fronts": critical_fronts,
    }
