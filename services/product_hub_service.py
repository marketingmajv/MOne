"""
M-One Product Hub Service (services/product_hub_service.py)
Serviço central de gestão de produtos mestre, fichas técnicas canônicas e
redistribuição inteligente para os canais de Atacado B2B e Varejo Outlet.
Preserva rigorosamente preços, estoques e as copys contextuais de cada canal.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import db
from services.outlet_specs import MODEL_SPECS
from services.product_hub_propagation import (
    propagate_all_products_to_channels,
    propagate_product_to_channels,
)

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent

_schema_ensured = False


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def run_exec(conn, sql: str, params=()):
    is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
    if is_pg:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def ensure_master_products_schema():
    """Garante a existência da tabela master_products no PostgreSQL/Supabase."""
    global _schema_ensured
    if _schema_ensured:
        return

    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS master_products (
                id SERIAL PRIMARY KEY,
                slug VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                category VARCHAR(100) NOT NULL DEFAULT 'Mobilidade Elétrica',
                brand VARCHAR(100) DEFAULT 'MAJ',
                sku VARCHAR(100),
                status VARCHAR(30) NOT NULL DEFAULT 'active',
                specs_json TEXT,
                copy_showroom TEXT,
                copy_atacado TEXT,
                copy_outlet TEXT,
                image_main TEXT,
                images_gallery TEXT,
                banner_widescreen TEXT,
                sync_atacado BOOLEAN DEFAULT TRUE,
                sync_outlet BOOLEAN DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_master_products_slug ON master_products(slug)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_master_products_status ON master_products(status)")
        try:
            conn.commit()
        except Exception:
            pass

    _schema_ensured = True


def seed_master_products_if_empty():
    """Povoa a base inicial da Central de Produtos com os 21 modelos se a tabela estiver vazia."""
    ensure_master_products_schema()

    with db() as conn:
        count_row = conn.execute("SELECT COUNT(*) as cnt FROM master_products").fetchone()
        cnt = count_row["cnt"] if isinstance(count_row, dict) else (count_row[0] if count_row else 0)
        if cnt > 0:
            return

        logger.info("Povoando Central de Produtos Mestre (master_products) com os 21 modelos...")

        # 1. Carrega dados do Showroom
        sh_path = BASE_DIR / "static" / "data" / "maj_models.json"
        sh_models = {}
        if sh_path.is_file():
            try:
                with open(sh_path, "r", encoding="utf-8") as f:
                    sh_raw = json.load(f)
                for m in sh_raw.get("all_models", []):
                    s = (m.get("slug") or "").lower().strip()
                    if s == "v8-mini-ultra":
                        s = "v8-mini"
                    sh_models[s] = m
            except Exception as e:
                logger.warning("Aviso ao carregar maj_models para seed: %s", e)

        # 2. Carrega Atacado e Outlet existentes
        at_rows = conn.execute("SELECT name, slug, category, description, specs_json, image_main, images_gallery FROM atacado_items").fetchall()
        ou_rows = conn.execute("SELECT name, slug, category, description, specs_json, image_main, images_gallery FROM outlet_items").fetchall()

        at_map = {r["slug"].lower().strip(): r for r in at_rows}
        ou_map = {r["slug"].lower().strip(): r for r in ou_rows}

        all_slugs = sorted(list(set(list(sh_models.keys()) + list(at_map.keys()) + list(ou_map.keys()))))

        for slug in all_slugs:
            sh = sh_models.get(slug)
            at = at_map.get(slug)
            ou = ou_map.get(slug)

            # Nome
            name = (sh.get("modelo") if sh else (at.get("name") if at else (ou.get("name") if ou else slug.upper()))).strip()
            category = (sh.get("categoria") if sh else (at.get("category") if at else (ou.get("category") if ou else "Mobilidade Elétrica")))

            # Ficha Técnica Base
            specs: Dict[str, Any] = {}
            if name in MODEL_SPECS:
                specs.update(MODEL_SPECS[name].get("specs", {}))

            if sh and sh.get("metrics"):
                met = sh["metrics"]
                if met.get("potencia_nominal_w"):
                    specs["Motor"] = f"{met['potencia_nominal_w']}W"
                if met.get("velocidade_max_kmh"):
                    specs["Velocidade Máxima"] = f"Até {met['velocidade_max_kmh']} km/h"
                aut = met.get("autonomia_maxima_km") or met.get("autonomia_conservadora_km")
                if aut:
                    specs["Autonomia"] = f"Até {aut} km" if "km" not in str(aut).lower() else f"Até {aut}"
                if met.get("voltagem_v"):
                    specs["Bateria"] = f"{str(met['voltagem_v']).upper()} Lítio"
                if met.get("carga_maxima_kg"):
                    specs["Carga Máxima"] = f"{met['carga_maxima_kg']} kg"
                if met.get("freios"):
                    specs["Freios"] = met["freios"]
                if met.get("diferencial"):
                    specs["Diferencial"] = met["diferencial"]

            # Resoluções Oficiais de Engenharia (Chamado do Léo SUP-2026-0003)
            if slug in ["v8-mini", "v8-mini-ultra"]:
                specs["Bateria"] = "36V Lítio"
                specs["Motor"] = "500W"
                specs["Autonomia"] = "Até 35 km"
                specs["Carga Máxima"] = "120 kg"
                specs["Freios"] = "Diant: Hidráulico / Tras: Hidráulico"
            elif slug == "mantis":
                specs["Bateria"] = "48V 20Ah Lítio"
                specs["Motor"] = "1000W"
                specs["Velocidade Máxima"] = "Até 32 km/h"
                specs["Autonomia"] = "Até 45 km"
            elif slug == "rz-110":
                specs["Autonomia"] = "Até 45 km"
                specs["Motor"] = "1000W"
                specs["Bateria"] = "60V Lítio"

            # Copys Contextuais
            copy_sh = (sh.get("metrics", {}).get("diferencial") or "").strip() if sh else ""
            copy_at = (at.get("description") or f"Modelo {name} para revenda no atacado. Preços e condições exclusivas com CNPJ.").strip() if at else ""
            copy_ou = (ou.get("description") or f"Queima de estoque oficial MAJ do modelo {name}. Pronta entrega revisado.").strip() if ou else ""

            # Imagens
            img_main = (sh.get("display_image") if sh else (ou.get("image_main") if ou else (at.get("image_main") if at else ""))) or ""
            banner = (sh.get("promo_banner_image") or sh.get("banner_image") or "") if sh else ""
            gallery = (ou.get("images_gallery") if ou else (at.get("images_gallery") if at else "[]")) or "[]"
            if isinstance(gallery, list):
                gallery = json.dumps(gallery)

            run_exec(conn, """
                INSERT INTO master_products (
                    slug, name, category, brand, status, specs_json,
                    copy_showroom, copy_atacado, copy_outlet,
                    image_main, images_gallery, banner_widescreen,
                    sync_atacado, sync_outlet
                ) VALUES (?, ?, ?, 'MAJ', 'active', ?, ?, ?, ?, ?, ?, ?, TRUE, TRUE)
                ON CONFLICT (slug) DO NOTHING
            """, (
                slug, name, category, json.dumps(specs, ensure_ascii=False),
                copy_sh, copy_at, copy_ou,
                img_main, gallery, banner
            ))

        try:
            conn.commit()
        except Exception:
            pass


def parse_decimal_safe(val: Any) -> Optional[float]:
    """Converte valor monetário ou número para float seguro."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("R$", "").replace(" ", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def get_all_master_products(search: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna lista de todos os produtos mestre enriquecidos com dados comerciais de canais."""
    ensure_master_products_schema()
    seed_master_products_if_empty()

    query = "SELECT * FROM master_products WHERE 1=1"
    params: List[Any] = []

    if search:
        query += " AND (name ILIKE ? OR slug ILIKE ? OR category ILIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    if category and category != "all":
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY name ASC"

    with db() as conn:
        rows = run_exec(conn, query, tuple(params)).fetchall()

        # Enriquecimento com dados comerciais do Outlet e Atacado
        ou_rows = run_exec(conn, "SELECT id, slug, name, price_outlet, price_original, installment_12, installment_18, stock_qty, specs_json FROM outlet_items").fetchall()
        at_rows = run_exec(conn, "SELECT id, slug, name, price_outlet, price_atacado_plus, price_original, stock_qty, is_best_seller FROM atacado_items").fetchall()

        ou_map: Dict[str, Dict[str, Any]] = {}
        for o in ou_rows:
            od = dict(o) if isinstance(o, dict) else o
            ou_map[od["slug"]] = od
            ou_map[od["name"].lower().strip()] = od

        at_map: Dict[str, Dict[str, Any]] = {}
        for a in at_rows:
            ad = dict(a) if isinstance(a, dict) else a
            at_map[ad["slug"]] = ad
            at_map[ad["name"].lower().strip()] = ad

        result = []
        for r in rows:
            item = dict(r) if isinstance(r, dict) else r
            sj = item.get("specs_json")
            if isinstance(sj, str):
                try: item["specs_json"] = json.loads(sj)
                except Exception: item["specs_json"] = {}
            elif not isinstance(sj, dict):
                item["specs_json"] = {}

            # Galeria de Fotos como lista JSON
            gal = item.get("images_gallery")
            if isinstance(gal, str):
                try: item["images_gallery"] = json.loads(gal)
                except Exception: item["images_gallery"] = []
            elif isinstance(gal, list):
                item["images_gallery"] = gal
            else:
                item["images_gallery"] = []

            slug = item.get("slug", "")
            name_key = (item.get("name") or "").lower().strip()

            # Dados Comerciais do Outlet
            ou_data = ou_map.get(slug) or ou_map.get(name_key)
            if ou_data:
                ou_specs = ou_data.get("specs_json") or {}
                if isinstance(ou_specs, str):
                    try: ou_specs = json.loads(ou_specs)
                    except Exception: ou_specs = {}
                elif not isinstance(ou_specs, dict):
                    ou_specs = {}

                item["outlet_info"] = {
                    "price_outlet": str(ou_data.get("price_outlet") or ""),
                    "price_original": str(ou_data.get("price_original") or ""),
                    "installment_12": str(ou_data.get("installment_12") or ""),
                    "installment_18": str(ou_data.get("installment_18") or ""),
                    "stock_qty": ou_data.get("stock_qty") or 0,
                    "color_prices": ou_specs.get("color_prices", []) if isinstance(ou_specs, dict) else []
                }
            else:
                item["outlet_info"] = {"color_prices": []}

            # Dados Comerciais do Atacado
            at_key = "v8-mini-ultra" if slug == "v8-mini" else slug
            at_data = at_map.get(at_key) or at_map.get(slug) or at_map.get(name_key)
            if at_data:
                item["atacado_info"] = {
                    "wholesale_price": str(at_data.get("price_outlet") or ""),
                    "price_atacado_plus": str(at_data.get("price_atacado_plus") or ""),
                    "price_original": str(at_data.get("price_original") or ""),
                    "stock_qty": at_data.get("stock_qty") or 0,
                    "is_best_seller": int(at_data.get("is_best_seller") or 0)
                }
            else:
                item["atacado_info"] = {}

            result.append(item)
        return result


