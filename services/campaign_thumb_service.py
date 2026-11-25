"""
M-One Campaign Thumb Service (services/campaign_thumb_service.py)
Motor de Agendamento 24/7 e Resolução Dinâmica de Capas & Thumbs Promocionais Multicanal.
Conecta o Showroom aos canais Outlet e Atacado com cascata inteligente de fallback.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.showroom_promo_service import ensure_showroom_settings_schema

logger = logging.getLogger(__name__)

DEFAULT_CAMPAIGN_SETTINGS: Dict[str, Any] = {
    "campaign_name": "Black November MAJ",
    "schedule_enabled": False,
    "start_at": "",
    "end_at": "",
    "manual_override": None,  # None | "promocional" | "atemporal"
    "updated_at": "",
}

DEFAULT_CHANNEL_BANNER_MODES: Dict[str, str] = {
    "showroom": "atemporal",
    "atacado": "atemporal",
    "outlet": "atemporal",
}


def get_channel_banner_modes() -> Dict[str, str]:
    """Carrega os modos de banners ativos por canal ('showroom', 'atacado', 'outlet')."""
    ensure_showroom_settings_schema()
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = "SELECT value FROM showroom_settings WHERE key = %s" if is_pg else "SELECT value FROM showroom_settings WHERE key = ?"
            row = conn.execute(sql, ("channel_banner_modes",)).fetchone()
            if row:
                raw_val = row["value"] if isinstance(row, dict) else row[0]
                if raw_val:
                    data = json.loads(raw_val)
                    if isinstance(data, dict):
                        merged = dict(DEFAULT_CHANNEL_BANNER_MODES)
                        for k in ("showroom", "atacado", "outlet"):
                            if data.get(k) in ("promocional", "atemporal"):
                                merged[k] = data[k]
                        return merged
    except Exception as e:
        logger.warning("Aviso ao carregar channel_banner_modes do banco: %s", e)

    # Fallback: herda do global_image_mode do showroom
    try:
        from services.showroom_crud_service import get_global_image_mode
        leg_mode = get_global_image_mode()
        if leg_mode in ("promocional", "atemporal"):
            return {k: leg_mode for k in DEFAULT_CHANNEL_BANNER_MODES}
    except Exception:
        pass

    return dict(DEFAULT_CHANNEL_BANNER_MODES)


def set_channel_banner_mode(channel: str, mode: str) -> Dict[str, str]:
    """Salva o modo ('promocional' ou 'atemporal') de um canal específico ou de todos ('all')."""
    ensure_showroom_settings_schema()
    clean_mode = "promocional" if mode == "promocional" else "atemporal"
    current = get_channel_banner_modes()

    target_chans = ["showroom", "atacado", "outlet"] if channel == "all" else [channel.lower()]
    for ch in target_chans:
        if ch in current:
            current[ch] = clean_mode

    # Sincroniza Showroom no showroom_crud_service se afetado
    if "showroom" in target_chans:
        try:
            from services.showroom_crud_service import set_global_image_mode
            set_global_image_mode(clean_mode)
        except Exception as e:
            logger.debug("Aviso ao sincronizar showroom_crud_service: %s", e)

    val_str = json.dumps(current, ensure_ascii=False)
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = (
                "INSERT INTO showroom_settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP"
                if is_pg else
                "INSERT OR REPLACE INTO showroom_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)"
            )
            conn.execute(sql, ("channel_banner_modes", val_str))
            conn.commit()
    except Exception as e:
        logger.warning("Aviso ao salvar channel_banner_modes em showroom_settings: %s", e)

    return current

SLUG_ALIASES: Dict[str, str] = {
    "v8-mini-ultra": "v8-mini",
    "v8-mini": "v8-mini-ultra",
}


def _norm_text(val: Any) -> str:
    txt = str(val or "").strip().lower()
    for pat, rep in [(r"[àáâãäå]", "a"), (r"[èéêë]", "e"), (r"[ìíîï]", "i"), (r"[òóôõö]", "o"), (r"[ùúûü]", "u"), (r"[ç]", "c")]:
        txt = re.sub(pat, rep, txt)
    return re.sub(r"[^a-z0-9]+", "", txt)


def get_campaign_schedule() -> Dict[str, Any]:
    """Carrega as configurações de agendamento e modo da campanha promocional."""
    ensure_showroom_settings_schema()
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = "SELECT value FROM showroom_settings WHERE key = %s" if is_pg else "SELECT value FROM showroom_settings WHERE key = ?"
            row = conn.execute(sql, ("campaign_schedule",)).fetchone()
            if row:
                raw_val = row["value"] if isinstance(row, dict) else row[0]
                if raw_val:
                    data = json.loads(raw_val)
                    if isinstance(data, dict):
                        merged = dict(DEFAULT_CAMPAIGN_SETTINGS)
                        merged.update(data)
                        return merged
    except Exception as e:
        logger.warning("Aviso ao carregar campaign_schedule do banco: %s", e)

    return dict(DEFAULT_CAMPAIGN_SETTINGS)


def save_campaign_schedule(data: Dict[str, Any]) -> Dict[str, Any]:
    """Persiste as configurações da campanha e agendador no Supabase/PostgreSQL."""
    ensure_showroom_settings_schema()
    current = get_campaign_schedule()
    current.update({
        "campaign_name": (data.get("campaign_name") or current.get("campaign_name", "Campanha MAJ")).strip(),
        "schedule_enabled": bool(data.get("schedule_enabled")),
        "start_at": (data.get("start_at") or "").strip(),
        "end_at": (data.get("end_at") or "").strip(),
        "manual_override": data.get("manual_override") if data.get("manual_override") in ["promocional", "atemporal"] else None,
        "updated_at": datetime.now().isoformat(),
    })

    val_str = json.dumps(current, ensure_ascii=False)
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = (
                "INSERT INTO showroom_settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP"
                if is_pg else
                "INSERT OR REPLACE INTO showroom_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)"
            )
            conn.execute(sql, ("campaign_schedule", val_str))
            conn.commit()
    except Exception as e:
        logger.warning("Aviso ao salvar campaign_schedule em showroom_settings: %s", e)

    # Mantém coerência com o global_image_mode legado
    _, effective_mode, _ = is_campaign_active_now(current)
    try:
        from services.showroom_crud_service import set_global_image_mode
        set_global_image_mode(effective_mode)
    except Exception as e:
        logger.debug("Aviso ao sincronizar global_image_mode legado: %s", e)

    return current


def is_campaign_active_now(settings: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Avalia se o modo promocional está ativo neste instante.
    Retorna (is_promo_active, active_mode_str, settings_dict).
    """
    cfg = settings or get_campaign_schedule()

    # 1. Prioridade: Sobrescrição manual forçada
    manual = cfg.get("manual_override")
    if manual in ["promocional", "atemporal"]:
        return (manual == "promocional", manual, cfg)

    # 2. Avaliação de Agendamento por Janela de Datas/Horas
    if cfg.get("schedule_enabled") and cfg.get("start_at") and cfg.get("end_at"):
        try:
            now = datetime.now()
            start = datetime.fromisoformat(str(cfg["start_at"]).strip())
            end = datetime.fromisoformat(str(cfg["end_at"]).strip())
            if start <= now <= end:
                return (True, "promocional", cfg)
            else:
                return (False, "atemporal", cfg)
        except Exception as e:
            logger.warning("Falha ao analisar datas do agendamento de campanha: %s", e)

    # 3. Fallback: Consulta o global_image_mode do Showroom
    try:
        from services.showroom_crud_service import get_global_image_mode
        legacy_mode = get_global_image_mode()
        return (legacy_mode == "promocional", legacy_mode, cfg)
    except Exception:
        return (False, "atemporal", cfg)


