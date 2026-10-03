"""
Serviço de parsing e ingestão multi-entrada de dados fiscais (XML NF-e, Excel, Lotes M-One e Manual).
"""
from __future__ import annotations

import io
import logging
import csv
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
import openpyxl
from database import db

logger = logging.getLogger("mone.fiscal_parser")


def parse_nfe_xml(xml_content: str | bytes) -> Dict[str, Any]:
    """
    Parses a NFe / DANFE XML document into header totals and item list.
    Handles XML namespaces transparently.
    """
    try:
        if isinstance(xml_content, str):
            xml_content = xml_content.encode("utf-8")

        root = ET.fromstring(xml_content)
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        def find_text(elem, tag_name, default=""):
            found = elem.find(f".//{ns}{tag_name}") if elem is not None else None
            return found.text.strip() if found is not None and found.text else default

        # Header info
        inf_nfe = root.find(f".//{ns}infNFe")
        nfe_key = inf_nfe.attrib.get("Id", "").replace("NFe", "") if inf_nfe is not None else ""

        supplier_name = find_text(root, "xNome", "COLVIX IMPORTACAO E EXPORTACAO LTDA")
        invoice_number = find_text(root, "nNF", "1001")
        invoice_date = find_text(root, "dhEmi", find_text(root, "dEmi", ""))

        # Totals
        total_products_val = float(find_text(root, "vProd", "0") or 0)
        total_ii_val = float(find_text(root, "vII", "0") or 0)
        total_pis_val = float(find_text(root, "vPIS", "0") or 0)
        total_cofins_val = float(find_text(root, "vCOFINS", "0") or 0)
        total_icms_val = float(find_text(root, "vICMS", "0") or 0)
        total_ipi_val = float(find_text(root, "vIPI", "0") or 0)

        v_outro = float(find_text(root, "vOutro", "0") or 0)
        v_frete = float(find_text(root, "vFrete", "0") or 0)
        v_seg = float(find_text(root, "vSeg", "0") or 0)
        general_expenses = v_outro + v_frete + v_seg

        # Items
        items_raw = []
        for det in root.findall(f".//{ns}det"):
            prod = det.find(f"{ns}prod")
            if prod is None:
                continue

            c_prod = find_text(prod, "cProd", "ITEM-00")
            x_prod = find_text(prod, "xProd", "Produto Importado")
            ncm = find_text(prod, "NCM", "87116000")
            q_com = float(find_text(prod, "qCom", "1") or 1)
            v_un_com = float(find_text(prod, "vUnCom", "0") or 0)
            v_prod = float(find_text(prod, "vProd", str(q_com * v_un_com)) or (q_com * v_un_com))

            imposto = det.find(f"{ns}imposto")
            v_ipi_item = float(find_text(imposto, "vIPI", "0") or 0)
            v_icms_item = float(find_text(imposto, "vICMS", "0") or 0)

            items_raw.append({
                "item_code": c_prod,
                "description": x_prod,
                "ncm": ncm,
                "quantity": q_com,
                "unit_product_val": v_un_com,
                "total_product_val": v_prod,
                "ipi_item": v_ipi_item,
                "icms_item": v_icms_item,
            })

        return {
            "source_type": "xml",
            "source_ref": nfe_key or f"NF-{invoice_number}",
            "supplier_name": supplier_name,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "total_products_val": total_products_val,
            "total_ii_val": total_ii_val,
            "total_pis_val": total_pis_val,
            "total_cofins_val": total_cofins_val,
            "total_icms_val": total_icms_val,
            "total_ipi_val": total_ipi_val,
            "general_expenses_header": general_expenses,
            "items_raw": items_raw,
        }
    except Exception as e:
        logger.error("[XML Parser Error]: %s", e)
        raise ValueError(f"Falha ao ler XML da NF-e: {e}")


