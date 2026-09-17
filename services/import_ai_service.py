"""
M-One Import AI Multi-Document Classifier & Extractor (services/import_ai_service.py)
Classifica automaticamente documentos aduaneiros (PI, CI, BL, Câmbio, Numerário, etc.),
detecta duplicatas por hash MD5 e extrai dados com vinculação por trecho/página.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from services.gemini_client import execute_gemini_payload
from services.pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)

DOC_TYPES_MAP = {
    "PI": "Proforma Invoice",
    "CI": "Commercial Invoice",
    "EXCHANGE_CONTRACT": "Contrato de Câmbio",
    "SUPPLIER_PAYMENT": "Comprovante de Pagamento ao Fornecedor",
    "FREIGHT_INVOICE": "Cobrança / Documento de Frete Internacional",
    "BL": "Conhecimento de Embarque (Bill of Lading)",
    "PL": "Packing List (Romaneio)",
    "DUIMP_DI": "DUIMP / Declaração de Importação (DI)",
    "CHASSIS_LIST": "Relação de Chassis",
    "ENTRY_NF": "Nota Fiscal de Entrada",
    "NUMERARIO": "Solicitação / Comprovante de Numerário Aduaneiro",
    "TAX_GUIDE": "Guia de Tributos / ICMS / DARF",
    "BROKER_SETTLEMENT": "Prestação de Contas do Despachante",
    "OTHER": "Outro Documento",
}


def calculate_file_hash(content: bytes) -> str:
    """Gera hash MD5 do conteúdo para blindagem de duplicidade."""
    return hashlib.md5(content).hexdigest()


def classify_and_extract_document(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "application/pdf",
    import_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analisa um arquivo enviado, classifica seu tipo oficial e extrai metadados estruturados."""
    import_context = import_context or {}
    file_hash = calculate_file_hash(file_bytes)

    # 1. Extração digital em memória se for PDF
    extracted_text = ""
    if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
        extracted_text = extract_text_from_pdf(file_bytes)

    # 2. Montar prompt com vocabulário aduaneiro
    text_snippet = (
        f"\n--- TEXTO EXTRAÍDO NATIVAMENTE DO ARQUIVO ({filename}) ---\n{extracted_text[:12000]}\n"
        if extracted_text
        else ""
    )

    types_list_str = "\n".join([f'- "{code}": {desc}' for code, desc in DOC_TYPES_MAP.items()])

    prompt = f"""
Você é o auditor aduaneiro e especialista em comércio exterior do M-One (MAJ Mobilidade Elétrica).
Analise o arquivo anexado "{filename}".

{text_snippet}

CONTEXTO ATUAL DA IMPORTAÇÃO NO SISTEMA:
- Referência: {import_context.get('reference', 'N/D')}
- Fornecedor: {import_context.get('supplier_name', 'N/D')}
- Número BL: {import_context.get('bl_no', 'N/D')}

TAREFA 1: CLASSIFIQUE O DOCUMENTO EXATAMENTE EM UMA DAS CATEGORIAS ABAIXO:
{types_list_str}

DIRETRIZES DE CLASSIFICAÇÃO:
- "PI": Se contiver "Proforma Invoice", "P/I", condições de encomenda prévia ou solicitação de depósito inicial.
- "CI": Se for a Commercial Invoice oficial definitiva ("Commercial Invoice", "Invoice No.", descrição de mercadorias embarcadas).
- "EXCHANGE_CONTRACT": Se for contrato de câmbio bancário (Travelex, Sicoob, etc., contendo taxa cambial, moeda, pagador e beneficiário).
- "SUPPLIER_PAYMENT": Comprovante de remessa internacional, SWIFT, comprovante bancário de transferência ao fornecedor chinês.
- "BL": Conhecimento de transporte marítimo ("Bill of Lading", "Sea Waybill", transportadora marítima como COSCO, Dawoo, etc.).
- "PL": Packing List, lista de volumes, peso bruto, cubagem e caixas.
- "DUIMP_DI": Extrato de Declaração de Importação emitida pela Receita Federal / Siscomex.
- "CHASSIS_LIST": Lista de números de chassi e modelos de veículos/motos.
- "ENTRY_NF": DANFE de Nota Fiscal de Entrada emitida no Brasil.
- "NUMERARIO": Solicitação de adiantamento de numerário emitida pelo despachante aduaneiro.
- "TAX_GUIDE": Guia DAE de ICMS Importação ou DARF de impostos federais.
- "BROKER_SETTLEMENT": Relatório final de prestação de contas com conciliação de numerário e recibos do despachante.

TAREFA 2: EXTRAIA OS CAMPOS RELEVANTES:
- `document_number`: Número do documento (ex: "DWSE26070035", "INV-2026-99", "PI-2026", número da DI, etc.).
- `issue_date`: Data de emissão ou embarque (YYYY-MM-DD).
- `currency`: Moeda (USD, BRL, EUR, CNY).
- `total_amount`: Valor monetário numérico principal do documento.
- `exchange_rate`: Taxa de câmbio se mencionada (ex: 5.65).
- `supplier_name`: Razão social do fornecedor ou exportador.
- `buyer_name`: Razão social do importador ou comprador.
- `container_no`: Número do contêiner marítimo se houver.
- `bl_no`: Número do BL se for um BL ou constar no documento.
- `products`: Lista de produtos identificados (nome, quantidade, valor unitário, valor total).
- `chassis_list`: Lista de números de chassi encontrados.
- `freight_included`: true se o frete internacional estiver embutido no valor das mercadorias.
- `summary`: Resumo sintético em português do que o documento representa.

FORMATO DE RESPOSTA OBRIGATÓRIO (APENAS JSON ESTRITO):
{{
  "doc_type": "CÓDIGO_DA_LISTA_ACIMA",
  "document_number": "...",
  "issue_date": "YYYY-MM-DD",
  "currency": "USD ou BRL",
  "total_amount": 0.00,
  "exchange_rate": null,
  "supplier_name": "...",
  "buyer_name": "...",
  "container_no": "...",
  "bl_no": "...",
  "products": [],
  "chassis_list": [],
  "freight_included": false,
  "summary": "Resumo claro do documento em português"
}}
"""

    parts: list[dict[str, Any]] = []
    # Anexa dados multimodais
    b64_data = base64.b64encode(file_bytes).decode("utf-8")
    parts.append({
        "inlineData": {
            "mimeType": mime_type or "application/pdf",
            "data": b64_data,
        }
    })
    parts.append({"text": prompt})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }

    res = execute_gemini_payload(payload, timeout=35)

    # Fallback puramente textual se multimodal falhar e houver texto extraído
    if not res.get("success") and extracted_text:
        text_payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        res = execute_gemini_payload(text_payload, timeout=25)

    extracted_json: dict[str, Any] = {}
    if res.get("success") and res.get("data"):
        extracted_json = res["data"]
    elif res.get("text"):
        try:
            extracted_json = json.loads(res["text"])
        except Exception:
            extracted_json = {}

    doc_type = extracted_json.get("doc_type", "OTHER")
    if doc_type not in DOC_TYPES_MAP:
        doc_type = "OTHER"

    return {
        "success": bool(extracted_json),
        "file_hash": file_hash,
        "doc_type": doc_type,
        "doc_type_label": DOC_TYPES_MAP.get(doc_type, "Outro"),
        "title": f"{DOC_TYPES_MAP.get(doc_type, 'Documento')} ({filename})",
        "data": extracted_json,
        "model_used": res.get("model_used"),
        "raw_message": res.get("message"),
    }


