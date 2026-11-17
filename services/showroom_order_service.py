"""
Serviço de Gestão de Ordenação e Configurações de Menu do Showroom MAJ
Persistência híbrida em Supabase (showroom_settings) e arquivos locais (quando graváveis).
Garante sincronização total entre o painel administrativo e a vitrine online na Vercel.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import db
from services.showroom_promo_service import ensure_showroom_settings_schema

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ORDER_FILE = BASE_DIR / "static" / "data" / "models_order.json"
API_ORDER_FILE = BASE_DIR / "api" / "static" / "data" / "models_order.json"
KIOSK_FILE = BASE_DIR / "static" / "data" / "models_kiosk.json"
API_KIOSK_FILE = BASE_DIR / "api" / "static" / "data" / "models_kiosk.json"

DEFAULT_MENU_CONFIG: Dict[str, Any] = {
    "mode": "category",
    "category_order": ["Scooter", "Bike"],
    "order": [],
    "category_items": {
        "Scooter": [],
        "Bike": []
    }
}

DEFAULT_KIOSK_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "interval_seconds": 30,
    "auto_pause_seconds": 45,
    "transition_effect": "slide_apple",
}


def _db_get_setting(key: str) -> Optional[str]:
    """Recupera valor bruto da tabela showroom_settings no Supabase."""
    ensure_showroom_settings_schema()
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = "SELECT value FROM showroom_settings WHERE key = %s" if is_pg else "SELECT value FROM showroom_settings WHERE key = ?"
            row = conn.execute(sql, (key,)).fetchone()
            if row:
                return row["value"] if isinstance(row, dict) else row[0]
    except Exception as e:
        logger.debug("Aviso ao ler %s de showroom_settings: %s", key, e)
    return None


def _db_set_setting(key: str, val_str: str) -> None:
    """Persiste valor na tabela showroom_settings no Supabase."""
    ensure_showroom_settings_schema()
    try:
        with db() as conn:
            is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
            sql = (
                "INSERT INTO showroom_settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP"
                if is_pg else
                "INSERT OR REPLACE INTO showroom_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)"
            )
            conn.execute(sql, (key, val_str))
            conn.commit()
    except Exception as e:
        logger.warning("Aviso ao gravar %s em showroom_settings: %s", key, e)


def load_menu_config() -> Dict[str, Any]:
    """Carrega configuração de modo de menu e ordenação com prioridade ao Supabase."""
    raw_db = _db_get_setting("menu_config")
    if raw_db:
        try:
            data = json.loads(raw_db)
            if isinstance(data, dict):
                cfg = dict(DEFAULT_MENU_CONFIG)
                cfg.update(data)
                return cfg
        except Exception as e:
            logger.warning("Erro ao decodificar menu_config do Supabase: %s", e)

    for p in [ORDER_FILE, API_ORDER_FILE]:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cfg = dict(DEFAULT_MENU_CONFIG)
                        cfg.update(data)
                        return cfg
                    elif isinstance(data, list):
                        cfg = dict(DEFAULT_MENU_CONFIG)
                        cfg["order"] = [str(s).strip().lower() for s in data if str(s).strip()]
                        return cfg
            except Exception as e:
                logger.warning(f"Erro ao ler {p}: {e}")
    return dict(DEFAULT_MENU_CONFIG)


def load_models_order() -> List[str]:
    """Retorna lista de slugs ordenada (retrocompatibilidade)."""
    return load_menu_config().get("order", [])


def save_menu_config(config: Any) -> bool:
    """Salva configurações de menu e ordenação no Supabase e em disco."""
    if isinstance(config, list):
        cfg = dict(DEFAULT_MENU_CONFIG)
        cfg["order"] = [str(s).strip().lower() for s in config if str(s).strip()]
    elif isinstance(config, dict):
        cfg = dict(DEFAULT_MENU_CONFIG)
        cfg.update(config)
        cfg["mode"] = "free" if config.get("mode") == "free" else "category"
        if "category_order" in config and isinstance(config["category_order"], list):
            cfg["category_order"] = [str(c).strip() for c in config["category_order"] if str(c).strip()]
        if "order" in config and isinstance(config["order"], list):
            cfg["order"] = [str(s).strip().lower() for s in config["order"] if str(s).strip()]
    else:
        return False

    cfg["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # 1. Salvar no Supabase (produção Vercel)
    _db_set_setting("menu_config", json.dumps(cfg, ensure_ascii=False))

    # 2. Salvar nos arquivos locais quando graváveis
    for p in [ORDER_FILE, API_ORDER_FILE]:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        except Exception as e:
            logger.debug(f"Aviso ao salvar ordem em {p}: {e}")

    # 3. Invalidar cache em memória
    try:
        import services.maj_models_sync_service as mms
        mms._memory_cache = None
        mms._last_sync_time = 0
    except Exception:
        pass

    return True


def save_models_order(order_slugs: List[str]) -> bool:
    """Salva a ordem customizada dos modelos."""
    return save_menu_config(order_slugs)


def load_kiosk_settings() -> Dict[str, Any]:
    """Carrega as configurações do Modo TV / Kiosk da vitrine."""
    raw_db = _db_get_setting("kiosk_settings")
    if raw_db:
        try:
            data = json.loads(raw_db)
            if isinstance(data, dict):
                merged = dict(DEFAULT_KIOSK_SETTINGS)
                merged.update(data)
                return merged
        except Exception as e:
            logger.warning("Erro ao decodificar kiosk_settings do Supabase: %s", e)

    for p in [KIOSK_FILE, API_KIOSK_FILE]:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        merged = dict(DEFAULT_KIOSK_SETTINGS)
                        merged.update(data)
                        return merged
            except Exception as e:
                logger.warning(f"Erro ao ler {p}: {e}")
    return dict(DEFAULT_KIOSK_SETTINGS)


def save_kiosk_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Salva as configurações do Modo TV / Kiosk no Supabase e em disco."""
    curr = load_kiosk_settings()
    curr.update({
        "enabled": bool(settings.get("enabled", curr.get("enabled", True))),
        "interval_seconds": max(5, min(300, int(settings.get("interval_seconds", curr.get("interval_seconds", 30))))),
        "auto_pause_seconds": max(10, min(300, int(settings.get("auto_pause_seconds", curr.get("auto_pause_seconds", 45))))),
        "transition_effect": str(settings.get("transition_effect", curr.get("transition_effect", "slide_apple"))),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    _db_set_setting("kiosk_settings", json.dumps(curr, ensure_ascii=False))

    for p in [KIOSK_FILE, API_KIOSK_FILE]:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(curr, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        except Exception as e:
            logger.debug(f"Aviso ao salvar kiosk settings em {p}: {e}")
    return curr


def apply_model_ordering(models_list: List[Dict[str, Any]], menu_cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Aplica ordenação determinística (modo livre ou por categoria) à lista de modelos."""
    if menu_cfg is None:
        menu_cfg = load_menu_config()

    mode = menu_cfg.get("mode", "category")
    cat_order_list = menu_cfg.get("category_order") or ["Scooter", "Bike"]
    cat_order_map = {cat.strip().lower(): idx + 1 for idx, cat in enumerate(cat_order_list)}
    custom_order = menu_cfg.get("order", [])
    order_map = {str(slug).strip().lower(): idx for idx, slug in enumerate(custom_order) if str(slug).strip()}

    if mode == "free" and custom_order:
        models_list.sort(key=lambda x: (
            order_map.get((x.get("slug") or "").strip().lower(), 999),
            (x.get("modelo") or "").lower()
        ))
    elif custom_order:
        models_list.sort(key=lambda x: (
            cat_order_map.get((x.get("categoria") or "").strip().lower(), 99),
            order_map.get((x.get("slug") or "").strip().lower(), 900),
            (x.get("modelo") or "").lower()
        ))
    else:
        models_list.sort(key=lambda x: (
            cat_order_map.get((x.get("categoria") or "").strip().lower(), 99),
            (x.get("modelo") or "").lower()
        ))

    return models_list

