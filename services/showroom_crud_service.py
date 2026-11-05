"""
Serviço CRUD e Persistência Soberana dos Modelos do Showroom MAJ
Permite cadastro e edição completa de veículos com foco nos Banners Panorâmicos
Widescreen (16:9 de estúdio) de Topo: Atemporal vs Promocional de Campanha.
Garante persistência híbrida: alterações locais/banco nunca são sobrescritas pela planilha.
"""

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from PIL import Image
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from database import db
from services.showroom_promo_service import ensure_showroom_settings_schema

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OVERRIDES_FILE = BASE_DIR / "static" / "data" / "model_overrides.json"
API_OVERRIDES_FILE = BASE_DIR / "api" / "static" / "data" / "model_overrides.json"
IMAGE_MODE_FILE = BASE_DIR / "static" / "data" / "models_image_mode.json"
API_IMAGE_MODE_FILE = BASE_DIR / "api" / "static" / "data" / "models_image_mode.json"
CACHE_FILE = BASE_DIR / "static" / "data" / "maj_models.json"
API_CACHE_FILE = BASE_DIR / "api" / "static" / "data" / "maj_models.json"

BANNER_DIR_STATIC = BASE_DIR / "static" / "images" / "models" / "banners"
BANNER_DIR_PUBLIC = BASE_DIR / "public" / "images" / "models" / "banners"
CUTOUT_DIR_STATIC = BASE_DIR / "static" / "images" / "models" / "cutouts"
CUTOUT_DIR_PUBLIC = BASE_DIR / "public" / "images" / "models" / "cutouts"


def slugify(name: str) -> str:
    """Gera slug limpo e padronizado a partir do nome."""
    slug = name.lower().strip()
    for pat, rep in [(r"[àáâãäå]", "a"), (r"[èéêë]", "e"), (r"[ìíîï]", "i"), (r"[òóôõö]", "o"), (r"[ùúûü]", "u"), (r"[ç]", "c")]:
        slug = re.sub(pat, rep, slug)
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def _db_get_showroom_setting(key: str) -> Optional[str]:
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


def _db_set_showroom_setting(key: str, val_str: str) -> None:
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


def get_global_image_mode() -> str:
    """Retorna o modo global de banners ('atemporal' ou 'promocional')."""
    raw_db = _db_get_showroom_setting("global_image_mode")
    if raw_db:
        try:
            data = json.loads(raw_db)
            mode = data.get("mode", "atemporal") if isinstance(data, dict) else str(raw_db)
            if mode in ["atemporal", "promocional"]:
                return mode
        except Exception:
            if raw_db in ["atemporal", "promocional"]:
                return raw_db
    for path in [IMAGE_MODE_FILE, API_IMAGE_MODE_FILE]:
        if path.is_file():
            try:
                mode = json.loads(path.read_text(encoding="utf-8")).get("mode", "atemporal")
                if mode in ["atemporal", "promocional"]:
                    return mode
            except Exception:
                pass
    return "atemporal"


def _refresh_local_models_cache() -> None:
    """Atualiza o cache local/memória de modelos instantaneamente sem bloquear na rede do Google Sheets."""
    import services.maj_models_sync_service as mms
    if mms._memory_cache and isinstance(mms._memory_cache, dict):
        all_m = merge_showroom_overrides(list(mms._memory_cache.get("all_models") or mms._memory_cache.get("models") or []))
        active_m = [m for m in all_m if m.get("is_active", True)]
        mms._memory_cache["all_models"] = all_m
        mms._memory_cache["models"] = active_m
        mms._memory_cache["total_models"] = len(active_m)
        for cache_path in [CACHE_FILE, API_CACHE_FILE]:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(mms._memory_cache, f, ensure_ascii=False, indent=2)
            except OSError:
                pass


