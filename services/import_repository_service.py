"""
M-One Import Document Repository Service (services/import_repository_service.py)
Serviço responsável pela árvore de pastas temáticas do Comex, busca inteligente,
leitura de metadados extraídos e geração de pacote ZIP do dossiê documental.
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import datetime
from typing import Any

from database import db
from services.import_ai_service import DOC_TYPES_MAP

logger = logging.getLogger(__name__)

# Configuração das Pastas Temáticas do Ciclo Comex
REPOSITORY_FOLDERS = [
    {
        "id": "comercial_cambio",
        "title": "1. Comercial & Câmbio",
        "icon": "💰",
        "color": "#0284C7",
        "bg": "rgba(2, 132, 199, 0.1)",
        "border": "rgba(2, 132, 199, 0.25)",
        "doc_types": ["PI", "CI", "EXCHANGE_CONTRACT", "SUPPLIER_PAYMENT"],
        "description": "Proforma, Commercial Invoice, Contratos de Câmbio e remessas ao exterior.",
    },
    {
        "id": "embarque_logistica",
        "title": "2. Embarque & Logística Internacional",
        "icon": "🚢",
        "color": "#2563EB",
        "bg": "rgba(37, 99, 235, 0.1)",
        "border": "rgba(37, 99, 235, 0.25)",
        "doc_types": ["BL", "PL", "FREIGHT_INVOICE", "AGENTE_CARGA_BR"],
        "description": "Bill of Lading, Packing List, Taxas de Agente de Carga e Frete Internacional.",
    },
    {
        "id": "veiculos_frota",
        "title": "3. Veículos & Frota (VIN CHASSI)",
        "icon": "🛵",
        "color": "#7C3AED",
        "bg": "rgba(124, 58, 237, 0.1)",
        "border": "rgba(124, 58, 237, 0.25)",
        "doc_types": ["CHASSIS_LIST"],
        "description": "Relação oficial de Chassis VIN, motores e numeração dos veículos.",
    },
    {
        "id": "desembaraco_fiscal",
        "title": "4. Desembaraço & Fiscal",
        "icon": "🏛️",
        "color": "#059669",
        "bg": "rgba(5, 150, 105, 0.1)",
        "border": "rgba(5, 150, 105, 0.25)",
        "doc_types": ["DUIMP_DI", "ENTRY_NF", "ICMS_GUIDE", "TAX_GUIDE"],
        "description": "Extrato de DI / DUIMP, Guias e Comprovantes de ICMS e NF de Entrada.",
    },
    {
        "id": "transporte_despesas",
        "title": "5. Transporte & Despesas Nacionais",
        "icon": "🚛",
        "color": "#D97706",
        "bg": "rgba(217, 119, 6, 0.1)",
        "border": "rgba(217, 119, 6, 0.25)",
        "doc_types": ["NF_FRETE_CARRETA", "AJUDANTES_PAGTO"],
        "description": "Frete de Carreta (transporte rodoviário porto ao CD) e Ajudantes na desova.",
    },
    {
        "id": "prestacao_fechamento",
        "title": "6. Prestação de Contas & Fechamento",
        "icon": "📑",
        "color": "#DC2626",
        "bg": "rgba(220, 38, 38, 0.1)",
        "border": "rgba(220, 38, 38, 0.25)",
        "doc_types": ["FECHAMENTO_DESPACHANTE", "BROKER_SETTLEMENT", "NUMERARIO"],
        "description": "Fechamento final do despachante, conciliação de numerário e recibos aduaneiros.",
    },
    {
        "id": "outros",
        "title": "7. Outros Documentos & Laudos",
        "icon": "📂",
        "color": "#64748B",
        "bg": "rgba(100, 116, 139, 0.1)",
        "border": "rgba(100, 116, 139, 0.25)",
        "doc_types": [],  # Captura qualquer outro tipo não listado acima
        "description": "Documentos avulsos, certidões, laudos técnicos e comprovantes complementares.",
    },
]


def _get_folder_for_doc_type(doc_type: str) -> dict[str, Any]:
    """Determina a pasta correspondente para um código de tipo de documento."""
    d_upper = (doc_type or "OTHER").upper()
    for folder in REPOSITORY_FOLDERS:
        if folder["id"] != "outros" and d_upper in folder["doc_types"]:
            return folder
    return REPOSITORY_FOLDERS[-1]  # Outros


def get_import_repository_tree(import_id: int, conn) -> dict[str, Any]:
    """
    Retorna a árvore estruturada de documentos de uma importação agrupada por pastas temáticas,
    incluindo contagens, tamanho total e metadados.
    """
    imp = conn.execute("SELECT id, reference, supplier_name, status, step FROM imports WHERE id = %s", (import_id,)).fetchone()
    if not imp:
        return {}

    docs_rows = conn.execute(
        """
        SELECT d.id, d.import_id, d.doc_type, d.title, d.filename, d.file_url,
               d.file_size, d.file_hash, d.extracted_data, d.ai_status, d.created_at,
               u.name as uploader_name
        FROM import_documents d
        LEFT JOIN users u ON u.id = d.uploaded_by
        WHERE d.import_id = %s
        ORDER BY d.id DESC
        """,
        (import_id,),
    ).fetchall()

    # Inicializar pastas
    folders_map: dict[str, dict[str, Any]] = {}
    for f in REPOSITORY_FOLDERS:
        folders_map[f["id"]] = {
            **f,
            "documents": [],
            "total_size": 0,
            "count": 0,
        }

    total_files = 0
    total_bytes = 0

    for r in docs_rows:
        doc = dict(r)
        doc_type = doc.get("doc_type") or "OTHER"
        folder = _get_folder_for_doc_type(doc_type)
        folder_id = folder["id"]

        ext_data = doc.get("extracted_data") or {}
        if isinstance(ext_data, str):
            try:
                ext_data = json.loads(ext_data)
            except Exception:
                ext_data = {}

        created_dt = doc.get("created_at")
        formatted_date = created_dt.strftime("%d/%m/%Y %H:%M") if isinstance(created_dt, datetime) else ""

        doc_item = {
            "id": doc["id"],
            "import_id": doc["import_id"],
            "doc_type": doc_type,
            "doc_type_label": DOC_TYPES_MAP.get(doc_type, doc_type),
            "title": doc.get("title") or doc.get("filename"),
            "filename": doc.get("filename"),
            "file_url": doc.get("file_url"),
            "file_size": doc.get("file_size") or 0,
            "file_hash": doc.get("file_hash"),
            "ai_status": doc.get("ai_status"),
            "uploader_name": doc.get("uploader_name") or "Sistema",
            "created_at_label": formatted_date,
            "extracted_data": ext_data,
        }

        folders_map[folder_id]["documents"].append(doc_item)
        folders_map[folder_id]["total_size"] += doc_item["file_size"]
        folders_map[folder_id]["count"] += 1
        total_files += 1
        total_bytes += doc_item["file_size"]

    return {
        "import_info": dict(imp),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "folders": list(folders_map.values()),
    }


def search_import_documents(import_id: int, query: str, conn) -> list[dict[str, Any]]:
    """Busca em tempo real dentro do repositório por nome, título, tipo ou dados extraídos."""
    q_norm = f"%{query.strip().lower()}%"
    rows = conn.execute(
        """
        SELECT d.id, d.import_id, d.doc_type, d.title, d.filename, d.file_url,
               d.file_size, d.extracted_data, d.created_at, u.name as uploader_name
        FROM import_documents d
        LEFT JOIN users u ON u.id = d.uploaded_by
        WHERE d.import_id = %s
          AND (
            LOWER(d.title) LIKE %s
            OR LOWER(d.filename) LIKE %s
            OR LOWER(d.doc_type) LIKE %s
            OR LOWER(CAST(d.extracted_data AS text)) LIKE %s
          )
        ORDER BY d.id DESC
        """,
        (import_id, q_norm, q_norm, q_norm, q_norm),
    ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        doc_type = d.get("doc_type") or "OTHER"
        folder = _get_folder_for_doc_type(doc_type)
        ext_data = d.get("extracted_data") or {}
        if isinstance(ext_data, str):
            try:
                ext_data = json.loads(ext_data)
            except Exception:
                ext_data = {}

        created_dt = d.get("created_at")
        results.append({
            "id": d["id"],
            "doc_type": doc_type,
            "doc_type_label": DOC_TYPES_MAP.get(doc_type, doc_type),
            "folder_title": folder["title"],
            "folder_color": folder["color"],
            "title": d.get("title") or d.get("filename"),
            "filename": d.get("filename"),
            "file_url": d.get("file_url"),
            "file_size": d.get("file_size") or 0,
            "uploader_name": d.get("uploader_name") or "Sistema",
            "created_at_label": created_dt.strftime("%d/%m/%Y") if isinstance(created_dt, datetime) else "",
            "extracted_data": ext_data,
        })
    return results


def generate_import_documents_zip(import_id: int, upload_folder: str, conn) -> tuple[io.BytesIO, str]:
    """
    Gera em memória um pacote ZIP com todos os documentos da importação organizados
    em subpastas pelo ciclo Comex. Retorna (zip_buffer, filename_zip).
    """
    imp = conn.execute("SELECT reference FROM imports WHERE id = %s", (import_id,)).fetchone()
    ref = imp["reference"] if imp and imp.get("reference") else f"IMP-{import_id}"
    safe_ref = ref.replace("/", "_").replace(" ", "_").replace("\\", "_")

    docs = conn.execute(
        "SELECT id, doc_type, filename, file_url FROM import_documents WHERE import_id = %s ORDER BY doc_type, id",
        (import_id,),
    ).fetchall()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # README explicativo no arquivo ZIP
        readme_content = f"""M-One • Dossiê de Documentos de Importação
