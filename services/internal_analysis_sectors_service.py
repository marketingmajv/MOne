"""
M-One Internal Analysis Sectors & Multi-Cycle History Service
Setorização oficial da Análise Interna em 5 setores canônicos e agregação histórica multi-ciclos.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from database import db
from services.employee_reports_service import get_all_cycles

logger = logging.getLogger(__name__)

# 5 Setores Oficiais da MAJ Mobilidade (alinhados aos 8 colaboradores reportantes)
CANONICAL_SECTORS: List[Dict[str, Any]] = [
    {
        "key": "financeiro",
        "label": "Financeiro & Faturamento",
        "short_label": "Financeiro",
        "icon": "💰",
        "color": "#10b981",
        "badge": "FINANCEIRO",
        "responsibles": "Marisa",
        "employee_keys": ["marisa"],
    },
    {
        "key": "estoque",
        "label": "Estoque & Galpões",
        "short_label": "Estoque",
        "icon": "📦",
        "color": "#f59e0b",
        "badge": "ESTOQUE",
        "responsibles": "Jhon",
        "employee_keys": ["jhon"],
    },
    {
        "key": "oficina",
        "label": "Oficina & Pós-Venda",
        "short_label": "Oficina & Pós-Venda",
        "icon": "🔧",
        "color": "#06b6d4",
        "badge": "OFICINA",
        "responsibles": "Ricardo & Léo",
        "employee_keys": ["ricardo", "leo"],
    },
    {
        "key": "comercial",
        "label": "Comercial & Atacado",
        "short_label": "Comercial & Atacado",
        "icon": "🤝",
        "color": "#8b5cf6",
        "badge": "COMERCIAL",
        "responsibles": "Luiza, Gabriel & Gustavo",
        "employee_keys": ["luiza", "gabriel", "gustavo"],
    },
    {
        "key": "marketing_sistemas",
        "label": "Marketing & Sistemas",
        "short_label": "Marketing & Sistemas",
        "icon": "⚡",
        "color": "#38bdf8",
        "badge": "MARKETING & TI",
        "responsibles": "Fauzer",
        "employee_keys": ["fauzer"],
    },
]

SECTOR_KEYS = [s["key"] for s in CANONICAL_SECTORS]
SECTOR_META_MAP = {s["key"]: s for s in CANONICAL_SECTORS}


def normalize_sector_key(
    raw_pilar: Optional[str],
    envolvidos: Optional[List[str]] = None,
    text: str = "",
) -> str:
    """Mapeia qualquer nome de pilar legado ou livre para uma das 5 chaves canônicas."""
    val = (raw_pilar or "").lower().strip()
    if val in SECTOR_META_MAP:
        return val

    joined_people = " ".join(str(p).lower() for p in (envolvidos or []))
    haystack = f"{val} {joined_people} {(text or '').lower()}"

    if any(k in val for k in ("financ", "caixa", "faturam", "fiscal", "marisa")):
        return "financeiro"
    if any(k in val for k in ("estoq", "galp", "patio", "pátio", "expedi", "jhon")):
        return "estoque"
    if any(k in val for k in ("oficina", "pos_venda", "pós-venda", "pos-venda", "peca", "peça", "triagem", "ricardo", "leo", "léo")):
        return "oficina"
    if any(k in val for k in ("comercial", "venda", "atacado", "varejo", "luiza", "gabriel", "gustavo")):
        return "comercial"
    if any(k in val for k in ("market", "sistem", "ti", "tecnolog", "process", "m-one", "botconversa", "ads", "gmb", "fauzer")):
        return "marketing_sistemas"

    # Fallback pelo conteúdo / envolvidos quando pilar é genérico ("geral", "", etc.)
    if any(k in haystack for k in ("marisa", "boleto", "mercado pago", "nf ", "caixa")):
        return "financeiro"
    if any(k in haystack for k in ("jhon", "chassi", "contagem", "galpão", "galpao")):
        return "estoque"
    if any(k in haystack for k in ("ricardo", "léo", "leo", "bateria", "oficina", "pós-venda", "os ")):
        return "oficina"
    if any(k in haystack for k in ("luiza", "gabriel", "gustavo", "revenda", "lojista", "atacado")):
        return "comercial"
    if any(k in haystack for k in ("fauzer", "meta ads", "botconversa", "m-one", "gmb", "tráfego")):
        return "marketing_sistemas"

    return "comercial"


def _parse_json_safe(raw: Any, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except Exception:
            return default
    return default


def extract_normalized_cycle_sectors(analysis_row: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai e normaliza gargalos, observações, destaques e decisões agrupados pelos 5 setores."""
    curated = _parse_json_safe(analysis_row.get("curated_data_json"), None)
    ai_sum = _parse_json_safe(analysis_row.get("ai_summary_json"), None)
    decisions_saved = _parse_json_safe(analysis_row.get("meeting_decisions_json"), [])

    base = curated or ai_sum or {}
    if not isinstance(base, dict):
        base = {}

    alerts = base.get("radar_alerts") or []
    decisions = base.get("pauta_decisoes") or []
    pilares = base.get("pilares") or {}

    # Mescla deliberações salvas na reunião ao vivo se existirem
    if isinstance(decisions_saved, list) and decisions_saved:
        saved_by_id = {d.get("id"): d for d in decisions_saved if isinstance(d, dict) and d.get("id")}
        merged_decisions = []
        for idx, dec in enumerate(decisions):
            if not isinstance(dec, dict):
                continue
            d_copy = dict(dec)
            match = saved_by_id.get(d_copy.get("id"))
            if not match and idx < len(decisions_saved) and isinstance(decisions_saved[idx], dict):
                if decisions_saved[idx].get("title") == d_copy.get("title"):
                    match = decisions_saved[idx]
            if match:
                d_copy["status"] = match.get("status", d_copy.get("status", "pending"))
                d_copy["deliberacao_texto"] = match.get("deliberacao_texto", d_copy.get("deliberacao_texto", ""))
            merged_decisions.append(d_copy)
        decisions = merged_decisions or decisions_saved

    sectors: Dict[str, Dict[str, Any]] = {}
    for meta in CANONICAL_SECTORS:
        sk = meta["key"]
        pilar_data = pilares.get(sk) if isinstance(pilares, dict) else {}
        if not isinstance(pilar_data, dict):
            pilar_data = {}
        sectors[sk] = {
            "key": sk,
            "label": meta["label"],
            "short_label": meta["short_label"],
            "icon": meta["icon"],
            "color": meta["color"],
            "responsibles": meta["responsibles"],
            "gargalos": [],
            "observacoes": list(pilar_data.get("pontos_atencao") or []),
            "destaques": list(pilar_data.get("destaques") or []),
            "decisoes": [],
        }

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        sk = normalize_sector_key(
            alert.get("pilar") or alert.get("pilar_label"),
            alert.get("envolvidos"),
            f"{alert.get('title', '')} {alert.get('description', '')}",
        )
        sectors[sk]["gargalos"].append({
            "id": alert.get("id"),
            "severity": alert.get("severity", "medium"),
            "title": alert.get("title", ""),
            "description": alert.get("description", ""),
            "envolvidos": alert.get("envolvidos") or [],
            "pilar": sk,
        })

    for dec in decisions:
        if not isinstance(dec, dict):
            continue
        sk = normalize_sector_key(
            dec.get("pilar"),
            None,
            f"{dec.get('title', '')} {dec.get('context', '')}",
        )
        sectors[sk]["decisoes"].append({
            "id": dec.get("id"),
            "title": dec.get("title", ""),
            "context": dec.get("context", ""),
            "proposta": dec.get("proposta", ""),
            "status": dec.get("status", "pending"),
            "deliberacao_texto": dec.get("deliberacao_texto", ""),
            "pilar": sk,
        })

    return {
        "executive_summary": base.get("executive_summary", ""),
        "sectors": sectors,
    }


