"""
M-One Import Settlement Service (services/import_settlement_service.py)
Motor de conciliação de fechamento, prestação de contas do despachante,
cruzamento de pagamentos finais e apuração definitiva do lote aduaneiro.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from database import db
from routes.helpers import audit
from services.import_audit_service import run_import_audit_checks
from services.import_calculator import calculate_import_financials, to_dec

logger = logging.getLogger(__name__)


def fmt_currency(val: float | Decimal | None, currency: str = "BRL") -> str:
    """Formata valor monetário para exibição padronizada."""
    num = float(val or 0.0)
    if currency == "USD":
        return f"US$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_import_baseline_for_settlement(import_id: int, conn) -> dict[str, Any]:
    """Coleta o panorama financeiro e documental de partida para o fechamento da importação."""
    imp = conn.execute("SELECT * FROM imports WHERE id = %s", (import_id,)).fetchone()
    if not imp:
        return {}

    fin = calculate_import_financials(import_id, conn)

    # Despesas cadastradas agrupadas
    br_rows = conn.execute(
        "SELECT category, description, predicted_amount, actual_amount, payment_mode FROM import_brazil_expenses WHERE import_id = %s",
        (import_id,),
    ).fetchall()

    exp_pred = {
        "icms": Decimal("0.00"),
        "frete_carreta": Decimal("0.00"),
        "agente_carga": Decimal("0.00"),
        "ajudantes": Decimal("0.00"),
        "outras": Decimal("0.00"),
    }
    exp_actual = {
        "icms": Decimal("0.00"),
        "frete_carreta": Decimal("0.00"),
        "agente_carga": Decimal("0.00"),
        "ajudantes": Decimal("0.00"),
        "outras": Decimal("0.00"),
    }

    for row in br_rows:
        cat = (row.get("category") or "").lower()
        desc = (row.get("description") or "").lower()
        pred = to_dec(row.get("predicted_amount"))
        act = to_dec(row.get("actual_amount"))

        target_key = "outras"
        if "icms" in desc or cat == "impostos":
            target_key = "icms"
        elif cat == "transporte_rodoviario" or "frete" in desc or "carreta" in desc:
            target_key = "frete_carreta"
        elif cat == "taxa_maritima" or "agente" in desc or "thc" in desc:
            target_key = "agente_carga"
        elif "ajudante" in desc or "descarga" in desc or "desova" in desc:
            target_key = "ajudantes"

        exp_pred[target_key] += pred
        exp_actual[target_key] += act

    return {
        "import_id": import_id,
        "reference": imp.get("reference"),
        "supplier_name": imp.get("supplier_name"),
        "status": imp.get("status"),
        "step": imp.get("step"),
        "currency": imp.get("currency") or "USD",
        "pi_amount_usd": fin.get("pi_amount_usd", 0.0),
        "ci_amount_usd": fin.get("ci_amount_usd", 0.0),
        "total_supplier_paid_usd": fin.get("total_supplier_paid_usd", 0.0),
        "total_supplier_paid_brl": fin.get("total_supplier_paid_brl", 0.0),
        "purchase_balance_usd": fin.get("purchase_balance_usd", 0.0),
        "broker_advances_brl": fin.get("advances_brl", 0.0),
        "broker_proven_brl": fin.get("proven_num_expenses_brl", 0.0),
        "broker_balance_brl": fin.get("numerario_balance_brl", 0.0),
        "total_disbursed_brl": fin.get("total_disbursed_brl", 0.0),
        "cost_factor": fin.get("cost_factor"),
        "cost_factor_status": fin.get("cost_factor_status"),
        "expenses_predicted": {k: float(v) for k, v in exp_pred.items()},
        "expenses_actual": {k: float(v) for k, v in exp_actual.items()},
    }


def cross_reference_settlement_documents(
    import_id: int,
    detected_docs: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """Cruza os documentos detectados na prestação de contas com o baseline financeiro."""
    totals_proven = {
        "cambio_fornecedor_usd": Decimal("0.00"),
        "cambio_fornecedor_brl": Decimal("0.00"),
        "fechamento_despachante": Decimal("0.00"),
        "icms": Decimal("0.00"),
        "frete_carreta": Decimal("0.00"),
        "agente_carga": Decimal("0.00"),
        "ajudantes": Decimal("0.00"),
        "outras": Decimal("0.00"),
    }

    categorized_docs: dict[str, list[dict[str, Any]]] = {
        "cambio_fornecedor": [],
        "fechamento_despachante": [],
        "icms": [],
        "frete_carreta": [],
        "agente_carga": [],
        "ajudantes": [],
        "outras": [],
    }

    for doc in detected_docs:
        doc_type = doc.get("doc_type") or "OTHER"
        amt = to_dec(doc.get("total_amount"))
        curr = (doc.get("currency") or "BRL").upper()

        if doc_type in ("EXCHANGE_CONTRACT", "SUPPLIER_PAYMENT"):
            categorized_docs["cambio_fornecedor"].append(doc)
            if curr == "USD":
                totals_proven["cambio_fornecedor_usd"] += amt
            else:
                totals_proven["cambio_fornecedor_brl"] += amt
        elif doc_type in ("FECHAMENTO_DESPACHANTE", "BROKER_SETTLEMENT", "NUMERARIO"):
            categorized_docs["fechamento_despachante"].append(doc)
            totals_proven["fechamento_despachante"] += amt
        elif doc_type in ("ICMS_GUIDE", "TAX_GUIDE"):
            categorized_docs["icms"].append(doc)
            totals_proven["icms"] += amt
        elif doc_type == "NF_FRETE_CARRETA":
            categorized_docs["frete_carreta"].append(doc)
            totals_proven["frete_carreta"] += amt
        elif doc_type == "AGENTE_CARGA_BR":
            categorized_docs["agente_carga"].append(doc)
            totals_proven["agente_carga"] += amt
        elif doc_type == "AJUDANTES_PAGTO":
            categorized_docs["ajudantes"].append(doc)
            totals_proven["ajudantes"] += amt
        else:
            categorized_docs["outras"].append(doc)
            totals_proven["outras"] += amt

    # Montagem dos itens de conciliação
    items = []

    # 1. Fornecedor / Câmbio
    exp_fob = to_dec(baseline.get("pi_amount_usd") or baseline.get("ci_amount_usd"))
    prior_paid_usd = to_dec(baseline.get("total_supplier_paid_usd"))
    new_usd = totals_proven["cambio_fornecedor_usd"]
    tot_usd = prior_paid_usd + new_usd
    diff_usd = exp_fob - tot_usd
    status_cambio = "reconciled" if abs(diff_usd) < Decimal("5.00") else ("pending" if tot_usd == Decimal("0.00") else "divergent")
    items.append({
        "category_key": "cambio_fornecedor",
        "title": "Câmbio & Pagamentos ao Fornecedor",
        "doc_count": len(categorized_docs["cambio_fornecedor"]),
        "currency": "USD",
        "expected_val": float(exp_fob),
        "expected_label": fmt_currency(exp_fob, "USD"),
        "proven_val": float(tot_usd),
        "proven_label": fmt_currency(tot_usd, "USD"),
        "diff_val": float(diff_usd),
        "diff_label": fmt_currency(diff_usd, "USD"),
        "status": status_cambio,
        "detail": f"{len(categorized_docs['cambio_fornecedor'])} comprovante(s) novo(s). Já registrado: {fmt_currency(prior_paid_usd, 'USD')}.",
    })

    # 2. Fechamento Despachante & Numerário
    advances_brl = to_dec(baseline.get("broker_advances_brl"))
    proven_broker = totals_proven["fechamento_despachante"] or to_dec(baseline.get("broker_proven_brl"))
    num_balance = advances_brl - proven_broker
    if num_balance == Decimal("0.00"):
        status_num = "reconciled"
        num_detail = "Contas 100% zeradas com o despachante."
    elif num_balance > Decimal("0.00"):
        status_num = "refund_due"
        num_detail = f"Despachante deve devolver {fmt_currency(num_balance)} à empresa."
    else:
        status_num = "complement_due"
        num_detail = f"Empresa deve complementar {fmt_currency(abs(num_balance))} ao despachante."

    items.append({
        "category_key": "fechamento_despachante",
        "title": "Prestação de Contas do Despachante (Numerário)",
        "doc_count": len(categorized_docs["fechamento_despachante"]),
        "currency": "BRL",
        "expected_val": float(advances_brl),
        "expected_label": f"Adiantado: {fmt_currency(advances_brl)}",
        "proven_val": float(proven_broker),
        "proven_label": f"Comprovado: {fmt_currency(proven_broker)}",
        "diff_val": float(num_balance),
        "diff_label": f"Saldo: {fmt_currency(num_balance)}",
        "status": status_num,
        "detail": num_detail,
    })

    # 3. Guias de ICMS
    exp_icms = to_dec(baseline.get("expenses_predicted", {}).get("icms"))
    prov_icms = totals_proven["icms"] or to_dec(baseline.get("expenses_actual", {}).get("icms"))
    diff_icms = exp_icms - prov_icms
    status_icms = "reconciled" if (prov_icms > Decimal("0.00") and abs(diff_icms) <= Decimal("5.00")) else ("divergent" if exp_icms > Decimal("0.00") else "ok")
    items.append({
        "category_key": "icms",
        "title": "Guias e Comprovantes de ICMS",
        "doc_count": len(categorized_docs["icms"]),
        "currency": "BRL",
        "expected_val": float(exp_icms),
        "expected_label": fmt_currency(exp_icms),
        "proven_val": float(prov_icms),
        "proven_label": fmt_currency(prov_icms),
        "diff_val": float(diff_icms),
        "diff_label": fmt_currency(diff_icms),
        "status": status_icms,
        "detail": f"{len(categorized_docs['icms'])} guia(s) analisada(s).",
    })

    # 4. Frete Carreta (Transporte Rodoviário)
    exp_frete = to_dec(baseline.get("expenses_predicted", {}).get("frete_carreta"))
    prov_frete = totals_proven["frete_carreta"] or to_dec(baseline.get("expenses_actual", {}).get("frete_carreta"))
    diff_frete = exp_frete - prov_frete
    status_frete = "reconciled" if (prov_frete > Decimal("0.00") and abs(diff_frete) <= Decimal("50.00")) else ("divergent" if exp_frete > Decimal("0.00") and prov_frete > Decimal("0.00") else "pending")
    items.append({
        "category_key": "frete_carreta",
        "title": "Nota Fiscal FRETE, CARRETA",
        "doc_count": len(categorized_docs["frete_carreta"]),
        "currency": "BRL",
        "expected_val": float(exp_frete),
        "expected_label": fmt_currency(exp_frete),
        "proven_val": float(prov_frete),
        "proven_label": fmt_currency(prov_frete),
        "diff_val": float(diff_frete),
        "diff_label": fmt_currency(diff_frete),
        "status": status_frete,
        "detail": f"{len(categorized_docs['frete_carreta'])} documento(s) anexado(s).",
    })

    # 5. Agente de Carga Brasil (Taxas Portuárias / Liberação BL)
    exp_agente = to_dec(baseline.get("expenses_predicted", {}).get("agente_carga"))
    prov_agente = totals_proven["agente_carga"] or to_dec(baseline.get("expenses_actual", {}).get("agente_carga"))
    diff_agente = exp_agente - prov_agente
    status_agente = "reconciled" if (prov_agente > Decimal("0.00") and abs(diff_agente) <= Decimal("50.00")) else ("divergent" if exp_agente > Decimal("0.00") and prov_agente > Decimal("0.00") else "pending")
    items.append({
        "category_key": "agente_carga",
        "title": "AGENTE DE CARGA BRASIL (THC / Liberação BL)",
        "doc_count": len(categorized_docs["agente_carga"]),
        "currency": "BRL",
        "expected_val": float(exp_agente),
        "expected_label": fmt_currency(exp_agente),
        "proven_val": float(prov_agente),
        "proven_label": fmt_currency(prov_agente),
        "diff_val": float(diff_agente),
        "diff_label": fmt_currency(diff_agente),
        "status": status_agente,
        "detail": f"{len(categorized_docs['agente_carga'])} fatura(s) analisada(s).",
    })

    # 6. Ajudantes (Comprovante Pagamento Descarga)
    exp_ajud = to_dec(baseline.get("expenses_predicted", {}).get("ajudantes"))
    prov_ajud = totals_proven["ajudantes"] or to_dec(baseline.get("expenses_actual", {}).get("ajudantes"))
    diff_ajud = exp_ajud - prov_ajud
    status_ajud = "reconciled" if prov_ajud > Decimal("0.00") else "pending"
    items.append({
        "category_key": "ajudantes",
        "title": "AJUDANTES (Comprovante de Pagamento)",
        "doc_count": len(categorized_docs["ajudantes"]),
        "currency": "BRL",
        "expected_val": float(exp_ajud),
        "expected_label": fmt_currency(exp_ajud),
        "proven_val": float(prov_ajud),
        "proven_label": fmt_currency(prov_ajud),
        "diff_val": float(diff_ajud),
        "diff_label": fmt_currency(diff_ajud),
        "status": status_ajud,
        "detail": f"{len(categorized_docs['ajudantes'])} comprovante(s) de desova/descarga.",
    })

    return {
        "baseline": baseline,
        "items": items,
        "detected_docs": detected_docs,
        "totals_proven": {k: float(v) for k, v in totals_proven.items()},
    }


def apply_settlement_reconciliation(
    import_id: int,
    user_id: int | None,
    detected_docs: list[dict[str, Any]],
    close_process: bool = False,
) -> dict[str, Any]:
    """Persiste os documentos conciliados, atualiza financeiro/numerário e opcionalmente fecha o processo."""
    with db() as conn:
        imp = conn.execute("SELECT * FROM imports WHERE id = %s", (import_id,)).fetchone()
        if not imp:
            raise ValueError("Importação não encontrada.")

        saved_docs_count = 0
        expenses_created = 0

        for doc in detected_docs:
            doc_type = doc.get("doc_type") or "OTHER"
            title = doc.get("title") or doc.get("filename") or "Comprovante de Fechamento"
            filename = doc.get("filename") or "arquivo"
            unique_name = doc.get("unique_filename") or filename
            file_hash = doc.get("file_hash")
            file_size = int(doc.get("file_size") or 0)
            doc_amt = to_dec(doc.get("total_amount"))
            doc_num = doc.get("document_number") or ""
            issue_date = doc.get("issue_date")

            # Inserir em import_documents se tiver hash e não for duplicado
            doc_id = None
            if file_hash:
                existing = conn.execute(
                    "SELECT id FROM import_documents WHERE import_id = %s AND file_hash = %s",
                    (import_id, file_hash),
                ).fetchone()
                if existing:
                    doc_id = existing["id"]
                else:
                    ins_doc = conn.execute(
                        """
                        INSERT INTO import_documents (
                            import_id, doc_type, title, filename, file_url, file_size, file_hash,
                            extracted_data, ai_status, uploaded_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processed', %s)
                        RETURNING id
                        """,
                        (
                            import_id,
                            doc_type,
                            title,
                            filename,
                            unique_name,
                            file_size,
                            file_hash,
                            json.dumps(doc),
                            user_id,
                        ),
                    ).fetchone()
                    if ins_doc:
                        doc_id = ins_doc["id"]
                        saved_docs_count += 1

            # Desdobramento financeiro automático baseado no tipo
            if doc_amt > Decimal("0.00"):
                if doc_type in ("FECHAMENTO_DESPACHANTE", "BROKER_SETTLEMENT"):
                    conn.execute(
                        """
                        INSERT INTO import_numerario (
                            import_id, entry_type, amount, entry_date, description, document_id
                        ) VALUES (%s, 'actual_expense', %s, %s, %s, %s)
                        """,
                        (
                            import_id,
                            float(doc_amt),
                            issue_date,
                            f"Fechamento Despachante - {doc_num or title}".strip(),
                            doc_id,
                        ),
                    )
                    expenses_created += 1

                elif doc_type in ("ICMS_GUIDE", "TAX_GUIDE"):
                    conn.execute(
                        """
                        INSERT INTO import_brazil_expenses (
                            import_id, category, provider, description, predicted_amount,
                            actual_amount, paid_at, payment_mode, document_id
                        ) VALUES (%s, 'impostos', 'SEFAZ / Estado', %s, %s, %s, %s, 'direct', %s)
                        """,
                        (
                            import_id,
                            f"Guia/Comprovante de ICMS {doc_num}".strip(),
                            float(doc_amt),
                            float(doc_amt),
                            issue_date,
                            doc_id,
                        ),
                    )
                    expenses_created += 1

                elif doc_type == "NF_FRETE_CARRETA":
                    conn.execute(
                        """
                        INSERT INTO import_brazil_expenses (
                            import_id, category, provider, description, predicted_amount,
                            actual_amount, paid_at, payment_mode, document_id
                        ) VALUES (%s, 'transporte_rodoviario', 'Transportadora Rodoviária', %s, %s, %s, %s, 'direct', %s)
                        """,
                        (
                            import_id,
                            f"NF Frete, Carreta {doc_num}".strip(),
                            float(doc_amt),
                            float(doc_amt),
                            issue_date,
                            doc_id,
                        ),
                    )
                    expenses_created += 1

                elif doc_type == "AGENTE_CARGA_BR":
                    conn.execute(
                        """
                        INSERT INTO import_brazil_expenses (
                            import_id, category, provider, description, predicted_amount,
                            actual_amount, paid_at, payment_mode, document_id
                        ) VALUES (%s, 'taxa_maritima', 'Agente de Carga Brasil', %s, %s, %s, %s, 'direct', %s)
                        """,
                        (
                            import_id,
                            f"Agente de Carga / Liberação BL {doc_num}".strip(),
                            float(doc_amt),
                            float(doc_amt),
                            issue_date,
                            doc_id,
                        ),
                    )
                    expenses_created += 1

                elif doc_type == "AJUDANTES_PAGTO":
                    conn.execute(
                        """
                        INSERT INTO import_brazil_expenses (
                            import_id, category, provider, description, predicted_amount,
                            actual_amount, paid_at, payment_mode, document_id
                        ) VALUES (%s, 'outras', 'Ajudantes Descarga', %s, %s, %s, %s, 'direct', %s)
                        """,
                        (
                            import_id,
                            f"Comprovante Ajudantes {doc_num}".strip(),
                            float(doc_amt),
                            float(doc_amt),
                            issue_date,
                            doc_id,
                        ),
                    )
                    expenses_created += 1

        # Fechar processo se requisitado
        if close_process:
            conn.execute(
                "UPDATE imports SET step = 'fechado', status = 'closed' WHERE id = %s",
                (import_id,),
            )
            audit("import.closed_via_settlement", f"import_id={import_id}")

        # Recalcular financeiro e auditoria
        updated_fin = calculate_import_financials(import_id, conn)
        run_import_audit_checks(import_id, conn)
        audit(
            "import.settlement_reconciled",
            f"import_id={import_id}, docs_saved={saved_docs_count}, expenses_created={expenses_created}",
        )

    return {
        "success": True,
        "import_id": import_id,
        "saved_docs_count": saved_docs_count,
        "expenses_created": expenses_created,
        "is_closed": close_process,
        "financials": updated_fin,
    }
