"""
M-One Atacado Enrichment & Canonical Sync Service (services/atacado_enrichment_service.py)
Enriquecimento técnico e comercial dos produtos de Atacado B2B:
Cálculo de margens estimadas, trilhas de produto, diferenciais de catálogo, faixas escalonadas de preço,
vínculo automático com a ficha técnica canônica (maj_models.json) e sincronização bidirecional.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = BASE_DIR / "static" / "data" / "maj_models.json"
API_CACHE_FILE = BASE_DIR / "api" / "static" / "data" / "maj_models.json"
OVERRIDES_FILE = BASE_DIR / "static" / "data" / "model_overrides.json"
API_OVERRIDES_FILE = BASE_DIR / "api" / "static" / "data" / "model_overrides.json"

CAMPEOES_SLUGS = {"max-12", "flow-one", "m2", "classic-1000", "gp1000", "gp-1000", "classic"}
ENTRADA_SLUGS = {"v8-mini-ultra", "v8-mini", "ride-on", "v20-ultra", "v80-pro", "m9-pro", "m50-pro"}
AUTONOMIA_SLUGS = {"rz-110", "vittoria", "nova", "x15-pro", "db-zero", "sport-701-short"}

DIFFERENTIATORS_DEFAULT = {
    "max-12": "🎁 Baú Incluso de Fábrica",
    "v20-ultra": "🛞 Pneus Fat Tire 20x4.0",
    "m9-pro": "☕ Estilo Café Racer Vintage",
    "flow-one": "🎁 Baú Porta-Capacete Espaçoso",
    "ride-on": "⚡ Chassi Ultraleve e Ágil",
    "m2": "🎁 Baú Incluso de Fábrica",
    "vittoria": "🎁 Baú Clássico Incluso",
    "gp1000": "⚡ Sistema 72V 30Ah",
    "gp-1000": "⚡ Sistema 72V 30Ah",
    "v80-pro": "🛡️ Quadro Reforçado Ergonômico",
    "jm-125": "🚀 Super Motor 3000W",
    "nova": "🔑 Partida Keyless + Alarme",
    "x15-pro": "🏎️ Duplo Amortecedor Reforçado",
    "mantis": "🏁 Chassi Esportivo Firme",
    "classic-1000": "🎁 Baú Retrô Incluso",
    "classic": "🎁 Baú Retrô Incluso",
    "v8-mini-ultra": "🚲 Quadro Baixo Step-Through",
    "v8-mini": "🚲 Quadro Baixo Step-Through",
    "rz-110": "💡 Faróis Ultra Potentes",
    "m50-pro": "✈️ Alumínio Aeroespacial",
    "db-zero": "🛸 Design Futurista Silver Black",
    "sport-701-short": "🏁 Suspensão Invertida Esportiva",
    "q8": "🧺 Quadro Rebaixado Conforto",
}

WH_LOOKUP = {
    "flow-one": 1440, "m2": 1440, "gp1000": 2160, "gp-1000": 2160, "vittoria": 1440,
    "classic-1000": 1440, "classic": 1440, "rz-110": 1440, "max-12": 1200, "nova": 1200,
    "x15-pro": 1200, "db-zero": 1200, "v20-ultra": 960, "ride-on": 960, "m9-pro": 960,
    "v80-pro": 960, "v8-mini-ultra": 720, "v8-mini": 720, "m50-pro": 960,
    "mantis": 1200, "jm-125": 1440,
}

CANONICAL_SLUG_ALIASES = {
    "max-12": "max-12",
    "max-12-maj": "max-12",
    "x13": "max-12",
    "x-13": "max-12",
    "gp1000": "gp-1000",
    "gp-1000": "gp-1000",
    "v8-mini-ultra": "v8-mini",
    "v8-mini": "v8-mini",
    "classic": "classic-1000",
    "classic-1000": "classic-1000",
    "flow-one": "flow-one",
    "flow-on": "flow-one",
    "db-zero": "db-zero",
    "dbzero": "db-zero",
    "m2": "m2",
    "scooter-m2": "m2",
    "vittoria": "vittoria",
    "sport-701-short": "sport-701-short",
    "nova": "nova",
    "rz-110": "rz-110",
    "ride-on": "ride-on",
    "m9-pro": "m9-pro",
    "v80-pro": "v80-pro",
    "m50-pro": "m50-pro",
    "v20-ultra": "v20-ultra",
    "h1": "h1",
}


def _slugify_simple(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[àáâãäå]", "a", s)
    s = re.sub(r"[èéêë]", "e", s)
    s = re.sub(r"[ìíîï]", "i", s)
    s = re.sub(r"[òóôõö]", "o", s)
    s = re.sub(r"[ùúûü]", "u", s)
    s = re.sub(r"[ç]", "c", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def resolve_canonical_slug(slug: str = "", name: str = "") -> str:
    """Resolve o slug ou nome de um produto de atacado para o slug canônico em maj_models.json."""
    for candidate in [_slugify_simple(slug), _slugify_simple(name)]:
        if not candidate:
            continue
        if candidate in CANONICAL_SLUG_ALIASES:
            return CANONICAL_SLUG_ALIASES[candidate]
    return _slugify_simple(slug) or _slugify_simple(name)


def load_canonical_models_map() -> Dict[str, Dict[str, Any]]:
    """Carrega rapidamente os modelos canônicos do disco aplicando overrides do Showroom."""
    models_list: List[Dict[str, Any]] = []
    for path in [CACHE_FILE, API_CACHE_FILE]:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    models_list = data.get("all_models") or data.get("models") or []
                if models_list:
                    break
            except Exception as e:
                logger.debug("Erro ao ler cache canônico %s: %s", path, e)

    try:
        from services.showroom_crud_service import merge_showroom_overrides
        models_list = merge_showroom_overrides(copy.deepcopy(models_list))
    except Exception as e:
        logger.debug("Aviso ao mesclar overrides canônicos: %s", e)

    result: Dict[str, Dict[str, Any]] = {}
    for m in models_list:
        s = (m.get("slug") or "").strip().lower()
        if s:
            result[s] = m
    return result


def extract_canonical_tech_specs(
    slug: str,
    name: str = "",
    item_specs: Optional[Dict[str, Any]] = None,
    canonical_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extrai a ficha técnica completa combinando o modelo canônico e overrides de atacado."""
    c_slug = resolve_canonical_slug(slug, name)
    if canonical_map is None:
        canonical_map = load_canonical_models_map()

    target = canonical_map.get(c_slug) or canonical_map.get(_slugify_simple(slug)) or {}
    sections = target.get("sections") or {}
    metrics = target.get("metrics") or {}
    desemp = sections.get("Desempenho") or {}
    bat = sections.get("Bateria e autonomia") or {}
    est = sections.get("Estrutura e conforto") or {}
    seg = sections.get("Segurança e componentes") or {}
    com = sections.get("Uso e comercial") or {}
    livre = sections.get("Texto livre") or {}

    specs = item_specs if isinstance(item_specs, dict) else {}

    def _pick(*vals: Any, default: str = "") -> str:
        for v in vals:
            if v is not None and str(v).strip() != "":
                return str(v).strip()
        return default

    freios_seg = ""
    if seg.get("Freio dianteiro") or seg.get("Freio traseiro"):
        freios_seg = f"Diant: {seg.get('Freio dianteiro', '')} / Tras: {seg.get('Freio traseiro', '')}".strip(" /")

    default_wh = f"{WH_LOOKUP.get(c_slug, WH_LOOKUP.get(_slugify_simple(slug), 1200))}Wh"

    return {
        "canonical_slug": c_slug,
        "has_canonical": bool(target),
        "modelo_canonico": target.get("modelo") or name,
        "categoria_canonica": target.get("categoria") or ("Bike" if "bike" in c_slug else "Scooter"),
        "potencia_nominal_w": _pick(specs.get("Potência Nominal"), specs.get("Potência"), metrics.get("potencia_nominal_w"), desemp.get("Potência nominal (W)"), default="1000W"),
        "velocidade_max_kmh": _pick(specs.get("Velocidade Máxima"), metrics.get("velocidade_max_kmh"), desemp.get("Velocidade máxima (km/h)"), default="32 km/h"),
        "modos_conducao": _pick(specs.get("Modos de Condução"), desemp.get("Modos de condução"), default="3 níveis"),
        "possui_re": _pick(specs.get("Marcha a Ré"), desemp.get("Possui ré?"), default="Sim"),
        "voltagem_v": _pick(specs.get("Voltagem"), metrics.get("voltagem_v"), bat.get("Voltagem (V)"), default="60V"),
        "capacidade_ah": _pick(specs.get("Capacidade (Ah)"), specs.get("Capacidade da Bateria"), metrics.get("capacidade_ah"), bat.get("Capacidade (Ah)"), default="20Ah"),
        "capacidade_wh": _pick(specs.get("Capacidade (Wh)"), specs.get("Energia (Wh)"), metrics.get("capacidade_wh"), bat.get("Capacidade (Wh)"), default=default_wh),
        "quimica_bateria": _pick(specs.get("Química da Bateria"), specs.get("Tipo de Bateria"), metrics.get("quimica_bateria"), bat.get("Química / tipo"), default="LiFePO₄ (LFP)"),
        "autonomia_conservadora_km": _pick(specs.get("Autonomia Conservadora"), metrics.get("autonomia_conservadora_km"), bat.get("Autonomia conservadora (km)"), default="35 km"),
        "autonomia_maxima_km": _pick(specs.get("Autonomia Máxima"), specs.get("Autonomia Estimada"), metrics.get("autonomia_maxima_km"), bat.get("Autonomia máxima estimada (km)"), default="50 km"),
        "freios": _pick(specs.get("Sistema de Freios"), specs.get("Freios"), metrics.get("freios"), est.get("Tipo de freios"), freios_seg, default="Diant: Hidráulico / Tras: Hidráulico"),
        "suspensao": _pick(specs.get("Suspensão"), est.get("Suspensão"), default="Dupla dianteira e traseira"),
        "aro_pneu": _pick(specs.get("Aro / Pneu"), specs.get("Pneus"), est.get("Aro / Pneu"), seg.get("Pneu / aro"), default="Aro 10/12 tubeless"),
        "carga_maxima_kg": _pick(specs.get("Carga Máxima"), metrics.get("carga_maxima_kg"), est.get("Carga máxima suportada (kg)"), est.get("Carga máxima (kg)"), default="180 kg"),
        "peso_kg": _pick(specs.get("Peso do Veículo"), metrics.get("peso_kg"), est.get("Peso do veículo (kg)"), default="75 kg"),
        "diferencial": _pick(metrics.get("diferencial"), com.get("Diferencial"), com.get("Principal diferencial")),
        "descricao_livre": _pick(metrics.get("descricao_livre"), livre.get("Descrição livre"), livre.get("Descrição comercial livre")),
    }


