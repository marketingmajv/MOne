"""
M-One Stock Sync & Schema Service (services/stock_sync_service.py)
Garante o schema estendido de estoque/conferência/baixa e sincroniza chassis
da planilha Google Sheets (COLVIX) respeitando a regra anti-reset.
"""

from __future__ import annotations

import io
import logging
import urllib.request
from typing import Any, Dict, List

import openpyxl

from database import db

logger = logging.getLogger(__name__)

COLVIX_SHEET_ID = "16csh8zLt8OjRER-3TnDrpq34sQX5J17sue4Cuq8txSY"

_schema_ensured = False


def ensure_stock_audit_schema(force: bool = False) -> None:
    """Garante colunas estendidas em stock_units/sales e tabelas stock_audits/stock_audit_items."""
    global _schema_ensured
    if _schema_ensured and not force:
        return

    with db() as conn:
        is_pg = hasattr(conn, "conn") and not str(type(conn.conn)).lower().find("sqlite") >= 0
        # Detectar se é PostgreSQL via módulo psycopg2 ou wrapper
        is_pg = type(conn).__name__ == "PGConnWrapper"

        if is_pg:
            alters = [
                "ALTER TABLE stock_units ADD COLUMN IF NOT EXISTS separated_order_number TEXT",
                "ALTER TABLE stock_units ADD COLUMN IF NOT EXISTS separated_at TIMESTAMP",
                "ALTER TABLE stock_units ADD COLUMN IF NOT EXISTS separated_by BIGINT",
                "ALTER TABLE stock_units ADD COLUMN IF NOT EXISTS last_audited_at TIMESTAMP",
                "ALTER TABLE stock_units ADD COLUMN IF NOT EXISTS last_audited_by BIGINT",
                "ALTER TABLE stock_units ADD COLUMN IF NOT EXISTS source_tab TEXT",
                "ALTER TABLE sales ADD COLUMN IF NOT EXISTS transfer_nf_1 TEXT",
                "ALTER TABLE sales ADD COLUMN IF NOT EXISTS transfer_nf_2 TEXT",
            ]
            for stmt in alters:
                try:
                    conn.execute(stmt)
                except Exception as ex:
                    logger.debug("Alter PG warning (%s): %s", stmt, ex)

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_audits (
                    id BIGSERIAL PRIMARY KEY,
                    location_scope TEXT NOT NULL DEFAULT 'Todos',
                    status TEXT NOT NULL DEFAULT 'in_progress',
                    started_by BIGINT,
                    started_by_name TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    expected_count INTEGER DEFAULT 0,
                    scanned_count INTEGER DEFAULT 0,
                    missing_count INTEGER DEFAULT 0,
                    alerts_count INTEGER DEFAULT 0,
                    notes TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_audit_items (
                    id BIGSERIAL PRIMARY KEY,
                    audit_id BIGINT NOT NULL REFERENCES stock_audits(id) ON DELETE CASCADE,
                    chassis TEXT NOT NULL,
                    stock_unit_id BIGINT,
                    scan_result TEXT NOT NULL DEFAULT 'ok',
                    unit_status_at_scan TEXT,
                    unit_location_at_scan TEXT,
                    order_number_snapshot TEXT,
                    product_name_snapshot TEXT,
                    color_snapshot TEXT,
                    source_tab_snapshot TEXT,
                    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scanned_by BIGINT
                )
                """
            )
            try:
                conn.execute("ALTER TABLE stock_audit_items ADD COLUMN IF NOT EXISTS source_tab_snapshot TEXT")
            except Exception:
                pass
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_stock_audit_items_audit ON stock_audit_items(audit_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_stock_audit_items_chassis ON stock_audit_items(chassis)"
            )
        else:
            # SQLite fallback
            existing_su = {
                r["name"] for r in conn.execute("PRAGMA table_info(stock_units)").fetchall()
            }
            for col, typ in [
                ("separated_order_number", "TEXT"),
                ("separated_at", "TIMESTAMP"),
                ("separated_by", "INTEGER"),
                ("last_audited_at", "TIMESTAMP"),
                ("last_audited_by", "INTEGER"),
                ("source_tab", "TEXT"),
            ]:
                if col not in existing_su:
                    conn.execute(f"ALTER TABLE stock_units ADD COLUMN {col} {typ}")

            existing_sales = {
                r["name"] for r in conn.execute("PRAGMA table_info(sales)").fetchall()
            }
            for col, typ in [("transfer_nf_1", "TEXT"), ("transfer_nf_2", "TEXT")]:
                if col not in existing_sales:
                    conn.execute(f"ALTER TABLE sales ADD COLUMN {col} {typ}")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_scope TEXT NOT NULL DEFAULT 'Todos',
                    status TEXT NOT NULL DEFAULT 'in_progress',
                    started_by INTEGER,
                    started_by_name TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    expected_count INTEGER DEFAULT 0,
                    scanned_count INTEGER DEFAULT 0,
                    missing_count INTEGER DEFAULT 0,
                    alerts_count INTEGER DEFAULT 0,
                    notes TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_audit_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id INTEGER NOT NULL,
                    chassis TEXT NOT NULL,
                    stock_unit_id INTEGER,
                    scan_result TEXT NOT NULL DEFAULT 'ok',
                    unit_status_at_scan TEXT,
                    unit_location_at_scan TEXT,
                    order_number_snapshot TEXT,
                    product_name_snapshot TEXT,
                    color_snapshot TEXT,
                    source_tab_snapshot TEXT,
                    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scanned_by INTEGER
                )
                """
            )
        conn.commit()
    _schema_ensured = True


