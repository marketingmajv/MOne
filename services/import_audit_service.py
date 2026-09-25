"""
M-One Import Automated Audit Service (services/import_audit_service.py)
Executa as checagens e auditorias automáticas da IA no processo de importação:
conferência PI vs CI vs Adicionais, Câmbio, Numerário, Duplicidade de Frete e ICMS.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from services.import_calculator import sync_ci_settlement_from_documents, to_dec

logger = logging.getLogger(__name__)


def run_import_audit_checks(import_id: int, conn) -> list[dict[str, Any]]:
    """Executa a bateria de checagens automáticas e atualiza a tabela import_checks."""
    imp = conn.execute("SELECT * FROM imports WHERE id = %s", (import_id,)).fetchone()
    if not imp:
        return []

    # Sincronizar liquidação da CI a partir de documentos comprobatórios (Câmbio / SWIFT)
    sync_ci_settlement_from_documents(import_id, conn)

    # Limpar checagens anteriores para reconstrução
    conn.execute("DELETE FROM import_checks WHERE import_id = %s", (import_id,))

    checks = []

    pi_usd = to_dec(imp.get("pi_amount_usd"))
    ci_usd = to_dec(imp.get("ci_amount_usd"))

    # 1. Checagem: Soma dos Itens vs Valor Declarado na CI ou Chassis Vinculados
    items = conn.execute("SELECT * FROM import_items WHERE import_id = %s", (import_id,)).fetchall()
    total_items_usd = sum(to_dec(it.get("total_price_usd")) for it in items)
    stock_units = conn.execute(
        """
        SELECT su.chassis, p.name as product_name 
        FROM stock_units su 
        LEFT JOIN products p ON p.id = su.product_id 
        WHERE su.import_id = %s
        """,
        (import_id,),
    ).fetchall()

    if items:
        if ci_usd > Decimal("0.00"):
            diff = abs(total_items_usd - ci_usd)
            status = "ok" if diff <= Decimal("1.00") else "divergent"
            checks.append({
                "check_code": "ITEMS_VS_CI",
                "title": "Soma dos Produtos vs Valor da CI",
                "status": status,
                "description": f"Soma dos itens cadastrados (US$ {total_items_usd:,.2f}) comparada com o valor da Commercial Invoice (US$ {ci_usd:,.2f}).",
                "left_value": f"US$ {total_items_usd:,.2f}",
                "right_value": f"US$ {ci_usd:,.2f}",
                "diff_value": float(diff),
            })
    elif stock_units:
        unique_chassis = len({u["chassis"] for u in stock_units if u.get("chassis")})
        models = sorted(list({u["product_name"] for u in stock_units if u.get("product_name")}))
        model_str = ", ".join(models) if models else "Veículos Elétricos"
        checks.append({
            "check_code": "ITEMS_VS_CI",
            "title": "Relação de Produtos e Chassis",
            "status": "ok",
            "description": f"{unique_chassis} unidades de chassis cadastradas e identificadas no lote ({model_str}).",
            "left_value": f"{unique_chassis} chassis",
            "right_value": f"US$ {ci_usd:,.2f}",
            "diff_value": None,
        })
    else:
        checks.append({
            "check_code": "ITEMS_VS_CI",
            "title": "Relação de Produtos e Chassis",
            "status": "pending_info",
            "description": "Nenhum produto cadastrado na lista de mercadorias da importação.",
            "left_value": "0 itens",
            "right_value": f"US$ {ci_usd:,.2f}",
            "diff_value": None,
        })

    # 2. Checagem: Conferência PI vs CI + Pagamentos Adicionais
    china_payments = conn.execute(
        "SELECT * FROM import_payments_china WHERE import_id = %s", (import_id,)
    ).fetchall()
    add_paid_usd = sum(
        to_dec(p.get("amount_usd"))
        for p in china_payments
        if p.get("payment_category") in ("additional_payment", "other_debit")
    )
    ci_paid_usd = sum(
        to_dec(p.get("amount_usd"))
        for p in china_payments
        if p.get("payment_category") == "ci_payment"
    )

    if pi_usd > Decimal("0.00") and ci_usd > Decimal("0.00"):
        expected_diff = pi_usd - ci_usd
        diff_balance = expected_diff - add_paid_usd

        # Se houver lançamentos adicionais / extras que excedem a diferença esperada PI vs CI
        if add_paid_usd > Decimal("0.00") and add_paid_usd > expected_diff:
            status = "extra_payment"
            extra_val = add_paid_usd - max(Decimal("0.00"), expected_diff)
            checks.append({
                "check_code": "PI_VS_CI_ADDITIONAL",
                "title": "Conferência da Compra: PI = (CI + Pagamento Extra)",
                "status": status,
                "description": f"Total PI: US$ {pi_usd:,.2f} | Parcela CI: US$ {ci_usd:,.2f} | Pagamento Extra/Adicional: US$ {add_paid_usd:,.2f}.",
                "left_value": f"US$ {pi_usd:,.2f}",
                "right_value": f"US$ {(ci_usd + add_paid_usd):,.2f}",
                "diff_value": float(extra_val),
            })
        else:
            status = "ok" if abs(diff_balance) <= Decimal("1.00") else "pending_info"
            checks.append({
                "check_code": "PI_VS_CI_ADDITIONAL",
                "title": "Conferência da Compra: PI = (CI + Pagamento Extra)",
                "status": status,
                "description": f"Total PI: US$ {pi_usd:,.2f} | Parcela CI: US$ {ci_usd:,.2f} | Outros Lançamentos: US$ {add_paid_usd:,.2f}.",
                "left_value": f"US$ {pi_usd:,.2f}",
                "right_value": f"US$ {(ci_usd + add_paid_usd):,.2f}",
                "diff_value": float(diff_balance),
            })
    else:
        checks.append({
            "check_code": "PI_VS_CI_ADDITIONAL",
            "title": "Conferência da Compra na China",
            "status": "pending_info",
            "description": "Aguardando preenchimento dos valores da Proforma Invoice (PI) ou Commercial Invoice (CI).",
            "left_value": f"US$ {pi_usd:,.2f}",
            "right_value": f"US$ {ci_usd:,.2f}",
            "diff_value": None,
        })

    # 3. Checagem: Quitação da Parcela da Commercial Invoice
    if ci_usd > Decimal("0.00"):
        ci_diff = ci_usd - ci_paid_usd
        settlement_docs = conn.execute(
            """
            SELECT id, doc_type, title, filename
            FROM import_documents
            WHERE import_id = %s AND doc_type IN ('EXCHANGE_CONTRACT', 'SUPPLIER_PAYMENT')
            """,
            (import_id,),
        ).fetchall()

        has_settlement_docs = len(settlement_docs) > 0
        is_settled = (ci_diff <= Decimal("0.00")) or has_settlement_docs
        status = "ok" if is_settled else "pending_info"

        doc_count = len(settlement_docs)
        if is_settled:
            doc_str = f" ({doc_count} documento(s) de câmbio/SWIFT vinculados)" if doc_count > 0 else ""
            confirmed_val = ci_paid_usd if ci_paid_usd > Decimal("0.00") else ci_usd
            desc = f"Parcela da CI quitada: US$ {confirmed_val:,.2f} comprovados{doc_str}."
        else:
            desc = f"Valor da CI: US$ {ci_usd:,.2f} | Pagamentos vinculados comprovados: US$ {ci_paid_usd:,.2f}."

        checks.append({
            "check_code": "CI_SETTLEMENT",
            "title": "Liquidação da Parcela da CI",
            "status": status,
            "description": desc,
            "left_value": f"US$ {ci_usd:,.2f}",
            "right_value": f"US$ {(ci_paid_usd if ci_paid_usd > Decimal('0.00') else ci_usd):,.2f}",
            "diff_value": 0.0 if is_settled else float(ci_diff),
        })

    # 4. Checagem: Blindagem de Duplicidade de Frete Internacional
    freight_in_ci = bool(imp.get("freight_included_in_ci"))
    freight_expenses = conn.execute(
        "SELECT * FROM import_brazil_expenses WHERE import_id = %s AND category IN ('frete_internacional', 'agente_cargas_br')",
        (import_id,),
    ).fetchall()

    if freight_in_ci and freight_expenses:
        checks.append({
            "check_code": "FREIGHT_DUPLICATION",
            "title": "Alerta de Duplicidade no Frete Internacional",
            "status": "divergent",
            "description": "O frete internacional está marcado como incluído na CI, mas há despesa avulsa de frete lançada nas despesas.",
            "left_value": "Frete Embutido na CI",
            "right_value": f"{len(freight_expenses)} despesa(s) avulsa(s)",
            "diff_value": None,
        })
    else:
        checks.append({
            "check_code": "FREIGHT_DUPLICATION",
            "title": "Consistência de Frete Internacional",
            "status": "ok",
            "description": "Frete marítimo consistente com as condições da CI e despesas externas.",
            "left_value": "Embutido na CI" if freight_in_ci else "Lançamento Avulso",
            "right_value": "OK",
            "diff_value": None,
        })

    # 5. Checagem: Blindagem de Duplicidade do ICMS
    icms_expenses = conn.execute(
        "SELECT * FROM import_brazil_expenses WHERE import_id = %s AND category = 'icms'",
        (import_id,),
    ).fetchall()
    icms_direct = [e for e in icms_expenses if e.get("payment_mode") == "direct"]
    icms_in_num = [e for e in icms_expenses if e.get("icms_in_numerario") or e.get("payment_mode") == "via_numerario"]

    if icms_direct and icms_in_num:
        checks.append({
            "check_code": "ICMS_DUPLICATION",
            "title": "Alerta de Duplicidade no ICMS",
            "status": "divergent",
            "description": "Existe lançamento de ICMS direto e simultaneamente marcado no numerário do despachante.",
            "left_value": "ICMS Direto",
            "right_value": "ICMS no Numerário",
            "diff_value": None,
        })
    else:
        checks.append({
            "check_code": "ICMS_DUPLICATION",
            "title": "Consistência de ICMS",
            "status": "ok",
            "description": "Tratamento de ICMS unificado sem duplicidade de quitação direta x numerário.",
            "left_value": "Sem conflito",
            "right_value": "OK",
            "diff_value": None,
        })

    # 6. Checagem: Conciliação de Numerário Aduaneiro
    num_rows = conn.execute("SELECT * FROM import_numerario WHERE import_id = %s", (import_id,)).fetchall()
    adv_total = sum(to_dec(n.get("amount")) for n in num_rows if n.get("entry_type") in ("advance", "complement"))
    ref_total = sum(to_dec(n.get("amount")) for n in num_rows if n.get("entry_type") == "refund")
    exp_total = sum(to_dec(n.get("amount")) for n in num_rows if n.get("entry_type") == "actual_expense")

    if adv_total > Decimal("0.00"):
        num_balance = adv_total - exp_total - ref_total
        status = "ok" if abs(num_balance) <= Decimal("5.00") else "pending_info"
        checks.append({
            "check_code": "NUMERARIO_SETTLEMENT",
            "title": "Prestação de Contas do Numerário",
            "status": status,
            "description": f"Adiantamentos: R$ {adv_total:,.2f} | Despesas Comprovadas: R$ {exp_total:,.2f} | Devoluções: R$ {ref_total:,.2f}.",
            "left_value": f"R$ {adv_total:,.2f}",
            "right_value": f"R$ {(exp_total + ref_total):,.2f}",
            "diff_value": float(num_balance),
        })

    # Gravar checagens no banco
    for c in checks:
        conn.execute(
            """
            INSERT INTO import_checks (import_id, check_code, status, title, description, left_value, right_value, diff_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                import_id,
                c["check_code"],
                c["status"],
                c["title"],
                c["description"],
                c["left_value"],
                c["right_value"],
                c["diff_value"],
            ),
        )

    return checks
