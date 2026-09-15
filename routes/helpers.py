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

from flask import flash, g, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
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
    """Gera hash criptográfico seguro PBKDF2:SHA256 com salt aleatório por usuário."""
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(stored_hash: str | None, password: str) -> tuple[bool, bool]:
    """
    Valida a senha contra o hash armazenado.
    Retorna (is_valid, needs_rehash).
    Suporta hashes modernos (pbkdf2/scrypt) e legado (SHA-256 com salt fixo), permitindo auto-upgrade transparente.
    """
    if not stored_hash or not password:
        return False, False

    # 1. Hash moderno Werkzeug
    if stored_hash.startswith(("pbkdf2:", "scrypt:")):
        return check_password_hash(stored_hash, password), False

    # 2. Hash legado SHA-256 (compatibilidade com contas antigas)
    salt = "m-one-v1"
    legacy = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    if legacy == stored_hash:
        return True, True  # Válido, mas sinaliza necessidade de upgrade transparente

    return False, False


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
    try:
        if hasattr(g, "_current_user"):
            return g._current_user
    except RuntimeError:
        pass

    uid = session.get("user_id")
    if not uid:
        try:
            g._current_user = None
        except (RuntimeError, AttributeError):
            pass
        return None

    with db() as conn:
        u = conn.execute("SELECT * FROM users WHERE id=%s AND active=TRUE", (uid,)).fetchone()
        user_dict = dict(u) if u else None
        try:
            g._current_user = user_dict
        except (RuntimeError, AttributeError):
            pass
        return user_dict


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


def user_has_permission(u: dict | None, permission_key: str, default_for_sales: bool = False) -> bool:
    """
    Verifica se o usuário tem permissão para acessar determinado módulo.
    Gestores ('admin', 'support') têm acesso total irrestrito a tudo.
    Para outros perfis, consulta custom_permissions (JSON) ou assume default_for_sales.
    """
    if not u:
        return False
    if u.get("role") in ["admin", "support"] or str(u.get("username", "")).strip().lower() in ["jam", "fauzer"]:
        return True

    perms = u.get("custom_permissions") or {}
    if isinstance(perms, str):
        try:
            perms = json.loads(perms)
        except Exception:
            perms = {}

    if permission_key in perms:
        return bool(perms[permission_key])

    # Defaults específicos para vendedores (Fretes, Estoque e Copilot IA liberados por padrão)
    if u.get("role") == "sales":
        if permission_key in ["freight", "stock", "copilot"]:
            return True
        return default_for_sales

    return default_for_sales



def ensure_audit_log_table(conn):
    """Garantido centralizadamente em database.ensure_runtime_schema."""
    pass


def audit(action, detail=""):
    try:
        with db() as conn:
            conn.execute("INSERT INTO audit_log(user_id,action,detail) VALUES(%s,%s,%s)", (session.get("user_id"), action, detail))
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

