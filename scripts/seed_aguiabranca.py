"""
Seed Águia Branca Encomendas (VAB - Viação Águia Branca S/A)
Mapeamento fiel da Proposta Comercial de Frete (Tabela Combinada) - MAJ Confecções
"""
import database

AGUIA_BRANCA_DATA = [
    # (UF, Destino/Região, p10, p20, p30, p40, p50, p_ton, despacho, pedagio, days)
    ('PE', 'Petrolina', 48.38, 55.64, 63.99, 73.59, 84.63, 2920.00, 7.70, 3.19, 5),
    ('SE', 'Aracaju Praça Polo', 48.38, 55.64, 63.99, 73.59, 84.63, 2920.00, 7.70, 3.19, 4),
    ('BA', 'Bahia (Geral)', 43.99, 50.58, 58.17, 66.89, 76.94, 1630.00, 7.70, 3.19, 4),
    ('ES', 'Espírito Santo (Geral)', 23.32, 25.66, 32.08, 38.49, 46.03, 1170.00, 7.70, 3.19, 2),
    ('MG', 'Minas Gerais (Geral)', 39.91, 45.90, 52.77, 60.68, 69.79, 1630.00, 7.70, 3.19, 4),
    ('RJ', 'Rio de Janeiro (Geral)', 39.91, 45.90, 52.77, 60.68, 69.79, 1630.00, 12.83, 3.19, 3),
    ('SP', 'São Paulo (Geral)', 47.87, 55.07, 63.33, 72.83, 83.74, 2330.00, 12.74, 3.19, 3),
]

def seed():
    with database.db() as conn:
        # 1. Obter ou criar Carrier
        cur_c = conn.execute("SELECT id FROM carriers WHERE LOWER(name) LIKE %s OR LOWER(trade_name) LIKE %s", ('%aguia branca%', '%águia branca%'))
        row_c = cur_c.fetchone()
        
        if row_c:
            carrier_id = row_c['id'] if hasattr(row_c, 'keys') else row_c[0]
            conn.execute("""
                UPDATE carriers SET 
                    name = 'Viação Águia Branca S/A',
                    trade_name = 'Águia Branca Encomendas',
                    address = 'Rod. Governador Mário Covas, Km 268',
                    city = 'Cariacica',
                    uf = 'ES',
                    phone = '(27) 4004-1010',
                    website = 'https://www.aguiabrancaencomendas.com.br',
                    sales_rep_name = 'Marcos Antonio Barbosa',
                    payment_terms = '15 dias após faturamento',
                    active = 1
                WHERE id = %s
            """, (carrier_id,))
        else:
            cur_ins = conn.execute("""
                INSERT INTO carriers (name, trade_name, address, city, uf, phone, website, sales_rep_name, payment_terms, active)
                VALUES ('Viação Águia Branca S/A', 'Águia Branca Encomendas', 'Rod. Governador Mário Covas, Km 268', 'Cariacica', 'ES', '(27) 4004-1010', 'https://www.aguiabrancaencomendas.com.br', 'Marcos Antonio Barbosa', '15 dias após faturamento', 1)
                RETURNING id
            """)
            ins_row = cur_ins.fetchone()
            carrier_id = ins_row['id'] if hasattr(ins_row, 'keys') else ins_row[0]

        # 2. Tabela de Frete Oficial
        cur_t = conn.execute("SELECT id FROM freight_tables WHERE carrier_id = %s", (carrier_id,))
        row_t = cur_t.fetchone()
        
        table_notes = "Tabela Combinada Proposta MAJ (Origem ES). Cubagem 150 kg/m³, TAS R$ 3,02/cte, Ad-Valorem 0.80%, Reajuste diesel 5.9%."
        if row_t:
            table_id = row_t['id'] if hasattr(row_t, 'keys') else row_t[0]
            conn.execute("""
                UPDATE freight_tables SET 
                    name = 'Tabela Combinada Águia Branca (Oficial 2026/2027)',
                    origin_city = 'Cariacica/ES',
                    cubing_factor = 150.0,
                    tas_fixed = 3.02,
                    tec_percent = 5.9,
                    notes = %s,
                    active = 1
                WHERE id = %s
            """, (table_notes, table_id))
        else:
            cur_ins_t = conn.execute("""
                INSERT INTO freight_tables (carrier_id, name, origin_city, cubing_factor, tas_fixed, tec_percent, notes, active)
                VALUES (%s, 'Tabela Combinada Águia Branca (Oficial 2026/2027)', 'Cariacica/ES', 150.0, 3.02, 5.9, %s, 1)
                RETURNING id
            """, (carrier_id, table_notes))
            ins_t_row = cur_ins_t.fetchone()
            table_id = ins_t_row['id'] if hasattr(ins_t_row, 'keys') else ins_t_row[0]

        # 3. Limpar tarifas antigas e inserir 6 faixas para cada UF
        conn.execute("DELETE FROM freight_rates WHERE table_id = %s", (table_id,))

        inserted = 0
        weight_brackets = [
            (0.0, 10.0),
            (10.01, 20.0),
            (20.01, 30.0),
            (30.01, 40.0),
            (40.01, 50.0),
        ]

        for uf, city, p10, p20, p30, p40, p50, p_ton, desp, ped, days in AGUIA_BRANCA_DATA:
            prices = [p10, p20, p30, p40, p50]
            # TAS de R$ 3,02 é adicionado na taxa fixa
            taxa_fixa_total = round(desp + 3.02, 2)

            for idx, (w_min, w_max) in enumerate(weight_brackets):
                price_bracket = prices[idx]
                conn.execute("""
                    INSERT INTO freight_rates (
                        table_id, uf, city, min_weight, max_weight, 
                        fixed_price, weight_price_per_kg, ad_valorem_percent, 
                        gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, 0.0, 0.80, 0.0, %s, %s, %s, %s)
                """, (
                    table_id, uf, city, w_min, w_max,
                    round(price_bracket + taxa_fixa_total, 2),
                    days, ped, desp,
                    f"Águia Branca {uf} {city} (Até {int(w_max)}kg)"
                ))
                inserted += 1

            # Faixa Excedente (> 50kg)
            over_per_kg = round(p_ton / 1000.0, 4)
            conn.execute("""
                INSERT INTO freight_rates (
                    table_id, uf, city, min_weight, max_weight, 
                    fixed_price, weight_price_per_kg, ad_valorem_percent, 
                    gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes
                ) VALUES (%s, %s, %s, 50.01, 999999.0, %s, %s, 0.80, 0.0, %s, %s, %s, %s)
            """, (
                table_id, uf, city,
                round(p50 + taxa_fixa_total, 2),
                over_per_kg, days, ped, desp,
                f"Águia Branca {uf} {city} (Excedente R${over_per_kg}/kg)"
            ))
            inserted += 1

        if hasattr(conn, 'commit'):
            conn.commit()

        print(f"✅ Águia Branca semeada com sucesso! Carrier ID: {carrier_id}, Tabela ID: {table_id}, {inserted} faixas inseridas.")

if __name__ == '__main__':
    seed()