def set_global_image_mode(mode: str) -> str:
    """Aplica em massa o modo de banners ('atemporal' ou 'promocional') a todos os modelos, mantendo edição individual livre."""
    clean_mode = "promocional" if mode == "promocional" else "atemporal"
    payload = {"mode": clean_mode}
    _db_set_showroom_setting("global_image_mode", json.dumps(payload, ensure_ascii=False))
    for path in [IMAGE_MODE_FILE, API_IMAGE_MODE_FILE]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        except Exception as e:
            logger.debug(f"Aviso ao salvar modo global em {path}: {e}")

    from services.maj_models_sync_service import get_all_models
    overrides = load_model_overrides()
    for m in get_all_models(include_inactive=True):
        s = m.get("slug")
        if s:
            ov = overrides.setdefault(s, {"slug": s, "modelo": m.get("modelo", s), "categoria": m.get("categoria", "Scooter")})
            ov["active_banner_type"] = clean_mode
            ov["active_image_type"] = clean_mode
    for s, ov in overrides.items():
        if isinstance(ov, dict):
            ov["active_banner_type"] = clean_mode
            ov["active_image_type"] = clean_mode
    save_model_overrides(overrides)
    _refresh_local_models_cache()
    return clean_mode


def toggle_model_banner_type(slug: str, target_type: Optional[str] = None) -> Dict[str, Any]:
    """Alterna individualmente o banner ativo ('atemporal' vs 'promocional') de um modelo específico."""
    from services.maj_models_sync_service import get_all_models
    clean_slug = slug.strip().lower()
    models = get_all_models(include_inactive=True)
    target = next((m for m in models if m.get("slug") == clean_slug), None)
    if not target:
        raise ValueError(f"Modelo '{clean_slug}' não encontrado.")

    banners = resolve_disk_banners(clean_slug)
    overrides = load_model_overrides()
    ov = overrides.setdefault(clean_slug, {"slug": clean_slug, "modelo": target.get("modelo", clean_slug), "categoria": target.get("categoria", "Scooter")})

    promo_url = ov.get("promo_banner_image") or target.get("promo_banner_image") or banners["promocional"] or ""
    atemp_url = ov.get("banner_image") or target.get("banner_image") or banners["atemporal"] or ""
    curr_type = ov.get("active_banner_type") or target.get("active_banner_type") or "atemporal"
    new_type = target_type if target_type in ("atemporal", "promocional") else ("atemporal" if curr_type == "promocional" else "promocional")

    if new_type == "promocional" and not promo_url:
        return {
            "status": "missing_promo",
            "slug": clean_slug,
            "has_promo_banner": False,
            "active_banner_type": "atemporal",
            "effective_banner_type": "atemporal",
            "display_image": atemp_url,
            "message": f"O modelo {target.get('modelo', clean_slug)} ainda não possui o 2º Banner Promocional cadastrado.",
        }

    ov["active_banner_type"] = new_type
    ov["active_image_type"] = new_type
    effective_img = promo_url if (new_type == "promocional" and promo_url) else atemp_url
    ov["hero_image"] = effective_img
    ov["display_image"] = effective_img
    save_model_overrides(overrides)
    _refresh_local_models_cache()
    return {
        "status": "success",
        "slug": clean_slug,
        "has_promo_banner": bool(promo_url),
        "active_banner_type": new_type,
        "effective_banner_type": "promocional" if (new_type == "promocional" and promo_url) else "atemporal",
        "display_image": effective_img,
    }


def resolve_disk_banners(slug: str) -> Dict[str, str]:
    """Detecta automaticamente os banners de estúdio (16:9) atemporal e promocional no disco."""
    clean_slug = slug.strip().lower()
    atemporal, promocional = "", ""
    for folder in [BANNER_DIR_PUBLIC, BANNER_DIR_STATIC]:
        for c in [f"{clean_slug}-banner.webp", f"{clean_slug}-banner-2x.webp", f"{clean_slug}-banner.jpg", f"{clean_slug}.webp"]:
            if not atemporal and (folder / c).is_file():
                atemporal = f"/public/images/models/banners/{c}"
        for c in [f"{clean_slug}-banner-promo.webp", f"{clean_slug}-promo.webp", f"{clean_slug}-promo.jpg"]:
            if not promocional and (folder / c).is_file():
                promocional = f"/public/images/models/banners/{c}"
    return {"atemporal": atemporal, "promocional": promocional}


