"""
M-One Support Items & Multi-Sector Service (services/support_items_service.py)
Gerencia o desdobramento de chamados em checklist de sub-tarefas (Alteração 1, 2, 3...)
e a seleção dinâmica multi-setor (Atacado, Outlet, Showroom, etc.).
Anti-monólito estrito: < 500 linhas.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.user_permission_service import user_has_permission_check

logger = logging.getLogger(__name__)

_items_schema_ensured = False


def _is_pg(conn) -> bool:
    return hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"


def ensure_support_items_schema() -> None:
    """Garante a coluna modules_json e a tabela support_ticket_items no banco."""
    global _items_schema_ensured
    if _items_schema_ensured:
        return

    with db() as conn:
        pg = _is_pg(conn)
        serial_pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        ts_type = "TIMESTAMP WITHOUT TIME ZONE"

        # 1. Garante coluna modules_json em support_tickets
        try:
            conn.execute("ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS modules_json TEXT DEFAULT '[]';")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        # 2. Cria tabela de itens/checklist de alterações
        sql_items = f"""
        CREATE TABLE IF NOT EXISTS support_ticket_items (
            id {serial_pk},
            ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
            item_order INTEGER NOT NULL DEFAULT 1,
            title TEXT NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            completed_at {ts_type}
        );
        """
        conn.execute(sql_items)

        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_support_items_ticket_id ON support_ticket_items(ticket_id);")
        except Exception as e:
            logger.debug("Índice de items de suporte já existente: %s", e)

        conn.commit()
        _items_schema_ensured = True


def get_available_modules_for_user(user: Dict[str, Any]) -> List[Dict[str, str]]:
    """Retorna os módulos operacionais elegíveis para o usuário abrir chamados."""
    public_modules = [
        {"key": "atacado", "label": "🏢 MAJ Atacado CNPJ (/atacado)"},
        {"key": "outlet", "label": "🏷️ Outlet MAJ (/outlet)"},
        {"key": "showroom", "label": "🛵 Modelos & Showroom (/show-room)"},
        {"key": "custom_catalog", "label": "📋 Catálogos Personalizados (/c/<slug>)"},
    ]

    operational_catalog = [
        ("vendas", "💼 Vendas & Pedidos"),
        ("stock", "📦 Estoque & Pátio de Chassis"),
        ("freight", "🚚 Fretes & Expedição"),
        ("imports", "🚢 Importações & Faturas China"),
        ("finance", "💰 Financeiro & Contas"),
        ("fiscal_pricing", "⚖️ Fiscal & Precificação"),
        ("mpay", "💳 M-Pay Cobranças"),
        ("copilot", "⚡ Copilot IA Assistente"),
        ("prospector", "🎯 Prospecção Contínua"),
        ("radar", "📡 Radar de Mercado"),
        ("users", "👥 Usuários & Permissões"),
        ("employee_portal", "📝 Meu Relatório Semanal"),
    ]

    result: List[Dict[str, str]] = list(public_modules)
    role = str(user.get("role") or "").lower()

    for key, label in operational_catalog:
        if role in ("admin", "support") or user_has_permission_check(user, key):
            result.append({"key": key, "label": label})

    general_modules = [
        {"key": "geral_login", "label": "🔑 Acesso, Login e Senha"},
        {"key": "geral_visual", "label": "🎨 Interface, Visual e Telas"},
        {"key": "sugestao", "label": "💡 Sugestão de Novo Recurso / Melhoria"},
        {"key": "outro", "label": "❓ Outro Assunto"},
    ]
    result.extend(general_modules)
    return result


def parse_ticket_modules(ticket: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extrai a lista de setores afetados a partir do modules_json ou do fallback legado."""
    raw = ticket.get("modules_json")
    if raw:
        if isinstance(raw, list):
            return raw
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception:
            pass

    # Fallback para chamados legados de setor único
    key = ticket.get("module_key") or "geral"
    label = ticket.get("module_label") or "Geral"
    return [{"key": key, "label": label}]


