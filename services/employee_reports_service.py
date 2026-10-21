"""
M-One Employee Reports Service (services/employee_reports_service.py)
Gerencia os ciclos semanais de reportes, submissões dos colaboradores, controle de prazos
e consolidação executiva para a reunião de diretoria da MAJ Mobilidade.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import db
from services.employee_reports_data import (
    REPORTING_EMPLOYEES,
    generate_whatsapp_charge_url,
    get_reporting_employee_meta,
)

logger = logging.getLogger(__name__)

_reports_schema_ensured = False


def _is_pg(conn) -> bool:
    return hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"


def ensure_reports_schema():
    """Garante a criação das tabelas de ciclos e relatórios semanais."""
    global _reports_schema_ensured
    if _reports_schema_ensured:
        return

    with db() as conn:
        pg = _is_pg(conn)
        cycle_tbl = """CREATE TABLE IF NOT EXISTS maj_report_cycles (
            id SERIAL PRIMARY KEY, cycle_code VARCHAR(30) UNIQUE NOT NULL, title VARCHAR(150) NOT NULL,
            start_date VARCHAR(30) NOT NULL, deadline TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE, notes TEXT DEFAULT '', created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );""" if pg else """CREATE TABLE IF NOT EXISTS maj_report_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
            start_date TEXT NOT NULL, deadline TIMESTAMP NOT NULL, is_active BOOLEAN DEFAULT 1, notes TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        rep_tbl = """CREATE TABLE IF NOT EXISTS maj_employee_reports (
            id SERIAL PRIMARY KEY, cycle_id INTEGER NOT NULL, user_id INTEGER, employee_key VARCHAR(50) NOT NULL,
            employee_name VARCHAR(100) NOT NULL, role_title VARCHAR(150) NOT NULL, answers_json TEXT NOT NULL DEFAULT '{}',
            status VARCHAR(30) NOT NULL DEFAULT 'draft', submitted_at TIMESTAMP WITHOUT TIME ZONE,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, UNIQUE(cycle_id, employee_key)
        );""" if pg else """CREATE TABLE IF NOT EXISTS maj_employee_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_id INTEGER NOT NULL, user_id INTEGER, employee_key TEXT NOT NULL,
            employee_name TEXT NOT NULL, role_title TEXT NOT NULL, answers_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'draft', submitted_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(cycle_id, employee_key)
        );"""
        for stmt in [cycle_tbl, rep_tbl]:
            try:
                conn.executescript(stmt)
                conn.commit()
            except Exception as e:
                logger.debug("Schema stmt notice: %s", e)
        _reports_schema_ensured = True