def load_model_overrides() -> Dict[str, Dict[str, Any]]:
    """Carrega os overrides salvos no disco e mescla com a persistência em banco (Supabase)."""
    merged: Dict[str, Dict[str, Any]] = {}
    for path in [OVERRIDES_FILE, API_OVERRIDES_FILE]:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        merged.update(data)
                        break
            except Exception as e:
                logger.warning(f"Erro ao ler overrides de {path}: {e}")

    raw_db = _db_get_showroom_setting("model_overrides")
    if raw_db:
        try:
            db_data = json.loads(raw_db)
            if isinstance(db_data, dict):
                for k, v in db_data.items():
                    if isinstance(v, dict) and isinstance(merged.get(k), dict):
                        merged[k].update(v)
                    else:
                        merged[k] = v
        except Exception as e:
            logger.warning("Erro ao fazer parse de model_overrides do banco: %s", e)

    return merged


def save_model_overrides(overrides: Dict[str, Dict[str, Any]]) -> None:
    """Salva os overrides no Supabase (produção Vercel) e nos arquivos estáticos locais quando graváveis."""
    _db_set_showroom_setting("model_overrides", json.dumps(overrides, ensure_ascii=False))
    for path in [OVERRIDES_FILE, API_OVERRIDES_FILE]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(overrides, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        except Exception as e:
            logger.debug(f"Aviso ao salvar overrides locais em {path}: {e}")


def merge_showroom_overrides(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aplica edições manuais, banners de estúdio e modo global com Soberania Inteligente."""
    overrides = load_model_overrides()
    global_mode = get_global_image_mode()
    models_by_slug = {m.get("slug"): m for m in models if m.get("slug")}

    for slug, override in overrides.items():
        if slug in models_by_slug:
            target = models_by_slug[slug]
            for k in ["categoria", "modelo", "is_active", "banner_image", "promo_banner_image", "hero_image", "cutout_image", "promo_image", "active_image_type", "active_banner_type"]:
                if k in override and override[k] is not None:
                    target[k] = override[k]
            if "metrics" in override:
                target.setdefault("metrics", {}).update(override["metrics"])
            if "sections" in override:
                target.setdefault("sections", {})
                for sec_name, sec_vals in override["sections"].items():
                    target["sections"].setdefault(sec_name, {}).update(sec_vals)
        else:
            models.append(override)
            models_by_slug[slug] = override

    for m in models:
        slug = m.get("slug", "")
        banners = resolve_disk_banners(slug)
        if not m.get("banner_image") and banners["atemporal"]:
            m["banner_image"] = banners["atemporal"]
        if not m.get("promo_banner_image") and banners["promocional"]:
            m["promo_banner_image"] = banners["promocional"]

        has_promo = bool(m.get("promo_banner_image"))
        m["has_promo_banner"] = has_promo
        m_active_type = m.get("active_banner_type") or m.get("active_image_type") or global_mode or "atemporal"
        m["requested_banner_type"] = m_active_type
        effective_type = "promocional" if (m_active_type == "promocional" and has_promo) else "atemporal"

        m["effective_image_type"] = effective_type
        m["effective_banner_type"] = effective_type

        if effective_type == "promocional" and has_promo:
            m["active_banner"] = m["promo_banner_image"]
            m["hero_image"] = m["promo_banner_image"]
            m["display_image"] = m["promo_banner_image"]
        else:
            m["active_banner"] = m.get("banner_image") or banners["atemporal"] or ""
            m["hero_image"] = m["active_banner"] or m.get("cutout_image") or ""
            m["display_image"] = m["active_banner"] or m.get("cutout_image") or ""

    return models


def get_model_full_for_edit(slug: str) -> Optional[Dict[str, Any]]:
    """Retorna dados completos e banners panorâmicos (16:9) para o modal."""
    from services.maj_models_sync_service import get_all_models, normalize_slug
    clean_slug = slug.lower().strip()
    norm_slug = normalize_slug(slug.replace("-", " "))
    alias_candidates = {clean_slug, norm_slug}
    if clean_slug in ("classic", "classic-1000"):
        alias_candidates.add("classic-1000")
    models = get_all_models(include_inactive=True)
    target = next((m for m in models if m.get("slug") in alias_candidates or normalize_slug(m.get("modelo", "")) in alias_candidates), None)
    if not target:
        return None

    banners = resolve_disk_banners(target.get("slug") or clean_slug)
    banner_atemp = target.get("banner_image") or banners["atemporal"] or ""
    banner_promo = target.get("promo_banner_image") or banners["promocional"] or ""

    sections, metrics = target.get("sections", {}), target.get("metrics", {})
    ident, desemp = sections.get("Identificação", {}), sections.get("Desempenho", {})
    bat, est = sections.get("Bateria e autonomia", {}), sections.get("Estrutura e conforto", {})
    com, livre = sections.get("Uso e comercial", {}), sections.get("Texto livre", {})

    return {
        "slug": target.get("slug", ""), "modelo": target.get("modelo", ""),
        "categoria": target.get("categoria", "Scooter"), "is_active": target.get("is_active", True),
        "banner_image": banner_atemp, "promo_banner_image": banner_promo,
        "active_banner_type": target.get("active_banner_type") or target.get("active_image_type", "atemporal"),
        "marca": ident.get("Marca", "MAJ"), "versao_ano": ident.get("Versão / ano", "2026"),
        "codigo_interno": ident.get("Código interno", ""),
        "potencia_nominal_w": metrics.get("potencia_nominal_w") or desemp.get("Potência nominal (W)", ""),
        "velocidade_max_kmh": metrics.get("velocidade_max_kmh") or desemp.get("Velocidade máxima (km/h)", ""),
        "modos_conducao": desemp.get("Modos de condução", "3 níveis"),
        "possui_re": desemp.get("Possui ré?", "Sim"),
        "voltagem_v": metrics.get("voltagem_v") or bat.get("Voltagem (V)", "60v"),
        "capacidade_ah": metrics.get("capacidade_ah") or bat.get("Capacidade (Ah)", "20ah"),
        "capacidade_wh": metrics.get("capacidade_wh") or bat.get("Capacidade (Wh)", "1200Wh"),
        "autonomia_conservadora_km": metrics.get("autonomia_conservadora_km") or bat.get("Autonomia conservadora (km)", ""),
        "autonomia_maxima_km": metrics.get("autonomia_maxima_km") or bat.get("Autonomia máxima estimada (km)", ""),
        "quimica_bateria": metrics.get("quimica_bateria") or bat.get("Química / tipo", "LiFePO₄ (LFP)"),
        "carga_maxima_kg": metrics.get("carga_maxima_kg") or est.get("Carga máxima suportada (kg)", "180"),
        "peso_kg": metrics.get("peso_kg") or est.get("Peso do veículo (kg)", "75"),
        "freios": metrics.get("freios") or est.get("Tipo de freios", "Diant: Hidráulico / Tras: Hidráulico"),
        "suspensao": est.get("Suspensão", "Dupla dianteira e traseira"),
        "aro_pneu": est.get("Aro / Pneu", "Aro 12"),
        "diferencial": metrics.get("diferencial") or com.get("Diferencial", ""),
        "pontos_fortes": metrics.get("pontos_fortes") or com.get("Pontos fortes", ""),
        "descricao_livre": metrics.get("descricao_livre") or livre.get("Descrição livre", ""),
    }


def _save_optimized_banner(file_obj, filename: str) -> str:
    """Converte o banner em WebP otimizado (16:9), tenta gravar em disco local e retorna Data URI resiliente para Vercel."""
    webp_bytes = b""
    mime = "image/webp"
    try:
        file_obj.seek(0)
        img = Image.open(file_obj)
        img = img.convert("RGBA" if img.mode in ("RGBA", "P") else "RGB")
        if img.width > 1600:
            new_h = int(round(img.height * (1600 / img.width)))
            img = img.resize((1600, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=82, method=6)
        webp_bytes = buf.getvalue()
    except Exception as e:
        logger.warning(f"Fallback lendo bytes brutos de banner {filename}: {e}")
        file_obj.seek(0)
        webp_bytes = file_obj.read()
        mime = getattr(file_obj, "mimetype", None) or "image/webp"

    for folder in [BANNER_DIR_STATIC, BANNER_DIR_PUBLIC]:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / filename, "wb") as f:
                f.write(webp_bytes)
        except OSError:
            pass
        except Exception as e:
            logger.debug(f"Aviso ao gravar banner local em {folder / filename}: {e}")

    b64_str = base64.b64encode(webp_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64_str}"


def save_showroom_model(data: Dict[str, Any], banner_atemporal=None, banner_promocional=None) -> Dict[str, Any]:
    """Salva a criação ou edição com foco nos banners de topo (Atemporal vs Promocional)."""
    name = (data.get("modelo") or "").strip()
    if not name:
        raise ValueError("O nome do modelo é obrigatório.")

    slug = (data.get("slug") or "").strip().lower() or slugify(name)
    overrides = load_model_overrides()
    existing_ovr = overrides.get(slug, {}) if isinstance(overrides.get(slug), dict) else {}

    banners = resolve_disk_banners(slug)
    banner_atemp_url = data.get("banner_image") or existing_ovr.get("banner_image") or banners["atemporal"] or ""
    banner_promo_url = data.get("promo_banner_image") or existing_ovr.get("promo_banner_image") or banners["promocional"] or ""

    if banner_atemporal and getattr(banner_atemporal, "filename", None):
        banner_atemp_url = _save_optimized_banner(banner_atemporal, f"{slug}-banner.webp")
    if banner_promocional and getattr(banner_promocional, "filename", None):
        banner_promo_url = _save_optimized_banner(banner_promocional, f"{slug}-banner-promo.webp")

    active_banner_type = data.get("active_banner_type") or data.get("active_image_type", "atemporal")
    if active_banner_type not in ["atemporal", "promocional"]:
        active_banner_type = "atemporal"
    effective_banner = banner_promo_url if (active_banner_type == "promocional" and banner_promo_url) else banner_atemp_url

    s = lambda k, default="": str(data.get(k) or default).strip()
    pot_nom, vel_max = s("potencia_nominal_w"), s("velocidade_max_kmh")
    aut_cons, aut_max = s("autonomia_conservadora_km"), s("autonomia_maxima_km")
    volt, cap_ah, cap_wh, quimica = s("voltagem_v"), s("capacidade_ah"), s("capacidade_wh"), s("quimica_bateria")
    carga, peso, freios = s("carga_maxima_kg"), s("peso_kg"), s("freios")
    diferencial, pontos_fortes, desc_livre = s("diferencial"), s("pontos_fortes"), s("descricao_livre")
    is_active = data.get("is_active") in [True, "true", "True", "1", 1]

    model_record = {
        "categoria": s("categoria", "Scooter"), "modelo": name, "slug": slug, "is_active": is_active,
        "banner_image": banner_atemp_url, "promo_banner_image": banner_promo_url,
        "active_banner_type": active_banner_type, "active_image_type": active_banner_type,
        "hero_image": effective_banner, "display_image": effective_banner, "cutout_image": banner_atemp_url,
        "images": [effective_banner] if effective_banner else [],
        "metrics": {
            "potencia_nominal_w": pot_nom, "velocidade_max_kmh": vel_max,
            "autonomia_conservadora_km": aut_cons, "autonomia_maxima_km": aut_max,
            "voltagem_v": volt, "capacidade_ah": cap_ah, "capacidade_wh": cap_wh, "quimica_bateria": quimica,
            "carga_maxima_kg": carga, "peso_kg": peso, "freios": freios,
            "diferencial": diferencial, "pontos_fortes": pontos_fortes, "descricao_livre": desc_livre,
        },
        "sections": {
            "Identificação": {"Marca": s("marca", "MAJ"), "Versão / ano": s("versao_ano", "2026"), "Código interno": s("codigo_interno"), "Status": "Ativo" if is_active else "Inativo"},
            "Desempenho": {"Potência nominal (W)": pot_nom, "Velocidade máxima (km/h)": vel_max, "Modos de condução": s("modos_conducao", "3 níveis"), "Possui ré?": s("possui_re", "Sim")},
            "Bateria e autonomia": {"Química / tipo": quimica, "Voltagem (V)": volt, "Capacidade (Ah)": cap_ah, "Capacidade (Wh)": cap_wh, "Autonomia conservadora (km)": aut_cons, "Autonomia máxima estimada (km)": aut_max},
            "Estrutura e conforto": {"Carga máxima suportada (kg)": carga, "Peso do veículo (kg)": peso, "Tipo de freios": freios, "Suspensão": s("suspensao"), "Aro / Pneu": s("aro_pneu")},
            "Uso e comercial": {"Diferencial": diferencial, "Pontos fortes": pontos_fortes},
            "Texto livre": {"Descrição livre": desc_livre},
        },
    }

    overrides = load_model_overrides()
    overrides[slug] = model_record
    save_model_overrides(overrides)
    _refresh_local_models_cache()
    return {"status": "success", "slug": slug, "model": model_record}


def export_models_to_xlsx_bytes(models: List[Dict[str, Any]]) -> io.BytesIO:
    """Gera planilha XLSX formatada com todos os modelos e suas especificações técnicas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Catálogo Showroom MAJ"

    headers = [
        "Status", "Categoria", "Modelo", "Slug", "Banner Ativo", "Banner Atemporal", "Banner Promo",
        "Potência (W)", "Vel. Máx (km/h)", "Autonomia Cons. (km)", "Autonomia Máx (km)",
        "Voltagem (V)", "Capacidade (Ah)", "Capacidade (Wh)", "Bateria Química",
        "Carga Máx (kg)", "Peso (kg)", "Freios", "Diferencial", "Descrição Vitrine"
    ]

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    thin = Side(style="thin", color="CBD5E1")
    border_thin = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font, cell.fill, cell.alignment = header_font, header_fill, align_center

    for m in models:
        metrics = m.get("metrics", {})
        row = [
            "Ativo" if m.get("is_active") else "Inativo", m.get("categoria", ""), m.get("modelo", ""),
            m.get("slug", ""), m.get("effective_banner_type", "atemporal"), m.get("banner_image", ""),
            m.get("promo_banner_image", ""), metrics.get("potencia_nominal_w", ""), metrics.get("velocidade_max_kmh", ""),
            metrics.get("autonomia_conservadora_km", ""), metrics.get("autonomia_maxima_km", ""),
            metrics.get("voltagem_v", ""), metrics.get("capacidade_ah", ""), metrics.get("capacidade_wh", ""),
            metrics.get("quimica_bateria", ""), metrics.get("carga_maxima_kg", ""), metrics.get("peso_kg", ""),
            metrics.get("freios", ""), metrics.get("diferencial", ""), metrics.get("descricao_livre", ""),
        ]
        ws.append(row)
        curr_row = ws.max_row
        for col_idx in range(1, len(row) + 1):
            cell = ws.cell(row=curr_row, column=col_idx)
            cell.border = border_thin
            cell.alignment = align_center if col_idx in [1, 2, 4, 5, 8, 9, 10, 11, 12, 13, 14, 16, 17] else align_left

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col[0].column)].width = min(max(max_len + 3, 12), 45)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
