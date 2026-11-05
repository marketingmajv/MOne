"""
M-One Support & Tickets Service (services/support_service.py)
Gerencia a Central de Suporte, chamados de erro/alteração com prints (Ctrl+V),
timeline de mensagens, alertas de urgência multicanal e notificações WhatsApp.
Anti-monólito estrito: < 500 linhas.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.support_items_service import (
    ensure_support_items_schema,
    get_available_modules_for_user,
    get_ticket_items,
    parse_ticket_modules,
    save_ticket_items,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SUPPORT_UPLOAD_DIR = Path("/tmp/uploads/support") if os.environ.get("VERCEL") else (BASE_DIR / "uploads" / "support")

try:
    SUPPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    logger.debug("Support upload dir mkdir warning: %s", e)

FAUZER_PHONE = "27999157162"
_support_schema_ensured = False


def _is_pg(conn) -> bool:
    return hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"


def _fmt_dt(val: Any) -> str:
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y %H:%M")
    if isinstance(val, str) and val:
        return val[:16].replace("T", " ")
    return ""


def _resolve_valid_attachments(raw_atts: Any) -> Tuple[List[str], int]:
    """Filtra anexos válidos, converte arquivos locais legados em Data URI e descarta links /tmp expirados."""
    if isinstance(raw_atts, str):
        try:
            att_list = json.loads(raw_atts)
        except Exception:
            att_list = []
    elif isinstance(raw_atts, list):
        att_list = raw_atts
    else:
        att_list = []

    valid: List[str] = []
    expired_count = 0
    for att in att_list:
        if not isinstance(att, str) or not att.strip():
            continue
        s = att.strip()
        if s.startswith("data:image/"):
            valid.append(s)
        elif s.startswith("/uploads/support/"):
            fname = s.split("/uploads/support/", 1)[1]
            candidate = SUPPORT_UPLOAD_DIR / fname
            if not candidate.exists():
                candidate = BASE_DIR / "uploads" / "support" / fname
            if candidate.exists():
                try:
                    b64 = base64.b64encode(candidate.read_bytes()).decode("ascii")
                    valid.append(f"data:image/webp;base64,{b64}")
                except Exception:
                    expired_count += 1
            else:
                expired_count += 1
        elif s.startswith(("http://", "https://", "/static/", "/public/")):
            valid.append(s)
    return valid, expired_count


def ensure_support_schema() -> None:
    """Garante a existência das tabelas de suporte no Supabase PostgreSQL / SQLite."""
    global _support_schema_ensured
    if _support_schema_ensured:
        return

    with db() as conn:
        pg = _is_pg(conn)
        serial_pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        ts_type = "TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        json_type = "JSONB DEFAULT '[]'::jsonb" if pg else "TEXT DEFAULT '[]'"

        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id {serial_pk},
            ticket_code VARCHAR(30) UNIQUE NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id),
            module_key VARCHAR(100) NOT NULL,
            module_label VARCHAR(150) NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            urgency VARCHAR(30) DEFAULT 'urgente',
            status VARCHAR(30) DEFAULT 'pendente',
            resolution_notes TEXT DEFAULT '',
            created_at {ts_type},
            updated_at {ts_type},
            resolved_at TIMESTAMP WITHOUT TIME ZONE
        );
        """)
        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS support_ticket_messages (
            id {serial_pk},
            ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
            sender_id INTEGER NOT NULL REFERENCES users(id),
            is_staff BOOLEAN DEFAULT FALSE,
            message_text TEXT NOT NULL,
            attachments {json_type},
            created_at {ts_type},
            read_by_user BOOLEAN DEFAULT FALSE,
            read_by_staff BOOLEAN DEFAULT FALSE
        );
        """)
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_support_messages_ticket_id ON support_ticket_messages(ticket_id);")
        except Exception as e:
            logger.debug("Índices de suporte já existentes: %s", e)

        conn.commit()
        _support_schema_ensured = True
    ensure_support_items_schema()


def _generate_ticket_code(conn) -> str:
    """Gera código amigável incremental anual para o chamado: SUP-2026-0001."""
    year = datetime.now().year
    pg = _is_pg(conn)
    sql = "SELECT COUNT(*) AS total FROM support_tickets WHERE ticket_code LIKE %s" if pg else "SELECT COUNT(*) AS total FROM support_tickets WHERE ticket_code LIKE ?"
    row = conn.execute(sql, (f"SUP-{year}-%",)).fetchone()
    raw_val = row["total"] if (isinstance(row, dict) or hasattr(row, "keys")) else (row[0] if row else 0)
    return f"SUP-{year}-{int(raw_val or 0) + 1:04d}"


def save_support_attachment(data_or_file: Any) -> Optional[str]:
    """Salva arquivo de imagem/print vindo de upload ou Base64 (Ctrl+V) como Data URI WebP persistente."""
    try:
        from PIL import Image

        if isinstance(data_or_file, str) and "base64," in data_or_file:
            _, encoded = data_or_file.split("base64,", 1)
            img = Image.open(io.BytesIO(base64.b64decode(encoded)))
        elif hasattr(data_or_file, "read"):
            img = Image.open(data_or_file)
        else:
            return None

        img = img.convert("RGBA") if (img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)) else img.convert("RGB")
        if max(img.size) > 1600:
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=82, method=6)
        webp_bytes = buf.getvalue()

        try:
            SUPPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            filename = f"print_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.webp"
            (SUPPORT_UPLOAD_DIR / filename).write_bytes(webp_bytes)
        except Exception:
            pass

        return f"data:image/webp;base64,{base64.b64encode(webp_bytes).decode('ascii')}"
    except Exception as e:
        logger.error("Erro ao salvar anexo de suporte: %s", e, exc_info=True)
        return None


def _notify_fauzer_whatsapp(ticket_code: str, user_name: str, module_label: str, title: str, urgency: str) -> None:
    """Dispara alerta imediato no WhatsApp do Fauzer sobre chamado urgente aberto."""
    try:
        from services.maintenance_service import send_whatsapp_message_botconversa
        msg = (
            f"🚨 *NOVO CHAMADO DE SUPORTE M-ONE*\n\n"
            f"📌 *Código:* {ticket_code}\n"
            f"👤 *Solicitante:* {user_name}\n"
            f"📍 *Área/Módulo:* {module_label}\n"
            f"⚡ *Urgência:* {urgency.upper()}\n"
            f"📝 *Título:* {title}\n\n"
            f"👉 *Acessar Painel:* https://m-one.majmobilidade.com.br/admin/suporte"
        )
        send_whatsapp_message_botconversa(phone=FAUZER_PHONE, text=msg, first_name="Fauzer")
    except Exception as e:
        logger.warning("Falha ao enviar notificação WhatsApp para Fauzer: %s", e)


def create_ticket(
    user: Dict[str, Any],
    module_key: str,
    module_label: str,
    title: str,
    description: str,
    urgency: str = "urgente",
    attachments: Optional[List[str]] = None,
    notify_whatsapp: bool = True,
    modules: Optional[List[Dict[str, str]]] = None,
    items: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Abre um novo chamado com múltiplos setores e checklist de alterações."""
    ensure_support_schema()
    attachments = attachments or []
    items = items or []
    user_id = user["id"]
    user_name = user.get("name") or user.get("username") or "Colaborador"

    if modules:
        modules_json = json.dumps(modules, ensure_ascii=False)
        if not module_key and len(modules) > 0:
            module_key = modules[0].get("key", "geral")
        if not module_label and len(modules) > 0:
            module_label = ", ".join(m.get("label", "") for m in modules)
    else:
        modules_json = json.dumps([{"key": module_key, "label": module_label}], ensure_ascii=False)

    with db() as conn:
        pg = _is_pg(conn)
        ticket_code = _generate_ticket_code(conn)

        ins_t = """
        INSERT INTO support_tickets (ticket_code, user_id, module_key, module_label, title, description, urgency, status, modules_json, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendente', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id;
        """ if pg else """
        INSERT INTO support_tickets (ticket_code, user_id, module_key, module_label, title, description, urgency, status, modules_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
        """
        params = (ticket_code, user_id, module_key, module_label, title.strip(), description.strip(), urgency, modules_json)
        res = conn.execute(ins_t, params)
        if pg:
            ret_row = res.fetchone()
            ticket_id = ret_row["id"] if (isinstance(ret_row, dict) or hasattr(ret_row, "keys")) else ret_row[0]
        else:
            ticket_id = res.lastrowid

        save_ticket_items(conn, ticket_id, items)

        msg_text = description.strip() or f"Chamado aberto: {title.strip()}"
        att_json = json.dumps(attachments, ensure_ascii=False)
        ins_m = """
        INSERT INTO support_ticket_messages (ticket_id, sender_id, is_staff, message_text, attachments, created_at, read_by_user, read_by_staff)
        VALUES (%s, %s, FALSE, %s, %s, CURRENT_TIMESTAMP, TRUE, FALSE);
        """ if pg else """
        INSERT INTO support_ticket_messages (ticket_id, sender_id, is_staff, message_text, attachments, created_at, read_by_user, read_by_staff)
        VALUES (?, ?, 0, ?, ?, CURRENT_TIMESTAMP, 1, 0);
        """
        conn.execute(ins_m, (ticket_id, user_id, msg_text, att_json))
        conn.commit()

    if notify_whatsapp and not is_fauzer_user(user):
        _notify_fauzer_whatsapp(ticket_code, user_name, module_label, title, urgency)
    return {"success": True, "ticket_id": ticket_id, "ticket_code": ticket_code}


