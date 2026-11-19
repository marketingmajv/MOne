"""
M-One Product Hierarchy Guard (services/product_hierarchy_guard.py)
Garante a hierarquia canônica da Central de Produtos (master_products) no topo dos canais:
1. Nenhum produto nasce ou vaza diretamente nos canais (Outlet, Atacado, Showroom).
2. A Central define EM QUAIS CANAIS o produto é permitido (sync_outlet, sync_atacado, sync_showroom).
3. Cada canal preserva autonomia sobre seu status interno (active/inactive), preços e estoque.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from database import db

logger = logging.getLogger(__name__)

CHANNEL_FIELD_MAP = {
    "outlet": "sync_outlet",
    "atacado": "sync_atacado",
    "showroom": "sync_showroom",
}

SLUG_ALIASES = {
    "v8-mini-ultra": "v8-mini",
    "v8-mini": "v8-mini-ultra",
}


def _norm_text(val: Any) -> str:
    txt = str(val or "").strip().lower()
    return re.sub(r"\s+", " ", txt)


def _norm_slug(val: Any) -> str:
    return str(val or "").strip().lower()


def _compact(val: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(val or "").lower())


def get_master_channel_rules() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Carrega regras de elegibilidade por canal diretamente da Central de Produtos."""
    from services.product_hub_service import ensure_master_products_schema

    ensure_master_products_schema()
    by_slug: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    by_compact: Dict[str, Dict[str, Any]] = {}

    with db() as conn:
        rows = conn.execute(
            "SELECT id, slug, name, sync_outlet, sync_atacado, sync_showroom FROM master_products"
        ).fetchall()

    for r in rows:
        row = dict(r) if isinstance(r, dict) or hasattr(r, "keys") else {
            "id": r[0],
            "slug": r[1],
            "name": r[2],
            "sync_outlet": r[3],
            "sync_atacado": r[4],
            "sync_showroom": r[5],
        }
        rule = {
            "id": row["id"],
            "slug": _norm_slug(row.get("slug")),
            "name": _norm_text(row.get("name")),
            "sync_outlet": True if row.get("sync_outlet") is None else bool(row.get("sync_outlet")),
            "sync_atacado": True if row.get("sync_atacado") is None else bool(row.get("sync_atacado")),
            "sync_showroom": True if row.get("sync_showroom") is None else bool(row.get("sync_showroom")),
        }
        if rule["slug"]:
            by_slug[rule["slug"]] = rule
            by_compact[_compact(rule["slug"])] = rule
        if rule["name"]:
            by_name[rule["name"]] = rule
            by_compact[_compact(rule["name"])] = rule

    return {"by_slug": by_slug, "by_name": by_name, "by_compact": by_compact}


