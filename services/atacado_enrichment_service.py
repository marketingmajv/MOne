"""
M-One Atacado Enrichment Service (services/atacado_enrichment_service.py)
Enriquecimento técnico e comercial dos produtos de Atacado B2B:
Cálculo de margens estimadas, trilhas de produto, diferenciais de catálogo, faixas escalonadas de preço e mídias.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

CAMPEOES_SLUGS = {"max-12", "flow-one", "m2", "classic-1000", "gp1000", "classic"}
ENTRADA_SLUGS = {"v8-mini-ultra", "ride-on", "v20-ultra", "v80-pro", "m9-pro", "m50-pro"}
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
    "v80-pro": "🛡️ Quadro Reforçado Ergonômico",
    "jm-125": "🚀 Super Motor 3000W",
    "nova": "🔑 Partida Keyless + Alarme",
    "x15-pro": "🏎️ Duplo Amortecedor Reforçado",
    "mantis": "🏁 Chassi Esportivo Firme",
    "classic-1000": "🎁 Baú Retrô Incluso",
    "v8-mini-ultra": "🚲 Quadro Baixo Step-Through",
    "rz-110": "💡 Faróis Ultra Potentes",
    "m50-pro": "✈️ Alumínio Aeroespacial",
    "db-zero": "🛸 Design Futurista Silver Black",
    "sport-701-short": "🏁 Suspensão Invertida Esportiva",
    "q8": "🧺 Quadro Rebaixado Conforto",
}

WH_LOOKUP = {
    "flow-one": 1440, "m2": 1440, "gp1000": 2160, "vittoria": 1440, "classic-1000": 1440,
    "rz-110": 1440, "max-12": 1200, "nova": 1200, "x15-pro": 1200, "db-zero": 1200,
    "v20-ultra": 960, "ride-on": 960, "m9-pro": 960, "v80-pro": 960, "v8-mini-ultra": 720, "m50-pro": 960,
    "mantis": 1200, "jm-125": 1440
}


def enrich_atacado_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enriquece itens com margem estimada, enquadramento em trilhas, faixas escalonadas de preço, métricas Wh e diferenciais técnicos."""
    for item in items:
        slug = (item.get("slug") or "").lower().strip()
        p_out = float(item.get("price_outlet") or 0)
        p_orig = float(item.get("price_original") or 0)
        
        # Patamares de desconto escalonado por volume
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

        # Mapeamento do tipo de veículo (Scooter vs Bike)
        BIKE_SLUGS = {"m9-pro", "m50-pro", "v20-ultra", "v8-mini-ultra", "v80-pro"}
        if slug in BIKE_SLUGS or "bike" in (item.get("category") or "").lower() or "bike" in slug:
            item["vehicle_type"] = "bike"
            item["category_display"] = "Bike Elétrica"
        else:
            item["vehicle_type"] = "scooter"
            item["category_display"] = "Scooter Elétrica"

        item["is_best_seller"] = bool(item.get("is_best_seller"))

        # Garantir fotos limpas (evitar base64 pesado no DOM) e galeria íntegra
        main_img = item.get("image_main")
        if not main_img or str(main_img).startswith("data:"):
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
        # Limpar fotos base64 da galeria substituindo pela foto principal limpa
        gal = [img for img in gal if img and not str(img).startswith("data:")]
        if main_img and main_img not in gal:
            gal = [main_img] + gal
        item["images_gallery"] = gal

    return items
