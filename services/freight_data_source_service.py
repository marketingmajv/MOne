"""
M-One Freight Data Source Service (services/freight_data_source_service.py)
Gerenciamento da fonte de dados oficial (Google Sheets) de Veículos, Dimensões de Caixas, Pesos e Preços.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

OFFICIAL_SHEETS_URL = "https://docs.google.com/spreadsheets/d/1xtZaD2vxOj1NwvQ3CFBJJcONh_TL5AtVKjftNJPUIAc/edit#gid=494760175"


def get_products_data_source(conn) -> Dict[str, Any]:
    """Retorna os metadados da fonte de catálogo/especificações de produtos."""
    row = conn.execute("SELECT * FROM data_sources WHERE key = 'products_catalog'").fetchone()
    if not row:
        conn.execute(
            """
            INSERT INTO data_sources (key, name, category, description, target_table, sheets_url, last_sync_status, records_count)
            VALUES ('products_catalog', 'Catálogo de Produtos & Tabela de Preços', 'Catálogo & Logística',
                    'Planilha mestre de modelos, SKU, Preço de Atacado, Varejo, Pesos e Dimensões das Caixas (LxAxC).',
                    'products', %s, 'pending', 0)
            """,
            (OFFICIAL_SHEETS_URL,)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM data_sources WHERE key = 'products_catalog'").fetchone()
    
    source = dict(row)
    # Se a URL for um placeholder ou vazia, atualizar para a oficial
    if not source.get("sheets_url") or "ejemplo" in source.get("sheets_url", ""):
        conn.execute("UPDATE data_sources SET sheets_url = %s WHERE key = 'products_catalog'", (OFFICIAL_SHEETS_URL,))
        conn.commit()
        source["sheets_url"] = OFFICIAL_SHEETS_URL

    return source


def get_products_with_specs(conn) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Retorna lista de produtos com cálculos de cubagem e estatísticas gerais."""
    rows = conn.execute(
        """
        SELECT id, name, sku, category, wholesale_price, retail_price, weight_kg, length_cm, width_cm, height_cm, created_at
        FROM products
        ORDER BY name ASC
        """
    ).fetchall()

    products = []
    total_complete = 0

    for r in rows:
        p = dict(r)
        w_kg = float(p.get("weight_kg") or 0)
        l_cm = float(p.get("length_cm") or 0)
        wi_cm = float(p.get("width_cm") or 0)
        h_cm = float(p.get("height_cm") or 0)
        w_price = float(p.get("wholesale_price") or 0)

        vol_m3 = round((l_cm * wi_cm * h_cm) / 1_000_000.0, 4) if (l_cm and wi_cm and h_cm) else 0.0
        cubed_kg = round(vol_m3 * 300.0, 2)
        has_specs = bool(w_kg > 0 and l_cm > 0 and wi_cm > 0 and h_cm > 0)
        if has_specs:
            total_complete += 1

        p.update({
            "weight_kg": w_kg,
            "length_cm": l_cm,
            "width_cm": wi_cm,
            "height_cm": h_cm,
            "volume_m3": vol_m3,
            "cubed_kg": cubed_kg,
            "wholesale_price": w_price,
            "one_third_wholesale": round(w_price / 3.0, 2),
            "has_specs": has_specs,
        })
        products.append(p)

    stats = {
        "total_products": len(products),
        "complete_specs": total_complete,
        "missing_specs": len(products) - total_complete,
    }
    return products, stats


def parse_official_products_csv(csv_text: str) -> List[Dict[str, Any]]:
    """Faz o parse das linhas da planilha oficial com cabeçalho LxAxC e Pesos."""
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    header_idx = -1
    for i, r in enumerate(rows):
        if len(r) > 1 and "Modelo" in str(r[0]):
            header_idx = i
            break

    if header_idx == -1:
        # Fallback se não achou 'Modelo' na primeira coluna
        for i, r in enumerate(rows):
            if any("MODELO" in str(c).upper() for c in r):
                header_idx = i
                break

    if header_idx == -1:
        raise ValueError("Cabeçalho 'Modelo' não foi encontrado na planilha.")

    items = []
    for r in rows[header_idx + 1:]:
        if not r or not any(r):
            continue
        name = str(r[0]).strip()
        if not name or "MODELO" in name.upper():
            continue

        atacado_str = str(r[1] if len(r) > 1 else "").replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            atacado = float(atacado_str)
        except Exception:
            atacado = None

        varejo_str = str(r[4] if len(r) > 4 else "").replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            varejo = float(varejo_str)
        except Exception:
            varejo = None

        peso_raw = str(r[8] if len(r) > 8 else "").strip().lower().replace("kg", "").replace(",", ".").strip()
        try:
            peso = float(peso_raw)
        except Exception:
            peso = None

        # Dimensões Centimetros LxAxC
        dims_raw = str(r[9] if len(r) > 9 else "").strip().lower()
        m = re.match(r"(\d+(?:[.,]\d+)?)\s*[xX*]\s*(\d+(?:[.,]\d+)?)\s*[xX*]\s*(\d+(?:[.,]\d+)?)", dims_raw)
        if m:
            wi_cm = float(m.group(1).replace(",", "."))
            h_cm = float(m.group(2).replace(",", "."))
            l_cm = float(m.group(3).replace(",", "."))
        else:
            wi_cm, h_cm, l_cm = None, None, None

        items.append({
            "name": name,
            "wholesale_price": atacado,
            "retail_price": varejo,
            "weight_kg": peso,
            "width_cm": wi_cm,
            "height_cm": h_cm,
            "length_cm": l_cm,
        })

    return items