def get_stock_locations() -> List[str]:
    """Retorna lista consolidada de galpões/locais disponíveis para filtro e conferência."""
    ensure_stock_audit_schema()
    defaults = ["Galpão MAJ", "COLVIX", "Depósito Consolação"]
    with db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT location FROM stock_units WHERE location IS NOT NULL AND TRIM(location) <> '' ORDER BY location"
        ).fetchall()
    locs = list(defaults)
    for r in rows:
        loc = (r["location"] or "").strip()
        if loc and loc not in locs:
            locs.append(loc)
    return locs


def _find_or_create_product_id(conn, model_name: str, product_cache: Dict[str, int]) -> int:
    key = (model_name or "MODELO INDEFINIDO").strip().upper()
    if key in product_cache:
        return product_cache[key]

    row = conn.execute("SELECT id FROM products WHERE UPPER(TRIM(name)) = %s", (key,)).fetchone()
    if row:
        product_cache[key] = row["id"]
        return row["id"]

    # Fallback para compatibilidade SQLite/PG
    is_pg = type(conn).__name__ == "PGConnWrapper"
    if is_pg:
        res = conn.execute(
            "INSERT INTO products (name, category) VALUES (%s, %s) RETURNING id",
            (model_name.strip(), "Mobilidade Elétrica"),
        ).fetchone()
        pid = res["id"]
    else:
        cur = conn.execute(
            "INSERT INTO products (name, category) VALUES (?, ?)",
            (model_name.strip(), "Mobilidade Elétrica"),
        )
        pid = cur.lastrowid
    product_cache[key] = pid
    return pid


def _infer_tab_location_and_status(sheet_name: str) -> tuple[str, str]:
    up = (sheet_name or "").strip().upper()
    if "MONTADA" in up:
        return "Galpão MAJ", "assembled"
    if "SHOW ROOM" in up or "SHOWROOM" in up:
        return "Showroom", "assembled"
    if "CAIXA" in up:
        return "Galpão MAJ", "available"
    return "COLVIX", "available"


