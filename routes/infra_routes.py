"""
M-One Infrastructure & Vercel Monitoring Blueprint (routes/infra_routes.py)
Acompanhamento de desempenho, limites da Vercel (Hobby) e alertas de migração (Passo 5).
Restrito a Jam Penitenti e Fauzer.
"""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from routes.helpers import audit, current_user, login_required, roles_required, user_has_permission
from services.supabase_monitor_service import (
    check_and_trigger_supabase_alerts_if_needed,
    fetch_supabase_health_metrics,
    send_test_supabase_alert_whatsapp,
)
from services.telemetry_service import (
    fetch_recent_incidents,
    send_test_render_alert_whatsapp,
    telemetry,
)
from services.vercel_service import (
    calculate_performance_report,
    check_and_trigger_alerts_if_needed,
    get_infra_config,
    save_infra_config,
    send_test_alert_whatsapp,
)

infra_bp = Blueprint("infra", __name__)


@infra_bp.route("/infra/performance", methods=["GET"])
@login_required
@roles_required("admin", "support")
def infra_performance():
    """Painel principal de monitoramento de desempenho, telemetria do Render e Supabase."""
    # Avalia se há necessidade de disparar alerta silencioso em segundo plano
    try:
        check_and_trigger_alerts_if_needed()
    except Exception as e:
        print("[Vercel Alert Background Check Error]:", e)

    try:
        check_and_trigger_supabase_alerts_if_needed()
    except Exception as e:
        print("[Supabase Alert Background Check Error]:", e)

    report = calculate_performance_report()
    supabase_metrics = fetch_supabase_health_metrics()
    telemetry_snap = telemetry.get_snapshot()
    incidents = fetch_recent_incidents(15)
    me = current_user()
    can_telemetry_beta = user_has_permission(me, "infra_telemetry_live")

    return render_template(
        "infra_performance.html",
        report=report,
        supabase=supabase_metrics,
        telemetry=telemetry_snap,
        incidents=incidents,
        can_telemetry_beta=can_telemetry_beta,
    )


@infra_bp.route("/infra/config", methods=["POST"])
@login_required
@roles_required("admin", "support")
def infra_config_save():
    """Atualiza as configurações de monitoramento e números de alerta de Jam e Fauzer."""
    try:
        save_infra_config(request.form)
        audit("infra.config_updated", "Configurações de limites e telefones atualizadas")
        flash("Configurações de infraestrutura atualizadas com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao salvar configurações: {e}", "danger")
    return redirect(url_for("infra.infra_performance"))


@infra_bp.route("/infra/test-alert", methods=["POST"])
@login_required
@roles_required("admin", "support")
def infra_test_alert():
    """Dispara um teste imediato de alerta de infraestrutura via WhatsApp."""
    target = request.form.get("target", "both").strip().lower()
    cfg = get_infra_config()

    sent_count = 0
    errors = []

    if target in ["jam", "both"] and cfg.get("phone_jam"):
        res_jam = send_test_alert_whatsapp(cfg["phone_jam"], "Jam Penitenti")
        if res_jam.get("success"):
            sent_count += 1
        else:
            errors.append(f"Jam: {res_jam.get('error')}")

    if target in ["fauzer", "both"] and cfg.get("phone_fauzer"):
        res_fauzer = send_test_alert_whatsapp(cfg["phone_fauzer"], "Fauzer")
        if res_fauzer.get("success"):
            sent_count += 1
        else:
            errors.append(f"Fauzer: {res_fauzer.get('error')}")

    if sent_count > 0:
        flash(f"✅ Alerta de teste enviado com sucesso para {sent_count} destinatário(s) via WhatsApp!", "success")
        audit("infra.test_alert_sent", f"sent_count={sent_count}")
    else:
        err_msg = "; ".join(errors) if errors else "Nenhum telefone de destino configurado."
        flash(f"⚠️ Falha ao disparar alerta de teste: {err_msg}", "warning")

    return redirect(url_for("infra.infra_performance"))


@infra_bp.route("/api/infra/metrics", methods=["GET"])
@login_required
@roles_required("admin", "support")
def api_infra_metrics():
    """Retorna dados de telemetria em tempo real para atualização assíncrona (HTMX/Alpine)."""
    report = calculate_performance_report()
    return jsonify(report)


@infra_bp.route("/infra/test-supabase-alert", methods=["POST"])
@login_required
@roles_required("admin", "support")
def infra_test_supabase_alert():
    """Dispara um teste imediato de alerta de monitoramento do Supabase via WhatsApp."""
    target = request.form.get("target", "both").strip().lower()
    cfg = get_infra_config()

    sent_count = 0
    errors = []

    if target in ["jam", "both"] and cfg.get("phone_jam"):
        res_jam = send_test_supabase_alert_whatsapp(cfg["phone_jam"], "Jam Penitenti")
        if res_jam.get("success"):
            sent_count += 1
        else:
            errors.append(f"Jam: {res_jam.get('error')}")

    if target in ["fauzer", "both"] and cfg.get("phone_fauzer"):
        res_fauzer = send_test_supabase_alert_whatsapp(cfg["phone_fauzer"], "Fauzer")
        if res_fauzer.get("success"):
            sent_count += 1
        else:
            errors.append(f"Fauzer: {res_fauzer.get('error')}")

    if sent_count > 0:
        flash(f"✅ Alerta de teste do Supabase enviado para {sent_count} destinatário(s) via WhatsApp!", "success")
        audit("infra.test_supabase_alert_sent", f"sent_count={sent_count}")
    else:
        err_msg = "; ".join(errors) if errors else "Nenhum telefone configurado."
        flash(f"⚠️ Falha ao disparar alerta de teste do Supabase: {err_msg}", "warning")

    return redirect(url_for("infra.infra_performance"))


@infra_bp.route("/api/infra/supabase-metrics", methods=["GET"])
@login_required
@roles_required("admin", "support")
def api_supabase_metrics():
    """Retorna métricas em tempo real de saúde do Supabase."""
    metrics = fetch_supabase_health_metrics(force_refresh=True)
    return jsonify(metrics)


@infra_bp.route("/api/infra/telemetry", methods=["GET"])
@login_required
@roles_required("admin", "support")
def api_infra_telemetry():
    """Retorna dados de telemetria em tempo real do container Render para Chart.js e painel."""
    snap = telemetry.get_snapshot()
    incidents = fetch_recent_incidents(15)
    return jsonify({"telemetry": snap, "incidents": incidents})


@infra_bp.route("/infra/test-render-alert", methods=["POST"])
@login_required
@roles_required("admin", "support")
def infra_test_render_alert():
    """Dispara um teste imediato de alerta de estresse do Render via WhatsApp exclusivo para Fauzer."""
    cfg = get_infra_config()
    phone_fauzer = cfg.get("phone_fauzer") or "+55 27 99999-9999"
    try:
        send_test_render_alert_whatsapp(phone_fauzer, "Fauzer")
        flash("✅ Alerta de teste do Render enviado com sucesso para Fauzer via WhatsApp!", "success")
        audit("infra.test_render_alert_sent", f"phone={phone_fauzer}")
    except Exception as e:
        flash(f"⚠️ Falha ao disparar alerta de teste do Render: {e}", "warning")
    return redirect(url_for("infra.infra_performance"))

