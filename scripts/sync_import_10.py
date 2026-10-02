"""
Script de Sincronização Integral da Importação 1 (DWSE26070036 - ID 10)
Replica a metodologia de alta assertividade aplicada na Importação 2 (DWSE26070035 - ID 11):
1. Câmbio da China e Liquidação da CI + Custos Operacionais
2. Numerário Sanvix (Tributos Federais e Taxas Aduaneiras)
3. Despesas Diretas Brasil (ICMS DUA Eletrônico + Attrius Cargas)
4. Ingestão dos 96 Chassis GP1000 no estoque (stock_units)
5. Recálculo dos Financials e Fator de Custo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
from decimal import Decimal
from database import db
from services.import_calculator import calculate_import_financials

def main():
    print("=== SINCRONIZANDO IMPORTAÇÃO 10 (DWSE26070036) ===")

    with db() as conn:
        # 1. Balde 1 - China
        # 1.1 Parcela da CI (USD 19.980,00 @ 5.1240 = R$ 102.377,52)
        ci_exist = conn.execute(
            "SELECT id FROM import_payments_china WHERE import_id = 10 AND payment_category = 'ci_payment'"
        ).fetchone()
        if not ci_exist:
            conn.execute(
                """
                INSERT INTO import_payments_china (
                    import_id, payment_category, description, amount_usd, amount_brl,
                    exchange_rate, bank_fees_brl, paid_at, document_id, is_verified
                ) VALUES (10, 'ci_payment', 'Liquidação da Parcela da CI (Contrato de Câmbio Garow)', 19980.00, 102377.52, 5.1240, 0.0, '2026-09-09', 9, TRUE)
                """
            )
            print("✓ Inserida Parcela da CI: USD 19.980,00 -> R$ 102.377,52")
        else:
            print("ℹ Parcela da CI já registrada")

        # 1.2 Carreta transporte
        carreta_exist = conn.execute(
            "SELECT id FROM import_payments_china WHERE import_id = %s AND description LIKE %s",
            (10, "%carreta%")
        ).fetchone()
        if not carreta_exist:
            conn.execute(
                """
                INSERT INTO import_payments_china (
                    import_id, payment_category, description, amount_usd, amount_brl,
                    exchange_rate, bank_fees_brl, paid_at, is_verified
                ) VALUES (10, 'other_debit', 'carreta transporte da Silotc até a empresa', 0.0, 1750.00, NULL, 0.0, '2026-09-25', TRUE)
                """
            )
            print("✓ Inserido custo de carreta: R$ 1.750,00")
        else:
            print("ℹ Carreta já registrada")

        # 1.3 Ajudantes descarregamento
        ajudantes_exist = conn.execute(
            "SELECT id FROM import_payments_china WHERE import_id = %s AND description LIKE %s",
            (10, "%ajudantes%")
        ).fetchone()
        if not ajudantes_exist:
            conn.execute(
                """
                INSERT INTO import_payments_china (
                    import_id, payment_category, description, amount_usd, amount_brl,
                    exchange_rate, bank_fees_brl, paid_at, is_verified
                ) VALUES (10, 'other_debit', 'ajudantes para descarregar', 0.0, 12000.00, NULL, 0.0, '2026-09-25', TRUE)
                """
            )
            print("✓ Inserido custo de ajudantes: R$ 12.000,00")
        else:
            print("ℹ Ajudantes já registrados")

        # 2. Balde 2 - Numerário Sanvix (R$ 110.089,52)
        num_exist = conn.execute(
            "SELECT id FROM import_numerario WHERE import_id = 10 AND entry_type = 'advance'"
        ).fetchone()
        if not num_exist:
            conn.execute(
                """
                INSERT INTO import_numerario (
                    import_id, entry_type, amount, entry_date, description, document_id
                ) VALUES (10, 'advance', 110089.52, '2026-09-11', 'Transferência Pix XP de Numerário para Sanvix Logística Ltda (Tributos Federais II/IPI/PIS/COFINS e Taxas Aduaneiras - BL DWSE26070036)', 13)
                """
            )
            print("✓ Inserido Numerário Sanvix: R$ 110.089,52")
        else:
            print("ℹ Numerário Sanvix já registrado")

        # 3. Balde 3 - Despesas Diretas Brasil
        # 3.1 ICMS DUA Eletrônico (R$ 32.442,78)
        icms_exist = conn.execute(
            "SELECT id FROM import_brazil_expenses WHERE import_id = 10 AND category = 'impostos'"
        ).fetchone()
        if not icms_exist:
            conn.execute(
                """
                INSERT INTO import_brazil_expenses (
                    import_id, category, provider, description, predicted_amount, actual_amount,
                    paid_at, payment_mode, icms_in_numerario, document_id
                ) VALUES (10, 'impostos', 'SEFAZ/ES - DUA ELETRÔNICO', 'ICMS Importação recolhido via DUA Eletrônico (DUIMP 26BR00017129576)', 32442.78, 32442.78, '2026-09-11', 'direct', FALSE, 16)
                """
            )
            print("✓ Inserido ICMS DUA Eletrônico: R$ 32.442,78")
        else:
            print("ℹ ICMS já registrado")

        # 3.2 Attrius Agenciamento de Carga (R$ 4.721,88)
        attrius_exist = conn.execute(
            "SELECT id FROM import_brazil_expenses WHERE import_id = 10 AND category = 'taxa_maritima'"
        ).fetchone()
        if not attrius_exist:
            conn.execute(
                """
                INSERT INTO import_brazil_expenses (
                    import_id, category, provider, description, predicted_amount, actual_amount,
                    paid_at, payment_mode, icms_in_numerario, document_id
                ) VALUES (10, 'taxa_maritima', 'ATTRIUS AGENCIAMENTO DE CARGAS INTL LTDA', 'Fatura 05408-0926 Attrius Agenciamento de Carga', 4721.88, 4721.88, '2026-09-10', 'direct', FALSE, 18)
                """
            )
            print("✓ Inserida Taxa Marítima Attrius: R$ 4.721,88")
        else:
            print("ℹ Attrius já registrado")

        # 4. Inserir/Atualizar Item do Processo em import_items (96 unidades GP1000)
        conn.execute("DELETE FROM import_items WHERE import_id = 10")
        conn.execute(
            """
            INSERT INTO import_items (
                import_id, product_id, product_name_custom, quantity, unit_price_usd, total_price_usd, unit_cost_brl
            ) VALUES (10, 20, 'GP1000 - Moto Elétrica 1000W', 96, 345.83, 33200.00, 3851.59)
            """
        )
        print("✓ Registrado item em import_items: 96 unidades GP1000")

        # 5. Ingerir os 96 Chassis em stock_units
        excel_path = "uploads/import_10_chassis_list_VIN_CHASSI_GR01BXMAJ2605-001A_DWSE26070036.xlsx"
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))

        traducao_cores = {
            "珠光特白": "Branco Pérola",
            "曙光金/绒毛白": "Dourado Aurora / Branco",
            "月慕白/绒毛白": "Branco Lunar",
            "亮镜银": "Prata Espelhado",
            "锆石灰": "Cinza Zircônio",
            "复苏绿/绒毛白": "Verde Renascer / Branco",
            "耀夜黑": "Preto Noite",
            "黛蓝灰": "Azul Petróleo / Cinza",
        }

        chassis_inseridos = 0
        for r in rows[2:]:
            chassis_vin = str(r[1] or "").strip()
            motor_no = str(r[5] or "").strip()
            cor_original = str(r[4] or "").strip()
            cor_pt = traducao_cores.get(cor_original, cor_original or "Padrão")

            if chassis_vin:
                conn.execute(
                    """
                    INSERT INTO stock_units (
                        chassis, motor_no, product_id, color, import_id, status, location, notes
                    ) VALUES (%s, %s, 20, %s, 10, 'unreleased', 'Depósito Consolação', %s)
                    ON CONFLICT (chassis) DO UPDATE SET
                        motor_no = EXCLUDED.motor_no,
                        color = EXCLUDED.color,
                        import_id = EXCLUDED.import_id,
                        status = EXCLUDED.status,
                        location = EXCLUDED.location
                    """,
                    (chassis_vin, motor_no, cor_pt, f"Lote DWSE26070036 - {cor_original}"),
                )
                chassis_inseridos += 1

        print(f"✓ Ingeridos {chassis_inseridos} chassis em stock_units com status 'unreleased'!")

        # 6. Recálculo dos Indicadores Financeiros da Importação 10
        financials = calculate_import_financials(10, conn)
        conn.commit()

    print("\n=== RESUMO FINANCEIRO APÓS RECÁLCULO (IMPORTAÇÃO 10) ===")
    print(f"Total Desembolsado: R$ {financials.get('total_disbursed_brl'):,.2f}")
    print(f"Fator de Custo: {financials.get('cost_factor')} R$/US$")
    print(f"Base de Mercadoria FOB: US$ {financials.get('goods_base_usd'):,.2f}")
    print(f"Frete Marítimo: US$ {financials.get('ocean_freight_usd'):,.2f}")
    print(f"Custo Médio por Moto GP1000: R$ {float(financials.get('total_disbursed_brl')) / 96:,.2f}")
    print("========================================================\n")

if __name__ == "__main__":
    main()
