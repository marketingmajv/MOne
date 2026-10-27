"""
M-One Manager Status & Team Diagnosis Service (services/manager_status_service.py)
Gerencia a avaliação de status geral dos colaboradores atribuída pelos gestores:
- Jam Penitenti: Avalia todos os colaboradores sob a ótica comercial, estratégica e geral.
- Geysa: Avalia todos os colaboradores sob a ótica de disciplina operacional, rotina, caixa e prazos.
- Fauzer: Avaliação técnica, opcional e sugestiva para a gerência sobre maturidade de processos, M-One e Bling.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.employee_reports_service import _is_pg, ensure_reports_schema, get_employee_report
from services.gemini_client import execute_gemini_payload

logger = logging.getLogger(__name__)

STATUS_CONFIG = {
    "aligned": {"label": "Alinhado", "badge": "🟢", "color": "#00e599"},
    "attention": {"label": "Atenção", "badge": "🟡", "color": "#fbbf24"},
    "critical": {"label": "Crítico", "badge": "🔴", "color": "#f87171"},
    "pending": {"label": "Pendente", "badge": "⚪", "color": "#94a3b8"},
}

_manager_status_schema_ensured = False


def ensure_manager_status_schema() -> None:
    """Garante que a coluna manager_evaluations_json exista na tabela maj_employee_reports."""
    global _manager_status_schema_ensured
    if _manager_status_schema_ensured:
        return

    ensure_reports_schema()
    with db() as conn:
        pg = _is_pg(conn)
        col_def = "TEXT DEFAULT '{}'"
        if pg:
            try:
                conn.execute(f"ALTER TABLE maj_employee_reports ADD COLUMN IF NOT EXISTS manager_evaluations_json {col_def};")
                conn.commit()
            except Exception as e:
                logger.debug(f"Aviso ao adicionar coluna manager_evaluations_json no PG: {e}")
        else:
            try:
                cur = conn.execute("PRAGMA table_info(maj_employee_reports);")
                existing_cols = {row[1] for row in cur.fetchall()}
                if "manager_evaluations_json" not in existing_cols:
                    conn.execute(f"ALTER TABLE maj_employee_reports ADD COLUMN manager_evaluations_json {col_def};")
                    conn.commit()
            except Exception as e:
                logger.debug(f"Aviso ao adicionar coluna manager_evaluations_json no SQLite: {e}")

        _manager_status_schema_ensured = True


def normalize_manager_evaluations(raw: Any) -> Dict[str, Dict[str, Any]]:
    """Normaliza o payload de avaliações dos gestores garantindo as chaves jam, geysa e fauzer."""
    data = {}
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
    elif isinstance(raw, dict):
        data = raw

    result = {}
    for mgr in ["jam", "geysa", "fauzer"]:
        mgr_data = data.get(mgr, {}) if isinstance(data, dict) else {}
        status = str(mgr_data.get("status") or "").lower().strip()
        if status not in STATUS_CONFIG:
            status = "pending"
        
        cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["pending"])
        result[mgr] = {
            "status": status,
            "status_label": cfg["label"],
            "badge_icon": cfg["badge"],
            "color": cfg["color"],
            "diagnosis": str(mgr_data.get("diagnosis") or "").strip(),
            "updated_at": mgr_data.get("updated_at") or None,
            "is_suggestion": bool(mgr_data.get("is_suggestion", mgr == "fauzer")),
        }
    return result


def get_employee_manager_evaluations(cycle_id: int, employee_key: str) -> Dict[str, Any]:
    """Recupera as avaliações dos gestores para um colaborador em um ciclo específico."""
    ensure_manager_status_schema()
    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        cur = conn.execute(
            f"SELECT manager_evaluations_json FROM maj_employee_reports WHERE cycle_id = {placeholder} AND employee_key = {placeholder} LIMIT 1",
            (cycle_id, employee_key)
        )
        row = cur.fetchone()
        raw = row["manager_evaluations_json"] if row else "{}"
        return normalize_manager_evaluations(raw)


def save_employee_manager_evaluations(
    cycle_id: int,
    employee_key: str,
    evaluations: Dict[str, Any]
) -> Dict[str, Any]:
    """Salva ou atualiza as avaliações dos gestores para um colaborador."""
    ensure_manager_status_schema()
    now_str = datetime.now().isoformat()
    existing = get_employee_manager_evaluations(cycle_id, employee_key)

    merged = dict(existing)
    for mgr in ["jam", "geysa", "fauzer"]:
        if mgr in evaluations and isinstance(evaluations[mgr], dict):
            new_st = str(evaluations[mgr].get("status") or existing[mgr]["status"]).lower().strip()
            if new_st not in STATUS_CONFIG:
                new_st = "pending"
            merged[mgr] = {
                "status": new_st,
                "status_label": STATUS_CONFIG[new_st]["label"],
                "badge_icon": STATUS_CONFIG[new_st]["badge"],
                "color": STATUS_CONFIG[new_st]["color"],
                "diagnosis": str(evaluations[mgr].get("diagnosis") if "diagnosis" in evaluations[mgr] else existing[mgr]["diagnosis"]).strip(),
                "updated_at": now_str,
                "is_suggestion": bool(evaluations[mgr].get("is_suggestion", mgr == "fauzer")),
            }

    json_str = json.dumps(merged, ensure_ascii=False)

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        conn.execute(
            f"UPDATE maj_employee_reports SET manager_evaluations_json = {placeholder}, updated_at = {placeholder} WHERE cycle_id = {placeholder} AND employee_key = {placeholder}",
            (json_str, datetime.now(), cycle_id, employee_key)
        )
        conn.commit()

    return merged


def save_batch_manager_status(
    cycle_id: int,
    manager_key: str,
    evaluations_map: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Atualiza as avaliações de um gestor específico (Jam, Geysa ou Fauzer) para vários colaboradores."""
    mgr = manager_key.lower().strip()
    if mgr not in ["jam", "geysa", "fauzer"]:
        raise ValueError("Gestor inválido. Permitidos: jam, geysa, fauzer.")

    results = {}
    for emp_key, eval_data in evaluations_map.items():
        current = get_employee_manager_evaluations(cycle_id, emp_key)
        current[mgr] = eval_data
        updated = save_employee_manager_evaluations(cycle_id, emp_key, current)
        results[emp_key] = updated[mgr]

    return results