def sync_products_sheets(conn, custom_url: Optional[str] = None) -> Dict[str, Any]:
    """Executa a sincronização completa da planilha oficial do Google Sheets com o Supabase."""
    source = get_products_data_source(conn)
    url = (custom_url or source.get("sheets_url") or OFFICIAL_SHEETS_URL).strip()

    export_url = url
    if "docs.google.com/spreadsheets" in export_url and "/export" not in export_url:
        export_url = export_url.split("/edit")[0].rstrip("/") + "/export?format=csv"
        gid = None
        if "#gid=" in url:
            gid = url.split("#gid=")[1].split("&")[0]
        elif "gid=" in url:
            gid = url.split("gid=")[1].split("&")[0]
        if gid:
            export_url += f"&gid={gid}"

    req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        csv_text = resp.read().decode("utf-8-sig", errors="replace")

    parsed_items = parse_official_products_csv(csv_text)
    if not parsed_items:
        raise ValueError("Nenhum modelo válido encontrado no arquivo exportado.")

    all_prods = conn.execute("SELECT id, name FROM products").fetchall()
    created_count = 0
    updated_count = 0

    for item in parsed_items:
        p_match = None
        item_name_up = item["name"].strip().upper()

        for p in all_prods:
            p_up = p["name"].strip().upper()
            if p_up == item_name_up:
                p_match = p
                break

        if not p_match:
            for p in all_prods:
                p_up = p["name"].strip().upper()
                if item_name_up in p_up or p_up in item_name_up:
                    p_match = p
                    break

        if p_match:
            p_id = p_match["id"]
            conn.execute(
                """
                UPDATE products
                SET weight_kg = COALESCE(%s, weight_kg),
                    length_cm = COALESCE(%s, length_cm),
                    width_cm = COALESCE(%s, width_cm),
                    height_cm = COALESCE(%s, height_cm),
                    wholesale_price = COALESCE(%s, wholesale_price),
                    retail_price = COALESCE(%s, retail_price)
                WHERE id = %s
                """,
                (item["weight_kg"], item["length_cm"], item["width_cm"], item["height_cm"],
                 item["wholesale_price"], item["retail_price"], p_id)
            )
            updated_count += 1
        else:
            conn.execute(
                """
                INSERT INTO products (name, category, wholesale_price, retail_price, weight_kg, length_cm, width_cm, height_cm)
                VALUES (%s, 'Motos Elétricas', %s, %s, %s, %s, %s, %s)
                """,
                (item["name"], item["wholesale_price"], item["retail_price"], item["weight_kg"],
                 item["length_cm"], item["width_cm"], item["height_cm"])
            )
            created_count += 1

    total_synced = created_count + updated_count
    msg = f"{total_synced} modelos sincronizados ({updated_count} atualizados, {created_count} novos)"

    conn.execute(
        """
        UPDATE data_sources
        SET sheets_url = %s, last_sync_at = CURRENT_TIMESTAMP, last_sync_status = 'synced',
            last_sync_message = %s, records_count = %s
        WHERE key = 'products_catalog'
        """,
        (url, msg, total_synced)
    )
    conn.commit()

    return {
        "ok": True,
        "message": msg,
        "created": created_count,
        "updated": updated_count,
        "total": total_synced,
    }


def update_product_specs(conn, pid: int, weight_kg: float, length_cm: float, width_cm: float, height_cm: float, wholesale_price: Optional[float] = None) -> bool:
    """Atualização manual rápida de dimensões e peso de um produto."""
    if wholesale_price is not None and wholesale_price > 0:
        conn.execute(
            """
            UPDATE products
            SET weight_kg = %s, length_cm = %s, width_cm = %s, height_cm = %s, wholesale_price = %s
            WHERE id = %s
            """,
            (weight_kg, length_cm, width_cm, height_cm, wholesale_price, pid)
        )
    else:
        conn.execute(
            """
            UPDATE products
            SET weight_kg = %s, length_cm = %s, width_cm = %s, height_cm = %s
            WHERE id = %s
            """,
            (weight_kg, length_cm, width_cm, height_cm, pid)
        )
    conn.commit()
    return True
