"""
M-One Employee Questions Management Service (services/employee_questions_service.py)
Gerencia a customização dinâmica das perguntas dos relatórios semanais por colaborador:
Adicionar, Editar, Ocultar/Exibir, Duplicar, Espelhar entre colaboradores, Reordenar e Excluir,
preservando automaticamente perguntas históricas que já possuam respostas em ciclos anteriores.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import copy
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.employee_desired_templates import DEFAULT_DESIRED_ANSWERS

logger = logging.getLogger(__name__)

_questions_schema_ensured = False


def _is_pg(conn) -> bool:
    return hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"


def strip_number_prefix(text: str) -> str:
    """Remove prefixos numéricos como '1. ', '2 - ', '10) ' do início do título da pergunta."""
    if not text:
        return ""
    return re.sub(r"^\s*\d+\s*[\.\-\)]\s*", "", str(text).strip())


def ensure_questions_schema() -> None:
    """Garante a criação da tabela de configuração de perguntas customizadas por colaborador."""
    global _questions_schema_ensured
    if _questions_schema_ensured:
        return

    with db() as conn:
        pg = _is_pg(conn)
        sql = """
        CREATE TABLE IF NOT EXISTS maj_employee_questions_config (
            employee_key VARCHAR(50) PRIMARY KEY,
            questions_json TEXT NOT NULL DEFAULT '[]',
            archived_questions_json TEXT NOT NULL DEFAULT '{}',
            updated_by VARCHAR(100) DEFAULT 'diretoria',
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """ if pg else """
        CREATE TABLE IF NOT EXISTS maj_employee_questions_config (
            employee_key TEXT PRIMARY KEY,
            questions_json TEXT NOT NULL DEFAULT '[]',
            archived_questions_json TEXT NOT NULL DEFAULT '{}',
            updated_by TEXT DEFAULT 'diretoria',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            conn.executescript(sql)
            conn.commit()
        except Exception as e:
            logger.debug("Schema notice maj_employee_questions_config: %s", e)
        _questions_schema_ensured = True


def _get_factory_questions(employee_key: str) -> List[Dict[str, Any]]:
    """Retorna a lista de perguntas originais de fábrica da cartilha do colaborador."""
    from services.employee_reports_data import REPORTING_EMPLOYEES

    emp_key = (employee_key or "").lower().strip()
    meta = REPORTING_EMPLOYEES.get(emp_key) or {}
    raw_list = copy.deepcopy(meta.get("questions", []))
    desired_map = DEFAULT_DESIRED_ANSWERS.get(emp_key, {})

    normalized = []
    for idx, q in enumerate(raw_list, start=1):
        qid = str(q.get("id") or f"q_{idx}").strip()
        raw_title = strip_number_prefix(q.get("raw_title") or q.get("label") or qid)
        normalized.append({
            "id": qid,
            "raw_title": raw_title,
            "label": f"{idx}. {raw_title}",
            "placeholder": str(q.get("placeholder") or "").strip(),
            "help": str(q.get("help") or "").strip(),
            "desired_answer": str(q.get("desired_answer") or desired_map.get(qid) or "").strip(),
            "hidden": bool(q.get("hidden", False)),
        })
    return normalized


_CONFIG_CACHE: Dict[str, Tuple[float, Any]] = {}


def _load_db_config(employee_key: str) -> Optional[Dict[str, Any]]:
    """Carrega o registro salvo no banco para um colaborador, se existir (com cache em memória)."""
    global _CONFIG_CACHE
    import time
    emp_key = (employee_key or "").lower().strip()
    now = time.time()
    if emp_key in _CONFIG_CACHE:
        ts, val = _CONFIG_CACHE[emp_key]
        if now - ts < 120.0:
            return val

    ensure_questions_schema()
    with db() as conn:
        ph = "%s" if _is_pg(conn) else "?"
        row = conn.execute(
            f"SELECT * FROM maj_employee_questions_config WHERE employee_key = {ph} LIMIT 1",
            (emp_key,)
        ).fetchone()
        if not row:
            _CONFIG_CACHE[emp_key] = (now, None)
            return None
        d = dict(row)
        try:
            d["questions"] = json.loads(d.get("questions_json") or "[]")
        except Exception:
            d["questions"] = []
        try:
            d["archived"] = json.loads(d.get("archived_questions_json") or "{}")
        except Exception:
            d["archived"] = {}
        _CONFIG_CACHE[emp_key] = (now, d)
        return d


def _renumber_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aplica numeração sequencial (1., 2., 3...) apenas às perguntas visíveis."""
    result = []
    vis_idx = 1
    for q in questions:
        item = dict(q)
        raw_title = strip_number_prefix(item.get("raw_title") or item.get("label") or "Pergunta")
        item["raw_title"] = raw_title
        is_hidden = bool(item.get("hidden", False))
        item["hidden"] = is_hidden
        if not is_hidden:
            item["display_number"] = vis_idx
            item["label"] = f"{vis_idx}. {raw_title}"
            vis_idx += 1
        else:
            item["display_number"] = None
            item["label"] = f"[Oculta] {raw_title}"
        result.append(item)
    return result


def get_all_Configured_Questions_For_Editor(employee_key: str) -> List[Dict[str, Any]]:
    """Retorna todas as perguntas (ativas e ocultas) de um colaborador para o modal de edição."""
    emp_key = (employee_key or "").lower().strip()
    cfg = _load_db_config(emp_key)
    desired_map = DEFAULT_DESIRED_ANSWERS.get(emp_key, {})

    if cfg and isinstance(cfg.get("questions"), list) and len(cfg["questions"]) > 0:
        raw_questions = cfg["questions"]
    else:
        raw_questions = _get_factory_questions(emp_key)

    cleaned = []
    for idx, q in enumerate(raw_questions, start=1):
        qid = str(q.get("id") or f"q_{idx}").strip()
        raw_title = strip_number_prefix(q.get("raw_title") or q.get("label") or qid)
        cleaned.append({
            "id": qid,
            "raw_title": raw_title,
            "placeholder": str(q.get("placeholder") or "").strip(),
            "help": str(q.get("help") or "").strip(),
            "desired_answer": str(q.get("desired_answer") or desired_map.get(qid) or "").strip(),
            "hidden": bool(q.get("hidden", False)),
        })
    return _renumber_questions(cleaned)


def get_effective_questions_for_employee(
    employee_key: str,
    existing_answers: Optional[Dict[str, Any]] = None,
    is_historical_cycle: bool = False
) -> List[Dict[str, Any]]:
    """
    Retorna a lista de perguntas efetivas para renderização em formulários, dashboard e IA:
    - No ciclo ativo: retorna todas as perguntas com hidden=False numeradas sequencialmente (1., 2., 3...).
    - Se houver respostas salvas (existing_answers) para uma pergunta oculta ou excluída em ciclos anteriores
      (ou mesmo no ciclo atual antes de ocultar), mantém a pergunta visível para nunca ocultar dados preenchidos.
    """
    emp_key = (employee_key or "").lower().strip()
    all_editor_q = get_all_Configured_Questions_For_Editor(emp_key)
    answers = existing_answers if isinstance(existing_answers, dict) else {}

    active_list = []
    included_ids = set()

    for q in all_editor_q:
        qid = q["id"]
        has_saved_answer = bool(str(answers.get(qid) or "").strip())
        if not q.get("hidden") or (is_historical_cycle and has_saved_answer):
            active_list.append(dict(q, hidden=False))
            included_ids.add(qid)

    # Verifica se há respostas em ciclos passados para perguntas que foram excluídas
    if answers:
        cfg = _load_db_config(emp_key)
        archived_map = (cfg.get("archived") or {}) if cfg else {}
        factory_map = {fq["id"]: fq for fq in _get_factory_questions(emp_key)}

        for ans_qid, ans_val in answers.items():
            if ans_qid not in included_ids and str(ans_val or "").strip():
                arch_q = archived_map.get(ans_qid) or factory_map.get(ans_qid)
                if arch_q:
                    raw_t = strip_number_prefix(arch_q.get("raw_title") or arch_q.get("label") or ans_qid)
                    active_list.append({
                        "id": ans_qid,
                        "raw_title": raw_t,
                        "placeholder": arch_q.get("placeholder", ""),
                        "help": arch_q.get("help", ""),
                        "desired_answer": arch_q.get("desired_answer", ""),
                        "hidden": False,
                        "is_archived": True,
                    })
                    included_ids.add(ans_qid)

    return _renumber_questions(active_list)


def get_custom_desired_answers_map(employee_key: str) -> Dict[str, str]:
    """Retorna o mapa {question_id: desired_answer} combinando fábrica e customizações."""
    emp_key = (employee_key or "").lower().strip()
    base_map = dict(DEFAULT_DESIRED_ANSWERS.get(emp_key, {}))
    try:
        for q in get_all_Configured_Questions_For_Editor(emp_key):
            if q.get("id") and q.get("desired_answer"):
                base_map[q["id"]] = q["desired_answer"]
    except Exception as e:
        logger.debug("Fallback desired_answers_map (%s): %s", emp_key, e)
    return base_map


def get_editor_payload(selected_employee_key: Optional[str] = None) -> Dict[str, Any]:
    """Retorna o pacote completo para o Modal de Edição de Perguntas de todos os colaboradores."""
    from services.employee_reports_data import REPORTING_EMPLOYEES

    employees_list = []
    for key, meta in REPORTING_EMPLOYEES.items():
        q_list = get_all_Configured_Questions_For_Editor(key)
        active_cnt = sum(1 for q in q_list if not q.get("hidden"))
        hidden_cnt = sum(1 for q in q_list if q.get("hidden"))
        cfg = _load_db_config(key)
        employees_list.append({
            "key": key,
            "name": meta.get("name", key.capitalize()),
            "role_title": meta.get("role_title", ""),
            "area": meta.get("area", ""),
            "badge": meta.get("badge", ""),
            "badge_color": meta.get("badge_color", "blue"),
            "is_customized": bool(cfg is not None),
            "active_count": active_cnt,
            "hidden_count": hidden_cnt,
            "total_count": len(q_list),
            "questions": q_list,
        })

    target_key = (selected_employee_key or "").lower().strip()
    if not target_key or target_key not in REPORTING_EMPLOYEES:
        target_key = next(iter(REPORTING_EMPLOYEES.keys()), "marisa")

    return {
        "selected_employee_key": target_key,
        "employees": employees_list,
    }


def _slugify_question_id(raw_title: str, existing_ids: set) -> str:
    """Gera um ID único e limpo para novas perguntas ou perguntas duplicadas."""
    clean = re.sub(r"[^a-z0-9]+", "_", (raw_title or "pergunta").lower()).strip("_")
    base = clean[:28] or "pergunta"
    candidate = base
    counter = 2
    while candidate in existing_ids:
        candidate = f"{base}_{counter}"
        counter += 1
    existing_ids.add(candidate)
    return candidate


def save_employee_questions(
    employee_key: str,
    questions: List[Dict[str, Any]],
    operator: str = "diretoria"
) -> Dict[str, Any]:
    """Salva a lista completa de perguntas de um colaborador (adição, edição, ocultação, ordem, exclusão)."""
    from services.employee_reports_data import REPORTING_EMPLOYEES

    ensure_questions_schema()
    emp_key = (employee_key or "").lower().strip()
    if emp_key not in REPORTING_EMPLOYEES:
        raise ValueError(f"Colaborador '{emp_key}' não encontrado.")

    if not isinstance(questions, list) or len(questions) == 0:
        raise ValueError("O colaborador deve possuir pelo menos 1 pergunta cadastrada.")

    # Preserva no arquivo morto qualquer pergunta anterior que tenha sido removida
    prev_questions = get_all_Configured_Questions_For_Editor(emp_key)
    prev_cfg = _load_db_config(emp_key)
    archived_map = dict((prev_cfg.get("archived") or {}) if prev_cfg else {})
    for fq in _get_factory_questions(emp_key):
        archived_map.setdefault(fq["id"], fq)
    for pq in prev_questions:
        archived_map[pq["id"]] = pq

    existing_ids: set = set()
    sanitized: List[Dict[str, Any]] = []

    for q in questions:
        raw_title = strip_number_prefix(q.get("raw_title") or q.get("label") or "").strip()
        if not raw_title:
            continue

        qid = str(q.get("id") or "").strip()
        if not qid or qid.startswith("new_") or qid in existing_ids:
            qid = _slugify_question_id(raw_title, existing_ids)
        else:
            existing_ids.add(qid)

        sanitized.append({
            "id": qid,
            "raw_title": raw_title,
            "placeholder": str(q.get("placeholder") or "").strip(),
            "help": str(q.get("help") or "").strip(),
            "desired_answer": str(q.get("desired_answer") or "").strip(),
            "hidden": bool(q.get("hidden", False)),
        })

    if not sanitized:
        raise ValueError("Nenhuma pergunta com título válido foi informada.")

    renumbered = _renumber_questions(sanitized)
    # Remove do arquivo morto as que continuam presentes na lista principal
    for rq in renumbered:
        archived_map.pop(rq["id"], None)

    q_json = json.dumps(renumbered, ensure_ascii=False)
    arch_json = json.dumps(archived_map, ensure_ascii=False)
    now = datetime.now()

    with db() as conn:
        pg = _is_pg(conn)
        if pg:
            conn.execute(
                """
                INSERT INTO maj_employee_questions_config
                    (employee_key, questions_json, archived_questions_json, updated_by, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (employee_key) DO UPDATE SET
                    questions_json = EXCLUDED.questions_json,
                    archived_questions_json = EXCLUDED.archived_questions_json,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at;
                """,
                (emp_key, q_json, arch_json, operator, now)
            )
        else:
            conn.execute(
                """
                INSERT INTO maj_employee_questions_config
                    (employee_key, questions_json, archived_questions_json, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(employee_key) DO UPDATE SET
                    questions_json = excluded.questions_json,
                    archived_questions_json = excluded.archived_questions_json,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at;
                """,
                (emp_key, q_json, arch_json, operator, now.strftime("%Y-%m-%d %H:%M:%S"))
            )
        conn.commit()

    _CONFIG_CACHE.pop(emp_key, None)
    return get_editor_payload(emp_key)


def copy_question_to_employee(
    target_employee_key: str,
    question_data: Dict[str, Any],
    operator: str = "diretoria"
) -> Dict[str, Any]:
    """Copia/espelha uma pergunta para a cartilha de outro colaborador."""
    from services.employee_reports_data import REPORTING_EMPLOYEES

    target_key = (target_employee_key or "").lower().strip()
    if target_key not in REPORTING_EMPLOYEES:
        raise ValueError(f"Colaborador de destino '{target_key}' inválido.")

    target_questions = get_all_Configured_Questions_For_Editor(target_key)
    existing_ids = {q["id"] for q in target_questions}

    raw_title = strip_number_prefix(question_data.get("raw_title") or question_data.get("label") or "").strip()
    if not raw_title:
        raise ValueError("Título da pergunta inválido para cópia.")

    base_id = str(question_data.get("id") or "").strip()
    new_id = base_id if (base_id and base_id not in existing_ids) else _slugify_question_id(raw_title, existing_ids)

    target_questions.append({
        "id": new_id,
        "raw_title": raw_title,
        "placeholder": str(question_data.get("placeholder") or "").strip(),
        "help": str(question_data.get("help") or "").strip(),
        "desired_answer": str(question_data.get("desired_answer") or "").strip(),
        "hidden": False,
    })

    save_employee_questions(target_key, target_questions, operator=operator)
    return get_editor_payload(target_key)


def restore_default_questions(employee_key: str, operator: str = "diretoria") -> Dict[str, Any]:
    """Restaura as perguntas originais da cartilha oficial do colaborador."""
    ensure_questions_schema()
    emp_key = (employee_key or "").lower().strip()
    with db() as conn:
        ph = "%s" if _is_pg(conn) else "?"
        conn.execute(f"DELETE FROM maj_employee_questions_config WHERE employee_key = {ph}", (emp_key,))
        conn.commit()
    return get_editor_payload(emp_key)