def build_showroom_lookup() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Constrói índices rápidos de busca por slug e nome normalizado dos modelos do Showroom."""
    from services.maj_models_sync_service import get_all_models
    models = get_all_models(include_inactive=True)

    by_slug: Dict[str, Dict[str, Any]] = {}
    by_norm: Dict[str, Dict[str, Any]] = {}

    for m in models:
        s = str(m.get("slug") or "").strip().lower()
        name = str(m.get("modelo") or "").strip()
        if s:
            by_slug[s] = m
            if s in SLUG_ALIASES:
                by_slug[SLUG_ALIASES[s]] = m
        if name:
            by_norm[_norm_text(name)] = m

    return by_slug, by_norm


def resolve_effective_thumb(
    item: Dict[str, Any],
    by_slug: Dict[str, Dict[str, Any]],
    by_norm: Dict[str, Dict[str, Any]],
    active_mode: str = "atemporal"
) -> Tuple[str, bool, bool]:
    """
    Cascata Inteligente de Fallback:
    1. Se Modo Promo -> Capa Promo do Showroom (se existir banner promocional dedicado).
    2. Imagem nativa (image_main) cadastrada no canal (se existir).
    3. Fallback inteligente -> Capa Atemporal do Showroom / Cutout (se existir e não houver foto nativa).
    Retorna: (url_resolvida, is_promo_thumb, is_inherited_from_showroom).
    """
    raw_slug = str(item.get("slug") or "").strip().lower()
    raw_name = str(item.get("name") or item.get("modelo") or "").strip()
    norm_name = _norm_text(raw_name)

    sh_model = by_slug.get(raw_slug) or by_norm.get(norm_name)
    if not sh_model and raw_slug in SLUG_ALIASES:
        sh_model = by_slug.get(SLUG_ALIASES[raw_slug])

    native_img = str(item.get("image_main") or "").strip()

    if sh_model:
        banner_promo = str(sh_model.get("promo_banner_image") or "").strip()
        banner_atemp = str(sh_model.get("banner_image") or sh_model.get("cutout_image") or "").strip()

        # 1. Se estiver em campanha promocional ativa e o showroom tiver capa promocional dedicada
        if active_mode == "promocional" and banner_promo:
            return (banner_promo, True, True)

        # 2. Se o item possui foto própria cadastrada/customizada no canal, respeita a foto nativa
        if native_img:
            return (native_img, False, False)

        # 3. Fallback para showroom somente quando não houver imagem nativa
        if banner_atemp:
            return (banner_atemp, False, True)

    return (native_img, False, False)


def enrich_items_with_effective_thumbs(
    items: List[Dict[str, Any]],
    channel: str = "generic"
) -> List[Dict[str, Any]]:
    """
    Enriquece a lista de produtos em memória com a thumb resolvida dinamicamente,
    sem alterar fisicamente o banco de dados nem quebrar templates legados.
    Respeita o modo independente configurado para cada canal (showroom, atacado, outlet).
    """
    if not items:
        return items

    try:
        by_slug, by_norm = build_showroom_lookup()
        c_modes = get_channel_banner_modes()
        chan_key = str(channel or "").strip().lower()

        if chan_key in c_modes:
            active_mode = c_modes[chan_key]
        else:
            _, active_mode, _ = is_campaign_active_now()

        for it in items:
            thumb_url, is_promo, is_inherited = resolve_effective_thumb(it, by_slug, by_norm, active_mode)
            it["effective_thumb"] = thumb_url
            it["is_promo_thumb"] = is_promo
            it["is_inherited_showroom"] = is_inherited
            it["original_image_main"] = it.get("image_main") or ""

            # Substitui suavemente para que todo template (item.image_main) use a capa correta
            if thumb_url:
                it["image_main"] = thumb_url

    except Exception as e:
        logger.error("Erro ao enriquecer thumbs promocionais (%s): %s", channel, e, exc_info=True)

    return items
