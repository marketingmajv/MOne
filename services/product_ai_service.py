"""
M-One Product AI Service (services/product_ai_service.py)
Motor de IA para Detecção Autônoma de Novos Produtos em Planilhas e
Enriquecimento/Atualização Contínua de Fichas Técnicas e Copys Comerciais.
"""

from __future__ import annotations

import io
import json
import logging
import re
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import openpyxl

from database import db
from services.gemini_client import execute_gemini_payload
from services.product_hub_propagation import propagate_product_to_channels
from services.product_hub_service import (
    ensure_master_products_schema,
    get_all_master_products,
    get_master_product_by_id_or_slug,
    save_master_product,
    slugify,
)

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent

OFFICIAL_KNOWLEDGE_BASE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1uYnE9-MCSuRSe-9bSvcUulALjvh8aUdYEMbGAWZEC5E/export?format=xlsx"
)


KNOWN_MODEL_ALIASES = {
    "gp1000": "gp-1000",
    "gp-1000": "gp-1000",
    "jm125": "jm-125",
    "jm-125": "jm-125",
    "jm125-ano-2023": "jm-125",
    "q8-aluminio": "q8",
    "q-8": "q8",
    "v8mini": "v8-mini",
    "v8-mini-ultra": "v8-mini",
    "v20": "v20-ultra",
    "v20-ultra": "v20-ultra",
    "dbzero": "db-zero",
    "db-zero": "db-zero",
    "max12": "max-12",
    "max-12-maj": "max-12",
    "vittoria": "vittoria",
    "m-2": "m2",
    "scooter-m2": "m2",
}


def canonical_model_slug(name_or_slug: str) -> str:
    """Normaliza o slug considerando aliases conhecidos e pontuações."""
    s = slugify(name_or_slug)
    if s in KNOWN_MODEL_ALIASES:
        return KNOWN_MODEL_ALIASES[s]
    # Tenta sem hífens
    s_clean = s.replace("-", "")
    if s_clean in KNOWN_MODEL_ALIASES:
        return KNOWN_MODEL_ALIASES[s_clean]
    return s


def get_active_sheet_sources() -> List[Dict[str, str]]:
    """Retorna as fontes de planilhas de produtos ativas cadastradas no sistema."""
    sources = [
        {
            "id": "base_conhecimento_modelos",
            "name": "Base de Conhecimento Modelos MAJ (Oficial)",
            "url": OFFICIAL_KNOWLEDGE_BASE_SHEET_URL,
            "type": "official",
        }
    ]

    try:
        with db() as conn:
            rows = conn.execute(
                """
                SELECT key, name, sheets_url FROM data_sources
                WHERE sheets_url IS NOT NULL AND TRIM(sheets_url) != ''
                  AND (category IN ('Catálogo & Comercial', 'Modelos', 'Produtos') OR key LIKE '%%product%%' OR key LIKE '%%model%%')
                """
            ).fetchall()
            for r in rows:
                if hasattr(r, "get"):
                    k = r.get("key")
                    nm = r.get("name")
                    url = (r.get("sheets_url") or "").strip()
                else:
                    k = r[0] if len(r) > 0 else ""
                    nm = r[1] if len(r) > 1 else ""
                    url = (r[2] if len(r) > 2 else "" or "").strip()
                if not url or url == OFFICIAL_KNOWLEDGE_BASE_SHEET_URL:
                    continue
                if "docs.google.com/spreadsheets" in url and "/export" not in url:
                    m = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
                    if m:
                        url = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx"
                sources.append({"id": k, "name": nm, "url": url, "type": "extra"})
    except Exception as e:
        logger.warning(f"Erro ao consultar data_sources adicionais: {e}")

    return sources


