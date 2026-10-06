"""
M-One Outlet Service (services/outlet_service.py)
Serviço de gerenciamento do Catálogo Promocional Outlet MAJ Mobilidade.
Suporta PostgreSQL (Supabase) e SQLite.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_OUTLET_DIR = BASE_DIR / "static" / "img" / "outlet"

DEFAULT_WHATSAPP = "5527999999999"  # Configurável pelo admin
DEFAULT_WA_MESSAGE = "Olá! Vi o modelo {model} no Outlet MAJ Mobilidade por {price} e gostaria de saber mais informações."


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


_outlet_schema_ensured = False


def ensure_outlet_schema():
    """Garante a existência das tabelas outlet_items e outlet_settings no banco."""
    global _outlet_schema_ensured
    if _outlet_schema_ensured:
        return

    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            statements = [
                """CREATE TABLE IF NOT EXISTS outlet_items (
                    id SERIAL PRIMARY KEY,
                    slug VARCHAR(255) UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    category VARCHAR(100) NOT NULL DEFAULT 'Mobilidade Elétrica',
                    condition VARCHAR(50) DEFAULT 'Na caixa',
                    color VARCHAR(100),
                    price_original NUMERIC(10, 2) NOT NULL DEFAULT 0,
                    price_outlet NUMERIC(10, 2) NOT NULL DEFAULT 0,
                    discount_percent INTEGER DEFAULT 0,
                    installment_12 NUMERIC(10, 2) DEFAULT 0,
                    installment_18 NUMERIC(10, 2) DEFAULT 0,
                    installments_text VARCHAR(255),
                    stock_qty INTEGER NOT NULL DEFAULT 1,
                    location VARCHAR(150) DEFAULT 'GALPÃO MAJ',
                    badge VARCHAR(100),
                    specs_json TEXT,
                    description TEXT,
                    image_main TEXT,
                    images_gallery TEXT,
                    status VARCHAR(30) NOT NULL DEFAULT 'active',
                    sort_order INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS outlet_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT
                )""",
                "CREATE INDEX IF NOT EXISTS idx_outlet_items_status ON outlet_items(status)",
                "CREATE INDEX IF NOT EXISTS idx_outlet_items_slug ON outlet_items(slug)"
            ]
            for stmt in statements:
                try:
                    conn.executescript(stmt)
                    conn.commit()
                except Exception as e:
                    logger.debug("Schema stmt error: %s", e)
        else:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS outlet_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Mobilidade Elétrica',
                condition TEXT DEFAULT 'Na caixa',
                color TEXT,
                price_original REAL NOT NULL DEFAULT 0,
                price_outlet REAL NOT NULL DEFAULT 0,
                discount_percent INTEGER DEFAULT 0,
                installment_12 REAL DEFAULT 0,
                installment_18 REAL DEFAULT 0,
                installments_text TEXT,
                stock_qty INTEGER NOT NULL DEFAULT 1,
                location TEXT DEFAULT 'GALPÃO MAJ',
                badge TEXT,
                specs_json TEXT,
                description TEXT,
                image_main TEXT,
                images_gallery TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                sort_order INTEGER DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS outlet_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_outlet_items_status ON outlet_items(status);
            CREATE INDEX IF NOT EXISTS idx_outlet_items_slug ON outlet_items(slug);
            """
            try:
                conn.executescript(schema_sql)
                conn.commit()
            except Exception as e:
                logger.warning("Aviso ao assegurar schema de outlet: %s", e)

        _outlet_schema_ensured = True


def run_exec(conn, sql: str, params=()):
    is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
    if is_pg:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def get_outlet_setting(key: str, default: str = "") -> str:
    ensure_outlet_schema()
    with db() as conn:
        row = run_exec(conn, "SELECT value FROM outlet_settings WHERE key = ?", (key,)).fetchone()
        if row:
            val = row["value"] if isinstance(row, dict) else row[0]
            return val if val is not None else default
        return default