def get_master_product_by_id_or_slug(identifier: Any) -> Optional[Dict[str, Any]]:
    """Busca um produto mestre por ID ou por Slug com dados comerciais."""
    all_prods = get_all_master_products()
    for p in all_prods:
        if str(p.get("id")) == str(identifier) or p.get("slug") == str(identifier).strip().lower():
            return p
    return None


def save_master_product(data: Dict[str, Any], product_id: Optional[int] = None) -> int:
    """Cria ou atualiza um produto na Central de Produtos Mestre e atualiza canais."""
    ensure_master_products_schema()

    specs = data.get("specs_json") or {}
    if not isinstance(specs, str):
        specs_str = json.dumps(specs, ensure_ascii=False)
    else:
        specs_str = specs

    gallery = data.get("images_gallery") or []
    if not isinstance(gallery, str):
        gallery_str = json.dumps(gallery, ensure_ascii=False)
    else:
        gallery_str = gallery

    target_slug = data.get("slug") or slugify(data.get("name") or "produto")

    with db() as conn:
        if product_id:
            curr_row = run_exec(conn, "SELECT images_gallery FROM master_products WHERE id = ?", (product_id,)).fetchone()
            curr_gal = curr_row["images_gallery"] if isinstance(curr_row, dict) else (curr_row[0] if curr_row else None)
            final_gal = gallery_str if (gallery_str and gallery_str != "[]") else (curr_gal or "[]")

            run_exec(conn, """
                UPDATE master_products SET
                    name = ?, category = ?, brand = ?, sku = ?, status = ?,
                    specs_json = ?, copy_showroom = ?, copy_atacado = ?, copy_outlet = ?,
                    image_main = ?, images_gallery = ?, banner_widescreen = ?,
                    sync_atacado = ?, sync_outlet = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data.get("name"), data.get("category", "Mobilidade Elétrica"),
                data.get("brand", "MAJ"), data.get("sku", ""), data.get("status", "active"),
                specs_str, data.get("copy_showroom", ""), data.get("copy_atacado", ""), data.get("copy_outlet", ""),
                data.get("image_main", ""), final_gal, data.get("banner_widescreen", ""),
                bool(data.get("sync_atacado", True)), bool(data.get("sync_outlet", True)),
                product_id
            ))
            res_id = product_id
        else:
            cur = run_exec(conn, """
                INSERT INTO master_products (
                    slug, name, category, brand, sku, status,
                    specs_json, copy_showroom, copy_atacado, copy_outlet,
                    image_main, images_gallery, banner_widescreen,
                    sync_atacado, sync_outlet
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, (
                target_slug, data.get("name"), data.get("category", "Mobilidade Elétrica"),
                data.get("brand", "MAJ"), data.get("sku", ""), data.get("status", "active"),
                specs_str, data.get("copy_showroom", ""), data.get("copy_atacado", ""), data.get("copy_outlet", ""),
                data.get("image_main", ""), gallery_str, data.get("banner_widescreen", ""),
                bool(data.get("sync_atacado", True)), bool(data.get("sync_outlet", True))
            ))
            ret = cur.fetchone()
            res_id = ret["id"] if isinstance(ret, dict) else (ret[0] if ret else 0)

        # Atualização Comercial Direta do Canal Outlet (Aba 4)
        if data.get("outlet_price_outlet"):
            ou_price = parse_decimal_safe(data.get("outlet_price_outlet"))
            ou_orig = parse_decimal_safe(data.get("outlet_price_original"))
            ou_i12 = parse_decimal_safe(data.get("outlet_installment_12"))
            ou_i18 = parse_decimal_safe(data.get("outlet_installment_18"))
            ou_stock = int(data.get("outlet_stock_qty") or 0)
            ou_colors_raw = data.get("outlet_color_prices_json")

            ou_row = run_exec(conn, "SELECT id, specs_json FROM outlet_items WHERE slug = ? OR name = ?", (target_slug, data.get("name"))).fetchone()
            if ou_row:
                ou_id = ou_row["id"] if isinstance(ou_row, dict) else ou_row[0]
                ou_specs = ou_row.get("specs_json") if isinstance(ou_row, dict) else ou_row[1]
                if isinstance(ou_specs, str):
                    try: ou_specs = json.loads(ou_specs)
                    except Exception: ou_specs = {}
                elif not isinstance(ou_specs, dict):
                    ou_specs = {}

                if ou_colors_raw:
                    try:
                        ou_specs["color_prices"] = json.loads(ou_colors_raw) if isinstance(ou_colors_raw, str) else ou_colors_raw
                    except Exception:
                        pass

                run_exec(conn, """
                    UPDATE outlet_items SET
                        price_outlet = ?, price_original = ?,
                        installment_12 = ?, installment_18 = ?,
                        stock_qty = ?, specs_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (ou_price, ou_orig, ou_i12, ou_i18, ou_stock, json.dumps(ou_specs, ensure_ascii=False), ou_id))

        # Atualização Comercial Direta do Canal Atacado (Aba 5)
        if data.get("atacado_price"):
            at_price = parse_decimal_safe(data.get("atacado_price"))
            at_plus = parse_decimal_safe(data.get("atacado_price_plus"))
            at_orig = parse_decimal_safe(data.get("atacado_price_original"))
            at_stock = int(data.get("atacado_stock_qty") or 0)
            at_best = 1 if str(data.get("atacado_is_best_seller")) == "1" else 0

            at_slug = "v8-mini-ultra" if target_slug == "v8-mini" else target_slug
            at_row = run_exec(conn, "SELECT id FROM atacado_items WHERE slug = ? OR slug = ? OR name = ?", (at_slug, target_slug, data.get("name"))).fetchone()
            if at_row:
                at_id = at_row["id"] if isinstance(at_row, dict) else at_row[0]
                run_exec(conn, """
                    UPDATE atacado_items SET
                        price_outlet = ?, price_atacado_plus = ?, price_original = ?,
                        stock_qty = ?, is_best_seller = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (at_price, at_plus, at_orig, at_stock, at_best, at_id))

        try:
            conn.commit()
        except Exception:
            pass

    # Propagação automática se solicitada
    if data.get("propagate_now") in ["1", "true", "True", True]:
        try:
            propagate_product_to_channels(res_id)
        except Exception as e:
            logger.warning("Aviso ao propagar produto mestre %s: %s", res_id, e)

    return res_id

