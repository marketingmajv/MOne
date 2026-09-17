"""
M-One Import Document Management Blueprint (routes/import_document_routes.py)
Rotas de envio em lote, classificação por IA, verificação de duplicidade e controle de versões de documentos aduaneiros.
"""

from __future__ import annotations

import logging
import os
from flask import Blueprint, current_app, flash, jsonify, redirect, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from database import db
from routes.helpers import audit, current_user, login_required, roles_required
from services.import_ai_service import (
    DOC_TYPES_MAP,
    analyze_import_batch,
    calculate_file_hash,
    classify_and_extract_document,
)
from services.import_audit_service import run_import_audit_checks
from services.import_calculator import calculate_import_financials
from services.import_rules_service import (
    get_document_rules,
    reset_document_rules_to_default,
    save_document_rules,
)

logger = logging.getLogger(__name__)

import_document_bp = Blueprint("import_document", __name__)


@import_document_bp.route("/api/imports/<int:iid>/documents/upload-batch", methods=["POST"])
@login_required
@roles_required("admin", "support")
def upload_documents_batch(iid: int):
    """Processa o upload múltiplo de arquivos com classificação automática da IA e detecção de duplicatas."""
    files = request.files.getlist("documents")
    if not files or all(f.filename == "" for f in files):
        flash("Nenhum arquivo foi selecionado para envio.", "error")
        return redirect(url_for("imports.import_detail", iid=iid, tab="documents"))

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    imported_count = 0
    duplicate_count = 0

    with db() as conn:
        imp = conn.execute("SELECT * FROM imports WHERE id = %s", (iid,)).fetchone()
        if not imp:
            flash("Importação não encontrada.", "error")
            return redirect(url_for("imports.imports"))

        import_ctx = dict(imp)
        me = current_user() or {}
        user_id = me.get("id")

        for f in files:
            if not f or not f.filename:
                continue

            orig_filename = secure_filename(f.filename)
            file_bytes = f.read()
            if not file_bytes:
                continue

            file_hash = calculate_file_hash(file_bytes)

            # Verificar duplicidade pelo hash
            existing = conn.execute(
                "SELECT id, title FROM import_documents WHERE import_id = %s AND file_hash = %s",
                (iid, file_hash),
            ).fetchone()
            if existing:
                duplicate_count += 1
                logger.info("Arquivo duplicado detectado para import_id=%d: %s", iid, orig_filename)
                continue

            # Classificação inteligente com IA
            mime = f.content_type or "application/pdf"
            ai_res = classify_and_extract_document(
                file_bytes=file_bytes,
                filename=orig_filename,
                mime_type=mime,
                import_context=import_ctx,
            )

            # Salvar arquivo no disco
            unique_filename = f"imp_{iid}_{file_hash[:8]}_{orig_filename}"
            save_path = os.path.join(upload_folder, unique_filename)
            with open(save_path, "wb") as out_f:
                out_f.write(file_bytes)

            doc_type = ai_res.get("doc_type", "OTHER")
            title = ai_res.get("title", orig_filename)
            extracted_data = ai_res.get("data", {})

            conn.execute(
                """
                INSERT INTO import_documents (
                    import_id, doc_type, title, filename, file_url, file_size, file_hash,
                    extracted_data, ai_status, uploaded_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processed', %s)
                """,
                (
                    iid,
                    doc_type,
                    title,
                    orig_filename,
                    unique_filename,
                    len(file_bytes),
                    file_hash,
                    json.dumps(extracted_data),
                    user_id,
                ),
            )
            imported_count += 1

        calculate_import_financials(iid, conn)
        run_import_audit_checks(iid, conn)
        audit("import.documents_uploaded", f"import_id={iid}, added={imported_count}, duplicates={duplicate_count}")

    msg = f"{imported_count} documento(s) classificado(s) e anexado(s) com sucesso!"
    if duplicate_count > 0:
        msg += f" ({duplicate_count} arquivo(s) duplicado(s) ignorado(s))."
    flash(msg, "success")

    return redirect(url_for("imports.import_detail", iid=iid, tab="documents"))


