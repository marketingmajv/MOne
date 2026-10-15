"""
M-One BotConversa & Campaign Monitoring Routes (routes/botconversa_routes.py)
Endpoints de API para gerenciamento de credenciais, diagnósticos de funil e download de relatórios em PDF.
Segue o padrão modular (< 500 linhas) do M-One.
"""

from __future__ import annotations

import logging
import os
from flask import Blueprint, jsonify, request, send_file

from services.botconversa_service import (
    generate_cross_funnel_diagnosis,
    get_botconversa_config,
    save_botconversa_config,
    test_botconversa_connection,
)

logger = logging.getLogger(__name__)

botconversa_bp = Blueprint("botconversa", __name__, url_prefix="/api/botconversa")


@botconversa_bp.route("/status", methods=["GET"])
def get_status():
    """Retorna o status consolidado da conexão BotConversa e das campanhas."""
    cfg = get_botconversa_config()
    test_res = test_botconversa_connection() if cfg.get("api_key") else {"valid": False, "message": "API Key pendente de cadastro"}
    
    return jsonify({
        "status": "success",
        "service_name": "botconversa",
        "configured": bool(cfg.get("api_key")),
        "api_url": cfg.get("api_url"),
        "updated_at": str(cfg.get("updated_at") or ""),
        "connection_test": test_res,
    })


@botconversa_bp.route("/config", methods=["POST"])
def update_config():
    """Salva a chave de API e configurações do BotConversa."""
    data = request.get_json(silent=True) or {}
    api_key = data.get("api_key", "").strip()
    api_url = data.get("api_url", "").strip()
    settings = data.get("settings", {})

    if not api_key:
        return jsonify({"status": "error", "message": "A chave de API é obrigatória."}), 400

    saved = save_botconversa_config(api_key, api_url=api_url, settings=settings)
    if not saved:
        return jsonify({"status": "error", "message": "Falha ao gravar configurações no banco."}), 500

    test_res = test_botconversa_connection(custom_key=api_key)
    return jsonify({
        "status": "success",
        "message": "Configurações do BotConversa salvas com sucesso!",
        "connection_test": test_res,
    })


@botconversa_bp.route("/diagnosis", methods=["GET"])
def get_diagnosis():
    """Retorna o diagnóstico estruturado do funil Meta Ads + BotConversa."""
    days = int(request.args.get("days", 7))
    try:
        diag = generate_cross_funnel_diagnosis(days=days)
        return jsonify({"status": "success", "diagnosis": diag})
    except Exception as e:
        logger.error("[botconversa_bp.get_diagnosis error]: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@botconversa_bp.route("/generate-pdf", methods=["POST"])
def generate_pdf():
    """Aciona o gerador de PDF ReportLab sob demanda e retorna os metadados do documento gerado."""
    days = int(request.args.get("days", 7))
    try:
        from scripts.generate_botconversa_diagnosis_pdf import build_diagnosis_pdf
        pdf_path = build_diagnosis_pdf(days=days)
        filename = os.path.basename(pdf_path)
        return jsonify({
            "status": "success",
            "message": "PDF de diagnóstico gerado com sucesso!",
            "filename": filename,
            "path": pdf_path,
            "download_url": f"/api/botconversa/download-pdf?file={filename}",
        })
    except Exception as e:
        logger.error("[botconversa_bp.generate_pdf error]: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


@botconversa_bp.route("/download-pdf", methods=["GET"])
def download_pdf():
    """Disponibiliza o download do PDF executivo gerado."""
    filename = request.args.get("file")
    base_pdf_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "PDF")
    
    if not filename:
        # Se não forneceu o nome específico, pega o mais recente no diretório PDF
        files = [f for f in os.listdir(base_pdf_dir) if f.startswith("diagnostico_campanhas_botconversa_") and f.endswith(".pdf")]
        if not files:
            return jsonify({"status": "error", "message": "Nenhum relatório PDF encontrado."}), 404
        files.sort(reverse=True)
        filename = files[0]

    target_path = os.path.join(base_pdf_dir, filename)
    if not os.path.exists(target_path):
        return jsonify({"status": "error", "message": "Arquivo PDF não encontrado."}), 404

    return send_file(target_path, mimetype="application/pdf", as_attachment=True, download_name=filename)
