"""
M-One Helpers & Utilities (routes/helpers.py)
Funções compartilhadas de autenticação, permissões, auditoria, uploads e formatação.
"""

from __future__ import annotations

import base64
import hashlib
import os
import unicodedata
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import flash, redirect, session, url_for
from werkzeug.utils import secure_filename

from database import db

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("VERCEL"):
    UPLOAD_DIR = Path("/tmp/uploads")
else:
    UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "webp", "xlsx", "xls", "csv"}

ROLE_LABELS = {
    "admin": "Diretoria",
    "finance": "Financeiro",
    "stock": "Estoque",
    "sales": "Vendas",
    "support": "Suporte Técnico",
}


def hash_password(password: str) -> str:
    salt = "m-one-v1"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_base64_upload(base64_str: str, prefix="photo") -> str | None:
    if not base64_str or "," not in base64_str:
        return None
    try:
        header, data = base64_str.split(",", 1)
        raw_bytes = base64.b64decode(data)
        ext = "png" if "png" in header else "jpg"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{stamp}.{ext}"
        (UPLOAD_DIR / filename).write_bytes(raw_bytes)
        return filename
    except Exception:
        return None


def save_upload(file_storage, prefix="file") -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        raise ValueError("Tipo de arquivo não permitido")
    original = secure_filename(file_storage.filename)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}_{stamp}_{original}"
    file_storage.save(UPLOAD_DIR / filename)
    return filename


def current_user() -> dict | None:
    uid = session.get("user_id")
    if not uid:
        return None
    with db() as conn:
        u = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
        return dict(u) if u else None


def login_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return inner


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            u = current_user()
            if not u or u.get("role") not in roles:
                flash("Você não tem permissão para acessar esta área.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return inner
    return decorator


def crm_pilot_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        u = current_user()
        if not u or str(u.get("username", "")).strip().lower() not in ["jam", "fauzer"]:
            flash("O módulo de CRM & WhatsApp está em fase piloto restrito exclusivamente a Jam e Fauzer.", "danger")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return inner


def ensure_audit_log_table(conn):
    try:
        is_pg = hasattr(conn, "conn")
        sql = """
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """ if is_pg else """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """
        conn.execute(sql)
        if hasattr(conn, "commit"):
            conn.commit()
    except Exception as e:
        print("[Audit Log Table Init Error]:", e)


def audit(action, detail=""):
    try:
        with db() as conn:
            ensure_audit_log_table(conn)
            conn.execute("INSERT INTO audit_log(user_id,action,detail) VALUES(?,?,?)", (session.get("user_id"), action, detail))
            conn.commit()
    except Exception as e:
        print("[Audit Log Error]:", e)


def money(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def money_usd(v):
    try:
        return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "$ 0,00"


def aliquota(v):
    try:
        if not v or float(v) == 0:
            return "—"
        return f"R$ {float(v):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def normalize_headers(row: list) -> list[str]:
    headers = []
    for c in row:
        val = str(c or "").strip()
        val = unicodedata.normalize("NFKD", val).encode("ASCII", "ignore").decode("utf-8")
        headers.append(val.lower())
    return headers


def find_header_and_data_rows(all_rows: list):
    if not all_rows:
        return 0, [], []
    candidate_keywords = ["produto", "product", "modelo", "model", "nome", "name", "sku", "codigo", "code", "varejo", "retail", "atacado", "wholesale"]
    header_idx = 0
    for idx, row in enumerate(all_rows[:10]):
        norm = normalize_headers(row)
        if any(kw in norm for kw in candidate_keywords) or any(any(kw in cell for kw in candidate_keywords) for cell in norm):
            header_idx = idx
            break
    headers = normalize_headers(all_rows[header_idx])
    return header_idx, headers, all_rows[header_idx + 1:]

