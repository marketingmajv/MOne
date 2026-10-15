from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_schema_ensured = False


def is_schema_ensured() -> bool:
    """Retorna se o schema e índices de runtime já foram verificados."""
    return _schema_ensured


def ensure_indexes(conn: Any) -> None:
    """Cria índices de alta performance se ainda não existirem."""
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_stock_units_product_status ON stock_units(product_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_stock_units_chassis ON stock_units(chassis);",
        "CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_phone_sent ON whatsapp_messages(phone, sent_at);",
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_phone ON crm_leads(phone);",
        "CREATE INDEX IF NOT EXISTS idx_freight_rates_table_uf ON freight_rates(table_id, uf);",
        "CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales(sold_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sales_seller ON sales(created_by, sold_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_payments_paid_at ON payments(paid_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sale_units_sale_id ON sale_units(sale_id);",
        "CREATE INDEX IF NOT EXISTS idx_sale_units_product_id ON sale_units(product_id);",
        "CREATE INDEX IF NOT EXISTS idx_sale_receipts_sale_id ON sale_receipts(sale_id);",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_id ON audit_log(id DESC);",
    ]
    is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
    for q in index_queries:
        try:
            conn.execute(q)
        except Exception as ex:
            logger.debug("Erro ao criar índice %s: %s", q, ex)
            if is_pg:
                try:
                    conn.rollback()
                except Exception:
                    pass


def ensure_runtime_schema(conn: Any) -> None:
    """Garante todas as colunas dinâmicas e índices apenas uma vez no ciclo de vida do processo."""
    global _schema_ensured
    if _schema_ensured:
        return

    is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
    if is_pg:
        try:
            chk = conn.execute("SELECT to_regclass('public.audit_log');").fetchone()
            reg = chk.get("to_regclass") if isinstance(chk, dict) else (chk[0] if chk else None)
            if reg:
                _schema_ensured = True
                return
        except Exception:
            pass

    if_not_exists = "IF NOT EXISTS " if is_pg else ""

    # 1. Colunas adicionais de produtos
    for col, col_type in [
        ("fob_price_usd", "REAL DEFAULT 0"),
        ("aliquota_rate", "REAL DEFAULT 0"),
        ("installment_12x", "REAL DEFAULT 0"),
        ("installment_18x", "REAL DEFAULT 0"),
        ("bling_id", "TEXT"),
        ("bling_stock", "INTEGER DEFAULT 0"),
        ("bling_updated_at", "TIMESTAMP"),
    ]:
        try:
            conn.execute(f"ALTER TABLE products ADD COLUMN {if_not_exists}{col} {col_type}")
        except Exception:
            if is_pg:
                try:
                    conn.rollback()
                except Exception:
                    pass

    # 2. Colunas adicionais de vendas
    for col in [
        "danfe_file",
        "delivery_term_files",
        "ai_chassis_verified",
        "ai_extracted_chassis",
        "vehicle_model",
        "chassis_photo_file",
        "warranty_term_file",
        "signed_stub_file",
    ]:
        try:
            conn.execute(f"ALTER TABLE sales ADD COLUMN {if_not_exists}{col} TEXT")
        except Exception:
            if is_pg:
                try:
                    conn.rollback()
                except Exception:
                    pass

    # 3. Colunas adicionais de importações
    for col, col_type in [
        ("ocean_freight_usd", "REAL DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE imports ADD COLUMN {if_not_exists}{col} {col_type}")
        except Exception:
            if is_pg:
                try:
                    conn.rollback()
                except Exception:
                    pass

    # 4. Colunas adicionais de pagamentos
    for col, col_type in [
        ("payment_method", "TEXT"),
        ("card_last4", "TEXT"),
        ("supplier", "TEXT"),
        ("document_no", "TEXT"),
        ("ai_verified", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE payments ADD COLUMN {if_not_exists}{col} {col_type}")
        except Exception:
            if is_pg:
                try:
                    conn.rollback()
                except Exception:
                    pass

    # 5. Tabela de auditoria
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception:
        pass

    # 6. Criação de índices estratégicos
    ensure_indexes(conn)
    _schema_ensured = True


SQLITE_FALLBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'sales',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sku TEXT UNIQUE,
    category TEXT,
    unit_cost REAL NOT NULL DEFAULT 0,
    retail_price REAL NOT NULL DEFAULT 0,
    wholesale_price REAL NOT NULL DEFAULT 0,
    promo_eligible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference TEXT NOT NULL UNIQUE,
    invoice_no TEXT,
    bl_no TEXT,
    arrival_date TEXT,
    usd_rate REAL NOT NULL DEFAULT 0,
    invoice_amount_usd REAL NOT NULL DEFAULT 0,
    nf_entry TEXT,
    invoice_file TEXT,
    bl_file TEXT,
    nf_entry_file TEXT,
    chassis_file TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(created_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS import_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL,
    cost_type TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'BRL',
    usd_rate REAL NOT NULL DEFAULT 0,
    paid_at TEXT,
    receipt_file TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(import_id) REFERENCES imports(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS stock_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chassis TEXT NOT NULL UNIQUE,
    motor_no TEXT,
    product_id INTEGER NOT NULL,
    color TEXT,
    import_id INTEGER,
    status TEXT NOT NULL DEFAULT 'available',
    location TEXT NOT NULL DEFAULT 'Depósito',
    received_at TEXT,
    sold_at TEXT,
    sale_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(import_id) REFERENCES imports(id)
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    channel TEXT NOT NULL,
    customer TEXT,
    sold_at TEXT NOT NULL,
    total_value REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(created_by) REFERENCES users(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_invoice_unique ON sales(invoice_number);
CREATE TABLE IF NOT EXISTS sale_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    stock_unit_id INTEGER NOT NULL UNIQUE,
    product_id INTEGER NOT NULL,
    unit_value REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY(stock_unit_id) REFERENCES stock_units(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS sale_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    method TEXT NOT NULL,
    account TEXT,
    amount REAL NOT NULL,
    received_at TEXT NOT NULL,
    receipt_file TEXT,
    FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paid_at TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    amount REAL NOT NULL,
    account TEXT,
    receipt_file TEXT,
    import_id INTEGER,
    visibility TEXT NOT NULL DEFAULT 'finance',
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(import_id) REFERENCES imports(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS freight_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_number TEXT UNIQUE,
    customer_name TEXT,
    cpf_cnpj TEXT,
    company_name TEXT,
    contact_phone TEXT,
    contact_person TEXT,
    full_address TEXT,
    cep_dest TEXT,
    cep_orig TEXT,
    items_summary TEXT,
    carrier_results_json TEXT,
    selected_carrier TEXT,
    selected_price REAL,
    status TEXT DEFAULT 'cotado',
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(created_by) REFERENCES users(id)
);
"""


def run_init_db(db_getter: Any, default_db_url: str | None = None, psycopg2_module: Any = None) -> None:
    """Inicializa índices de alta performance e schema fallback se necessário."""
    try:
        with db_getter() as conn:
            ensure_runtime_schema(conn)
    except Exception as e:
        logger.warning("[Init DB Warning]: %s", e)

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or default_db_url
    if db_url and psycopg2_module and os.environ.get("USE_LOCAL_DB") != "1":
        return

    try:
        with db_getter() as conn:
            conn.executescript(SQLITE_FALLBACK_SCHEMA)
            conn.commit()
    except Exception as e:
        logger.warning("[Init DB SQLite fallback warning]: %s", e)

    try:
        from services.fiscal_db_init import init_fiscal_db
        init_fiscal_db()
    except Exception as e:
        logger.warning("[Init Fiscal DB warning]: %s", e)