def fetch_workbook(url: str, timeout: int = 20) -> Optional[openpyxl.Workbook]:
    """Baixa e carrega uma planilha XLSX em memória."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MOne-ProductAI/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except Exception as e:
        logger.error(f"Falha ao carregar planilha de {url}: {e}")
        return None


def find_model_media(slug: str) -> Dict[str, Any]:
    """Descobre fotos, recortes e banners existentes para o slug informado."""
    clean_slug = slug.strip().lower()
    media: Dict[str, Any] = {
        "image_main": "",
        "banner_widescreen": "",
        "gallery": [],
    }

    cutout_path = BASE_DIR / "public" / "images" / "models" / "cutouts" / f"{clean_slug}.png"
    banner_path = BASE_DIR / "public" / "images" / "models" / "banners" / f"{clean_slug}-banner.webp"
    share_path = BASE_DIR / "public" / "images" / "models" / "share" / f"{clean_slug}.jpg"

    if cutout_path.is_file():
        media["image_main"] = f"/public/images/models/cutouts/{clean_slug}.png"
    elif share_path.is_file():
        media["image_main"] = f"/public/images/models/share/{clean_slug}.jpg"

    if banner_path.is_file():
        media["banner_widescreen"] = f"/public/images/models/banners/{clean_slug}-banner.webp"

    search_dirs = [
        BASE_DIR / "public" / "images" / clean_slug,
        BASE_DIR / "static" / "images" / clean_slug,
        BASE_DIR / "public" / "images" / clean_slug.replace("-", ""),
    ]
    for d in search_dirs:
        if d.is_dir():
            for f in sorted(d.glob("*.jpg")) + sorted(d.glob("*.png")) + sorted(d.glob("*.webp")):
                if f.name.startswith(".") or "original" in f.name.lower() or "banner" in f.name.lower():
                    continue
                web_url = f"/static/images/{clean_slug}/{f.name}" if "static" in str(d) else f"/public/images/{clean_slug}/{f.name}"
                media["gallery"].append(web_url)
                if not media["image_main"]:
                    media["image_main"] = web_url
            if media["gallery"]:
                break

    return media


def extract_raw_models_data(wb: openpyxl.Workbook) -> Dict[str, Dict[str, Any]]:
    """
    Vasculha todas as abas da planilha e agrega todos os atributos encontrados
    por modelo (nome normalizado e dados brutos de cada seção).
    """
    raw_models: Dict[str, Dict[str, Any]] = {}

    for sheet_name in wb.sheetnames:
        if sheet_name in ["Instruções", "Resumo"]:
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 4:
            continue

        headers = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(rows[2])]
        model_col_idx = 2 if "Marca" in headers and headers.index("Marca") < headers.index("Modelo") else (
            headers.index("Modelo") if "Modelo" in headers else 1
        )
        cat_col_idx = headers.index("Categoria") if "Categoria" in headers else 0

        for r_idx, r in enumerate(rows[3:], start=4):
            if not r or len(r) <= model_col_idx or not r[model_col_idx]:
                continue
            model_name = str(r[model_col_idx]).strip()
            if not model_name or model_name.lower() in ["modelo", "categoria", "none", "marca"]:
                continue

            slug = canonical_model_slug(model_name)
            if not slug:
                continue

            if slug not in raw_models:
                cat = str(r[cat_col_idx]).strip() if len(r) > cat_col_idx and r[cat_col_idx] else ""
                raw_models[slug] = {
                    "raw_name": model_name,
                    "slug": slug,
                    "category": cat,
                    "sheet_occurrences": [],
                    "sections": {},
                    "free_text": [],
                }

            sheet_data: Dict[str, Any] = {}
            for h, val in zip(headers, r):
                if h in ["Categoria", "Modelo", "% preenchido", "Potência de pico (W)"]:
                    continue
                if val is not None and str(val).strip():
                    sheet_data[h] = str(val).strip()

            raw_models[slug]["sheet_occurrences"].append(f"{sheet_name}:linha_{r_idx}")
            if sheet_name == "Texto livre":
                for val in sheet_data.values():
                    raw_models[slug]["free_text"].append(val)
            else:
                if sheet_name not in raw_models[slug]["sections"]:
                    raw_models[slug]["sections"][sheet_name] = {}
                raw_models[slug]["sections"][sheet_name].update(sheet_data)

    return raw_models


def detect_new_products(custom_sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Detecta produtos presentes nas planilhas mas ausentes na Central de Produtos Mestre.
    Usa IA Gemini para sintetizar fichas canônicas e copys comerciais.
    """
    ensure_master_products_schema()
    existing_products = get_all_master_products()
    existing_slugs = {canonical_model_slug(p.get("slug")) for p in existing_products if p.get("slug")}
    existing_slugs_raw = {p.get("slug", "").replace("-", "") for p in existing_products if p.get("slug")}
    existing_names = {p.get("name", "").strip().lower() for p in existing_products if p.get("name")}

    sources = get_active_sheet_sources()
    if custom_sources:
        for idx, cs in enumerate(custom_sources):
            sources.append({"id": f"custom_{idx}", "name": f"Planilha Customizada {idx+1}", "url": cs, "type": "custom"})

    detected_new: List[Dict[str, Any]] = []

    for src in sources:
        wb = fetch_workbook(src["url"])
        if not wb:
            continue

        raw_models = extract_raw_models_data(wb)
        for slug, mdata in raw_models.items():
            raw_name = mdata["raw_name"]
            c_slug = canonical_model_slug(slug)
            if c_slug in existing_slugs or c_slug.replace("-", "") in existing_slugs_raw or raw_name.strip().lower() in existing_names:
                continue
            if any(item["slug"] == c_slug for item in detected_new):
                continue

            # Produto novo detectado! Sintetiza com IA Gemini
            logger.info(f"✨ Novo produto detectado em {src['name']}: {raw_name} (slug: {slug})")
            ai_data = synthesize_product_with_ai(mdata)
            media = find_model_media(slug)

            # Prepara URL amigável da planilha Google Sheets para auditoria
            clean_source_url = src["url"].replace("/export?format=xlsx", "/edit").replace("/export", "/edit")
            if "1uYnE9-MCSuRSe-9bSvcUulALjvh8aUdYEMbGAWZEC5E" in clean_source_url and any("Texto livre" in occ for occ in mdata["sheet_occurrences"]):
                clean_source_url = "https://docs.google.com/spreadsheets/d/1uYnE9-MCSuRSe-9bSvcUulALjvh8aUdYEMbGAWZEC5E/edit?gid=1639092973#gid=1639092973"

            occ_formatted = []
            for occ in mdata["sheet_occurrences"]:
                parts = occ.split(":")
                tab = parts[0]
                line = parts[1].replace("linha_", "Linha ") if len(parts) > 1 else ""
                occ_formatted.append(f"{tab} ({line})")

            detected_new.append({
                "source_name": src["name"],
                "source_url": clean_source_url,
                "source_sheet": " • ".join(occ_formatted),
                "raw_name": raw_name,
                "slug": slug,
                "name": ai_data.get("name") or raw_name,
                "category": ai_data.get("category") or mdata.get("category") or "Mobilidade Elétrica",
                "brand": ai_data.get("brand") or "MAJ",
                "sku": ai_data.get("sku") or "",
                "specs": ai_data.get("specs") or {},
                "copy_showroom": ai_data.get("copy_showroom") or "",
                "copy_atacado": ai_data.get("copy_atacado") or "",
                "copy_outlet": ai_data.get("copy_outlet") or "",
                "notes": ai_data.get("notes") or "",
                "image_main": media.get("image_main") or "",
                "banner_widescreen": media.get("banner_widescreen") or "",
                "gallery": media.get("gallery") or [],
                "raw_sections": mdata.get("sections") or {},
            })

    return detected_new


