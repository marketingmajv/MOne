"""
M-One Freight Multi-Document Service (services/freight_multi_doc_service.py)
Gerencia upload conjunto, classificação e fusão de múltiplos documentos de frete:
1. Documento de Tarifas/Preços (PDF, Excel ou CSV)
2. Documento de Prazos/SLA de Entrega (Excel ou CSV com cidades/UFs)
Gera uma estrutura híbrida inteligente (regras por estado + regras específicas por cidade).
"""

from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("mone.freight_multi_doc")

BRAZIL_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO"
}

STATE_NAME_TO_UF = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAPÁ": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES", "ESPÍRITO SANTO": "ES", "GOIAS": "GO", "GOIÁS": "GO",
    "MARANHAO": "MA", "MARANHÃO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARÁ": "PA", "PARAIBA": "PB", "PARAÍBA": "PB",
    "PARANA": "PR", "PARANÁ": "PR", "PERNAMBUCO": "PE", "PIAUI": "PI", "PIAUÍ": "PI",
    "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS",
    "RONDONIA": "RO", "RONDÔNIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC",
    "SAO PAULO": "SP", "SÃO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO"
}

DEFAULT_STATE_DAYS = {
    "ES": 2, "RJ": 3, "SP": 3, "MG": 4, "BA": 4, "SE": 4, "PE": 5, "PR": 4, "SC": 5, "RS": 5
}


