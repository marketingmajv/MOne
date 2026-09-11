import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import db
from routes.helpers import (
    login_required,
    roles_required,
    hash_password,
    audit
)

user_bp = Blueprint("user", __name__)


@user_bp.route("/users", methods=["GET", "POST"])
@login_required
@roles_required("admin", "support")
def users():
    if request.method == "POST":
        name = request.form["name"].strip()
        username = request.form["username"].strip().lower()
        password = request.form.get("password") or "MOne2026!"
        role = request.form.get("role", "sales")
        with db() as conn:
            try:
                conn.execute(
                    "INSERT INTO users(name,username,password_hash,role) VALUES(%s,%s,%s,%s)",
                    (name, username, hash_password(password), role)
                )
                conn.commit()
                flash("Usuário criado.", "success")
            except Exception:
                flash("Esse nome de usuário já existe.", "danger")
        return redirect(url_for("users"))
    with db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    return render_template("users.html", users=rows)


@user_bp.route("/users/<int:uid>/toggle", methods=["POST"])
@login_required
@roles_required("admin", "support")
def toggle_user(uid):
    with db() as conn:
        u = conn.execute("SELECT active FROM users WHERE id=%s", (uid,)).fetchone()
        if u:
            new_val = False if u["active"] else True
            conn.execute("UPDATE users SET active=%s WHERE id=%s", (new_val, uid))
            conn.commit()
            flash("Status do usuário alterado.", "success")
    return redirect(url_for("users"))


@user_bp.route("/users/<int:uid>/reset-password", methods=["POST"])
@login_required
@roles_required("admin", "support")
def reset_user_password(uid):
    with db() as conn:
        conn.execute("UPDATE users SET password_hash=%s WHERE id=%s", (hash_password("MOne2026!"), uid))
        conn.commit()
        flash("Senha resetada para MOne2026!.", "success")
    return redirect(url_for("users"))


@user_bp.route("/users/<int:uid>/edit", methods=["POST"])
@login_required
@roles_required("admin", "support")
def edit_user(uid):
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip().lower()
    role = request.form.get("role", "sales")
    new_password = request.form.get("password", "").strip()
    with db() as conn:
        if new_password:
            conn.execute(
                "UPDATE users SET name=%s, username=%s, role=%s, password_hash=%s WHERE id=%s",
                (name, username, role, hash_password(new_password), uid)
            )
        else:
            conn.execute(
                "UPDATE users SET name=%s, username=%s, role=%s WHERE id=%s",
                (name, username, role, uid)
            )
        conn.commit()
    audit("user.edited", f"user_id={uid}; username={username}; role={role}")
    flash("Usuário atualizado com sucesso.", "success")
    return redirect(url_for("users"))


@user_bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete_user(uid):
    if uid == session.get("user_id"):
        flash("Você não pode excluir a sua própria conta logada.", "danger")
        return redirect(url_for("users"))
    try:
        with db() as conn:
            conn.execute("UPDATE imports SET created_by=NULL WHERE created_by=%s", (uid,))
            conn.execute("UPDATE sales SET created_by=NULL WHERE created_by=%s", (uid,))
            conn.execute("UPDATE payments SET created_by=NULL WHERE created_by=%s", (uid,))
            conn.execute("UPDATE audit_log SET user_id=NULL WHERE user_id=%s", (uid,))
            conn.execute("DELETE FROM users WHERE id=%s", (uid,))
            conn.commit()
        audit("user.deleted", f"user_id={uid}")
        flash("Usuário excluído com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao excluir usuário: {str(e)}", "danger")
    return redirect(url_for("users"))


@user_bp.route("/users/<int:uid>/permissions", methods=["POST"])
@login_required
@roles_required("admin")
def update_user_permissions(uid):
    perms = {
        "crm": bool(request.form.get("perm_crm")),
        "chat_analyzer": bool(request.form.get("perm_chat_analyzer")),
        "copilot": bool(request.form.get("perm_copilot")),
        "freight": bool(request.form.get("perm_freight")),
        "stock": bool(request.form.get("perm_stock")),
        "products": bool(request.form.get("perm_products")),
        "all_sales": bool(request.form.get("perm_all_sales")),
    }
    with db() as conn:
        conn.execute(
            "UPDATE users SET custom_permissions = %s WHERE id = %s",
            (json.dumps(perms), uid)
        )
        conn.commit()
    audit("user.permissions_updated", f"user_id={uid}; perms={json.dumps(perms)}")
    flash("Permissões do usuário atualizadas com sucesso.", "success")
    return redirect(url_for("users"))
