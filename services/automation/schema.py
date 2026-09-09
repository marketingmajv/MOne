"""
M-One WhatsApp Automation Schema & Migrations (services/automation/schema.py)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time

from database import db

logger = logging.getLogger(__name__)
_schema_initialized = False


def is_unique_violation(ex: Exception) -> bool:
    """Verifica se a exceção é especificamente uma violação de restrição UNIQUE no SQLite ou PostgreSQL."""
    if not ex:
        return False
    msg = str(ex).lower()
    ex_type = type(ex).__name__.lower()

    if "unique constraint" in msg or "duplicate key" in msg or "unique_violation" in msg:
        return True
    if "integrityerror" in ex_type or "uniqueviolation" in ex_type:
        return True

    return getattr(ex, "pgcode", None) == "23505"


def has_column(conn, table_name: str, column_name: str) -> bool:
    """Verifica via introspecção de esquema se a coluna já existe na tabela (compatível com SQLite e PG)."""
    try:
        res = conn.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name=? AND column_name=?",
            (table_name.lower(), column_name.lower())
        ).fetchone()
        if res:
            return True
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, sqlite3.Error) as ex:
        logger.debug("Tabela ou informação de esquema não encontrada: %s", ex)

    try:
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        for c in cols:
            col_nm = c["name"] if isinstance(c, dict) or hasattr(c, "__getitem__") else c[1]
            if str(col_nm).lower() == column_name.lower():
                return True
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, sqlite3.Error) as ex:
        logger.debug("Falha ao ler PRAGMA table_info(%s): %s", table_name, ex)

    return False


def ensure_automation_schema(force: bool = False):
    """Cria tabelas aditivas de automação de fluxo, locks por contato e garante tabelas base do CRM."""
    global _schema_initialized
    if _schema_initialized and not force:
        return

    with db() as conn:
        # Base CRM tables for local SQLite environment
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crm_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT UNIQUE,
                email TEXT,
                channel TEXT DEFAULT 'WhatsApp',
                status TEXT DEFAULT 'novo',
                assigned_to TEXT,
                seller_id INTEGER,
                bot_paused INTEGER DEFAULT 0,
                notes TEXT,
                custom_fields TEXT DEFAULT '{}',
                tags TEXT DEFAULT '[]',
                ticket_status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wam_id TEXT,
                phone TEXT NOT NULL,
                direction TEXT NOT NULL,
                message_type TEXT NOT NULL,
                body TEXT,
                status TEXT NOT NULL DEFAULT 'received',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Entidade de Respostas Rápidas (Canned Responses)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_canned_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Entidade de Tarefas do CRM
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crm_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                phone TEXT NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT,
                assigned_to TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Reserva Atômica de WAM_ID com Estados e Payload
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_processed_wams (
                wam_id TEXT PRIMARY KEY,
                phone TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                lease_expires_at INTEGER,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Ledger de Efeitos por Sessão e Nó com Rastreamento de Status (pending, completed, failed, uncertain)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_node_effects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                node_id TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                detail TEXT,
                status TEXT NOT NULL DEFAULT 'completed',
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, node_id, effect_type)
            );
        """)

        # Travamento por Contato (Lease / Lock com Expiração para Retomada de Falhas)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_locks (
                phone TEXT PRIMARY KEY,
                locked_by TEXT NOT NULL,
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at INTEGER NOT NULL
            );
        """)

        # 1. Fluxos de Automação (Draft vs Active)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                version INTEGER NOT NULL DEFAULT 1,
                active_version_data TEXT,
                draft_version_data TEXT,
                draft_trigger_type TEXT DEFAULT 'keyword',
                draft_trigger_config TEXT DEFAULT '{}',
                active_trigger_type TEXT DEFAULT 'keyword',
                active_trigger_config TEXT DEFAULT '{}',
                trigger_type TEXT DEFAULT 'keyword',
                trigger_config TEXT DEFAULT '{}',
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Sessões / Execuções de Automação com Delay Persistido e Snapshot
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id INTEGER NOT NULL,
                phone TEXT NOT NULL,
                lead_id INTEGER,
                status TEXT NOT NULL DEFAULT 'running',
                current_node_id TEXT,
                waiting_variable TEXT,
                waiting_validation TEXT,
                question_asked_at INTEGER,
                timeout_seconds INTEGER DEFAULT 300,
                resume_due_at INTEGER,
                variables TEXT DEFAULT '{}',
                flow_snapshot TEXT DEFAULT '{}',
                execution_log TEXT DEFAULT '[]',
                claimed_by TEXT,
                last_error TEXT,
                last_interaction_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Logs de Execução de Nós e Resposta Webhook
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                flow_id INTEGER,
                phone TEXT NOT NULL,
                node_id TEXT,
                event_type TEXT NOT NULL,
                detail TEXT,
                response_code INTEGER,
                response_body TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Garantir colunas aditivas via introspecção segura de esquema (sem falhar transações em PG)
        additive_columns = [
            ("crm_leads", "custom_fields", "TEXT DEFAULT '{}'"),
            ("crm_leads", "tags", "TEXT DEFAULT '[]'"),
            ("crm_leads", "ticket_status", "TEXT DEFAULT 'open'"),
            ("automation_node_effects", "status", "TEXT DEFAULT 'completed'"),
            ("automation_node_effects", "last_error", "TEXT"),
            ("automation_sessions", "last_error", "TEXT"),
            ("automation_flows", "title", "TEXT"),
            ("automation_flows", "name", "TEXT"),
        ]

        for tbl, col, col_type in additive_columns:
            if not has_column(conn, tbl, col):
                try:
                    conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}")
                except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, sqlite3.Error) as ex:
                    logger.debug("Coluna %s em %s já existe ou erro ao adicionar: %s", col, tbl, ex)

        conn.commit()
    _schema_initialized = True


def seed_default_flows_if_empty():
    """Popula um fluxo inicial padronizado da MAJ caso a tabela esteja vazia."""
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM automation_flows").fetchone()[0]
        if count == 0:
            default_graph = {
                "nodes": [
                    {
                        "id": "node_trigger",
                        "type": "trigger",
                        "label": "Gatilho: Palavras-chave",
                        "config": {"keywords": ["ola", "olá", "menu", "ajuda", "inicio"]},
                        "position": {"x": 60, "y": 100}
                    },
                    {
                        "id": "node_welcome",
                        "type": "send_message",
                        "label": "Boas-Vindas MAJ",
                        "config": {"text": "👋 Olá! Bem-vindo à MAJ Mobilidade Elétrica.\nComo podemos te ajudar hoje?"},
                        "position": {"x": 380, "y": 100}
                    },
                    {
                        "id": "node_menu",
                        "type": "send_menu",
                        "label": "Menu Principal",
                        "config": {
                            "title": "Escolha uma opção digitando o número correspondente:",
                            "options": [
                                {"id": "opt_catalog", "text": "1. Ver Veículos Elétricos"},
                                {"id": "opt_freight", "text": "2. Cotar Frete"},
                                {"id": "opt_human", "text": "3. Falar com Vendedor"}
                            ],
                            "save_variable": "menu_choice"
                        },
                        "position": {"x": 700, "y": 100}
                    }
                ],
                "edges": [
                    {"id": "e1", "source": "node_trigger", "target": "node_welcome"},
                    {"id": "e2", "source": "node_welcome", "target": "node_menu"}
                ]
            }

            graph_str = json.dumps(default_graph)
            conn.execute(
                """
                INSERT INTO automation_flows 
                (name, title, description, status, active_version_data)
                VALUES (?, ?, ?, 'active', ?)
                """,
                ("Menu Principal MAJ", "Menu Principal MAJ", "Fluxo padrão de recepção e menu de opções", graph_str)
            )
            conn.commit()


def acquire_contact_lock(phone: str, worker_id: str, lock_ttl_seconds: int = 30, lease_seconds: int = 30) -> bool:
    """Adquire trava exclusiva (lock) por contato com expiração automática."""
    now_ts = int(time.time())
    ttl = lock_ttl_seconds if lock_ttl_seconds != 30 else lease_seconds
    expires_at = now_ts + ttl

    with db() as conn:
        conn.execute("DELETE FROM contact_locks WHERE phone=? AND expires_at <= ?", (phone, now_ts))
        conn.commit()

        try:
            conn.execute(
                "INSERT INTO contact_locks (phone, locked_by, expires_at) VALUES (?, ?, ?)",
                (phone, worker_id, expires_at)
            )
            conn.commit()
            return True
        except Exception as ex:
            if not is_unique_violation(ex):
                raise
            conn.execute(
                "UPDATE contact_locks SET locked_by=?, expires_at=? WHERE phone=? AND expires_at <= ?",
                (worker_id, expires_at, phone, now_ts)
            )
            conn.commit()
            row = conn.execute("SELECT locked_by FROM contact_locks WHERE phone=?", (phone,)).fetchone()
            return bool(row and row["locked_by"] == worker_id)


def release_contact_lock(phone: str, worker_id: str):
    """Libera o lock do contato se pertencer ao worker especificador."""
    with db() as conn:
        conn.execute("DELETE FROM contact_locks WHERE phone=? AND locked_by=?", (phone, worker_id))
        conn.commit()


def record_node_effect(session_id: int, node_id: str, effect_type: str, detail: str = "", status: str = "completed") -> tuple[bool, str]:
    """
    Registra ou verifica o efeito de um nó no ledger transacional.
    Status suportados: 'pending', 'completed', 'failed', 'uncertain'.
    Retorna (can_execute: bool, current_status: str).
    """
    with db() as conn:
        existing = conn.execute(
            "SELECT status FROM automation_node_effects WHERE session_id=? AND node_id=? AND effect_type=?",
            (session_id, node_id, effect_type)
        ).fetchone()

        if existing:
            return False, existing["status"]

        try:
            conn.execute(
                """
                INSERT INTO automation_node_effects (session_id, node_id, effect_type, detail, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, node_id, effect_type, detail, status)
            )
            conn.commit()
            return True, status
        except Exception as ex:
            if not is_unique_violation(ex):
                raise
            row = conn.execute(
                "SELECT status FROM automation_node_effects WHERE session_id=? AND node_id=? AND effect_type=?",
                (session_id, node_id, effect_type)
            ).fetchone()
            st = row["status"] if row else "uncertain"
            return False, st


