"""
M-One Custom Catalog Requests Service (services/custom_catalog_requests_service.py)
Gerenciamento de solicitações de novos catálogos personalizados enviadas por
vendedores externos e lojistas parceiros mediante código de convite comercial.
Conformidade estrita com limites anti-monólito (< 500 linhas).
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.custom_catalog_service import ensure_custom_catalogs_schema

logger = logging.getLogger(__name__)

DEFAULT_INVITE_CODE = "MAJ-PARCEIRO-2026"
_requests_schema_ensured = False


def _is_pg(conn) -> bool:
    return hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"


def _run_exec(conn, sql: str, params=()):
    if _is_pg(conn):
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def ensure_catalog_requests_schema():
    """Garante a existência da tabela de solicitações de catálogo e configurações."""
    global _requests_schema_ensured
    if _requests_schema_ensured:
        return

    ensure_custom_catalogs_schema()

    with db() as conn:
        pg = _is_pg(conn)
        
        # 1. Tabela de configurações dos catálogos
        settings_sql = """
        CREATE TABLE IF NOT EXISTS maj_catalog_settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        _run_exec(conn, settings_sql)

        # 2. Tabela de solicitações de catálogo
        if pg:
            table_sql = """
            CREATE TABLE IF NOT EXISTS maj_custom_catalog_requests (
                id SERIAL PRIMARY KEY,
                invite_code VARCHAR(100) NOT NULL DEFAULT '',
                applicant_name VARCHAR(150) NOT NULL,
                store_name VARCHAR(150) NOT NULL DEFAULT '',
                whatsapp_number VARCHAR(30) NOT NULL,
                city_state VARCHAR(100) NOT NULL DEFAULT '',
                suggested_slug VARCHAR(100) NOT NULL DEFAULT '',
                notes TEXT DEFAULT '',
                status VARCHAR(30) NOT NULL DEFAULT 'pendente',
                created_catalog_id INTEGER REFERENCES maj_custom_catalogs(id) ON DELETE SET NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP WITHOUT TIME ZONE,
                approved_by VARCHAR(100) DEFAULT ''
            );
            """
        else:
            table_sql = """
            CREATE TABLE IF NOT EXISTS maj_custom_catalog_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invite_code TEXT NOT NULL DEFAULT '',
                applicant_name TEXT NOT NULL,
                store_name TEXT NOT NULL DEFAULT '',
                whatsapp_number TEXT NOT NULL,
                city_state TEXT NOT NULL DEFAULT '',
                suggested_slug TEXT NOT NULL DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pendente',
                created_catalog_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP,
                approved_by TEXT DEFAULT '',
                FOREIGN KEY (created_catalog_id) REFERENCES maj_custom_catalogs(id) ON DELETE SET NULL
            );
            """
        _run_exec(conn, table_sql)

        # Tabela de tokens randômicos descartáveis (One-Time Tokens)
        if pg:
            tokens_table_sql = """
            CREATE TABLE IF NOT EXISTS maj_catalog_invite_tokens (
                id SERIAL PRIMARY KEY,
                token VARCHAR(64) UNIQUE NOT NULL,
                is_used BOOLEAN NOT NULL DEFAULT FALSE,
                used_at TIMESTAMP WITHOUT TIME ZONE,
                used_by_request_id INTEGER,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(100) DEFAULT 'system'
            );
            """
        else:
            tokens_table_sql = """
            CREATE TABLE IF NOT EXISTS maj_catalog_invite_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                is_used INTEGER NOT NULL DEFAULT 0,
                used_at TIMESTAMP,
                used_by_request_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'system'
            );
            """
        _run_exec(conn, tokens_table_sql)
        conn.commit()

    _requests_schema_ensured = True


