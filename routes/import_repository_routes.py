"""
M-One Import Document Repository Routes Blueprint (routes/import_repository_routes.py)
Rotas do Repositório Inteligente de Documentos: árvore temática, busca e download de dossiê em ZIP.
"""

from __future__ import annotations

import logging
from flask import Blueprint, current_app, jsonify, request, send_file

from database import db
from routes.helpers import audit, login_required, roles_required
from services.import_repository_service import (
    generate_import_documents_zip,
    get_import_repository_tree,
    search_import_documents,
)

logger = logging.getLogger(__name__)

import_repository_bp = Blueprint("import_repository", __name__)


@import_repository_bp.route("/api/imports/<int:iid>/repository", methods=["GET"])
@login_required
def get_repository_tree(iid: int):
    """Retorna a árvore completa de pastas e documentos de uma importação."""
    try:
        with db() as conn:
            data = get_import_repository_tree(iid, conn)
            if not data:
                return jsonify({"success": False, "error": "Importação não encontrada."}), 404
            return jsonify({"success": True, "repository": data})
    except Exception as e:
        logger.error("Erro ao buscar repositório da importação %d: %s", iid, e)
        return jsonify({"success": False, "error": str(e)}), 500


@import_repository_bp.route("/api/imports/<int:iid>/repository/search", methods=["GET"])
@login_required
def search_repository(iid: int):
    """Realiza busca textual rápida dentro dos documentos da importação."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"success": True, "results": []})
    try:
        with db() as conn:
            results = search_import_documents(iid, query, conn)
            return jsonify({"success": True, "results": results})
    except Exception as e:
        logger.error("Erro na busca de documentos da importação %d: %s", iid, e)
        return jsonify({"success": False, "error": str(e)}), 500


@import_repository_bp.route("/api/imports/<int:iid>/documents/<int:doc_id>/details", methods=["GET"])
@login_required
def get_document_details(iid: int, doc_id: int):
    """Retorna detalhes completos e metadados extraídos pela IA de um documento."""
    try:
        with db() as conn:
            row = conn.execute(
                """
                SELECT d.*, u.name as uploader_name
                FROM import_documents d
                LEFT JOIN users u ON u.id = d.uploaded_by
                WHERE d.id = %s AND d.import_id = %s
                """,
                (doc_id, iid),
            ).fetchone()
            if not row:
                return jsonify({"success": False, "error": "Documento não encontrado."}), 404
            return jsonify({"success": True, "document": dict(row)})
    except Exception as e:
        logger.error("Erro ao carregar detalhes do documento %d: %s", doc_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@import_repository_bp.route("/api/imports/<int:iid>/documents/download-zip", methods=["GET"])
@login_required
@roles_required("admin", "support")
def download_documents_zip(iid: int):
    """Gera e envia o pacote ZIP completo com os documentos organizados em pastas (restrito a diretoria e suporte)."""
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    try:
        with db() as conn:
            zip_buf, zip_name = generate_import_documents_zip(iid, upload_folder, conn)
            audit("import.repository_zip_downloaded", f"import_id={iid}, filename={zip_name}")
            return send_file(
                zip_buf,
                mimetype="application/zip",
                as_attachment=True,
                download_name=zip_name,
            )
    except Exception as e:
        logger.error("Erro ao gerar ZIP da importação %d: %s", iid, e)
        return jsonify({"success": False, "error": f"Erro ao gerar pacote ZIP: {str(e)}"}), 500
