"""
Módulo de Serviço de Frete & Tabelas de Transportadoras — M-One (MAJ Operating System)
Responsável pelo upload, parsing por IA (Gemini), cálculo e geração de orçamentos de frete.
"""

import os
import re
import json
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
    """Consulta estado (UF) e cidade do CEP via API gratuita ViaCEP."""
    c = clean_cep(cep_raw)
    if len(c) != 8:
        return {"found": False}
    url = f"https://viacep.com.br/ws/{c}/json/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "M-One-ERP/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("erro"):
                return {"found": False}
            return {
                "found": True,
                "cep": data.get("cep"),
                "uf": data.get("uf"),
                "city": data.get("localidade"),
                "bairro": data.get("bairro"),
                "street": data.get("logradouro")
            }
    except Exception as e:
        print(f"[ViaCEP] Erro ao consultar CEP {c}: {e}")
        return {"found": False}

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
