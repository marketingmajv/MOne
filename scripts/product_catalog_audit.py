#!/usr/bin/env python3
"""
M-One Product Catalog Audit (scripts/product_catalog_audit.py)
Varredura profunda de consistência entre Showroom, Atacado e Outlet.
Compara descrições, especificações técnicas e propõe a Descrição Combinada Mestre.
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database import db
from services.outlet_specs import MODEL_SPECS

def normalize_slug(s: str) -> str:
    s = (s or "").strip().lower().replace("_", "-")
    mapping = {
        "v8-mini-ultra": "v8-mini",
        "gp1000": "gp-1000",
        "sport-701-short": "sport-701-short",
        "rz110": "rz-110",
        "dbzero": "db-zero",
    }
    return mapping.get(s, s)

def run_audit():
    # 1. Carrega Showroom
    cache_path = Path(__file__).resolve().parent.parent / "static" / "data" / "maj_models.json"
    showroom_data = {}
    if cache_path.is_file():
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for m in raw.get("all_models", []):
            slug = normalize_slug(m.get("slug") or "")
            met = m.get("metrics") or {}
            showroom_data[slug] = {
                "name": m.get("modelo", ""),
                "slug": slug,
                "categoria": m.get("categoria", ""),
                "diferencial": met.get("diferencial", ""),
                "descricao_livre": met.get("descricao_livre", ""),
                "pontos_fortes": met.get("pontos_fortes", ""),
                "metrics": met,
            }

    # 2. Carrega Atacado e Outlet do Supabase
    with db() as conn:
        atacado_rows = conn.execute("SELECT id, name, slug, category, description, specs_json FROM atacado_items").fetchall()
        outlet_rows = conn.execute("SELECT id, name, slug, category, description, specs_json, price_outlet FROM outlet_items").fetchall()

    atacado_data = {normalize_slug(r["slug"]): r for r in atacado_rows}
    outlet_data = {normalize_slug(r["slug"]): r for r in outlet_rows}

    # Reúne todos os slugs únicos
    all_slugs = sorted(list(set(list(showroom_data.keys()) + list(atacado_data.keys()) + list(outlet_data.keys()))))

    results = []

    for slug in all_slugs:
        sh = showroom_data.get(slug)
        at = atacado_data.get(slug)
        ou = outlet_data.get(slug)

        # Nome de referência
        ref_name = (sh["name"] if sh else (at["name"] if at else (ou["name"] if ou else slug.upper())))
        
        # Descrições atuais
        sh_desc = ""
        if sh:
            dif = sh.get("diferencial") or ""
            liv = sh.get("descricao_livre") or ""
            sh_desc = dif if dif else liv

        at_desc = (at.get("description") or "").strip() if at else "[NÃO CADASTRADO NO ATACADO]"
        ou_desc = (ou.get("description") or "").strip() if ou else "[NÃO CADASTRADO NO OUTLET]"

        # Proposta de Descrição Combinada Mestre (Texto Conceitual + Bullets)
        # 1. Pega proposta de valor conceitual
        conceito = ""
        if sh and sh.get("diferencial"):
            conceito = sh["diferencial"].strip()
        elif ou and ou.get("description") and "revenda no atacado" not in ou.get("description").lower():
            conceito = ou["description"].strip()
        elif ref_name in MODEL_SPECS and MODEL_SPECS[ref_name].get("description"):
            conceito = MODEL_SPECS[ref_name]["description"].strip()
        else:
            conceito = f"Veículo elétrico MAJ {ref_name} projetado para máxima eficiência e conforto urbano."

        # 2. Pega bullets de destaques
        bullets = []
        if sh and sh.get("metrics"):
            m = sh["metrics"]
            if m.get("potencia_nominal_w"):
                bullets.append(f"Motor {m['potencia_nominal_w']}W")
            if m.get("velocidade_max_kmh"):
                bullets.append(f"Até {m['velocidade_max_kmh']} km/h")
            aut = m.get("autonomia_maxima_km") or m.get("autonomia_conservadora_km")
            if aut:
                bullets.append(f"Autonomia de até {aut} km" if "km" not in str(aut).lower() else f"Autonomia {aut}")
            if m.get("carga_maxima_kg"):
                bullets.append(f"Suporta até {m['carga_maxima_kg']} kg")
            if m.get("freios"):
                bullets.append(f"Freios {m['freios']}")
        elif ref_name in MODEL_SPECS and MODEL_SPECS[ref_name].get("specs"):
            sp = MODEL_SPECS[ref_name]["specs"]
            for k in ["Motor", "Velocidade Máxima", "Autonomia", "Bateria", "Carga Máxima", "Freios"]:
                if sp.get(k):
                    bullets.append(f"{k}: {sp[k]}")

        # Monta a Descrição Combinada
        if bullets:
            bullets_text = " • ".join(bullets[:4])
            prop_desc = f"{conceito} ({bullets_text})"
        else:
            prop_desc = conceito

        # Análise de inconsistência
        status = "OK"
        divergencias = []

        if not sh:
            divergencias.append("Ausente no Showroom")
        if not at:
            divergencias.append("Ausente no Atacado")
        if not ou:
            divergencias.append("Ausente no Outlet")

        if at and ou:
            if at_desc.lower() != ou_desc.lower():
                divergencias.append("Descrições Atacado e Outlet diferentes")
            if "revenda no atacado" in at_desc.lower():
                divergencias.append("Atacado usa texto genérico de compra CNPJ")

        status = "CRÍTICO" if len(divergencias) > 1 else ("DIVERGENTE" if divergencias else "SINCRONIZADO")

        results.append({
            "slug": slug,
            "name": ref_name,
            "status": status,
            "divergencias": divergencias,
            "sh_desc": sh_desc,
            "at_desc": at_desc,
            "ou_desc": ou_desc,
            "proposed_master_desc": prop_desc,
            "in_showroom": bool(sh),
            "in_atacado": bool(at),
            "in_outlet": bool(ou),
        })

    return results

if __name__ == "__main__":
    res = run_audit()
    print(f"Total Modelos Auditados: {len(res)}")
    divergentes = [r for r in res if r["status"] != "SINCRONIZADO"]
    print(f"Modelos com Divergências: {len(divergentes)}")
    for r in res[:5]:
        print(f"\n[{r['status']}] {r['name']} ({r['slug']})")
        print(f"  Divergências: {', '.join(r['divergencias']) if r['divergencias'] else 'Nenhuma'}")
        print(f"  Proposta Mestre: {r['proposed_master_desc']}")
