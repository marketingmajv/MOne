"""
Motor de simulação tributária, ICMS-ST, Lucro Real (24%) e espelho de NF-e.
Calcula o comparativo de retenção de ICMS-ST entre Venda M-ONE vs Venda PJ Direto.
"""
from __future__ import annotations

from typing import Any, Dict


def get_default_ipi_by_ncm(ncm: str) -> float:
    """Retorna alíquota IPI estimada de saída por NCM (ex: 35% scooters elétricas, 0% peças)."""
    clean_ncm = str(ncm or "").replace(".", "").strip()
    if clean_ncm.startswith("871160"):  # Scooters / Motos elétricas
        return 35.0
    elif clean_ncm.startswith("8711"):  # Motocicletas
        return 20.0
    elif clean_ncm.startswith("8712"):  # Bicicletas elétricas
        return 10.0
    return 0.0


def simulate_commercial_sale(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a simulação tributária completa de saída da COLVIX para M-ONE ou PJ Direto.
    """
    unit_cost_colvix = float(params.get("unit_cost_colvix", 0) or 0)
    margin_pct = float(params.get("margin_pct", 30.0) or 30.0)
    qty = float(params.get("qty", 1) or 1)
    dest_uf = str(params.get("dest_uf", "SP") or "SP").upper()
    dest_type = str(params.get("dest_type", "M-ONE") or "M-ONE").upper()
    ncm = str(params.get("ncm", "87116000") or "87116000")

    # Alíquotas configuráveis
    ipi_sale_pct = float(params.get("ipi_sale_pct", get_default_ipi_by_ncm(ncm)) or get_default_ipi_by_ncm(ncm))
    icms_own_pct = float(params.get("icms_own_pct", 12.0) or 12.0)
    mva_pct = float(params.get("mva_pct", 34.0) or 34.0)
    icms_st_dest_pct = float(params.get("icms_st_dest_pct", 18.0) or 18.0)
    op_expenses_pct = float(params.get("op_expenses_pct", 5.0) or 5.0)

    # Créditos unitários disponíveis
    pis_cred_unit = float(params.get("pis_credit_unit", 0) or 0)
    cofins_cred_unit = float(params.get("cofins_credit_unit", 0) or 0)
    icms_cred_unit = float(params.get("icms_credit_unit", 0) or 0)
    ipi_cred_unit = float(params.get("ipi_credit_unit", 0) or 0)

    # 1. Formação de Preço de Venda
    unit_sale_price = unit_cost_colvix * (1.0 + (margin_pct / 100.0))
    total_sale_price = unit_sale_price * qty
    total_colvix_cost = unit_cost_colvix * qty

    # 2. Débitos de Saída da COLVIX
    icms_own_val = total_sale_price * (icms_own_pct / 100.0)
    ipi_sale_val = total_sale_price * (ipi_sale_pct / 100.0)
    pis_sale_val = total_sale_price * 0.0165
    cofins_sale_val = total_sale_price * 0.0760
    total_colvix_debits = icms_own_val + ipi_sale_val + pis_sale_val + cofins_sale_val

    # 3. Cálculo do ICMS-ST
    base_st = (total_sale_price + ipi_sale_val) * (1.0 + (mva_pct / 100.0))
    st_bruto = base_st * (icms_st_dest_pct / 100.0)
    icms_st_val = max(0.0, st_bruto - icms_own_val)

    # 4. Comparativo Lado a Lado (M-ONE vs PJ Direto)
    # Cenário 1 (COLVIX -> M-ONE): M-ONE absorve o desembolso do ICMS-ST
    # Cenário 2 (COLVIX -> PJ Direto): Cliente PJ recolhe o ICMS-ST -> Economia imediata de caixa para M-ONE
    is_pj_direct = (dest_type == "PJ_DIRECT")
    st_cashflow_saving = icms_st_val if is_pj_direct else 0.0

    # 5. Apuração Débito x Crédito da COLVIX
    total_credits = (pis_cred_unit + cofins_cred_unit + icms_cred_unit + ipi_cred_unit) * qty
    net_tax_balance = total_colvix_debits - total_credits
    colvix_tax_status = "CRÉDITO RESTANTE" if net_tax_balance <= 0 else "A PAGAR"

    # 6. Apuração de Lucro Real (24% IRPJ/CSLL) e Despesas Operacionais
    gross_profit = total_sale_price - total_colvix_cost - total_colvix_debits
    op_expenses_val = total_sale_price * (op_expenses_pct / 100.0)
    taxable_base_ir_csll = gross_profit - op_expenses_val
    ir_csll_val = 0.24 * max(0.0, taxable_base_ir_csll)
    net_profit = taxable_base_ir_csll - ir_csll_val

    return {
        "unit_cost_colvix": round(unit_cost_colvix, 2),
        "margin_pct": round(margin_pct, 2),
        "unit_sale_price": round(unit_sale_price, 2),
        "total_sale_price": round(total_sale_price, 2),
        "total_colvix_cost": round(total_colvix_cost, 2),
        "qty": qty,
        "dest_uf": dest_uf,
        "dest_type": dest_type,
        "ncm": ncm,
        # Débitos
        "icms_own_pct": icms_own_pct,
        "icms_own_val": round(icms_own_val, 2),
        "ipi_sale_pct": ipi_sale_pct,
        "ipi_sale_val": round(ipi_sale_val, 2),
        "pis_sale_pct": 1.65,
        "pis_sale_val": round(pis_sale_val, 2),
        "cofins_sale_pct": 7.60,
        "cofins_sale_val": round(cofins_sale_val, 2),
        "total_colvix_debits": round(total_colvix_debits, 2),
        # ST & Economia
        "mva_pct": mva_pct,
        "icms_st_dest_pct": icms_st_dest_pct,
        "base_st": round(base_st, 2),
        "icms_st_val": round(icms_st_val, 2),
        "st_cashflow_saving": round(st_cashflow_saving, 2),
        # Apuração Créditos
        "total_credits": round(total_credits, 2),
        "net_tax_balance": round(net_tax_balance, 2),
        "colvix_tax_status": colvix_tax_status,
        # Lucro Real 24%
        "gross_profit": round(gross_profit, 2),
        "op_expenses_pct": op_expenses_pct,
        "op_expenses_val": round(op_expenses_val, 2),
        "taxable_base_ir_csll": round(taxable_base_ir_csll, 2),
        "ir_csll_val": round(ir_csll_val, 2),
        "net_profit": round(net_profit, 2),
    }


def generate_nfe_mirror_data(sim: Dict[str, Any]) -> Dict[str, Any]:
    """Estrutura memória de cálculo pronta para conferência antes da emissão de NF-e."""
    return {
        "header": {
            "uf_emissor": "ES",
            "uf_destino": sim.get("dest_uf", "SP"),
            "destinatario_tipo": sim.get("dest_type", "M-ONE"),
            "ncm": sim.get("ncm", "87116000"),
            "natureza_operacao": "Venda Comercial Intercompany / PJ",
        },
        "totals": {
            "vBC_ICMS": sim.get("total_sale_price", 0),
            "vICMS": sim.get("icms_own_val", 0),
            "vBC_ST": sim.get("base_st", 0),
            "vST": sim.get("icms_st_val", 0),
            "vIPI": sim.get("ipi_sale_val", 0),
            "vPIS": sim.get("pis_sale_val", 0),
            "vCOFINS": sim.get("cofins_sale_val", 0),
            "vProd": sim.get("total_sale_price", 0),
            "vNF": sim.get("total_sale_price", 0) + sim.get("icms_st_val", 0) + sim.get("ipi_sale_val", 0),
        },
        "rates": {
            "pICMS": sim.get("icms_own_pct", 12.0),
            "pIPI": sim.get("ipi_sale_pct", 0.0),
            "pPIS": 1.65,
            "pCOFINS": 7.60,
            "pMVA": sim.get("mva_pct", 34.0),
            "pICMS_ST_Dest": sim.get("icms_st_dest_pct", 18.0),
        },
        "cashflow_highlight": {
            "saving": sim.get("st_cashflow_saving", 0),
            "is_pj_direct": sim.get("dest_type") == "PJ_DIRECT",
        }
    }