def list_tickets_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Lista todos os chamados abertos pelo colaborador autenticado."""
    ensure_support_schema()
    with db() as conn:
        pg = _is_pg(conn)
        sql = """
        SELECT t.*, 
               (SELECT COUNT(*) FROM support_ticket_messages m WHERE m.ticket_id = t.id) AS total_messages,
               (SELECT COUNT(*) FROM support_ticket_messages m WHERE m.ticket_id = t.id AND m.is_staff = TRUE AND m.read_by_user = FALSE) AS unread_replies
        FROM support_tickets t
        WHERE t.user_id = %s
        ORDER BY t.updated_at DESC;
        """ if pg else """
        SELECT t.*, 
               (SELECT COUNT(*) FROM support_ticket_messages m WHERE m.ticket_id = t.id) AS total_messages,
               (SELECT COUNT(*) FROM support_ticket_messages m WHERE m.ticket_id = t.id AND m.is_staff = 1 AND m.read_by_user = 0) AS unread_replies
        FROM support_tickets t
        WHERE t.user_id = ?
        ORDER BY t.updated_at DESC;
        """
        rows = conn.execute(sql, (user_id,)).fetchall()
        tickets = []
        for r in rows:
            d = dict(r)
            d["modules"] = parse_ticket_modules(d)
            tickets.append(d)
        return tickets


def list_all_tickets_for_admin(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todos os chamados da empresa para o painel de atendimento do Fauzer."""
    ensure_support_schema()
    with db() as conn:
        pg = _is_pg(conn)
        where_clauses = []
        params = []
        if status_filter and status_filter != "todos":
            where_clauses.append("t.status = %s" if pg else "t.status = ?")
            params.append(status_filter)

        where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"""
        SELECT t.*, u.name AS user_name, u.username, u.role AS user_role, u.phone AS user_phone,
               (SELECT COUNT(*) FROM support_ticket_messages m WHERE m.ticket_id = t.id) AS total_messages,
               (SELECT COUNT(*) FROM support_ticket_messages m WHERE m.ticket_id = t.id AND m.is_staff = FALSE AND m.read_by_staff = FALSE) AS unread_user_messages
        FROM support_tickets t
        JOIN users u ON t.user_id = u.id
        {where_str}
        ORDER BY 
            CASE WHEN t.status = 'pendente' THEN 1 
                 WHEN t.status = 'em_andamento' THEN 2 
                 ELSE 3 END,
            t.updated_at DESC;
        """
        rows = conn.execute(sql, tuple(params)).fetchall()
        tickets = []
        for r in rows:
            d = dict(r)
            d["modules"] = parse_ticket_modules(d)
            tickets.append(d)
        return tickets


