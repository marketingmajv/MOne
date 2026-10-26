"""
M-One Employee Alignment & Evaluation Service (services/employee_alignment_service.py)
Gerencia o novo sistema de aferição focado em pessoas:
Confronta a Resposta Fornecida com a Resposta Desejada (definida pela Diretoria),
calcula o scoring ponderado via Gemini e segmenta as sugestões para Jam/Geysa e Fauzer.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.employee_desired_templates import get_employee_default_desired_map
from services.employee_reports_data import REPORTING_EMPLOYEES, get_reporting_employee_meta
from services.employee_reports_service import _is_pg, ensure_reports_schema, get_employee_report
from services.employee_report_dispatch_service import normalize_question_actions
from services.gemini_client import execute_gemini_payload

logger = logging.getLogger(__name__)

_alignment_schema_ensured = False


def ensure_alignment_schema() -> None:
    """Garante que as colunas de respostas desejadas, avaliação de IA e liberação existam na tabela maj_employee_reports."""
    global _alignment_schema_ensured
    if _alignment_schema_ensured:
        return

    ensure_reports_schema()
    with db() as conn:
        pg = _is_pg(conn)
        columns_to_add = [
            ("desired_answers_json", "TEXT DEFAULT '{}'"),
            ("evaluation_json", "TEXT DEFAULT '{}'"),
            ("alignment_suggestions_json", "TEXT DEFAULT '{}'"),
            ("score_total", "INTEGER DEFAULT NULL"),
            ("score_badge", "VARCHAR(30) DEFAULT ''" if pg else "TEXT DEFAULT ''"),
            ("is_feedback_released", "BOOLEAN DEFAULT FALSE" if pg else "INTEGER DEFAULT 0"),
            ("evaluated_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL" if pg else "TIMESTAMP DEFAULT NULL"),
            ("director_comments_json", "TEXT DEFAULT '{}'"),
            ("agreements_jam_geysa", "TEXT DEFAULT ''"),
            ("agreements_fauzer", "TEXT DEFAULT ''"),
        ]

        if pg:
            for col_name, col_def in columns_to_add:
                try:
                    conn.execute(f"ALTER TABLE maj_employee_reports ADD COLUMN IF NOT EXISTS {col_name} {col_def};")
                except Exception as e:
                    logger.debug(f"Aviso ao adicionar coluna PG {col_name}: {e}")
        else:
            try:
                cur = conn.execute("PRAGMA table_info(maj_employee_reports);")
                existing_cols = {row[1] for row in cur.fetchall()}
                for col_name, col_def in columns_to_add:
                    if col_name not in existing_cols:
                        conn.execute(f"ALTER TABLE maj_employee_reports ADD COLUMN {col_name} {col_def};")
            except Exception as e:
                logger.debug(f"Aviso ao adicionar coluna SQLite: {e}")

        try:
            conn.commit()
        except Exception:
            pass

        _alignment_schema_ensured = True


def _parse_json(val: Any, default: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return json.loads(val)
        except Exception:
            return default
    return default


def generate_whatsapp_alignment_url(
    employee_name: str,
    phone: str,
    triad_questions: List[Dict[str, Any]],
    agreements_jam_geysa: str,
    agreements_fauzer: str
) -> str:
    """Gera link oficial do WhatsApp com a pauta e combinados da semana prontos para envio."""
    import urllib.parse

    clean_phone = "".join(c for c in (phone or "") if c.isdigit())
    if clean_phone and not clean_phone.startswith("55") and len(clean_phone) <= 11:
        clean_phone = f"55{clean_phone}"

    msg_lines = [
        f"Olá {employee_name}! Segue o resumo do nosso alinhamento semanal da MAJ Mobilidade: ⚡\n"
    ]

    has_comments = False
    comments_section = ["📋 *Pontos de Alinhamento das Entregas:*"]
    for q in triad_questions:
        comment = (q.get("director_comment") or "").strip()
        if comment:
            has_comments = True
            comments_section.append(f"• *{q['label']}*: {comment}")

    if has_comments:
        msg_lines.extend(comments_section)
        msg_lines.append("")

    if agreements_jam_geysa and isinstance(agreements_jam_geysa, str) and agreements_jam_geysa.strip():
        msg_lines.append(f"📌 *Acordos & Metas (Jam & Geysa):*\n{agreements_jam_geysa.strip()}\n")

    if agreements_fauzer and isinstance(agreements_fauzer, str) and agreements_fauzer.strip():
        msg_lines.append(f"⚡ *Sistemas & Processos (Fauzer):*\n{agreements_fauzer.strip()}\n")

    msg_lines.append("Contamos com seu empenho e dedicação para batermos as metas! Uma excelente semana! 🚀")

    full_msg = "\n".join(msg_lines)
    encoded = urllib.parse.quote(full_msg)

    if clean_phone:
        return f"https://wa.me/{clean_phone}?text={encoded}"
    return f"https://api.whatsapp.com/send?text={encoded}"


def get_employee_evaluation_data(cycle_id: int, employee_key: str) -> Dict[str, Any]:
    """Retorna os dados completos de um colaborador no ciclo: perguntas, respostas fornecidas,

    comentários e parecer da diretoria, acordos para Jam/Geysa e Fauzer, e status de liberação.
    """
    ensure_alignment_schema()
    meta = get_reporting_employee_meta(employee_key) or {}
    report = get_employee_report(cycle_id, employee_key)

    questions = meta.get("questions", [])
    default_desired = get_employee_default_desired_map(employee_key)

    raw_provided = _parse_json(report.get("answers_json"), {})
    raw_desired = _parse_json(report.get("desired_answers_json"), {})
    raw_comments = _parse_json(report.get("director_comments_json"), {})
    evaluation = _parse_json(report.get("evaluation_json"), {})
    suggestions = _parse_json(report.get("alignment_suggestions_json"), {})

    agreements_jam_geysa = report.get("agreements_jam_geysa") or ""
    agreements_fauzer = report.get("agreements_fauzer") or ""

    # Monta a tríade estruturada por pergunta
    triad_questions = []
    questions_eval_map = {q.get("id"): q for q in evaluation.get("questions_eval", [])}

    for q in questions:
        qid = q.get("id")
        provided_text = str(raw_provided.get(qid) or "").strip() if isinstance(raw_provided, dict) else ""
        desired_text = str(raw_desired.get(qid) or default_desired.get(qid) or "").strip() if isinstance(raw_desired, dict) else str(default_desired.get(qid) or "")
        raw_comm_val = raw_comments.get(qid) if isinstance(raw_comments, dict) else ""
        if isinstance(raw_comm_val, dict):
            director_comment = str(raw_comm_val.get("employee_feedback") or raw_comm_val.get("demand_jam") or raw_comm_val.get("demand_fauzer") or "").strip()
        else:
            director_comment = str(raw_comm_val or "").strip()

        q_eval = questions_eval_map.get(qid, {})

        triad_questions.append({
            "id": qid,
            "label": q.get("label", ""),
            "placeholder": q.get("placeholder", ""),
            "help": q.get("help", ""),
            "provided_answer": provided_text,
            "desired_answer": desired_text,
            "director_comment": director_comment,
            "score": q_eval.get("score"),
            "badge": q_eval.get("badge", "neutral"),
            "gap": q_eval.get("gap", ""),
        })

    is_released = bool(report.get("is_feedback_released"))
    phone = meta.get("phone", "")
    emp_name = meta.get("name") or report.get("employee_name") or employee_key.capitalize()

    whatsapp_url = generate_whatsapp_alignment_url(
        employee_name=emp_name,
        phone=phone,
        triad_questions=triad_questions,
        agreements_jam_geysa=agreements_jam_geysa,
        agreements_fauzer=agreements_fauzer
    )

    return {
        "cycle_id": cycle_id,
        "employee_key": employee_key,
        "employee_name": emp_name,
        "role_title": meta.get("role_title") or report.get("role_title") or "",
        "area": meta.get("area", ""),
        "badge": meta.get("badge", ""),
        "badge_color": meta.get("badge_color", "blue"),
        "status": report.get("status", "pending"),
        "submitted_at": report.get("submitted_at"),
        "score_total": report.get("score_total"),
        "score_badge": report.get("score_badge", "neutral"),
        "is_feedback_released": is_released,
        "evaluated_at": report.get("evaluated_at"),
        "triad_questions": triad_questions,
        "director_comments": raw_comments if isinstance(raw_comments, dict) else {},
        "director_actions": {
            str(q.get("id")): normalize_question_actions(raw_comments.get(str(q.get("id"))))
            for q in triad_questions
        } if isinstance(raw_comments, dict) else {},
        "agreements_jam_geysa": agreements_jam_geysa,
        "agreements_fauzer": agreements_fauzer,
        "whatsapp_alignment_url": whatsapp_url,
        "evaluation_summary": evaluation.get("summary", ""),
        "alignment_suggestions": suggestions if suggestions else evaluation.get("alignment_suggestions", {}),
    }


def save_desired_answers(cycle_id: int, employee_key: str, desired_answers: Dict[str, str]) -> Dict[str, Any]:
    """Salva as respostas desejadas customizadas pela Diretoria no ciclo."""
    ensure_alignment_schema()
    now = datetime.now()
    desired_json = json.dumps(desired_answers, ensure_ascii=False)

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"

        cur = conn.execute(
            f"SELECT id FROM maj_employee_reports WHERE cycle_id = {placeholder} AND employee_key = {placeholder} LIMIT 1",
            (cycle_id, employee_key)
        )
        row = cur.fetchone()

        if row:
            sql = f"""
                UPDATE maj_employee_reports
                SET desired_answers_json = {placeholder}, updated_at = {placeholder}
                WHERE cycle_id = {placeholder} AND employee_key = {placeholder}
            """
            conn.execute(sql, (desired_json, now, cycle_id, employee_key))
        else:
            meta = get_reporting_employee_meta(employee_key) or {}
            emp_name = meta.get("name", employee_key.capitalize())
            role_title = meta.get("role_title", "Colaborador")
            sql = f"""
                INSERT INTO maj_employee_reports
                (cycle_id, employee_key, employee_name, role_title, answers_json, desired_answers_json, status, updated_at)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, '{{}}', {placeholder}, 'draft', {placeholder})
            """
            conn.execute(sql, (cycle_id, employee_key, emp_name, role_title, desired_json, now))
        conn.commit()

    return get_employee_evaluation_data(cycle_id, employee_key)


def save_director_alignment(
    cycle_id: int,
    employee_key: str,
    director_comments: Dict[str, str],
    agreements_jam_geysa: str = "",
    agreements_fauzer: str = ""
) -> Dict[str, Any]:
    """Salva os comentários de alinhamento por pergunta e os acordos de Jam/Geysa e Fauzer no ciclo."""
    ensure_alignment_schema()
    now = datetime.now()
    comments_json = json.dumps(director_comments, ensure_ascii=False)

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"

        cur = conn.execute(
            f"SELECT id FROM maj_employee_reports WHERE cycle_id = {placeholder} AND employee_key = {placeholder} LIMIT 1",
            (cycle_id, employee_key)
        )
        row = cur.fetchone()

        if row:
            sql = f"""
                UPDATE maj_employee_reports
                SET director_comments_json = {placeholder},
                    agreements_jam_geysa = {placeholder},
                    agreements_fauzer = {placeholder},
                    updated_at = {placeholder}
                WHERE cycle_id = {placeholder} AND employee_key = {placeholder}
            """
            conn.execute(sql, (comments_json, agreements_jam_geysa, agreements_fauzer, now, cycle_id, employee_key))
        else:
            meta = get_reporting_employee_meta(employee_key) or {}
            emp_name = meta.get("name", employee_key.capitalize())
            role_title = meta.get("role_title", "Colaborador")
            sql = f"""
                INSERT INTO maj_employee_reports
                (cycle_id, employee_key, employee_name, role_title, answers_json, director_comments_json, agreements_jam_geysa, agreements_fauzer, status, updated_at)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, '{{}}', {placeholder}, {placeholder}, {placeholder}, 'draft', {placeholder})
            """
            conn.execute(sql, (cycle_id, employee_key, emp_name, role_title, comments_json, agreements_jam_geysa, agreements_fauzer, now))
        conn.commit()

    return get_employee_evaluation_data(cycle_id, employee_key)


def suggest_comment_with_ai(
    question_label: str,
    provided_answer: str,
    role_title: str,
    employee_name: str
) -> str:
    """Gera 1 a 2 frases construtivas e profissionais de sugestão de comentário para a Diretoria."""
    prompt = f"""Você é um mentor executivo sênior de liderança e gestão da MAJ Mobilidade Elétrica.