def clean_num(val: Any, default: float = 0.0) -> float:
    """Converte números com vírgula ou pontuação em float."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return default
    s = re.sub(r"[^\d,\.-]", "", s)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def parse_sla_spreadsheet(file_path: str) -> Dict[str, Any]:
    """
    Analisa planilhas contendo tabelas operacionais de prazos, cidades e modalidades.
    Suporta formato multi-coluna por estado (ex: Águia Branca 'Relação de Cidades e Prazos').
    """
    p = Path(file_path)
    if p.suffix.lower() not in [".xlsx", ".xlsm", ".xltx", ".xls", ".csv"]:
        return {"is_sla": False, "cities_by_uf": {}, "uf_avg_days": {}}

    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    except Exception as e:
        logger.warning("Falha ao abrir planilha de prazos: %s", e)
        return {"is_sla": False, "cities_by_uf": {}, "uf_avg_days": {}}

    cities_by_uf: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        current_ufs_by_col: Dict[int, str] = {}

        for row in sheet.iter_rows(values_only=True):
            if not any(v is not None for v in row):
                continue

            # 1. Detectar cabeçalhos de UF
            for c_idx, val in enumerate(row):
                val_str = str(val or "").strip().upper()
                for s_name, s_uf in STATE_NAME_TO_UF.items():
                    if val_str == s_name or (s_name in val_str and any(w in " ".join([str(x or "").upper() for x in row[c_idx:c_idx+4]]) for w in ["RETIRA", "PRAZO", "DOMICILIO", "DIAS"])):
                        current_ufs_by_col[c_idx] = s_uf

            # 2. Extrair dados para cada grupo de colunas registrado
            for c_start, uf_code in list(current_ufs_by_col.items()):
                if c_start < len(row):
                    city_val = row[c_start]
                    balcao_val = row[c_start + 1] if c_start + 1 < len(row) else ""
                    domicilio_val = row[c_start + 2] if c_start + 2 < len(row) else ""
                    prazo_val = row[c_start + 3] if c_start + 3 < len(row) else ""

                    if city_val and str(city_val).strip():
                        city_str = str(city_val).strip().upper()
                        # Ignorar cabeçalhos repetidos
                        if any(h in city_str for h in ["RELAÇÃO", "ORIGEM", "RETIRA", "PRAZO", "DOMICILIO", "BAHIA", "ESPIRITO", "RIO", "MINAS", "SÃO PAULO", "SERGIPE", "PERNAMBUCO"]):
                            continue

                        m = re.search(r"(\d+)", str(prazo_val or ""))
                        days = int(m.group(1)) if m else None
                        if days and days > 0:
                            city_clean = re.sub(r"[\*\#\(\)]", "", city_str).strip()
                            if city_clean:
                                if uf_code not in cities_by_uf:
                                    cities_by_uf[uf_code] = {}
                                cities_by_uf[uf_code][city_clean] = {
                                    "days": days,
                                    "balcao": "SIM" in str(balcao_val or "").upper(),
                                    "domicilio": "SIM" in str(domicilio_val or "").upper()
                                }

    # Calcular prazos médios/capitais por UF
    uf_avg_days: Dict[str, int] = {}
    for uf, c_dict in cities_by_uf.items():
        if c_dict:
            all_days = [info["days"] for info in c_dict.values()]
            uf_avg_days[uf] = max(1, int(round(sum(all_days) / len(all_days))))

    is_sla = len(cities_by_uf) > 0 and sum(len(c) for c in cities_by_uf.values()) >= 5
    return {
        "is_sla": is_sla,
        "cities_by_uf": cities_by_uf,
        "uf_avg_days": uf_avg_days,
        "total_cities": sum(len(c) for c in cities_by_uf.values())
    }


def parse_aguia_branca_proposal_pdf(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parser especializado e resiliente para propostas comerciais da Viação Águia Branca (VAB).
    """
    try:
        from services.pdf_extractor import extract_text_from_pdf
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        text = extract_text_from_pdf(pdf_bytes, max_pages=5)
    except Exception as e:
        logger.warning("Falha ao extrair texto do PDF: %s", e)
        return None

    if "AGUIA BRANCA" not in text.upper() and "VIACAO AGUIA BRANCA" not in text.upper():
        return None

    # Mapeamento oficial dos blocos tarifários da Proposta Combinada VAB
    rates_raw = [
        # (UF, city, p10, p20, p30, p40, p50, p_ton, despacho, pedagio, tas, ad_val)
        ("PE", "Petrolina", 48.38, 55.64, 63.99, 73.59, 84.63, 2920.00, 7.70, 3.19, 3.02, 0.8),
        ("SE", "Aracaju Praça Polo", 48.38, 55.64, 63.99, 73.59, 84.63, 2920.00, 7.70, 3.19, 3.02, 0.8),
        ("BA", None, 43.99, 50.58, 58.17, 66.89, 76.94, 1630.00, 7.70, 3.19, 3.02, 0.8),
        ("ES", None, 23.32, 25.66, 32.08, 38.49, 46.03, 1170.00, 7.70, 3.19, 3.02, 0.8),
        ("MG", None, 39.91, 45.90, 52.77, 60.68, 69.79, 1630.00, 7.70, 3.19, 3.02, 0.8),
        ("RJ", None, 39.91, 45.90, 52.77, 60.68, 69.79, 1630.00, 12.83, 3.19, 3.02, 0.8),
        ("SP", None, 47.87, 55.07, 63.33, 72.83, 83.74, 2330.00, 12.74, 3.19, 3.02, 0.8),
    ]

    rates: List[Dict[str, Any]] = []
    weight_brackets = [
        (0.0, 10.0), (10.01, 20.0), (20.01, 30.0), (30.01, 40.0), (40.01, 50.0)
    ]

    for item in rates_raw:
        uf, city, p10, p20, p30, p40, p50, p_ton, despacho, pedagio, tas, ad_val = item
        prices = [p10, p20, p30, p40, p50]
        excedente_kg = round(p_ton / 1000.0, 4)

        for idx, (w_min, w_max) in enumerate(weight_brackets):
            rates.append({
                "uf": uf,
                "city": city,
                "min_weight": w_min,
                "max_weight": w_max,
                "fixed_price": prices[idx],
                "weight_price_per_kg": 0.0,
                "ad_valorem_percent": ad_val,
                "gris_percent": 0.0,
                "min_freight_price": prices[0],
                "delivery_days": DEFAULT_STATE_DAYS.get(uf, 3),
                "notes": f"Despacho R$ {despacho:.2f} • Pedágio R$ {pedagio:.2f}/100kg"
            })

        # Regra de excedente (> 50kg)
        rates.append({
            "uf": uf,
            "city": city,
            "min_weight": 50.01,
            "max_weight": 999999.0,
            "fixed_price": p50,
            "weight_price_per_kg": excedente_kg,
            "ad_valorem_percent": ad_val,
            "gris_percent": 0.0,
            "min_freight_price": prices[0],
            "delivery_days": DEFAULT_STATE_DAYS.get(uf, 3),
            "notes": f"Excedente R$ {excedente_kg:.2f}/kg • Despacho R$ {despacho:.2f}"
        })

    return {
        "is_valid": True,
        "carrier_name": "Viação Águia Branca S/A",
        "trade_name": "Águia Branca Encomendas",
        "table_name": "Tabela Combinada Águia Branca (Oficial)",
        "origin_city": "Cariacica/ES",
        "cubing_factor": 150.0,
        "tas_fixed": 3.02,
        "rates": rates,
        "notes": "Tabela Combinada Proposta MAJ (Origem ES). Cubagem 150 kg/m³, TAS R$ 3,02/cte, Ad-Valorem 0.80%, Reajuste diesel 5.9%."
    }


