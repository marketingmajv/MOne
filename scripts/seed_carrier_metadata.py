"""
Script de Carga e Enriquecimento de Dados de Transportadoras (M-One)
Popula os dados reais cadastrais, fiscais, operacionais e tarifários da TJB, Generoso e Vinislog.
"""
import database

TJB_ROWS = [
    ('ES', 'Capital e Metropolitana', 58.15, 67.16, 80.76, 625.0, 10.0, 5.0, 2),
    ('ES', 'Interior I', 95.50, 102.58, 124.12, 950.0, 35.0, 5.0, 3),
    ('ES', 'Interior II', 124.15, 133.35, 161.35, 1230.0, 35.0, 5.0, 4),
    ('SP', 'Capital e Metropolitana', 61.37, 70.89, 85.25, 660.56, 15.0, 5.0, 2),
    ('SP', 'Interior 1', 100.80, 108.19, 131.02, 1243.10, 20.0, 5.0, 4),
    ('SP', 'Interior 2', 105.86, 113.62, 137.60, 1305.54, 35.0, 5.0, 5),
    ('RJ', 'Capital e Metropolitana', 64.61, 74.62, 89.74, 695.33, 10.0, 5.0, 3),
    ('RJ', 'Interior', 106.11, 113.88, 137.92, 1198.00, 35.0, 5.0, 5),
    ('PR', 'Capital e Metropolitana', 67.45, 75.10, 83.71, 761.03, 15.0, 5.0, 3),
    ('PR', 'Interior', 113.33, 119.36, 144.54, 1478.25, 35.0, 5.0, 5),
    ('SC', 'Capital e Metropolitana', 72.29, 79.52, 87.47, 777.45, 10.0, 5.0, 3),
    ('SC', 'Interior 1', 86.75, 95.42, 104.96, 965.00, 10.0, 5.0, 4),
    ('SC', 'Interior 2', 104.08, 114.48, 125.93, 1292.10, 35.0, 5.0, 5),
    ('RS', 'Porto Alegre e Região metropolitana', 74.88, 82.37, 90.61, 865.05, 10.0, 5.0, 3),
    ('RS', 'Caxias do Sul', 86.53, 95.19, 104.70, 982.00, 10.0, 5.0, 4),
    ('RS', 'Interior', 119.51, 131.46, 144.61, 1490.00, 35.0, 5.0, 5)
]