Jam Penitenti e Geysa estão em reunião de gestão semanal alinhando o relatório de um colaborador:
COLABORADOR: {employee_name} ({role_title})
PERGUNTA ANALISADA: {question_label}
RESPOSTA ENTREGUE PELO COLABORADOR NA SEXTA-FEIRA:
{provided_answer if provided_answer.strip() else '[O colaborador deixou este campo em branco ou não relatou nada]'}

OBJETIVO:
Redija uma sugestão de comentário/parecer para a Diretoria (Jam e Geysa) anotar nesta pergunta.
REGRAS:
- Seja extremamente conciso: máximo de 1 a 2 frases curtas.
- Tom profissional, humano, orientador e firme (foco em resultado e melhoria contínua).
- Se a resposta foi boa, inicie elogiando e aponte o próximo passo.
- Se a resposta foi vazia ou incompleta, indique de forma clara e educada o que precisa ser alinhado ou corrigido.
- Retorne APENAS o texto da sugestão em texto puro, sem aspas e sem introduções.
"""
    try:
        response = execute_gemini_payload({"contents": [{"parts": [{"text": prompt}]}]})
        candidates = response.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts and "text" in parts[0]:
                return parts[0]["text"].strip().strip('"')
    except Exception as e:
        logger.warning(f"Erro ao gerar sugestão de comentário com IA: {e}")

    if not provided_answer.strip():
        return f"Alinhar com {employee_name} a importância de preencher este ponto semanalmente conforme o padrão da cartilha."
    return f"Validar os pontos apresentados por {employee_name} e acompanhar a evolução na rotina da próxima semana."


def toggle_feedback_release(cycle_id: int, employee_key: str, is_released: bool) -> bool:
    """Ativa ou desativa a liberação da visualização das respostas desejadas e pontuação no portal do colaborador."""
    ensure_alignment_schema()
    now = datetime.now()
    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        released_val = True if pg else (1 if is_released else 0) if not pg else is_released

        sql = f"""
            UPDATE maj_employee_reports
            SET is_feedback_released = {placeholder}, updated_at = {placeholder}
            WHERE cycle_id = {placeholder} AND employee_key = {placeholder}
        """
        conn.execute(sql, (released_val, now, cycle_id, employee_key))
        conn.commit()
    return is_released


def evaluate_employee_with_gemini(cycle_id: int, employee_key: str) -> Dict[str, Any]:
    """Executa a análise de IA via Gemini comparando [Resposta Fornecida] vs [Resposta Desejada].

    Calcula pontuação por pergunta, score total ponderado, gaps e sugestões para Jam/Geysa e Fauzer.
    """
    ensure_alignment_schema()
    data = get_employee_evaluation_data(cycle_id, employee_key)
    triad = data.get("triad_questions", [])
    emp_name = data.get("employee_name", employee_key.capitalize())
    role_title = data.get("role_title", "")
    area = data.get("area", "")

    # Monta o confronto textual pergunta por pergunta
    confront_blocks = []
    for q in triad:
        confront_blocks.append(
            f"--- PERGUNTA: {q['label']} (ID: {q['id']}) ---\n"
            f"• RESPOSTA FORNECIDA PELO COLABORADOR:\n"
            f"  {q['provided_answer'] if q['provided_answer'] else '[NÃO INFORMOU / CAMPO VAZIO]'}\n\n"
            f"• RESPOSTA DESEJADA PELA DIRETORIA (GABARITO DE EXCELÊNCIA):\n"
            f"  {q['desired_answer']}\n"
        )

    confront_text = "\n".join(confront_blocks)

    prompt = (
        f"Auditor de Governança MAJ Mobilidade: Avalie o relatório de {emp_name} ({role_title} - {area}).\n"
        f"CONFRONTO:\n{confront_text}\n"
        "Retorne JSON: {\"score_total\": 85, \"score_badge\": \"green\", \"summary\": \"Resumo\", "
        "\"questions_eval\": [{\"id\": \"id\", \"score\": 90, \"badge\": \"green\", \"gap\": \"gap\"}], "
        "\"alignment_suggestions\": {\"jam_geysa\": [\"Ação Jam/Geysa\"], \"fauzer\": [\"Ação Fauzer\"]}}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }

    resp = execute_gemini_payload(payload, timeout=35)
    candidates = resp.get("candidates", [])
    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() if candidates else ""

    eval_result = {}
    if raw_text:
        try:
            eval_result = json.loads(raw_text)
        except Exception as e:
            logger.warning(f"Erro ao parsear JSON retornado pelo Gemini: {e}")

    # Fallback de segurança se o Gemini retornar vazio ou falhar
    if not eval_result or "score_total" not in eval_result:
        ans_count = sum(1 for q in triad if q.get("provided_answer"))
        total_q = len(triad) or 1
        calc_score = int((ans_count / total_q) * 80)
        eval_result = {
            "score_total": calc_score,
            "score_badge": "green" if calc_score >= 80 else ("yellow" if calc_score >= 50 else "red"),
            "summary": f"Relatório com {ans_count} de {total_q} perguntas preenchidas.",
            "questions_eval": [
                {"id": q["id"], "score": 80 if q.get("provided_answer") else 30, "badge": "green" if q.get("provided_answer") else "red", "gap": "Preenchido." if q.get("provided_answer") else "Não preenchido."}
                for q in triad
            ],
            "alignment_suggestions": {
                "jam_geysa": [f"Alinhar rotina com {emp_name} na reunião de diretoria."],
                "fauzer": [f"Validar processos e sistema M-One com {emp_name}."],
            },
        }

    score_total = int(eval_result.get("score_total", 70))
    score_badge = eval_result.get("score_badge", "yellow")
    suggestions = eval_result.get("alignment_suggestions", {})

    now = datetime.now()
    eval_json_str = json.dumps(eval_result, ensure_ascii=False)
    sug_json_str = json.dumps(suggestions, ensure_ascii=False)

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        sql = f"""
            UPDATE maj_employee_reports
            SET evaluation_json = {placeholder},
                alignment_suggestions_json = {placeholder},
                score_total = {placeholder},
                score_badge = {placeholder},
                evaluated_at = {placeholder},
                updated_at = {placeholder}
            WHERE cycle_id = {placeholder} AND employee_key = {placeholder}
        """
        conn.execute(sql, (eval_json_str, sug_json_str, score_total, score_badge, now, now, cycle_id, employee_key))
        conn.commit()

    return get_employee_evaluation_data(cycle_id, employee_key)


def evaluate_all_employees_with_gemini(cycle_id: int) -> List[Dict[str, Any]]:
    """Avalia em lote todos os colaboradores cadastrados para o ciclo selecionado."""
    ensure_alignment_schema()
    results = []
    for emp_key in REPORTING_EMPLOYEES.keys():
        try:
            res = evaluate_employee_with_gemini(cycle_id, emp_key)
            results.append({
                "employee_key": emp_key,
                "name": res.get("employee_name"),
                "score_total": res.get("score_total"),
                "score_badge": res.get("score_badge"),
                "success": True,
            })
        except Exception as e:
            logger.error(f"Erro ao avaliar colaborador {emp_key} no ciclo {cycle_id}: {e}")
            results.append({
                "employee_key": emp_key,
                "error": str(e),
                "success": False,
            })
    return results