def set_outlet_setting(key: str, value: str):
    ensure_outlet_schema()
    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            run_exec(
                conn,
                """
                INSERT INTO outlet_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value)
            )
        else:
            run_exec(
                conn,
                "INSERT OR REPLACE INTO outlet_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        conn.commit()


def get_all_outlet_items(status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_outlet_schema()
    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        query = "SELECT * FROM outlet_items WHERE 1=1"
        params: List[Any] = []

        if status and status != "all":
            query += " AND status = ?"
            params.append(status)

        if search:
            query += " AND (name ILIKE ? OR category ILIKE ? OR color ILIKE ?)" if is_pg else " AND (name LIKE ? OR category LIKE ? OR color LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])

        query += " ORDER BY stock_qty DESC, price_outlet ASC, sort_order ASC, id ASC"

        rows = run_exec(conn, query, tuple(params)).fetchall()
        items = []
        for r in rows:
            item = dict(r)
            if item.get("images_gallery") and isinstance(item["images_gallery"], str):
                try:
                    item["images_gallery"] = json.loads(item["images_gallery"])
                except Exception:
                    item["images_gallery"] = []
            else:
                item["images_gallery"] = []

            if item.get("specs_json") and isinstance(item["specs_json"], str):
                try:
                    item["specs_json"] = json.loads(item["specs_json"])
                except Exception:
                    item["specs_json"] = {}
            else:
                item["specs_json"] = {}
            items.append(item)
        return items


def get_outlet_item_by_id_or_slug(identifier: Any) -> Optional[Dict[str, Any]]:
    ensure_outlet_schema()
    with db() as conn:
        if str(identifier).isdigit():
            row = run_exec(conn, "SELECT * FROM outlet_items WHERE id = ?", (int(identifier),)).fetchone()
        else:
            row = run_exec(conn, "SELECT * FROM outlet_items WHERE slug = ?", (str(identifier),)).fetchone()

        if not row:
            return None
        item = dict(row)
        if item.get("images_gallery") and isinstance(item["images_gallery"], str):
            try:
                item["images_gallery"] = json.loads(item["images_gallery"])
            except Exception:
                item["images_gallery"] = []
        else:
            item["images_gallery"] = []

        if item.get("specs_json") and isinstance(item["specs_json"], str):
            try:
                item["specs_json"] = json.loads(item["specs_json"])
            except Exception:
                item["specs_json"] = {}
        else:
            item["specs_json"] = {}
        return item


def save_outlet_item(data: Dict[str, Any], item_id: Optional[int] = None) -> int:
    ensure_outlet_schema()
    with db() as conn:
        name = (data.get("name") or "").strip()
        slug = slugify(data.get("slug") or name)
        category = (data.get("category") or "Mobilidade Elétrica").strip()
        condition = (data.get("condition") or "Na caixa").strip()
        color = (data.get("color") or "").strip()
        price_orig = float(data.get("price_original") or 0)
        price_out = float(data.get("price_outlet") or 0)
        
        # Calculate discount
        discount = 0
        if price_orig > price_out and price_orig > 0:
            discount = int(round(((price_orig - price_out) / price_orig) * 100))

        inst12 = float(data.get("installment_12") or 0)
        inst18 = float(data.get("installment_18") or 0)
        if inst12 == 0 and price_out > 0:
            inst12 = round((price_out * 1.1013216) / 12, 2)
        if inst18 == 0 and price_out > 0:
            inst18 = round((price_out * 1.1437722) / 18, 2)

        inst_text = data.get("installments_text") or f"12x de R$ {inst12:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        stock_qty = int(data.get("stock_qty") or 0)
        location = (data.get("location") or "GALPÃO MAJ").strip()
        badge = (data.get("badge") or "").strip()
        description = (data.get("description") or "").strip()
        image_main = (data.get("image_main") or "").strip()
        
        gallery = data.get("images_gallery")
        if isinstance(gallery, list):
            gallery_str = json.dumps(gallery, ensure_ascii=False)
        elif isinstance(gallery, str):
            gallery_str = gallery
        else:
            gallery_str = "[]"

        specs = data.get("specs_json")
        if isinstance(specs, dict):
            specs_str = json.dumps(specs, ensure_ascii=False)
        elif isinstance(specs, str):
            specs_str = specs
        else:
            specs_str = "{}"

        status = (data.get("status") or "active").strip()
        sort_order = int(data.get("sort_order") or 0)
        notes = (data.get("notes") or "").strip()

        if item_id:
            query = """
            UPDATE outlet_items SET
                slug = ?, name = ?, category = ?, condition = ?, color = ?,
                price_original = ?, price_outlet = ?, discount_percent = ?,
                installment_12 = ?, installment_18 = ?, installments_text = ?,
                stock_qty = ?, location = ?, badge = ?, specs_json = ?,
                description = ?, image_main = ?, images_gallery = ?,
                status = ?, sort_order = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """
            run_exec(
                conn,
                query,
                (
                    slug, name, category, condition, color,
                    price_orig, price_out, discount,
                    inst12, inst18, inst_text,
                    stock_qty, location, badge, specs_str,
                    description, image_main, gallery_str,
                    status, sort_order, notes, item_id
                )
            )
            conn.commit()
            return item_id
        else:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            query = """
            INSERT INTO outlet_items (
                slug, name, category, condition, color,
                price_original, price_outlet, discount_percent,
                installment_12, installment_18, installments_text,
                stock_qty, location, badge, specs_json,
                description, image_main, images_gallery,
                status, sort_order, notes
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )
            """
            if is_pg:
                query += " RETURNING id"

            cur = run_exec(
                conn,
                query,
                (
                    slug, name, category, condition, color,
                    price_orig, price_out, discount,
                    inst12, inst18, inst_text,
                    stock_qty, location, badge, specs_str,
                    description, image_main, gallery_str,
                    status, sort_order, notes
                )
            )
            conn.commit()
            return cur.lastrowid or 0


def delete_outlet_item(item_id: int):
    ensure_outlet_schema()
    with db() as conn:
        run_exec(conn, "DELETE FROM outlet_items WHERE id = ?", (item_id,))
        conn.commit()


def parse_currency(val_str: str) -> float:
    if not val_str:
        return 0.0
    clean = re.sub(r"[^\d,\.]", "", str(val_str)).strip()
    if not clean:
        return 0.0
    if "," in clean and "." in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return 0.0