def seed():
    with database.db() as conn:
        # 1. Update TJB carrier
        conn.execute("""
            UPDATE carriers SET 
                trade_name = %s, cnpj = %s, address = %s, city = %s, uf = %s, 
                phone = %s, website = %s, sales_rep_name = %s, payment_terms = %s
            WHERE LOWER(name) LIKE %s
        """, (
            'TJB Transportes', '17.120.090/0001-57', 'Rod. Gov. Mario Covas, 4409 - Galpão 03 Sala 02 - Planeta',
            'Cariacica', 'ES', '(11) 3588 2007', 'https://www.tjbtransportes.com.br',
            'Valeria Penzin', 'Semanal com mais 14 dias', '%tjb%'
        ))

        # 2. Update TJB freight_tables
        cur_tjb_c = conn.execute("SELECT id FROM carriers WHERE LOWER(name) LIKE %s", ('%tjb%',))
        tjb_c_row = cur_tjb_c.fetchone()
        if tjb_c_row:
            tjb_cid = tjb_c_row['id'] if hasattr(tjb_c_row, 'keys') else tjb_c_row[0]
            conn.execute("""
                UPDATE freight_tables SET 
                    origin_city = 'Cariacica', cubing_factor = 300.0, tec_percent = 7.5,
                    tas_fixed = 8.89, pos_fixed = 4.85, min_gris_value = 11.62, expiration_days = 90,
                    notes = %s
                WHERE carrier_id = %s
            """, (
                'Tabela Comercial TJB Cargas Fracionadas. Cubagem 300kg/m³, TEC 7.5%, TAS R$ 8.89/cte, POS R$ 4.85/cte, GRIS mín R$ 11.62, Pedágio R$ 5.00/100kg. Faturamento semanal + 14 dias.',
                tjb_cid
            ))
            
            # Get table_id
            cur_tbl = conn.execute("SELECT id FROM freight_tables WHERE carrier_id = %s", (tjb_cid,))
            tbl_row = cur_tbl.fetchone()
            if tbl_row:
                table_id = tbl_row['id'] if hasattr(tbl_row, 'keys') else tbl_row[0]
                # Delete existing incomplete rates for TJB
                conn.execute("DELETE FROM freight_rates WHERE table_id = %s", (table_id,))
                
                # Insert full 4 brackets
                # 0-30kg, 30.01-50kg, 50.01-100kg, 100.01-999999kg (tonelada/kg)
                inserted = 0
                for uf, city, p30, p50, p100, pton, desp, ped, days in TJB_ROWS:
                    # Faixa 1: 0 a 30kg
                    conn.execute("""
                        INSERT INTO freight_rates (table_id, uf, city, min_weight, max_weight, fixed_price, weight_price_per_kg, ad_valorem_percent, gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes)
                        VALUES (%s, %s, %s, 0.0, 30.0, %s, 0.0, 0.30, 0.20, %s, %s, 0.0, %s)
                    """, (table_id, uf, city, p30, days, ped, f'TJB {uf} {city} (Até 30kg)'))
                    
                    # Faixa 2: 30.01 a 50kg
                    conn.execute("""
                        INSERT INTO freight_rates (table_id, uf, city, min_weight, max_weight, fixed_price, weight_price_per_kg, ad_valorem_percent, gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes)
                        VALUES (%s, %s, %s, 30.01, 50.0, %s, 0.0, 0.30, 0.20, %s, %s, 0.0, %s)
                    """, (table_id, uf, city, p50, days, ped, f'TJB {uf} {city} (30-50kg)'))
                    
                    # Faixa 3: 50.01 a 100kg
                    conn.execute("""
                        INSERT INTO freight_rates (table_id, uf, city, min_weight, max_weight, fixed_price, weight_price_per_kg, ad_valorem_percent, gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes)
                        VALUES (%s, %s, %s, 50.01, 100.0, %s, 0.0, 0.30, 0.20, %s, %s, 0.0, %s)
                    """, (table_id, uf, city, p100, days, ped, f'TJB {uf} {city} (50-100kg)'))
                    
                    # Faixa 4: Carga Pesada / Tonelada (>100kg)
                    kg_rate = round(pton / 1000.0, 4)
                    conn.execute("""
                        INSERT INTO freight_rates (table_id, uf, city, min_weight, max_weight, fixed_price, weight_price_per_kg, ad_valorem_percent, gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes)
                        VALUES (%s, %s, %s, 100.01, 999999.0, %s, %s, 0.30, 0.20, %s, %s, %s, %s)
                    """, (table_id, uf, city, p100, kg_rate, days, ped, desp, f'TJB {uf} {city} (Excedente R${kg_rate}/kg + Despacho R${desp})'))
                    inserted += 4
                print(f'TJB updated with {inserted} rules!')

        # 3. Update Generoso
        conn.execute("""
            UPDATE carriers SET 
                trade_name = 'Generoso Transportes', cnpj = '05.345.922/0001-14',
                address = 'Rodovia BR-101, Km 268 - Carapina', city = 'Serra', uf = 'ES',
                phone = '(27) 3398-2500', website = 'https://www.transportegeneroso.com.br',
                sales_rep_name = 'Comercial Matriz ES', payment_terms = 'Quinzenal 15 dias'
            WHERE LOWER(name) LIKE %s
        """, ('%generoso%',))
        conn.execute("""
            UPDATE freight_tables SET 
                origin_city = 'Vitória', cubing_factor = 300.0, tec_percent = 5.0, expiration_days = 90
            WHERE carrier_id IN (SELECT id FROM carriers WHERE LOWER(name) LIKE %s)
        """, ('%generoso%',))

        # 4. Update Vinislog
        conn.execute("""
            UPDATE carriers SET 
                trade_name = 'Vinislog Cargas & Encomendas', cnpj = '28.194.883/0001-70',
                address = 'Av. Jerônimo Vervloet, 595 - Goiabeiras', city = 'Vitória', uf = 'ES',
                phone = '(27) 3026-8800', website = 'https://www.vinislog.com.br',
                sales_rep_name = 'Atendimento Comercial ES', payment_terms = 'Decendial 10 dias'
            WHERE LOWER(name) LIKE %s
        """, ('%vinislog%',))
        conn.execute("""
            UPDATE freight_tables SET 
                origin_city = 'Vitória', cubing_factor = 300.0, tec_percent = 4.5, expiration_days = 90
            WHERE carrier_id IN (SELECT id FROM carriers WHERE LOWER(name) LIKE %s)
        """, ('%vinislog%',))

        if hasattr(conn, 'commit'):
            conn.commit()
        print('All carriers seeded successfully!')

if __name__ == '__main__':
    seed()
