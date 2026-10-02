"""
M-One Import Lifecycle Blueprint (routes/import_lifecycle_routes.py)
Gerencia o arquivamento, desarquivamento e exclusão segura de importações,
garantindo a preservação total de chassis no estoque e documentos no repositório.
"""

from __future__ import annotations

import logging
from flask import Blueprint, flash, jsonify, redirect, request, url_for

from database import db
from routes.helpers import audit, current_user, login_required, roles_required

logger = logging.getLogger(__name__)

import_lifecycle_bp = Blueprint("import_lifecycle", __name__)


@import_lifecycle_bp.route("/imports/<int:iid>/archive", methods=["POST"])
@login_required
@roles_required("admin", "support")
def archive_import(iid: int):
    """Arquiva um processo de importação, ocultando-o da listagem ativa."""
    return_to = request.form.get("return_to", "").strip()
    with db() as conn:
        imp = conn.execute("SELECT id, reference FROM imports WHERE id = %s", (iid,)).fetchone()
        if not imp:
            flash("Importação não encontrada.", "error")
            return redirect(return_to or url_for("imports.imports"))

        conn.execute("UPDATE imports SET is_archived = TRUE WHERE id = %s", (iid,))
        conn.commit()
        audit("import.archived", f"import_id={iid}, ref={imp['reference']}")

    flash(f"Importação '{imp['reference']}' arquivada com sucesso!", "success")
    return redirect(return_to or url_for("imports.imports", tab="active"))


@import_lifecycle_bp.route("/imports/<int:iid>/unarchive", methods=["POST"])
@login_required
@roles_required("admin", "support")
def unarchive_import(iid: int):
    """Restaura uma importação arquivada de volta para a listagem ativa."""
    return_to = request.form.get("return_to", "").strip()
    with db() as conn:
        imp = conn.execute("SELECT id, reference FROM imports WHERE id = %s", (iid,)).fetchone()
        if not imp:
            flash("Importação não encontrada.", "error")
            return redirect(return_to or url_for("imports.imports"))

        conn.execute("UPDATE imports SET is_archived = FALSE WHERE id = %s", (iid,))
        conn.commit()
        audit("import.unarchived", f"import_id={iid}, ref={imp['reference']}")

    flash(f"Importação '{imp['reference']}' restaurada para a lista de ativas!", "success")
    return redirect(return_to or url_for("imports.imports", tab="archived"))


@import_lifecycle_bp.route("/imports/<int:iid>/delete", methods=["POST"])
@login_required
@roles_required("admin", "support")
def delete_import(iid: int):
    """
    Exclui a importação do sistema preservando integralmente os dados de entrada:
    - Chassis continuam no estoque físico desvinculados, etiquetados com [Lote Original: REF].
    - Documentos continuam preservados na Central de Documentos vinculados à batch_reference.
    """
    return_to = request.form.get("return_to", "").strip()
    with db() as conn:
        imp = conn.execute("SELECT id, reference FROM imports WHERE id = %s", (iid,)).fetchone()
        if not imp:
            flash("Importação não encontrada.", "error")
            return redirect(return_to or url_for("imports.imports"))

        ref = imp["reference"]

        # 1. Contar chassis vinculados para log
        chassis_count_row = conn.execute("SELECT COUNT(*) as c FROM stock_units WHERE import_id = %s", (iid,)).fetchone()
        chassis_count = chassis_count_row["c"] if chassis_count_row else 0

        # 2. Preservar chassis no estoque desvinculando foreign key e carimbando lote original
        conn.execute(
            """
            UPDATE stock_units 
            SET notes = TRIM(CONCAT(COALESCE(notes, ''), ' [Lote Original: ', %s::text, ']')),
                import_id = NULL
            WHERE import_id = %s
            """,
            (ref, iid),
        )

        # 3. Preservar pagamentos do fluxo financeiro geral
        conn.execute("UPDATE payments SET import_id = NULL WHERE import_id = %s", (iid,))

        # 4. Preservar documentos na Central de Documentos
        conn.execute(
            """
            UPDATE import_documents 
            SET batch_reference = COALESCE(batch_reference, %s),
                import_id = NULL 
            WHERE import_id = %s
            """,
            (ref, iid),
        )

        # 5. Limpar tabelas auxiliares que pertencem estritamente ao processo do lote
        conn.execute("DELETE FROM import_items WHERE import_id = %s", (iid,))
        conn.execute("DELETE FROM import_payments_china WHERE import_id = %s", (iid,))
        conn.execute("DELETE FROM import_brazil_expenses WHERE import_id = %s", (iid,))
        conn.execute("DELETE FROM import_numerario WHERE import_id = %s", (iid,))
        conn.execute("DELETE FROM import_checks WHERE import_id = %s", (iid,))
        conn.execute("DELETE FROM import_costs WHERE import_id = %s", (iid,))

        # 6. Deletar a importação em si
        conn.execute("DELETE FROM imports WHERE id = %s", (iid,))
        conn.commit()

        audit("import.deleted", f"import_id={iid}, ref={ref}, chassis_preserved={chassis_count}")

    flash(f"Importação '{ref}' excluída com sucesso! Os {chassis_count} chassis e todos os documentos foram preservados no sistema.", "success")
    return redirect(return_to or url_for("imports.imports", tab="archived"))
