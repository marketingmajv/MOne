"""
M-One Maintenance & Feature Flags Service (services/maintenance_service.py)
Gerencia modo manutenção por módulo, bloqueio seletivo de telas e notificações via BotConversa WhatsApp.
Segregação estrita modular (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.botconversa_service import _botconversa_request

logger = logging.getLogger(__name__)

MODULE_ROUTES = {
    "prospeccao": "/prospeccao",
    "freight": "/freight",
    "imports": "/imports",
    "sales": "/sales",
    "fiscal_pricing": "/fiscal/pricing",
}


def get_module_status(slug: str) -> Dict[str, Any]:
    """Retorna o status de manutenção de um módulo específico."""
    try:
        with db() as conn:
            row = conn.execute(
                """
                SELECT slug, name, in_maintenance, expected_time, reason, updated_by, updated_at, roles_allowed
                FROM public.system_modules
                WHERE slug = %s
                LIMIT 1;
                """,
                [slug],
            ).fetchone()
            if row:
                return {
                    "slug": row["slug"],
                    "name": row["name"],
                    "in_maintenance": bool(row["in_maintenance"]),
                    "expected_time": row["expected_time"] or "",
                    "reason": row["reason"] or "",
                    "updated_by": row["updated_by"] or "",
                    "roles_allowed": row["roles_allowed"] or ["admin", "support"],
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
    except Exception as e:
        logger.error("[get_module_status error for %s]: %s", slug, e)

    return {
        "slug": slug,
        "name": slug.capitalize(),
        "in_maintenance": False,
        "expected_time": "",
        "reason": "",
        "updated_by": "",
        "roles_allowed": ["admin", "support"],
        "updated_at": None,
    }


def get_all_modules_status() -> List[Dict[str, Any]]:
    """Retorna a lista completa de módulos e seus respectivos status de manutenção."""
    try:
        with db() as conn:
            rows = conn.execute(
                """
                SELECT slug, name, in_maintenance, expected_time, reason, updated_by, updated_at, roles_allowed
                FROM public.system_modules
                ORDER BY id ASC;
                """
            ).fetchall()
            return [
                {
                    "slug": r["slug"],
                    "name": r["name"],
                    "in_maintenance": bool(r["in_maintenance"]),
                    "expected_time": r["expected_time"] or "",
                    "reason": r["reason"] or "",
                    "updated_by": r["updated_by"] or "",
                    "roles_allowed": r["roles_allowed"] or ["admin", "support"],
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                    "route": MODULE_ROUTES.get(r["slug"], f"/{r['slug']}"),
                }
                for r in rows
            ]
    except Exception as e:
        logger.error("[get_all_modules_status error]: %s", e)
        return []


def get_maintenance_recipients(module_slug: str) -> List[Dict[str, Any]]:
    """Retorna os colaboradores com telefone cadastrado que recebem avisos deste módulo."""
    recipients: List[Dict[str, Any]] = []
    try:
        with db() as conn:
            if module_slug == "prospeccao":
                query = """
                SELECT id, name, phone, role 
                FROM public.users 
                WHERE active = TRUE AND phone IS NOT NULL AND phone != '' AND role IN ('sales', 'admin', 'support')
                ORDER BY role DESC, name ASC;
                """
            else:
                query = """
                SELECT id, name, phone, role 
                FROM public.users 
                WHERE active = TRUE AND phone IS NOT NULL AND phone != ''
                ORDER BY role DESC, name ASC;
                """
            rows = conn.execute(query).fetchall() or []
            for r in rows:
                phone_raw = re.sub(r"\D", "", str(r["phone"] or ""))
                # Formata telefone para exibição: (XX) 9XXXX-XXXX
                if len(phone_raw) >= 10:
                    ddd = phone_raw[-11:-9] if len(phone_raw) >= 11 else phone_raw[:2]
                    num = phone_raw[-9:] if len(phone_raw) >= 11 else phone_raw[2:]
                    masked = f"({ddd}) {num[:5]}-{num[5:]}"
                else:
                    masked = str(r["phone"])

                role_pt = {
                    "admin": "Diretoria",
                    "support": "Suporte Técnico",
                    "sales": "Vendas",
                    "finance": "Financeiro",
                    "workshop": "Oficina",
                }.get(r["role"], str(r["role"]).capitalize())

                recipients.append({
                    "id": r["id"],
                    "name": r["name"],
                    "first_name": (r["name"] or "Colaborador").strip().split()[0],
                    "phone": r["phone"],
                    "phone_formatted": masked,
                    "role": r["role"],
                    "role_pt": role_pt,
                })
    except Exception as e:
        logger.error("[get_maintenance_recipients query error]: %s", e)

    return recipients


def build_default_maintenance_message(
    module_slug: str,
    in_maintenance: bool,
    expected_time: str = "",
    reason: str = "",
    user_name: str = "{nome}",
) -> str:
    """Gera o texto padrão de notificação WhatsApp com formatação e emojis executivos."""
    mod_status = get_module_status(module_slug)
    nome_modulo = mod_status.get("name") or module_slug.capitalize()
    rota = MODULE_ROUTES.get(module_slug, f"/{module_slug}")

    if in_maintenance:
        previsao_str = f"⏳ *Previsão de retorno:* {expected_time.strip()}\n\n" if expected_time.strip() else ""
        motivo_str = f"📌 *Detalhes:* {reason.strip()}\n\n" if reason.strip() else ""
        return (
            f"🛠️ *[M-One] Aviso de Manutenção Técnica*\n\n"
            f"Olá, {user_name}!\n\n"
            f"O módulo de *{nome_modulo}* do M-One está temporariamente em manutenção técnica para melhorias e atualizações.\n\n"
            f"{previsao_str}"
            f"{motivo_str}"
            f"Você receberá uma nova notificação por aqui assim que o sistema estiver 100% liberado para uso. Obrigado pela compreensão!"
        )
    else:
        return (
            f"🚀 *[M-One] Módulo Operacional Liberado!*\n\n"
            f"Olá, {user_name}!\n\n"
            f"As atualizações no módulo de *{nome_modulo}* foram concluídas com sucesso. O sistema já está 100% operacional e liberado para uso.\n\n"
            f"🔗 Acesse em: https://m-one.majmobilidade.com.br{rota}\n\n"
            f"Bom trabalho e ótimas vendas!"
        )


def toggle_module_maintenance(
    slug: str,
    in_maintenance: bool,
    expected_time: str = "",
    reason: str = "",
    updated_by: str = "Admin",
    notify_whatsapp: bool = False,
    custom_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Altera o status de manutenção do módulo e dispara notificações via WhatsApp se solicitado."""
    try:
        with db() as conn:
            conn.execute(
                """
                UPDATE public.system_modules
                SET in_maintenance = %s,
                    expected_time = %s,
                    reason = %s,
                    updated_by = %s,
                    updated_at = NOW()
                WHERE slug = %s;
                """,
                [in_maintenance, expected_time.strip(), reason.strip(), updated_by, slug],
            )
            conn.commit()

        notification_result = None
        if notify_whatsapp:
            notification_result = notificar_equipe_whatsapp(
                module_slug=slug,
                in_maintenance=in_maintenance,
                expected_time=expected_time.strip(),
                reason=reason.strip(),
                custom_message=custom_message,
            )

        status_atual = get_module_status(slug)
        return {
            "status": "success",
            "message": f"Módulo '{status_atual['name']}' agora está {'EM MANUTENÇÃO' if in_maintenance else 'OPERACIONAL'}.",
            "module": status_atual,
            "notifications": notification_result,
        }
    except Exception as e:
        logger.error("[toggle_module_maintenance error for %s]: %s", slug, e)
        return {"status": "error", "message": f"Falha ao alterar status de manutenção: {e}"}


