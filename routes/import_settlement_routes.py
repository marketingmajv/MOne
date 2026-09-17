"""
M-One Import Settlement Routes Blueprint (routes/import_settlement_routes.py)
Rotas do subsistema de Fechamento de Importação, Prestação de Contas e Conciliação com IA.
"""

from __future__ import annotations

import json
import logging
import os
from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from database import db
from routes.helpers import current_user, login_required, roles_required
from services.import_ai_service import calculate_file_hash, classify_and_extract_document
from services.import_settlement_service import (
    apply_settlement_reconciliation,
    cross_reference_settlement_documents,
    get_import_baseline_for_settlement,
)

logger = logging.getLogger(__name__)

import_settlement_bp = Blueprint("import_settlement", __name__)


@import_settlement_bp.route("/api/imports/settlement-candidates", methods=["GET"])
@login_required
@roles_required("admin", "support")
def get_settlement_candidates():
    """Retorna lista de importações disponíveis para conciliação e fechamento."""
    try:
        with db() as conn:
            rows = conn.execute(
                """
                SELECT id, reference, supplier_name, status, step, invoice_no, bl_no,
                       pi_amount_usd, ci_amount_usd, cost_factor
                FROM imports
                ORDER BY CASE WHEN step = 'fechado' THEN 1 ELSE 0 END, id DESC
                """
            ).fetchall()
            return jsonify({
                "success": True,
                "imports": [dict(r) for r in rows],
            })
    except Exception as e:
        logger.error("Erro ao buscar candidatos de fechamento: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@import_settlement_bp.route("/api/imports/<int:iid>/settlement-baseline", methods=["GET"])
@login_required
@roles_required("admin", "support")
def get_settlement_baseline(iid: int):
    """Retorna o panorama financeiro e documental previsto para a importação."""
    try:
        with db() as conn:
            baseline = get_import_baseline_for_settlement(iid, conn)
            if not baseline:
                return jsonify({"success": False, "error": "Importação não encontrada"}), 404
            return jsonify({"success": True, "baseline": baseline})
    except Exception as e:
        logger.error("Erro ao carregar baseline para import_id=%d: %s", iid, e)
        return jsonify({"success": False, "error": str(e)}), 500


@import_settlement_bp.route("/api/imports/analyze-settlement", methods=["POST"])
@login_required
@roles_required("admin", "support")
def analyze_settlement_batch():
    """Recebe arquivos de fechamento/prestação de contas, classifica por IA e cruza com a importação."""
    try:
        iid = request.form.get("import_id")
        if not iid:
            return jsonify({"success": False, "error": "Selecione a importação para o fechamento."}), 400
        iid = int(iid)

        user_notes = (request.form.get("document_notes") or "").strip()
        files = request.files.getlist("documents")

        if not files or all(f.filename == "" for f in files):
            return jsonify({"success": False, "error": "Nenhum documento de fechamento foi enviado."}), 400

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        with db() as conn:
            baseline = get_import_baseline_for_settlement(iid, conn)
            if not baseline:
                return jsonify({"success": False, "error": "Importação não encontrada."}), 404

            detected_docs = []

            for f in files:
                if not f or not f.filename:
                    continue

                orig_filename = secure_filename(f.filename)
                file_bytes = f.read()
                if not file_bytes:
                    continue

                file_hash = calculate_file_hash(file_bytes)
                unique_filename = f"settle_{iid}_{file_hash[:8]}_{orig_filename}"
                save_path = os.path.join(upload_folder, unique_filename)

                # Salvar no disco
                with open(save_path, "wb") as out_f:
                    out_f.write(file_bytes)

                # Analisar com IA Gemini
                mime = f.content_type or "application/pdf"
                ai_res = classify_and_extract_document(
                    file_bytes=file_bytes,
                    filename=orig_filename,
                    mime_type=mime,
                    import_context={
                        "reference": baseline.get("reference"),
                        "supplier_name": baseline.get("supplier_name"),
                    },
                    user_notes=user_notes,
                )

                doc_data = ai_res.get("data") or {}
                doc_type = ai_res.get("doc_type") or "OTHER"

                # Normalizar nomes
                if doc_type in ("TAX_GUIDE", "ICMS_GUIDE"):
                    doc_type = "ICMS_GUIDE"
                elif doc_type in ("BROKER_SETTLEMENT", "FECHAMENTO_DESPACHANTE"):
                    doc_type = "FECHAMENTO_DESPACHANTE"

                detected_docs.append({
                    "filename": orig_filename,
                    "unique_filename": unique_filename,
                    "file_hash": file_hash,
                    "file_size": len(file_bytes),
                    "doc_type": doc_type,
                    "title": ai_res.get("title", orig_filename),
                    "document_number": doc_data.get("document_number"),
                    "issue_date": doc_data.get("issue_date"),
                    "total_amount": doc_data.get("total_amount") or 0.0,
                    "currency": doc_data.get("currency") or "BRL",
                    "summary": doc_data.get("summary", ""),
                })

            # Cruzamento de dados com a importação
            reconciliation = cross_reference_settlement_documents(iid, detected_docs, baseline)

            return jsonify({
                "success": True,
                "import_id": iid,
                "baseline": baseline,
                "detected_docs": detected_docs,
                "reconciliation": reconciliation,
            })

    except Exception as e:
        logger.error("Erro na análise de fechamento com IA: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@import_settlement_bp.route("/api/imports/<int:iid>/commit-settlement", methods=["POST"])
@login_required
@roles_required("admin", "support")
def commit_settlement(iid: int):
    """Grava os documentos no banco, consolida as despesas e opcionalmente fecha o processo."""
    try:
        data = request.get_json(silent=True) or {}
        detected_docs = data.get("detected_docs") or []
        close_process = bool(data.get("close_process", False))

        me = current_user() or {}
        user_id = me.get("id")

        result = apply_settlement_reconciliation(
            import_id=iid,
            user_id=user_id,
            detected_docs=detected_docs,
            close_process=close_process,
        )

        return jsonify({
            "success": True,
            "message": "Conciliação de fechamento concluída com sucesso!",
            "result": result,
        })
    except Exception as e:
        logger.error("Erro ao confirmar conciliação de fechamento para import_id=%d: %s", iid, e)
        return jsonify({"success": False, "error": str(e)}), 500