def analyze_import_batch(file_items: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analisa em lote os arquivos enviados no Wizard de Nova Importação.
    Classifica cada arquivo, extrai metadados cadastrais, lê planilhas de chassis
    e cruza com as regras documentais ativas.
    """
    from services.chassis_service import check_duplicate_chassis, parse_chassis_file
    from services.import_rules_service import get_document_rules

    detected_docs: list[dict[str, Any]] = []
    extracted_fields: dict[str, Any] = {
        "reference": "",
        "supplier_name": "",
        "supplier_contact": "",
        "currency": "USD",
        "incoterm": "FOB",
        "pi_amount_usd": 0.0,
        "ci_amount_usd": 0.0,
        "bl_no": "",
        "invoice_no": "",
        "arrival_date_estimated": "",
        "departure_date_estimated": "",
        "notes": "",
    }
    all_chassis_items: list[dict[str, str]] = []

    for item in file_items:
        filename = item.get("filename", "")
        file_bytes = item.get("bytes", b"")
        mime_type = item.get("mime_type", "")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # 1. Tratar planilhas diretamente
        if ext in ["xlsx", "xls", "csv"]:
            class MemFile:
                def __init__(self, fn: str, b: bytes):
                    self.filename = fn
                    self.content = b
                def read(self):
                    return self.content

            try:
                chassis_rows = parse_chassis_file(MemFile(filename, file_bytes))
                all_chassis_items.extend(chassis_rows)
                detected_docs.append({
                    "filename": filename,
                    "doc_type": "CHASSIS_LIST",
                    "doc_type_label": DOC_TYPES_MAP.get("CHASSIS_LIST", "Relação de Chassis"),
                    "title": f"Planilha de Chassis ({filename})",
                    "chassis_count": len(chassis_rows),
                    "summary": f"{len(chassis_rows)} chassis estruturados lidos na planilha.",
                })
                continue
            except Exception as e:
                logger.info("[analyze_import_batch] Arquivo %s não é planilha de chassis pura: %s", filename, e)

        # 2. Documentos PDF / Imagens via IA Gemini
        res = classify_and_extract_document(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
            import_context=extracted_fields,
        )
        doc_data = res.get("data") or {}
        doc_type = res.get("doc_type", "OTHER")

        # Unificar NUMERARIO e TAX_GUIDE no tipo de regra NUMERARIO_TAX se aplicável
        normalized_doc_type = doc_type
        if doc_type in ["NUMERARIO", "TAX_GUIDE"]:
            normalized_doc_type = "NUMERARIO_TAX"

        detected_docs.append({
            "filename": filename,
            "doc_type": normalized_doc_type,
            "original_doc_type": doc_type,
            "doc_type_label": DOC_TYPES_MAP.get(doc_type, "Documento"),
            "title": res.get("title", filename),
            "document_number": doc_data.get("document_number"),
            "total_amount": doc_data.get("total_amount"),
            "currency": doc_data.get("currency"),
            "summary": doc_data.get("summary", ""),
        })

        # Preenchimento inteligente prioritário dos campos da importação
        if doc_data.get("bl_no") and not extracted_fields.get("bl_no"):
            extracted_fields["bl_no"] = doc_data["bl_no"]
            if not extracted_fields.get("reference"):
                extracted_fields["reference"] = doc_data["bl_no"]

        if doc_type == "BL":
            if doc_data.get("document_number"):
                extracted_fields["bl_no"] = doc_data["document_number"]
                if not extracted_fields.get("reference"):
                    extracted_fields["reference"] = doc_data["document_number"]
            if doc_data.get("issue_date") and not extracted_fields.get("departure_date_estimated"):
                extracted_fields["departure_date_estimated"] = doc_data["issue_date"]

        if doc_type == "CI":
            if doc_data.get("document_number"):
                extracted_fields["invoice_no"] = doc_data["document_number"]
            if doc_data.get("total_amount"):
                extracted_fields["ci_amount_usd"] = float(doc_data["total_amount"])
                if not extracted_fields.get("pi_amount_usd"):
                    extracted_fields["pi_amount_usd"] = float(doc_data["total_amount"])
            if doc_data.get("supplier_name") and not extracted_fields.get("supplier_name"):
                extracted_fields["supplier_name"] = doc_data["supplier_name"]

        if doc_type == "PI":
            if doc_data.get("total_amount") and not extracted_fields.get("pi_amount_usd"):
                extracted_fields["pi_amount_usd"] = float(doc_data["total_amount"])
            if doc_data.get("supplier_name") and not extracted_fields.get("supplier_name"):
                extracted_fields["supplier_name"] = doc_data["supplier_name"]

        # Extração de chassis embutidos em texto se houver
        if doc_data.get("chassis_list") and isinstance(doc_data["chassis_list"], list):
            for c in doc_data["chassis_list"]:
                if isinstance(c, str) and c.strip():
                    all_chassis_items.append({"model": "Veículo Elétrico", "chassis": c.strip(), "motor": "", "color": ""})

    # Verificar duplicidade de chassis no banco de dados
    unique_chassis_vins = list({item["chassis"].strip().upper() for item in all_chassis_items if item.get("chassis")})
    duplicates = check_duplicate_chassis(unique_chassis_vins)

    return {
        "success": True,
        "files": detected_docs,
        "extracted_data": extracted_fields,
        "chassis_info": {
            "total_count": len(all_chassis_items),
            "unique_count": len(unique_chassis_vins),
            "duplicates": duplicates,
            "items": all_chassis_items[:300],  # amostra inicial
        },
        "rules": get_document_rules(),
    }


def persist_creation_documents(import_id: int, req, conn, user_id: int | None = None) -> int:
    """Salva os arquivos enviados durante o Wizard de criação da importação e vincula os chassis."""
    import os
    from flask import current_app
    from werkzeug.utils import secure_filename
    from services.chassis_service import parse_chassis_file

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    # 1. Carregar mapeamento manual de classificações se enviado
    meta_map = {}
    raw_meta = req.form.get("documents_meta")
    if raw_meta:
        try:
            meta_list = json.loads(raw_meta)
            for m in meta_list:
                if m.get("filename"):
                    meta_map[m["filename"]] = m.get("doc_type", "OTHER")
        except Exception:
            pass

    # 2. Coletar todos os arquivos
    files_to_save = []
    # Dropzone múltiplo
    for f in req.files.getlist("documents"):
        if f and f.filename:
            files_to_save.append(f)
    # Inputs clássicos/fallback
    for k in ["invoice_file", "bl_file", "nf_entry_file", "chassis_file"]:
        f = req.files.get(k)
        if f and f.filename and not any(saved.filename == f.filename for saved in files_to_save):
            files_to_save.append(f)

    saved_count = 0
    for f in files_to_save:
        orig_name = secure_filename(f.filename)
        content = f.read()
        if not content:
            continue

        f_hash = calculate_file_hash(content)
        doc_type = meta_map.get(f.filename) or meta_map.get(orig_name) or "OTHER"
        ext = orig_name.rsplit(".", 1)[-1].lower() if "." in orig_name else ""

        # Se for planilha e ainda não tiver classificação, define como CHASSIS_LIST
        if ext in ["xlsx", "xls", "csv"] and doc_type in ["OTHER", "CHASSIS_LIST"]:
            doc_type = "CHASSIS_LIST"
            # Processar e cadastrar os chassis diretamente no estoque deste lote
            class MemFile:
                def __init__(self, fn: str, b: bytes):
                    self.filename = fn
                    self.content = b
                def read(self):
                    return self.content

            try:
                chassis_rows = parse_chassis_file(MemFile(orig_name, content))
                if chassis_rows:
                    prod_map = {p["name"].strip().lower(): p["id"] for p in conn.execute("SELECT id, name FROM products").fetchall()}
                    for cr in chassis_rows:
                        model_name = cr.get("model", "Veículo Elétrico").strip()
                        p_id = prod_map.get(model_name.lower())
                        if not p_id:
                            res_p = conn.execute("INSERT INTO products (name, category) VALUES (%s, 'Motos Elétricas') RETURNING id", (model_name,)).fetchone()
                            p_id = res_p["id"]
                            prod_map[model_name.lower()] = p_id
                        conn.execute(
                            """
                            INSERT INTO stock_units (product_id, chassis, motor_number, color, import_id, status)
                            VALUES (%s, %s, %s, %s, %s, 'unreleased')
                            ON CONFLICT DO NOTHING;
                            """,
                            (p_id, cr["chassis"].strip(), cr.get("motor", "").strip(), cr.get("color", "").strip(), import_id),
                        )
            except Exception as err:
                logger.warning("[persist_creation_documents] Falha ao processar chassis de %s: %s", orig_name, err)

        save_name = f"import_{import_id}_{doc_type.lower()}_{orig_name}"
        save_path = os.path.join(upload_folder, save_name)
        with open(save_path, "wb") as out:
            out.write(content)

        conn.execute(
            """
            INSERT INTO import_documents (import_id, doc_type, title, file_url, file_hash, uploaded_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (import_id, doc_type, orig_name, save_name, f_hash, user_id),
        )
        saved_count += 1

    return saved_count