def sync_colvix_sheets_to_stock() -> Dict[str, Any]:
    """
    Sincroniza chassis de TODAS as abas da planilha Google Sheets (COLVIX, Garo, Galpão MAJ, etc.)
    via export XLSX para stock_units.
    Regra Anti-Reset: apenas INSERE chassis novos e nunca sobrescreve status,
    conferências, separações ou vendas já registradas no M-One.
    """
    ensure_stock_audit_schema()
    inserted = 0
    skipped_existing = 0
    errors: List[str] = []
    tabs_processed: List[str] = []
    product_cache: Dict[str, int] = {}

    xlsx_url = f"https://docs.google.com/spreadsheets/d/{COLVIX_SHEET_ID}/export?format=xlsx"
    try:
        req = urllib.request.Request(xlsx_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            wb = openpyxl.load_workbook(io.BytesIO(resp.read()), data_only=True)
    except Exception as ex:
        return {"ok": False, "inserted": 0, "skipped_existing": 0, "errors": [f"Download XLSX: {ex}"]}

    with db() as conn:
        existing_rows = conn.execute("SELECT UPPER(TRIM(chassis)) AS ch, source_tab FROM stock_units").fetchall()
        existing_chassis = {r["ch"] for r in existing_rows if r.get("ch")}
        existing_no_tab = {r["ch"] for r in existing_rows if r.get("ch") and not (r.get("source_tab") or "").strip()}

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = [
                [("" if c is None else str(c).strip()) for c in r]
                for r in ws.iter_rows(values_only=True)
            ]
            header_idx = -1
            col_map: Dict[str, int] = {}
            for idx, r in enumerate(rows[:20]):
                norm = [c.lower() for c in r]
                has_chassi_col = any(("chassi" in c and len(c) <= 25) for c in norm)
                has_meta_col = any(k in c for c in norm for k in ("modelo", "motor", "produto", "cor"))
                if has_chassi_col and has_meta_col:
                    header_idx = idx
                    for c_i, col_name in enumerate(norm):
                        if "chassi" in col_name and "chassis" not in col_map:
                            col_map["chassis"] = c_i
                        elif ("modelo" in col_name or "produto" in col_name or "nome do produto" in col_name) and "model" not in col_map:
                            col_map["model"] = c_i
                        elif (col_name == "cor" or "color" in col_name) and "color" not in col_map:
                            col_map["color"] = c_i
                        elif "motor" in col_name and "motor" not in col_map:
                            col_map["motor"] = c_i
                        elif "cliente" in col_name and "customer" not in col_map:
                            col_map["customer"] = c_i
                        elif "nf de venda" in col_name and "nf_venda" not in col_map:
                            col_map["nf_venda"] = c_i
                    break

            if header_idx < 0 or "chassis" not in col_map:
                continue

            tabs_processed.append(sheet_name)
            tab_loc, tab_default_status = _infer_tab_location_and_status(sheet_name)

            for r in rows[header_idx + 1 :]:
                ch_idx = col_map["chassis"]
                if ch_idx >= len(r):
                    continue
                chassis = r[ch_idx].strip().upper()
                if not chassis or len(chassis) < 6 or " " in chassis:
                    continue

                if chassis in existing_chassis:
                    if chassis in existing_no_tab:
                        conn.execute(
                            "UPDATE stock_units SET source_tab = %s WHERE UPPER(TRIM(chassis)) = %s",
                            (sheet_name, chassis),
                        )
                        existing_no_tab.discard(chassis)
                    skipped_existing += 1
                    continue

                model_name = r[col_map["model"]].strip() if col_map.get("model") is not None and col_map["model"] < len(r) else ""
                if not model_name:
                    model_name = "TRICICLO GARO" if "garo" in sheet_name.lower() else "OUTROS"
                color = r[col_map["color"]].strip() if col_map.get("color") is not None and col_map["color"] < len(r) else ""
                motor_no = r[col_map["motor"]].strip() if col_map.get("motor") is not None and col_map["motor"] < len(r) else ""
                customer = r[col_map["customer"]].strip() if col_map.get("customer") is not None and col_map["customer"] < len(r) else ""
                nf_venda = r[col_map["nf_venda"]].strip() if col_map.get("nf_venda") is not None and col_map["nf_venda"] < len(r) else ""

                initial_status = "sold" if (customer or nf_venda) else tab_default_status
                pid = _find_or_create_product_id(conn, model_name, product_cache)

                conn.execute(
                    """
                    INSERT INTO stock_units (chassis, motor_no, product_id, color, status, location, source_tab, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chassis,
                        motor_no or None,
                        pid,
                        color or None,
                        initial_status,
                        tab_loc,
                        sheet_name,
                        f"Sincronizado aba '{sheet_name}'" + (f" | Cliente: {customer}" if customer else ""),
                    ),
                )
                existing_chassis.add(chassis)
                inserted += 1

        conn.commit()

    return {
        "ok": True,
        "inserted": inserted,
        "skipped_existing": skipped_existing,
        "tabs_processed": tabs_processed,
        "errors": errors,
    }
