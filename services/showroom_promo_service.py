"""
Serviço de Gestão da Promoção Black November no Showroom MAJ (services/showroom_promo_service.py)
Gerencia a persistência de status, imagem e chamadas do banner da Black November.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from database import db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROMO_BANNER_FILE = BASE_DIR / "static" / "data" / "models_promo_banner.json"
API_PROMO_BANNER_FILE = BASE_DIR / "api" / "static" / "data" / "models_promo_banner.json"

_schema_ensured = False


def ensure_showroom_settings_schema():
    """Garante a existência da tabela showroom_settings no Supabase/PostgreSQL."""
    global _schema_ensured
    if _schema_ensured:
        return
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = """
            CREATE TABLE IF NOT EXISTS showroom_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """ if is_pg else """
            CREATE TABLE IF NOT EXISTS showroom_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            conn.execute(sql)
            conn.commit()
            _schema_ensured = True
    except Exception as e:
        logger.warning("Erro ao garantir schema showroom_settings: %s", e)


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
    """Carrega as configurações do Banner da Black November do Showroom a partir do Supabase."""
    ensure_showroom_settings_schema()
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = "SELECT value FROM showroom_settings WHERE key = %s" if is_pg else "SELECT value FROM showroom_settings WHERE key = ?"
            row = conn.execute(sql, ("promo_banner",)).fetchone()
            if row:
                raw_val = row["value"] if isinstance(row, dict) else row[0]
                if raw_val:
                    data = json.loads(raw_val)
                    if isinstance(data, dict):
                        merged = dict(DEFAULT_PROMO_BANNER_SETTINGS)
                        merged.update(data)
                        return merged
    except Exception as e:
        logger.warning("Erro ao carregar promo_banner do banco de dados: %s", e)

    # Fallback para arquivos locais se não houver registro no banco ainda
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
    """Salva as configurações do Banner da Black November no banco de dados Supabase e arquivos locais."""
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

    # Persistência oficial no Supabase (PostgreSQL IPv4)
    ensure_showroom_settings_schema()
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            val_json = json.dumps(curr, ensure_ascii=False)
            if is_pg:
                conn.execute(
                    """
                    INSERT INTO showroom_settings (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                    """,
                    ("promo_banner", val_json)
                )
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO showroom_settings (key, value) VALUES (?, ?)",
                    ("promo_banner", val_json)
                )
            conn.commit()
    except Exception as e:
        logger.error("Erro ao salvar promo_banner no banco de dados Supabase: %s", e)

    # Backup nos arquivos locais
    for p in [PROMO_BANNER_FILE, API_PROMO_BANNER_FILE]:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(curr, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug("Não foi possível salvar backup local em %s: %s", p, e)

    return curr


def toggle_promo_banner_status(enabled: Optional[bool] = None) -> bool:
    """Alterna imediatamente o status de exibição do banner no Showroom."""
    curr = load_promo_banner_settings()
    if enabled is None:
        curr["enabled"] = not curr.get("enabled", True)
    else:
        curr["enabled"] = bool(enabled)
    save_promo_banner_settings(curr)
    return curr["enabled"]
