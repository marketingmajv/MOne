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


def get_all_master_products(search: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna lista de todos os produtos mestre com dados parseados."""
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
        result = []
        for r in rows:
            item = dict(r) if isinstance(r, dict) else r
            sj = item.get("specs_json")
            if isinstance(sj, str):
                try:
                    item["specs_json"] = json.loads(sj)
                except Exception:
                    item["specs_json"] = {}
            elif not sj:
                item["specs_json"] = {}
            result.append(item)
        return result


def get_master_product_by_id_or_slug(identifier: Any) -> Optional[Dict[str, Any]]:
    """Busca um produto mestre por ID ou por Slug."""
    ensure_master_products_schema()
    with db() as conn:
        if str(identifier).isdigit():
            row = run_exec(conn, "SELECT * FROM master_products WHERE id = ?", (int(identifier),)).fetchone()
        else:
            row = run_exec(conn, "SELECT * FROM master_products WHERE slug = ?", (str(identifier).strip().lower(),)).fetchone()

        if not row:
            return None

        item = dict(row) if isinstance(row, dict) else row
        sj = item.get("specs_json")
        if isinstance(sj, str):
            try:
                item["specs_json"] = json.loads(sj)
            except Exception:
                item["specs_json"] = {}
        return item


def save_master_product(data: Dict[str, Any], product_id: Optional[int] = None) -> int:
    """Cria ou atualiza um produto na Central de Produtos Mestre."""
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

    with db() as conn:
        if product_id:
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
                data.get("image_main", ""), gallery_str, data.get("banner_widescreen", ""),
                bool(data.get("sync_atacado", True)), bool(data.get("sync_outlet", True)),
                product_id
            ))
            res_id = product_id
        else:
            slug = data.get("slug") or slugify(data.get("name") or "produto")
            cur = run_exec(conn, """
                INSERT INTO master_products (
                    slug, name, category, brand, sku, status,
                    specs_json, copy_showroom, copy_atacado, copy_outlet,
                    image_main, images_gallery, banner_widescreen,
                    sync_atacado, sync_outlet
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, (
                slug, data.get("name"), data.get("category", "Mobilidade Elétrica"),
                data.get("brand", "MAJ"), data.get("sku", ""), data.get("status", "active"),
                specs_str, data.get("copy_showroom", ""), data.get("copy_atacado", ""), data.get("copy_outlet", ""),
                data.get("image_main", ""), gallery_str, data.get("banner_widescreen", ""),
                bool(data.get("sync_atacado", True)), bool(data.get("sync_outlet", True))
            ))
            ret = cur.fetchone()
            res_id = ret["id"] if isinstance(ret, dict) else (ret[0] if ret else 0)

        try:
            conn.commit()
        except Exception:
            pass

    return res_id


def propagate_product_to_channels(identifier: Any, sync_showroom: bool = True) -> Dict[str, Any]:
    """
    Propaga a Ficha Técnica Ouro e as Copys Contextuais do Produto Mestre para os canais
    de Atacado B2B e Varejo Outlet. NUNCA reseta preços, estoques ou variações de cores!
    """
    prod = get_master_product_by_id_or_slug(identifier)
    if not prod:
        return {"success": False, "error": "Produto mestre não encontrado"}

    slug = prod["slug"]
    specs = prod.get("specs_json") or {}
    copy_at = (prod.get("copy_atacado") or "").strip()
    copy_ou = (prod.get("copy_outlet") or "").strip()
    copy_sh = (prod.get("copy_showroom") or "").strip()
    img_main = prod.get("image_main") or ""

    channels_updated = []

    with db() as conn:
        # 1. Propagação para o Outlet
        if prod.get("sync_outlet") is not False:
            ou_row = run_exec(conn, "SELECT id, specs_json FROM outlet_items WHERE slug = ? OR name = ?", (slug, prod["name"])).fetchone()
            if ou_row:
                ou_id = ou_row["id"] if isinstance(ou_row, dict) else ou_row[0]
                curr_specs = ou_row.get("specs_json") if isinstance(ou_row, dict) else ou_row[1]
                if isinstance(curr_specs, str):
                    try:
                        curr_specs = json.loads(curr_specs)
                    except Exception:
                        curr_specs = {}
                elif not isinstance(curr_specs, dict):
                    curr_specs = {}

                merged_specs = dict(specs)
                if "color_prices" in curr_specs:
                    merged_specs["color_prices"] = curr_specs["color_prices"]

                update_fields = ["specs_json = ?", "updated_at = CURRENT_TIMESTAMP"]
                params = [json.dumps(merged_specs, ensure_ascii=False)]

                if copy_ou:
                    update_fields.append("description = ?")
                    params.append(copy_ou)

                if img_main:
                    update_fields.append("image_main = ?")
                    params.append(img_main)

                params.append(ou_id)
                run_exec(conn, f"UPDATE outlet_items SET {', '.join(update_fields)} WHERE id = ?", tuple(params))
                channels_updated.append("Outlet")

        # 2. Propagação para o Atacado
        if prod.get("sync_atacado") is not False:
            at_slug = "v8-mini-ultra" if slug == "v8-mini" else slug
            at_row = run_exec(conn, "SELECT id, specs_json FROM atacado_items WHERE slug = ? OR slug = ? OR name = ?", (at_slug, slug, prod["name"])).fetchone()
            if at_row:
                at_id = at_row["id"] if isinstance(at_row, dict) else at_row[0]
                update_fields = ["specs_json = ?", "updated_at = CURRENT_TIMESTAMP"]
                params = [json.dumps(specs, ensure_ascii=False)]

                if copy_at:
                    update_fields.append("description = ?")
                    params.append(copy_at)

                if img_main:
                    update_fields.append("image_main = ?")
                    params.append(img_main)

                params.append(at_id)
                run_exec(conn, f"UPDATE atacado_items SET {', '.join(update_fields)} WHERE id = ?", tuple(params))
                channels_updated.append("Atacado B2B")

        try:
            conn.commit()
        except Exception:
            pass

    # 3. Propagação para o Showroom & Modelos
    if sync_showroom:
        try:
            from services.showroom_crud_service import load_model_overrides, save_model_overrides
            overrides = load_model_overrides()
            sh_ovr = overrides.get(slug, {}) if isinstance(overrides.get(slug), dict) else {}
            if copy_sh:
                sh_ovr["descricao_livre"] = copy_sh
            if prod.get("banner_widescreen"):
                sh_ovr["banner_image"] = prod["banner_widescreen"]
                sh_ovr["promo_banner_image"] = prod["banner_widescreen"]
            if img_main:
                sh_ovr["display_image"] = img_main

            metrics = sh_ovr.get("metrics", {}) if isinstance(sh_ovr.get("metrics"), dict) else {}
            if specs.get("Motor"):
                metrics["potencia_nominal_w"] = str(specs["Motor"])
            if specs.get("Velocidade Máxima"):
                metrics["velocidade_max_kmh"] = str(specs["Velocidade Máxima"])
            if specs.get("Autonomia"):
                metrics["autonomia_conservadora_km"] = str(specs["Autonomia"])
            if metrics:
                sh_ovr["metrics"] = metrics

            overrides[slug] = sh_ovr
            save_model_overrides(overrides)
            channels_updated.append("Showroom")
        except Exception as e:
            logger.warning("Aviso ao propagar para o Showroom (%s): %s", slug, e)

    return {
        "success": True,
        "product": prod["name"],
        "channels_updated": channels_updated,
        "specs_propagated": list(specs.keys())
    }


def propagate_all_products_to_channels() -> Dict[str, Any]:
    """Redistribui em massa todos os produtos mestre ativos para os canais."""
    products = get_all_master_products()
    count = 0
    details = []

    try:
        from services.showroom_crud_service import load_model_overrides, save_model_overrides
        overrides = load_model_overrides()
    except Exception:
        overrides = {}

    for p in products:
        if p.get("status") == "active":
            slug = p["slug"]
            specs = p.get("specs_json") or {}
            res = propagate_product_to_channels(p["id"], sync_showroom=False)
            if res.get("success"):
                count += 1
                chans = list(res.get("channels_updated", []))

                if overrides is not None:
                    sh_ovr = overrides.get(slug, {}) if isinstance(overrides.get(slug), dict) else {}
                    if p.get("copy_showroom"):
                        sh_ovr["descricao_livre"] = p["copy_showroom"].strip()
                    if p.get("banner_widescreen"):
                        sh_ovr["banner_image"] = p["banner_widescreen"]
                        sh_ovr["promo_banner_image"] = p["banner_widescreen"]
                    if p.get("image_main"):
                        sh_ovr["display_image"] = p["image_main"]

                    metrics = sh_ovr.get("metrics", {}) if isinstance(sh_ovr.get("metrics"), dict) else {}
                    if specs.get("Motor"):
                        metrics["potencia_nominal_w"] = str(specs["Motor"])
                    if specs.get("Velocidade Máxima"):
                        metrics["velocidade_max_kmh"] = str(specs["Velocidade Máxima"])
                    if specs.get("Autonomia"):
                        metrics["autonomia_conservadora_km"] = str(specs["Autonomia"])
                    if metrics:
                        sh_ovr["metrics"] = metrics
                    overrides[slug] = sh_ovr
                    chans.append("Showroom")

                details.append(f"{p['name']} ({', '.join(chans)})")

    if overrides:
        try:
            from services.showroom_crud_service import save_model_overrides
            save_model_overrides(overrides)
        except Exception as e:
            logger.warning("Aviso ao salvar overrides em massa para o Showroom: %s", e)

    return {
        "success": True,
        "total_propagated": count,
        "details": details
    }