def get_ticket_details(ticket_id: int, current_user_id: int, is_admin: bool = False) -> Optional[Dict[str, Any]]:
    """Recupera detalhes do chamado e timeline completa de mensagens, marcando como lidas."""
    ensure_support_schema()
    with db() as conn:
        pg = _is_pg(conn)
        sql_t = """
        SELECT t.*, u.name AS user_name, u.username, u.role AS user_role, u.phone AS user_phone
        FROM support_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.id = %s;
        """ if pg else """
        SELECT t.*, u.name AS user_name, u.username, u.role AS user_role, u.phone AS user_phone
        FROM support_tickets t
        JOIN users u ON t.user_id = u.id
        WHERE t.id = ?;
        """
        row_t = conn.execute(sql_t, (ticket_id,)).fetchone()
        if not row_t:
            return None
        ticket = dict(row_t)

        if not is_admin and ticket["user_id"] != current_user_id:
            return None

        if is_admin:
            up_read = "UPDATE support_ticket_messages SET read_by_staff = TRUE WHERE ticket_id = %s" if pg else "UPDATE support_ticket_messages SET read_by_staff = 1 WHERE ticket_id = ?"
        else:
            up_read = "UPDATE support_ticket_messages SET read_by_user = TRUE WHERE ticket_id = %s" if pg else "UPDATE support_ticket_messages SET read_by_user = 1 WHERE ticket_id = ?"
        conn.execute(up_read, (ticket_id,))
        conn.commit()

        sql_m = """
        SELECT m.*, u.name AS sender_name, u.username AS sender_username, u.role AS sender_role
        FROM support_ticket_messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.ticket_id = %s
        ORDER BY m.created_at ASC;
        """ if pg else """
        SELECT m.*, u.name AS sender_name, u.username AS sender_username, u.role AS sender_role
        FROM support_ticket_messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.ticket_id = ?
        ORDER BY m.created_at ASC;
        """
        msg_rows = conn.execute(sql_m, (ticket_id,)).fetchall()
        items = get_ticket_items(ticket_id)
        messages = []
        all_attachments: List[str] = []
        expired_attachments_total = 0
        desc_clean = str(ticket.get("description") or "").strip()

        for idx, r in enumerate(msg_rows):
            d = dict(r)
            valid_atts, expired_cnt = _resolve_valid_attachments(d.get("attachments"))
            d["attachments"] = valid_atts
            expired_attachments_total += expired_cnt

            for att in valid_atts:
                if att not in all_attachments:
                    all_attachments.append(att)

            d["created_at"] = _fmt_dt(d.get("created_at"))
            if idx == 0 and isinstance(d.get("message_text"), str):
                for marker in ("\n\n📋 Alterações:", "📋 Alterações Solicitadas:"):
                    if marker in d["message_text"]:
                        d["message_text"] = d["message_text"].split(marker)[0].strip()
                # Evita duplicar a 1ª mensagem automática quando já exibida no card superior do chamado
                msg_clean = d["message_text"].strip()
                if not d.get("is_staff") and (not msg_clean or msg_clean == desc_clean or msg_clean.startswith("Chamado aberto:")):
                    continue

            messages.append(d)

        ticket["created_at"] = _fmt_dt(ticket.get("created_at"))
        ticket["updated_at"] = _fmt_dt(ticket.get("updated_at"))
        ticket["resolved_at"] = _fmt_dt(ticket.get("resolved_at"))
        ticket["messages"] = messages
        ticket["modules"] = parse_ticket_modules(ticket)
        ticket["items"] = items
        ticket["all_attachments"] = all_attachments
        ticket["expired_attachments_count"] = expired_attachments_total
        return ticket