def synthesize_product_with_ai(mdata: Dict[str, Any]) -> Dict[str, Any]:
    """Submete os dados brutos das planilhas ao Gemini para gerar ficha e copys."""
    raw_name = mdata["raw_name"]
    sections_json = json.dumps(mdata.get("sections", {}), ensure_ascii=False)
    free_text_str = " ".join(mdata.get("free_text", []))

    prompt = f"""Você é o Engenheiro Chefe e Copywriter da MAJ Mobilidade Elétrica.
Analise os dados brutos de engenharia para o modelo: "{raw_name}".
DADOS DAS PLANILHAS: {sections_json}
ANOTAÇÕES: {free_text_str}

TAREFA:
1. Definir Nome Oficial Limpo e Categoria adequada (Triciclo, Scooter, Bike).
2. Extrair specs canônicas: Motor, Bateria, Autonomia, Velocidade, Freios, Química, Carga Máxima, Peso, Tempo de Recarga, Diferencial.
3. Gerar 3 copys:
   - copy_showroom: Inspiradora, elegante, foco em estilo e experiência.
   - copy_atacado: Direta e técnica para lojistas B2B (margens, garantia, revenda).
   - copy_outlet: Promocional para consumidor B2C (economia, mobilidade diária).
4. Gerar notes técnicas (alertas de homologação/uso).

RESPONDA EXCLUSIVAMENTE COM JSON:
{{
  "name": "{raw_name}", "category": "Triciclo / Scooter / Bike", "brand": "MAJ", "sku": "MAJ-...",
  "specs": {{ "Motor": "...", "Bateria": "...", "Autonomia": "...", "Velocidade": "...", "Freios": "...", "Química": "...", "Carga Máxima": "...", "Peso": "...", "Tempo de Recarga": "...", "Diferencial": "..." }},
  "copy_showroom": "...", "copy_atacado": "...", "copy_outlet": "...", "notes": "..."
}}
"""

    try:
        res = execute_gemini_payload({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        })
        text_resp = res.get("text", "").strip()
        # Remove eventuais fences de markdown
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:]
        if text_resp.endswith("```"):
            text_resp = text_resp[:-3]
        return json.loads(text_resp.strip())
    except Exception as e:
        logger.warning(f"Falha na síntese IA do produto {raw_name}: {e}. Usando fallback seguro.")
        # Fallback manual seguro a partir dos dados brutos
        desempenho = mdata.get("sections", {}).get("Desempenho", {})
        bateria = mdata.get("sections", {}).get("Bateria e autonomia", {})
        estrutura = mdata.get("sections", {}).get("Estrutura e conforto", {})
        return {
            "name": raw_name,
            "category": mdata.get("category") or "Mobilidade Elétrica",
            "brand": "MAJ",
            "sku": f"MAJ-{mdata['slug'].upper()}",
            "specs": {
                "Motor": desempenho.get("Potência nominal (W)", "") + ("W" if desempenho.get("Potência nominal (W)") else ""),
                "Bateria": f"{bateria.get('Voltagem (V)', '')}V {bateria.get('Capacidade (Ah)', '')}Ah".strip(),
                "Autonomia": f"Até {bateria.get('Autonomia conservadora (km)', '')} km" if bateria.get('Autonomia conservadora (km)') else "",
                "Velocidade": f"Até {desempenho.get('Velocidade máxima (km/h)', '')} km/h" if desempenho.get('Velocidade máxima (km/h)') else "",
                "Carga Máxima": f"{estrutura.get('Carga máxima (kg)', '')} kg" if estrutura.get('Carga máxima (kg)') else "",
            },
            "copy_showroom": free_text_str[:250] if free_text_str else f"Modelo {raw_name} de alta performance MAJ.",
            "copy_atacado": f"Oportunidade de alta rotação B2B para o modelo {raw_name}.",
            "copy_outlet": f"Aproveite as condições exclusivas de Outlet para o modelo {raw_name}.",
            "notes": "Cadastro gerado a partir da base de conhecimento de modelos.",
        }


