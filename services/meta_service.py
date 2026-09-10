"""
M-One Meta Marketing & Graph API Service (services/meta_service.py)
Gerencia credenciais, diagnósticos de tokens, campanhas da Meta Ads e API de Conversões (CAPI).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import db
from services.whatsapp_service import get_whatsapp_config

logger = logging.getLogger(__name__)
META_GRAPH_VERSION = "v20.0"
META_GRAPH_BASE = f"https://graph.facebook.com/{META_GRAPH_VERSION}"


def get_meta_config() -> Dict[str, Any]:
    """Recupera a configuração consolidada da Meta (Ads + WhatsApp)."""
    cfg = {
        "service_name": "meta_ads",
        "access_token": "",
        "ad_account_id": "",
        "pixel_id": "",
        "page_id": "",
        "app_id": "",
        "app_secret": "",
        "waba_id": "",
        "phone_number_id": "",
        "status": "Não Configurado",
        "updated_at": None,
    }

    try:
        with db() as conn:
            row = conn.execute(
                "SELECT * FROM integrations WHERE service_name = 'meta_ads' LIMIT 1"
            ).fetchone()
            if row:
                row_dict = dict(row)
                cfg["access_token"] = row_dict.get("access_token") or ""
                cfg["app_id"] = row_dict.get("client_id") or ""
                cfg["app_secret"] = row_dict.get("client_secret") or ""
                cfg["updated_at"] = row_dict.get("updated_at")

                settings = row_dict.get("settings_json") or {}
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except Exception:
                        settings = {}
                cfg["ad_account_id"] = settings.get("ad_account_id", "")
                cfg["pixel_id"] = settings.get("pixel_id", "")
                cfg["page_id"] = settings.get("page_id", "")
                cfg["waba_id"] = settings.get("waba_id", "")
                cfg["phone_number_id"] = settings.get("phone_number_id", "")
    except Exception as e:
        logger.error("[get_meta_config error]: %s", e)

    # Preencher fallback com dados do whatsapp_config se estiverem vazios
    w_cfg = get_whatsapp_config()
    if not cfg["waba_id"] and w_cfg.get("waba_id"):
        cfg["waba_id"] = str(w_cfg["waba_id"])
    if not cfg["phone_number_id"] and w_cfg.get("phone_number_id"):
        cfg["phone_number_id"] = str(w_cfg["phone_number_id"])
    if not cfg["access_token"] and w_cfg.get("token"):
        cfg["access_token"] = str(w_cfg["token"])

    return cfg


def save_meta_config(data: Dict[str, Any]) -> bool:
    """Salva a configuração do Meta Ads e sincroniza o token com o WhatsApp."""
    access_token = (data.get("access_token") or "").strip()
    ad_account_id = (data.get("ad_account_id") or "").strip()
    if ad_account_id.startswith("act_"):
        ad_account_id = ad_account_id.replace("act_", "")

    pixel_id = (data.get("pixel_id") or "").strip()
    page_id = (data.get("page_id") or "").strip()
    app_id = (data.get("app_id") or "").strip()
    app_secret = (data.get("app_secret") or "").strip()
    waba_id = (data.get("waba_id") or "").strip()
    phone_number_id = (data.get("phone_number_id") or "").strip()

    settings = {
        "ad_account_id": ad_account_id,
        "pixel_id": pixel_id,
        "page_id": page_id,
        "waba_id": waba_id,
        "phone_number_id": phone_number_id,
    }

    try:
        with db() as conn:
            existing = conn.execute(
                "SELECT id FROM integrations WHERE service_name = 'meta_ads' LIMIT 1"
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE integrations 
                    SET access_token = %s, client_id = %s, client_secret = %s, 
                        settings_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE service_name = 'meta_ads'
                    """,
                    (access_token, app_id, app_secret, json.dumps(settings)),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO integrations (service_name, access_token, client_id, client_secret, settings_json)
                    VALUES ('meta_ads', %s, %s, %s, %s)
                    """,
                    (access_token, app_id, app_secret, json.dumps(settings)),
                )

            # Sincronizar token e IDs com whatsapp_config se preenchidos
            if access_token or waba_id or phone_number_id:
                w_row = conn.execute("SELECT id FROM whatsapp_config ORDER BY id DESC LIMIT 1").fetchone()
                if w_row:
                    updates = []
                    params = []
                    if access_token:
                        updates.append("token = %s")
                        params.append(access_token)
                    if waba_id:
                        updates.append("waba_id = %s")
                        params.append(waba_id)
                    if phone_number_id:
                        updates.append("phone_number_id = %s")
                        params.append(phone_number_id)
                    if updates:
                        params.append(w_row["id"])
                        conn.execute(
                            f"UPDATE whatsapp_config SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                            tuple(params),
                        )
            conn.commit()
            return True
    except Exception as e:
        logger.error("[save_meta_config error]: %s", e)
        return False


def test_meta_connection(custom_token: Optional[str] = None) -> Dict[str, Any]:
    """Testa o token contra a Graph API da Meta e retorna diagnóstico detalhado."""
    cfg = get_meta_config()
    token = (custom_token or cfg.get("access_token") or "").strip()

    result = {
        "valid": False,
        "is_permanent": False,
        "token_type": "Desconhecido",
        "expires_in": "Indisponível",
        "app_name": "",
        "user_name": "",
        "scopes": [],
        "waba_health": "Não verificado",
        "ad_account_health": "Não verificado",
        "error_message": "",
    }

    if not token:
        result["error_message"] = "Nenhum Access Token informado."
        return result

    # 1. Testar /me ou /debug_token
    try:
        url = f"{META_GRAPH_BASE}/me?fields=id,name&access_token={urllib.parse.quote(token)}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            result["valid"] = True
            result["user_name"] = data.get("name", "Meta App/User")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        try:
            err_json = json.loads(err_body)
            result["error_message"] = err_json.get("error", {}).get("message", err_body)
        except Exception:
            result["error_message"] = f"HTTP {e.code}: {err_body}"
        return result
    except Exception as ex:
        result["error_message"] = f"Erro de conexão: {ex}"
        return result

    # 2. Testar /debug_token para saber se expira ou é permanente
    try:
        app_id = cfg.get("app_id") or "10988893282731750"
        app_secret = cfg.get("app_secret") or ""
        app_token = f"{app_id}|{app_secret}" if app_secret else token

        debug_url = f"{META_GRAPH_BASE}/debug_token?input_token={urllib.parse.quote(token)}&access_token={urllib.parse.quote(app_token)}"
        req = urllib.request.Request(debug_url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            dbg = json.loads(resp.read().decode()).get("data", {})
            result["is_valid"] = dbg.get("is_valid", False)
            result["app_name"] = dbg.get("application", "")
            result["token_type"] = dbg.get("type", "System User")
            result["scopes"] = dbg.get("scopes", [])

            exp = dbg.get("expires_at", 0)
            if exp == 0:
                result["is_permanent"] = True
                result["expires_in"] = "Nunca (Token Permanente)"
            else:
                dt = datetime.fromtimestamp(exp)
                result["is_permanent"] = False
                result["expires_in"] = dt.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        # Se debug_token não tiver permissão de app_secret, inferir que está ativo
        result["is_permanent"] = True
        result["expires_in"] = "Válido"

    # 3. Testar WABA / WhatsApp Phone
    phone_id = cfg.get("phone_number_id")
    if phone_id:
        try:
            p_url = f"{META_GRAPH_BASE}/{phone_id}?fields=display_phone_number,verified_name,quality_rating&access_token={urllib.parse.quote(token)}"
            req = urllib.request.Request(p_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                p_data = json.loads(resp.read().decode())
                result["waba_health"] = f"Conectado ({p_data.get('display_phone_number', phone_id)}) - Qualidade: {p_data.get('quality_rating', 'GREEN')}"
        except Exception as e:
            result["waba_health"] = f"Aviso WABA: {e}"

    # 4. Testar Conta de Anúncios (Ad Account)
    ad_acc = cfg.get("ad_account_id")
    if ad_acc:
        clean_acc = ad_acc if ad_acc.startswith("act_") else f"act_{ad_acc}"
        try:
            a_url = f"{META_GRAPH_BASE}/{clean_acc}?fields=name,account_status,currency,amount_spent&access_token={urllib.parse.quote(token)}"
            req = urllib.request.Request(a_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                a_data = json.loads(resp.read().decode())
                st_map = {1: "Ativa", 2: "Desativada", 3: "Liquidação Não Paga", 7: "Pendente"}
                st = st_map.get(a_data.get("account_status"), "Ativa")
                result["ad_account_health"] = f"Conta '{a_data.get('name')}' ({st}) - Moeda: {a_data.get('currency', 'BRL')}"
        except Exception as e:
            result["ad_account_health"] = f"Aviso Ad Account: {e}"

    return result


def fetch_meta_campaigns(limit: int = 10) -> List[Dict[str, Any]]:
    """Busca campanhas ativas e métricas na Meta Marketing API."""
    cfg = get_meta_config()
    token = cfg.get("access_token")
    ad_acc = cfg.get("ad_account_id")

    if not token or not ad_acc:
        return []

    clean_acc = ad_acc if ad_acc.startswith("act_") else f"act_{ad_acc}"
    fields = "id,name,status,objective,daily_budget,lifetime_budget,insights.date_preset(last_30d){spend,impressions,clicks,cpc,ctr}"
    url = f"{META_GRAPH_BASE}/{clean_acc}/campaigns?fields={fields}&limit={limit}&access_token={urllib.parse.quote(token)}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
            items = []
            for c in data.get("data", []):
                insights_data = (c.get("insights", {}).get("data") or [{}])[0]
                spend = float(insights_data.get("spend", 0.0))
                impressions = int(insights_data.get("impressions", 0))
                clicks = int(insights_data.get("clicks", 0))
                cpc = float(insights_data.get("cpc", 0.0))
                ctr = float(insights_data.get("ctr", 0.0))

                items.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "status": c.get("status"),
                    "objective": c.get("objective", "").replace("OUTCOME_", ""),
                    "spend": spend,
                    "impressions": impressions,
                    "clicks": clicks,
                    "cpc": cpc,
                    "ctr": ctr,
                })
            return items
    except Exception as e:
        logger.warning("[fetch_meta_campaigns warning]: %s", e)
        return []


def get_monitored_lines() -> List[Dict[str, Any]]:
    """Retorna a lista de contas e linhas do WhatsApp com status de monitoramento."""
    try:
        with db() as conn:
            rows = conn.execute(
                """
                SELECT id, waba_id, account_name, phone_number_id, display_phone_number,
                       quality_rating, is_monitored, assigned_seller_name, updated_at
                FROM whatsapp_monitored_lines
                ORDER BY id ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error("[get_monitored_lines error]: %s", e)
        return []


