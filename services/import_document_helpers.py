from __future__ import annotations

import re
from datetime import date
from typing import Any


def clean_float(val: Any) -> float:
    """Converte com segurança valores numéricos ou strings formatadas (ex: 'R$ 1.500,00', '1,500.00') em float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return 0.0
    s = re.sub(r"[^\d.,-]", "", s)
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_date_safe(val: Any) -> str | None:
    """Converte qualquer string ou data (ex: '11/09/2026', '11/09/26', '2026-09-11') em formato ISO 'YYYY-MM-DD' aceito pelo PostgreSQL."""
    if not val:
        return None
    s = str(val).strip()
    if not s or s.lower() in ["null", "none", "n/d", "—", "undefined"]:
        return None

    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s

    m = re.match(r"^(\d{1,2})[\/\.-](\d{1,2})[\/\.-](\d{2,4})$", s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day).strftime("%Y-%m-%d")
        except Exception:
            return None

    return None


def extract_amount_from_doc(extracted_data: dict[str, Any], text_content: str = "", filename: str = "") -> float:
    """Extrai o valor numérico de forma resiliente via IA, dicionário ou regex no texto do arquivo."""
    # 1. Tentar chaves conhecidas do JSON retornado pela IA
    if isinstance(extracted_data, dict):
        possible_keys = [
            "total_amount", "amount", "valor_total", "valor", "total",
            "amount_brl", "total_brl", "valor_adiantamento", "valor_despesa",
            "net_amount", "gross_amount", "val_total", "valor_liquido", "value",
            "total_a_depositar", "total_geral"
        ]
        for k in possible_keys:
            if k in extracted_data and extracted_data[k] is not None:
                v = clean_float(extracted_data[k])
                if v > 0:
                    return v

        for k, v in extracted_data.items():
            k_lower = str(k).lower()
            if isinstance(v, (int, float)) and v > 0 and not any(sub in k_lower for sub in ["date", "rate", "number", "hash", "id", "year", "sku", "qty", "quantity"]):
                return float(v)
            elif isinstance(v, str) and any(sub in k_lower for sub in ["valor", "amount", "total", "preco", "custo"]):
                v_clean = clean_float(v)
                if v_clean > 0:
                    return v_clean

    # 2. Tentar busca direcionada por padrões de TOTAL no texto do PDF/documento
    if text_content:
        total_patterns = [
            r"(?:TOTAL\s+A\s+DEPOSITAR|TOTAL\s+GERAL(?:\s+DAS\s+DESPESAS)?|TOTAL\s+GERAL|TOTAL\s+A\s+PAGAR|VALOR\s+TOTAL|TOTAL\s+DESPESAS)\s*(?:[A-Z0-9\s]{0,30})?[:\s]*R?\$\s*([\d\.\,]+)",
            r"(?:TOTAL|VALOR|LIQUIDO|DEBITO|ADIANTAMENTO|SOLICITADO|DEPOSITAR)[^\d\n\r]{0,35}?R?\$\s*([\d\.\,]+)",
        ]
        for pat in total_patterns:
            matches = re.findall(pat, text_content, re.IGNORECASE)
            for m in matches:
                v = clean_float(m)
                if v > 0:
                    return v

        # 3. Se nenhuma linha de total específica deu match, pegar todos os números formatados como moeda brasileira (ex: 187.169,74)
        currency_matches = re.findall(r"(?:^|[^\d])([\d]{1,3}(?:\.[\d]{3})*\,[\d]{2})(?:[^\d]|$)", text_content)
        valid_amounts = []
        for m in currency_matches:
            v = clean_float(m)
            if 10.0 <= v <= 50_000_000.0:
                valid_amounts.append(v)

        if valid_amounts:
            return max(valid_amounts)

    return 0.0
