"""
Serviço de inicialização e suporte de tabelas do Módulo de Precificação Fiscal.
Garante criação compatível entre PostgreSQL (Supabase) e SQLite.
"""
from __future__ import annotations

import logging
from database import db

logger = logging.getLogger("mone.fiscal_db")


def init_fiscal_db() -> None:
    """Cria as tabelas de lotes fiscais, itens e simulações com compatibilidade Postgres/SQLite."""
    with db() as conn:
        is_pg = isinstance(conn, object) and (
            hasattr(conn, "conn") or hasattr(conn, "pg_conn") or type(conn).__name__ == "PGConnWrapper"
        )

        id_pk = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        ts_type = "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP" if is_pg else "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"

        # 1. fiscal_batches
        try:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS fiscal_batches (
                    id {id_pk},
                    batch_code VARCHAR(100) UNIQUE NOT NULL,
                    source_type VARCHAR(50) NOT NULL DEFAULT 'manual',
                    source_ref VARCHAR(255),
                    supplier_name VARCHAR(255) DEFAULT 'COLVIX',
                    invoice_number VARCHAR(100),
                    invoice_date VARCHAR(50),
                    total_products_val DOUBLE PRECISION DEFAULT 0.0,
                    total_ii_val DOUBLE PRECISION DEFAULT 0.0,
                    total_pis_val DOUBLE PRECISION DEFAULT 0.0,
                    total_cofins_val DOUBLE PRECISION DEFAULT 0.0,
                    total_icms_val DOUBLE PRECISION DEFAULT 0.0,
                    total_ipi_val DOUBLE PRECISION DEFAULT 0.0,
                    total_other_expenses_val DOUBLE PRECISION DEFAULT 0.0,
                    total_cost_colvix DOUBLE PRECISION DEFAULT 0.0,
                    pis_credit_initial DOUBLE PRECISION DEFAULT 0.0,
                    pis_credit_balance DOUBLE PRECISION DEFAULT 0.0,
                    cofins_credit_initial DOUBLE PRECISION DEFAULT 0.0,
                    cofins_credit_balance DOUBLE PRECISION DEFAULT 0.0,
                    icms_credit_initial DOUBLE PRECISION DEFAULT 0.0,
                    icms_credit_balance DOUBLE PRECISION DEFAULT 0.0,
                    ipi_credit_initial DOUBLE PRECISION DEFAULT 0.0,
                    ipi_credit_balance DOUBLE PRECISION DEFAULT 0.0,
                    status VARCHAR(50) DEFAULT 'simulacao',
                    created_by INTEGER,
                    created_at {ts_type}
                );
            """)
        except Exception as e:
            logger.info("[Fiscal DB Init fallback SQLite]: %s", e)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fiscal_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_code TEXT UNIQUE NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'manual',
                    source_ref TEXT,
                    supplier_name TEXT DEFAULT 'COLVIX',
                    invoice_number TEXT,
                    invoice_date TEXT,
                    total_products_val REAL DEFAULT 0.0,
                    total_ii_val REAL DEFAULT 0.0,
                    total_pis_val REAL DEFAULT 0.0,
                    total_cofins_val REAL DEFAULT 0.0,
                    total_icms_val REAL DEFAULT 0.0,
                    total_ipi_val REAL DEFAULT 0.0,
                    total_other_expenses_val REAL DEFAULT 0.0,
                    total_cost_colvix REAL DEFAULT 0.0,
                    pis_credit_initial REAL DEFAULT 0.0,
                    pis_credit_balance REAL DEFAULT 0.0,
                    cofins_credit_initial REAL DEFAULT 0.0,
                    cofins_credit_balance REAL DEFAULT 0.0,
                    icms_credit_initial REAL DEFAULT 0.0,
                    icms_credit_balance REAL DEFAULT 0.0,
                    ipi_credit_initial REAL DEFAULT 0.0,
                    ipi_credit_balance REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'simulacao',
                    created_by INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

        # 2. fiscal_batch_items
        try:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS fiscal_batch_items (
                    id {id_pk},
                    batch_id INTEGER NOT NULL,
                    product_id INTEGER,
                    item_code VARCHAR(100),
                    description VARCHAR(255) NOT NULL,
                    ncm VARCHAR(50),
                    quantity DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                    unit_product_val DOUBLE PRECISION DEFAULT 0.0,
                    total_product_val DOUBLE PRECISION DEFAULT 0.0,
                    participacao_pct DOUBLE PRECISION DEFAULT 0.0,
                    ii_rateado DOUBLE PRECISION DEFAULT 0.0,
                    pis_rateado DOUBLE PRECISION DEFAULT 0.0,
                    cofins_rateado DOUBLE PRECISION DEFAULT 0.0,
                    other_expenses_rateadas DOUBLE PRECISION DEFAULT 0.0,
                    ipi_item DOUBLE PRECISION DEFAULT 0.0,
                    icms_item DOUBLE PRECISION DEFAULT 0.0,
                    total_cost_item DOUBLE PRECISION DEFAULT 0.0,
                    unit_cost_colvix DOUBLE PRECISION DEFAULT 0.0,
                    quantity_sold DOUBLE PRECISION DEFAULT 0.0,
                    quantity_remaining DOUBLE PRECISION DEFAULT 0.0,
                    created_at {ts_type},
                    FOREIGN KEY(batch_id) REFERENCES fiscal_batches(id) ON DELETE CASCADE
                );
            """)
        except Exception:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fiscal_batch_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER NOT NULL,
                    product_id INTEGER,
                    item_code TEXT,
                    description TEXT NOT NULL,
                    ncm TEXT,
                    quantity REAL NOT NULL DEFAULT 1.0,
                    unit_product_val REAL DEFAULT 0.0,
                    total_product_val REAL DEFAULT 0.0,
                    participacao_pct REAL DEFAULT 0.0,
                    ii_rateado REAL DEFAULT 0.0,
                    pis_rateado REAL DEFAULT 0.0,
                    cofins_rateado REAL DEFAULT 0.0,
                    other_expenses_rateadas REAL DEFAULT 0.0,
                    ipi_item REAL DEFAULT 0.0,
                    icms_item REAL DEFAULT 0.0,
                    total_cost_item REAL DEFAULT 0.0,
                    unit_cost_colvix REAL DEFAULT 0.0,
                    quantity_sold REAL DEFAULT 0.0,
                    quantity_remaining REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(batch_id) REFERENCES fiscal_batches(id) ON DELETE CASCADE
                );
            """)

        # 3. fiscal_simulations
        try:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS fiscal_simulations (
                    id {id_pk},
                    batch_id INTEGER,
                    item_id INTEGER,
                    title VARCHAR(255),
                    dest_uf VARCHAR(10) DEFAULT 'SP',
                    dest_type VARCHAR(50) DEFAULT 'M-ONE',
                    margin_pct DOUBLE PRECISION DEFAULT 30.0,
                    unit_sale_price DOUBLE PRECISION DEFAULT 0.0,
                    qty DOUBLE PRECISION DEFAULT 1.0,
                    icms_own_pct DOUBLE PRECISION DEFAULT 12.0,
                    icms_own_val DOUBLE PRECISION DEFAULT 0.0,
                    ipi_sale_pct DOUBLE PRECISION DEFAULT 0.0,
                    ipi_sale_val DOUBLE PRECISION DEFAULT 0.0,
                    pis_sale_pct DOUBLE PRECISION DEFAULT 1.65,
                    pis_sale_val DOUBLE PRECISION DEFAULT 0.0,
                    cofins_sale_pct DOUBLE PRECISION DEFAULT 7.6,
                    cofins_sale_val DOUBLE PRECISION DEFAULT 0.0,
                    mva_pct DOUBLE PRECISION DEFAULT 34.0,
                    base_st DOUBLE PRECISION DEFAULT 0.0,
                    icms_st_dest_pct DOUBLE PRECISION DEFAULT 18.0,
                    icms_st_val DOUBLE PRECISION DEFAULT 0.0,
                    st_cashflow_saving DOUBLE PRECISION DEFAULT 0.0,
                    colvix_net_tax DOUBLE PRECISION DEFAULT 0.0,
                    colvix_tax_status VARCHAR(50) DEFAULT 'CRÉDITO RESTANTE',
                    op_expenses_pct DOUBLE PRECISION DEFAULT 5.0,
                    op_expenses_val DOUBLE PRECISION DEFAULT 0.0,
                    gross_profit DOUBLE PRECISION DEFAULT 0.0,
                    taxable_base_ir_csll DOUBLE PRECISION DEFAULT 0.0,
                    ir_csll_val DOUBLE PRECISION DEFAULT 0.0,
                    net_profit DOUBLE PRECISION DEFAULT 0.0,
                    created_by INTEGER,
                    created_at {ts_type}
                );
            """)
        except Exception:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fiscal_simulations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER,
                    item_id INTEGER,
                    title TEXT,
                    dest_uf TEXT DEFAULT 'SP',
                    dest_type TEXT DEFAULT 'M-ONE',
                    margin_pct REAL DEFAULT 30.0,
                    unit_sale_price REAL DEFAULT 0.0,
                    qty REAL DEFAULT 1.0,
                    icms_own_pct REAL DEFAULT 12.0,
                    icms_own_val REAL DEFAULT 0.0,
                    ipi_sale_pct REAL DEFAULT 0.0,
                    ipi_sale_val REAL DEFAULT 0.0,
                    pis_sale_pct REAL DEFAULT 1.65,
                    pis_sale_val REAL DEFAULT 0.0,
                    cofins_sale_pct REAL DEFAULT 7.6,
                    cofins_sale_val REAL DEFAULT 0.0,
                    mva_pct REAL DEFAULT 34.0,
                    base_st REAL DEFAULT 0.0,
                    icms_st_dest_pct REAL DEFAULT 18.0,
                    icms_st_val REAL DEFAULT 0.0,
                    st_cashflow_saving REAL DEFAULT 0.0,
                    colvix_net_tax REAL DEFAULT 0.0,
                    colvix_tax_status TEXT DEFAULT 'CRÉDITO RESTANTE',
                    op_expenses_pct REAL DEFAULT 5.0,
                    op_expenses_val REAL DEFAULT 0.0,
                    gross_profit REAL DEFAULT 0.0,
                    taxable_base_ir_csll REAL DEFAULT 0.0,
                    ir_csll_val REAL DEFAULT 0.0,
                    net_profit REAL DEFAULT 0.0,
                    created_by INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
        logger.info("[Fiscal DB Init]: Tabelas de precificação fiscal inicializadas com sucesso.")
