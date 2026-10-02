"""
M-One Central Global de Documentos Blueprint (routes/document_center_routes.py)
Ambiente global para consulta, visualização e download de documentos agrupados por importações,
incluindo arquivos históricos de lotes encerrados ou arquivados.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, render_template, request

from database import db
from routes.helpers import current_user, login_required, roles_required
from services.import_ai_service import DOC_TYPES_MAP

logger = logging.getLogger(__name__)

document_center_bp = Blueprint("document_center", __name__)


@document_center_bp.route("/documents", methods=["GET"])
@login_required
@roles_required("admin", "support", "finance")
def document_center():
    """Painel global de consulta e gestão de documentos do ecossistema Comex."""
    me = current_user() or {}
    q = request.args.get("q", "").strip()
    selected_batch = request.args.get("batch", "").strip()
    selected_type = request.args.get("doc_type", "").strip()

    with db() as conn:
        # 1. Carregar lista de lotes disponíveis
        batches_raw = conn.execute(
            """
            SELECT DISTINCT COALESCE(NULLIF(batch_reference, ''), 'Sem Lote') as batch_name
            FROM import_documents
            ORDER BY batch_name ASC
            """
        ).fetchall()
        batches = [b["batch_name"] for b in batches_raw if b["batch_name"]]

        # 2. Carregar lista de tipos disponíveis
        types_raw = conn.execute(
            """
            SELECT DISTINCT doc_type
            FROM import_documents
            WHERE doc_type IS NOT NULL AND doc_type != ''
            ORDER BY doc_type ASC
            """
        ).fetchall()
        doc_types_available = [t["doc_type"] for t in types_raw]

        # 3. Montar query com filtros dinâmicos
        conditions = ["1=1"]
        params = []

        if q:
            conditions.append("(d.title ILIKE %s OR d.filename ILIKE %s OR d.batch_reference ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

        if selected_batch:
            conditions.append("COALESCE(d.batch_reference, '') = %s")
            params.append(selected_batch)

        if selected_type:
            conditions.append("d.doc_type = %s")
            params.append(selected_type)

        where_clause = " AND ".join(conditions)

        docs_rows = conn.execute(
            f"""
            SELECT d.*, u.name as uploader_name, i.status as import_status, i.is_archived as import_is_archived,
                   i.name as import_name, i.reference as import_reference
            FROM import_documents d
            LEFT JOIN users u ON u.id = d.uploaded_by
            LEFT JOIN imports i ON i.id = d.import_id
            WHERE {where_clause}
            ORDER BY d.batch_reference ASC, d.doc_type ASC, d.id DESC
            """,
            tuple(params),
        ).fetchall()

        # Agrupar documentos por Lote de Importação
        grouped_docs = {}
        total_size = 0
        for doc in docs_rows:
            batch = doc.get("batch_reference") or "Documentos Gerais"
            if batch not in grouped_docs:
                grouped_docs[batch] = {
                    "batch": batch,
                    "import_id": doc.get("import_id"),
                    "import_name": doc.get("import_name"),
                    "is_archived": doc.get("import_is_archived", False),
                    "documents": [],
                }
            elif not grouped_docs[batch].get("import_name") and doc.get("import_name"):
                grouped_docs[batch]["import_name"] = doc.get("import_name")
            grouped_docs[batch]["documents"].append(dict(doc))
            total_size += int(doc.get("file_size") or 0)

        total_docs = len(docs_rows)
        total_batches = len(grouped_docs)

    return render_template(
        "document_center.html",
        me=me,
        grouped_docs=grouped_docs,
        batches=batches,
        doc_types=doc_types_available,
        doc_types_map=DOC_TYPES_MAP,
        selected_batch=selected_batch,
        selected_type=selected_type,
        q=q,
        total_docs=total_docs,
        total_batches=total_batches,
        total_size=total_size,
    )