def send_whatsapp_message_botconversa(phone: str, text: str, first_name: str = "Colaborador") -> Dict[str, Any]:
    """Envia mensagem de texto via BotConversa para um número de telefone brasileiro."""
    if not phone:
        return {"success": False, "error": "Telefone não informado"}

    clean = re.sub(r"\D", "", str(phone))
    if clean.startswith("0"):
        clean = clean[1:]
    if not clean.startswith("55"):
        clean = "55" + clean

    # Formato internacional com prefixo '+'
    e164_plus = f"+{clean}"

    # 1. Localiza ou cadastra o assinante pelo telefone
    sub_res = _botconversa_request(
        "webhook/subscriber/",
        method="POST",
        payload={"phone": e164_plus, "first_name": first_name.strip()},
    )

    if not sub_res.get("success") or not sub_res.get("data", {}).get("id"):
        return {
            "success": False,
            "error": sub_res.get("error") or "Não foi possível cadastrar/localizar o assinante no BotConversa",
        }

    subscriber_id = sub_res["data"]["id"]

    # 2. Envia a mensagem de texto
    send_res = _botconversa_request(
        f"webhook/subscriber/{subscriber_id}/send_message/",
        method="POST",
        payload={"type": "text", "value": text},
    )

    return {
        "success": bool(send_res.get("success")),
        "subscriber_id": subscriber_id,
        "phone": e164_plus,
        "error": send_res.get("error") if not send_res.get("success") else None,
    }


def notificar_equipe_whatsapp(
    module_slug: str,
    in_maintenance: bool,
    expected_time: str = "",
    reason: str = "",
    custom_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispara mensagens para todos os colaboradores com telefone cadastrado vinculados ao módulo."""
    recipients = get_maintenance_recipients(module_slug)
    enviados = []
    falhas = []

    for user in recipients:
        nome_primeiro = user.get("first_name") or "Colaborador"
        tel = user.get("phone")

        # Se o administrador aprovou/personalizou uma mensagem específica
        if custom_message and custom_message.strip():
            msg = custom_message.strip()
            # Substituição do token {nome} se presente
            msg = msg.replace("{nome}", nome_primeiro).replace("{Nome}", nome_primeiro)
        else:
            msg = build_default_maintenance_message(
                module_slug=module_slug,
                in_maintenance=in_maintenance,
                expected_time=expected_time,
                reason=reason,
                user_name=nome_primeiro,
            )

        res = send_whatsapp_message_botconversa(phone=tel, text=msg, first_name=nome_primeiro)
        if res.get("success"):
            enviados.append({"user": user.get("name"), "phone": tel})
        else:
            falhas.append({"user": user.get("name"), "phone": tel, "error": res.get("error")})

    return {
        "total_targets": len(recipients),
        "total_sent": len(enviados),
        "total_failed": len(falhas),
        "enviados": enviados,
        "falhas": falhas,
    }
