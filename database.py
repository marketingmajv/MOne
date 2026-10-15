from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

# Carregar variáveis de ambiente locais se presentes
load_dotenv()
load_dotenv(".env.local")

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.pool
    from psycopg2.extras import RealDictCursor
except (ImportError, ModuleNotFoundError):
    psycopg2 = None

DEFAULT_DB_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("SUPABASE_DB_URL")
    or "postgresql://postgres.ztbmnzwrpigcohwobrig:%40Jammajjam24@aws-0-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require"
)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "m_one.db"
pg_pool = None


def get_pg_pool():
    global pg_pool
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or DEFAULT_DB_URL
    if db_url and psycopg2 and pg_pool is None:
        try:
            pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, dsn=db_url)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as ex:
            logger.debug("Falha ao inicializar pool PostgreSQL: %s", ex)
            pg_pool = None
    return pg_pool


class PGCursorWrapper:
    def __init__(self, cur, returned_row=None, lastrowid=None):
        self.cur = cur
        self._returned_row = returned_row
        self.lastrowid = lastrowid or (returned_row.get("id") if (returned_row and isinstance(returned_row, dict)) else None)

    @property
    def rowcount(self):
        return getattr(self.cur, "rowcount", -1)

    def fetchone(self):
        if self._returned_row is not None:
            row = self._returned_row
            self._returned_row = None
            return row
        return self.cur.fetchone()

    def fetchall(self):
        if self._returned_row is not None:
            extra = [self._returned_row]
            self._returned_row = None
            return extra + (self.cur.fetchall() or [])
        return self.cur.fetchall()

    def __iter__(self):
        if self._returned_row is not None:
            yield self._returned_row
            self._returned_row = None
        yield from self.cur


class PGConnWrapper:
    def __init__(self, conn, pool=None):
        self.conn = conn
        self.pool = pool

    def execute(self, sql: str, params=()):
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        returned_row = None
        if "RETURNING" in sql.upper():
            try:
                returned_row = cur.fetchone()
            except Exception:
                returned_row = None
        return PGCursorWrapper(cur, returned_row=returned_row)

    def executescript(self, sql: str):
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self.conn.rollback()
            except Exception:
                pass
        else:
            try:
                self.conn.commit()
            except Exception:
                pass
        if self.pool:
            try:
                self.pool.putconn(self.conn)
            except Exception:
                pass
        else:
            try:
                self.conn.close()
            except Exception:
                pass


def connect_pg(db_url: str):
    if not db_url or not psycopg2:
        return None
    try:
        parsed = urlparse(db_url)
        user = unquote(parsed.username) if parsed.username else None
        pwd = unquote(parsed.password) if parsed.password else None
        dbname = parsed.path.lstrip("/") if parsed.path else "postgres"
        host = parsed.hostname
        port = parsed.port or 5432
        return psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=pwd,
            dbname=dbname,
            sslmode="require",
            connect_timeout=10
        )
    except Exception as ex:
        logger.debug("Falha ao conectar via DSN parseada: %s", ex)
        try:
            return psycopg2.connect(db_url, sslmode="require", connect_timeout=10)
        except Exception as ex2:
            logger.warning("Falha ao conectar via DSN direta ao PostgreSQL: %s", ex2)
            return None


def db():
    # Isolamento estrito para suíte de testes automatizada
    test_db = os.environ.get("TEST_DB_FILE")
    if test_db:
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # Forçar SQLite apenas se USE_LOCAL_DB estiver explicitamente ativado
    if os.environ.get("USE_LOCAL_DB") == "1":
        if os.environ.get("VERCEL"):
            tmp_db_path = Path("/tmp/m_one.db")
            conn = sqlite3.connect(tmp_db_path)
        else:
            conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # Conexão padrão ao PostgreSQL remoto do Supabase (IPv4 Pooler verificado)
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or DEFAULT_DB_URL
    if db_url and psycopg2:
        try:
            conn_raw = None
            pool = get_pg_pool()
            if pool:
                try:
                    conn_raw = pool.getconn()
                    # Testar vivacidade da conexão obtida do pool
                    with conn_raw.cursor() as cur:
                        cur.execute("SELECT 1")
                except Exception as pool_err:
                    logger.debug("Conexão do pool inválida/expirada, tentando conexão direta: %s", pool_err)
                    if conn_raw:
                        try:
                            pool.putconn(conn_raw, close=True)
                        except Exception:
                            pass
                    conn_raw = None

            if not conn_raw:
                conn_raw = connect_pg(db_url)

            if conn_raw:
                wrapper = PGConnWrapper(conn_raw, pool=pool if conn_raw != pool else None)
                if not is_schema_ensured():
                    try:
                        ensure_runtime_schema(wrapper)
                    except Exception as schema_err:
                        logger.warning("Erro ao assegurar runtime schema: %s", schema_err)
                return wrapper
        except Exception as e:
            logger.warning("Falha ao obter conexão PostgreSQL via pool/direto: %s", e)

    # Fallback seguro para SQLite (local ou Vercel /tmp)
    if os.environ.get("VERCEL"):
        tmp_db_path = Path("/tmp/m_one.db")
        conn = sqlite3.connect(tmp_db_path)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if not is_schema_ensured():
        try:
            ensure_runtime_schema(conn)
        except Exception as schema_err:
            logger.warning("Erro ao assegurar runtime schema no fallback: %s", schema_err)
    return conn


from database_schema import (
    ensure_indexes,
    ensure_runtime_schema,
    is_schema_ensured,
    run_init_db,
)


def init_db():
    """Inicializa índices de alta performance e schema fallback se necessário."""
    run_init_db(db, default_db_url=DEFAULT_DB_URL, psycopg2_module=psycopg2)