def save_ticket_items(conn, ticket_id: int, items_list: List[str]) -> None:
    """Insere a lista de alterações estruturadas na tabela de sub-itens."""
    if not items_list:
        return

    pg = _is_pg(conn)
    ins_sql = """
    INSERT INTO support_ticket_items (ticket_id, item_order, title, completed)
    VALUES (%s, %s, %s, FALSE);
    """ if pg else """
    INSERT INTO support_ticket_items (ticket_id, item_order, title, completed)
    VALUES (?, ?, ?, 0);
    """

    order = 1
    for raw_text in items_list:
        text = str(raw_text or "").strip()
        if text:
            conn.execute(ins_sql, (ticket_id, order, text))
            order += 1


def get_ticket_items(ticket_id: int) -> List[Dict[str, Any]]:
    """Recupera todos os sub-itens/alterações de um chamado ordenados."""
    ensure_support_items_schema()
    with db() as conn:
        pg = _is_pg(conn)
        sql = """
        SELECT id, ticket_id, item_order, title, completed, completed_at
        FROM support_ticket_items
        WHERE ticket_id = %s
        ORDER BY item_order ASC, id ASC;
        """ if pg else """
        SELECT id, ticket_id, item_order, title, completed, completed_at
        FROM support_ticket_items
        WHERE ticket_id = ?
        ORDER BY item_order ASC, id ASC;
        """
        rows = conn.execute(sql, (ticket_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["completed"] = bool(d.get("completed"))
            result.append(d)
        return result


def toggle_ticket_item(ticket_id: int, item_id: int, completed: Optional[bool] = None) -> Dict[str, Any]:
    """Alterna ou define o status de conclusão de uma alteração e audita conclusão geral."""
    ensure_support_items_schema()
    with db() as conn:
        pg = _is_pg(conn)
        # 1. Recupera estado atual
        chk_sql = "SELECT id, completed FROM support_ticket_items WHERE id = %s AND ticket_id = %s;" if pg else "SELECT id, completed FROM support_ticket_items WHERE id = ? AND ticket_id = ?;"
        row = conn.execute(chk_sql, (item_id, ticket_id)).fetchone()
        if not row:
            return {"success": False, "error": "Item de alteração não encontrado."}

        current_val = bool(row["completed"] if (isinstance(row, dict) or hasattr(row, "keys")) else row[1])
        new_val = (not current_val) if completed is None else bool(completed)

        # 2. Atualiza item
        up_sql = """
        UPDATE support_ticket_items
        SET completed = %s,
            completed_at = (CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END)
        WHERE id = %s AND ticket_id = %s;
        """ if pg else """
        UPDATE support_ticket_items
        SET completed = ?,
            completed_at = (CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END)
        WHERE id = ? AND ticket_id = ?;
        """
        conn.execute(up_sql, (new_val, new_val, item_id, ticket_id))

        # 3. Calcula total e concluídos
        stats_sql = """
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN completed IS TRUE THEN 1 ELSE 0 END) AS completed_count
        FROM support_ticket_items
        WHERE ticket_id = %s;
        """ if pg else """
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_count
        FROM support_ticket_items
        WHERE ticket_id = ?;
        """
        stats_row = conn.execute(stats_sql, (ticket_id,)).fetchone()
        total = int(stats_row["total"] if (isinstance(stats_row, dict) or hasattr(stats_row, "keys")) else (stats_row[0] or 0))
        done = int(stats_row["completed_count"] if (isinstance(stats_row, dict) or hasattr(stats_row, "keys")) else (stats_row[1] or 0))

        conn.commit()

        return {
            "success": True,
            "item_id": item_id,
            "completed": new_val,
            "total_items": total,
            "completed_items": done,
            "all_completed": (total > 0 and done == total),
        }
