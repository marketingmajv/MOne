"""
Módulo de Serviço de Frete & Tabelas de Transportadoras — M-One (MAJ Operating System)
Responsável pelo upload, parsing por IA (Gemini), cálculo e geração de orçamentos de frete.
"""

import os
import re
import json
import base64
import urllib.request
from pathlib import Path
from services.gemini_client import execute_gemini_payload, get_gemini_api_key

# CEP Padrão da Loja/CD MAJ (Vitória - ES)
DEFAULT_MAJ_CEP = "29045-660"


def clean_cep(cep_raw: str) -> str:
    """Remove caracteres não numéricos do CEP e garante 8 dígitos."""
    if not cep_raw:
        return ""
    digits = re.sub(r"\D", "", str(cep_raw))
    if len(digits) < 8:
        digits = digits.zfill(8)
    return digits[:8]

def format_cep(cep_raw: str) -> str:
    """Formata CEP como XXXXX-XXX."""
    c = clean_cep(cep_raw)
    if len(c) == 8:
        return f"{c[:5]}-{c[5:]}"
    return cep_raw

def lookup_cep_viacep(cep_raw: str) -> dict:
    """Consulta estado (UF) e cidade do CEP via API gratuita ViaCEP com fallback offline instantâneo."""
    c = clean_cep(cep_raw)
    if len(c) != 8:
        return {"found": False}
    uf_fallback = get_uf_from_cep(c)
    url = f"https://viacep.com.br/ws/{c}/json/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "M-One-ERP/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("erro"):
                return {"found": True, "uf": uf_fallback, "city": ""}
            return {
                "found": True,
                "cep": data.get("cep"),
                "uf": data.get("uf") or uf_fallback,
                "city": data.get("localidade"),
                "bairro": data.get("bairro"),
                "street": data.get("logradouro")
            }
    except Exception:
        return {"found": True, "uf": uf_fallback, "city": ""}

def get_uf_from_cep(cep_raw: str) -> str:
    """Retorna a UF de destino instantaneamente a partir dos 8 dígitos do CEP."""
    c = clean_cep(cep_raw)
    if len(c) != 8:
        return ""
    try:
        prefix = int(c[:5])
        if 1000 <= prefix <= 19999: return "SP"
        if 20000 <= prefix <= 28999: return "RJ"
        if 29000 <= prefix <= 29999: return "ES"
        if 30000 <= prefix <= 39999: return "MG"
        if 40000 <= prefix <= 48999: return "BA"
        if 49000 <= prefix <= 49999: return "SE"
        if 50000 <= prefix <= 56999: return "PE"
        if 57000 <= prefix <= 57999: return "AL"
        if 58000 <= prefix <= 58999: return "PB"
        if 59000 <= prefix <= 59999: return "RN"
        if 60000 <= prefix <= 63999: return "CE"
        if 64000 <= prefix <= 64999: return "PI"
        if 65000 <= prefix <= 65999: return "MA"
        if 66000 <= prefix <= 68899: return "PA"
        if 68900 <= prefix <= 68999: return "AP"
        if 69000 <= prefix <= 69299 or 69400 <= prefix <= 69899: return "AM"
        if 69300 <= prefix <= 69399: return "RR"
        if 69900 <= prefix <= 69999: return "AC"
        if 70000 <= prefix <= 72799: return "DF"
        if 72800 <= prefix <= 76799: return "GO"
        if 76800 <= prefix <= 76999 or 78900 <= prefix <= 78999: return "RO"
        if 77000 <= prefix <= 77999: return "TO"
        if 78000 <= prefix <= 78899: return "MT"
        if 79000 <= prefix <= 79999: return "MS"
        if 80000 <= prefix <= 87999: return "PR"
        if 88000 <= prefix <= 89999: return "SC"
        if 90000 <= prefix <= 99999: return "RS"
    except Exception:
        pass
_freight_tables_ensured = False


def execute_db(conn, sql: str, params=()):
    """Executa consultas SQL adaptando sintaxe de parâmetros %s -> ? para SQLite quando necessário."""
    if params:
        is_pg = hasattr(conn, "pool") or type(conn).__name__ == "PGConnWrapper"
        if not is_pg and "%s" in sql:
            sql = sql.replace("%s", "?")
    return conn.execute(sql, params)


def insert_and_get_id(conn, sql: str, params=()):
    """Insere registro e retorna a chave primária de forma compatível com SQLite e PostgreSQL."""
    is_pg = hasattr(conn, "pool") or type(conn).__name__ == "PGConnWrapper"
    if not is_pg and "%s" in sql:
        sql = sql.replace("%s", "?")
    if not is_pg and "RETURNING" in sql.upper():
        sql_clean = re.sub(r"\s+RETURNING\s+\w+", "", sql, flags=re.IGNORECASE)
        cur = conn.execute(sql_clean, params)
        return getattr(cur, "lastrowid", 1)

    cur = conn.execute(sql, params)
    if is_pg:
        row = cur.fetchone() if hasattr(cur, "fetchone") else None
        if row and (hasattr(row, "keys") or isinstance(row, dict)):
            return row["id"]
        elif row and len(row) > 0:
            return row[0]

    return getattr(cur, "lastrowid", 1)