def generate_one_time_token(prefix: str = "MAJ", created_by: str = "system") -> str:
    """Gera um token randômico único descartável (ex: MAJ-8F4K-9D2B) e registra no banco."""
    ensure_catalog_requests_schema()
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(10):
        part1 = "".join(secrets.choice(chars) for _ in range(4))
        part2 = "".join(secrets.choice(chars) for _ in range(4))
        token = f"{prefix}-{part1}-{part2}"
        try:
            with db() as conn:
                pg = _is_pg(conn)
                _run_exec(
                    conn,
                    "INSERT INTO maj_catalog_invite_tokens (token, is_used, created_by) VALUES (?, ?, ?)",
                    (token, False if pg else 0, created_by)
                )
                conn.commit()
                return token
        except Exception:
            continue

    # Fallback
    token = f"{prefix}-{secrets.token_hex(4).upper()}"
    with db() as conn:
        pg = _is_pg(conn)
        _run_exec(
            conn,
            "INSERT INTO maj_catalog_invite_tokens (token, is_used, created_by) VALUES (?, ?, ?)",
            (token, False if pg else 0, created_by)
        )
        conn.commit()
    return token


def validate_catalog_invite_token(token: str) -> Dict[str, Any]:
    """Valida se o token existe e ainda não foi utilizado."""
    clean_token = (token or "").strip().upper()
    if not clean_token:
        return {"valid": False, "reason": "Token de convite não informado."}

    # Código mestre configurado pelo admin (sempre válido)
    master_code = get_catalog_invite_code().strip().upper()
    if clean_token == master_code:
        return {"valid": True, "token": clean_token, "is_master": True}

    ensure_catalog_requests_schema()
    with db() as conn:
        row = _run_exec(
            conn,
            "SELECT id, token, is_used FROM maj_catalog_invite_tokens WHERE token = ?",
            (clean_token,)
        ).fetchone()
        if not row:
            return {"valid": False, "reason": "Código de convite ou token não encontrado."}

        is_used = row["is_used"] if isinstance(row, dict) else row[2]
        if bool(is_used):
            return {"valid": False, "reason": "Este token já foi utilizado e expirou após o uso."}

        return {"valid": True, "token": clean_token, "is_master": False}


def consume_catalog_invite_token(token: str, request_id: Optional[int] = None) -> bool:
    """Marca o token randômico como utilizado/expirado após o envio da requisição."""
    clean_token = (token or "").strip().upper()
    master_code = get_catalog_invite_code().strip().upper()
    if clean_token == master_code:
        return True

    ensure_catalog_requests_schema()
    with db() as conn:
        pg = _is_pg(conn)
        cursor = _run_exec(
            conn,
            """
            UPDATE maj_catalog_invite_tokens
            SET is_used = ?, used_at = CURRENT_TIMESTAMP, used_by_request_id = ?
            WHERE token = ? AND is_used = ?
            """,
            (True if pg else 1, request_id, clean_token, False if pg else 0)
        )
        conn.commit()
        return (cursor.rowcount or 0) > 0


def get_catalog_invite_code() -> str:
    """Recupera o código de convite geral configurado pelo Administrador."""
    ensure_catalog_requests_schema()
    try:
        with db() as conn:
            row = _run_exec(conn, "SELECT value FROM maj_catalog_settings WHERE key = ?", ("invite_code",)).fetchone()
            if row:
                val = (row["value"] if isinstance(row, dict) else row[0]) or ""
                val = str(val).strip()
                if val:
                    return val
    except Exception as e:
        logger.warning("Erro ao ler invite_code: %s", e)
    return DEFAULT_INVITE_CODE


