"""
M-One MAJ Atacado Service (services/atacado_service.py)
Serviço de gerenciamento do Catálogo Atacado MAJ Mobilidade (Exclusivo CNPJ).
Totalmente independente do Catálogo Outlet.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_WHATSAPP = "5527999999999"
DEFAULT_WA_MESSAGE = "Olá! Tenho interesse no modelo {model} no Atacado MAJ Mobilidade (CNPJ) por {price}. Gostaria de solicitar uma cotação/pedido."

COLVIX_SHEET_ID = "16csh8zLt8OjRER-3TnDrpq34sQX5J17sue4Cuq8txSY"
COLVIX_GIDS = ["1364652365", "1136023792", "112393779"]

MAJ_SHEET_ID = "1tFwiOFjfVPp2ll-SLB79bG2c6wcIJHc3yHgQxK6PDxo"
MAJ_GID = "1059541403"

PRICES_SHEET_ID = "1xtZaD2vxOj1NwvQ3CFBJJcONh_TL5AtVKjftNJPUIAc"
PRICES_GID = "494760175"

_atacado_schema_ensured = False


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def ensure_atacado_schema():
    """Garante a existência das tabelas atacado_items e atacado_settings no banco."""
    global _atacado_schema_ensured
    if _atacado_schema_ensured:
        return

    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            statements = [
                """CREATE TABLE IF NOT EXISTS atacado_items (
                    id SERIAL PRIMARY KEY,
                    slug VARCHAR(255) UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    category VARCHAR(100) NOT NULL DEFAULT 'Atacado CNPJ',
                    condition VARCHAR(50) DEFAULT 'Novo',
                    color VARCHAR(500),
                    price_original NUMERIC(10, 2) DEFAULT 0,
                    price_outlet NUMERIC(10, 2) NOT NULL DEFAULT 0,
                    price_atacado_plus NUMERIC(10, 2) DEFAULT 0,
                    discount_percent INTEGER DEFAULT 0,
                    installment_12 NUMERIC(10, 2) DEFAULT 0,
                    installment_18 NUMERIC(10, 2) DEFAULT 0,
                    installments_text VARCHAR(255),
                    stock_qty INTEGER NOT NULL DEFAULT 0,
                    location VARCHAR(150) DEFAULT 'GALPÃO M-ONE / GALPÃO MAJ NOVO',
                    badge VARCHAR(100) DEFAULT 'EXCLUSIVO CNPJ',
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
                """CREATE TABLE IF NOT EXISTS atacado_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT
                )""",
                "CREATE INDEX IF NOT EXISTS idx_atacado_items_status ON atacado_items(status)",
                "CREATE INDEX IF NOT EXISTS idx_atacado_items_slug ON atacado_items(slug)"
            ]
            for stmt in statements:
                try:
                    conn.executescript(stmt)
                    conn.commit()
                except Exception as e:
                    logger.debug("Atacado Schema stmt error: %s", e)
        else:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS atacado_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Atacado CNPJ',
                condition TEXT DEFAULT 'Novo',
                color TEXT,
                price_original REAL DEFAULT 0,
                price_outlet REAL NOT NULL DEFAULT 0,
                price_atacado_plus REAL DEFAULT 0,
                discount_percent INTEGER DEFAULT 0,
                installment_12 REAL DEFAULT 0,
                installment_18 REAL DEFAULT 0,
                installments_text TEXT,
                stock_qty INTEGER NOT NULL DEFAULT 0,
                location TEXT DEFAULT 'GALPÃO M-ONE / GALPÃO MAJ NOVO',
                badge TEXT DEFAULT 'EXCLUSIVO CNPJ',
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
            CREATE TABLE IF NOT EXISTS atacado_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_atacado_items_status ON atacado_items(status);
            CREATE INDEX IF NOT EXISTS idx_atacado_items_slug ON atacado_items(slug);
            """
            try:
                conn.executescript(schema_sql)
                conn.commit()
            except Exception as e:
                logger.warning("Aviso ao assegurar schema de atacado: %s", e)

        _atacado_schema_ensured = True


def run_exec(conn, sql: str, params=()):
    is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
    if is_pg:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def get_atacado_setting(key: str, default: str = "") -> str:
    ensure_atacado_schema()
    with db() as conn:
        row = run_exec(conn, "SELECT value FROM atacado_settings WHERE key = ?", (key,)).fetchone()
        if row:
            val = row["value"] if isinstance(row, dict) else row[0]
            return val if val is not None else default
        return default


def set_atacado_setting(key: str, value: str):
    ensure_atacado_schema()
    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            run_exec(
                conn,
                """
                INSERT INTO atacado_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value)
            )
        else:
            run_exec(
                conn,
                "INSERT OR REPLACE INTO atacado_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        conn.commit()


def get_all_atacado_items(status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    ensure_atacado_schema()
    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        query = "SELECT * FROM atacado_items WHERE 1=1"
        params: List[Any] = []

        if status and status != "all":
            query += " AND status = ?"
            params.append(status)

        if search:
            query += " AND (name ILIKE ? OR category ILIKE ? OR color ILIKE ?)" if is_pg else " AND (name LIKE ? OR category LIKE ? OR color LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])

        query += " ORDER BY sort_order ASC, price_outlet ASC, id ASC"

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


def get_atacado_item_by_id_or_slug(identifier: Any) -> Optional[Dict[str, Any]]:
    ensure_atacado_schema()
    with db() as conn:
        if str(identifier).isdigit():
            row = run_exec(conn, "SELECT * FROM atacado_items WHERE id = ?", (int(identifier),)).fetchone()
        else:
            row = run_exec(conn, "SELECT * FROM atacado_items WHERE slug = ?", (str(identifier),)).fetchone()

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


def save_atacado_item(data: Dict[str, Any], item_id: Optional[int] = None) -> int:
    ensure_atacado_schema()
    with db() as conn:
        name = (data.get("name") or "").strip()
        slug = slugify(data.get("slug") or name)
        category = (data.get("category") or "Atacado CNPJ").strip()
        condition = (data.get("condition") or "Novo").strip()
        color = (data.get("color") or "").strip()
        price_orig = float(data.get("price_original") or 0)
        price_out = float(data.get("price_outlet") or 0)
        price_plus = float(data.get("price_atacado_plus") or 0)
        
        discount = 0
        if price_orig > price_out and price_orig > 0:
            discount = int(round(((price_orig - price_out) / price_orig) * 100))

        inst12 = float(data.get("installment_12") or 0)
        inst18 = float(data.get("installment_18") or 0)
        if inst12 == 0 and price_out > 0:
            inst12 = round((price_out * 1.1416) / 12, 2)
        if inst18 == 0 and price_out > 0:
            inst18 = round((price_out * 1.1855) / 18, 2)

        inst_text = data.get("installments_text") or f"12x de R$ {inst12:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        stock_qty = int(data.get("stock_qty") or 0)
        location = (data.get("location") or "GALPÃO M-ONE / GALPÃO MAJ NOVO").strip()
        badge = (data.get("badge") or "EXCLUSIVO CNPJ").strip()
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
            UPDATE atacado_items SET
                slug = ?, name = ?, category = ?, condition = ?, color = ?,
                price_original = ?, price_outlet = ?, price_atacado_plus = ?, discount_percent = ?,
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
                    price_orig, price_out, price_plus, discount,
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
            INSERT INTO atacado_items (
                slug, name, category, condition, color,
                price_original, price_outlet, price_atacado_plus, discount_percent,
                installment_12, installment_18, installments_text,
                stock_qty, location, badge, specs_json,
                description, image_main, images_gallery,
                status, sort_order, notes
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
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
                    price_orig, price_out, price_plus, discount,
                    inst12, inst18, inst_text,
                    stock_qty, location, badge, specs_str,
                    description, image_main, gallery_str,
                    status, sort_order, notes
                )
            )
            conn.commit()
            return cur.lastrowid or 0


def delete_atacado_item(item_id: int):
    ensure_atacado_schema()
    with db() as conn:
        run_exec(conn, "DELETE FROM atacado_items WHERE id = ?", (item_id,))
        conn.commit()


def parse_price_str(val_str: str) -> float:
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


def sync_atacado_catalog() -> Dict[str, Any]:
    """
    Sincroniza e unifica o Catálogo MAJ Atacado (CNPJ):
    1. Importa preços de Atacado da planilha de preços (1xtZaD2vxOj1NwvQ3CFBJJcONh_TL5AtVKjftNJPUIAc).
    2. Importa estoque do Galpão COLVIX (16csh8zLt8OjRER-3TnDrpq34sQX5J17sue4Cuq8txSY - 3 gids).
       Desconsidera unidades vendidas (com nome de cliente).
    3. Unifica estoque com Galpão MAJ ANTIGA (1tFwiOFjfVPp2ll-SLB79bG2c6wcIJHc3yHgQxK6PDxo).
    4. Atualiza/cria os produtos na tabela atacado_items, combinando todas as cores por modelo.
    5. Reaproveita imagens já existentes do Outlet se disponíveis.
    """
    ensure_atacado_schema()
    
    # 1. Carregar Preços Atacado
    prices_url = f"https://docs.google.com/spreadsheets/d/{PRICES_SHEET_ID}/export?format=csv&gid={PRICES_GID}"
    wholesale_prices = {}
    try:
        req = urllib.request.Request(prices_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = [r for r in reader if any(r)]
        for r in rows[3:]:
            if len(r) >= 3 and r[0].strip():
                model = r[0].strip()
                wholesale_prices[model] = {
                    "atacado": parse_price_str(r[1]),
                    "atacado_plus": parse_price_str(r[2]),
                    "varejo_12x": parse_price_str(r[5]) if len(r) > 5 else 0.0,
                    "varejo_12x_parc": parse_price_str(r[6]) if len(r) > 6 else 0.0,
                    "varejo_18x_parc": parse_price_str(r[7]) if len(r) > 7 else 0.0,
                    "peso": r[8].strip() if len(r) > 8 else "",
                    "dimensoes": r[9].strip() if len(r) > 9 else ""
                }
    except Exception as e:
        logger.error("Erro ao carregar planilha de preços de atacado: %s", e)

    # 2. Carregar Estoque MAJ ANTIGA
    maj_url = f"https://docs.google.com/spreadsheets/d/{MAJ_SHEET_ID}/export?format=csv&gid={MAJ_GID}"
    combined_stock = defaultdict(lambda: {"total_qty": 0, "colors": defaultdict(int), "sources": set()})
    try:
        req = urllib.request.Request(maj_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = [r for r in reader if any(r)]
        for r in rows[2:]:
            if len(r) >= 4 and r[0].strip():
                model = r[0].strip()
                color = r[2].strip() if len(r) > 2 and r[2].strip() else "Conforme lote"
                try:
                    avail = int(r[3].strip())
                except Exception:
                    avail = 0
                if avail > 0:
                    combined_stock[model]["total_qty"] += avail
                    combined_stock[model]["colors"][color] += avail
                    combined_stock[model]["sources"].add("GALPÃO MAJ NOVO")
    except Exception as e:
        logger.error("Erro ao carregar planilha MAJ Antiga: %s", e)

    # 3. Carregar Estoque COLVIX
    colvix_sold_count = 0
    for gid in COLVIX_GIDS:
        url = f"https://docs.google.com/spreadsheets/d/{COLVIX_SHEET_ID}/export?format=csv&gid={gid}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp:
                content = resp.read().decode("utf-8")
            reader = csv.reader(io.StringIO(content))
            rows = [r for r in reader if any(r)]
            for r in rows[6:]:
                if len(r) >= 4 and r[0].strip().isdigit():
                    model = r[2].strip()
                    color = r[3].strip() if len(r) > 3 and r[3].strip() else "Conforme lote"
                    cliente = r[6].strip() if len(r) > 6 else ""
                    
                    if cliente:
                        colvix_sold_count += 1
                    else:
                        combined_stock[model]["total_qty"] += 1
                        combined_stock[model]["colors"][color] += 1
                        combined_stock[model]["sources"].add("GALPÃO M-ONE (COLVIX)")
        except Exception as e:
            logger.error("Erro ao carregar aba COLVIX gid %s: %s", gid, e)

    # Carregar imagens existentes do Outlet para reaproveitar visual
    outlet_images = {}
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            o_rows = run_exec(conn, "SELECT name, image_main, images_gallery, specs_json FROM outlet_items").fetchall()
            for r in o_rows:
                d = dict(r)
                outlet_images[d["name"]] = {
                    "image_main": d.get("image_main") or "",
                    "images_gallery": d.get("images_gallery") or "[]",
                    "specs_json": d.get("specs_json") or "{}"
                }
    except Exception as e:
        logger.warning("Erro ao carregar imagens do Outlet: %s", e)

    # 4. Salvar/Atualizar no Banco de Dados
    updated_models = []
    total_catalog_stock = 0

    with db() as conn:
        # Pega todos os modelos únicos encontrados no estoque ou nos preços
        all_models = sorted(list(set(wholesale_prices.keys()) | set(combined_stock.keys())))

        for model in all_models:
            pinfo = wholesale_prices.get(model, {})
            sinfo = combined_stock.get(model, {"total_qty": 0, "colors": {}, "sources": set()})

            price_atacado = pinfo.get("atacado") or 0.0
            price_atacado_plus = pinfo.get("atacado_plus") or 0.0
            p12 = pinfo.get("varejo_12x_parc") or (round((price_atacado * 1.1416) / 12, 2) if price_atacado > 0 else 0.0)
            p18 = pinfo.get("varejo_18x_parc") or (round((price_atacado * 1.1855) / 18, 2) if price_atacado > 0 else 0.0)
            p12_total = pinfo.get("varejo_12x") or (round(price_atacado * 1.1416, 2) if price_atacado > 0 else 0.0)

            # Lista de cores combinadas com quantidades
            colors_dict = sinfo["colors"]
            if colors_dict:
                colors_list = [f"{c} ({q} un)" for c, q in colors_dict.items()]
                colors_str = ", ".join(colors_list)
            else:
                colors_str = "Cores sob consulta"

            total_qty = sinfo["total_qty"]
            total_catalog_stock += total_qty
            sources_str = " & ".join(sorted(list(sinfo["sources"]))) if sinfo["sources"] else "GALPÃO M-ONE / MAJ"

            # Imagem e Specs do Outlet se disponível
            o_info = outlet_images.get(model, {})
            image_main = o_info.get("image_main") or ""
            images_gallery = o_info.get("images_gallery") or "[]"
            
            # Montar specs_json rico
            specs_obj = {}
            if o_info.get("specs_json"):
                try:
                    specs_obj = json.loads(o_info["specs_json"]) if isinstance(o_info["specs_json"], str) else o_info["specs_json"]
                except Exception:
                    specs_obj = {}

            specs_obj["Preço Atacado À Vista"] = f"R$ {price_atacado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if price_atacado > 0 else "Sob consulta"
            if price_atacado_plus > 0:
                specs_obj["Preço Atacado Plus"] = f"R$ {price_atacado_plus:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if pinfo.get("peso"):
                specs_obj["Peso Embalado"] = pinfo["peso"]
            if pinfo.get("dimensoes"):
                specs_obj["Dimensões Embalagem"] = pinfo["dimensoes"]

            specs_obj["Disponibilidade em Estoque"] = f"{total_qty} unidades"
            specs_obj["Localização do Estoque"] = sources_str
            specs_obj["Cores e Lotes"] = colors_str

            # Verificar se produto já existe no banco atacado
            existing = run_exec(conn, "SELECT id FROM atacado_items WHERE name = ?", (model,)).fetchone()
            
            item_data = {
                "name": model,
                "slug": slugify(model),
                "category": "Atacado CNPJ",
                "condition": "Novo na caixa / Revisado",
                "color": colors_str,
                "price_original": p12_total,
                "price_outlet": price_atacado,
                "price_atacado_plus": price_atacado_plus,
                "installment_12": p12,
                "installment_18": p18,
                "stock_qty": total_qty,
                "location": sources_str,
                "badge": "VENDA ATACADO CNPJ",
                "specs_json": specs_obj,
                "description": f"Modelo {model} para revenda no atacado. Preços exclusivos para compras com CNPJ. Veículos completos com garantia oficial de fábrica MAJ Mobilidade.",
                "image_main": image_main,
                "images_gallery": images_gallery,
                "status": "active" if (total_qty > 0 or price_atacado > 0) else "inactive"
            }

            if existing:
                e_id = existing["id"] if isinstance(existing, dict) else existing[0]
                save_atacado_item(item_data, item_id=e_id)
            else:
                save_atacado_item(item_data)

            updated_models.append(model)

    return {
        "success": True,
        "total_models": len(updated_models),
        "total_stock": total_catalog_stock,
        "colvix_sold_units_excluded": colvix_sold_count,
        "models": updated_models
    }
