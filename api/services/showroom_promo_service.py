"""
Serviço de Gestão da Promoção Black November no Showroom MAJ (services/showroom_promo_service.py)
Gerencia a persistência de status, imagem e chamadas do banner da Black November.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROMO_BANNER_FILE = BASE_DIR / "static" / "data" / "models_promo_banner.json"
API_PROMO_BANNER_FILE = BASE_DIR / "api" / "static" / "data" / "models_promo_banner.json"

DEFAULT_PROMO_BANNER_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "banner_image": "",
    "ticker_height": 35,
    "container_height": 210,
    "sticky_top": False,
    "ticker_speed": 24,
    "ticker_color": "#00e599",
    "tag_text": "BLACK NOVEMBER MAJ",
    "ticker_text": "⚡ BLACK NOVEMBER MAJ • ATÉ 50% OFF • PARCELAMENTO EM ATÉ 18X • PRONTA ENTREGA • GARANTIA OFICIAL DE FÁBRICA",
    "headline": "A MAIOR QUEIMA DE ESTOQUE DE MOBILIDADE ELÉTRICA",
    "subheadline": "Condições exclusivas de fábrica com até 50% OFF e parcelamento facilitado em até 18X.",
    "highlight_1": "🔥 Até 50% OFF",
    "highlight_2": "💳 Em até 18X",
    "cta_text": "Garantir Condição Especial",
    "cta_url": "https://wa.me/5527996051538?text=Ol%C3%A1%21+Vim+pelo+Showroom+e+quero+aproveitar+as+condi%C3%A7%C3%B5es+da+Black+November+MAJ%21",
    "updated_at": "",
}


def load_promo_banner_settings() -> Dict[str, Any]:
    """Carrega as configurações do Banner da Black November do Showroom."""
    for p in [PROMO_BANNER_FILE, API_PROMO_BANNER_FILE]:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        merged = dict(DEFAULT_PROMO_BANNER_SETTINGS)
                        merged.update(data)
                        return merged
            except Exception as e:
                logger.warning("Erro ao ler configurações do banner promocional em %s: %s", p, e)
    return dict(DEFAULT_PROMO_BANNER_SETTINGS)


def save_promo_banner_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Salva as configurações do Banner da Black November nos arquivos de dados."""
    curr = load_promo_banner_settings()

    # Sanitização com clamp estrito de UX para a altura da faixa (20px a 50px)
    raw_th = settings.get("ticker_height", curr.get("ticker_height", 35))
    try:
        th = max(20, min(50, int(raw_th)))
    except (ValueError, TypeError):
        th = 35

    # Sanitização com clamp da altura total do container (160px a 360px, padrão 210px)
    raw_ch = settings.get("container_height", curr.get("container_height", 210))
    try:
        ch = max(160, min(360, int(raw_ch)))
    except (ValueError, TypeError):
        ch = 210

    # Opção de congelar no topo (sticky top)
    sticky_top = bool(settings.get("sticky_top", curr.get("sticky_top", False)))

    # Sanitização da velocidade de rolagem (10s a 60s, padrão 24s)
    raw_spd = settings.get("ticker_speed", curr.get("ticker_speed", 24))
    try:
        spd = max(10, min(60, int(raw_spd)))
    except (ValueError, TypeError):
        spd = 24

    # Sanitização da cor da letra (hexadecimal válido)
    color = str(settings.get("ticker_color", curr.get("ticker_color", "#00e599"))).strip()
    if not (color.startswith("#") and len(color) in (4, 7)):
        color = "#00e599"

    curr.update({
        "enabled": bool(settings.get("enabled", curr.get("enabled", True))),
        "banner_image": str(settings.get("banner_image") or "").strip(),
        "ticker_height": th,
        "container_height": ch,
        "sticky_top": sticky_top,
        "ticker_speed": spd,
        "ticker_color": color,
        "tag_text": str(settings.get("tag_text") or DEFAULT_PROMO_BANNER_SETTINGS["tag_text"]).strip(),
        "ticker_text": str(settings.get("ticker_text") or DEFAULT_PROMO_BANNER_SETTINGS["ticker_text"]).strip(),
        "headline": str(settings.get("headline") or DEFAULT_PROMO_BANNER_SETTINGS["headline"]).strip(),
        "subheadline": str(settings.get("subheadline") or DEFAULT_PROMO_BANNER_SETTINGS["subheadline"]).strip(),
        "highlight_1": str(settings.get("highlight_1", curr.get("highlight_1", DEFAULT_PROMO_BANNER_SETTINGS["highlight_1"])) or "").strip(),
        "highlight_2": str(settings.get("highlight_2", curr.get("highlight_2", DEFAULT_PROMO_BANNER_SETTINGS["highlight_2"])) or "").strip(),
        "cta_text": str(settings.get("cta_text") or DEFAULT_PROMO_BANNER_SETTINGS["cta_text"]).strip(),
        "cta_url": str(settings.get("cta_url") or DEFAULT_PROMO_BANNER_SETTINGS["cta_url"]).strip(),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    for p in [PROMO_BANNER_FILE, API_PROMO_BANNER_FILE]:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(curr, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Erro ao salvar banner promocional em %s: %s", p, e)

    return curr