@import_document_bp.route("/api/imports/<int:iid>/documents/<int:doc_id>/reclassify", methods=["POST"])
@login_required
@roles_required("admin", "support")
def reclassify_document(iid: int, doc_id: int):
    """Permite alterar a categoria/tipo de um documento anexado."""
    new_type = request.form.get("doc_type", "OTHER")
    if new_type not in DOC_TYPES_MAP:
        new_type = "OTHER"

    with db() as conn:
        conn.execute(
            """
            UPDATE import_documents 
            SET doc_type = %s, title = %s
            WHERE id = %s AND import_id = %s
            """,
            (new_type, DOC_TYPES_MAP[new_type], doc_id, iid),
        )
        run_import_audit_checks(iid, conn)
        audit("import.doc_reclassified", f"import_id={iid}, doc_id={doc_id}, new_type={new_type}")

    flash("Classificação do documento atualizada com sucesso.", "success")
    return redirect(url_for("imports.import_detail", iid=iid, tab="documents"))


@import_document_bp.route("/api/imports/<int:iid>/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_document(iid: int, doc_id: int):
    """Remove um documento da importação."""
    with db() as conn:
        doc = conn.execute("SELECT * FROM import_documents WHERE id = %s AND import_id = %s", (doc_id, iid)).fetchone()
        if doc:
            upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
            file_path = os.path.join(upload_folder, doc["file_url"])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            conn.execute("DELETE FROM import_documents WHERE id = %s", (doc_id,))
            run_import_audit_checks(iid, conn)
            audit("import.doc_deleted", f"import_id={iid}, doc_id={doc_id}")

    flash("Documento removido com sucesso.", "success")
    return redirect(url_for("imports.import_detail", iid=iid, tab="documents"))


@import_document_bp.route("/api/imports/document-rules", methods=["GET"])
@login_required
@roles_required("admin", "support")
def get_rules():
    """Retorna as regras ativas de validação documental."""
    rules = get_document_rules()
    return jsonify({"success": True, "rules": rules})


@import_document_bp.route("/api/imports/document-rules", methods=["POST"])
@login_required
@roles_required("admin", "support")
def update_rules():
    """Salva a parametrização de regras documentais."""
    data = request.get_json() or {}
    rules = data.get("rules", [])
    if not rules:
        return jsonify({"success": False, "message": "Nenhuma regra fornecida."}), 400

    user = current_user() or {}
    ok = save_document_rules(rules, user_id=user.get("id"))
    if ok:
        return jsonify({"success": True, "message": "Regras atualizadas com sucesso!", "rules": get_document_rules()})
    return jsonify({"success": False, "message": "Falha ao persistir regras no banco."}), 500


@import_document_bp.route("/api/imports/document-rules/reset", methods=["POST"])
@login_required
@roles_required("admin", "support")
def reset_rules():
    """Restaura as regras para o padrão oficial."""
    user = current_user() or {}
    rules = reset_document_rules_to_default(user_id=user.get("id"))
    return jsonify({"success": True, "message": "Regras restauradas para o padrão oficial!", "rules": rules})


@import_document_bp.route("/api/imports/analyze-docs", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_analyze_import_docs():
    """Pré-preenchimento com IA a partir de arquivos selecionados no modal de criação."""
    file_objs = []
    
    # 1. Arquivos enviados em lote pelo Dropzone
    batch_files = request.files.getlist("documents")
    for f in batch_files:
        if f and f.filename:
            content = f.read()
            ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
            mime = "application/pdf" if ext == "pdf" else ("text/csv" if ext == "csv" else f"image/{ext if ext != 'jpg' else 'jpeg'}")
            file_objs.append({"bytes": content, "mime_type": mime, "filename": f.filename})

    # 2. Arquivos individuais enviados por campos específicos (fallback de compatibilidade)
    for key in ["invoice_file", "bl_file", "nf_entry_file", "chassis_file"]:
        f = request.files.get(key)
        if f and f.filename and not any(o["filename"] == f.filename for o in file_objs):
            content = f.read()
            ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
            mime = "application/pdf" if ext == "pdf" else ("text/csv" if ext == "csv" else f"image/{ext if ext != 'jpg' else 'jpeg'}")
            file_objs.append({"bytes": content, "mime_type": mime, "filename": f.filename})

    if not file_objs:
        return jsonify({"success": False, "message": "Nenhum arquivo enviado para análise da IA."})

    try:
        res = analyze_import_batch(file_objs)
        return jsonify(res)
    except Exception as e:
        logger.error("[api_analyze_import_docs] Erro na análise em lote: %s", e)
        return jsonify({"success": False, "message": f"Erro durante análise dos documentos: {str(e)}"})

