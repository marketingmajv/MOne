"""
M-One Import Document Management Blueprint (routes/import_document_routes.py)
Rotas de envio em lote, classificação por IA, verificação de duplicidade e controle de versões de documentos aduaneiros.
"""

from __future__ import annotations

import json
import logging
import os
from flask import Blueprint, current_app, flash, jsonify, redirect, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from database import db
from routes.helpers import audit, current_user, login_required, roles_required, verify_password
from services.import_ai_service import (
    DOC_TYPES_MAP,
    analyze_import_batch,
    calculate_file_hash,
    classify_and_extract_document,
)
from services.import_audit_service import run_import_audit_checks
from services.import_calculator import calculate_import_financials
from services.import_rules_service import (
    CORE_DOC_TYPES,
    add_custom_document_rule,
    delete_document_rule,
    duplicate_document_rule,
    get_document_rules,
    reset_document_rules_to_default,
    save_document_rules,
    update_document_rule_details,
)

import re
from typing import Any

logger = logging.getLogger(__name__)

import_document_bp = Blueprint("import_document", __name__)


def clean_float(val: Any) -> float:
    """Converte com segurança valores numéricos ou strings formatadas (ex: 'R$ 1.500,00', '1,500.00') em float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return 0.0
    s = re.sub(r"[^\d.,-]", "", s)
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


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
            extracted_data = ai_res.get("extracted_data") or ai_res.get("data") or {}

            if not isinstance(extracted_data, dict):
                extracted_data = {}

            new_doc = conn.execute(
                """
                INSERT INTO import_documents (
                    import_id, doc_type, title, filename, file_url, file_size, file_hash,
                    extracted_data, ai_status, uploaded_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processed', %s)
                RETURNING id
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
            ).fetchone()
            doc_id = new_doc["id"] if new_doc else None
            imported_count += 1

            # Inclusão e vinculação automática de lançamentos no financeiro via IA
            try:
                amt_val = clean_float(extracted_data.get("total_amount"))
                issue_date = extracted_data.get("issue_date") or None
                if issue_date and len(str(issue_date)) < 8:
                    issue_date = None
                summary_text = str(extracted_data.get("summary") or f"{title} ({orig_filename})")

                # 1. Numerário Aduaneiro
                if doc_type in ["NUMERARIO", "FECHAMENTO_DESPACHANTE", "BROKER_SETTLEMENT"]:
                    entry_type = "actual_expense" if doc_type in ["FECHAMENTO_DESPACHANTE", "BROKER_SETTLEMENT"] else "advance"
                    conn.execute(
                        """
                        INSERT INTO import_numerario (import_id, entry_type, amount, entry_date, description, document_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (iid, entry_type, amt_val, issue_date, summary_text, doc_id),
                    )

                # 2. Despesas e Tributos no Brasil
                elif doc_type in ["ICMS_GUIDE", "TAX_GUIDE", "NF_FRETE_CARRETA", "AGENTE_CARGA_BR", "AJUDANTES_PAGTO", "ENTRY_NF"]:
                    cat_map = {
                        "ICMS_GUIDE": "impostos",
                        "TAX_GUIDE": "impostos",
                        "NF_FRETE_CARRETA": "transporte_rodoviario",
                        "AGENTE_CARGA_BR": "taxa_maritima",
                        "AJUDANTES_PAGTO": "outras",
                        "ENTRY_NF": "outras",
                    }
                    category = cat_map.get(doc_type, "outras")
                    provider_name = str(extracted_data.get("supplier_name") or extracted_data.get("buyer_name") or DOC_TYPES_MAP.get(doc_type, "Lançamento IA"))
                    conn.execute(
                        """
                        INSERT INTO import_brazil_expenses (
                            import_id, category, provider, description, predicted_amount, actual_amount,
                            paid_at, payment_mode, document_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'direct', %s)
                        """,
                        (iid, category, provider_name, summary_text, amt_val, amt_val, issue_date, doc_id),
                    )

                # 3. Pagamentos na China / Remessas / Câmbio
                elif doc_type in ["EXCHANGE_CONTRACT", "SUPPLIER_PAYMENT"]:
                    curr = str(extracted_data.get("currency") or "USD").upper()
                    amt_usd = amt_val if "USD" in curr else 0.0
                    amt_brl = amt_val if "BRL" in curr else 0.0
                    exch_rate = clean_float(extracted_data.get("exchange_rate")) or None
                    conn.execute(
                        """
                        INSERT INTO import_payments_china (
                            import_id, payment_category, description, amount_usd, amount_brl,
                            exchange_rate, paid_at, document_id, is_verified
                        ) VALUES (%s, 'ci_payment', %s, %s, %s, %s, %s, %s, TRUE)
                        """,
                        (iid, summary_text, amt_usd, amt_brl, exch_rate, issue_date, doc_id),
                    )
            except Exception as auto_err:
                logger.warning("[upload_documents_batch] Falha na inserção automática do financeiro para %s: %s", orig_filename, auto_err, exc_info=True)

            # Vinculação automática de chassis ao estoque se for planilha/CHASSIS_LIST
            if doc_type == "CHASSIS_LIST" or orig_filename.lower().endswith((".xlsx", ".xls", ".csv")):
                try:
                    from services.chassis_service import parse_chassis_file

                    class MemFile:
                        def __init__(self, fn: str, b: bytes):
                            self.filename = fn
                            self.content = b

                        def read(self):
                            return self.content

                    ch_rows = parse_chassis_file(MemFile(orig_filename, file_bytes))
                    if ch_rows:
                        prod_map = {p["name"].strip().lower(): p["id"] for p in conn.execute("SELECT id, name FROM products").fetchall()}
                        for cr in ch_rows:
                            m_name = cr.get("model", "Veículo Elétrico").strip()
                            p_id = prod_map.get(m_name.lower())
                            if not p_id:
                                res_p = conn.execute("INSERT INTO products (name, category) VALUES (%s, 'Motos Elétricas') RETURNING id", (m_name,)).fetchone()
                                p_id = res_p["id"]
                                prod_map[m_name.lower()] = p_id
                            conn.execute(
                                """
                                INSERT INTO stock_units (product_id, chassis, motor_no, color, import_id, status)
                                VALUES (%s, %s, %s, %s, %s, 'unreleased')
                                ON CONFLICT (chassis) DO UPDATE 
                                SET motor_no = EXCLUDED.motor_no, 
                                    color = EXCLUDED.color, 
                                    import_id = EXCLUDED.import_id;
                                """,
                                (p_id, cr["chassis"].strip(), cr.get("motor", "").strip(), cr.get("color", "").strip(), iid),
                            )
                except Exception as err:
                    logger.debug("[upload_documents_batch] Planilha %s sem chassis válidos: %s", orig_filename, err)

        calculate_import_financials(iid, conn)
        run_import_audit_checks(iid, conn)
        audit("import.documents_uploaded", f"import_id={iid}, added={imported_count}, duplicates={duplicate_count}")

    msg = f"🤖 IA Analisou: {imported_count} documento(s) classificado(s) e incluído(s) automaticamente no financeiro!"
    if duplicate_count > 0:
        msg += f" ({duplicate_count} arquivo(s) duplicado(s) ignorado(s))."
    flash(msg, "success")

    target_tab = request.args.get("tab") or request.form.get("tab") or "documents"
    return redirect(url_for("imports.import_detail", iid=iid, tab=target_tab))


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
    """Retorna as regras ativas de validação documental e os tipos essenciais."""
    rules = get_document_rules()
    return jsonify({"success": True, "rules": rules, "core_types": list(CORE_DOC_TYPES)})


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
        return jsonify({"success": True, "message": "Regras atualizadas com sucesso!", "rules": get_document_rules(), "core_types": list(CORE_DOC_TYPES)})
    return jsonify({"success": False, "message": "Falha ao persistir regras no banco."}), 500


@import_document_bp.route("/api/imports/document-rules/reset", methods=["POST"])
@login_required
@roles_required("admin", "support")
def reset_rules():
    """Restaura as regras para o padrão oficial."""
    user = current_user() or {}
    rules = reset_document_rules_to_default(user_id=user.get("id"))
    return jsonify({"success": True, "message": "Regras restauradas para o padrão oficial!", "rules": rules, "core_types": list(CORE_DOC_TYPES)})


@import_document_bp.route("/api/imports/document-rules/add-category", methods=["POST"])
@login_required
@roles_required("admin", "support")
def add_rule_category():
    """Cadastra uma nova categoria customizada de documento."""
    data = request.get_json() or {}
    doc_type = data.get("doc_type", "").strip()
    label = data.get("label", "").strip()
    req_water = bool(data.get("required_on_water", False))
    req_cleared = bool(data.get("required_cleared", False))
    allow_post = bool(data.get("allow_post_attach", True))
    user = current_user() or {}

    ok, msg = add_custom_document_rule(
        doc_type=doc_type,
        label=label,
        required_on_water=req_water,
        required_cleared=req_cleared,
        allow_post_attach=allow_post,
        user_id=user.get("id"),
    )
    if ok:
        return jsonify({"success": True, "message": msg, "rules": get_document_rules(), "core_types": list(CORE_DOC_TYPES)})
    return jsonify({"success": False, "message": msg}), 400


def _verify_admin_password(password: str) -> tuple[bool, str]:
    """Valida a senha do administrador logado antes de operações sensíveis em documentos essenciais."""
    user = current_user() or {}
    if user.get("role") != "admin":
        return False, "Operação restrita exclusivamente a administradores."
    if not password:
        return False, "Senha de administrador não informada."

    with db() as conn:
        u = conn.execute("SELECT password_hash FROM users WHERE id = %s", (user.get("id"),)).fetchone()
        if not u or not u.get("password_hash"):
            return False, "Usuário não encontrado ou senha não configurada."
        is_valid, _ = verify_password(u["password_hash"], password)
        if not is_valid:
            return False, "Senha de administrador incorreta. Ação não autorizada."
    return True, ""


@import_document_bp.route("/api/imports/document-rules/delete-category", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_rule_category():
    """Exclui uma categoria. Se for documento essencial (core), exige senha do administrador."""
    data = request.get_json() or {}
    doc_type = data.get("doc_type", "").strip().upper()
    admin_password = data.get("admin_password", "")
    user = current_user() or {}

    is_core = doc_type in CORE_DOC_TYPES
    is_admin_override = False
    if is_core:
        authorized, reason = _verify_admin_password(admin_password)
        if not authorized:
            return jsonify({"success": False, "message": reason, "requires_password": True}), 403
        is_admin_override = True

    ok, msg = delete_document_rule(doc_type=doc_type, user_id=user.get("id"), is_admin_override=is_admin_override)
    if ok:
        return jsonify({"success": True, "message": msg, "rules": get_document_rules(), "core_types": list(CORE_DOC_TYPES)})
    return jsonify({"success": False, "message": msg}), 400


@import_document_bp.route("/api/imports/document-rules/edit-category", methods=["POST"])
@login_required
@roles_required("admin", "support")
def edit_rule_category():
    """Edita uma categoria existente. Se for documento essencial (core), exige senha do administrador."""
    data = request.get_json() or {}
    doc_type = data.get("doc_type", "").strip().upper()
    label = data.get("label", "").strip()
    req_water = bool(data.get("required_on_water", False))
    req_cleared = bool(data.get("required_cleared", False))
    allow_post = bool(data.get("allow_post_attach", True))
    admin_password = data.get("admin_password", "")
    user = current_user() or {}

    is_core = doc_type in CORE_DOC_TYPES
    if is_core:
        authorized, reason = _verify_admin_password(admin_password)
        if not authorized:
            return jsonify({"success": False, "message": reason, "requires_password": True}), 403

    ok, msg = update_document_rule_details(
        doc_type=doc_type,
        label=label,
        required_on_water=req_water,
        required_cleared=req_cleared,
        allow_post_attach=allow_post,
        user_id=user.get("id"),
    )
    if ok:
        return jsonify({"success": True, "message": msg, "rules": get_document_rules(), "core_types": list(CORE_DOC_TYPES)})
    return jsonify({"success": False, "message": msg}), 400


@import_document_bp.route("/api/imports/document-rules/duplicate-category", methods=["POST"])
@login_required
@roles_required("admin", "support")
def duplicate_rule_category():
    """Duplica uma categoria. Se a origem for documento essencial (core), exige senha do administrador."""
    data = request.get_json() or {}
    source_doc_type = data.get("source_doc_type", "").strip().upper()
    new_doc_type = data.get("new_doc_type", "").strip().upper()
    new_label = data.get("new_label", "").strip()
    admin_password = data.get("admin_password", "")
    user = current_user() or {}

    is_core = source_doc_type in CORE_DOC_TYPES
    if is_core:
        authorized, reason = _verify_admin_password(admin_password)
        if not authorized:
            return jsonify({"success": False, "message": reason, "requires_password": True}), 403

    ok, msg = duplicate_document_rule(
        source_doc_type=source_doc_type,
        new_doc_type=new_doc_type,
        new_label=new_label,
        user_id=user.get("id"),
    )
    if ok:
        return jsonify({"success": True, "message": msg, "rules": get_document_rules(), "core_types": list(CORE_DOC_TYPES)})
    return jsonify({"success": False, "message": msg}), 400


@import_document_bp.route("/api/imports/analyze-docs", methods=["POST"])
@import_document_bp.route("/api/imports/analyze-batch", methods=["POST"])
@login_required
@roles_required("admin", "support")
def api_analyze_import_docs():
    """Pré-preenchimento com IA a partir de arquivos selecionados no modal de criação."""
    file_objs = []

    # 1. Arquivos específicos do fechamento despachante (upload separado)
    fechamento_files = request.files.getlist("fechamento_docs") or request.files.getlist("fechamento_file")
    if not fechamento_files:
        f_single = request.files.get("fechamento_file") or request.files.get("fechamento_despachante")
        if f_single and f_single.filename:
            fechamento_files = [f_single]

    def _get_mime(fn: str) -> str:
        e = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
        if e == "pdf":
            return "application/pdf"
        if e in ["xlsx", "xls"]:
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if e == "xlsx" else "application/vnd.ms-excel"
        if e == "csv":
            return "text/csv"
        return f"image/{e if e != 'jpg' else 'jpeg'}"

    for f in fechamento_files:
        if f and f.filename:
            content = f.read()
            file_objs.append({
                "bytes": content,
                "mime_type": _get_mime(f.filename),
                "filename": f.filename,
                "forced_doc_type": "FECHAMENTO_DESPACHANTE",
            })

    # 2. Arquivos enviados em lote pelo Dropzone principal
    batch_files = request.files.getlist("documents")
    for f in batch_files:
        if f and f.filename:
            content = f.read()
            file_objs.append({"bytes": content, "mime_type": _get_mime(f.filename), "filename": f.filename})

    # 3. Arquivos individuais enviados por campos legados
    for key in ["invoice_file", "bl_file", "nf_entry_file", "chassis_file"]:
        f = request.files.get(key)
        if f and f.filename and not any(o["filename"] == f.filename for o in file_objs):
            content = f.read()
            file_objs.append({"bytes": content, "mime_type": _get_mime(f.filename), "filename": f.filename})

    if not file_objs:
        return jsonify({"success": False, "message": "Nenhum arquivo enviado para análise da IA."})

    user_notes = (request.form.get("document_notes") or request.form.get("user_notes") or "").strip()

    try:
        res = analyze_import_batch(file_objs, user_notes=user_notes)
        return jsonify(res)
    except Exception as e:
        logger.error("[api_analyze_import_docs] Erro na análise em lote: %s", e)
        return jsonify({"success": False, "message": f"Erro durante análise dos documentos: {str(e)}"})