def ensure_freight_tables(conn):
    """Inicializa as tabelas do banco de dados para o módulo de fretes apenas uma vez no processo."""
    global _freight_tables_ensured
    if _freight_tables_ensured:
        return

    is_pg = hasattr(conn, "pool") or type(conn).__name__ == "PGConnWrapper"
    pk_type = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    carrier_sql = f"""
        CREATE TABLE IF NOT EXISTS carriers (
            id {pk_type},
            name TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """

    tables_sql = f"""
        CREATE TABLE IF NOT EXISTS freight_tables (
            id {pk_type},
            carrier_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            file_url TEXT,
            notes TEXT,
            origin_city TEXT DEFAULT 'Cariacica/ES',
            cubing_factor REAL DEFAULT 300.0,
            tec_percent REAL DEFAULT 7.5,
            tas_fixed REAL DEFAULT 0.0,
            pos_percent REAL DEFAULT 0.0,
            gris_min REAL DEFAULT 0.0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(carrier_id) REFERENCES carriers(id) ON DELETE CASCADE
        );
    """

    rates_sql = f"""
        CREATE TABLE IF NOT EXISTS freight_rates (
            id {pk_type},
            table_id INTEGER NOT NULL,
            uf TEXT,
            city TEXT,
            cep_start TEXT,
            cep_end TEXT,
            min_weight REAL NOT NULL DEFAULT 0,
            max_weight REAL NOT NULL DEFAULT 999999,
            fixed_price REAL NOT NULL DEFAULT 0,
            weight_price_per_kg REAL NOT NULL DEFAULT 0,
            ad_valorem_percent REAL NOT NULL DEFAULT 0,
            gris_percent REAL NOT NULL DEFAULT 0,
            min_freight_price REAL NOT NULL DEFAULT 0,
            delivery_days INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            FOREIGN KEY(table_id) REFERENCES freight_tables(id) ON DELETE CASCADE
        );
    """

    quotes_sql = f"""
        CREATE TABLE IF NOT EXISTS freight_quotes (
            id {pk_type},
            quote_number TEXT UNIQUE,
            customer_name TEXT,
            cpf_cnpj TEXT,
            company_name TEXT,
            contact_phone TEXT,
            contact_person TEXT,
            full_address TEXT,
            cep_dest TEXT,
            cep_orig TEXT,
            items_summary TEXT,
            carrier_results_json TEXT,
            selected_carrier TEXT,
            selected_price REAL,
            status TEXT DEFAULT 'cotado',
            created_by INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """

    for stmt in [carrier_sql, tables_sql, rates_sql, quotes_sql]:
        try:
            conn.execute(stmt)
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception as e:
            print("[Freight DB Init Warning]:", e)
            if hasattr(conn, "conn") and hasattr(conn.conn, "rollback"):
                try:
                    conn.conn.rollback()
                except Exception:
                    pass

    # Colunas dinâmicas para bases de dados pré-existentes
    for col, col_def in [
        ("origin_city", "TEXT DEFAULT 'Cariacica/ES'"),
        ("cubing_factor", "REAL DEFAULT 300.0"),
        ("tec_percent", "REAL DEFAULT 7.5"),
        ("tas_fixed", "REAL DEFAULT 0.0"),
        ("pos_percent", "REAL DEFAULT 0.0"),
        ("gris_min", "REAL DEFAULT 0.0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE freight_tables ADD COLUMN {col} {col_def}")
            if hasattr(conn, "commit"):
                conn.commit()
        except Exception:
            pass

    # Se não existirem tabelas ou se Vinislog/Generoso estiverem ausentes, semear automaticamente
    try:
        cur_check = conn.execute("SELECT COUNT(*) AS total FROM freight_tables")
        row_check = cur_check.fetchone()
        tot = (row_check["total"] if hasattr(row_check, "keys") or isinstance(row_check, dict) else row_check[0]) if row_check else 0
        if tot == 0:
            seed_generoso_rate_table(conn)
            seed_vinislog_rate_table(conn)
        else:
            # Verificar se a Vinislog está semeada
            cur_v_check = execute_db(conn, "SELECT c.id FROM carriers c JOIN freight_tables t ON t.carrier_id = c.id WHERE LOWER(c.name) LIKE %s", ("%vinislog%",))
            if not cur_v_check.fetchone():
                seed_vinislog_rate_table(conn)
            # Verificar se Generoso está semeada
            cur_g_check = execute_db(conn, "SELECT c.id FROM carriers c JOIN freight_tables t ON t.carrier_id = c.id WHERE LOWER(c.name) LIKE %s", ("%generoso%",))
            if not cur_g_check.fetchone():
                seed_generoso_rate_table(conn)
    except Exception as e:
        print("[Freight Auto-Seed Check Error]:", e)
    _freight_tables_ensured = True


GENEROSO_DATA = [
    # (uf, city_type, w0_10, w11_20, w21_30, w31_50, w51_70, w71_100, w101_150, w151_200, over200_per_kg, days)
    ("RJ", "Capital", 54.73, 62.60, 66.60, 77.63, 94.09, 111.45, 150.12, 184.86, 0.925, 3),
    ("RJ", "Interior I", 59.51, 67.11, 71.46, 83.21, 101.43, 120.01, 159.48, 199.08, 0.996, 4),
    ("RJ", "Interior II", 59.51, 67.11, 71.46, 83.21, 101.43, 120.01, 159.48, 199.08, 0.996, 5),
    ("ES", "Capital", 38.12, 39.94, 41.94, 49.05, 58.86, 69.47, 99.44, 132.57, 0.664, 1),
    ("ES", "Interior I", 38.12, 39.94, 41.94, 49.05, 58.86, 69.47, 99.44, 132.57, 0.664, 2),
    ("ES", "Interior II", 75.04, 85.75, 90.06, 105.31, 127.74, 154.54, 207.62, 246.52, 1.233, 3),
    ("SP", "Capital", 101.39, 130.16, 144.68, 174.40, 207.08, 224.55, 336.71, 448.86, 2.241, 2),
    ("SP", "Interior I", 68.45, 87.86, 97.65, 117.72, 139.78, 151.58, 227.28, 302.98, 1.518, 3),
    ("SP", "Interior II", 42.24, 63.82, 74.71, 97.01, 121.51, 134.62, 218.73, 302.85, 1.600, 4),
    ("MG", "Capital", 42.24, 63.82, 74.71, 97.01, 121.51, 134.62, 218.73, 302.85, 1.600, 2),
    ("MG", "Interior I", 59.06, 80.28, 92.65, 117.58, 145.12, 160.09, 256.62, 353.15, 1.836, 3),
    ("MG", "Interior II", 71.98, 98.68, 110.35, 136.79, 167.59, 183.65, 291.61, 399.59, 2.062, 4),
    ("PR", "Capital", 42.24, 63.82, 74.71, 97.01, 121.51, 134.62, 218.73, 302.85, 1.600, 3),
    ("PR", "Interior I", 59.06, 80.28, 92.65, 117.58, 145.12, 160.09, 256.62, 353.15, 1.836, 4),
    ("PR", "Interior II", 71.98, 98.68, 110.35, 136.79, 167.59, 183.65, 291.61, 399.59, 2.062, 5),
    ("SC", "Capital", 42.24, 63.82, 74.71, 97.01, 121.51, 134.62, 218.73, 302.85, 1.600, 3),
    ("SC", "Interior I", 59.06, 80.28, 92.65, 117.58, 145.12, 160.09, 256.62, 353.15, 1.836, 4),
    ("SC", "Interior II", 71.98, 98.68, 110.35, 136.79, 167.59, 183.65, 291.61, 399.59, 2.062, 5),
    ("RS", "Capital", 68.85, 97.98, 112.69, 142.78, 175.87, 193.55, 307.11, 420.67, 2.163, 4),
    ("RS", "Interior I", 91.56, 120.20, 136.92, 170.58, 207.74, 227.95, 358.27, 488.59, 2.478, 5),
    ("RS", "Interior II", 109.00, 145.05, 160.79, 196.48, 238.08, 259.75, 405.52, 551.27, 2.783, 6),
    ("DF", "Capital", 68.85, 97.98, 112.69, 142.78, 175.87, 193.55, 307.11, 420.67, 2.163, 3),
    ("GO", "Capital", 68.85, 97.98, 112.69, 142.78, 175.87, 193.55, 307.11, 420.67, 2.163, 3),
    ("GO", "Interior I", 91.56, 120.20, 136.92, 170.58, 207.74, 227.95, 358.27, 488.59, 2.478, 4),
    ("GO", "Interior II", 109.00, 145.05, 160.79, 196.48, 238.08, 259.75, 405.52, 551.27, 2.783, 5),
    ("MS", "Capital", 108.37, 132.98, 143.73, 168.08, 196.47, 211.27, 269.71, 336.68, 1.684, 4),
    ("MS", "Interior I", 133.67, 148.12, 160.34, 187.73, 217.43, 231.95, 290.42, 386.95, 1.933, 5),
    ("MS", "Interior II", 148.12, 164.92, 178.44, 208.97, 242.63, 259.24, 295.66, 386.95, 1.933, 6),
    ("MT", "Capital", 160.23, 178.49, 178.49, 226.47, 263.07, 281.13, 321.12, 361.09, 1.755, 5),
    ("MT", "Interior I", 178.77, 196.68, 213.56, 250.87, 290.74, 310.13, 353.99, 397.85, 1.933, 6),
    ("MT", "Interior II", 223.73, 224.09, 257.54, 303.52, 358.14, 392.53, 448.39, 504.26, 2.467, 7),
    ("RO", "Capital", 210.18, 230.80, 250.46, 293.94, 340.53, 363.29, 415.40, 467.51, 2.289, 6),
    ("RO", "Interior I", 313.75, 324.57, 396.86, 425.12, 501.82, 550.26, 629.81, 709.34, 3.486, 7),
    ("AC", "Capital", 313.75, 324.57, 396.86, 425.12, 501.82, 550.26, 629.81, 709.34, 3.486, 7),
    ("AC", "Interior", 349.94, 361.76, 442.14, 473.54, 558.91, 612.88, 701.74, 790.61, 3.901, 8),
]


def seed_generoso_rate_table(conn):
    """Semeia automaticamente a tabela oficial do Transporte Generoso no banco de dados."""
    try:
        cur_c = execute_db(conn, "SELECT id FROM carriers WHERE LOWER(name) LIKE %s OR LOWER(name) LIKE %s", ("%generoso%", "transporte generoso"))
        row_c = cur_c.fetchone()

        if row_c:
            carrier_id = row_c["id"] if (hasattr(row_c, "keys") or isinstance(row_c, dict)) else row_c[0]
        else:
            try:
                carrier_id = insert_and_get_id(conn, "INSERT INTO carriers (name) VALUES (%s) RETURNING id", ("Transporte Generoso",))
                if hasattr(conn, "commit"):
                    conn.commit()
            except Exception:
                cur_c = execute_db(conn, "SELECT id FROM carriers WHERE LOWER(name) LIKE %s", ("%generoso%",))
                row_c = cur_c.fetchone()
                if row_c:
                    carrier_id = row_c["id"] if (hasattr(row_c, "keys") or isinstance(row_c, dict)) else row_c[0]
                else:
                    return

        # Criar Tabela de Frete Oficial Generoso
        table_id = insert_and_get_id(
            conn,
            "INSERT INTO freight_tables (carrier_id, name, notes, cubing_factor) VALUES (%s, %s, %s, %s) RETURNING id",
            (carrier_id, "Proposta Comercial Oficial (CIF ES / Nível Brasil)", "Tabela com Seguro 0.30%, GRIS 0.20%, Pedágio e TEC", 300.0)
        )
        if hasattr(conn, "commit"):
            conn.commit()

        weight_brackets = [
            (0.0, 10.0),
            (10.01, 20.0),
            (20.01, 30.0),
            (30.01, 50.0),
            (51.01, 70.0),
            (70.01, 100.0),
            (100.01, 150.0),
            (150.01, 200.0),
        ]

        rates_to_insert = []
        for row in GENEROSO_DATA:
            uf = row[0]
            city_type = row[1]
            prices = row[2:10]
            over200_per_kg = row[10]
            days = row[11]

            # Faixas de peso fixo até 200kg
            for idx, (w_min, w_max) in enumerate(weight_brackets):
                p_fixed = prices[idx]
                rates_to_insert.append((
                    table_id, uf, city_type, w_min, w_max,
                    p_fixed, 0.0, 0.30, 0.20, days, f"Generoso {uf} {city_type}"
                ))

            # Faixa acima de 200kg (preço base da faixa 151-200 + valor por kg excedente)
            p_base_200 = prices[7]
            rates_to_insert.append((
                table_id, uf, city_type, 200.01, 999999.0,
                p_base_200, over200_per_kg, 0.30, 0.20, days, f"Generoso {uf} {city_type} Excedente"
            ))

        sql_ins = """
            INSERT INTO freight_rates (
                table_id, uf, city, min_weight, max_weight, 
                fixed_price, weight_price_per_kg, ad_valorem_percent, 
                gris_percent, delivery_days, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        for r_item in rates_to_insert:
            execute_db(conn, sql_ins, r_item)

        if hasattr(conn, "commit"):
            conn.commit()
        print(f"✅ Tabela do Transporte Generoso semeada com sucesso ({len(rates_to_insert)} regras)!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("[Generoso Seeder Error]:", e)


VINISLOG_DATA = [
    # (uf, city_type, p20, p30, p50, p70, p100, over100_per_kg, ad_val_pct, gris_pct, taxa_fixa, pedagio, days)
    ("ES", "Capital", 21.08, 29.89, 34.09, 45.09, 50.03, 0.52, 0.20, 0.15, 16.0, 0.0, 2),
    ("ES", "Interior I", 43.64, 50.81, 60.23, 70.26, 104.61, 1.10, 0.20, 0.15, 20.0, 5.10, 3),
    ("ES", "Interior II", 43.64, 50.81, 60.23, 70.26, 104.61, 1.10, 0.20, 0.15, 20.0, 5.10, 3),
    ("RJ", "Capital", 41.78, 45.64, 55.63, 65.33, 100.23, 0.90, 0.20, 0.15, 20.0, 5.10, 4),
    ("RJ", "Interior I", 51.63, 59.33, 65.33, 77.91, 115.10, 1.05, 0.25, 0.20, 20.0, 5.10, 5),
    ("RJ", "Interior II", 51.63, 59.33, 65.33, 77.91, 115.10, 1.05, 0.25, 0.20, 20.0, 5.10, 5),
    ("SP", "Capital", 29.11, 32.55, 44.10, 55.22, 61.42, 0.70, 0.20, 0.15, 15.0, 4.10, 2),
    ("SP", "Interior I", 43.64, 50.81, 60.23, 70.26, 104.61, 1.05, 0.20, 0.15, 20.0, 4.10, 4),
    ("SP", "Interior II", 51.63, 59.33, 65.33, 77.91, 115.10, 1.15, 0.25, 0.20, 20.0, 5.10, 5),
]


def seed_vinislog_rate_table(conn):
    """Semeia automaticamente a tabela oficial da Vinislog Transportes no banco de dados."""
    try:
        cur_c = execute_db(conn, "SELECT id FROM carriers WHERE LOWER(name) LIKE %s", ("%vinislog%",))
        row_c = cur_c.fetchone()

        if row_c:
            carrier_id = row_c["id"] if (hasattr(row_c, "keys") or isinstance(row_c, dict)) else row_c[0]
        else:
            try:
                carrier_id = insert_and_get_id(conn, "INSERT INTO carriers (name) VALUES (%s) RETURNING id", ("Vinislog Transportes",))
                if hasattr(conn, "commit"):
                    conn.commit()
            except Exception:
                cur_c = execute_db(conn, "SELECT id FROM carriers WHERE LOWER(name) LIKE %s", ("%vinislog%",))
                row_c = cur_c.fetchone()
                if row_c:
                    carrier_id = row_c["id"] if (hasattr(row_c, "keys") or isinstance(row_c, dict)) else row_c[0]
                else:
                    return

        # Verificar se já existe a tabela da Vinislog
        cur_t_check = execute_db(conn, "SELECT id FROM freight_tables WHERE carrier_id = %s", (carrier_id,))
        if cur_t_check.fetchone():
            return

        # Criar Tabela de Frete Oficial Vinislog
        table_id = insert_and_get_id(
            conn,
            "INSERT INTO freight_tables (carrier_id, name, notes, cubing_factor) VALUES (%s, %s, %s, %s) RETURNING id",
            (carrier_id, "Tabela MAJ Vinislog (Origem VIX - ES, RJ, SP)", "Tabela de Frete Fracionado oficial Vinislog com Ad-valorem, GRIS e Taxa", 300.0)
        )
        if hasattr(conn, "commit"):
            conn.commit()

        weight_brackets = [
            (0.0, 20.0),
            (20.01, 30.0),
            (30.01, 50.0),
            (50.01, 70.0),
            (70.01, 100.0)
        ]

        rates_to_insert = []
        for row in VINISLOG_DATA:
            uf = row[0]
            city_type = row[1]
            p_bracket_prices = [row[2], row[3], row[4], row[5], row[6]]
            over100_per_kg = row[7]
            ad_val_pct = row[8]
            gris_pct = row[9]
            taxa_fixa = row[10]
            pedagio = row[11]
            days = row[12]

            # Faixas de peso fixo até 100kg
            for idx, (w_min, w_max) in enumerate(weight_brackets):
                p_fixed = p_bracket_prices[idx] + taxa_fixa
                rates_to_insert.append((
                    table_id, uf, city_type, w_min, w_max,
                    p_fixed, 0.0, ad_val_pct, gris_pct, days, f"Vinislog {uf} {city_type}"
                ))

            # Faixa acima de 100kg (preço base dos 100kg + valor por kg excedente)
            p100_fixed = p_bracket_prices[4] + taxa_fixa - (100.0 * over100_per_kg)
            rates_to_insert.append((
                table_id, uf, city_type, 100.01, 999999.0,
                p100_fixed, over100_per_kg, ad_val_pct, gris_pct, days, f"Vinislog {uf} {city_type} Excedente"
            ))

        sql_ins = """
            INSERT INTO freight_rates (
                table_id, uf, city, min_weight, max_weight, 
                fixed_price, weight_price_per_kg, ad_valorem_percent, 
                gris_percent, delivery_days, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        for r_item in rates_to_insert:
            execute_db(conn, sql_ins, r_item)

        if hasattr(conn, "commit"):
            conn.commit()
        print(f"✅ Tabela da Vinislog Transportes semeada com sucesso ({len(rates_to_insert)} regras)!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("[Vinislog Seeder Error]:", e)


def extract_text_from_spreadsheet(file_path: str) -> str:
    """Extrai todas as linhas e abas de arquivos Excel (.xlsx, .xls) ou CSV de forma legível."""
    p = Path(file_path)
    ext = p.suffix.lower()
    
    if ext in [".xlsx", ".xlsm", ".xltx"]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            lines = []
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                lines.append(f"=== ABA: {sheet_name} ===")
                row_count = 0
                for row in sheet.iter_rows(values_only=True):
                    if not any(v is not None and str(v).strip() != "" for v in row):
                        continue
                    cells = [str(v).strip() if v is not None else "" for v in row]
                    lines.append(" | ".join(cells))
                    row_count += 1
                    if row_count >= 800:
                        lines.append("... [linhas adicionais truncadas para brevidade]")
                        break
            return "\n".join(lines)
        except Exception as e:
            print(f"[Spreadsheet Parser] Erro no openpyxl: {e}")

    # Fallback CSV ou texto
    for enc in ["utf-8", "latin1", "cp1252"]:
        try:
            with open(file_path, "r", encoding=enc, errors="ignore") as f:
                content = f.read(60000)
                if content and any(delim in content[:500] for delim in [";", ",", "\t", "|"]):
                    return content
        except Exception:
            pass
    return ""


def parse_freight_table_with_gemini(file_path: str, carrier_name: str) -> dict:
    """
    Utiliza o Gemini 2.5/2.0 para analisar arquivos PDF/Excel/CSV de transportadoras,
    auditar pendências e extrair automaticamente as regras de CEP, peso, valores e prazos.
    Retorna dict com {'is_valid': bool, 'issues': list[str], 'rates': list[dict]}.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        print("[Gemini Freight Parser] API key não configurada.")
        return {"is_valid": False, "issues": ["API Key do Gemini não está configurada no servidor."], "rates": []}

    file_path = str(file_path)
    if not os.path.exists(file_path):
        return {"is_valid": False, "issues": ["Arquivo da tabela não encontrado no servidor."], "rates": []}

    p = Path(file_path)
    ext = p.suffix.lower()

    # Se for planilha Excel ou CSV, extraímos em texto legível
    sheet_text = ""
    if ext in [".xlsx", ".xls", ".csv", ".tsv"]:
        sheet_text = extract_text_from_spreadsheet(file_path)

    prompt = f"""
    Você é um auditor especialista em logística e tabelas de frete rodoviário brasileiro.
    Analise a tabela de frete da transportadora '{carrier_name}' enviada.

    MISSÃO CRÍTICA:
    1. Auditar a completude dos dados da tabela. Para que uma tabela de frete seja operacional no sistema M-One, ela PRECISA conter:
       - Estados (UF), Cidades ou Faixas de CEP de destino atendidos.
       - Faixas de peso (ex: 0-20kg, 20-50kg, etc.) ou tarifas por kg excedente.
       - Preços fixos ou taxas básicas por faixa de peso.
       - Prazos de entrega estimados em dias úteis (delivery_days).
       - Taxa de seguro / Ad-valorem / GRIS em % ou taxa de despacho.
    2. Se faltarem informações fundamentais para calcular o frete, liste claramente as pendências em 'issues' (para que o usuário possa solicitar diretamente à transportadora).
    3. Extrair todas as regras operacionais válidas em 'rates'.

    Retorne ESTRITAMENTE um JSON no seguinte formato:
    ```json
    {{
      "is_valid": true,
      "issues": [
        "Descreva aqui eventuais pendências ou informações faltantes na planilha (ex: 'Faltam prazos de entrega em dias úteis para o Nordeste', 'Ausência de valor por kg para carga acima de 100kg', etc.)"
      ],
      "rates": [
        {{
          "uf": "UF de 2 letras (ex: ES, RJ, SP, BA, PE) ou null",
          "city": "Nome da cidade ou tipo (Capital/Interior) ou null",
          "cep_start": "CEP de 8 dígitos numéricos (ex: 29000000) ou null",
          "cep_end": "CEP de 8 dígitos numéricos (ex: 29999999) ou null",
          "min_weight": 0.0,
          "max_weight": 100.0,
          "fixed_price": 150.0,
          "weight_price_per_kg": 1.5,
          "ad_valorem_percent": 0.3,
          "gris_percent": 0.2,
          "min_freight_price": 40.0,
          "delivery_days": 3,
          "notes": "Observações se houver"
        }}
      ]
    }}
    ```

    Regras obrigatórias:
    - Retorne APENAS o bloco ```json ```, sem introduções ou conclusões.
    - Se a tabela tiver dados operacionais suficientes, "is_valid" deve ser true.
    - Se a tabela for ilegível, não contiver faixas de peso ou faltarem preços essenciais, defina "is_valid": false e liste as pendências em "issues".
    - Remova traços de CEP (ex: 29000-000 -> 29000000).
    """

    parts = []
    if sheet_text:
        parts.append({"text": f"{prompt}\n\nCONTEÚDO DA PLANILHA EXTRAÍDO:\n{sheet_text[:80000]}"})
    else:
        # Envio binário para PDF
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            b64_file = base64.b64encode(raw_bytes).decode("utf-8")
            mime_type = "application/pdf" if ext == ".pdf" else "application/octet-stream"
            parts.append({"text": prompt})
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_file
                }
            })
        except Exception as e:
            return {"is_valid": False, "issues": [f"Erro ao ler arquivo: {e}"], "rates": []}

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}
    }

    try:
        gemini_res = execute_gemini_payload(payload, api_key=api_key, timeout=60)
        if not gemini_res.get("success"):
            err_msg = gemini_res.get("message") or "Falha na comunicação com o serviço de IA."
            return {"is_valid": False, "issues": [err_msg], "rates": []}

        raw_text = gemini_res.get("text", "")
        match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
        json_str = match.group(1) if match else raw_text
        parsed = json.loads(json_str)

        # Normalização de retorno (caso venha lista direta ou dict)
        if isinstance(parsed, list):
            rates = parsed
            issues = []
        elif isinstance(parsed, dict):
            rates = parsed.get("rates", [])
            issues = parsed.get("issues", [])
        else:
            return {"is_valid": False, "issues": ["Formato de resposta inesperado da IA."], "rates": []}

        # Sanitizar prazos de entrega faltantes com fallback inteligente (3 dias Capital, 5 dias Interior)
        for r in rates:
            if not r.get("delivery_days") or int(r.get("delivery_days") or 0) <= 0:
                desc = f"{r.get('city') or ''} {r.get('notes') or ''} {r.get('uf') or ''}".lower()
                if "capital" in desc or "metropolitana" in desc:
                    r["delivery_days"] = 3
                elif "interior" in desc:
                    r["delivery_days"] = 5
                else:
                    r["delivery_days"] = 4

        if rates and len(rates) > 0:
            is_valid = True
        else:
            is_valid = False
            if not issues:
                issues.append("Nenhuma faixa tarifária de frete pôde ser extraída da tabela.")

        return {"is_valid": is_valid, "issues": issues, "rates": rates}
    except Exception as e:
        print(f"[Gemini Freight Parser] Erro na análise por IA: {e}")
        return {"is_valid": False, "issues": [f"Falha ao interpretar resposta da IA: {str(e)}"], "rates": []}


def calculate_freight(db_conn, cep_dest: str, items: list = None, weight_kg: float = 0.0, declared_value: float = 0.0, product_id: int = None, cep_orig: str = None) -> dict:
    """
    Calcula as opções de frete disponíveis em todas as transportadoras ativas.
    Suporta múltiplos itens e quantidades por modelo.
    Regra de Seguro MAJ: O valor considerado para seguro é estritamente 1/3 do valor de atacado.
    """
    clean_dest = clean_cep(cep_dest)
    if len(clean_dest) != 8:
        return {"success": False, "message": "CEP de destino inválido (deve conter 8 dígitos)."}

    clean_orig = clean_cep(cep_orig or DEFAULT_MAJ_CEP)

    # 1. Buscar estado (UF) e Cidade do CEP de destino
    via_cep = lookup_cep_viacep(clean_dest)
    uf_dest = via_cep.get("uf", "").upper()
    city_dest = via_cep.get("city", "")

    # 2. Processar lista de itens
    total_weight = 0.0
    total_insurance_value = 0.0
    item_descriptions = []
    processed_items = []
    total_volumes_count = 0
    total_volume_m3 = 0.0

    # Compatibilidade caso venha 1 unico produto
    if not items or not isinstance(items, list):
        items = []
        if product_id or weight_kg > 0 or declared_value > 0:
            items.append({
                "product_id": product_id,
                "qty": 1,
                "weight_kg": weight_kg,
                "declared_value": declared_value
            })

    for it in items:
        p_id = it.get("product_id")
        qty = int(it.get("qty", 1) or 1)
        w = float(it.get("weight_kg", 0) or 0)
        l = float(it.get("length_cm", 0) or 0)
        w_dim = float(it.get("width_cm", 0) or 0)
        h = float(it.get("height_cm", 0) or 0)
        d_val = float(it.get("declared_value", 0) or 0)
        w_price = 0.0
        p_name = it.get("name") or ""

        if p_id and db_conn:
            try:
                cur = db_conn.execute("SELECT id, name, wholesale_price FROM products WHERE id = %s", (int(p_id),))
                p = cur.fetchone()
                if p:
                    p_dict = dict(p) if hasattr(p, "keys") else p
                    p_name = p_dict["name"] if isinstance(p_dict, dict) else p_dict[1]
                    w_price = float(p_dict["wholesale_price"] if isinstance(p_dict, dict) else (p_dict[2] or 0))
            except Exception as e:
                print("[Freight Service] Erro ao buscar produto:", e)
                if hasattr(db_conn, "rollback"):
                    try:
                        db_conn.rollback()
                    except Exception:
                        pass

        # Regra da MAJ: 1/3 do valor de atacado para seguro
        if w_price > 0:
            item_insurance = (w_price / 3.0)
        elif d_val > 0:
            item_insurance = (d_val / 3.0)
        else:
            item_insurance = 0.0

        vol_unit_m3 = (l * w_dim * h) / 1000000.0 if (l > 0 and w_dim > 0 and h > 0) else 0.0

        processed_items.append({
            "product_id": p_id,
            "name": p_name or "Produto MAJ",
            "qty": qty,
            "weight_kg": w,
            "length_cm": l,
            "width_cm": w_dim,
            "height_cm": h,
            "volume_m3": round(vol_unit_m3, 4),
            "total_volume_m3": round(vol_unit_m3 * qty, 4)
        })

        total_weight += (w * qty)
        total_insurance_value += (item_insurance * qty)
        total_volumes_count += qty
        total_volume_m3 += (vol_unit_m3 * qty)

        if p_name:
            item_descriptions.append(f"{qty}x {p_name}")
        elif w > 0:
            item_descriptions.append(f"{qty}x Carga ({w}kg)")

    product_summary = ", ".join(item_descriptions) if item_descriptions else "Carga Geral"

    if weight_kg > 0 and total_weight == 0:
        total_weight = weight_kg

    # 3. Buscar todas as regras de frete ativas
    if not db_conn:
        return {"success": False, "message": "Sem conexão com o banco de dados."}

    sql = """
        SELECT 
            c.id AS carrier_id,
            c.name AS carrier_name,
            t.id AS table_id,
            t.name AS table_name,
            t.cubing_factor,
            r.uf,
            r.city,
            r.cep_start,
            r.cep_end,
            r.min_weight,
            r.max_weight,
            r.fixed_price,
            r.weight_price_per_kg,
            r.ad_valorem_percent,
            r.gris_percent,
            r.min_freight_price,
            r.delivery_days,
            r.notes
        FROM carriers c
        JOIN freight_tables t ON t.carrier_id = c.id
        JOIN freight_rates r ON r.table_id = t.id
        WHERE c.active = 1 AND t.active = 1
    """
    
    try:
        cur = db_conn.execute(sql)
        all_rates = cur.fetchall()
    except Exception as e:
        print("[Freight Service] Erro ao consultar tarifas:", e)
        if hasattr(db_conn, "rollback"):
            try:
                db_conn.rollback()
            except Exception:
                pass
        all_rates = []

    dest_int = int(clean_dest)
    carrier_best_rates = {}
    active_carriers = {}
    carrier_rates_map = {}

    for r_raw in all_rates:
        r = dict(r_raw) if hasattr(r_raw, "keys") else r_raw
        c_id = r["carrier_id"]
        c_name = r["carrier_name"]
        t_name = r.get("table_name") or ""
        if c_id not in active_carriers:
            active_carriers[c_id] = {"id": c_id, "name": c_name, "table_name": t_name}
            carrier_rates_map[c_id] = []
        carrier_rates_map[c_id].append(r)
        
        # Filtro de CEP
        r_cep_start = clean_cep(r.get("cep_start"))
        r_cep_end = clean_cep(r.get("cep_end"))
        r_uf = str(r.get("uf") or "").upper().strip()

        match_cep = False
        if r_cep_start and r_cep_end:
            try:
                start_int = int(r_cep_start)
                end_int = int(r_cep_end)
                if start_int <= dest_int <= end_int:
                    match_cep = True
            except Exception:
                pass

        match_uf = (r_uf and uf_dest and r_uf == uf_dest)

        if not (match_cep or match_uf or (not r_cep_start and not r_uf)):
            continue

        # Regra do Peso Cubado MAJ: peso_tarifado = max(peso_bruto, volume_m3 * cubing_factor)
        cubing_factor = float(r.get("cubing_factor") or 300.0)
        cubic_weight = total_volume_m3 * cubing_factor
        charged_weight = max(total_weight, cubic_weight)

        # Filtro por Peso Tarifado
        min_w = float(r.get("min_weight") or 0)
        max_w = float(r.get("max_weight") or 999999)
        check_w = charged_weight if charged_weight > 0 else total_weight
        if check_w > 0 and not (min_w <= check_w <= max_w):
            continue

        # Cálculo do frete considerando o peso tarifado
        fixed_p = float(r.get("fixed_price") or 0)
        w_per_kg = float(r.get("weight_price_per_kg") or 0)
        ad_val_pct = float(r.get("ad_valorem_percent") or 0)
        gris_pct = float(r.get("gris_percent") or 0)
        min_f = float(r.get("min_freight_price") or 0)
        days = int(r.get("delivery_days") or 1)

        weight_cost = check_w * w_per_kg
        insurance_cost = total_insurance_value * ((ad_val_pct + gris_pct) / 100.0)

        total_price = fixed_p + weight_cost + insurance_cost
        if total_price < min_f:
            total_price = min_f

        rate_option = {
            "carrier_id": c_id,
            "carrier_name": c_name,
            "table_name": r.get("table_name"),
            "total_price": round(total_price, 2),
            "fixed_price": round(fixed_p, 2),
            "insurance_cost": round(insurance_cost, 2),
            "delivery_days": days,
            "gross_weight_kg": round(total_weight, 2),
            "cubic_weight_kg": round(cubic_weight, 2),
            "charged_weight_kg": round(charged_weight, 2),
            "cubing_factor": cubing_factor,
            "notes": r.get("notes") or ""
        }

        if c_id not in carrier_best_rates or total_price < carrier_best_rates[c_id]["total_price"]:
            carrier_best_rates[c_id] = rate_option

    options = list(carrier_best_rates.values())

    # Diagnóstico detalhado de transportadoras ativas não classificadas nesta rota
    unserved_carriers = []
    served_ids = set(carrier_best_rates.keys())
    for c_id, c_info in active_carriers.items():
        if c_id in served_ids:
            continue
        c_rates = carrier_rates_map.get(c_id, [])
        if not c_rates:
            reason = "Sem faixas tarifárias cadastradas na tabela."
        else:
            dest_matching = []
            for r in c_rates:
                s_c = clean_cep(r.get("cep_start"))
                e_c = clean_cep(r.get("cep_end"))
                u_c = str(r.get("uf") or "").upper().strip()
                m_cep = False
                if s_c and e_c:
                    try:
                        if int(s_c) <= dest_int <= int(e_c):
                            m_cep = True
                    except Exception:
                        pass
                m_uf = (u_c and uf_dest and u_c == uf_dest)
                if m_cep or m_uf or (not s_c and not u_c):
                    dest_matching.append(r)

            if not dest_matching:
                dest_str = f"{city_dest}/{uf_dest}" if (city_dest and uf_dest) else (uf_dest or format_cep(clean_dest))
                reason = f"Não atende esta localidade ({dest_str})."
            else:
                max_w_list = [float(r.get("max_weight") or 0) for r in dest_matching if float(r.get("max_weight") or 0) > 0]
                min_w_list = [float(r.get("min_weight") or 0) for r in dest_matching]
                highest_max = max(max_w_list) if max_w_list else 0
                lowest_min = min(min_w_list) if min_w_list else 0

                check_w = max(total_weight, total_volume_m3 * 300.0)
                w_gross_str = f"{total_weight:.1f}".replace(".", ",")
                w_charged_str = f"{check_w:.1f}".replace(".", ",")
                if highest_max > 0 and check_w > highest_max:
                    max_str = f"{highest_max:.1f}".replace(".", ",")
                    reason = f"Peso tarifado ({w_charged_str} kg [Bruto: {w_gross_str}kg]) excede o limite máximo da tabela (até {max_str} kg)."
                elif check_w < lowest_min:
                    min_str = f"{lowest_min:.1f}".replace(".", ",")
                    reason = f"Peso tarifado ({w_charged_str} kg) abaixo do limite mínimo da tabela ({min_str} kg)."
                else:
                    reason = "Faixa tarifária não contempla os parâmetros da rota."

        unserved_carriers.append({
            "carrier_id": c_id,
            "carrier_name": c_info["name"],
            "table_name": c_info["table_name"],
            "reason": reason
        })

    overall_charged_weight = max(total_weight, total_volume_m3 * 300.0)

    if not options:
        return {
            "success": True,
            "cep_dest": format_cep(clean_dest),
            "uf": uf_dest,
            "city": city_dest,
            "product_name": product_summary,
            "total_weight_kg": round(total_weight, 2),
            "total_volumes_count": total_volumes_count,
            "total_volume_m3": round(total_volume_m3, 3),
            "charged_weight_kg": round(overall_charged_weight, 2),
            "insurance_base_value": round(total_insurance_value, 2),
            "items": processed_items,
            "options": [],
            "unserved_carriers": unserved_carriers,
            "message": "Nenhuma transportadora atende este CEP / faixa de peso cadastrada."
        }

    # Ordenar por Menor Preço
    options.sort(key=lambda x: (x["total_price"], x["delivery_days"]))

    cheapest_price = min(o["total_price"] for o in options)
    fastest_days = min(o["delivery_days"] for o in options)

    for o in options:
        badges = []
        if o["total_price"] == cheapest_price:
            badges.append("Mais Barato")
        if o["delivery_days"] == fastest_days:
            badges.append("Mais Rápido")
        o["badges"] = badges

    return {
        "success": True,
        "cep_dest": format_cep(clean_dest),
        "uf": uf_dest,
        "city": city_dest,
        "product_name": product_summary,
        "total_weight_kg": round(total_weight, 2),
        "total_volumes_count": total_volumes_count,
        "total_volume_m3": round(total_volume_m3, 3),
        "charged_weight_kg": round(overall_charged_weight, 2),
        "insurance_base_value": round(total_insurance_value, 2),
        "items": processed_items,
        "options": options,
        "unserved_carriers": unserved_carriers
    }


def generate_whatsapp_budget(customer_name: str, cep_dest: str, product_name: str, options: list) -> str:
    """Gera texto formatado e elegante para enviar ao cliente no WhatsApp."""
    cust_str = f"para *{customer_name.strip()}*" if customer_name and customer_name.strip() else ""
    prod_str = f"📦 *Produto*: {product_name}\n" if product_name else ""
    
    msg = f"🚚 *Orçamento de Frete - MAJ Mobilidade*\n"
    if cust_str:
        msg += f"👤 Cliente: {customer_name}\n"
    msg += f"📍 *CEP Destino*: {format_cep(cep_dest)}\n"
    if prod_str:
        msg += prod_str
    msg += "\n*Opções de Envio Disponíveis*:\n"

    for i, opt in enumerate(options, 1):
        badges_str = f" 🏆 [{', '.join(opt.get('badges', []))}]" if opt.get("badges") else ""
        msg += f"{i}️⃣ *{opt['carrier_name']}*\n"
        msg += f"   • Valor: *R$ {opt['total_price']:.2f}*\n"
        msg += f"   • Prazo: *{opt['delivery_days']} dia(s) útil(eis)*{badges_str}\n\n"

    msg += "⚡ *Valores sujeitos a alteração no momento da coleta.*\n"
    msg += "Dúvidas? Estamos à disposição!"
    return msg
