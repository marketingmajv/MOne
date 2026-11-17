"""
M-One Stock Audit & Sync Blueprint (routes/stock_audit_routes.py)
Rotas de sincronização da planilha COLVIX, conferência física contínua por bipagem,
marcação de produto montado e download do Relatório Executivo em PDF.
"""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, request, send_file, url_for

from routes.helpers import audit, current_user, login_required, permission_required
from services.stock_audit_pdf_service import build_stock_audit_pdf
from services.stock_audit_service import (
    finish_stock_audit,
    get_active_audit,
    get_audit_summary,
    list_recent_audits,
    scan_chassis_in_audit,
    start_stock_audit,
)
from services.stock_chassis_action_service import mark_chassis_assembled
from services.stock_sync_service import get_stock_locations, sync_colvix_sheets_to_stock

stock_audit_bp = Blueprint("stock_audit", __name__)


@stock_audit_bp.route("/stock/sync-sheets", methods=["POST"])
@login_required
@permission_required("stock")
def sync_sheets():
    res = sync_colvix_sheets_to_stock()
    audit("stock.sync_sheets", f"inserted={res['inserted']} skipped={res['skipped_existing']}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(res)
    if res["inserted"] > 0:
        flash(f"✅ Planilha COLVIX sincronizada: {res['inserted']} novo(s) chassi(s) importado(s).", "success")
    else:
        flash(f"ℹ️ Planilha COLVIX verificada: nenhum chassi novo ({res['skipped_existing']} já existentes).", "info")
    return redirect(url_for("stock"))


@stock_audit_bp.route("/stock/audit/state", methods=["GET"])
@login_required
@permission_required("stock")
def audit_state():
    active = get_active_audit()
    active_summary = get_audit_summary(active["id"]) if active else None
    recent = list_recent_audits(limit=15)
    locations = get_stock_locations()
    return jsonify({
        "ok": True,
        "active": active_summary,
        "recent": recent,
        "locations": locations,
    })


@stock_audit_bp.route("/stock/audit/start", methods=["POST"])
@login_required
@permission_required("stock")
def audit_start():
    data = request.get_json(silent=True) or request.form or {}
    location_scope = data.get("location_scope", "Automático")
    existing = get_active_audit()
    if existing:
        summary = get_audit_summary(existing["id"])
        return jsonify({"ok": True, "already_active": True, "summary": summary})

    u = current_user() or {}
    created = start_stock_audit(
        location_scope=location_scope,
        user_id=u.get("id"),
        user_name=u.get("name") or u.get("username") or "Operador",
    )
    audit("stock.audit_started", f"audit_id={created['id']} scope={location_scope}")
    summary = get_audit_summary(created["id"])
    return jsonify({"ok": True, "summary": summary})


@stock_audit_bp.route("/stock/audit/scan", methods=["POST"])
@login_required
@permission_required("stock")
def audit_scan():
    data = request.get_json(silent=True) or request.form or {}
    audit_id = int(data.get("audit_id") or 0)
    chassis = data.get("chassis", "")
    u = current_user() or {}
    res = scan_chassis_in_audit(audit_id, chassis, u.get("id"))
    status_code = 200 if res.get("ok") else 400
    return jsonify(res), status_code


@stock_audit_bp.route("/stock/audit/<int:audit_id>/finish", methods=["POST"])
@login_required
@permission_required("stock")
def audit_finish(audit_id: int):
    summary = finish_stock_audit(audit_id)
    if not summary:
        return jsonify({"ok": False, "error": "Conferência não encontrada."}), 404
    audit(
        "stock.audit_finished",
        f"audit_id={audit_id} scanned={summary['scanned_count']} missing={summary['missing_count']} alerts={summary['alerts_count']}",
    )
    return jsonify({"ok": True, "summary": summary})


@stock_audit_bp.route("/stock/audit/<int:audit_id>/pdf", methods=["GET"])
@login_required
@permission_required("stock")
def audit_pdf(audit_id: int):
    summary = get_audit_summary(audit_id)
    if not summary:
        flash("Relatório de conferência não encontrado.", "danger")
        return redirect(url_for("stock"))
    pdf_buf = build_stock_audit_pdf(summary)
    filename = f"conferencia_estoque_{audit_id}.pdf"
    return send_file(
        pdf_buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@stock_audit_bp.route("/stock/chassis/assemble", methods=["POST"])
@login_required
@permission_required("stock")
def chassis_assemble():
    data = request.get_json(silent=True) or request.form or {}
    chassis = data.get("chassis", "")
    u = current_user() or {}
    res = mark_chassis_assembled(chassis, u.get("id"))
    if res.get("ok"):
        audit("stock.chassis_assembled", f"chassis={res['chassis']}")
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(res), (200 if res.get("ok") else 400)
    flash("Chassi marcado como Montado (Exposição/Loja)." if res.get("ok") else res.get("error", "Erro"), "success" if res.get("ok") else "danger")
    return redirect(url_for("stock"))
