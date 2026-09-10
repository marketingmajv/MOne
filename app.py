import os
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()
load_dotenv(".env.local")

from database import init_db
from routes import register_blueprints
from routes.helpers import (
    current_user,
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
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024


@app.context_processor
def inject_globals():
    u = current_user()
    return {
        "current_user": u,
        "me": u,
        "role_labels": ROLE_LABELS,
        "now": datetime.utcnow(),
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
    import traceback
    return f"<h3>Erro Interno</h3><pre>{traceback.format_exc()}</pre>", 500


# Registra todos os Blueprints modulares com aliases de endpoint para compatibilidade total
register_blueprints(app)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5001")), debug=True)
