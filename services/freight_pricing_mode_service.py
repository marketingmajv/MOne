"""
M-One Freight Pricing Mode Service (services/freight_pricing_mode_service.py)
Gerencia o regime de precificação/seguro na cotação de frete:
- 'atacado': base de seguro = 1/3 do preço de atacado (regra padrão B2B)
- 'varejo':  base de seguro = 100% do preço de varejo (nota fiscal cheia B2C)
"""

from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any

VALID_PRICING_MODES = ("atacado", "varejo")
_pricing_mode_col_ensured = False


def normalize_pricing_mode(mode: str | None) -> str:
    """Normaliza o modo de precificação do frete para 'atacado' ou 'varejo'."""
    raw = str(mode or "").strip().lower()
    return "varejo" if raw == "varejo" else "atacado"


def resolve_authorized_pricing_mode(user: dict[str, Any] | None, raw_mode: str | None) -> tuple[str, bool]:
    """Valida a feature flag RBAC 'freight_retail_mode' e retorna (modo_autorizado, can_retail)."""
    from services.user_permission_service import user_has_permission_check

    can_retail = user_has_permission_check(user, "freight_retail_mode")
    if not can_retail:
        return "atacado", False
    return normalize_pricing_mode(raw_mode), True


def ensure_freight_quotes_pricing_mode(conn) -> None:
    """Garante coluna retrocompatível pricing_mode em freight_quotes (SQLite e PostgreSQL)."""
    global _pricing_mode_col_ensured
    if _pricing_mode_col_ensured or not conn:
        return

    is_pg = hasattr(conn, "pool") or type(conn).__name__ == "PGConnWrapper"
    try:
        if is_pg:
            cur = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'freight_quotes' AND column_name = 'pricing_mode'"
            )
            exists = bool(cur.fetchone())
        else:
            cur = conn.execute("PRAGMA table_info(freight_quotes)")
            exists = any(str(r["name"]).lower() == "pricing_mode" for r in cur.fetchall())

        if not exists:
            conn.execute("ALTER TABLE freight_quotes ADD COLUMN pricing_mode TEXT DEFAULT 'atacado'")
            if hasattr(conn, "commit"):
                conn.commit()
        _pricing_mode_col_ensured = True
    except Exception:
        if hasattr(conn, "rollback"):
            try:
                conn.rollback()
            except Exception:
                pass


