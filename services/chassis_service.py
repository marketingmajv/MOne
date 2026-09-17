"""
M-One Chassis Import & Parsing Service (services/chassis_service.py)
Processamento e validação de planilhas de chassis (CSV e XLSX).
"""

from __future__ import annotations

import csv
import io
import logging

try:
    from openpyxl import load_workbook
except Exception:
    load_workbook = None

logger = logging.getLogger(__name__)


def normalize_headers(headers: list) -> list[str]:
    """Normaliza cabeçalhos removendo acentos e espaços."""
    out = []
    for h in headers:
        s = str(h or "").strip().lower()
        s = (
            s.replace("ç", "c")
            .replace("ã", "a")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
        )
        out.append(s)
    return out


def parse_chassis_file(file_storage) -> list[dict[str, str]]:
    """Lê arquivo CSV ou XLSX e extrai lista de dicionários de chassis."""
    ext = file_storage.filename.rsplit(".", 1)[1].lower() if "." in file_storage.filename else ""
    data = file_storage.read()
    if ext == "csv":
        text = data.decode("utf-8-sig", errors="replace")
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ";"
        reader = csv.reader(io.StringIO(text), dialect)
        all_rows = list(reader)
    elif ext in ["xlsx", "xls"]:
        if load_workbook is None:
            raise ValueError("Suporte a XLSX indisponível. Instale openpyxl.")
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        all_rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]
    else:
        raise ValueError("Use CSV ou XLSX para a planilha de chassis.")

    if not all_rows:
        return []

    headers = normalize_headers(all_rows[0])

    def idx(candidates: list[str]):
        for c in candidates:
            if c in headers:
                return headers.index(c)
        return None

    i_model = idx(["modelo", "model", "produto", "product"])
    i_chassis = idx(["chassi", "chassis", "quadro", "frame", "frame no", "frame number", "vin"])
    i_motor = idx(["motor", "motor no", "motor number", "numero do motor", "n motor"])
    i_color = idx(["cor", "color", "colour"])

    if i_model is None or i_chassis is None:
        raise ValueError("A planilha precisa ter pelo menos as colunas MODELO e CHASSI.")

    rows = []
    for raw in all_rows[1:]:
        model = str(raw[i_model] or "").strip() if i_model < len(raw) else ""
        chassis = str(raw[i_chassis] or "").strip() if i_chassis < len(raw) else ""
        motor = str(raw[i_motor] or "").strip() if i_motor is not None and i_motor < len(raw) else ""
        color = str(raw[i_color] or "").strip() if i_color is not None and i_color < len(raw) else ""
        if model and chassis:
            rows.append({"model": model, "chassis": chassis, "motor": motor, "color": color})

    return rows


def check_duplicate_chassis(chassis_numbers: list[str]) -> list[str]:
    """Retorna lista de chassis que já constam cadastrados no banco de dados."""
    if not chassis_numbers:
        return []
    try:
        from database import db
        with db() as conn:
            # Consulta em blocos de até 200 itens
            duplicates = []
            chunk_size = 200
            for i in range(0, len(chassis_numbers), chunk_size):
                chunk = [c.strip() for c in chassis_numbers[i : i + chunk_size] if c and c.strip()]
                if not chunk:
                    continue
                placeholders = ", ".join(["%s"] * len(chunk))
                rows = conn.execute(
                    f"SELECT chassis FROM stock_units WHERE UPPER(chassis) IN ({placeholders});",
                    tuple(c.upper() for c in chunk),
                ).fetchall()
                duplicates.extend([r["chassis"] for r in rows])
            return duplicates
    except Exception as e:
        logger.warning("[check_duplicate_chassis] Falha ao verificar duplicatas: %s", e)
        return []