def suggest_manager_evaluations_ai(cycle_id: int, employee_key: str) -> Dict[str, Any]:
    """Gera sugestões de status (badge e diagnóstico) via Gemini para Jam, Geysa e Fauzer."""
    meta = get_reporting_employee_meta(employee_key) or {}
    report = get_employee_report(cycle_id, employee_key)
    answers = report.get("answers", {})
    emp_name = meta.get("name") or employee_key.capitalize()
    role_title = meta.get("role_title") or ""
    area = meta.get("area") or ""

    # Extrai respostas textuais
    answers_text_list = []
    if isinstance(answers, dict):
        for q in meta.get("questions", []):
            qid = q.get("id")
            ans = str(answers.get(qid) or "").strip()
            if ans:
                answers_text_list.append(f"• {q.get('label')}: {ans}")

    answers_str = "\n".join(answers_text_list) if answers_text_list else "Colaborador ainda não detalhou respostas completas."

    prompt = f"""Você é o Consultor Executivo Sênior da MAJ Mobilidade Elétrica.
Analise o relatório semanal do colaborador abaixo e sugira a avaliação executiva para a Gerência/Diretoria.

COLABORADOR:
- Nome: {emp_name}
- Função: {role_title}
- Área: {area}

RELATÓRIO FORNECIDO PELO COLABORADOR NESTA SEMANA:
---
{answers_str[:5000]}
---

REGRAS DE RESPONSABILIDADE DOS GESTORES:
1. JAM PENITENTI (Diretor Geral / Comercial): Avalia todos os colaboradores sob a ótica de postura comercial, foco em resultado, impacto nas vendas e visão estratégica.
2. GEYSA (Gerente Geral / Operações / Financeiro): Avalia todos os colaboradores sob a ótica de disciplina operacional, cumprimento de rotina, conferências físicas, prazos de OS e integridade de caixa.
3. FAUZER (Tecnologia, Sistemas & Processos): Avaliação técnica e sugestiva para a gerência sobre uso correto do M-One, Bling, BotConversa, checklists e cumprimento das cartilhas.

CLASSIFICAÇÃO DE STATUS:
- 'aligned' (🟢 Alinhado): Entregas dentro do esperado, sem pendências críticas.
- 'attention' (🟡 Atenção): Pequenas pendências, atrasos ou pontos que precisam de alinhamento.
- 'critical' (🔴 Crítico): Gargalo operacional grave, motos paradas sem peças, desvios de caixa ou faturamento travado.

DIRETRIZ DO PARECER/DIAGNÓSTICO:
- Exatamente 1 a 2 frases objetivas, diretas e executivas para cada gestor.

Retorne ESTRITAMENTE um objeto JSON válido com a seguinte estrutura:
{{
  "jam": {{
    "status": "aligned" | "attention" | "critical",
    "diagnosis": "Parecer executivo do Jam em 1 ou 2 frases."
  }},
  "geysa": {{
    "status": "aligned" | "attention" | "critical",
    "diagnosis": "Parecer operacional da Geysa em 1 ou 2 frases."
  }},
  "fauzer": {{
    "status": "aligned" | "attention" | "critical",
    "diagnosis": "Parecer técnico/sugestivo de processos do Fauzer em 1 ou 2 frases.",
    "is_suggestion": true
  }}
}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        raw_resp = execute_gemini_payload(payload)
        candidates = raw_resp.get("candidates", [])
        if candidates:
            txt = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            parsed = json.loads(txt)
            if "jam" in parsed and "geysa" in parsed and "fauzer" in parsed:
                return normalize_manager_evaluations(parsed)
    except Exception as e:
        logger.warning(f"Falha ao gerar sugestão de status com IA: {e}")

    # Fallback estruturado inteligente caso IA não responda
    return _generate_fallback_evaluations(employee_key, answers_str)


def _generate_fallback_evaluations(employee_key: str, answers_str: str) -> Dict[str, Any]:
    """Gera fallback conciso baseado no papel do colaborador."""
    meta = get_reporting_employee_meta(employee_key) or {}
    name = meta.get("name") or employee_key.capitalize()

    low = answers_str.lower()
    has_crit = any(w in low for w in ["parada", "atrasad", "falta de peça", "divergência", "vencid", "bloqueio"])
    default_st = "attention" if has_crit else "aligned"

    return {
        "jam": {
            "status": default_st,
            "status_label": STATUS_CONFIG[default_st]["label"],
            "badge_icon": STATUS_CONFIG[default_st]["badge"],
            "color": STATUS_CONFIG[default_st]["color"],
            "diagnosis": f"{name} demonstrou alinhamento com os objetivos da semana; acompanhar conversão e prioridades comerciais.",
            "is_suggestion": False,
        },
        "geysa": {
            "status": default_st,
            "status_label": STATUS_CONFIG[default_st]["label"],
            "badge_icon": STATUS_CONFIG[default_st]["badge"],
            "color": STATUS_CONFIG[default_st]["color"],
            "diagnosis": f"Rotina operacional executada por {name}; manter cobrança das conferências e prazos de retorno.",
            "is_suggestion": False,
        },
        "fauzer": {
            "status": "aligned",
            "status_label": "Alinhado",
            "badge_icon": "🟢",
            "color": "#00e599",
            "diagnosis": f"Uso regular dos sistemas por {name}; sugerido reforçar alimentação correta dos dados no M-One/Bling.",
            "is_suggestion": True,
        }
    }


def get_cycle_manager_status_overview(cycle_id: int) -> Dict[str, Any]:
    """Retorna a visão panorâmica de todos os colaboradores do ciclo para Jam, Geysa e Fauzer."""
    ensure_manager_status_schema()
    
    # Lista de colaboradores avaliados (Marisa, Jhon, Ricardo, Luiza, Leo, Gabriel)
    eval_target_keys = ["marisa", "jhon", "ricardo", "luiza", "leo", "gabriel"]

    overview = {
        "cycle_id": cycle_id,
        "jam": [],
        "geysa": [],
        "fauzer": []
    }

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        cur = conn.execute(
            f"SELECT employee_key, employee_name, role_title, status, manager_evaluations_json FROM maj_employee_reports WHERE cycle_id = {placeholder} ORDER BY employee_name ASC",
            (cycle_id,)
        )
        rows = {r["employee_key"]: dict(r) for r in cur.fetchall()}

    for emp_key in eval_target_keys:
        meta = get_reporting_employee_meta(emp_key) or {}
        r_data = rows.get(emp_key, {})
        emp_name = meta.get("name") or r_data.get("employee_name") or emp_key.capitalize()
        role = meta.get("role_title") or r_data.get("role_title") or ""
        sub_status = r_data.get("status") or "pending"

        evals = normalize_manager_evaluations(r_data.get("manager_evaluations_json") or "{}")

        # Se os status estiverem totalmente vazios e o colaborador já submeteu, gera sugestão base
        if evals["jam"]["status"] == "pending" and evals["geysa"]["status"] == "pending" and sub_status in ["submitted_on_time", "submitted_late"]:
            evals = _generate_fallback_evaluations(emp_key, "")

        item_base = {
            "employee_key": emp_key,
            "employee_name": emp_name,
            "role_title": role,
            "submission_status": sub_status,
        }

        overview["jam"].append({**item_base, **evals["jam"]})
        overview["geysa"].append({**item_base, **evals["geysa"]})
        overview["fauzer"].append({**item_base, **evals["fauzer"]})

    return overview
