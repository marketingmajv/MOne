"""
M-One Demo Import Generator (services/demo_import.py)
Criação de um processo completo de importação de demonstração com dados realistas
de compra da China, pagamentos em câmbio, despesas locais, numerário e itens.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from database import db
from services.import_audit_service import run_import_audit_checks
from services.import_calculator import calculate_import_financials

logger = logging.getLogger(__name__)


def create_demo_import_data(user: dict | None) -> int:
    """Gera uma importação completa de demonstração com todas as 7 abas povoadas."""
    user_id = user.get("id") if user else None
    today = date.today()

    with db() as conn:
        # 1. Cria cabeçalho da importação
        imp = conn.execute(
            """
            INSERT INTO imports (
                reference, importer_company, supplier_name, supplier_contact, currency, incoterm,
                freight_forwarder, customs_broker, pi_amount_usd, ci_amount_usd, bl_no, invoice_no,
                freight_included_in_ci, freight_included_in_pi, insurance_included,
                departure_date_estimated, arrival_date,
                step, status, notes, created_by
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
            """,
            (
                f"IMP-{today.year}-DEMO",
                "MAJ Mobilidade Elétrica LTDA",
                "Zhejiang Leike Electric Vehicle Co., Ltd.",
                "Mr. Chen (Sales Director)",
                "USD",
                "FOB",
                "Asia Shipping Transportes",
                "Despachante Aduaneiro Santos & Cia",
                52000.00,
                52000.00,
                "COSU6321908230",
                "INV-2026-LK889",
                False,
                False,
                True,
                today - timedelta(days=25),
                today + timedelta(days=10),
                "desembaraco",
                "draft",
                "Lote de demonstração: 50 unidades de scooters elétricas modelos Hawk 2000W e Eagle 1500W.",
                user_id,
            ),
        ).fetchone()
        iid = imp["id"]

        # 2. Cadastra Itens de Mercadoria (import_items)
        conn.execute(
            """
            INSERT INTO import_items (import_id, product_name_custom, quantity, unit_price_usd, total_price_usd)
            VALUES 
            (%s, 'Scooter Elétrica MAJ Hawk 2000W 72V 20Ah', 20, 1400.00, 28000.00),
            (%s, 'Scooter Elétrica MAJ Eagle 1500W 60V 20Ah', 30, 800.00, 24000.00)
            """,
            (iid, iid),
        )

        # 3. Cadastra Pagamentos no Exterior / Câmbios (import_payments_china)
        conn.execute(
            """
            INSERT INTO import_payments_china (
                import_id, payment_category, description, amount_usd, exchange_rate, amount_brl, bank_fees_brl, paid_at
            ) VALUES 
            (%s, 'ci_payment', 'Sinal de 30%% para início de produção (Câmbio CAMB-0012)', 15600.00, 5.6200, 87672.00, 450.00, %s),
            (%s, 'ci_payment', 'Saldo final de 70%% pré-embarque (Câmbio CAMB-0035)', 36400.00, 5.6850, 206934.00, 520.00, %s)
            """,
            (iid, today - timedelta(days=40), iid, today - timedelta(days=22)),
        )

        # 4. Cadastra Despesas no Brasil (import_brazil_expenses)
        conn.execute(
            """
            INSERT INTO import_brazil_expenses (
                import_id, category, description, actual_amount, predicted_amount, payment_mode, due_date
            ) VALUES 
            (%s, 'frete_interno', 'Transporte Rodoviário Porto de Santos ao CD Serra/ES', 7500.00, 7500.00, 'direct', %s),
            (%s, 'armazenagem', 'Armazenagem e Capatazia Terminal Retroportuário', 9200.00, 9500.00, 'direct', %s)
            """,
            (iid, today + timedelta(days=12), iid, today + timedelta(days=5)),
        )

        # 5. Cadastra Movimentações de Numerário (import_numerario)
        conn.execute(
            """
            INSERT INTO import_numerario (
                import_id, entry_type, amount, entry_date, description
            ) VALUES 
            (%s, 'advance', 65000.00, %s, 'Transferência adiantamento de numerário para conta do despachante'),
            (%s, 'proven_expense', 38400.00, %s, 'Impostos federais recolhidos na Declaração de Importação (II, IPI, PIS/COFINS)'),
            (%s, 'proven_expense', 18200.00, %s, 'ICMS Importação recolhido pelo despachante'),
            (%s, 'proven_expense', 3800.00, %s, 'Honorários do despachante aduaneiro e SDA')
            """,
            (iid, today - timedelta(days=5), iid, today - timedelta(days=2), iid, today - timedelta(days=2), iid, today - timedelta(days=1)),
        )

        # 6. Recalcula custos e auditoria
        calculate_import_financials(iid, conn)
        run_import_audit_checks(iid, conn)

    return iid