def update_node_effect_status(session_id: int, node_id: str, effect_type: str, status: str, last_error: str | None = None):
    """Atualiza o status de um efeito existente no ledger (ex: de pending para completed ou uncertain)."""
    with db() as conn:
        conn.execute(
            """
            UPDATE automation_node_effects 
            SET status=?, last_error=?, updated_at=CURRENT_TIMESTAMP
            WHERE session_id=? AND node_id=? AND effect_type=?
            """,
            (status, last_error, session_id, node_id, effect_type)
        )
        conn.commit()


def reserve_wam_id_atomically(wam_id: str | None, phone: str, payload: dict | None = None) -> str:
    """Reserva atômica de WAM_ID no banco local."""
    if not wam_id:
        return "new_untracked"

    now_ts = int(time.time())
    lease_expires = now_ts + 60
    payload_str = json.dumps(payload or {})

    with db() as conn:
        existing = conn.execute(
            "SELECT status, lease_expires_at FROM automation_processed_wams WHERE wam_id=?", (wam_id,)
        ).fetchone()

        if existing:
            st = existing["status"]
            exp = existing["lease_expires_at"] or 0
            if st == "completed":
                return "completed_duplicate"
            if st == "processing" and now_ts < exp:
                return "processing_locked"
            
            conn.execute(
                """
                UPDATE automation_processed_wams 
                SET status='processing', lease_expires_at=?, attempts=attempts+1, updated_at=CURRENT_TIMESTAMP
                WHERE wam_id=?
                """,
                (lease_expires, wam_id)
            )
            conn.commit()
            return "retry_reserved"

        try:
            conn.execute(
                """
                INSERT INTO automation_processed_wams (wam_id, phone, payload, status, attempts, lease_expires_at)
                VALUES (?, ?, ?, 'processing', 1, ?)
                """,
                (wam_id, phone, payload_str, lease_expires)
            )
            conn.commit()
            return "reserved"
        except Exception as ex:
            if not is_unique_violation(ex):
                raise
            return "completed_duplicate"
