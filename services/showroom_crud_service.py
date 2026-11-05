"""
Serviço CRUD e Persistência Soberana dos Modelos do Showroom MAJ
Permite cadastro e edição completa de veículos com foco nos Banners Panorâmicos
Widescreen (16:9 de estúdio) de Topo: Atemporal vs Promocional de Campanha.
Garante persistência híbrida: alterações locais/banco nunca são sobrescritas pela planilha.
"""

import io
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from PIL import Image
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

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
    slug = re.sub(r"[àáâãäå]", "a", slug)
    slug = re.sub(r"[èéêë]", "e", slug)
    slug = re.sub(r"[ìíîï]", "i", slug)
    slug = re.sub(r"[òóôõö]", "o", slug)
    slug = re.sub(r"[ùúûü]", "u", slug)
    slug = re.sub(r"[ç]", "c", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def get_global_image_mode() -> str:
    """Retorna o modo global de banners ('atemporal' ou 'promocional')."""
    for path in [IMAGE_MODE_FILE, API_IMAGE_MODE_FILE]:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    mode = data.get("mode", "atemporal")
                    if mode in ["atemporal", "promocional"]:
                        return mode
            except Exception:
                pass
    return "atemporal"


def set_global_image_mode(mode: str) -> str:
    """Define a chave mestra global do modo de banners do mostruário."""
    clean_mode = "promocional" if mode == "promocional" else "atemporal"
    payload = {"mode": clean_mode}
    for path in [IMAGE_MODE_FILE, API_IMAGE_MODE_FILE]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar modo global em {path}: {e}")

    from services.maj_models_sync_service import sync_models_from_sheets
    sync_models_from_sheets(force=True)
    return clean_mode


def resolve_disk_banners(slug: str) -> Dict[str, str]:
    """Detecta automaticamente os banners de estúdio (16:9) atemporal e promocional no disco."""
    clean_slug = slug.strip().lower()
    atemporal = ""
    promocional = ""

    # 1. Busca por banner atemporal oficial
    for folder in [BANNER_DIR_PUBLIC, BANNER_DIR_STATIC]:
        for candidate in [f"{clean_slug}-banner.webp", f"{clean_slug}-banner-2x.webp", f"{clean_slug}-banner.jpg", f"{clean_slug}.webp"]:
            f = folder / candidate
            if f.is_file():
                atemporal = f"/public/images/models/banners/{candidate}"
                break
        if atemporal:
            break

    # 2. Busca por banner promocional de campanha
    for folder in [BANNER_DIR_PUBLIC, BANNER_DIR_STATIC]:
        for candidate in [f"{clean_slug}-banner-promo.webp", f"{clean_slug}-promo.webp", f"{clean_slug}-promo.jpg"]:
            f = folder / candidate
            if f.is_file():
                promocional = f"/public/images/models/banners/{candidate}"
                break
        if promocional:
            break

    return {"atemporal": atemporal, "promocional": promocional}


def load_model_overrides() -> Dict[str, Dict[str, Any]]:
    """Carrega os overrides salvos no sistema."""
    for path in [OVERRIDES_FILE, API_OVERRIDES_FILE]:
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"Erro ao ler overrides de {path}: {e}")
    return {}