def analyze_product_updates(product_id_or_slug: Any) -> Dict[str, Any]:
    """
    Localiza um produto existente nas planilhas, compara com a ficha salva no banco
    e usa IA para identificar campos que ganharam novas informações ou correções.
    """
    prod = get_master_product_by_id_or_slug(product_id_or_slug)
    if not prod:
        return {"success": False, "error": "Produto mestre não encontrado no M-One."}

    prod_name = prod.get("name", "")
    prod_slug = prod.get("slug", "")
    sources = get_active_sheet_sources()

    matched_data: Optional[Dict[str, Any]] = None
    matched_source_name = ""

    for src in sources:
        wb = fetch_workbook(src["url"])
        if not wb:
            continue
        raw_models = extract_raw_models_data(wb)
        for s, m in raw_models.items():
            if s == prod_slug or m["raw_name"].strip().lower() == prod_name.strip().lower() or prod_slug in s:
                matched_data = m
                matched_source_name = src["name"]
                break
        if matched_data:
            break

    if not matched_data:
        return {
            "success": False,
            "error": f"Nenhum registro encontrado nas planilhas para o modelo '{prod_name}'.",
        }

    # Sintetiza com IA a comparação direta
    current_specs = prod.get("specs_json") or {}
    prompt = f"""Você é o Auditor Técnico da MAJ Mobilidade.
Compare a ficha técnica e copys atuais do modelo "{prod_name}" no M-One com os dados mais recentes das planilhas ({matched_source_name}).
DADOS ATUAIS NO M-ONE: Categoria: {prod.get('category')} | Specs: {json.dumps(current_specs, ensure_ascii=False)} | Showroom: {prod.get('copy_showroom')} | Atacado: {prod.get('copy_atacado')} | Outlet: {prod.get('copy_outlet')}
DADOS PLANILHA: {json.dumps(matched_data.get('sections', {}), ensure_ascii=False)} | Notas: {' '.join(matched_data.get('free_text', []))}

TAREFA: Identificar dados mais precisos, correções ou melhorias. Se a planilha tiver informações mais ricas, forneça os novos valores. Se o atual for melhor, mantenha.
RESPONDA EXCLUSIVAMENTE COM JSON:
{{ "has_updates": true/false, "diff_summary": ["..."], "updated_fields": {{ "category": "...", "specs": {{ ...specs completas... }}, "copy_showroom": "...", "copy_atacado": "...", "copy_outlet": "..." }} }}
"""

    try:
        res = execute_gemini_payload({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        })
        text_resp = res.get("text", "").strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:]
        if text_resp.endswith("```"):
            text_resp = text_resp[:-3]
        parsed = json.loads(text_resp.strip())
        parsed["success"] = True
        parsed["source_name"] = matched_source_name
        return parsed
    except Exception as e:
        logger.error(f"Erro ao auditar atualizações com IA para {prod_name}: {e}")
        return {
            "success": False,
            "error": f"Falha na análise de inteligência artificial: {str(e)}",
        }


