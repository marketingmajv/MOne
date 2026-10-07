"""
M-One Freight Parser Service (services/freight_parser_service.py)
Parser resiliente e híbrido para planilhas e documentos de frete rodoviário.
Combina extração determinística nativa (Excel/CSV) com auditoria via IA (Gemini) e fallback seguro.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

from services.gemini_client import execute_gemini_payload, get_gemini_api_key

logger = logging.getLogger("mone.freight_parser")

BRAZIL_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO"
}


def clean_numeric(val: Any, default: float = 0.0) -> float:
    """Converte valores com R$, %, separadores de milhar ou vírgula em float com segurança."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return default
    s = re.sub(r"[^\d,\.-]", "", s)
    if not s:
        return default
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def clean_int(val: Any, default: int = 1) -> int:
    """Converte valores para inteiro com fallback seguro."""
    f = clean_numeric(val, default=float(default))
    try:
        i = int(round(f))
        return i if i > 0 else default
    except Exception:
        return default


def clean_cep(cep: Any) -> Optional[str]:
    """Retorna CEP limpo com 8 dígitos numéricos ou None."""
    if not cep:
        return None
    c = re.sub(r"\D", "", str(cep)).strip()
    return c if len(c) == 8 else None


def parse_freight_spreadsheet_native(file_path: str, carrier_name: str) -> Dict[str, Any]:
    """
    Parser nativo determinístico para arquivos Excel (.xlsx, .xls) e CSV.
    Detecta automaticamente:
    1. Formato matricial de faixas de peso (UF, Tipo/Cidade, Até 20kg, Até 50kg, ..., Excedente/kg, Prazos)
    2. Formato tabular por linha (UF, Cidade, CEP, Peso Mín, Peso Máx, Preço, Excedente, Prazo)
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    raw_rows: List[List[Any]] = []

    if ext in [".xlsx", ".xlsm", ".xltx"]:
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            for sheetname in wb.sheetnames:
                sheet = wb[sheetname]
                for row in sheet.iter_rows(values_only=True):
                    if any(c is not None and str(c).strip() != "" for c in row):
                        raw_rows.append([c for c in row])
                if len(raw_rows) > 10:
                    break  # Usar primeira aba representativa
        except Exception as e:
            logger.warning("Falha ao abrir com openpyxl: %s", e)

    if not raw_rows:
        # Fallback CSV / TSV
        for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
            try:
                with open(file_path, "r", encoding=enc, errors="ignore") as f:
                    content = f.read(200000)
                    delim = ";" if ";" in content[:2000] else ("," if "," in content[:2000] else "\t")
                    reader = csv.reader(io.StringIO(content), delimiter=delim)
                    for r in reader:
                        if any(c.strip() for c in r):
                            raw_rows.append(r)
                if raw_rows:
                    break
            except Exception:
                pass

    if not raw_rows or len(raw_rows) < 2:
        return {"is_valid": False, "issues": ["Arquivo vazio ou sem linhas legíveis."], "rates": []}

    # 1. Localizar linha de cabeçalho
    header_idx = -1
    for idx, row in enumerate(raw_rows[:15]):
        str_cells = " ".join([str(c or "").upper() for c in row])
        if ("UF" in str_cells or "ESTADO" in str_cells or "DESTINO" in str_cells) and any(w in str_cells for w in ["KG", "PESO", "PRAZO", "DIAS", "VALOR", "TARIFA", "CAPITAL", "INTERIOR"]):
            header_idx = idx
            break

    if header_idx == -1:
        # Tentar primeira linha com qualquer palavra-chave
        for idx, row in enumerate(raw_rows[:10]):
            str_cells = " ".join([str(c or "").upper() for c in row])
            if any(u in str_cells.split() for u in ["ES", "SP", "RJ", "MG", "BA"]):
                header_idx = max(0, idx - 1)
                break

    if header_idx == -1:
        header_idx = 0

    header = [str(c or "").strip() for c in raw_rows[header_idx]]
    data_rows = raw_rows[header_idx + 1:]

    rates: List[Dict[str, Any]] = []
    issues: List[str] = []

    # Identificar colunas especiais
    uf_col = -1
    city_col = -1
    days_col = -1
    adv_col = -1
    gris_col = -1
    fixed_tax_col = -1
    min_freight_col = -1
    over_kg_col = -1
    weight_bracket_cols: List[Tuple[int, float, float]] = []  # (col_idx, min_w, max_w)

    last_weight = 0.0
    for c_idx, col_name in enumerate(header):
        c_clean = col_name.upper().strip()
        if not c_clean:
            continue

        if re.search(r"\b(UF|ESTADO|SIGLA)\b", c_clean) and uf_col == -1:
            uf_col = c_idx
        elif any(k in c_clean for k in ["CIDADE", "MUNICIPIO", "LOCALIDADE", "REGIAO", "TIPO", "DESTINO"]) and city_col == -1:
            city_col = c_idx
        elif any(k in c_clean for k in ["PRAZO", "DIAS", "TRANSIT"]) and days_col == -1:
            days_col = c_idx
        elif any(k in c_clean for k in ["AD-VALOREM", "AD VALOREM", "ADV", "SEGURO"]):
            adv_col = c_idx
        elif "GRIS" in c_clean:
            gris_col = c_idx
        elif any(k in c_clean for k in ["TAXA", "DESPACHO", "PEDAGIO", "TRT", "TAXA FIXA"]):
            fixed_tax_col = c_idx
        elif any(k in c_clean for k in ["MINIMO", "FRETE MIN", "MIN"]):
            min_freight_col = c_idx
        elif any(k in c_clean for k in ["EXCED", "ADICIONAL", "SOBRA", "KG EXC", "POR KG", "EXC"]):
            over_kg_col = c_idx
        else:
            # Checar se é faixa de peso (ex: 'ATÉ 20KG', '20KG', '0-20', 'ATE 50')
            m_weight = re.search(r"(?:AT[EÉ]|\<|\<\=)?\s*(\d+(?:[,\.]\d+)?)\s*(?:KG)?", c_clean)
            if m_weight:
                try:
                    w_limit = clean_numeric(m_weight.group(1))
                    if 0 < w_limit <= 5000:
                        weight_bracket_cols.append((c_idx, last_weight, w_limit))
                        last_weight = w_limit + 0.01
                except Exception:
                    pass

    # Se não identificou coluna de UF pelo cabeçalho, checar primeira coluna onde os valores são siglas de estado
    if uf_col == -1:
        for c_idx in range(min(5, len(header))):
            sample_vals = [str(r[c_idx]).strip().upper() for r in data_rows[:10] if len(r) > c_idx and r[c_idx]]
            if sum(1 for v in sample_vals if v in BRAZIL_UFS) >= 2:
                uf_col = c_idx
                break

    if uf_col == -1:
        uf_col = 0

    if city_col == -1 and len(header) > 1 and uf_col != 1:
        city_col = 1

    # PARSEAMENTO LINHA A LINHA
    for r in data_rows:
        if not r or len(r) <= uf_col:
            continue

        raw_uf = str(r[uf_col]).strip().upper() if len(r) > uf_col and r[uf_col] else ""
        if len(raw_uf) > 2 and raw_uf not in BRAZIL_UFS:
            # Tentar encontrar UF embutida
            m_uf = re.search(r"\b([A-Z]{2})\b", raw_uf)
            if m_uf and m_uf.group(1) in BRAZIL_UFS:
                raw_uf = m_uf.group(1)
            else:
                continue
        elif raw_uf not in BRAZIL_UFS:
            continue

        raw_city = str(r[city_col]).strip() if city_col != -1 and len(r) > city_col and r[city_col] else "Geral"
        days = clean_int(r[days_col], default=3 if "CAPITAL" in raw_city.upper() else 5) if days_col != -1 and len(r) > days_col else (3 if "CAPITAL" in raw_city.upper() else 5)
        adv = clean_numeric(r[adv_col], default=0.30) if adv_col != -1 and len(r) > adv_col else 0.30
        if adv > 5.0:  # Se veio em percentual inteiro (ex: 30 ao invés de 0.30)
            adv = adv / 100.0

        gris = clean_numeric(r[gris_col], default=0.20) if gris_col != -1 and len(r) > gris_col else 0.20
        if gris > 5.0:
            gris = gris / 100.0

        tax_fixa = clean_numeric(r[fixed_tax_col], default=0.0) if fixed_tax_col != -1 and len(r) > fixed_tax_col else 0.0
        min_freight = clean_numeric(r[min_freight_col], default=0.0) if min_freight_col != -1 and len(r) > min_freight_col else 0.0

        # CASO 1: Tabela matricial com colunas de faixa de peso
        if weight_bracket_cols:
            for c_bracket, w_min, w_max in weight_bracket_cols:
                if len(r) > c_bracket and r[c_bracket] is not None:
                    p_val = clean_numeric(r[c_bracket])
                    if p_val > 0:
                        rates.append({
                            "uf": raw_uf,
                            "city": raw_city,
                            "cep_start": None,
                            "cep_end": None,
                            "min_weight": w_min,
                            "max_weight": w_max,
                            "fixed_price": round(p_val + tax_fixa, 2),
                            "weight_price_per_kg": 0.0,
                            "ad_valorem_percent": adv,
                            "gris_percent": gris,
                            "min_freight_price": min_freight,
                            "delivery_days": days,
                            "notes": f"{carrier_name} {raw_uf} {raw_city}"
                        })

            # Se houver taxa de kg excedente
            if over_kg_col != -1 and len(r) > over_kg_col and r[over_kg_col] is not None:
                over_price = clean_numeric(r[over_kg_col])
                if over_price > 0:
                    last_max = weight_bracket_cols[-1][2] if weight_bracket_cols else 100.0
                    last_price = clean_numeric(r[weight_bracket_cols[-1][0]]) if weight_bracket_cols else 100.0
                    fixed_base = max(0.0, last_price + tax_fixa - (last_max * over_price))
                    rates.append({
                        "uf": raw_uf,
                        "city": raw_city,
                        "cep_start": None,
                        "cep_end": None,
                        "min_weight": round(last_max + 0.01, 2),
                        "max_weight": 999999.0,
                        "fixed_price": round(fixed_base, 2),
                        "weight_price_per_kg": over_price,
                        "ad_valorem_percent": adv,
                        "gris_percent": gris,
                        "min_freight_price": min_freight,
                        "delivery_days": days,
                        "notes": f"{carrier_name} {raw_uf} {raw_city} Excedente"
                    })

        # CASO 2: Linha única com tarifa geral
        else:
            # Procurar primeira coluna numérica válida para preço
            found_price = 0.0
            for idx_val in range(len(r)):
                if idx_val not in [uf_col, city_col, days_col]:
                    v_num = clean_numeric(r[idx_val])
                    if v_num > 10.0:
                        found_price = v_num
                        break

            if found_price > 0:
                rates.append({
                    "uf": raw_uf,
                    "city": raw_city,
                    "cep_start": None,
                    "cep_end": None,
                    "min_weight": 0.0,
                    "max_weight": 999999.0,
                    "fixed_price": round(found_price + tax_fixa, 2),
                    "weight_price_per_kg": 0.0,
                    "ad_valorem_percent": adv,
                    "gris_percent": gris,
                    "min_freight_price": min_freight,
                    "delivery_days": days,
                    "notes": f"{carrier_name} {raw_uf} {raw_city}"
                })

    if rates:
        ufs_found = sorted(list({r["uf"] for r in rates if r.get("uf")}))
        return {
            "is_valid": True,
            "issues": [f"Parser nativo extraiu {len(rates)} faixas tarifárias atendendo as UFs: {', '.join(ufs_found)}."],
            "rates": rates,
            "method": "native_spreadsheet"
        }

    return {
        "is_valid": False,
        "issues": ["Não foi possível identificar colunas de tarifas ou pesos na estrutura da planilha."],
        "rates": []
    }


def parse_freight_table_unified(file_path: str, carrier_name: str) -> Dict[str, Any]:
    """
    Função mestra unificada:
    1. Para arquivos Excel (.xlsx, .xls) e CSV, tenta primeiro o parser determinístico nativo.
    2. Se for PDF ou se a planilha for complexa/não tabulada, aciona o Gemini com múltiplos modelos.
    3. Se o Gemini falhar por 503/timeout e o arquivo for planilha, usa o resultado nativo como garantia operacional.
    """
    file_path = str(file_path)
    p = Path(file_path)
    ext = p.suffix.lower()

    # 1. Tentativa Nativa Direta para Planilhas
    native_res = None
    if ext in [".xlsx", ".xlsm", ".xltx", ".xls", ".csv", ".tsv"]:
        try:
            native_res = parse_freight_spreadsheet_native(file_path, carrier_name)
            if native_res.get("is_valid") and len(native_res.get("rates", [])) >= 3:
                logger.info("Planilha de frete '%s' importada nativamente com sucesso (%d regras).", carrier_name, len(native_res["rates"]))
                return native_res
        except Exception as e:
            logger.warning("Falha na tentativa nativa: %s", e)

    # 2. Acionar Gemini se for PDF ou se o parser nativo precisou de auxílio
    from freight_service import parse_freight_table_with_gemini
    try:
        gemini_res = parse_freight_table_with_gemini(file_path, carrier_name)
        if gemini_res.get("is_valid") and len(gemini_res.get("rates", [])) > 0:
            return gemini_res
    except Exception as e:
        logger.warning("Gemini parser error: %s", e)

    # 3. Fallback: se Gemini falhou e tínhamos qualquer regra nativa, usa a nativa
    if native_res and native_res.get("rates") and len(native_res["rates"]) > 0:
        native_res["is_valid"] = True
        return native_res

    # 4. Se for PDF e a IA falhou
    return {
        "is_valid": False,
        "issues": [
            "Não foi possível extrair faixas tarifárias legíveis do documento. "
            "Certifique-se de que o arquivo contém colunas claras de UF, faixa de peso (ex: 20kg, 50kg, 100kg), "
            "valores e prazos de entrega estimados."
        ],
        "rates": []
    }


def inspect_freight_document_metadata(file_path: str, filename: str = "") -> Dict[str, Any]:
    """
    Inspeciona documento de frete (PDF, Excel, CSV) via heurísticas locais e IA Gemini
    para auto-preencher Transportadora, Nome da Tabela, Fator de Cubagem e Observações.
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    doc_text = ""

    # Extração de texto para inspeção preliminar
    if ext == ".pdf":
        try:
            from services.pdf_extractor import extract_text_from_pdf
            with open(file_path, "rb") as f:
                doc_text = extract_text_from_pdf(f.read(), max_pages=4, max_chars=16000)
        except Exception as e:
            logger.warning("Falha ao extrair texto do PDF para metadados: %s", e)
    elif ext in [".xlsx", ".xlsm", ".xltx", ".xls", ".csv", ".tsv"]:
        try:
            from freight_service import extract_text_from_spreadsheet
            doc_text = extract_text_from_spreadsheet(str(file_path))[:16000]
        except Exception as e:
            logger.warning("Falha ao extrair texto da planilha para metadados: %s", e)

    carrier_guess = ""
    table_guess = ""
    cubing_guess = 300.0

    lower_text = (doc_text + " " + filename).lower()
    if "aguia branca" in lower_text or "águia branca" in lower_text or "vab" in lower_text:
        carrier_guess = "Viação Águia Branca S/A"
        table_guess = "Tabela Combinada (ES para BA, MG, RJ, SP, PE, SE)"
        cubing_guess = 150.0
    elif "vinislog" in lower_text:
        carrier_guess = "Vinislog Cargas & Encomendas"
        table_guess = "Tabela Operacional Vinislog"
    elif "generoso" in lower_text:
        carrier_guess = "Transporte Generoso"
        table_guess = "Tabela Comercial Generoso"
    elif "tjb" in lower_text:
        carrier_guess = "TJB Transportes"
        table_guess = "Tabela Cargas Fracionadas TJB"
    elif "jamef" in lower_text:
        carrier_guess = "Jamef Encomendas Urgentes"
    elif "braspress" in lower_text:
        carrier_guess = "Braspress Transportes"

    m_cub = re.search(r"cubagem\s*[-:]?\s*(\d+(?:[,\.]\d+)?)\s*(?:kg/m3|kg)", doc_text, re.IGNORECASE)
    if m_cub:
        cubing_guess = clean_numeric(m_cub.group(1), cubing_guess)

    # Refinamento profundo com Gemini se houver API Key e texto
    api_key = get_gemini_api_key()
    if api_key and doc_text.strip():
        prompt = (
            "Você é um assistente logístico do sistema M-One (MAJ Mobilidade). "
            "Analise este trecho de proposta/tabela de frete e extraia os metadados principais para cadastrar a transportadora.\n"
            "Regras obrigatórias:\n"
            "- 'carrier_name': Razão social ou nome fantasia da transportadora emitente/prestadora (NÃO use o nome do cliente 'MAJ Confecções', use a transportadora!).\n"
            "- 'table_name': Nome descritivo da tabela ou regiões atendidas (ex: 'Tabela Combinada (ES para BA, MG, RJ, SP, PE, SE)' ou 'Região Sudeste 2026').\n"
            "- 'cubing_factor': Número do fator de cubagem em kg/m³ (ex: 150.0 ou 300.0). Padrão 300.0 se não constar.\n"
            "- 'origin_city': Cidade/UF de origem identificada (ex: 'Cariacica/ES' ou 'ES').\n"
            "- 'notes': Resumo conciso de taxas (seguro, despacho, vigência).\n\n"
            "Retorne ESTRITAMENTE um JSON no formato:\n"
            '{\n  "carrier_name": "...",\n  "table_name": "...",\n  "cubing_factor": 150.0,\n  "origin_city": "...",\n  "notes": "..."\n}\n\n'
            f"CONTEÚDO DO DOCUMENTO:\n{doc_text[:12000]}"
        )
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}
            }
            res = execute_gemini_payload(payload, api_key=api_key, timeout=15)
            if res.get("success"):
                match = re.search(r"```json\s*(.*?)\s*```", res.get("text", ""), re.DOTALL)
                raw_json = match.group(1) if match else res.get("text", "")
                parsed = json.loads(raw_json)
                c_name = parsed.get("carrier_name") or carrier_guess
                t_name = parsed.get("table_name") or table_guess
                c_factor = clean_numeric(parsed.get("cubing_factor"), cubing_guess)
                return {
                    "success": True,
                    "carrier_name": str(c_name).strip(),
                    "table_name": str(t_name).strip(),
                    "cubing_factor": c_factor,
                    "origin_city": parsed.get("origin_city", "Cariacica/ES"),
                    "notes": parsed.get("notes", ""),
                    "source": "gemini_ai"
                }
        except Exception as err:
            logger.warning("Falha ao analisar metadados com Gemini: %s", err)

    # Fallback heurístico inteligente
    if not carrier_guess:
        clean_fn = Path(filename).stem.replace("_", " ").replace("-", " ").title()
        carrier_guess = clean_fn
    if not table_guess:
        table_guess = f"Tabela {Path(filename).stem.replace('_', ' ').title()}"

    return {
        "success": True,
        "carrier_name": carrier_guess.strip(),
        "table_name": table_guess.strip(),
        "cubing_factor": cubing_guess,
        "origin_city": "Cariacica/ES",
        "notes": "Extraído via leitura determinística de cabeçalho",
        "source": "heuristic"
    }

