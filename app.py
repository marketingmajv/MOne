import os
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, request, session, url_for

load_dotenv()
load_dotenv(".env.local")

from database import init_db
from routes import register_blueprints
from routes.helpers import (
    current_user,
    user_has_permission,
    ROLE_LABELS,
    money,
    money_usd,
    aliquota
)

app = Flask(__name__)
app.secret_key = (
    os.environ.get("FLASK_SECRET_KEY")
    or os.environ.get("SECRET_KEY")
    or "maj-m-one-production-fixed-secret-key-2026-v1"
)

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=60)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if os.environ.get("VERCEL") or os.environ.get("FLASK_ENV") == "production":
    app.config["SESSION_COOKIE_SECURE"] = True
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000


def generate_csrf_token() -> str:
    """Gera ou recupera o token CSRF único da sessão do usuário."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


@app.before_request
def validate_csrf():
    """Valida tokens CSRF em todas as requisições de alteração de estado (POST/PUT/DELETE/PATCH)."""
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        # 1. Exceção: Webhooks externos de terceiros (ex: WhatsApp/Z-API) que não usam sessão
        if request.path.startswith("/webhook/"):
            return

        # 2. Exceção de testes automatizados unitários
        if app.config.get("TESTING") and "_csrf_token" not in session:
            return

        expected_token = session.get("_csrf_token")
        sent_token = (
            request.form.get("csrf_token")
            or request.headers.get("X-CSRF-Token")
            or request.headers.get("X-CSRFToken")
        )
        if not sent_token and request.is_json:
            try:
                sent_token = (request.get_json(silent=True) or {}).get("csrf_token")
            except Exception:
                sent_token = None

        # Validação segura em tempo constante (evita timing attacks)
        if not expected_token or not sent_token or not secrets.compare_digest(str(expected_token), str(sent_token)):
            import logging
            logging.getLogger(__name__).warning("Bloqueio CSRF ativado: rota=%s ip=%s", request.path, request.remote_addr)
            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": "Token de segurança CSRF inválido ou expirado."}), 403
            flash("Sua sessão de segurança expirou. Por favor, tente novamente.", "danger")
            return redirect(request.referrer or url_for("dashboard")), 403


@app.after_request
def apply_security_and_cache_headers(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    # Cabeçalhos defensivos de segurança OWASP
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if os.environ.get("VERCEL") or request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.context_processor
def inject_globals():
    u = current_user()
    return {
        "current_user": u,
        "me": u,
        "role_labels": ROLE_LABELS,
        "now": datetime.utcnow(),
        "user_has_permission": user_has_permission,
        "csrf_token": generate_csrf_token,
    }


@app.template_filter("money")
def filter_money(v):
    return money(v)


@app.template_filter("money_usd")
def filter_money_usd(v):
    return money_usd(v)


@app.template_filter("aliquota")
def filter_aliquota(v):
    return aliquota(v)


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"success": False, "message": "Arquivo muito grande. O limite máximo permitido é 64MB."}), 413


@app.errorhandler(500)
def handle_500(e):
    import logging
    logging.getLogger(__name__).error("Erro Interno 500: %s", e, exc_info=True)
    return (
        """<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Erro Interno • M-One</title>
        <style>body{background:#070b12;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
        .card{background:rgba(15,23,42,0.85);border:1px solid rgba(255,255,255,0.1);padding:40px;border-radius:18px;max-width:480px;text-align:center;}
        h2{color:#38bdf8;margin-top:0;}p{color:#94a3b8;line-height:1.5;}a{color:#00e599;text-decoration:none;font-weight:600;display:inline-block;margin-top:16px;}</style></head>
        <body><div class='card'><h2>Erro Interno no Servidor</h2><p>Ocorreu uma falha temporária ao processar sua requisição. O evento foi registrado de forma segura para análise técnica.</p><a href='/'>← Voltar para o Sistema</a></div></body></html>""",
        500,
    )


# Registra todos os Blueprints modulares com aliases de endpoint para compatibilidade total
register_blueprints(app)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5001")), debug=True)
