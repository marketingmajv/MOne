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
        if pg:
            stmts = [
                """CREATE TABLE IF NOT EXISTS maj_report_cycles (
                    id SERIAL PRIMARY KEY,
                    cycle_code VARCHAR(30) UNIQUE NOT NULL,
                    title VARCHAR(150) NOT NULL,
                    start_date VARCHAR(30) NOT NULL,
                    deadline TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );""",
                """CREATE TABLE IF NOT EXISTS maj_employee_reports (
                    id SERIAL PRIMARY KEY,
                    cycle_id INTEGER NOT NULL,
                    user_id INTEGER,
                    employee_key VARCHAR(50) NOT NULL,
                    employee_name VARCHAR(100) NOT NULL,
                    role_title VARCHAR(150) NOT NULL,
                    answers_json TEXT NOT NULL DEFAULT '{}',
                    status VARCHAR(30) NOT NULL DEFAULT 'draft',
                    submitted_at TIMESTAMP WITHOUT TIME ZONE,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(cycle_id, employee_key)
                );"""
            ]
            for s in stmts:
                try:
                    conn.executescript(s)
                    conn.commit()
                except Exception as e:
                    logger.debug("Schema stmt notice: %s", e)
        else:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS maj_report_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                start_date TEXT NOT NULL,
                deadline TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS maj_employee_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                user_id INTEGER,
                employee_key TEXT NOT NULL,
                employee_name TEXT NOT NULL,
                role_title TEXT NOT NULL,
                answers_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'draft',
                submitted_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(cycle_id, employee_key)
            );
            """
            try:
                conn.executescript(schema_sql)
                conn.commit()
            except Exception as e:
                logger.warning("Erro ao criar schema SQLite de relatórios: %s", e)

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

        if status == "submitted_on_time":
            status_label = "Enviado no Prazo"
            badge_class = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
            icon = "✅"
            counts["submitted_on_time"] += 1
        elif status == "submitted_late":
            status_label = "Enviado com Atraso"
            badge_class = "bg-amber-500/10 text-amber-400 border border-amber-500/30"
            icon = "⚠️"
            counts["submitted_late"] += 1
        elif status == "draft":
            status_label = "Rascunho Salvo"
            badge_class = "bg-sky-500/10 text-sky-400 border border-sky-500/30"
            icon = "📝"
            counts["draft"] += 1
        else:
            status = "pending"
            status_label = "Pendente"
            badge_class = "bg-rose-500/10 text-rose-400 border border-rose-500/30"
            icon = "⏳"
            counts["pending"] += 1

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
            "submitted_at": submitted_at,
            "answered_count": answered_q,
            "total_questions": total_q,
            "progress_percent": progress_pct,
            "whatsapp_url": wa_url,
            "answers": answers,
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
    critical_fronts = [
        {
            "front_title": "1. Faturamento, Caixa & Conciliação",
            "owner": "Marisa",
            "badge": "FINANCEIRO",
            "badge_color": "green",
            "employee_data": emp_map.get("marisa"),
            "key_highlights": [
                {"label": "Faturamento Relevante", "answer": emp_map.get("marisa", {}).get("answers", {}).get("faturamento_nfs")},
                {"label": "Entradas Pendentes", "answer": emp_map.get("marisa", {}).get("answers", {}).get("entradas_pendentes")},
                {"label": "Contas para Geysa", "answer": emp_map.get("marisa", {}).get("answers", {}).get("contas_vencimentos")},
                {"label": "Piloto Mercado Pago", "answer": emp_map.get("marisa", {}).get("answers", {}).get("piloto_mercado_pago")},
            ]
        },
        {
            "front_title": "2. Estoque Físico, Galpões & Divergências",
            "owner": "Jhon",
            "badge": "ESTOQUE",
            "badge_color": "amber",
            "employee_data": emp_map.get("jhon"),
            "key_highlights": [
                {"label": "Contagem de Sexta", "answer": emp_map.get("jhon", {}).get("answers", {}).get("contagem_rotativa")},
                {"label": "Divergências Investigadas", "answer": emp_map.get("jhon", {}).get("answers", {}).get("divergencias")},
                {"label": "NFs de Demonstração", "answer": emp_map.get("jhon", {}).get("answers", {}).get("nfs_demonstracao")},
                {"label": "Código de Barras", "answer": emp_map.get("jhon", {}).get("answers", {}).get("codigo_barras")},
            ]
        },
        {
            "front_title": "3. Oficina Técnica, Produtividade & Falhas",
            "owner": "Ricardo",
            "badge": "OFICINA",
            "badge_color": "cyan",
            "employee_data": emp_map.get("ricardo"),
            "key_highlights": [
                {"label": "Serviços Liberados", "answer": emp_map.get("ricardo", {}).get("answers", {}).get("servicos_concluidos")},
                {"label": "OS Atrasadas / Pendentes", "answer": emp_map.get("ricardo", {}).get("answers", {}).get("os_pendentes")},
                {"label": "Retrabalhos", "answer": emp_map.get("ricardo", {}).get("answers", {}).get("retrabalhos")},
                {"label": "Defeitos Recorrentes", "answer": emp_map.get("ricardo", {}).get("answers", {}).get("defeitos_recorrentes")},
                {"label": "Peças & Ferramentas", "answer": emp_map.get("ricardo", {}).get("answers", {}).get("necessidade_pecas")},
            ]
        },
        {
            "front_title": "4. Voz do Cliente, Vendas & Objeções",
            "owner": "Luiza & Gabriel",
            "badge": "COMERCIAL",
            "badge_color": "emerald",
            "employee_data": emp_map.get("luiza"),
            "key_highlights": [
                {"label": "Modelos Mais Procurados", "answer": emp_map.get("luiza", {}).get("answers", {}).get("modelos_procurados")},
                {"label": "Objeções Comerciais", "answer": emp_map.get("luiza", {}).get("answers", {}).get("objecoes_perdas")},
                {"label": "Preços Considerados Altos", "answer": emp_map.get("luiza", {}).get("answers", {}).get("precos_altos")},
                {"label": "Sugestão da Semana", "answer": emp_map.get("luiza", {}).get("answers", {}).get("sugestao_comercial")},
                {"label": "Atacado B2B (Gabriel)", "answer": emp_map.get("gabriel", {}).get("answers", {}).get("resultados_comerciais")},
            ]
        },
        {
            "front_title": "5. Pós-Venda, Garantias & Clientes Sensíveis",
            "owner": "Léo",
            "badge": "PÓS-VENDA",
            "badge_color": "blue",
            "employee_data": emp_map.get("leo"),
            "key_highlights": [
                {"label": "OS Pós-Venda", "answer": emp_map.get("leo", {}).get("answers", {}).get("os_abertas_concluidas")},
                {"label": "Clientes Sensíveis / 48h+", "answer": emp_map.get("leo", {}).get("answers", {}).get("clientes_sensiveis")},
                {"label": "Concessões Utilizadas", "answer": emp_map.get("leo", {}).get("answers", {}).get("concessoes_utilizadas")},
                {"label": "Decisões da Gerência", "answer": emp_map.get("leo", {}).get("answers", {}).get("decisoes_necessarias")},
            ]
        },
        {
            "front_title": "6. Sistemas, Marketing & Desvios de Processo",
            "owner": "Fauzer",
            "badge": "SISTEMAS",
            "badge_color": "purple",
            "employee_data": emp_map.get("fauzer"),
            "key_highlights": [
                {"label": "Marketing & CPL", "answer": emp_map.get("fauzer", {}).get("answers", {}).get("marketing_investimento")},
                {"label": "Sistemas & Bling/M-One", "answer": emp_map.get("fauzer", {}).get("answers", {}).get("processos_sistemas")},
                {"label": "Falhas & Desvios", "answer": emp_map.get("fauzer", {}).get("answers", {}).get("falhas_desvios")},
                {"label": "Decisões para Jam & Geysa", "answer": emp_map.get("fauzer", {}).get("answers", {}).get("pontos_decisao_diretoria")},
            ]
        }
    ]

    return {
        "cycle": summary["cycle"],
        "deadline_str": summary["deadline_str"],
        "summary": summary,
        "fronts": critical_fronts,
    }
