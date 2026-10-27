"""
M-One Employee Report Dispatch Service (services/employee_report_dispatch_service.py)
Serviço especializado na geração, normalização e formatação dos 4 relatórios executivos de alinhamento:
1. Devolutiva de Feedback ao Colaborador
2. Pauta de Demandas do Jam Penitenti
3. Pauta de Demandas da Geysa
4. Pauta de Demandas de Sistemas & Processos do Fauzer
Também provê a consolidação global de demandas de toda a equipe para a Diretoria no ciclo.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def normalize_question_actions(raw_comment: Any) -> Dict[str, Any]:
    """
    Normaliza a estrutura de ações por pergunta de forma 100% retrocompatível.
    Suporta strings legadas salvas na reunião de hoje e o novo formato de objeto estruturado.
    """
    default_structure = {
        "acknowledged": False,
        "employee_feedback": "",
        "demand_jam": "",
        "demand_geysa": "",
        "demand_fauzer": "",
    }

    if not raw_comment:
        return default_structure

    if isinstance(raw_comment, dict):
        return {
            "acknowledged": bool(raw_comment.get("acknowledged", False)),
            "employee_feedback": str(raw_comment.get("employee_feedback") or "").strip(),
            "demand_jam": str(raw_comment.get("demand_jam") or "").strip(),
            "demand_geysa": str(raw_comment.get("demand_geysa") or "").strip(),
            "demand_fauzer": str(raw_comment.get("demand_fauzer") or "").strip(),
        }

    # Tratamento de string legada (ex: registros feitos na reunião anterior)
    text = str(raw_comment).strip()
    low = text.lower()
    res = dict(default_structure)

    if any(k in low for k in ["registrado", "ok", "conferido", "comunicado", "ciente"]):
        res["acknowledged"] = True

    if "[fauzer" in low or "(fauzer)" in low:
        res["demand_fauzer"] = text
    elif "[jam" in low or "(jam)" in low or "jam ciente" in low:
        res["demand_jam"] = text
    elif "[geysa" in low or "(geysa)" in low:
        res["demand_geysa"] = text
    else:
        res["employee_feedback"] = text

    return res


def generate_employee_feedback_report(
    employee_name: str,
    role_title: str,
    cycle_name: str,
    triad_questions: List[Dict[str, Any]],
    director_actions: Dict[str, Dict[str, Any]],
    agreements_jam_geysa: str = "",
    agreements_fauzer: str = "",
) -> str:
    """Gera o texto executivo da Devolutiva para envio no WhatsApp do Colaborador."""
    first_name = employee_name.split()[0] if employee_name else "Colaborador"
    lines = [
        "📋 *DEVOLUTIVA DE ALINHAMENTO SEMANAL — MAJ MOBILIDADE*",
        f"👤 *Colaborador:* {employee_name} ({role_title})",
        f"📅 *Ciclo:* {cycle_name}",
        "",
        f"Olá, *{first_name}*! A Diretoria analisou seu relatório semanal. Segue o parecer e orientações:",
        "",
    ]

    has_items = False
    for idx, q in enumerate(triad_questions, start=1):
        q_id = str(q.get("id", ""))
        label = q.get("label", f"Item {idx}")
        act = normalize_question_actions(director_actions.get(q_id))
        ans = (q.get("provided_answer") or "").strip()

        # Inclui o item se houver resposta ou feedback
        if ans or act["employee_feedback"] or act["acknowledged"]:
            has_items = True
            lines.append(f"*{idx}. {label}*")
            if ans:
                short_ans = ans.replace("\n", " ")
                if len(short_ans) > 160:
                    short_ans = short_ans[:157] + "..."
                lines.append(f"📥 *Seu relato:* {short_ans}")

            if act["employee_feedback"]:
                lines.append(f"💬 *Parecer da Gerência:* {act['employee_feedback']}")
            elif act["acknowledged"]:
                lines.append("✅ *Parecer da Gerência:* Registrado e acompanhado pela Diretoria.")
            lines.append("")

    if not has_items:
        lines.append("• Relatório analisado e registrado pela Diretoria.\n")

    if agreements_jam_geysa.strip() or agreements_fauzer.strip():
        lines.append("📌 *Combinados para a Próxima Semana:*")
        if agreements_jam_geysa.strip():
            lines.append(f"• {agreements_jam_geysa.strip()}")
        if agreements_fauzer.strip():
            lines.append(f"• {agreements_fauzer.strip()}")
        lines.append("")

    lines.append("Contamos com seu empenho e excelência contínua! 🚀")
    return "\n".join(lines).strip()


def generate_leader_demand_report(
    leader_name: str,
    leader_role: str,
    leader_key: str,  # "jam", "geysa" ou "fauzer"
    employee_name: str,
    role_title: str,
    cycle_name: str,
    triad_questions: List[Dict[str, Any]],
    director_actions: Dict[str, Dict[str, Any]],
    general_agreement: str = "",
) -> str:
    """Gera a pauta de demandas de um líder específico (Jam, Geysa ou Fauzer)."""
    target_field = f"demand_{leader_key}"
    icon = "👔" if leader_key == "jam" else ("💼" if leader_key == "geysa" else "⚡")

    lines = [
        f"{icon} *PAUTA DE DEMANDAS — {leader_name.upper()}*",
        f"🎯 *Responsável:* {leader_name} ({leader_role})",
        f"👤 *Colaborador Avaliado:* {employee_name} ({role_title})",
        f"📅 *Ciclo:* {cycle_name}",
        "",
        "Ações sob sua responsabilidade atribuídas na reunião de aferição:",
        "",
    ]

    items_found = 0
    for idx, q in enumerate(triad_questions, start=1):
        q_id = str(q.get("id", ""))
        label = q.get("label", f"Item {idx}")
        act = normalize_question_actions(director_actions.get(q_id))
        demand = act.get(target_field, "").strip()
        ans = (q.get("provided_answer") or "").strip()

        if demand:
            items_found += 1
            lines.append(f"*[{items_found}] {label}*")
            lines.append(f"📝 *Ação {leader_name}:* {demand}")
            if ans:
                short_ans = ans.replace("\n", " ")
                if len(short_ans) > 140:
                    short_ans = short_ans[:137] + "..."
                lines.append(f"📥 *Contexto Colaborador:* _{short_ans}_")
            lines.append("")

    if items_found == 0:
        lines.append(f"• Nenhuma demanda individual específica atribuída para {leader_name} neste colaborador.")
        lines.append("")

    if general_agreement.strip():
        lines.append("📌 *Acordos Gerais de Alinhamento da Semana:*")
        lines.append(f"• {general_agreement.strip()}\n")

    return "\n".join(lines).strip()


def generate_all_reports_bundle(
    employee_name: str,
    role_title: str,
    cycle_name: str,
    triad_questions: List[Dict[str, Any]],
    director_actions: Dict[str, Dict[str, Any]],
    agreements_jam_geysa: str = "",
    agreements_fauzer: str = "",
) -> Dict[str, str]:
    """Gera o pacote com os 4 relatórios individuais formatados."""
    return {
        "employee_feedback": generate_employee_feedback_report(
            employee_name=employee_name,
            role_title=role_title,
            cycle_name=cycle_name,
            triad_questions=triad_questions,
            director_actions=director_actions,
            agreements_jam_geysa=agreements_jam_geysa,
            agreements_fauzer=agreements_fauzer,
        ),
        "jam_demands": generate_leader_demand_report(
            leader_name="Jam Penitenti",
            leader_role="Diretoria Comercial & Geral",
            leader_key="jam",
            employee_name=employee_name,
            role_title=role_title,
            cycle_name=cycle_name,
            triad_questions=triad_questions,
            director_actions=director_actions,
            general_agreement=agreements_jam_geysa,
        ),
        "geysa_demands": generate_leader_demand_report(
            leader_name="Geysa",
            leader_role="Gestão Financeira & Loja",
            leader_key="geysa",
            employee_name=employee_name,
            role_title=role_title,
            cycle_name=cycle_name,
            triad_questions=triad_questions,
            director_actions=director_actions,
            general_agreement=agreements_jam_geysa,
        ),
        "fauzer_demands": generate_leader_demand_report(
            leader_name="Fauzer",
            leader_role="Sistemas, Processos & M-One",
            leader_key="fauzer",
            employee_name=employee_name,
            role_title=role_title,
            cycle_name=cycle_name,
            triad_questions=triad_questions,
            director_actions=director_actions,
            general_agreement=agreements_fauzer,
        ),
    }


def get_consolidated_cycle_demands(cycle_id: int) -> Dict[str, Any]:
    """
    Varre todos os relatórios do ciclo e agrupa todas as demandas de Jam, Geysa e Fauzer
    para exibição consolidada na tela principal de Gestão Interna.
    """
    from database import db
    from services.employee_reports_service import _is_pg, get_all_cycles

    all_cycles = get_all_cycles()
    cycle = next((c for c in all_cycles if c.get("id") == cycle_id), None) or {"title": f"Ciclo #{cycle_id}"}
    cycle_title = cycle.get("title", f"Ciclo #{cycle_id}")

    consolidated = {
        "cycle_id": cycle_id,
        "cycle_title": cycle_title,
        "jam": [],
        "geysa": [],
        "fauzer": [],
        "whatsapp_jam": "",
        "whatsapp_geysa": "",
        "whatsapp_fauzer": "",
    }

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        cur = conn.execute(
            f"SELECT employee_key, employee_name, role_title, director_comments_json FROM maj_employee_reports WHERE cycle_id = {placeholder} ORDER BY employee_name ASC",
            (cycle_id,)
        )
        rows = cur.fetchall()

    for r in rows:
        d = dict(r)
        emp_name = d.get("employee_name") or d.get("employee_key", "").capitalize()
        role = d.get("role_title", "")
        raw_json = d.get("director_comments_json") or "{}"
        try:
            comments = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        except Exception:
            comments = {}

        if not isinstance(comments, dict):
            continue

        for q_id, val in comments.items():
            act = normalize_question_actions(val)
            if act["demand_jam"]:
                consolidated["jam"].append({
                    "employee_name": emp_name,
                    "role_title": role,
                    "question_id": q_id,
                    "demand": act["demand_jam"]
                })
            if act["demand_geysa"]:
                consolidated["geysa"].append({
                    "employee_name": emp_name,
                    "role_title": role,
                    "question_id": q_id,
                    "demand": act["demand_geysa"]
                })
            if act["demand_fauzer"]:
                consolidated["fauzer"].append({
                    "employee_name": emp_name,
                    "role_title": role,
                    "question_id": q_id,
                    "demand": act["demand_fauzer"]
                })

    # Incluir Status Geral dos Gestores
    from services.manager_status_service import get_cycle_manager_status_overview
    mgr_overview = get_cycle_manager_status_overview(cycle_id)
    consolidated["status_jam"] = mgr_overview["jam"]
    consolidated["status_geysa"] = mgr_overview["geysa"]
    consolidated["status_fauzer"] = mgr_overview["fauzer"]

    # Formatar WhatsApp consolidado para cada um dos 3 líderes
    def _format_lead(lead_name, lead_icon, lead_key, items, team_statuses):
        lead_lines = [
            f"{lead_icon} *PAUTA CONSOLIDADA DE DEMANDAS — {lead_name.upper()}*",
            f"📅 *{cycle_title}* (Toda a Equipe)",
            "",
        ]

        # Bloco 1: Status Geral dos Colaboradores
        if lead_key == "fauzer":
            lead_lines.append("📊 *PARECER TÉCNICO & SUGESTÕES DE PROCESSOS (FAUZER):*")
        else:
            lead_lines.append(f"📊 *STATUS GERAL DA EQUIPE (AVALIAÇÃO {lead_name.upper()}):*")

        if team_statuses:
            for s in team_statuses:
                badge = s.get("badge_icon", "⚪")
                st_label = s.get("status_label", "Pendente")
                emp = s.get("employee_name", "")
                diag = (s.get("diagnosis") or "").strip()
                if diag:
                    lead_lines.append(f"• *{emp}:* {badge} *{st_label}* — {diag}")
                else:
                    lead_lines.append(f"• *{emp}:* {badge} *{st_label}*")
            lead_lines.append("")
        else:
            lead_lines.append("• Nenhum colaborador avaliado ainda.\n")

        # Bloco 2: Demandas e Ações Atribuídas
        lead_lines.append(f"📝 *DEMANDAS & TAREFAS ATRIBUÍDAS AO {lead_name.upper()} ({len(items)}):*")
        if not items:
            lead_lines.append("• Nenhuma demanda pendente atribuída para esta semana! 🎉\n")
        else:
            for i, it in enumerate(items, 1):
                lead_lines.append(f"*{i}. {it['employee_name']}* ({it['role_title']}):")
                lead_lines.append(f"   📝 {it['demand']}")
                lead_lines.append("")

        return "\n".join(lead_lines).strip()

    consolidated["whatsapp_jam"] = _format_lead("Jam Penitenti", "👔", "jam", consolidated["jam"], mgr_overview["jam"])
    consolidated["whatsapp_geysa"] = _format_lead("Geysa", "💼", "geysa", consolidated["geysa"], mgr_overview["geysa"])
    consolidated["whatsapp_fauzer"] = _format_lead("Fauzer", "⚡", "fauzer", consolidated["fauzer"], mgr_overview["fauzer"])

    return consolidated