def set_catalog_invite_code(code: str) -> str:
    """Atualiza o código de convite geral."""
    ensure_catalog_requests_schema()
    clean_code = (code or "").strip().upper()
    if not clean_code:
        clean_code = DEFAULT_INVITE_CODE
    with db() as conn:
        pg = _is_pg(conn)
        if pg:
            _run_exec(
                conn,
                """
                INSERT INTO maj_catalog_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """,
                ("invite_code", clean_code)
            )
        else:
            _run_exec(
                conn,
                """
                INSERT OR REPLACE INTO maj_catalog_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                ("invite_code", clean_code)
            )
        conn.commit()
    return clean_code


def validate_catalog_invite_code(input_code: str) -> bool:
    """Valida se o código de convite ou token fornecido é válido."""
    res = validate_catalog_invite_token(input_code)
    return bool(res.get("valid"))


def create_catalog_request(data: Dict[str, Any]) -> int:
    """Registra uma nova solicitação de catálogo e consome o token de uso único."""
    ensure_catalog_requests_schema()

    applicant_name = (data.get("applicant_name") or "").strip().upper()
    store_name = (data.get("store_name") or "").strip().upper()
    raw_wa = (data.get("whatsapp_number") or "").strip()
    whatsapp_number = re.sub(r"\D", "", raw_wa)
    city_state = (data.get("city_state") or "").strip().upper()
    suggested_slug = (data.get("suggested_slug") or "").strip().lower()
    notes = (data.get("notes") or "").strip().upper()
    invite_code = (data.get("invite_code") or "").strip().upper()

    with db() as conn:
        cursor = _run_exec(
            conn,
            """
            INSERT INTO maj_custom_catalog_requests
            (invite_code, applicant_name, store_name, whatsapp_number, city_state, suggested_slug, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente')
            RETURNING id
            """ if _is_pg(conn) else
            """
            INSERT INTO maj_custom_catalog_requests
            (invite_code, applicant_name, store_name, whatsapp_number, city_state, suggested_slug, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pendente')
            """,
            (invite_code, applicant_name, store_name, whatsapp_number, city_state, suggested_slug, notes)
        )
        if _is_pg(conn):
            row = cursor.fetchone()
            req_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            req_id = cursor.lastrowid
        conn.commit()

        # Consome o token descartável de uso único imediatamente
        consume_catalog_invite_token(invite_code, req_id)

        return req_id


def list_catalog_requests(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista as solicitações de catálogo, ordenadas pelas mais recentes."""
    ensure_catalog_requests_schema()
    with db() as conn:
        if status:
            cursor = _run_exec(
                conn,
                """
                SELECT r.*, c.slug as created_catalog_slug, c.title as created_catalog_title
                FROM maj_custom_catalog_requests r
                LEFT JOIN maj_custom_catalogs c ON r.created_catalog_id = c.id
                WHERE r.status = ?
                ORDER BY r.created_at DESC
                """,
                (status,)
            )
        else:
            cursor = _run_exec(
                conn,
                """
                SELECT r.*, c.slug as created_catalog_slug, c.title as created_catalog_title
                FROM maj_custom_catalog_requests r
                LEFT JOIN maj_custom_catalogs c ON r.created_catalog_id = c.id
                ORDER BY r.created_at DESC
                """
            )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("created_at"), datetime):
                d["created_at_str"] = d["created_at"].strftime("%d/%m/%Y %H:%M")
            elif d.get("created_at"):
                d["created_at_str"] = str(d["created_at"])[:16]
            else:
                d["created_at_str"] = ""
            result.append(d)
        return result


def get_catalog_request_by_id(request_id: int) -> Optional[Dict[str, Any]]:
    """Obtém detalhes de uma solicitação específica."""
    ensure_catalog_requests_schema()
    with db() as conn:
        row = _run_exec(
            conn,
            """
            SELECT r.*, c.slug as created_catalog_slug, c.title as created_catalog_title
            FROM maj_custom_catalog_requests r
            LEFT JOIN maj_custom_catalogs c ON r.created_catalog_id = c.id
            WHERE r.id = ?
            """,
            (request_id,)
        ).fetchone()
        return dict(row) if row else None


def update_catalog_request_status(
    request_id: int,
    status: str,
    catalog_id: Optional[int] = None,
    approved_by: Optional[str] = None
) -> bool:
    """Atualiza o status de uma solicitação (ex: aprovada, recusada)."""
    ensure_catalog_requests_schema()
    with db() as conn:
        now_dt = datetime.utcnow() if status == "aprovada" else None
        _run_exec(
            conn,
            """
            UPDATE maj_custom_catalog_requests
            SET status = ?, created_catalog_id = COALESCE(?, created_catalog_id),
                approved_at = COALESCE(?, approved_at), approved_by = COALESCE(?, approved_by)
            WHERE id = ?
            """,
            (status, catalog_id, now_dt, approved_by or "", request_id)
        )
        conn.commit()
        return True


def delete_catalog_request(request_id: int) -> bool:
    """Exclui uma solicitação de catálogo."""
    ensure_catalog_requests_schema()
    with db() as conn:
        _run_exec(conn, "DELETE FROM maj_custom_catalog_requests WHERE id = ?", (request_id,))
        conn.commit()
        return True
