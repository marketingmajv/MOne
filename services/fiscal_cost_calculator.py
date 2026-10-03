"""
Serviço de cálculo de rateio de custos e tributos na entrada COLVIX (ES).
Aplica os rateios proporcionais por item e formação do Custo Unitário COLVIX.
"""
from __future__ import annotations

from typing import Any, Dict, List


def calculate_apportionment(
    items_raw: List[Dict[str, Any]],
    total_ii_header: float = 0.0,
    total_pis_header: float = 0.0,
    total_cofins_header: float = 0.0,
    general_expenses_header: float = 0.0,
) -> Dict[str, Any]:
    """
    Calcula o rateio proporcional por item baseado na participação do valor do produto no total.
    """
    processed_items = []
    total_products_val = 0.0

    # 1. Primeira passada: calcular total dos produtos
    for item in items_raw:
        qty = float(item.get("quantity", 1) or 1)
        unit_val = float(item.get("unit_product_val", 0) or 0)
        tot_val = float(item.get("total_product_val", 0) or (qty * unit_val))
        total_products_val += tot_val

    total_ii_calc = 0.0
    total_pis_calc = 0.0
    total_cofins_calc = 0.0
    total_other_expenses_calc = 0.0
    total_ipi_calc = 0.0
    total_icms_calc = 0.0
    total_cost_colvix = 0.0

    # 2. Segunda passada: calcular rateio proporcional e Custo COLVIX por item
    for idx, item in enumerate(items_raw):
        qty = float(item.get("quantity", 1) or 1)
        unit_val = float(item.get("unit_product_val", 0) or 0)
        tot_val = float(item.get("total_product_val", 0) or (qty * unit_val))

        part_pct = (tot_val / total_products_val * 100.0) if total_products_val > 0 else 0.0

        # Rateios proporcionais se fornecidos no cabeçalho ou por item
        ii_item = float(item.get("ii_rateado", 0) or (total_ii_header * part_pct / 100.0))
        pis_item = float(item.get("pis_rateado", 0) or (total_pis_header * part_pct / 100.0))
        cofins_item = float(item.get("cofins_rateado", 0) or (total_cofins_header * part_pct / 100.0))
        other_exp_item = float(item.get("other_expenses_rateadas", 0) or (general_expenses_header * part_pct / 100.0))

        ipi_item = float(item.get("ipi_item", 0) or 0)
        icms_item = float(item.get("icms_item", 0) or 0)

        # Custo Total do Item = Produto + II + PIS + COFINS + Despesas + IPI + ICMS
        total_cost_item = tot_val + ii_item + pis_item + cofins_item + other_exp_item + ipi_item + icms_item
        unit_cost_colvix = (total_cost_item / qty) if qty > 0 else total_cost_item

        total_ii_calc += ii_item
        total_pis_calc += pis_item
        total_cofins_calc += cofins_item
        total_other_expenses_calc += other_exp_item
        total_ipi_calc += ipi_item
        total_icms_calc += icms_item
        total_cost_colvix += total_cost_item

        processed_items.append({
            "item_code": str(item.get("item_code", f"ITEM-{idx+1}") or f"ITEM-{idx+1}"),
            "description": str(item.get("description", "Produto Sem Descrição") or "Produto"),
            "ncm": str(item.get("ncm", "87116000") or "87116000"),
            "quantity": qty,
            "unit_product_val": round(unit_val, 2),
            "total_product_val": round(tot_val, 2),
            "participacao_pct": round(part_pct, 4),
            "ii_rateado": round(ii_item, 2),
            "pis_rateado": round(pis_item, 2),
            "cofins_rateado": round(cofins_item, 2),
            "other_expenses_rateadas": round(other_exp_item, 2),
            "ipi_item": round(ipi_item, 2),
            "icms_item": round(icms_item, 2),
            "total_cost_item": round(total_cost_item, 2),
            "unit_cost_colvix": round(unit_cost_colvix, 2),
            "quantity_remaining": qty,
        })

    # Saldos Iniciais de Crédito no Lucro Real
    pis_credit_initial = round(total_products_val * 0.0165, 2)
    cofins_credit_initial = round(total_products_val * 0.0760, 2)
    icms_credit_initial = round(total_icms_calc if total_icms_calc > 0 else (total_products_val * 0.12), 2)
    ipi_credit_initial = round(total_ipi_calc, 2)

    return {
        "items": processed_items,
        "totals": {
            "total_products_val": round(total_products_val, 2),
            "total_ii_val": round(total_ii_calc, 2),
            "total_pis_val": round(total_pis_calc, 2),
            "total_cofins_val": round(total_cofins_calc, 2),
            "total_other_expenses_val": round(total_other_expenses_calc, 2),
            "total_ipi_val": round(total_ipi_calc, 2),
            "total_icms_val": round(total_icms_calc, 2),
            "total_cost_colvix": round(total_cost_colvix, 2),
            "pis_credit_initial": pis_credit_initial,
            "cofins_credit_initial": cofins_credit_initial,
            "icms_credit_initial": icms_credit_initial,
            "ipi_credit_initial": ipi_credit_initial,
        }
    }