def add_ticket_reply(
    ticket_id: int,
    sender_id: int,
    is_staff: bool,
    message_text: str,
    attachments: Optional[List[str]] = None,
    new_status: Optional[str] = None,
    resolution_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Adiciona nova resposta à linha do tempo do chamado e atualiza status."""
    ensure_support_schema()
    attachments = attachments or []

    with db() as conn:
        pg = _is_pg(conn)
        att_json = json.dumps(attachments, ensure_ascii=False)
        read_user = True if not is_staff else False
        read_staff = True if is_staff else False

        ins = """
        INSERT INTO support_ticket_messages (ticket_id, sender_id, is_staff, message_text, attachments, created_at, read_by_user, read_by_staff)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s);
        """ if pg else """
        INSERT INTO support_ticket_messages (ticket_id, sender_id, is_staff, message_text, attachments, created_at, read_by_user, read_by_staff)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?);
        """
        conn.execute(ins, (ticket_id, sender_id, is_staff, message_text.strip(), att_json, read_user, read_staff))

        status_to_set = new_status or ("em_andamento" if is_staff else "pendente")
        resolved_clause = ", resolved_at = CURRENT_TIMESTAMP" if status_to_set == "resolvido" else ", resolved_at = NULL"
        up = f"""
        UPDATE support_tickets 
        SET status = %s, updated_at = CURRENT_TIMESTAMP {resolved_clause}
            {", resolution_notes = %s" if resolution_notes is not None else ""}
        WHERE id = %s;
        """ if pg else f"""
        UPDATE support_tickets 
        SET status = ?, updated_at = CURRENT_TIMESTAMP {resolved_clause}
            {", resolution_notes = ?" if resolution_notes is not None else ""}
        WHERE id = ?;
        """
        params: List[Any] = [status_to_set]
        if resolution_notes is not None:
            params.append(resolution_notes.strip())
        params.append(ticket_id)

        conn.execute(up, tuple(params))
        conn.commit()

    return {"success": True, "status": status_to_set}


def is_fauzer_user(user: Optional[Dict[str, Any]]) -> bool:
    """Verifica se o usuário autenticado é exclusivamente o Fauzer (responsável técnico pelo suporte)."""
    return bool(user and str(user.get("username") or "").strip().lower() == "fauzer")


def get_support_badges(user: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna contadores de badges reativos e estado de alerta urgente exclusivo do Fauzer."""
    ensure_support_schema()
    user_id = user["id"]
    is_fauzer = is_fauzer_user(user)

    with db() as conn:
        pg = _is_pg(conn)
        if is_fauzer:
            row = conn.execute("SELECT COUNT(*) AS total FROM support_tickets WHERE status = 'pendente';").fetchone()
            pending_count = int(row["total"] if (isinstance(row, dict) or hasattr(row, "keys")) else (row[0] if row else 0))

            urgent_row = conn.execute("""
            SELECT ticket_code, title, module_label, created_at 
            FROM support_tickets WHERE status = 'pendente' 
            ORDER BY created_at DESC LIMIT 1;
            """).fetchone()
            latest_urgent = dict(urgent_row) if urgent_row else None
            if latest_urgent and isinstance(latest_urgent.get("created_at"), datetime):
                latest_urgent["created_at"] = latest_urgent["created_at"].strftime("%d/%m %H:%M")

            return {
                "badge_count": pending_count,
                "has_urgent_pending": pending_count > 0,
                "latest_urgent": latest_urgent,
            }
        else:
            sql = """
            SELECT COUNT(*) AS total FROM support_ticket_messages m
            JOIN support_tickets t ON m.ticket_id = t.id
            WHERE t.user_id = %s AND m.is_staff = TRUE AND m.read_by_user = FALSE;
            """ if pg else """
            SELECT COUNT(*) AS total FROM support_ticket_messages m
            JOIN support_tickets t ON m.ticket_id = t.id
            WHERE t.user_id = ? AND m.is_staff = 1 AND m.read_by_user = 0;
            """
            row = conn.execute(sql, (user_id,)).fetchone()
            unread_count = int(row["total"] if (isinstance(row, dict) or hasattr(row, "keys")) else (row[0] if row else 0))
            return {"badge_count": unread_count, "has_urgent_pending": False, "latest_urgent": None}
