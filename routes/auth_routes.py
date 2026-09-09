"""
M-One Authentication & Session Blueprint (routes/auth_routes.py)
Rotas de Login, Logout, Alteração de Senha, Termos de Uso e Política de Privacidade.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database import db
from routes.helpers import audit, hash_password, login_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/politica-de-privacidade")
@auth_bp.route("/termos-de-uso")
def privacy_policy():
    return render_template("privacy_policy.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        try:
            with db() as conn:
                user = conn.execute(
                    "SELECT * FROM users WHERE lower(username)=lower(?) AND (active=1 OR active IS TRUE)",
                    (username,)
                ).fetchone()
            if user and user["password_hash"] == hash_password(password):
                session.permanent = True
                session["user_id"] = user["id"]
                audit("auth.login", f"username={username}")
                flash(f"Bem-vindo, {user['name']}.", "success")
                return redirect(url_for("dashboard"))
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
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), session["user_id"]))
        conn.commit()
    audit("auth.password_changed", "")
    flash("Senha alterada.", "success")
    return redirect(request.referrer or url_for("dashboard"))