def _topic_fingerprint(title: str) -> str:
    """Gera assinatura normalizada para detectar gargalos recorrentes entre ciclos."""
    clean = re.sub(r"[^a-zà-ú0-9\s]", " ", (title or "").lower())
    stopwords = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "para", "com", "por", "a", "o", "os", "as", "sem", "falta"}
    tokens = [t for t in clean.split() if len(t) > 2 and t not in stopwords]
    return " ".join(tokens[:4])


def get_multi_cycle_internal_history(include_curating: bool = False) -> Dict[str, Any]:
    """Agrega as análises internas de todos os ciclos para visão histórica e recorrências."""
    cycles = get_all_cycles()
    with db() as conn:
        rows = conn.execute("SELECT * FROM maj_cycle_internal_analyses").fetchall()
        analyses_by_cycle = {r["cycle_id"]: dict(r) for r in rows}

    timeline: List[Dict[str, Any]] = []
    recurring_map: Dict[str, Dict[str, Any]] = {}
    unresolved_decisions: List[Dict[str, Any]] = []
    sector_totals: Dict[str, Dict[str, int]] = {
        sk: {"gargalos": 0, "observacoes": 0, "decisoes_pendentes": 0}
        for sk in SECTOR_KEYS
    }

    for cycle in cycles:
        cid = cycle["id"]
        analysis = analyses_by_cycle.get(cid)
        if not analysis:
            continue
        status = analysis.get("status", "curating")
        if not include_curating and status != "published":
            continue

        normalized = extract_normalized_cycle_sectors(analysis)
        sectors = normalized["sectors"]

        has_content = bool(normalized["executive_summary"]) or any(
            s["gargalos"] or s["observacoes"] or s["decisoes"] or s["destaques"]
            for s in sectors.values()
        )
        if not has_content:
            continue

        cycle_entry = {
            "cycle_id": cid,
            "cycle_code": cycle.get("cycle_code", ""),
            "cycle_title": cycle.get("display_name") or cycle.get("title") or f"Ciclo #{cid}",
            "status": status,
            "executive_summary": normalized["executive_summary"],
            "sectors": sectors,
        }
        timeline.append(cycle_entry)

        # Acumula recorrências de gargalos e pendências de decisões
        for sk, sec in sectors.items():
            sector_totals[sk]["gargalos"] += len(sec["gargalos"])
            sector_totals[sk]["observacoes"] += len(sec["observacoes"])

            for g in sec["gargalos"]:
                fp = f"{sk}::{_topic_fingerprint(g.get('title', ''))}"
                if not fp.endswith("::"):
                    if fp not in recurring_map:
                        recurring_map[fp] = {
                            "sector_key": sk,
                            "sector_label": sec["short_label"],
                            "sector_icon": sec["icon"],
                            "sector_color": sec["color"],
                            "title": g.get("title", ""),
                            "latest_description": g.get("description", ""),
                            "severity": g.get("severity", "medium"),
                            "count": 0,
                            "cycles": [],
                        }
                    recurring_map[fp]["count"] += 1
                    recurring_map[fp]["cycles"].append(cycle.get("cycle_code") or f"#{cid}")
                    if g.get("severity") == "high":
                        recurring_map[fp]["severity"] = "high"

            for d in sec["decisoes"]:
                if d.get("status") in ("pending", "postponed", "", None):
                    sector_totals[sk]["decisoes_pendentes"] += 1
                    unresolved_decisions.append({
                        "cycle_id": cid,
                        "cycle_code": cycle.get("cycle_code", ""),
                        "cycle_title": cycle_entry["cycle_title"],
                        "sector_key": sk,
                        "sector_label": sec["short_label"],
                        "sector_icon": sec["icon"],
                        "sector_color": sec["color"],
                        "title": d.get("title", ""),
                        "proposta": d.get("proposta", ""),
                        "status": d.get("status") or "pending",
                    })

    recurring_list = sorted(
        [item for item in recurring_map.values() if item["count"] >= 2],
        key=lambda x: (-x["count"], 0 if x["severity"] == "high" else 1),
    )

    return {
        "sectors_meta": CANONICAL_SECTORS,
        "total_cycles": len(timeline),
        "timeline": timeline,
        "recurring_gargalos": recurring_list,
        "unresolved_decisions": unresolved_decisions,
        "sector_totals": sector_totals,
    }