def approve_and_register_new_product(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Persiste um novo produto aprovado na Central de Produtos Mestre
    e propaga opcionalmente para Atacado B2B e Varejo Outlet.
    """
    name = (data.get("name") or "").strip()
    if not name:
        return {"success": False, "error": "Nome do produto é obrigatório."}

    slug = data.get("slug") or slugify(name)
    specs = data.get("specs") or {}

    save_payload = {
        "name": name,
        "slug": slug,
        "category": data.get("category", "Mobilidade Elétrica"),
        "brand": data.get("brand", "MAJ"),
        "sku": data.get("sku", ""),
        "status": data.get("status", "inactive"),
        "specs_json": specs,
        "copy_showroom": data.get("copy_showroom", ""),
        "copy_atacado": data.get("copy_atacado", ""),
        "copy_outlet": data.get("copy_outlet", ""),
        "image_main": data.get("image_main", ""),
        "banner_widescreen": data.get("banner_widescreen", ""),
        "images_gallery": data.get("gallery", []),
        "sync_atacado": bool(data.get("sync_atacado", True)),
        "sync_outlet": bool(data.get("sync_outlet", True)),
        "notes": data.get("notes", ""),
    }

    new_id = save_master_product(save_payload)
    if not new_id:
        return {"success": False, "error": "Falha ao salvar produto no banco de dados."}

    # Propagação para canais se solicitado
    prop_res = {}
    if save_payload["sync_atacado"] or save_payload["sync_outlet"]:
        try:
            prop_res = propagate_product_to_channels(new_id)
        except Exception as e:
            logger.warning(f"Aviso na propagação imediata do produto {new_id}: {e}")

    return {
        "success": True,
        "product_id": new_id,
        "slug": slug,
        "name": name,
        "propagation": prop_res,
    }
