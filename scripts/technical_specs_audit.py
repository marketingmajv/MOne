#!/usr/bin/env python3
"""
M-One Technical Specifications Audit (scripts/technical_specs_audit.py)
Varredura profunda estrita de FICHAS TÉCNICAS E ESPECIFICAÇÕES DE ENGENHARIA.
Cruza Showroom, Atacado e Outlet para apontar conflitos numéricos e campos faltantes,
preservando as copys contextuais de cada canal.
"""

import json
import re
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


def clean_num(val) -> str:
    if val is None:
        return ""
    text = str(val).strip()
    m = re.search(r"(\d+[\.,]?\d*)", text)
    return m.group(1).replace(",", ".") if m else ""


def parse_specs_json(s) -> dict:
    if not s:
        return {}
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s)
    except Exception:
        return {}


def run_technical_audit():
    # 1. Carrega Showroom (maj_models.json)
    cache_path = BASE_DIR / "static" / "data" / "maj_models.json"
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
                "motor": met.get("potencia_nominal_w") or "",
                "velocidade": met.get("velocidade_max_kmh") or "",
                "autonomia": met.get("autonomia_maxima_km") or met.get("autonomia_conservadora_km") or "",
                "bateria": met.get("voltagem_v") or "",
                "quimica": met.get("quimica_bateria") or "",
                "carga": met.get("carga_maxima_kg") or "",
                "freios": met.get("freios") or "",
                "peso": met.get("peso_kg") or "",
            }

    # 2. Carrega Atacado e Outlet do Supabase
    with db() as conn:
        atacado_rows = conn.execute("SELECT id, name, slug, specs_json FROM atacado_items").fetchall()
        outlet_rows = conn.execute("SELECT id, name, slug, specs_json FROM outlet_items").fetchall()

    atacado_data = {normalize_slug(r["slug"]): {"name": r["name"], "specs": parse_specs_json(r["specs_json"])} for r in atacado_rows}
    outlet_data = {normalize_slug(r["slug"]): {"name": r["name"], "specs": parse_specs_json(r["specs_json"])} for r in outlet_rows}

    # Reúne todos os slugs únicos dos 3 canais
    all_slugs = sorted(list(set(list(showroom_data.keys()) + list(atacado_data.keys()) + list(outlet_data.keys()))))

    results = []

    for slug in all_slugs:
        sh = showroom_data.get(slug)
        at = atacado_data.get(slug)
        ou = outlet_data.get(slug)

        ref_name = sh["name"] if sh else (at["name"] if at else (ou["name"] if ou else slug.upper()))

        at_specs = at["specs"] if at else {}
        ou_specs = ou["specs"] if ou else {}

        # Mapeia valores dos 6 atributos vitais
        # Motor
        sh_motor = str(sh.get("motor") or "").replace("W", "").strip() if sh else ""
        at_motor = str(at_specs.get("Motor") or at_specs.get("Potência Nominal") or "").replace("W", "").strip()
        ou_motor = str(ou_specs.get("Motor") or "").replace("W", "").strip()

        # Velocidade
        sh_vel = clean_num(sh.get("velocidade")) if sh else ""
        at_vel = clean_num(at_specs.get("Velocidade Máxima") or at_specs.get("velocidade_max_kmh"))
        ou_vel = clean_num(ou_specs.get("Velocidade Máxima"))

        # Autonomia
        sh_aut = clean_num(sh.get("autonomia")) if sh else ""
        at_aut = clean_num(at_specs.get("Autonomia") or at_specs.get("Autonomia Máxima"))
        ou_aut = clean_num(ou_specs.get("Autonomia"))

        # Bateria (Voltagem)
        sh_bat = clean_num(sh.get("bateria")) if sh else ""
        at_bat = clean_num(at_specs.get("Bateria") or at_specs.get("Voltagem"))
        ou_bat = clean_num(ou_specs.get("Bateria"))

        # Carga Máxima
        sh_carga = clean_num(sh.get("carga")) if sh else ""
        at_carga = clean_num(at_specs.get("Carga Máxima"))
        ou_carga = clean_num(ou_specs.get("Carga Máxima"))

        # Freios
        sh_freios = (sh.get("freios") or "").strip() if sh else ""
        at_freios = (at_specs.get("Freios") or at_specs.get("Sistema de Freios") or "").strip()
        ou_freios = (ou_specs.get("Freios") or "").strip()

        # Detecção de Conflitos e Omissões
        conflitos = []
        omissoes = []

        # Validação Motor
        m_vals = {v for v in [sh_motor, at_motor, ou_motor] if v}
        if len(m_vals) > 1:
            conflitos.append(f"Motor discordante: Sh={sh_motor or 'N/D'}W | At={at_motor or 'N/D'}W | Ou={ou_motor or 'N/D'}W")
        if sh and not at_motor and at:
            omissoes.append("Motor ausente no Atacado")
        if sh and not ou_motor and ou:
            omissoes.append("Motor ausente no Outlet")

        # Validação Bateria
        b_vals = {v for v in [sh_bat, at_bat, ou_bat] if v}
        if len(b_vals) > 1:
            conflitos.append(f"Voltagem da Bateria discordante: Sh={sh_bat or 'N/D'}V | At={at_bat or 'N/D'}V | Ou={ou_bat or 'N/D'}V")
        if sh and not at_bat and at:
            omissoes.append("Bateria ausente no Atacado")
        if sh and not ou_bat and ou:
            omissoes.append("Bateria ausente no Outlet")

        # Validação Autonomia
        a_vals = {v for v in [sh_aut, at_aut, ou_aut] if v}
        if len(a_vals) > 1:
            conflitos.append(f"Autonomia discordante: Sh={sh_aut or 'N/D'}km | At={at_aut or 'N/D'}km | Ou={ou_aut or 'N/D'}km")
        if sh and not at_aut and at:
            omissoes.append("Autonomia ausente no Atacado")
        if sh and not ou_aut and ou:
            omissoes.append("Autonomia ausente no Outlet")

        # Validação Freios
        if sh and not at_freios and at:
            omissoes.append("Freios não informados no Atacado")
        if sh and not ou_freios and ou:
            omissoes.append("Freios não informados no Outlet")

        # Validação Carga Máxima
        if sh and not at_carga and at:
            omissoes.append("Carga Máxima não informada no Atacado")
        if sh and not ou_carga and ou:
            omissoes.append("Carga Máxima não informada no Outlet")

        # Presença nos canais
        presenca = []
        if not sh:
            presenca.append("Não cadastrado no Showroom")
        if not at:
            presenca.append("Não cadastrado no Atacado")
        if not ou:
            presenca.append("Não cadastrado no Outlet")

        # Status Geral
        if conflitos:
            status = "CONFLITO"
        elif omissoes:
            status = "INCOMPLETO"
        elif presenca:
            status = "CANAL_PENDENTE"
        else:
            status = "SINCRONIZADO"

        results.append({
            "name": ref_name,
            "slug": slug,
            "status": status,
            "conflitos": conflitos,
            "omissoes": omissoes,
            "presenca": presenca,
            "sh_vals": {"motor": sh_motor, "vel": sh_vel, "aut": sh_aut, "bat": sh_bat, "carga": sh_carga, "freios": sh_freios},
            "at_vals": {"motor": at_motor, "vel": at_vel, "aut": at_aut, "bat": at_bat, "carga": at_carga, "freios": at_freios},
            "ou_vals": {"motor": ou_motor, "vel": ou_vel, "aut": ou_aut, "bat": ou_bat, "carga": ou_carga, "freios": ou_freios},
            "in_sh": bool(sh),
            "in_at": bool(at),
            "in_ou": bool(ou),
        })

    return results


if __name__ == "__main__":
    audit = run_technical_audit()
    print(f"Total de Modelos Auditados: {len(audit)}")
    conflitos = [r for r in audit if r["status"] == "CONFLITO"]
    incompletos = [r for r in audit if r["status"] == "INCOMPLETO"]
    pendentes = [r for r in audit if r["status"] == "CANAL_PENDENTE"]
    ok = [r for r in audit if r["status"] == "SINCRONIZADO"]

    print(f"  🔴 Conflitos Numéricos: {len(conflitos)}")
    print(f"  🟡 Omissões / Ficha Incompleta: {len(incompletos)}")
    print(f"  ⚪ Modelos com Canal Pendente: {len(pendentes)}")
    print(f"  🟢 Totalmente Sincronizados: {len(ok)}")

