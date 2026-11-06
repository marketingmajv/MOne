"""
M-One Product Hub Propagation Engine (services/product_hub_propagation.py)
Motor de redistribuição e propagação tripartite (Central Mestre -> Outlet, Atacado, Showroom).
Garante sincronização canônica de Fichas Técnicas, Copys e Galerias sem reset de banco.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from database import db

logger = logging.getLogger(__name__)


def run_exec(conn: Any, sql: str, params: tuple = ()) -> Any:
    is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
    if is_pg and "?" in sql:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def propagate_product_to_channels(
    identifier: Any,
    sync_showroom: bool = True,
    get_master_fn: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Propaga a Ficha Técnica Ouro, Copys Contextuais e Galeria de Fotos do Produto Mestre
    para os canais de Atacado B2B, Varejo Outlet e Showroom.
    """
    if get_master_fn:
        prod = get_master_fn(identifier)
    else:
        from services.product_hub_service import get_master_product_by_id_or_slug
        prod = get_master_product_by_id_or_slug(identifier)

    if not prod:
        return {"success": False, "error": "Produto mestre não encontrado"}

    slug = prod["slug"]
    specs = prod.get("specs_json") or {}
    copy_at = (prod.get("copy_atacado") or "").strip()
    copy_ou = (prod.get("copy_outlet") or "").strip()
    copy_sh = (prod.get("copy_showroom") or "").strip()
    img_main = prod.get("image_main") or ""

    gallery = prod.get("images_gallery") or []
    if not isinstance(gallery, str):
        gallery_str = json.dumps(gallery, ensure_ascii=False)
    else:
        gallery_str = gallery

    channels_updated: List[str] = []

    with db() as conn:
        # 1. Propagação para o Outlet MAJ B2C
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

                # Mantém a galeria individual do Outlet preservada (Opção 1)
                # Não sobrescreve images_gallery para manter as fotos cadastradas no canal

                params.append(ou_id)
                run_exec(conn, f"UPDATE outlet_items SET {', '.join(update_fields)} WHERE id = ?", tuple(params))
                channels_updated.append("Outlet")

        # 2. Propagação para o MAJ Atacado CNPJ B2B
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

                # Mantém a galeria individual do Atacado preservada (Opção 1)
                # Não sobrescreve images_gallery para manter as fotos cadastradas no canal

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
    from services.product_hub_service import get_all_master_products
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

