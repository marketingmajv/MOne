"""
M-One Outlet Sync Service (services/outlet_sync_service.py)
Serviço de sincronização de dados do Outlet a partir de planilha CSV oficial.
Atualiza quantidades em estoque, preços de queima de lote e parcelamentos.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from database import db
from services.outlet_specs import MODEL_SPECS

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


def sync_outlet_from_csv(csv_content_or_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Sincroniza os itens do catálogo do Outlet MAJ com base no arquivo CSV oficial.
    Atualiza quantidades em estoque, preços promocionais e condições sem apagar
    fotos já existentes cadastradas no banco de dados.
    """
    from services.outlet_service import (
        ensure_outlet_schema,
        get_outlet_item_by_id_or_slug,
        parse_currency,
        save_outlet_item,
        slugify,
    )

    ensure_outlet_schema()

    raw_text = None
    if csv_content_or_path:
        p = Path(csv_content_or_path)
        if p.exists():
            raw_text = p.read_text(encoding="utf-8-sig")
        else:
            raw_text = csv_content_or_path

    if not raw_text:
        csv_file = BASE_DIR / "uploads" / "outlet" / "tabela_precos_outlet.csv"
        if csv_file.exists():
            raw_text = csv_file.read_text(encoding="utf-8-sig")
        else:
            try:
                url = "https://raw.githubusercontent.com/marketingmajv/MOne/main/uploads/outlet/tabela_precos_outlet.csv"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (M-One-Sync)"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_text = resp.read().decode("utf-8-sig")
            except Exception as e:
                logger.error("Falha ao buscar CSV do GitHub (%s): %s", url, e)
                raise FileNotFoundError(f"Planilha CSV do Outlet não encontrada no disco ({csv_file}) nem no GitHub: {e}")


    reader = csv.DictReader(io.StringIO(raw_text))
    model_groups: Dict[str, Dict[str, Any]] = {}

    # Carregar modelos canônicos da Planilha Oficial Google para unificação de dados
    official_models: Dict[str, Dict[str, Any]] = {}
    try:
        from services.maj_models_sync_service import get_all_models
        for m in get_all_models(include_inactive=True):
            official_models[m.get("modelo", "").strip().upper()] = m
    except Exception as e:
        logger.warning("Não foi possível carregar modelos oficiais da planilha: %s", e)

    for row in reader:
        raw_name = (row.get("Correspondência tabela") or "").strip()
        if not raw_name:
            continue

        qty_str = (row.get("Qtd. Disponível") or "0").strip()
        qty = int(qty_str) if qty_str.isdigit() else 0
        price_out = parse_currency(row.get("Preço promoção") or "")
        p12 = parse_currency(row.get("Promoção 12x (parcela R$)") or "")
        p18 = parse_currency(row.get("Promoção 18x (parcela R$)") or "")
        cond = (row.get("Condição") or "").strip()
        color = (row.get("Cor / Banco") or "").strip()
        loc = (row.get("Localização") or "").strip()
        obs = (row.get("Observação") or "").strip()
        group_name = raw_name

        if group_name not in model_groups:
            model_groups[group_name] = {
                "name": group_name,
                "total_qty": 0,
                "min_price": price_out,
                "max_price": price_out,
                "installment_12": p12,
                "installment_18": p18,
                "conditions": set(),
                "colors": set(),
                "locations": set(),
                "observations": set(),
            }

        grp = model_groups[group_name]
        grp["total_qty"] += qty
        if price_out > 0:
            if grp["min_price"] == 0 or price_out < grp["min_price"]:
                grp["min_price"] = price_out
                grp["installment_12"] = p12
                grp["installment_18"] = p18
            if price_out > grp["max_price"]:
                grp["max_price"] = price_out
        if cond:
            grp["conditions"].add(cond)
        if color:
            grp["colors"].add(color)
        if loc:
            grp["locations"].add(loc)
        if obs:
            grp["observations"].add(obs)

    synced_count = 0
    total_stock = 0
    order = 1

    for model_name, grp in sorted(model_groups.items(), key=lambda x: x[1]["total_qty"], reverse=True):
        slug = slugify(model_name)
        specs_data = MODEL_SPECS.get(model_name, {})
        category = specs_data.get("category", "Mobilidade Elétrica")
        desc = specs_data.get("description", f"Veículo elétrico MAJ {model_name} de alta qualidade.")
        specs = dict(specs_data.get("specs", {}))

        # Cruzar dinamicamente com as especificações oficiais da Planilha Google
        clean_name = model_name.strip().upper()
        matched = official_models.get(clean_name)
        if not matched:
            for s_k, s_m in official_models.items():
                if s_k in clean_name or clean_name in s_k or s_k.replace(" ", "") == clean_name.replace(" ", ""):
                    matched = s_m
                    break
        if matched:
            m_metrics = matched.get("metrics", {})
            if m_metrics.get("potencia_nominal_w"):
                specs["Motor"] = f"{m_metrics['potencia_nominal_w']}W"
            if m_metrics.get("velocidade_max_kmh"):
                specs["Velocidade Máxima"] = f"Até {m_metrics['velocidade_max_kmh']} km/h"
            if m_metrics.get("autonomia_maxima_km"):
                specs["Autonomia"] = f"Até {m_metrics['autonomia_maxima_km']} km"
            if m_metrics.get("carga_maxima_kg"):
                specs["Carga Máxima"] = f"{m_metrics['carga_maxima_kg']} kg"
            if m_metrics.get("freios"):
                specs["Freios"] = m_metrics["freios"]

        if "color_prices" in specs_data:
            specs["color_prices"] = specs_data["color_prices"]
        badge = specs_data.get("badge", "OFERTA OUTLET")

        price_out = grp["min_price"]
        price_orig = round(price_out * 1.25, 2) if price_out > 0 else 0

        colors_list = sorted(list(grp["colors"]))
        colors_str = ", ".join(colors_list) if colors_list else "Conforme lote"
        conditions_str = ", ".join(sorted(list(grp["conditions"])))

        existing = get_outlet_item_by_id_or_slug(slug)
        main_img = ""
        gallery = []
        inst12_val = grp["installment_12"]
        inst18_val = grp["installment_18"]
        if existing:
            main_img = existing.get("image_main") or ""
            gallery = existing.get("images_gallery") or []
            # Preserva customizações manuais já realizadas no banco
            if existing.get("description"):
                desc = existing.get("description")
            if existing.get("badge"):
                badge = existing.get("badge")
            if existing.get("category"):
                category = existing.get("category")
            if existing.get("price_original") and float(existing.get("price_original")) > 0:
                price_orig = float(existing.get("price_original"))
            existing_specs = existing.get("specs_json") if isinstance(existing.get("specs_json"), dict) else {}
            if existing_specs.get("color_prices"):
                specs["color_prices"] = existing_specs["color_prices"]

        # Se houver variações de cor configuradas, definir preço principal a partir da variação principal/menor ativa
        if isinstance(specs.get("color_prices"), list) and specs["color_prices"]:
            active_cps = [cp for cp in specs["color_prices"] if cp.get("active", True) is not False]
            if active_cps:
                chosen_cp = next((cp for cp in active_cps if cp.get("is_main")), None)
                if not chosen_cp:
                    chosen_cp = min(
                        active_cps,
                        key=lambda cp: parse_currency(cp.get("price") or "") or float("inf"),
                    )
                cp_price = parse_currency(chosen_cp.get("price") or "")
                if cp_price > 0:
                    price_out = cp_price
                    cp_p12 = parse_currency(chosen_cp.get("p12") or "")
                    cp_p18 = parse_currency(chosen_cp.get("p18") or "")
                    inst12_val = cp_p12 if cp_p12 > 0 else round((price_out * 1.1013216) / 12, 2)
                    inst18_val = cp_p18 if cp_p18 > 0 else round((price_out * 1.1437722) / 18, 2)

        if not main_img:
            slug_img = re.sub(r"[^\w]", "-", model_name.lower())
            slug_img = re.sub(r"-+", "-", slug_img).strip("-")
            main_img = f"https://raw.githubusercontent.com/marketingmajv/MOne/main/public/images/{slug_img}/{slug_img}-01.jpg"

        inst_text = ""
        if inst12_val > 0:
            inst_text = f"12x de R$ {inst12_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        show_on_demand_val = bool(existing.get("show_on_demand")) if existing else False
        show_color_prices_val = True if (not existing or existing.get("show_color_prices") is None) else bool(existing.get("show_color_prices"))

        item_dict = {
            "slug": slug,
            "name": model_name,
            "category": category,
            "condition": conditions_str,
            "color": colors_str,
            "price_original": price_orig,
            "price_outlet": price_out,
            "installment_12": inst12_val,
            "installment_18": inst18_val,
            "installments_text": inst_text,
            "stock_qty": grp["total_qty"],
            "show_on_demand": show_on_demand_val,
            "show_color_prices": show_color_prices_val,
            "location": ", ".join(grp["locations"]),
            "badge": badge,
            "specs_json": specs,
            "description": desc,
            "image_main": main_img,
            "images_gallery": gallery,
            "status": "active" if (grp["total_qty"] > 0 or show_on_demand_val) else "sold_out",
            "sort_order": order,
            "notes": f"Lote promocional. Cores: {colors_str}. Observações: {'; '.join(grp['observations'])}",
        }

        save_outlet_item(item_dict, item_id=existing.get("id") if existing else None)
        synced_count += 1
        total_stock += grp["total_qty"]
        order += 1

    # Registrar metadados do último sync sem resetar nenhuma configuração
    try:
        from datetime import datetime
        from services.outlet_service import set_outlet_setting
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        set_outlet_setting("outlet_last_sync_at", now_str)
        set_outlet_setting("outlet_last_sync_summary", f"{synced_count} modelos ({total_stock} unidades)")
    except Exception as e:
        logger.warning("Aviso ao salvar metadados do último sync: %s", e)

    return {
        "synced_count": synced_count,
        "total_stock": total_stock,
        "models": list(model_groups.keys()),
    }
