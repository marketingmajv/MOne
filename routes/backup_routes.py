"""
M-One Backup & Disaster Recovery Blueprint (routes/backup_routes.py)
Gestão de cópias físicas de contingência, sincronização Google Drive e restauração.
Restrito à Diretoria e Administradores.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for

from routes.helpers import audit, login_required, roles_required
from services.backup_service import (
    LOCAL_BACKUP_DIR,
    generate_backup_package,
    get_backup_summary,
    list_backups,
)

logger = logging.getLogger(__name__)

backup_bp = Blueprint("backups", __name__)


@backup_bp.route("/admin/backups", methods=["GET"])
@login_required
@roles_required("admin", "support")
def backups_dashboard():
    """Painel de gestão de backups físicos, status de nuvem e contingência."""
    summary = get_backup_summary()
    return render_template("backups.html", summary=summary)


@backup_bp.route("/admin/backups/generate", methods=["POST"])
@login_required
@roles_required("admin", "support")
def backup_generate_manual():
    """Dispara a geração manual de uma nova cópia completa imediatamente."""
    try:
        current_user = getattr(request, "current_user", None) or {}
        username = current_user.get("username", "admin")
        res = generate_backup_package(triggered_by=f"manual:{username}")
        
        msg = f"Backup gerado com sucesso! ({res['filename']}, {res['total_records']} registros)."
        if res.get("gdrive_synced"):
            msg += " Sincronizado automaticamente com o Google Drive."
        
        audit("backup.manual_generated", f"Backup {res['filename']} gerado por {username}")
        
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({
                "success": True,
                "message": msg,
                "download_url": url_for("backups.backup_download", filename=res["filename"]),
                "details": res
            })
            
        flash(msg, "success")
    except Exception as e:
        logger.error("Erro ao gerar backup manual: %s", e)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Falha ao gerar backup: {e}", "danger")

    return redirect(url_for("backups.backups_dashboard"))


@backup_bp.route("/admin/backups/download/<filename>", methods=["GET"])
@login_required
@roles_required("admin", "support")
def backup_download(filename: str):
    """Permite à Diretoria baixar o pacote .zip de backup para seu computador."""
    # Previne path traversal
    safe_filename = Path(filename).name
    target_path = LOCAL_BACKUP_DIR / safe_filename

    if not target_path.exists() or not safe_filename.endswith(".zip"):
        flash("Arquivo de backup solicitado não foi encontrado.", "danger")
        return redirect(url_for("backups.backups_dashboard"))

    audit("backup.downloaded", f"Download do backup {safe_filename}")
    return send_file(
        str(target_path),
        as_attachment=True,
        download_name=safe_filename,
        mimetype="application/zip"
    )