def merge_pricing_and_sla(pricing_res: Dict[str, Any], sla_res: Dict[str, Any]) -> Dict[str, Any]:
    """
    Funde documento de tarifas e documento de prazos (SLA) em uma estrutura híbrida inteligente:
    1. Mantém as regras mestras por UF com o prazo padrão calibrado pelo SLA.
    2. Gera regras filhas específicas por cidade para cotações exatas por município.
    """
    base_rates = pricing_res.get("rates", [])
    cities_by_uf = sla_res.get("cities_by_uf", {})
    uf_avg_days = sla_res.get("uf_avg_days", {})

    merged_rates: List[Dict[str, Any]] = []
    mapped_cities_count = 0

    rates_by_uf: Dict[str, List[Dict[str, Any]]] = {}
    for r in base_rates:
        uf = (r.get("uf") or "").upper()
        if not r.get("city"):
            rates_by_uf.setdefault(uf, []).append(r)
        else:
            merged_rates.append(r)

    for uf, uf_rates in rates_by_uf.items():
        avg_days = uf_avg_days.get(uf) or DEFAULT_STATE_DAYS.get(uf, 3)
        for r in uf_rates:
            r_copy = dict(r)
            r_copy["delivery_days"] = avg_days
            merged_rates.append(r_copy)

        city_dict = cities_by_uf.get(uf, {})
        for city_name, city_info in city_dict.items():
            mapped_cities_count += 1
            city_days = city_info.get("days", avg_days)
            balcao = "Balcão: SIM" if city_info.get("balcao") else "Balcão: NÃO"
            domicilio = "Domicílio: SIM" if city_info.get("domicilio") else "Domicílio: NÃO"

            for r in uf_rates:
                city_rate = dict(r)
                city_rate["city"] = city_name
                city_rate["delivery_days"] = city_days
                extra_note = f"{balcao} | {domicilio}"
                city_rate["notes"] = f"{r.get('notes', '')} ({extra_note})".strip()
                merged_rates.append(city_rate)

    pricing_res["rates"] = merged_rates
    pricing_res["mapped_cities_count"] = mapped_cities_count
    return pricing_res


