"""
M-One Authentication & Session Blueprint (routes/auth_routes.py)
Rotas de Login, Logout, Alteração de Senha, Termos de Uso e Política de Privacidade.
"""

from __future__ import annotations

import time
from collections import defaultdict
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database import db
from routes.helpers import audit, hash_password, login_required, verify_password

auth_bp = Blueprint("auth", __name__)

# Controle em memória de tentativas falhas de login: IP -> [timestamps]
_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 900  # 15 minutos


def check_rate_limit(ip: str) -> tuple[bool, int]:
    now = time.time()
    attempts = [t for t in _login_attempts[ip] if now - t < LOCKOUT_WINDOW_SECONDS]
    _login_attempts[ip] = attempts
    if len(attempts) >= MAX_LOGIN_ATTEMPTS:
        remaining = int(LOCKOUT_WINDOW_SECONDS - (now - attempts[0]))
        return True, max(1, remaining)
    return False, 0


def record_failed_attempt(ip: str):
    _login_attempts[ip].append(time.time())


def clear_failed_attempts(ip: str):
    _login_attempts.pop(ip, None)


@auth_bp.route("/politica-de-privacidade")
@auth_bp.route("/termos-de-uso")
def privacy_policy():
    return render_template("privacy_policy.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET" and session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        client_ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "127.0.0.1").split(",")[0].strip()
        is_blocked, wait_secs = check_rate_limit(client_ip)
        if is_blocked:
            mins = wait_secs // 60 + 1
            flash(f"Muitas tentativas incorretas. Por segurança, aguarde {mins} minuto(s) antes de tentar novamente.", "danger")
            return render_template("login.html"), 429

        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") in ["1", "on", "true", True]
        try:
            with db() as conn:
                user = conn.execute(
                    "SELECT * FROM users WHERE LOWER(username) = LOWER(%s) AND active = TRUE",
                    (username,)
                ).fetchone()

            if user:
                is_valid, needs_rehash = verify_password(user.get("password_hash"), password)
                if is_valid:
                    clear_failed_attempts(client_ip)
                    if needs_rehash:
                        with db() as conn:
                            conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(password), user["id"]))
                            conn.commit()
                    session.permanent = remember
                    session["user_id"] = user["id"]
                    audit("auth.login", f"username={username}")
                    flash(f"Bem-vindo, {user['name']}.", "success")
                    return redirect(url_for("dashboard"))

            record_failed_attempt(client_ip)
            flash("Usuário ou senha inválidos.", "danger")
        except Exception as e:
            flash(f"Erro de conexão com o banco de dados: {str(e)}", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    audit("auth.logout", "")
    session.clear()
    return redirect(url_for("login"))


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    new_password = request.form.get("new_password", "")
    if len(new_password) < 8:
        flash("Use uma senha com pelo menos 8 caracteres.", "danger")
        return redirect(request.referrer or url_for("dashboard"))
    with db() as conn:
        conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_password), session["user_id"]))
        conn.commit()
    audit("auth.password_changed", "")
    flash("Senha alterada.", "success")
    return redirect(request.referrer or url_for("dashboard"))
