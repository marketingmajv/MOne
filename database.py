from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.pool
    from psycopg2.extras import RealDictCursor
except (ImportError, ModuleNotFoundError):
    psycopg2 = None

DEFAULT_DB_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or ""
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "m_one.db"
pg_pool = None


def get_pg_pool():
    global pg_pool
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if db_url and psycopg2 and pg_pool is None:
        try:
            pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, dsn=db_url)
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as ex:
            logger.debug("Falha ao inicializar pool PostgreSQL: %s", ex)
            pg_pool = None
    return pg_pool


class PGCursorWrapper:
    def __init__(self, cur, lastrowid=None):
        self.cur = cur
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return getattr(self.cur, "rowcount", -1)

    def fetchone(self):
        return self.cur.fetchone()
    def fetchall(self):
        return self.cur.fetchall()
    def __iter__(self):
        return iter(self.cur)


class PGConnWrapper:
    def __init__(self, conn, pool=None):
        self.conn = conn
        self.pool = pool
    def execute(self, sql, params=()):
        pg_sql = sql.replace("?", "%s")
        pg_sql = pg_sql.replace("active=1", "active=TRUE").replace("active=0", "active=FALSE")
        pg_sql = pg_sql.replace("promo_eligible=1", "promo_eligible=TRUE").replace("promo_eligible=0", "promo_eligible=FALSE")
        pg_sql = pg_sql.replace("COALESCE(st.received_at, substr(st.created_at,1,10))", "COALESCE(st.received_at, st.created_at::date)")
        pg_sql = pg_sql.replace("HAVING available>0 AND oldest_date<=", "HAVING COUNT(st.id)>0 AND MIN(COALESCE(st.received_at, st.created_at::date))<=")
        pg_sql = pg_sql.replace("GROUP_CONCAT(st.chassis, ', ')", "STRING_AGG(st.chassis, ', ')")
        pg_sql = pg_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        
        if "INSERT OR IGNORE INTO" in pg_sql.upper():
            pg_sql = pg_sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            if "ON CONFLICT" not in pg_sql.upper():
                pg_sql += " ON CONFLICT DO NOTHING"
        
        is_insert = pg_sql.strip().upper().startswith("INSERT INTO") or pg_sql.strip().upper().startswith("INSERT ")
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        lastrowid = None

        if is_insert and "RETURNING" not in pg_sql.upper() and "ON CONFLICT" not in pg_sql.upper():
            try:
                cur.execute("SAVEPOINT try_returning_id;")
                cur.execute(pg_sql + " RETURNING id", params)
                row = cur.fetchone()
                if row and isinstance(row, dict) and "id" in row:
                    lastrowid = row["id"]
                cur.execute("RELEASE SAVEPOINT try_returning_id;")
                return PGCursorWrapper(cur, lastrowid)
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as ex:
                logger.debug("Erro em RETURNING id com SAVEPOINT: %s", ex)
                cur.execute("ROLLBACK TO SAVEPOINT try_returning_id;")

        cur.execute(pg_sql, params)
        return PGCursorWrapper(cur, lastrowid)

    def executescript(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        return cur
    def commit(self):
        self.conn.commit()
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        if self.pool:
            self.pool.putconn(self.conn)
        else:
            self.conn.close()


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
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as ex:
        logger.debug("Falha ao conectar via DSN parseada: %s", ex)
        return psycopg2.connect(db_url, sslmode="require", connect_timeout=10)


def db():
    # Isolamento estrito para suíte de testes automatizada
    test_db = os.environ.get("TEST_DB_FILE")
    if test_db:
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # Isolamento de segurança estrito: Por padrão em ambiente local/testes, força uso do SQLite local m_one.db
    # Para conectar ao PostgreSQL remoto do Supabase em produção, exige VERCEL=1 ou USE_PRODUCTION_DB=1
    use_remote_db = (os.environ.get("VERCEL") or os.environ.get("USE_PRODUCTION_DB") == "1") and not os.environ.get("USE_LOCAL_DB")
    
    if use_remote_db:
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
        if not db_url:
            raise RuntimeError("Ambiente configurado para banco remoto (USE_PRODUCTION_DB/VERCEL), mas DATABASE_URL/SUPABASE_DB_URL não foi configurada.")
        if not psycopg2:
            raise RuntimeError("Driver psycopg2 não disponível para conexão PostgreSQL.")
        try:
            pool = get_pg_pool()
            if pool:
                conn = pool.getconn()
                return PGConnWrapper(conn, pool=pool)
            conn = connect_pg(db_url)
            if conn:
                return PGConnWrapper(conn)
            raise RuntimeError("Não foi possível conectar ao banco de dados PostgreSQL remoto.")
        except Exception as e:
            raise RuntimeError(f"Falha de conexão com banco de dados remoto PostgreSQL: {e}") from e

    if os.environ.get("VERCEL"):
        tmp_db_path = Path("/tmp/m_one.db")
        conn = sqlite3.connect(tmp_db_path)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn



def ensure_indexes(conn):
    """Cria índices de alta performance se ainda não existirem."""
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_stock_units_product_status ON stock_units(product_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_stock_units_chassis ON stock_units(chassis);",
        "CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_phone_sent ON whatsapp_messages(phone, sent_at);",
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_phone ON crm_leads(phone);",
        "CREATE INDEX IF NOT EXISTS idx_freight_rates_table_uf ON freight_rates(table_id, uf);",
        "CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);"
    ]
    for q in index_queries:
        try:
            conn.execute(q)
        except (sqlite3.Error, RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as ex:
            logger.debug("Erro ao criar índice %s: %s", q, ex)
