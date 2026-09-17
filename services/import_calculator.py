"""
M-One Import Calculator Engine (services/import_calculator.py)
Motor matemático de cálculo do Fator de Custo (R$/US$), conferência documental da compra na China,
conferência financeira, conciliação de numerário e apuração do custo unitário por produto/chassi.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def to_dec(val: Any) -> Decimal:
    """Converte valor para Decimal de forma segura."""
    if val is None or val == "":
        return Decimal("0.00")
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0.00")


def calculate_import_financials(import_id: int, conn) -> dict[str, Any]:
    """Calcula todos os indicadores financeiros e o Fator de Custo (R$/US$) da importação.

    Regras Fundamentais:
    1. Compra na China:
       - PI = Teto da compra
       - CI = Parcela declarada
       - Diferença Documental = PI - CI - Pagamentos Adicionais
       - Saldo a Pagar = PI - Pagamentos CI - Pagamentos Adicionais
       - NÃO somar PI + CI + comprovantes como despesas separadas!
    2. Numerário Aduaneiro:
       - Saldo a Prestar Contas = Adiantamentos - Despesas Comprovadas - Devoluções
       - NUNCA somar adiantamentos e despesas comprovadas no mesmo total de desembolso!
    3. Fator de Custo (R$/US$):
       - Numerador = Total líquido efetivamente desembolsado em reais no processo
       - Denominador = Total em dólares pago ao fornecedor pelas mercadorias
       - Custo Unitário Gerencial (R$) = Preço USD × Fator de Custo
    """
    # 1. Carregar dados da importação
    imp = conn.execute("SELECT * FROM imports WHERE id = %s", (import_id,)).fetchone()
    if not imp:
        return {}

    pi_amount_usd = to_dec(imp.get("pi_amount_usd"))
    ci_amount_usd = to_dec(imp.get("ci_amount_usd"))

    # 2. Pagamentos no Exterior (China)
    china_rows = conn.execute(
        "SELECT * FROM import_payments_china WHERE import_id = %s ORDER BY paid_at ASC, id ASC",
        (import_id,),
    ).fetchall()

    ci_paid_usd = Decimal("0.00")
    ci_paid_brl = Decimal("0.00")
    additional_paid_usd = Decimal("0.00")
    additional_paid_brl = Decimal("0.00")
    total_bank_fees_brl = Decimal("0.00")
    total_paid_supplier_usd = Decimal("0.00")

    for p in china_rows:
        amt_usd = to_dec(p.get("amount_usd"))
        amt_brl = to_dec(p.get("amount_brl"))
        fees = to_dec(p.get("bank_fees_brl"))
        cat = p.get("payment_category") or "ci_payment"

        total_bank_fees_brl += fees

        if cat == "ci_payment":
            ci_paid_usd += amt_usd
            ci_paid_brl += amt_brl
            total_paid_supplier_usd += amt_usd
        elif cat == "additional_payment":
            additional_paid_usd += amt_usd
            additional_paid_brl += amt_brl
            total_paid_supplier_usd += amt_usd
        else:
            # Outros pagamentos ao fornecedor (frete exterior, etc.)
            total_paid_supplier_usd += amt_usd
            ci_paid_brl += amt_brl

    total_supplier_paid_brl = ci_paid_brl + additional_paid_brl

    # Conferência Documental: PI - CI - Adicionais Comprovados
    documental_diff_usd = pi_amount_usd - ci_amount_usd - additional_paid_usd

    # Saldo da Compra: PI - Pagamentos CI - Pagamentos Adicionais
    purchase_balance_usd = pi_amount_usd - ci_paid_usd - additional_paid_usd
    if purchase_balance_usd < Decimal("0.00"):
        purchase_balance_usd = Decimal("0.00")

    # 3. Despesas no Brasil
    br_rows = conn.execute(
        "SELECT * FROM import_brazil_expenses WHERE import_id = %s",
        (import_id,),
    ).fetchall()

    total_predicted_brl = Decimal("0.00")
    total_direct_expenses_brl = Decimal("0.00")
    total_broker_expenses_brl = Decimal("0.00")
    pending_expenses_brl = Decimal("0.00")

    expenses_by_category = {}

    for e in br_rows:
        actual = to_dec(e.get("actual_amount"))
        predicted = to_dec(e.get("predicted_amount"))
        mode = e.get("payment_mode") or "direct"
        cat = e.get("category") or "outras"

        total_predicted_brl += predicted

        if actual > Decimal("0.00"):
            if mode == "direct":
                total_direct_expenses_brl += actual
            else:
                total_broker_expenses_brl += actual
        else:
            pending_expenses_brl += predicted

        expenses_by_category[cat] = expenses_by_category.get(cat, Decimal("0.00")) + (actual or predicted)

    # 4. Numerário Aduaneiro do Despachante
    num_rows = conn.execute(
        "SELECT * FROM import_numerario WHERE import_id = %s",
        (import_id,),
    ).fetchall()

    advances_brl = Decimal("0.00")
    refunds_brl = Decimal("0.00")
    complements_brl = Decimal("0.00")
    proven_num_expenses_brl = Decimal("0.00")

    for n in num_rows:
        amt = to_dec(n.get("amount"))
        etype = n.get("entry_type")
        if etype in ("advance", "complement"):
            advances_brl += amt
        elif etype == "refund":
            refunds_brl += amt
        elif etype == "actual_expense":
            proven_num_expenses_brl += amt

    # Se houver despesas do numerário registradas na tabela de despesas com mode='via_numerario',
    # considera o maior valor entre a prestação de contas do numerário e as despesas apontadas
    effective_proven_broker_expenses = max(proven_num_expenses_brl, total_broker_expenses_brl)

    # Saldo a prestar contas = Adiantamentos - Despesas Comprovadas - Devoluções
    numerario_balance_brl = advances_brl - effective_proven_broker_expenses - refunds_brl

    # 5. Total Líquido Desembolsado em Reais
    # Regra: Desembolso = Pagamentos Fornecedor + Tarifas + Despesas Diretas + Adiantamentos Líquidos ao Despachante
    net_broker_disbursement = advances_brl - refunds_brl
    if net_broker_disbursement < Decimal("0.00"):
        net_broker_disbursement = Decimal("0.00")

    total_disbursed_brl = (
        total_supplier_paid_brl
        + total_bank_fees_brl
        + total_direct_expenses_brl
        + net_broker_disbursement
    )

    # 6. Base em Dólares das Mercadorias (Denominador do Fator)
    # Dólares pagos ao fornecedor pelas mercadorias (se nada foi pago ainda, usa base da PI/CI)
    goods_base_usd = total_paid_supplier_usd
    if goods_base_usd <= Decimal("0.00"):
        goods_base_usd = pi_amount_usd or ci_amount_usd

    # 7. Cálculo do Fator de Custo (R$/US$)
    cost_factor = None
    if goods_base_usd > Decimal("0.00") and total_disbursed_brl > Decimal("0.00"):
        cost_factor = round(total_disbursed_brl / goods_base_usd, 4)

    # Status do Fator
    is_closed = imp.get("step") == "fechado" or imp.get("status") == "closed"
    factor_status = "final" if is_closed else "provisional"

    # Atualiza o fator e status na tabela imports
    try:
        conn.execute(
            """
            UPDATE imports 
            SET cost_factor = %s, cost_factor_status = %s
            WHERE id = %s
            """,
            (float(cost_factor) if cost_factor is not None else None, factor_status, import_id),
        )
    except Exception as upd_err:
        logger.warning("Erro ao atualizar cost_factor na tabela imports: %s", upd_err)

    # 8. Atualizar custos unitários gerenciais dos produtos (import_items)
    if cost_factor is not None:
        try:
            conn.execute(
                """
                UPDATE import_items
                SET unit_cost_brl = ROUND(unit_price_usd * %s, 2)
                WHERE import_id = %s
                """,
                (float(cost_factor), import_id),
            )
        except Exception as item_upd_err:
            logger.warning("Erro ao atualizar unit_cost_brl em import_items: %s", item_upd_err)

    return {
        "import_id": import_id,
        "pi_amount_usd": float(pi_amount_usd),
        "ci_amount_usd": float(ci_amount_usd),
        "ci_paid_usd": float(ci_paid_usd),
        "ci_paid_brl": float(ci_paid_brl),
        "additional_paid_usd": float(additional_paid_usd),
        "additional_paid_brl": float(additional_paid_brl),
        "total_supplier_paid_usd": float(total_paid_supplier_usd),
        "total_supplier_paid_brl": float(total_supplier_paid_brl),
        "total_bank_fees_brl": float(total_bank_fees_brl),
        "documental_diff_usd": float(documental_diff_usd),
        "purchase_balance_usd": float(purchase_balance_usd),
        "total_direct_expenses_brl": float(total_direct_expenses_brl),
        "total_broker_expenses_brl": float(total_broker_expenses_brl),
        "pending_expenses_brl": float(pending_expenses_brl),
        "advances_brl": float(advances_brl),
        "refunds_brl": float(refunds_brl),
        "proven_num_expenses_brl": float(effective_proven_broker_expenses),
        "numerario_balance_brl": float(numerario_balance_brl),
        "net_broker_disbursement": float(net_broker_disbursement),
        "total_disbursed_brl": float(total_disbursed_brl),
        "goods_base_usd": float(goods_base_usd),
        "cost_factor": float(cost_factor) if cost_factor is not None else None,
        "cost_factor_status": factor_status,
        "expenses_by_category": {k: float(v) for k, v in expenses_by_category.items()},
    }
