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


def extract_text_from_spreadsheet(file_bytes: bytes, filename: str) -> str:
    """Extrai texto tabular estruturado de planilhas CSV ou XLSX para envio ao modelo de IA."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        try:
            text = file_bytes.decode("utf-8-sig", errors="replace")
            return "\n".join(text.splitlines()[:150])
        except Exception:
            return ""

    if ext in ["xlsx", "xls"]:
        if load_workbook is None:
            return ""
        try:
            wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            lines: list[str] = []
            for sheetname in wb.sheetnames[:3]:
                ws = wb[sheetname]
                lines.append(f"[Aba: {sheetname}]")
                row_count = 0
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c).strip() if c is not None else "" for c in row]
                    if any(cells):
                        lines.append(" | ".join(cells[:15]))
                        row_count += 1
                        if row_count >= 80:
                            lines.append(f"... (+ linhas na aba {sheetname})")
                            break
            return "\n".join(lines)
        except Exception as err:
            logger.warning("[extract_text_from_spreadsheet] Falha ao extrair texto da planilha %s: %s", filename, err)
            return ""
    return ""


def parse_chassis_file(file_storage) -> list[dict[str, str]]:
    """Lê arquivo CSV ou XLSX e extrai lista de dicionários de chassis com detecção tolerante a cabeçalhos."""
    ext = file_storage.filename.rsplit(".", 1)[1].lower() if "." in file_storage.filename else ""
    data = file_storage.read()
    all_sheets_rows: list[list[list]] = []

    if ext == "csv":
        text = data.decode("utf-8-sig", errors="replace")
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ";"
        reader = csv.reader(io.StringIO(text), dialect)
        all_sheets_rows.append(list(reader))
    elif ext in ["xlsx", "xls"]:
        if load_workbook is None:
            raise ValueError("Suporte a XLSX indisponível. Instale openpyxl.")
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        for sname in wb.sheetnames:
            ws = wb[sname]
            sheet_rows = [[cell for cell in row] for row in ws.iter_rows(values_only=True)]
            if sheet_rows:
                all_sheets_rows.append(sheet_rows)
    else:
        raise ValueError("Use CSV ou XLSX para a planilha de chassis.")

    candidates_chassis = [
        "chassi", "chassis", "quadro", "frame", "frame no", "frame number", "vin",
        "serial", "serial no", "serial number", "numero do chassi", "n chassi", "numero chassi",
        "nº chassi", "chassi nº"
    ]
    candidates_model = [
        "modelo", "model", "produto", "product", "descricao", "description", "item",
        "mercadoria", "tipo", "veiculo", "desc", "especificacao"
    ]
    candidates_motor = ["motor", "motor no", "motor number", "numero do motor", "n motor", "engine", "engine no"]
    candidates_color = ["cor", "color", "colour"]

    for all_rows in all_sheets_rows:
        if not all_rows:
            continue

        # Procurar a linha de cabeçalho nas primeiras 15 linhas
        header_row_idx = None
        i_chassis = None
        i_model = None
        i_motor = None
        i_color = None

        max_scan = min(15, len(all_rows))
        for r_idx in range(max_scan):
            row_normalized = normalize_headers(all_rows[r_idx])
            for ch_cand in candidates_chassis:
                if ch_cand in row_normalized:
                    i_chassis = row_normalized.index(ch_cand)
                    header_row_idx = r_idx
                    break
            if header_row_idx is not None:
                # Encontrou a linha de cabeçalhos! Mapear demais colunas
                for md_cand in candidates_model:
                    if md_cand in row_normalized:
                        i_model = row_normalized.index(md_cand)
                        break
                for mot_cand in candidates_motor:
                    if mot_cand in row_normalized:
                        i_motor = row_normalized.index(mot_cand)
                        break
                for col_cand in candidates_color:
                    if col_cand in row_normalized:
                        i_color = row_normalized.index(col_cand)
                        break
                break

        if i_chassis is None:
            continue

        rows = []
        for raw in all_rows[header_row_idx + 1:]:
            chassis = str(raw[i_chassis] or "").strip() if i_chassis < len(raw) else ""
            if not chassis or len(chassis) < 4:
                continue
            if chassis.lower() in candidates_chassis:
                continue

            model = str(raw[i_model] or "").strip() if (i_model is not None and i_model < len(raw)) else "Veículo Elétrico"
            if not model:
                model = "Veículo Elétrico"
            motor = str(raw[i_motor] or "").strip() if (i_motor is not None and i_motor < len(raw)) else ""
            color = str(raw[i_color] or "").strip() if (i_color is not None and i_color < len(raw)) else ""

            rows.append({"model": model, "chassis": chassis, "motor": motor, "color": color})

        if rows:
            return rows

    raise ValueError("A planilha precisa ter pelo menos uma coluna com os números de Chassi/VIN.")



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