Referência: {ref}
Data de Exportação: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
Total de Arquivos: {len(docs)}

Estrutura das Pastas:
1_Comercial_Cambio/      - Proforma, Commercial Invoice e Câmbio
2_Embarque_Logistica/    - Bill of Lading, Packing List e Agente de Carga
3_Veiculos_Frota/        - Planilhas de VIN Chassi e Motores
4_Desembaraco_Fiscal/    - DI / DUIMP, Guias de ICMS e NF Entrada
5_Transporte_Despesas/   - NF Frete Carreta e Ajudantes
6_Prestacao_Fechamento/  - Fechamento Despachante e Recibos
7_Outros/                - Documentos complementares
"""
        zf.writestr("README_DOSSIE.txt", readme_content)

        used_names: set[str] = set()

        for d in docs:
            doc_type = d.get("doc_type") or "OTHER"
            folder = _get_folder_for_doc_type(doc_type)
            folder_name = folder["id"]

            file_url = d.get("file_url")
            orig_name = d.get("filename") or f"documento_{d['id']}.pdf"

            if not file_url:
                continue

            disk_path = os.path.join(upload_folder, file_url)
            if not os.path.exists(disk_path):
                logger.warning("Arquivo físico não encontrado para o ZIP: %s", disk_path)
                continue

            # Evitar nomes duplicados dentro da mesma pasta do zip
            archive_path = f"{folder_name}/{orig_name}"
            counter = 1
            while archive_path in used_names:
                name_parts = orig_name.rsplit(".", 1)
                if len(name_parts) == 2:
                    archive_path = f"{folder_name}/{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    archive_path = f"{folder_name}/{orig_name}_{counter}"
                counter += 1
            used_names.add(archive_path)

            zf.write(disk_path, arcname=archive_path)

    buf.seek(0)
    zip_filename = f"dossie_documental_{safe_ref}_{datetime.now().strftime('%Y%m%d')}.zip"
    return buf, zip_filename
