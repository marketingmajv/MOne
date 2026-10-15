"""
M-One Import Document Rules Blueprint (routes/import_rules_routes.py)
Rotas de parametrização e gestão das regras de validação documental e categorias alfandegárias.
"""

from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from database import db
from routes.helpers import current_user, login_required, roles_required, verify_password
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

logger = logging.getLogger(__name__)

import_rules_bp = Blueprint("import_rules", __name__)


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


@import_rules_bp.route("/api/imports/document-rules", methods=["GET"])
@login_required
@roles_required("admin", "support")
def get_rules():
    """Retorna as regras ativas de validação documental e os tipos essenciais."""
    rules = get_document_rules()
    return jsonify({"success": True, "rules": rules, "core_types": list(CORE_DOC_TYPES)})


@import_rules_bp.route("/api/imports/document-rules", methods=["POST"])
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


@import_rules_bp.route("/api/imports/document-rules/reset", methods=["POST"])
@login_required
@roles_required("admin", "support")
def reset_rules():
    """Restaura as regras para o padrão oficial."""
    user = current_user() or {}
    rules = reset_document_rules_to_default(user_id=user.get("id"))
    return jsonify({"success": True, "message": "Regras restauradas para o padrão oficial!", "rules": rules, "core_types": list(CORE_DOC_TYPES)})


@import_rules_bp.route("/api/imports/document-rules/add-category", methods=["POST"])
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


@import_rules_bp.route("/api/imports/document-rules/delete-category", methods=["POST"])
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


@import_rules_bp.route("/api/imports/document-rules/edit-category", methods=["POST"])
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


@import_rules_bp.route("/api/imports/document-rules/duplicate-category", methods=["POST"])
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
