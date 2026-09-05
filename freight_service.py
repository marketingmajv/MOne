"""
Módulo de Serviço de Frete & Tabelas de Transportadoras — M-One (MAJ Operating System)
Responsável pelo upload, parsing por IA (Gemini), cálculo e geração de orçamentos de frete.
"""

import os
import re
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from gemini_service import get_gemini_api_key

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
    return ""


def ensure_freight_tables(conn):
    """Inicializa as tabelas do banco de dados para o módulo de fretes de forma 100% compatível com SQLite e PostgreSQL."""
    is_pg = hasattr(conn, "conn")  # PGConnWrapper

    carrier_sql = """
        CREATE TABLE IF NOT EXISTS carriers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """ if is_pg else """
        CREATE TABLE IF NOT EXISTS carriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """

    tables_sql = """
        CREATE TABLE IF NOT EXISTS freight_tables (
            id SERIAL PRIMARY KEY,
            carrier_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            file_url TEXT,
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(carrier_id) REFERENCES carriers(id) ON DELETE CASCADE
        );
    """ if is_pg else """
        CREATE TABLE IF NOT EXISTS freight_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            carrier_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            file_url TEXT,
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(carrier_id) REFERENCES carriers(id) ON DELETE CASCADE
        );
    """

    rates_sql = """
        CREATE TABLE IF NOT EXISTS freight_rates (
            id SERIAL PRIMARY KEY,
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
    """ if is_pg else """
        CREATE TABLE IF NOT EXISTS freight_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    for stmt in [carrier_sql, tables_sql, rates_sql]:
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

    # Se não existir nenhuma tabela cadastrada, semear a tabela oficial do Transporte Generoso
    try:
        cur_check = conn.execute("SELECT COUNT(*) AS total FROM freight_tables")
        row_check = cur_check.fetchone()
        tot = row_check.get("total") if row_check else 0
        if tot == 0:
            seed_generoso_rate_table(conn)
    except Exception as e:
        print("[Freight Auto-Seed Check Error]:", e)


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
        cur_c = conn.execute("SELECT id FROM carriers WHERE LOWER(name) LIKE ? OR LOWER(name) LIKE ?", ("%generoso%", "transporte generoso"))
        row_c = cur_c.fetchone()

        if row_c:
            carrier_id = row_c["id"]
        else:
            try:
                cur_ins = conn.execute("INSERT INTO carriers (name) VALUES (?)", ("Transporte Generoso",))
                carrier_id = cur_ins.lastrowid
            except Exception:
                if hasattr(conn, "conn") and hasattr(conn.conn, "rollback"):
                    try:
                        conn.conn.rollback()
                    except Exception:
                        pass
                cur_c = conn.execute("SELECT id FROM carriers WHERE LOWER(name) LIKE ?", ("%generoso%",))
                row_c = cur_c.fetchone()
                carrier_id = row_c["id"] if row_c else 1


        # Criar Tabela de Frete Oficial Generoso
        cur_t = conn.execute(
            "INSERT INTO freight_tables (carrier_id, name, notes) VALUES (?, ?, ?)",
            (carrier_id, "Proposta Comercial Oficial (CIF ES / Nível Brasil)", "Tabela com Seguro 0.30%, GRIS 0.20%, Pedágio e TEC")
        )
        table_id = cur_t.lastrowid

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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for r_item in rates_to_insert:
            conn.execute(sql_ins, r_item)

        if hasattr(conn, "commit"):
            conn.commit()
        print(f"✅ Tabela do Transporte Generoso semeada com sucesso ({len(rates_to_insert)} regras)!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("[Generoso Seeder Error]:", e)





def parse_freight_table_with_gemini(file_path: str, carrier_name: str) -> list:
    """
    Utiliza o Gemini 2.5/2.0 para analisar arquivos PDF/Excel/CSV de transportadoras
    e extrair automaticamente as regras de CEP, peso, valores e prazos.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        print("[Gemini Freight Parser] API key não configurada.")
        return []

    file_path = str(file_path)
    if not os.path.exists(file_path):
        return []

    # Determinar tipo de arquivo e converter se necessário
    mime_type = "application/pdf"
    if file_path.lower().endswith((".xlsx", ".xls", ".csv")):
        mime_type = "text/csv"
        # Tentar ler CSV/Planilha se possível ou converter para texto
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                csv_sample = f.read(50000)
            file_data = csv_sample.encode("utf-8")
        except Exception:
            with open(file_path, "rb") as f:
                file_data = f.read()
    else:
        with open(file_path, "rb") as f:
            file_data = f.read()

    b64_file = base64.b64encode(file_data).decode("utf-8") if 'base64' in globals() else ""

    prompt = f"""
    Você é um especialista em logística e cálculo de frete rodoviário brasileiro.
    Analise a tabela de frete da transportadora '{carrier_name}' enviada em anexo.

    Extraia TODAS as regras de frete presentes no documento em formato JSON estrito:
    Uma lista de objetos com o seguinte esquema:
    [
      {{
        "uf": "UF de destino (ex: ES, RJ, SP, MG, etc. ou null se for por CEP)",
        "city": "Nome da cidade se especificado ou null",
        "cep_start": "CEP inicial de 8 dígitos numéricos (ex: 29000000) ou null",
        "cep_end": "CEP final de 8 dígitos numéricos (ex: 29999999) ou null",
        "min_weight": 0.0,
        "max_weight": 100.0,
        "fixed_price": 150.0,
        "weight_price_per_kg": 1.5,
        "ad_valorem_percent": 0.5,
        "gris_percent": 0.2,
        "min_freight_price": 50.0,
        "delivery_days": 3,
        "notes": "Observações adicionais se houver"
      }}
    ]

    Regras importantes:
    - Retorne APENAS o JSON puro dentro do bloco ```json ```, sem conversas.
    - Se a tabela usar faixas de peso (ex: 0 a 50kg, 51 a 100kg), crie uma regra separada para cada faixa.
    - Se houver taxa de ad-valorem/seguro em %, informe em 'ad_valorem_percent'.
    - Se o CEP for informado com traço (ex: 29000-000), remova o traço e deixe apenas os 8 números.
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_file
                        }
                    }
                ]
            }
        ],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192}
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Extrair bloco JSON
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            json_str = match.group(1) if match else text
            return json.loads(json_str)
    except Exception as e:
        print(f"[Gemini Freight Parser] Erro na análise por IA: {e}")
        return []


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
        d_val = float(it.get("declared_value", 0) or 0)
        w_price = 0.0
        p_name = it.get("name") or ""

        if p_id and db_conn:
            try:
                cur = db_conn.execute("SELECT id, name, wholesale_price FROM products WHERE id = ?", (int(p_id),))
                p = cur.fetchone()
                if p:
                    p_name = p.get("name") or ""
                    w_price = float(p.get("wholesale_price") or 0)
            except Exception as e:
                print("[Freight Service] Erro ao buscar produto:", e)

        # Regra da MAJ: 1/3 do valor de atacado para seguro
        if w_price > 0:
            item_insurance = (w_price / 3.0)
        elif d_val > 0:
            item_insurance = (d_val / 3.0)
        else:
            item_insurance = 0.0

        total_weight += (w * qty)
        total_insurance_value += (item_insurance * qty)

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
        all_rates = []

    dest_int = int(clean_dest)
    carrier_best_rates = {}

    for r in all_rates:
        c_id = r.get("carrier_id")
        c_name = r.get("carrier_name")
        
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

        # Filtro de Peso Total
        min_w = float(r.get("min_weight") or 0)
        max_w = float(r.get("max_weight") or 999999)
        if total_weight > 0 and not (min_w <= total_weight <= max_w):
            continue

        # Cálculo do frete
        fixed_p = float(r.get("fixed_price") or 0)
        w_per_kg = float(r.get("weight_price_per_kg") or 0)
        ad_val_pct = float(r.get("ad_valorem_percent") or 0)
        gris_pct = float(r.get("gris_percent") or 0)
        min_f = float(r.get("min_freight_price") or 0)
        days = int(r.get("delivery_days") or 1)

        # Custo do Peso Total
        weight_cost = total_weight * w_per_kg

        # Custo do Seguro (Ad-valorem + GRIS) sobre 1/3 do Valor de Atacado Total
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
            "notes": r.get("notes") or ""
        }

        if c_id not in carrier_best_rates or total_price < carrier_best_rates[c_id]["total_price"]:
            carrier_best_rates[c_id] = rate_option

    options = list(carrier_best_rates.values())

    if not options:
        return {
            "success": True,
            "cep_dest": format_cep(clean_dest),
            "uf": uf_dest,
            "city": city_dest,
            "product_name": product_summary,
            "total_weight_kg": total_weight,
            "insurance_base_value": round(total_insurance_value, 2),
            "options": [],
            "message": "Nenhuma transportadora atende este CEP / faixa de peso cadastrada."
        }

    # Ordenar por Menor Preço
    options.sort(key=lambda x: (x["total_price"], x["delivery_days"]))

    # Identificar Mais Barato e Mais Rápido
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
        "total_weight_kg": total_weight,
        "insurance_base_value": round(total_insurance_value, 2),
        "options": options
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