def get_or_create_current_cycle() -> Dict[str, Any]:
    """Retorna o ciclo semanal ativo corrente ou cria um novo para a semana atual."""
    ensure_reports_schema()
    now = datetime.now()
    iso_year, iso_week, _ = now.isocalendar()
    cycle_code = f"{iso_year}-W{iso_week:02d}"

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        cur = conn.execute(
            f"SELECT * FROM maj_report_cycles WHERE cycle_code = {placeholder} LIMIT 1",
            (cycle_code,)
        )
        row = cur.fetchone()
        if row:
            return dict(row)

        # Calcula a data de início (Segunda-feira) e deadline padrão (Sexta-feira 18:00)
        # weekday(): Monday is 0, Sunday is 6
        monday = now - timedelta(days=now.weekday())
        monday_str = monday.strftime("%Y-%m-%d")

        friday = monday + timedelta(days=4)
        deadline = datetime(friday.year, friday.month, friday.day, 18, 0, 0)
        title = f"Ciclo Semanal {iso_week:02d}/{iso_year}"

        if pg:
            conn.execute(
                """INSERT INTO maj_report_cycles (cycle_code, title, start_date, deadline, is_active)
                   VALUES (%s, %s, %s, %s, TRUE)""",
                (cycle_code, title, monday_str, deadline)
            )
        else:
            conn.execute(
                """INSERT INTO maj_report_cycles (cycle_code, title, start_date, deadline, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (cycle_code, title, monday_str, deadline.strftime("%Y-%m-%d %H:%M:%S"))
            )
        conn.commit()

        cur2 = conn.execute(
            f"SELECT * FROM maj_report_cycles WHERE cycle_code = {placeholder} LIMIT 1",
            (cycle_code,)
        )
        new_row = cur2.fetchone()
        return dict(new_row) if new_row else {}


def update_cycle_deadline(cycle_id: int, new_deadline_str: str) -> bool:
    """Atualiza o prazo final de entrega de um ciclo específico."""
    ensure_reports_schema()
    try:
        # Tenta interpretar formato ISO ou datetime padrão
        cleaned_str = new_deadline_str.replace("T", " ")
        if len(cleaned_str) == 16:
            cleaned_str += ":00"
        parsed_dt = datetime.fromisoformat(cleaned_str)

        with db() as conn:
            pg = _is_pg(conn)
            placeholder = "%s" if pg else "?"
            val = parsed_dt if pg else parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                f"UPDATE maj_report_cycles SET deadline = {placeholder} WHERE id = {placeholder}",
                (val, cycle_id)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.error("Erro ao atualizar prazo do ciclo %s: %s", cycle_id, e)
        return False


def get_all_cycles() -> List[Dict[str, Any]]:
    """Retorna todos os ciclos ordenados do mais recente para o mais antigo."""
    ensure_reports_schema()
    with db() as conn:
        rows = conn.execute("SELECT * FROM maj_report_cycles ORDER BY start_date DESC, id DESC").fetchall()
        return [dict(r) for r in rows]


def get_employee_history(employee_key: str) -> List[Dict[str, Any]]:
    """Retorna o histórico de relatórios submetidos por um colaborador em todos os ciclos."""
    ensure_reports_schema()
    meta = get_reporting_employee_meta(employee_key)
    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"
        sql = f"""SELECT r.*, c.cycle_code, c.title as cycle_title, c.start_date, c.deadline
            FROM maj_employee_reports r
            JOIN maj_report_cycles c ON r.cycle_id = c.id
            WHERE r.employee_key = {ph}
            ORDER BY c.start_date DESC, c.id DESC"""
        rows = conn.execute(sql, (employee_key.lower().strip(),)).fetchall()
        history = []
        for r in rows:
            d = dict(r)
            try:
                ans = json.loads(d.get("answers_json") or "{}")
            except Exception:
                ans = {}
            d["answers"] = ans
            sub = d.get("submitted_at")
            d["submitted_at_fmt"] = sub.strftime("%d/%m/%Y às %H:%M") if hasattr(sub, "strftime") else (str(sub)[:16] if sub else "")
            q_list = []
            if meta:
                for q in meta.get("questions", []):
                    qid = q["id"]
                    q_list.append({
                        "id": qid,
                        "label": q.get("label", qid),
                        "help": q.get("help", ""),
                        "answer": (ans.get(qid) or "").strip(),
                    })
            d["questions"] = q_list
            history.append(d)
        return history


def get_employee_report(cycle_id: int, employee_key: str) -> Dict[str, Any]:
    """Recupera a submissão de um colaborador para determinado ciclo."""
    ensure_reports_schema()
    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"
        cur = conn.execute(
            f"SELECT * FROM maj_employee_reports WHERE cycle_id = {placeholder} AND employee_key = {placeholder} LIMIT 1",
            (cycle_id, employee_key.lower().strip())
        )
        row = cur.fetchone()
        if not row:
            return {}
        data = dict(row)
        if isinstance(data.get("answers_json"), str):
            try:
                data["answers"] = json.loads(data["answers_json"])
            except Exception:
                data["answers"] = {}
        else:
            data["answers"] = data.get("answers_json") or {}
        return data


def save_or_submit_report(
    cycle_id: int,
    user_id: Optional[int],
    employee_key: str,
    answers: Dict[str, Any],
    is_draft: bool = False
) -> Dict[str, Any]:
    """Salva como rascunho ou submete oficialmente o relatório do colaborador."""
    ensure_reports_schema()
    meta = get_reporting_employee_meta(employee_key)
    if not meta:
        raise ValueError(f"Colaborador inválido: {employee_key}")

    now = datetime.now()
    answers_str = json.dumps(answers, ensure_ascii=False)

    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"

        # Busca dados do ciclo para checar prazo
        cur_c = conn.execute(
            f"SELECT * FROM maj_report_cycles WHERE id = {placeholder} LIMIT 1",
            (cycle_id,)
        )
        cycle = cur_c.fetchone()
        deadline = cycle["deadline"] if cycle else now

        # Define status
        if is_draft:
            status = "draft"
            submitted_at = None
        else:
            # Se for datetime parseado ou string
            deadline_dt = deadline
            if isinstance(deadline, str):
                try:
                    deadline_dt = datetime.fromisoformat(deadline.replace("T", " "))
                except Exception:
                    deadline_dt = now

            if now > deadline_dt:
                status = "submitted_late"
            else:
                status = "submitted_on_time"
            submitted_at = now if pg else now.strftime("%Y-%m-%d %H:%M:%S")

        # Verifica se já existe registro
        cur_r = conn.execute(
            f"SELECT id, submitted_at FROM maj_employee_reports WHERE cycle_id = {placeholder} AND employee_key = {placeholder} LIMIT 1",
            (cycle_id, employee_key)
        )
        existing = cur_r.fetchone()

        if existing:
            # Se já estava submetido e é rascunho, preserva a submissão original
            final_submitted_at = submitted_at if submitted_at else existing.get("submitted_at")
            final_status = status if not is_draft else ("draft" if not existing.get("submitted_at") else "submitted_on_time")

            up_sql = f"""
                UPDATE maj_employee_reports
                SET user_id = {placeholder},
                    answers_json = {placeholder},
                    status = {placeholder},
                    submitted_at = {placeholder},
                    updated_at = {placeholder}
                WHERE id = {placeholder}
            """
            conn.execute(
                up_sql,
                (user_id, answers_str, final_status, final_submitted_at, now, existing["id"])
            )
        else:
            ins_sql = f"""
                INSERT INTO maj_employee_reports
                (cycle_id, user_id, employee_key, employee_name, role_title, answers_json, status, submitted_at, updated_at)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """
            conn.execute(
                ins_sql,
                (cycle_id, user_id, employee_key, meta["name"], meta["role_title"], answers_str, status, submitted_at, now)
            )

        conn.commit()

    return get_employee_report(cycle_id, employee_key)


def get_cycle_submissions_summary(cycle_id: int) -> Dict[str, Any]:
    """Gera resumo consolidado das entregas para o Dashboard da Diretoria/Gerência."""
    ensure_reports_schema()
    with db() as conn:
        pg = _is_pg(conn)
        placeholder = "%s" if pg else "?"

        cur_c = conn.execute(f"SELECT * FROM maj_report_cycles WHERE id = {placeholder} LIMIT 1", (cycle_id,))
        cycle_row = cur_c.fetchone()
        cycle = dict(cycle_row) if cycle_row else {}

        cur_r = conn.execute(f"SELECT * FROM maj_employee_reports WHERE cycle_id = {placeholder}", (cycle_id,))
        reports_map = {r["employee_key"]: dict(r) for r in cur_r.fetchall()}

    doc_links_map = {}
    try:
        from services.employee_doc_importer_service import get_all_doc_links
        doc_links_map = get_all_doc_links()
    except Exception:
        pass

    deadline = cycle.get("deadline")
    deadline_str = ""
    if isinstance(deadline, datetime):
        deadline_str = deadline.strftime("%d/%m/%Y às %H:%M")
    elif deadline:
        deadline_str = str(deadline)[:16]

    items = []
    counts = {
        "total": len(REPORTING_EMPLOYEES),
        "submitted_on_time": 0,
        "submitted_late": 0,
        "draft": 0,
        "pending": 0,
    }

    for key, meta in REPORTING_EMPLOYEES.items():
        rep = reports_map.get(key)
        answers = {}
        if rep:
            try:
                answers = json.loads(rep.get("answers_json") or "{}")
            except Exception:
                answers = {}

        # Determina estado
        status = rep.get("status") if rep else "pending"
        submitted_at = rep.get("submitted_at") if rep else None

        status_map = {
            "submitted_on_time": ("Enviado no Prazo", "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30", "✅"),
            "submitted_late": ("Enviado com Atraso", "bg-amber-500/10 text-amber-400 border border-amber-500/30", "⚠️"),
            "draft": ("Rascunho Salvo", "bg-sky-500/10 text-sky-400 border border-sky-500/30", "📝"),
        }
        status_label, badge_class, icon = status_map.get(status, ("Pendente", "bg-rose-500/10 text-rose-400 border border-rose-500/30", "⏳"))
        counts[status if status in counts else "pending"] += 1

        # Percentual de respostas preenchidas
        total_q = len(meta.get("questions", []))
        answered_q = sum(1 for q in meta.get("questions", []) if (answers.get(q["id"]) or "").strip())
        progress_pct = int((answered_q / total_q) * 100) if total_q else 0

        # Link do WhatsApp
        wa_url = generate_whatsapp_charge_url(
            employee_name=meta["name"],
            phone=meta.get("phone", ""),
            cycle_title=cycle.get("title", "Semana Atual"),
            deadline_str=deadline_str or "Sexta-feira 18h",
            status_label=status_label
        )

        # Formatação amigável de data e lista estruturada de perguntas com respostas
        submitted_at_fmt = ""
        if submitted_at:
            submitted_at_fmt = submitted_at.strftime("%d/%m/%Y às %H:%M") if hasattr(submitted_at, "strftime") else str(submitted_at)

        q_list = []
        for q in meta.get("questions", []):
            qid = q["id"]
            q_list.append({
                "id": qid,
                "label": q.get("label", qid),
                "help": q.get("help", ""),
                "answer": (answers.get(qid) or "").strip(),
            })

        items.append({
            "key": key,
            "name": meta["name"],
            "role_title": meta["role_title"],
            "area": meta["area"],
            "badge": meta["badge"],
            "badge_color": meta["badge_color"],
            "status": status,
            "status_label": status_label,
            "badge_class": badge_class,
            "icon": icon,
            "submitted_at": submitted_at_fmt,
            "answered_count": answered_q,
            "total_questions": total_q,
            "progress_percent": progress_pct,
            "whatsapp_url": wa_url,
            "answers": answers,
            "questions": q_list,
            "history": get_employee_history(key),
            "google_doc_url": (rep.get("google_doc_url") if rep else None) or doc_links_map.get(key, {}).get("google_doc_url", ""),
            "uses_google_doc": (key != "fauzer"),
        })

    total_submitted = counts["submitted_on_time"] + counts["submitted_late"]
    on_time_pct = int((counts["submitted_on_time"] / counts["total"]) * 100) if counts["total"] else 0
    total_completion_pct = int((total_submitted / counts["total"]) * 100) if counts["total"] else 0

    return {
        "cycle": cycle,
        "deadline_str": deadline_str,
        "counts": counts,
        "total_submitted": total_submitted,
        "on_time_percent": on_time_pct,
        "completion_percent": total_completion_pct,
        "employees": items,
    }


def get_monday_consolidation_briefing(cycle_id: int) -> Dict[str, Any]:
    """Monta o briefing executivo consolidado para a reunião de segunda-feira (Jam + Geysa + Fauzer)."""
    summary = get_cycle_submissions_summary(cycle_id)
    emp_map = {e["key"]: e for e in summary["employees"]}

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
        ("4. Voz do Cliente, Vendas & Objeções", "Luiza & Gabriel", "COMERCIAL", "emerald", "luiza", [
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