def find_master_rule(
    slug: str = "",
    name: str = "",
    rules: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    """Localiza a regra do produto mestre por slug, alias conhecido ou nome normalizado."""
    cache = rules or get_master_channel_rules()
    by_slug = cache["by_slug"]
    by_name = cache["by_name"]
    by_compact = cache.get("by_compact", {})

    s = _norm_slug(slug)
    if s:
        if s in by_slug:
            return by_slug[s]
        alias = SLUG_ALIASES.get(s)
        if alias and alias in by_slug:
            return by_slug[alias]
        cs = _compact(s)
        if cs in by_compact:
            return by_compact[cs]

    n = _norm_text(name)
    if n:
        if n in by_name:
            return by_name[n]
        cn = _compact(n)
        if cn in by_compact:
            return by_compact[cn]
    return None


def is_allowed_in_channel(
    channel: str,
    slug: str = "",
    name: str = "",
    rules: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> bool:
    """Retorna True somente se o produto existir na Central e tiver o canal habilitado."""
    field = CHANNEL_FIELD_MAP.get(channel)
    if not field:
        return False
    rule = find_master_rule(slug=slug, name=name, rules=rules)
    if not rule:
        return False
    return bool(rule.get(field, False))


def filter_channel_items(channel: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra itens de vitrine pública mantendo apenas produtos autorizados pela Central."""
    if not items:
        return []
    rules = get_master_channel_rules()
    filtered: List[Dict[str, Any]] = []
    for item in items:
        slug = item.get("slug") or ""
        name = item.get("name") or item.get("modelo") or ""
        if is_allowed_in_channel(channel, slug=slug, name=name, rules=rules):
            filtered.append(item)
    return filtered


def validate_channel_write(
    channel: str,
    slug: str = "",
    name: str = "",
    is_create: bool = False,
) -> Tuple[bool, str]:
    """Valida criação/edição em um canal contra a hierarquia da Central de Produtos."""
    if is_create:
        return (
            False,
            "Hierarquia M-One: todo novo produto deve ser cadastrado na Central de Produtos (/admin/central-produtos) antes de ir para os canais.",
        )

    rule = find_master_rule(slug=slug, name=name)
    if not rule:
        return (
            False,
            "Produto sem vínculo com a Central de Produtos (/admin/central-produtos). Cadastre-o na Central antes de publicar ou editar neste canal.",
        )

    field = CHANNEL_FIELD_MAP.get(channel)
    if field and not rule.get(field, False):
        return (
            False,
            f"O canal '{channel.title()}' não está habilitado para este produto na Central de Produtos (/admin/central-produtos).",
        )
    return True, ""


def toggle_master_product_channel(
    product_id: int,
    channel: str,
    enabled: Optional[bool] = None,
) -> Dict[str, Any]:
    """Liga ou desliga um canal na Central de Produtos E ativa/inativa o produto no canal."""
    ch = (channel or "").strip().lower()
    field = CHANNEL_FIELD_MAP.get(ch)
    if not field:
        raise ValueError(f"Canal inválido: {channel}")

    from services.product_hub_service import ensure_master_products_schema

    ensure_master_products_schema()
    with db() as conn:
        row = conn.execute(
            f"SELECT id, slug, name, {field} FROM master_products WHERE id = %s",
            (product_id,),
        ).fetchone()
        if not row:
            raise ValueError("Produto mestre não encontrado.")
        row_d = dict(row) if isinstance(row, dict) or hasattr(row, "keys") else {
            "id": row[0], "slug": row[1], "name": row[2], field: row[3]
        }
        current_val = True if row_d.get(field) is None else bool(row_d.get(field))
        new_val = (not current_val) if enabled is None else bool(enabled)
        slug = (row_d.get("slug") or "").strip().lower()
        name = row_d.get("name") or ""

        conn.execute(
            f"UPDATE master_products SET {field} = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (new_val, product_id),
        )

        target_status = "active" if new_val else "inactive"
        if ch == "outlet":
            ou_row = conn.execute(
                "SELECT id FROM outlet_items WHERE slug = %s OR name = %s LIMIT 1",
                (slug, name),
            ).fetchone()
            if ou_row:
                ou_id = ou_row["id"] if isinstance(ou_row, dict) or hasattr(ou_row, "keys") else ou_row[0]
                conn.execute(
                    "UPDATE outlet_items SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (target_status, ou_id),
                )
        elif ch == "atacado":
            at_slug = "v8-mini-ultra" if slug == "v8-mini" else slug
            gp_alt = "gp1000" if slug == "gp-1000" else at_slug
            at_row = conn.execute(
                "SELECT id FROM atacado_items WHERE slug = %s OR slug = %s OR slug = %s OR name = %s LIMIT 1",
                (at_slug, gp_alt, slug, name),
            ).fetchone()
            if at_row:
                at_id = at_row["id"] if isinstance(at_row, dict) or hasattr(at_row, "keys") else at_row[0]
                conn.execute(
                    "UPDATE atacado_items SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (target_status, at_id),
                )
        conn.commit()

    if ch == "showroom":
        from services.maj_models_sync_service import set_model_active_status
        from services.showroom_crud_service import load_model_overrides, save_model_overrides

        overrides = load_model_overrides()
        if slug in overrides and isinstance(overrides[slug], dict):
            overrides[slug]["is_active"] = new_val
        else:
            overrides[slug] = {"slug": slug, "modelo": name, "is_active": new_val}
        save_model_overrides(overrides)
        set_model_active_status(slug, new_val)

    return {
        "success": True,
        "product_id": product_id,
        "name": name,
        "channel": ch,
        "enabled": new_val,
    }


def set_master_product_discontinued(product_id: int, discontinued: bool = True) -> Dict[str, Any]:
    """Marca um produto como Descontinuado (desligando os 3 canais) ou Reativa para Em Linha."""
    from services.product_hub_service import ensure_master_products_schema

    ensure_master_products_schema()
    if discontinued:
        for ch in ("showroom", "atacado", "outlet"):
            toggle_master_product_channel(product_id=product_id, channel=ch, enabled=False)
        new_status = "discontinued"
    else:
        new_status = "active"

    with db() as conn:
        row = conn.execute("SELECT id, name FROM master_products WHERE id = %s", (product_id,)).fetchone()
        if not row:
            raise ValueError("Produto mestre não encontrado.")
        name = row["name"] if isinstance(row, dict) or hasattr(row, "keys") else row[1]
        conn.execute(
            "UPDATE master_products SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (new_status, product_id),
        )
        conn.commit()
    return {"success": True, "product_id": product_id, "name": name, "status": new_status}