def sync_atacado_to_canonical_model(
    form_data: Dict[str, Any],
    existing_specs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constrói o specs_json consolidado para atacado_items e sincroniza as especificações
    técnicas com o modelo canônico correspondente (model_overrides.json e maj_models.json),
    preservando integralmente os banners e configurações visuais do Showroom.
    """
    specs_out = dict(existing_specs) if isinstance(existing_specs, dict) else {}

    field_to_label = [
        ("potencia_nominal_w", "Potência Nominal"),
        ("velocidade_max_kmh", "Velocidade Máxima"),
        ("modos_conducao", "Modos de Condução"),
        ("possui_re", "Marcha a Ré"),
        ("voltagem_v", "Voltagem"),
        ("capacidade_ah", "Capacidade (Ah)"),
        ("capacidade_wh", "Capacidade (Wh)"),
        ("quimica_bateria", "Química da Bateria"),
        ("autonomia_conservadora_km", "Autonomia Conservadora"),
        ("autonomia_maxima_km", "Autonomia Máxima"),
        ("freios", "Sistema de Freios"),
        ("suspensao", "Suspensão"),
        ("aro_pneu", "Aro / Pneu"),
        ("carga_maxima_kg", "Carga Máxima"),
        ("peso_kg", "Peso do Veículo"),
    ]

    clean_tech: Dict[str, str] = {}
    for key, label in field_to_label:
        val = str(form_data.get(key) or "").strip()
        clean_tech[key] = val
        if val:
            specs_out[label] = val

    name = str(form_data.get("name") or "").strip()
    raw_slug = str(form_data.get("slug") or name).strip()
    c_slug = resolve_canonical_slug(raw_slug, name)
    if not c_slug:
        return specs_out

    try:
        from services.showroom_crud_service import load_model_overrides, save_model_overrides, merge_showroom_overrides

        canonical_map = load_canonical_models_map()
        base_model = copy.deepcopy(canonical_map.get(c_slug) or {})
        overrides = load_model_overrides()
        existing_ovr = copy.deepcopy(overrides.get(c_slug) or base_model or {})

        cat_raw = str(form_data.get("category") or "").strip()
        if "bike" in cat_raw.lower():
            canon_cat = "Bike"
        elif "triciclo" in cat_raw.lower():
            canon_cat = "Triciclo"
        elif "patinete" in cat_raw.lower():
            canon_cat = "Patinete"
        else:
            canon_cat = existing_ovr.get("categoria") or base_model.get("categoria") or "Scooter"

        existing_ovr.setdefault("slug", c_slug)
        existing_ovr.setdefault("modelo", base_model.get("modelo") or name)
        existing_ovr["categoria"] = canon_cat
        if "is_active" not in existing_ovr:
            existing_ovr["is_active"] = base_model.get("is_active", True)

        metrics = existing_ovr.setdefault("metrics", dict(base_model.get("metrics") or {}))
        for m_key in [
            "potencia_nominal_w", "velocidade_max_kmh", "autonomia_conservadora_km",
            "autonomia_maxima_km", "voltagem_v", "capacidade_ah", "capacidade_wh",
            "quimica_bateria", "carga_maxima_kg", "peso_kg", "freios"
        ]:
            if clean_tech.get(m_key):
                metrics[m_key] = clean_tech[m_key]

        badge_val = str(form_data.get("badge") or "").strip()
        desc_val = str(form_data.get("description") or "").strip()
        if badge_val and not metrics.get("diferencial"):
            metrics["diferencial"] = badge_val
        if desc_val:
            metrics["descricao_livre"] = desc_val

        sections = existing_ovr.setdefault("sections", copy.deepcopy(base_model.get("sections") or {}))
        desemp = sections.setdefault("Desempenho", {})
        if clean_tech["potencia_nominal_w"]:
            desemp["Potência nominal (W)"] = clean_tech["potencia_nominal_w"]
        if clean_tech["velocidade_max_kmh"]:
            desemp["Velocidade máxima (km/h)"] = clean_tech["velocidade_max_kmh"]
        if clean_tech["modos_conducao"]:
            desemp["Modos de condução"] = clean_tech["modos_conducao"]
        if clean_tech["possui_re"]:
            desemp["Possui ré?"] = clean_tech["possui_re"]

        bat = sections.setdefault("Bateria e autonomia", {})
        if clean_tech["quimica_bateria"]:
            bat["Química / tipo"] = clean_tech["quimica_bateria"]
        if clean_tech["voltagem_v"]:
            bat["Voltagem (V)"] = clean_tech["voltagem_v"]
        if clean_tech["capacidade_ah"]:
            bat["Capacidade (Ah)"] = clean_tech["capacidade_ah"]
        if clean_tech["capacidade_wh"]:
            bat["Capacidade (Wh)"] = clean_tech["capacidade_wh"]
        if clean_tech["autonomia_conservadora_km"]:
            bat["Autonomia conservadora (km)"] = clean_tech["autonomia_conservadora_km"]
        if clean_tech["autonomia_maxima_km"]:
            bat["Autonomia máxima estimada (km)"] = clean_tech["autonomia_maxima_km"]

        est = sections.setdefault("Estrutura e conforto", {})
        if clean_tech["carga_maxima_kg"]:
            est["Carga máxima suportada (kg)"] = clean_tech["carga_maxima_kg"]
            est["Carga máxima (kg)"] = clean_tech["carga_maxima_kg"]
        if clean_tech["peso_kg"]:
            est["Peso do veículo (kg)"] = clean_tech["peso_kg"]
        if clean_tech["freios"]:
            est["Tipo de freios"] = clean_tech["freios"]
        if clean_tech["suspensao"]:
            est["Suspensão"] = clean_tech["suspensao"]
        if clean_tech["aro_pneu"]:
            est["Aro / Pneu"] = clean_tech["aro_pneu"]

        if desc_val:
            livre = sections.setdefault("Texto livre", {})
            livre["Descrição livre"] = desc_val

        overrides[c_slug] = existing_ovr
        save_model_overrides(overrides)

        # Atualizar arquivos maj_models.json (static/ e api/static/) instantaneamente
        for cache_path in [CACHE_FILE, API_CACHE_FILE]:
            if cache_path.is_file():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cache_payload = json.load(f)
                    all_m = cache_payload.get("all_models") or cache_payload.get("models") or []
                    merged_m = merge_showroom_overrides(all_m)
                    cache_payload["all_models"] = merged_m
                    cache_payload["models"] = [m for m in merged_m if m.get("is_active", True)]
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(cache_payload, f, ensure_ascii=False, indent=2)
                except Exception as ce:
                    logger.debug("Aviso ao atualizar cache %s: %s", cache_path, ce)

        import services.maj_models_sync_service as sync_svc
        sync_svc._memory_cache = None
        sync_svc._last_sync_time = 0
    except Exception as e:
        logger.warning("Aviso ao sincronizar ficha canônica do modelo %s: %s", c_slug, e)

    return specs_out


def enrich_atacado_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enriquece itens com margem estimada, trilhas, faixas escalonadas, ficha canônica e mídias."""
    canonical_map = load_canonical_models_map()

    for item in items:
        slug = (item.get("slug") or "").lower().strip()
        p_out = float(item.get("price_outlet") or 0)
        p_orig = float(item.get("price_original") or 0)

        item["price_tier_1"] = p_out
        item["price_tier_2"] = max(0.0, round(p_out - 100.0, 2))
        item["price_tier_3"] = max(0.0, round(p_out - 200.0, 2))

        if p_orig > p_out and p_out > 0:
            margin_reais = round(p_orig - p_out, 2)
            margin_pct = int(round((margin_reais / p_orig) * 100))
        else:
            margin_pct = 30 if p_out > 0 else 0
            p_orig = round(p_out / 0.70, 2) if p_out > 0 else 0
            margin_reais = round(p_orig - p_out, 2) if p_out > 0 else 0

        item["margin_reais"] = margin_reais
        item["margin_percent"] = margin_pct
        item["price_retail_suggested"] = p_orig

        if slug in CAMPEOES_SLUGS:
            item["track"] = "campeoes"
        elif slug in ENTRADA_SLUGS:
            item["track"] = "entrada"
        elif slug in AUTONOMIA_SLUGS:
            item["track"] = "autonomia"
        else:
            if p_out <= 5500:
                item["track"] = "entrada"
            elif p_out <= 7700:
                item["track"] = "campeoes"
            else:
                item["track"] = "autonomia"

        raw_badge = (item.get("badge") or "").strip()
        if raw_badge and raw_badge not in ["VENDA ATACADO CNPJ", "EXCLUSIVO CNPJ", "NOVO"]:
            item["differentiator"] = raw_badge
        else:
            item["differentiator"] = DIFFERENTIATORS_DEFAULT.get(slug, "⚡ Pronta Entrega Brasil")

        item["has_trunk"] = any(w in item["differentiator"].lower() for w in ["baú", "bau", "porta-capacete"])
        item["battery_wh"] = WH_LOOKUP.get(slug, 1200)

        BIKE_SLUGS = {"m9-pro", "m50-pro", "v20-ultra", "v8-mini-ultra", "v8-mini", "v80-pro"}
        if slug in BIKE_SLUGS or "bike" in (item.get("category") or "").lower() or "bike" in slug:
            item["vehicle_type"] = "bike"
            item["category_display"] = "Bike Elétrica"
        else:
            item["vehicle_type"] = "scooter"
            item["category_display"] = "Scooter Elétrica"

        item["is_best_seller"] = bool(item.get("is_best_seller"))

        # Enriquecer com especificações técnicas canônicas
        existing_specs = item.get("specs_json") if isinstance(item.get("specs_json"), dict) else {}
        canonical_specs = extract_canonical_tech_specs(
            slug=slug,
            name=item.get("name") or "",
            item_specs=existing_specs,
            canonical_map=canonical_map,
        )
        item["canonical_specs"] = canonical_specs

        # Preencher specs_json com dados canônicos caso ainda não estejam populados
        enriched_specs = dict(existing_specs)
        default_spec_pairs = [
            ("Potência Nominal", canonical_specs.get("potencia_nominal_w")),
            ("Velocidade Máxima", canonical_specs.get("velocidade_max_kmh")),
            ("Modos de Condução", canonical_specs.get("modos_conducao")),
            ("Voltagem", canonical_specs.get("voltagem_v")),
            ("Capacidade (Ah)", canonical_specs.get("capacidade_ah")),
            ("Capacidade (Wh)", canonical_specs.get("capacidade_wh")),
            ("Química da Bateria", canonical_specs.get("quimica_bateria")),
            ("Autonomia Conservadora", canonical_specs.get("autonomia_conservadora_km")),
            ("Autonomia Máxima", canonical_specs.get("autonomia_maxima_km")),
            ("Sistema de Freios", canonical_specs.get("freios")),
            ("Suspensão", canonical_specs.get("suspensao")),
            ("Aro / Pneu", canonical_specs.get("aro_pneu")),
            ("Carga Máxima", canonical_specs.get("carga_maxima_kg")),
            ("Peso do Veículo", canonical_specs.get("peso_kg")),
        ]
        for label, val in default_spec_pairs:
            if val and label not in enriched_specs:
                enriched_specs[label] = val
        item["specs_json"] = enriched_specs

        main_img = (item.get("image_main") or "").strip()
        if not main_img:
            main_img = f"https://raw.githubusercontent.com/marketingmajv/MOne/main/public/images/{slug}/{slug}-01.jpg"
            item["image_main"] = main_img

        gal = item.get("images_gallery")
        if isinstance(gal, str):
            try:
                gal = json.loads(gal)
            except Exception:
                gal = []
        if not isinstance(gal, list):
            gal = []
        gal = [str(img).strip() for img in gal if img and str(img).strip()]
        if main_img and main_img not in gal:
            gal = [main_img] + gal
        item["images_gallery"] = gal

    return items