def resolve_freight_items_and_insurance(
    db_conn,
    items: list[dict[str, Any]] | None = None,
    pricing_mode: str = "atacado",
    weight_kg: float = 0.0,
    declared_value: float = 0.0,
    product_id: int | None = None,
) -> tuple[list[dict[str, Any]], list[str], float, float, int, float]:
    """
    Processa itens da carga, consulta preços de catálogo e calcula a base de seguro
    conforme o regime ('atacado' = 1/3 do atacado; 'varejo' = 100% do varejo),
    respeitando sobrescrita manual por item quando informada.
    """
    mode = normalize_pricing_mode(pricing_mode)
    total_weight = 0.0
    total_insurance_value = 0.0
    item_descriptions: list[str] = []
    processed_items: list[dict[str, Any]] = []
    total_volumes_count = 0
    total_volume_m3 = 0.0

    raw_items = list(items) if isinstance(items, list) else []
    if not raw_items and (product_id or weight_kg > 0 or declared_value > 0):
        raw_items = [{
            "product_id": product_id,
            "qty": 1,
            "weight_kg": weight_kg,
            "declared_value": declared_value,
        }]

    for it in raw_items:
        p_id = it.get("product_id")
        qty = max(1, int(it.get("qty", 1) or 1))
        w = float(it.get("weight_kg", 0) or 0)
        l_cm = float(it.get("length_cm", 0) or 0)
        w_dim = float(it.get("width_cm", 0) or 0)
        h_cm = float(it.get("height_cm", 0) or 0)
        d_val = float(it.get("declared_value", 0) or 0)
        manual_invoice_raw = it.get("invoice_value")
        invoice_overridden = bool(it.get("invoice_overridden"))

        w_price = 0.0
        r_price = 0.0
        p_name = it.get("name") or ""

        if p_id and db_conn:
            try:
                cur = db_conn.execute(
                    "SELECT id, name, wholesale_price, retail_price FROM products WHERE id = %s",
                    (int(p_id),),
                )
                p = cur.fetchone()
                if p:
                    p_dict = dict(p) if hasattr(p, "keys") else p
                    if isinstance(p_dict, dict):
                        p_name = p_dict.get("name") or p_name
                        w_price = float(p_dict.get("wholesale_price") or 0)
                        r_price = float(p_dict.get("retail_price") or 0)
                    else:
                        p_name = p_dict[1] or p_name
                        w_price = float(p_dict[2] or 0)
                        r_price = float(p_dict[3] or 0)
            except Exception as e:
                print("[Freight Service] Erro ao buscar produto:", e)
                if hasattr(db_conn, "rollback"):
                    try:
                        db_conn.rollback()
                    except Exception:
                        pass

        manual_val = None
        if manual_invoice_raw not in (None, ""):
            try:
                manual_val = max(0.0, float(manual_invoice_raw))
            except (TypeError, ValueError):
                manual_val = None

        if invoice_overridden and manual_val is not None:
            item_insurance = manual_val
        elif mode == "varejo":
            if r_price > 0:
                item_insurance = r_price
            elif d_val > 0:
                item_insurance = d_val
            elif manual_val is not None:
                item_insurance = manual_val
            else:
                item_insurance = 0.0
        else:
            if w_price > 0:
                item_insurance = w_price / 3.0
            elif d_val > 0:
                item_insurance = d_val / 3.0
            elif manual_val is not None:
                item_insurance = manual_val
            else:
                item_insurance = 0.0

        vol_unit_m3 = (l_cm * w_dim * h_cm) / 1000000.0 if (l_cm > 0 and w_dim > 0 and h_cm > 0) else 0.0

        processed_items.append({
            "product_id": p_id,
            "name": p_name or "Produto MAJ",
            "qty": qty,
            "weight_kg": w,
            "length_cm": l_cm,
            "width_cm": w_dim,
            "height_cm": h_cm,
            "volume_m3": round(vol_unit_m3, 4),
            "total_volume_m3": round(vol_unit_m3 * qty, 4),
            "unit_insurance_value": round(item_insurance, 2),
            "pricing_mode": mode,
        })

        total_weight += w * qty
        total_insurance_value += item_insurance * qty
        total_volumes_count += qty
        total_volume_m3 += vol_unit_m3 * qty

        if p_name:
            item_descriptions.append(f"{qty}x {p_name}")
        elif w > 0:
            item_descriptions.append(f"{qty}x Carga ({w}kg)")

    if weight_kg > 0 and total_weight == 0:
        total_weight = weight_kg

    return (
        processed_items,
        item_descriptions,
        total_weight,
        total_insurance_value,
        total_volumes_count,
        total_volume_m3,
    )


def save_freight_quote_record(
    conn,
    *,
    customer_name: str,
    cpf_cnpj: str,
    company_name: str,
    contact_phone: str,
    contact_person: str,
    full_address: str,
    cep_dest: str,
    cep_orig: str,
    items: list[dict[str, Any]],
    res: dict[str, Any],
    pricing_mode: str,
    user_id: int | None,
) -> str:
    """Persiste uma cotação calculada em freight_quotes com o regime de preço utilizado."""
    ensure_freight_quotes_pricing_mode(conn)
    quote_number = f"COT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
    items_json = json.dumps(items, ensure_ascii=False)
    options = res.get("options") or []
    carrier_results_json = json.dumps(options, ensure_ascii=False)
    best_opt = res.get("best_option") or (options[0] if options else {})
    best_price = best_opt.get("final_cost")
    if best_price is None:
        best_price = best_opt.get("total_price", 0)

    conn.execute(
        """INSERT INTO freight_quotes(
            quote_number, customer_name, cpf_cnpj, company_name, contact_phone,
            contact_person, full_address, cep_dest, cep_orig, items_summary,
            carrier_results_json, selected_carrier, selected_price, status, pricing_mode, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'cotado', %s, %s)""",
        (
            quote_number, customer_name, cpf_cnpj, company_name, contact_phone,
            contact_person, full_address, cep_dest, cep_orig, items_json,
            carrier_results_json, best_opt.get("carrier_name", ""),
            float(best_price or 0), normalize_pricing_mode(pricing_mode), user_id,
        ),
    )
    conn.commit()
    return quote_number