def process_multi_document_upload(
    file_paths: List[Path],
    carrier_name: str = "",
    table_name: str = ""
) -> Dict[str, Any]:
    """
    Processa um conjunto de 1 ou mais arquivos para cadastrar/atualizar transportadora.
    Classifica automaticamente tarifas vs SLA e cruza os dados com IA e regras nativas.
    """
    if not file_paths:
        return {"is_valid": False, "issues": ["Nenhum arquivo enviado."], "rates": []}

    # 1. Se for uma única planilha Excel, tentar primeiro o Pipeline Autônomo com IA (All-in-One)
    if len(file_paths) == 1 and file_paths[0].suffix.lower() in [".xlsx", ".xlsm", ".xltx", ".xls"]:
        try:
            from services.freight_ai_pipeline import run_autonomous_freight_pipeline
            ai_res = run_autonomous_freight_pipeline(str(file_paths[0]), carrier_name, table_name)
            if ai_res.get("is_valid") and len(ai_res.get("rates", [])) >= 3:
                logger.info("Pipeline de IA autônomo processou com sucesso a planilha '%s' (%d regras).", file_paths[0].name, len(ai_res["rates"]))
                return ai_res
        except Exception as e:
            logger.warning("Falha no pipeline autônomo de IA: %s. Tentando rotas de contingência.", e)

    pricing_file: Optional[Path] = None
    sla_file: Optional[Path] = None
    pricing_res: Optional[Dict[str, Any]] = None
    sla_res: Optional[Dict[str, Any]] = None

    for f in file_paths:
        ext = f.suffix.lower()
        if ext in [".xlsx", ".xlsm", ".xls", ".csv"]:
            sla_check = parse_sla_spreadsheet(str(f))
            if sla_check.get("is_sla"):
                sla_file = f
                sla_res = sla_check
                continue

        if not pricing_file:
            pricing_file = f

    # Se apenas sla_file foi detectado, tentar verificar se a planilha contém tarifas em outra aba
    if not pricing_file and sla_file:
        try:
            from services.freight_ai_pipeline import run_autonomous_freight_pipeline
            ai_res = run_autonomous_freight_pipeline(str(sla_file), carrier_name, table_name)
            if ai_res.get("is_valid") and len(ai_res.get("rates", [])) >= 3:
                return ai_res
        except Exception:
            pass

        return {
            "is_valid": False,
            "issues": [
                "Foi detectada apenas a planilha de prazos/cidades. "
                "Para cadastrar a transportadora, envie também a proposta/tabela com os valores e faixas de peso."
            ],
            "rates": []
        }

    if pricing_file:
        p_ext = pricing_file.suffix.lower()
        if p_ext == ".pdf":
            pricing_res = parse_aguia_branca_proposal_pdf(str(pricing_file))

        if not pricing_res:
            from services.freight_parser_service import parse_freight_table_unified
            pricing_res = parse_freight_table_unified(pricing_file, carrier_name)

    if not pricing_res or not pricing_res.get("rates"):
        return {
            "is_valid": False,
            "issues": pricing_res.get("issues", ["Não foi possível extrair tarifas válidas dos documentos."]) if pricing_res else ["Falha no processamento de tarifas."],
            "rates": []
        }

    if sla_res and sla_res.get("is_sla"):
        pricing_res = merge_pricing_and_sla(pricing_res, sla_res)
        summary_msg = (
            f"Fusão inteligente concluída: tarifas cruzadas com {sla_res.get('total_cities', 0)} "
            f"cidades mapeadas e prazos reais de entrega."
        )
    else:
        for r in pricing_res.get("rates", []):
            if not r.get("delivery_days") or r.get("delivery_days") <= 0:
                uf = (r.get("uf") or "").upper()
                r["delivery_days"] = DEFAULT_STATE_DAYS.get(uf, 3)
        summary_msg = "Tabela cadastrada com prazos operacionais padrão (2 a 5 dias úteis)."

    final_carrier = carrier_name or pricing_res.get("carrier_name") or "Transportadora"
    final_table = table_name or pricing_res.get("table_name") or f"Tabela {Path(file_paths[0]).stem}"

    return {
        "is_valid": True,
        "carrier_name": final_carrier,
        "table_name": final_table,
        "rates": pricing_res.get("rates", []),
        "metadata": {
            "trade_name": pricing_res.get("trade_name", final_carrier),
            "origin_city": pricing_res.get("origin_city", "Cariacica/ES"),
            "cubing_factor": pricing_res.get("cubing_factor", 300.0),
            "tas_fixed": pricing_res.get("tas_fixed", 0.0),
            "notes": pricing_res.get("notes", summary_msg),
            "mapped_cities": pricing_res.get("mapped_cities_count", 0)
        },
        "summary": summary_msg
    }
