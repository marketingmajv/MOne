import io
import os
import sys
import urllib.request
from pathlib import Path

# Garantir visibilidade dos módulos raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import database
from services.freight_multi_doc_service import parse_sla_spreadsheet

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
        
        table_notes = "Tabela Combinada Oficial Águia Branca (Origem ES). Cubagem 150 kg/m³, TAS R$ 3,02/cte, Ad-Valorem 0.80%, Reajuste diesel 5.9%."
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

        # 3. Baixar e analisar Planilha de Prazos (SLA) do Google Sheets
        sla_url = "https://docs.google.com/spreadsheets/d/1ygBBhFTUbBVawAGgbdmMClTKhurHVeZv/export?format=xlsx"
        print("📥 Baixando relação de prazos e cidades da Águia Branca...")
        temp_sla = BASE_DIR / "temp_sla_seed.xlsx"
        try:
            req = urllib.request.Request(sla_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                with open(temp_sla, "wb") as f_out:
                    f_out.write(resp.read())
            sla_info = parse_sla_spreadsheet(str(temp_sla))
            cities_by_uf = sla_info.get("cities_by_uf", {})
            print(f"📊 {sla_info.get('total_cities', 0)} cidades mapeadas com SLA na planilha.")
        except Exception as e:
            print(f"⚠️ Aviso: Não foi possível baixar SLA dinamicamente ({e}), usando fallback.")
            cities_by_uf = {}
        finally:
            if os.path.exists(temp_sla):
                os.remove(temp_sla)

        # 4. Limpar tarifas antigas e inserir estrutura híbrida (UF + Cidades)
        conn.execute("DELETE FROM freight_rates WHERE table_id = %s", (table_id,))

        weight_brackets = [
            (0.0, 10.0),
            (10.01, 20.0),
            (20.01, 30.0),
            (30.01, 40.0),
            (40.01, 50.0),
        ]

        # Tarifas por estado baseadas no PDF da Águia Branca
        state_tariffs = {
            'PE': (48.38, 55.64, 63.99, 73.59, 84.63, 2920.00, 7.70, 3.19, 5),
            'SE': (48.38, 55.64, 63.99, 73.59, 84.63, 2920.00, 7.70, 3.19, 4),
            'BA': (43.99, 50.58, 58.17, 66.89, 76.94, 1630.00, 7.70, 3.19, 4),
            'ES': (23.32, 25.66, 32.08, 38.49, 46.03, 1170.00, 7.70, 3.19, 2),
            'MG': (39.91, 45.90, 52.77, 60.68, 69.79, 1630.00, 7.70, 3.19, 4),
            'RJ': (39.91, 45.90, 52.77, 60.68, 69.79, 1630.00, 12.83, 3.19, 3),
            'SP': (47.87, 55.07, 63.33, 72.83, 83.74, 2330.00, 12.74, 3.19, 3),
        }

        rows_to_insert = []

        # Coletar regras gerais para cada UF
        for uf, t_data in state_tariffs.items():
            p10, p20, p30, p40, p50, p_ton, desp, ped, default_days = t_data
            prices = [p10, p20, p30, p40, p50]
            taxa_fixa_total = round(desp + 3.02, 2)
            over_per_kg = round(p_ton / 1000.0, 4)

            for idx, (w_min, w_max) in enumerate(weight_brackets):
                rows_to_insert.append((
                    table_id, uf, None, w_min, w_max,
                    round(prices[idx] + taxa_fixa_total, 2),
                    0.0, 0.80, 0.0,
                    default_days, ped, desp,
                    f"Águia Branca {uf} Geral (Até {int(w_max)}kg)"
                ))

            rows_to_insert.append((
                table_id, uf, None, 50.01, 999999.0,
                round(p50 + taxa_fixa_total, 2),
                over_per_kg, 0.80, 0.0,
                default_days, ped, desp,
                f"Águia Branca {uf} Geral (Excedente R${over_per_kg}/kg)"
            ))

            # Coletar regras para cada cidade deste estado que veio no SLA
            city_dict = cities_by_uf.get(uf, {})
            for city_name, c_info in city_dict.items():
                c_days = c_info.get("days", default_days)
                b_txt = "Balcão: SIM" if c_info.get("balcao") else "Balcão: NÃO"
                d_txt = "Domicílio: SIM" if c_info.get("domicilio") else "Domicílio: NÃO"
                mod_notes = f"{b_txt} • {d_txt}"

                for idx, (w_min, w_max) in enumerate(weight_brackets):
                    rows_to_insert.append((
                        table_id, uf, city_name, w_min, w_max,
                        round(prices[idx] + taxa_fixa_total, 2),
                        0.0, 0.80, 0.0,
                        c_days, ped, desp,
                        f"Águia Branca {city_name}/{uf} ({mod_notes})"
                    ))

                rows_to_insert.append((
                    table_id, uf, city_name, 50.01, 999999.0,
                    round(p50 + taxa_fixa_total, 2),
                    over_per_kg, 0.80, 0.0,
                    c_days, ped, desp,
                    f"Águia Branca {city_name}/{uf} Excedente ({mod_notes})"
                ))

        # Inserção em Lotes (Batch Insert)
        chunk_size = 150
        print(f"⚡ Inserindo {len(rows_to_insert)} regras em lotes de {chunk_size}...")
        for i in range(0, len(rows_to_insert), chunk_size):
            chunk = rows_to_insert[i:i + chunk_size]
            placeholders = []
            params = []
            for r in chunk:
                placeholders.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                params.extend(r)
            sql = f"""
                INSERT INTO freight_rates (
                    table_id, uf, city, min_weight, max_weight, 
                    fixed_price, weight_price_per_kg, ad_valorem_percent, 
                    gris_percent, delivery_days, toll_per_100kg, dispatch_fixed, notes
                ) VALUES {', '.join(placeholders)}
            """
            conn.execute(sql, tuple(params))
        inserted = len(rows_to_insert)

        if hasattr(conn, 'commit'):
            conn.commit()

        print(f"✅ Águia Branca semeada com sucesso! Carrier ID: {carrier_id}, Tabela ID: {table_id}, {inserted} regras inseridas.")

if __name__ == '__main__':
    seed()
