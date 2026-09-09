from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from database import db
import bling_service
from routes.helpers import login_required, roles_required

bling_bp = Blueprint("bling", __name__)


@bling_bp.route("/integrations/bling", methods=["GET"])
@login_required
@roles_required("admin", "support")
def integrations_bling():
    rec = bling_service.get_bling_integration_record()
    has_credentials = bool(rec and rec.get("client_id") and rec.get("client_secret"))
    is_connected = bool(rec and rec.get("access_token"))
    callback_url = url_for("bling_callback", _external=True)
    return render_template(
        "integrations_bling.html",
        rec=rec or {},
        has_credentials=has_credentials,
        is_connected=is_connected,
        callback_url=callback_url
    )


@bling_bp.route("/integrations/bling/save", methods=["POST"])
@login_required
@roles_required("admin", "support")
def save_bling_config():
    client_id = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()
    if not client_id or not client_secret:
        flash("Informe o Client ID e o Client Secret do Bling.", "danger")
        return redirect(url_for("integrations_bling"))
    bling_service.save_bling_credentials(client_id, client_secret)
    flash("Credenciais do Bling salvas com sucesso! Agora clique em 'Conectar com Bling'.", "success")
    return redirect(url_for("integrations_bling"))


@bling_bp.route("/bling/authorize")
@login_required
@roles_required("admin", "support")
def bling_authorize():
    try:
        callback_url = url_for("bling_callback", _external=True)
        auth_url = bling_service.get_bling_auth_url(callback_url)
        return redirect(auth_url)
    except Exception as e:
        flash(f"Erro ao iniciar autorização com Bling: {str(e)}", "danger")
        return redirect(url_for("integrations_bling"))


@bling_bp.route("/bling/callback")
@login_required
@roles_required("admin", "support")
def bling_callback():
    code = request.args.get("code")
    err = request.args.get("error")
    if err:
        flash(f"Autorização cancelada ou recusada no Bling: {err}", "danger")
        return redirect(url_for("integrations_bling"))
    if not code:
        flash("Nenhum código de autorização retornado pelo Bling.", "danger")
        return redirect(url_for("integrations_bling"))
    try:
        callback_url = url_for("bling_callback", _external=True)
        bling_service.exchange_code_for_token(code, callback_url)
        flash("🎉 Conexão com o Bling ERP autorizada e ativada com sucesso!", "success")
    except Exception as e:
        flash(f"Falha ao trocar código pelo token do Bling: {str(e)}", "danger")
    return redirect(url_for("integrations_bling"))


@bling_bp.route("/bling/disconnect")
@login_required
@roles_required("admin", "support")
def bling_disconnect():
    with db() as conn:
        conn.execute("UPDATE integrations SET access_token = NULL, refresh_token = NULL WHERE service_name = 'bling'")
        conn.commit()
    flash("Conexão com o Bling foi desconectada.", "warning")
    return redirect(url_for("integrations_bling"))


@bling_bp.route("/api/bling/order/<path:order_num>")
@login_required
def api_bling_order(order_num):
    try:
        data = bling_service.search_bling_order(order_num)
        return jsonify(data)
    except Exception as e:
        return jsonify({"found": False, "message": str(e)}), 400


@bling_bp.route("/api/bling/invoice/<path:inv_num>")
@login_required
def api_bling_invoice(inv_num):
    try:
        data = bling_service.search_bling_invoice(inv_num)
        return jsonify(data)
    except Exception as e:
        return jsonify({"found": False, "message": str(e)}), 400


@bling_bp.route("/products/sync-bling-stock", methods=["POST"])
@bling_bp.route("/api/bling/sync-stock", methods=["POST"])
@login_required
def sync_bling_stock_route():
    try:
        res = bling_service.sync_bling_products_stock()
        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify(res)
        if res.get("success"):
            flash(f"✅ {res.get('message')}", "success")
        else:
            flash(f"⚠️ {res.get('message')}", "warning")
    except Exception as e:
        if request.headers.get("Accept") == "application/json" or request.is_json:
            return jsonify({"success": False, "message": str(e)}), 400
        flash(f"Erro ao sincronizar estoque com o Bling: {str(e)}", "danger")
    return redirect(url_for("products"))