def parse_excel_file(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Parses a dataset from Excel (.xlsx) or CSV spreadsheet as the primary source of truth.
    Scans top rows adaptively to identify the header row and maps all portuguese/english column variations.
    """
    items_raw = []
    total_products_val = 0.0
    total_ii_val = 0.0
    total_pis_val = 0.0
    total_cofins_val = 0.0
    total_icms_val = 0.0
    total_ipi_val = 0.0
    general_expenses = 0.0

    try:
        is_csv = filename.lower().endswith(".csv")
        if is_csv:
            text = file_content.decode("utf-8-sig", errors="ignore")
            reader = csv.reader(io.StringIO(text), delimiter=";" if ";" in text else ",")
            rows = [row for row in reader if row]
        else:
            wb = openpyxl.load_workbook(filename=io.BytesIO(file_content), data_only=True)
            sheet = wb.active
            rows = [[cell.value for cell in row] for row in sheet.iter_rows()]

        if not rows:
            raise ValueError("Planilha vazia.")

        import unicodedata

        def clean_str(val: Any) -> str:
            if val is None:
                return ""
            s = str(val).strip().lower()
            # Remove accents
            s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
            return s

        # Scan top 10 rows to detect the true header row
        header_row_idx = 0
        best_score = -1
        header_keywords = ["cod", "codigo", "item", "desc", "descricao", "ncm", "qtd", "quant", "unit", "valor", "preco", "total", "val"]

        for r_i in range(min(10, len(rows))):
            row_clean = [clean_str(c) for c in rows[r_i]]
            score = sum(1 for cell in row_clean if any(kw in cell for kw in header_keywords))
            if score > best_score and score >= 2:
                best_score = score
                header_row_idx = r_i

        header = [clean_str(c) for c in rows[header_row_idx]]

        def get_col_idx(names: List[str], exclude: List[str] = None) -> int:
            for idx, col in enumerate(header):
                if exclude and any(e in col for e in exclude):
                    continue
                if any(n in col for n in names):
                    return idx
            return -1

        c_desc = get_col_idx(["descricao", "desc", "description", "discriminacao"])
        c_code = get_col_idx(["codigo", "cod", "code", "sku", "ref", "modelo", "part"], exclude=["desc", "discriminacao"])
        if c_desc == -1:
            c_desc = get_col_idx(["produto", "nome", "item"], exclude=["codigo", "cod", "code", "sku", "ref"])
        if c_code == -1:
            c_code = get_col_idx(["item"], exclude=["desc", "discriminacao", "produto", "nome"])
        c_ncm = get_col_idx(["ncm", "sh"])
        c_qty = get_col_idx(["qtd", "quantidade", "qty", "quant", "unidades", "qnt", "qtd."])
        c_unit = get_col_idx(["unitario", "unit", "valor_unit", "vlr_unit", "val_unit", "preco_unit", "preco", "valor", "vuncom", "vlr", "cost", "custo", "val."])
        c_total = get_col_idx(["total", "vprod", "valor_total", "vlr_total", "val_total", "tot"], exclude=["unitario", "unit", "val_unit", "preco_unit"])
        c_ipi = get_col_idx(["ipi"])
        c_icms = get_col_idx(["icms"])

        item_counter = 1
        for r_idx, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 1):
            if not any(row):
                continue

            def parse_num(val, default=0.0):
                if val is None:
                    return default
                try:
                    s = str(val).replace("R$", "").replace("$", "").replace(" ", "").strip()
                    if "," in s and "." in s:
                        # Brazilian format e.g. 1.250,50
                        s = s.replace(".", "").replace(",", ".")
                    elif "," in s:
                        s = s.replace(",", ".")
                    return float(s)
                except Exception:
                    return default

            # Check if this row is a total/summary row
            row_str = " ".join([clean_str(c) for c in row if c is not None])
            if any(term in row_str for term in ["total geral", "subtotal", "somatorio", "resumo"]):
                continue

            code_raw = row[c_code] if c_code != -1 and c_code < len(row) else None
            desc_raw = row[c_desc] if c_desc != -1 and c_desc < len(row) else None
            ncm_raw = row[c_ncm] if c_ncm != -1 and c_ncm < len(row) else None
            qty_raw = row[c_qty] if c_qty != -1 and c_qty < len(row) else None
            unit_raw = row[c_unit] if c_unit != -1 and c_unit < len(row) else None
            total_raw = row[c_total] if c_total != -1 and c_total < len(row) else None

            # If all parsed elements are empty, skip
            if not any([code_raw, desc_raw, ncm_raw, qty_raw, unit_raw, total_raw]):
                continue

            code = str(code_raw).strip() if code_raw is not None and str(code_raw).strip() else f"ITEM-{item_counter:02d}"
            desc = str(desc_raw).strip() if desc_raw is not None and str(desc_raw).strip() else "Produto Importado"
            ncm = str(ncm_raw).strip() if ncm_raw is not None and str(ncm_raw).strip() else "87116000"
            qty = parse_num(qty_raw, 1.0)
            if qty <= 0:
                qty = 1.0

            unit_val = parse_num(unit_raw, 0.0)
            tot_val = parse_num(total_raw, 0.0)

            # Auto-calculate unit or total if one of them is missing
            if tot_val == 0.0 and unit_val > 0.0:
                tot_val = round(qty * unit_val, 2)
            elif unit_val == 0.0 and tot_val > 0.0 and qty > 0:
                unit_val = round(tot_val / qty, 2)

            ipi_val = parse_num(row[c_ipi] if c_ipi != -1 and c_ipi < len(row) else None, 0.0)
            icms_val = parse_num(row[c_icms] if c_icms != -1 and c_icms < len(row) else None, 0.0)

            total_products_val += tot_val
            total_ipi_val += ipi_val
            total_icms_val += icms_val

            items_raw.append({
                "item_code": code,
                "description": desc,
                "ncm": ncm,
                "quantity": qty,
                "unit_product_val": unit_val,
                "total_product_val": tot_val,
                "ipi_item": ipi_val,
                "icms_item": icms_val,
            })
            item_counter += 1

        # Estimar créditos de PIS (1,65%) e COFINS (7,6%)
        total_pis_val = round(total_products_val * 0.0165, 2)
        total_cofins_val = round(total_products_val * 0.0760, 2)

        return {
            "source_type": "excel",
            "source_ref": filename,
            "supplier_name": "COLVIX (Planilha Fonte Única)",
            "invoice_number": f"XLS-{filename}",
            "invoice_date": "",
            "total_products_val": total_products_val,
            "total_ii_val": total_ii_val,
            "total_pis_val": total_pis_val,
            "total_cofins_val": total_cofins_val,
            "total_icms_val": total_icms_val,
            "total_ipi_val": total_ipi_val,
            "general_expenses_header": general_expenses,
            "items_raw": items_raw,
        }
    except Exception as e:
        logger.error("[Excel Parser Error]: %s", e)
        raise ValueError(f"Falha ao ler planilha Excel/CSV: {e}")


def parse_mone_import(import_id: int) -> Dict[str, Any]:
    """
    Puxa os dados de um lote de importação cadastrado na tabela `imports` do M-One.
    """
    with db() as conn:
        row = conn.execute("SELECT * FROM imports WHERE id = ?", (import_id,)).fetchone()
        if not row:
            raise ValueError(f"Lote de importação #{import_id} não encontrado no M-One.")

        imp = dict(row) if hasattr(row, "keys") else row
        costs_rows = conn.execute("SELECT * FROM import_costs WHERE import_id = ?", (import_id,)).fetchall()
        costs = [dict(c) if hasattr(c, "keys") else c for c in costs_rows]

    general_expenses = sum(float(c.get("amount", 0) or 0) for c in costs)
    container_no = imp.get("reference") or imp.get("invoice_no") or f"IMP-{import_id:03d}"
    fob_usd = float(imp.get("invoice_amount_usd", 0) or 0)
    taxa_dolar = float(imp.get("usd_rate", 5.5) or 5.5)

    total_brl = fob_usd * taxa_dolar if fob_usd > 0 else 10000.0
    items_raw = [{
        "item_code": container_no,
        "description": f"Lote Importação {container_no} - Veículos / Peças Elétricas",
        "ncm": "87116000",
        "quantity": 1.0,
        "unit_product_val": round(total_brl, 2),
        "total_product_val": round(total_brl, 2),
        "ipi_item": round(total_brl * 0.35, 2),
        "icms_item": round(total_brl * 0.12, 2),
    }]

    return {
        "source_type": "import_ref",
        "source_ref": str(import_id),
        "supplier_name": "COLVIX / MAJ EXPORT",
        "invoice_number": container_no,
        "invoice_date": str(imp.get("created_at", ""))[:10],
        "total_products_val": total_brl,
        "total_ii_val": float(imp.get("total_ii", 0) or (total_brl * 0.16)),
        "total_pis_val": round(total_brl * 0.021, 2),
        "total_cofins_val": round(total_brl * 0.0965, 2),
        "total_icms_val": round(total_brl * 0.12, 2),
        "total_ipi_val": round(total_brl * 0.35, 2),
        "general_expenses_header": general_expenses,
        "items_raw": items_raw,
    }