def save_model_overrides(overrides: Dict[str, Dict[str, Any]]) -> None:
    """Salva os overrides nos locais estáticos do servidor e Vercel."""
    for path in [OVERRIDES_FILE, API_OVERRIDES_FILE]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(overrides, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar overrides em {path}: {e}")


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
                target.setdefault("metrics", {})
                target["metrics"].update(override["metrics"])
            if "sections" in override:
                target.setdefault("sections", {})
                for sec_name, sec_vals in override["sections"].items():
                    target["sections"].setdefault(sec_name, {})
                    target["sections"][sec_name].update(sec_vals)
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

        m_active_type = m.get("active_banner_type") or m.get("active_image_type", "atemporal")
        effective_type = "promocional" if (global_mode == "promocional" and m.get("promo_banner_image")) else m_active_type

        m["effective_image_type"] = effective_type
        m["effective_banner_type"] = effective_type

        # Banner ativo no topo da página
        if effective_type == "promocional" and m.get("promo_banner_image"):
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
    target = next(
        (
            m for m in models
            if m.get("slug") in alias_candidates
            or normalize_slug(m.get("modelo", "")) in alias_candidates
        ),
        None,
    )
    if not target:
        return None

    banners = resolve_disk_banners(target.get("slug") or clean_slug)
    banner_atemp = target.get("banner_image") or banners["atemporal"] or ""
    banner_promo = target.get("promo_banner_image") or banners["promocional"] or ""

    sections = target.get("sections", {})
    metrics = target.get("metrics", {})
    ident = sections.get("Identificação", {})
    desemp = sections.get("Desempenho", {})
    bat = sections.get("Bateria e autonomia", {})
    est = sections.get("Estrutura e conforto", {})
    com = sections.get("Uso e comercial", {})
    livre = sections.get("Texto livre", {})

    return {
        "slug": target.get("slug", ""),
        "modelo": target.get("modelo", ""),
        "categoria": target.get("categoria", "Scooter"),
        "is_active": target.get("is_active", True),
        "banner_image": banner_atemp,
        "promo_banner_image": banner_promo,
        "active_banner_type": target.get("active_banner_type") or target.get("active_image_type", "atemporal"),
        "marca": ident.get("Marca", "MAJ"),
        "versao_ano": ident.get("Versão / ano", "2026"),
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


def _save_optimized_banner(file_obj, filename: str) -> None:
    """Converte e salva o banner em WebP otimizado (16:9 estúdio) nas pastas canônicas."""
    try:
        img = Image.open(file_obj)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        for folder in [BANNER_DIR_STATIC, BANNER_DIR_PUBLIC]:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / filename
            img.save(target, format="WEBP", quality=90, method=6)
    except Exception as e:
        logger.warning(f"Fallback gravando arquivo bruto de banner {filename}: {e}")
        file_obj.seek(0)
        file_bytes = file_obj.read()
        for folder in [BANNER_DIR_STATIC, BANNER_DIR_PUBLIC]:
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / filename, "wb") as f:
                f.write(file_bytes)


def save_showroom_model(data: Dict[str, Any], banner_atemporal=None, banner_promocional=None) -> Dict[str, Any]:
    """Salva a criação ou edição com foco nos banners de topo (Atemporal vs Promocional)."""
    name = (data.get("modelo") or "").strip()
    if not name:
        raise ValueError("O nome do modelo é obrigatório.")

    slug = (data.get("slug") or "").strip().lower()
    if not slug:
        slug = slugify(name)

    banners = resolve_disk_banners(slug)
    banner_atemp_url = data.get("banner_image") or banners["atemporal"] or ""
    banner_promo_url = data.get("promo_banner_image") or banners["promocional"] or ""

    # Processamento do Banner Atemporal (16:9)
    if banner_atemporal and getattr(banner_atemporal, "filename", None):
        fname = f"{slug}-banner.webp"
        _save_optimized_banner(banner_atemporal, fname)
        banner_atemp_url = f"/public/images/models/banners/{fname}"

    # Processamento do Banner Promocional (16:9)
    if banner_promocional and getattr(banner_promocional, "filename", None):
        fname = f"{slug}-banner-promo.webp"
        _save_optimized_banner(banner_promocional, fname)
        banner_promo_url = f"/public/images/models/banners/{fname}"

    active_banner_type = data.get("active_banner_type") or data.get("active_image_type", "atemporal")
    if active_banner_type not in ["atemporal", "promocional"]:
        active_banner_type = "atemporal"

    effective_banner = banner_promo_url if (active_banner_type == "promocional" and banner_promo_url) else banner_atemp_url

    pot_nom = str(data.get("potencia_nominal_w") or "").strip()
    vel_max = str(data.get("velocidade_max_kmh") or "").strip()
    aut_cons = str(data.get("autonomia_conservadora_km") or "").strip()
    aut_max = str(data.get("autonomia_maxima_km") or "").strip()
    volt = str(data.get("voltagem_v") or "").strip()
    cap_ah = str(data.get("capacidade_ah") or "").strip()
    cap_wh = str(data.get("capacidade_wh") or "").strip()
    quimica = str(data.get("quimica_bateria") or "").strip()
    carga = str(data.get("carga_maxima_kg") or "").strip()
    peso = str(data.get("peso_kg") or "").strip()
    freios = str(data.get("freios") or "").strip()
    diferencial = str(data.get("diferencial") or "").strip()
    pontos_fortes = str(data.get("pontos_fortes") or "").strip()
    desc_livre = str(data.get("descricao_livre") or "").strip()
    is_active = data.get("is_active") in [True, "true", "True", "1", 1]

    model_record = {
        "categoria": (data.get("categoria") or "Scooter").strip(),
        "modelo": name,
        "slug": slug,
        "is_active": is_active,
        "banner_image": banner_atemp_url,
        "promo_banner_image": banner_promo_url,
        "active_banner_type": active_banner_type,
        "active_image_type": active_banner_type,
        "hero_image": effective_banner,
        "display_image": effective_banner,
        "cutout_image": banner_atemp_url,
        "images": [effective_banner] if effective_banner else [],
        "metrics": {
            "potencia_nominal_w": pot_nom,
            "velocidade_max_kmh": vel_max,
            "autonomia_conservadora_km": aut_cons,
            "autonomia_maxima_km": aut_max,
            "voltagem_v": volt,
            "capacidade_ah": cap_ah,
            "capacidade_wh": cap_wh,
            "quimica_bateria": quimica,
            "carga_maxima_kg": carga,
            "peso_kg": peso,
            "freios": freios,
            "diferencial": diferencial,
            "pontos_fortes": pontos_fortes,
            "descricao_livre": desc_livre,
        },
        "sections": {
            "Identificação": {
                "Marca": str(data.get("marca") or "MAJ").strip(),
                "Versão / ano": str(data.get("versao_ano") or "2026").strip(),
                "Código interno": str(data.get("codigo_interno") or "").strip(),
                "Status": "Ativo" if is_active else "Inativo",
            },
            "Desempenho": {
                "Potência nominal (W)": pot_nom,
                "Velocidade máxima (km/h)": vel_max,
                "Modos de condução": str(data.get("modos_conducao") or "3 níveis").strip(),
                "Possui ré?": str(data.get("possui_re") or "Sim").strip(),
            },
            "Bateria e autonomia": {
                "Química / tipo": quimica,
                "Voltagem (V)": volt,
                "Capacidade (Ah)": cap_ah,
                "Capacidade (Wh)": cap_wh,
                "Autonomia conservadora (km)": aut_cons,
                "Autonomia máxima estimada (km)": aut_max,
            },
            "Estrutura e conforto": {
                "Carga máxima suportada (kg)": carga,
                "Peso do veículo (kg)": peso,
                "Tipo de freios": freios,
                "Suspensão": str(data.get("suspensao") or "").strip(),
                "Aro / Pneu": str(data.get("aro_pneu") or "").strip(),
            },
            "Uso e comercial": {
                "Diferencial": diferencial,
                "Pontos fortes": pontos_fortes,
            },
            "Texto livre": {
                "Descrição livre": desc_livre,
            },
        },
    }

    overrides = load_model_overrides()
    overrides[slug] = model_record
    save_model_overrides(overrides)

    from services.maj_models_sync_service import sync_models_from_sheets
    sync_models_from_sheets(force=True)

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
    border_thin = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    for m in models:
        metrics = m.get("metrics", {})
        row = [
            "Ativo" if m.get("is_active") else "Inativo",
            m.get("categoria", ""),
            m.get("modelo", ""),
            m.get("slug", ""),
            m.get("effective_banner_type", "atemporal"),
            m.get("banner_image", ""),
            m.get("promo_banner_image", ""),
            metrics.get("potencia_nominal_w", ""),
            metrics.get("velocidade_max_kmh", ""),
            metrics.get("autonomia_conservadora_km", ""),
            metrics.get("autonomia_maxima_km", ""),
            metrics.get("voltagem_v", ""),
            metrics.get("capacidade_ah", ""),
            metrics.get("capacidade_wh", ""),
            metrics.get("quimica_bateria", ""),
            metrics.get("carga_maxima_kg", ""),
            metrics.get("peso_kg", ""),
            metrics.get("freios", ""),
            metrics.get("diferencial", ""),
            metrics.get("descricao_livre", ""),
        ]
        ws.append(row)
        curr_row = ws.max_row
        for col_idx in range(1, len(row) + 1):
            cell = ws.cell(row=curr_row, column=col_idx)
            cell.border = border_thin
            cell.alignment = align_center if col_idx in [1, 2, 4, 5, 8, 9, 10, 11, 12, 13, 14, 16, 17] else align_left

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
