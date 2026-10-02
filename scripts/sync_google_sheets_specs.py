"""
Script para sincronizar as especificações de Autonomia, Velocidade Máxima, Motor, Bateria e Ficha Técnica
dos modelos do Outlet a partir da planilha oficial do Google Sheets.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import urllib.request
from pathlib import Path

from database import db
from services.outlet_service import ensure_outlet_schema, run_exec

logger = logging.getLogger(__name__)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1uYnE9-MCSuRSe-9bSvcUulALjvh8aUdYEMbGAWZEC5E/export?format=csv&gid=1639092973"


def fetch_and_sync_specs():
    print("🔄 Baixando especificações atualizadas da planilha do Google Sheets...")
    req = urllib.request.Request(
        SHEET_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = resp.read().decode("utf-8-sig", errors="replace")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    data_rows = rows[3:]
    model_specs_map = {}

    for r in data_rows:
        if len(r) < 3:
            continue
        category = r[0].strip()
        model_raw = r[1].strip()
        desc_free = r[2].strip()
        pontos_fortes = r[3].strip() if len(r) > 3 else ""
        limitacoes = r[4].strip() if len(r) > 4 else ""
        comparacao = r[5].strip() if len(r) > 5 else ""

        if not model_raw:
            continue

        lines = [line.strip() for line in desc_free.split("\n") if line.strip()]
        specs = {}

        for line in lines:
            if line.startswith("Motor"):
                specs["Motor"] = line.replace("Motor ", "").strip()
            elif "km/h" in line:
                specs["Velocidade Máxima"] = line.strip()
            elif "Autonomia" in line:
                specs["Autonomia"] = line.strip()
            elif "Suporta" in line or "kg" in line:
                specs["Carga Máxima"] = line.strip()
            elif "Freios" in line or "freio" in line.lower():
                specs["Freios"] = line.strip()
            elif "Câmbio" in line:
                specs["Câmbio"] = line.strip()
            elif "Aro" in line:
                specs["Aro"] = line.strip()

        if "bateria" in pontos_fortes.lower():
            for part in pontos_fortes.split(";"):
                if "bateria" in part.lower():
                    specs["Bateria"] = part.strip().capitalize()
                    break

        model_specs_map[model_raw] = {
            "category": category,
            "specs": specs,
            "description": pontos_fortes or desc_free.replace("\n", " • "),
            "limitacoes": limitacoes,
            "comparacao": comparacao,
        }

    ensure_outlet_schema()

    updated_count = 0
    with db() as conn:
        rows_db = run_exec(conn, "SELECT id, name, slug, specs_json, description FROM outlet_items").fetchall()
        for item in rows_db:
            item_dict = dict(item)
            item_id = item_dict["id"]
            name = item_dict["name"]
            
            # Match com o modelo da planilha
            matched_sheet_data = None
            for sheet_model_name, sheet_data in model_specs_map.items():
                sm_clean = sheet_model_name.lower().replace(" ", "")
                n_clean = name.lower().replace(" ", "")
                if sm_clean in n_clean or n_clean in sm_clean:
                    matched_sheet_data = sheet_data
                    break

            if matched_sheet_data:
                existing_specs = {}
                if item_dict.get("specs_json"):
                    try:
                        existing_specs = json.loads(item_dict["specs_json"]) if isinstance(item_dict["specs_json"], str) else (item_dict["specs_json"] or {})
                    except Exception:
                        existing_specs = {}

                # Atualizar/Substituir chaves de especificações com a planilha
                new_specs = matched_sheet_data["specs"]
                for k, v in new_specs.items():
                    existing_specs[k] = v

                description = matched_sheet_data["description"]
                if matched_sheet_data.get("limitacoes"):
                    description += f" (Obs: {matched_sheet_data['limitacoes']})"

                specs_str = json.dumps(existing_specs, ensure_ascii=False)

                run_exec(
                    conn,
                    """
                    UPDATE outlet_items
                    SET specs_json = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (specs_str, description, item_id)
                )
                updated_count += 1
                print(f"  ✓ {name}: Especificações atualizadas -> {specs_str}")

        conn.commit()

    print(f"\n✅ Sincronização concluída! {updated_count} modelos do Outlet foram atualizados com a planilha.")


if __name__ == "__main__":
    fetch_and_sync_specs()