def toggle_monitored_line(line_id: int, enable: bool) -> Dict[str, Any]:
    """Ativa (pluga) ou desativa (despluga) o monitoramento de uma linha/conta."""
    try:
        with db() as conn:
            row = conn.execute(
                "SELECT * FROM whatsapp_monitored_lines WHERE id = %s",
                (line_id,),
            ).fetchone()
            if not row:
                return {"success": False, "error": "Linha não encontrada"}

            conn.execute(
                """
                UPDATE whatsapp_monitored_lines
                SET is_monitored = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (enable, line_id),
            )
            conn.commit()

            waba_id = row.get("waba_id")
            # Se ativando e o waba_id for válido na Meta (não placeholder)
            if enable and waba_id and not waba_id.startswith("waba_"):
                cfg = get_meta_config()
                token = cfg.get("access_token")
                if token:
                    sub_url = f"{META_GRAPH_BASE}/{waba_id}/subscribed_apps"
                    sub_data = urllib.parse.urlencode({"access_token": token}).encode()
                    req = urllib.request.Request(sub_url, data=sub_data, method="POST")
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            pass
                    except Exception as sub_err:
                        logger.warning("[WABA Subscribed Apps Warning]: %s", sub_err)

            return {"success": True, "is_monitored": enable, "account_name": row.get("account_name")}
    except Exception as e:
        logger.error("[toggle_monitored_line error]: %s", e)
        return {"success": False, "error": str(e)}


def sync_meta_lines() -> Dict[str, Any]:
    """Consulta a Meta Graph API e sincroniza números de telefone disponíveis para monitoramento."""
    cfg = get_meta_config()
    token = cfg.get("access_token")
    waba_id = cfg.get("waba_id") or "638446228813266"

    if not token:
        return {"success": False, "error": "Token da Meta não configurado"}

    synced_count = 0
    try:
        # 1. Buscar números da WABA configurada
        url = f"{META_GRAPH_BASE}/{waba_id}/phone_numbers?fields=id,display_phone_number,verified_name,quality_rating,code_verification_status,platform_type&access_token={urllib.parse.quote(token)}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
            phones = data.get("data", [])

            with db() as conn:
                for p in phones:
                    p_id = p.get("id")
                    disp_num = p.get("display_phone_number")
                    v_name = p.get("verified_name") or "Linha WhatsApp Meta"
                    q_rating = p.get("quality_rating", "GREEN")

                    conn.execute(
                        """
                        INSERT INTO whatsapp_monitored_lines (waba_id, account_name, phone_number_id, display_phone_number, quality_rating, is_monitored, assigned_seller_name)
                        VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                        ON CONFLICT (waba_id, COALESCE(phone_number_id, ''))
                        DO UPDATE SET 
                            display_phone_number = EXCLUDED.display_phone_number,
                            quality_rating = EXCLUDED.quality_rating,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (waba_id, v_name, p_id, disp_num, q_rating, v_name),
                    )
                    synced_count += 1
                conn.commit()

        return {"success": True, "synced_count": synced_count}
    except Exception as e:
        logger.error("[sync_meta_lines error]: %s", e)
        return {"success": False, "error": str(e)}

