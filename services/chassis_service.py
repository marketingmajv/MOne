"""
M-One Chassis Import & Parsing Service (services/chassis_service.py)
Processamento e validação de planilhas de chassis (CSV e XLSX).
"""

from __future__ import annotations

import csv
import io
import logging
import re

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


CHINESE_COLOR_MAP = {
    "碳黑": "Preto Carbono",
    "亮黑色": "Preto Brilhante",
    "亮黑": "Preto Brilhante",
    "纳多灰": "Cinza Nardo",
    "亚黑": "Preto Fosco",
    "磨砂黑": "Preto Fosco",
    "黑色": "Preto",
    "黑": "Preto",
    "白色": "Branco",
    "白": "Branco",
    "珍珠白": "Branco Pérola",
    "红色": "Vermelho",
    "红": "Vermelho",
    "亮红色": "Vermelho Brilhante",
    "酒红色": "Vermelho Vinho",
    "酒红": "Vermelho Vinho",
    "蓝色": "Azul",
    "蓝": "Azul",
    "浅湖蓝色": "Azul Lago Claro",
    "磨砂深蓝": "Azul Escuro Fosco",
    "黄色": "Amarelo",
    "黄": "Amarelo",
    "灰色": "Cinza",
    "灰": "Cinza",
    "银色": "Prata",
    "银": "Prata",
    "绿色": "Verde",
    "绿": "Verde",
    "墨绿色": "Verde Militar",
    "橙色": "Laranja",
    "橙": "Laranja",
}


def _is_chassis_header(cell) -> bool:
    s = str(cell or "").strip().lower()
    if not s:
        return False
    # Evitar banners longos de título ou totais de pedido (ex: "26je26订单x13车架号197台")
    if len(s) > 25 and any(p in s for p in ["订单", "pedido", "order", "total", "台", "unidades", "lista"]):
        return False
    if "车架" in s or "vin码" in s or "车架号" in s:
        return True
    tokens = set(re.findall(r"[a-z0-9]+", s))
    if any(t in tokens for t in ["chassi", "chassis", "vin", "frame", "quadro", "serial"]):
        return True
    return any(p in s for p in ["chassi", "chassis", "vin", "frame no", "serial no", "quadro"])


def _is_model_header(cell) -> bool:
    s = str(cell or "").strip().lower()
    if not s:
        return False
    if "型号" in s or "车型" in s:
        return True
    tokens = set(re.findall(r"[a-z0-9]+", s))
    if any(t in tokens for t in ["modelo", "model", "produto", "product", "descricao", "description", "item", "tipo", "especificacao"]):
        return True
    return any(p in s for p in ["modelo", "model", "produto", "product", "item"])


def _is_motor_header(cell) -> bool:
    s = str(cell or "").strip().lower()
    if not s:
        return False
    if "电机" in s or "发动机" in s:
        return True
    tokens = set(re.findall(r"[a-z0-9]+", s))
    return any(t in tokens for t in ["motor", "engine"])


def _is_color_header(cell) -> bool:
    s = str(cell or "").strip().lower()
    if not s:
        return False
    if "颜色" in s:
        return True
    tokens = set(re.findall(r"[a-z0-9]+", s))
    return any(t in tokens for t in ["cor", "color", "colour"])


def parse_chassis_file(file_storage) -> list[dict[str, str]]:
    """Lê arquivo CSV ou XLSX e extrai lista de dicionários de chassis com detecção tolerante a cabeçalhos compostos e padrões de VIN."""
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

    vin_pattern = re.compile(r"^[A-HJ-NPR-Z0-9]{8,25}$", re.IGNORECASE)

    for all_rows in all_sheets_rows:
        if not all_rows:
            continue

        header_row_idx = None
        i_chassis = None
        i_model = None
        i_motor = None
        i_color = None
        inferred_model = "Veículo Elétrico"

        # Tentar extrair nome do modelo de banners ou títulos iniciais (ex: '26JE26订单X13车架号197台')
        for banner_row in all_rows[:5]:
            banner_text = " ".join(str(c or "").strip() for c in banner_row)
            m_match = re.search(r"(?:^|[^a-zA-Z0-9])(X13|MAX\s*12|V80\s*PRO|V20\s*ULTRA|CLASSIC\s*1000|FLOW\s*ONE|M9\s*PRO|M2|NOVA|RZ-110)(?:$|[^a-zA-Z0-9])", banner_text, re.IGNORECASE)
            if m_match:
                inferred_model = m_match.group(1).upper()
                break

        # 1. Varredura inteligente de cabeçalhos nas primeiras 20 linhas
        max_scan = min(20, len(all_rows))
        for r_idx in range(max_scan):
            row = all_rows[r_idx]
            non_empty_cells = [c for c in row if str(c or "").strip()]
            if len(non_empty_cells) <= 1:
                # Linha com apenas 1 célula preenchida é banner/título, não cabeçalho de tabela
                continue

            cand_chassis = None
            for col_idx, cell in enumerate(row):
                if _is_chassis_header(cell):
                    cand_chassis = col_idx
                    break

            if cand_chassis is not None:
                # Validação ativa: checar se as linhas subsequentes contêm padrões de VIN/chassi
                valid_count = 0
                for check_row in all_rows[r_idx + 1: r_idx + 25]:
                    if cand_chassis < len(check_row):
                        val = str(check_row[cand_chassis] or "").strip()
                        if len(val) >= 6 and re.match(r"^[A-Za-z0-9_-]+$", val):
                            valid_count += 1
                if valid_count >= 1:
                    i_chassis = cand_chassis
                    header_row_idx = r_idx
                    for col_idx, cell in enumerate(row):
                        if col_idx == i_chassis:
                            continue
                        if i_model is None and _is_model_header(cell):
                            i_model = col_idx
                        elif i_motor is None and _is_motor_header(cell):
                            i_motor = col_idx
                        elif i_color is None and _is_color_header(cell):
                            i_color = col_idx
                    break

        # 2. Fallback por conteúdo: caso cabeçalho não seja óbvio ou tenha sido mesclado
        if i_chassis is None:
            best_col = None
            best_count = 0
            best_start_row = 1
            num_cols = max(len(r) for r in all_rows) if all_rows else 0

            for c_idx in range(num_cols):
                matches = 0
                first_row = None
                for r_idx, row in enumerate(all_rows):
                    if c_idx < len(row):
                        val = str(row[c_idx] or "").strip()
                        if _is_chassis_header(val):
                            continue
                        if vin_pattern.match(val):
                            matches += 1
                            if first_row is None:
                                first_row = r_idx
                if matches > best_count and matches >= 2:
                    best_count = matches
                    best_col = c_idx
                    best_start_row = first_row or 1

            if best_col is not None:
                i_chassis = best_col
                header_row_idx = max(0, best_start_row - 1)

        if i_chassis is None:
            continue

        rows = []
        for raw in all_rows[header_row_idx + 1:]:
            chassis = str(raw[i_chassis] or "").strip() if i_chassis < len(raw) else ""
            if not chassis or len(chassis) < 4:
                continue
            if _is_chassis_header(chassis):
                continue

            model = str(raw[i_model] or "").strip() if (i_model is not None and i_model < len(raw)) else inferred_model
            if not model:
                model = inferred_model
            motor = str(raw[i_motor] or "").strip() if (i_motor is not None and i_motor < len(raw)) else ""
            raw_color = str(raw[i_color] or "").strip() if (i_color is not None and i_color < len(raw)) else ""
            color = CHINESE_COLOR_MAP.get(raw_color, raw_color)

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

