#!/usr/bin/env python3
"""
BotConversa CLI & Tool Integrator for M-One (scripts/botconversa_tool.py)
Ferramenta de linha de comando e biblioteca operacional para consulta e ações no BotConversa da MAJ Mobilidade.
Compatível com Antigravity, automações e auditorias.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# Garantir importações do root do projeto M-One
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.botconversa_service import get_botconversa_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("botconversa_tool")

BASE_WEBHOOK_URL = "https://backend.botconversa.com.br/api/v1/webhook"


def _get_api_headers() -> Dict[str, str]:
    cfg = get_botconversa_config()
    api_key = cfg.get("api_key")
    if not api_key:
        logger.error("API Key do BotConversa não encontrada na configuração do M-One.")
        sys.exit(1)
    return {
        "API-KEY": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "M-One-Agent/1.0",
    }


def _request(endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{BASE_WEBHOOK_URL}/{endpoint.lstrip('/')}"
    headers = _get_api_headers()
    data = json.dumps(payload).encode("utf-8") if payload and method in ("POST", "PUT") else None

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        logger.error("Erro HTTP %s: %s", e.code, err_msg)
        return {"error": f"HTTP {e.code}", "details": err_msg}
    except Exception as ex:
        logger.error("Falha na requisição: %s", ex)
        return {"error": str(ex)}


def list_tags() -> List[Dict[str, Any]]:
    """Retorna lista de todas as etiquetas cadastradas no BotConversa."""
    res = _request("tags/")
    return res if isinstance(res, list) else []


def list_flows() -> List[Dict[str, Any]]:
    """Retorna lista de fluxos de automação cadastrados."""
    res = _request("flows/")
    return res if isinstance(res, list) else []


def get_contact_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    """Busca contato por número de telefone (com DDD)."""
    clean_phone = re.sub(r"\D", "", phone)
    if not clean_phone.startswith("55") and len(clean_phone) in (10, 11):
        clean_phone = f"55{clean_phone}"

    res = _request(f"subscriber/get_by_phone/{clean_phone}/")
    if isinstance(res, dict) and "id" in res:
        return res
    return None


def add_tag_to_contact(subscriber_id: int, tag_id_or_name: str | int) -> Dict[str, Any]:
    """Aplica uma etiqueta ao contato pelo ID ou Nome da tag."""
    tag_id = tag_id_or_name
    if isinstance(tag_id_or_name, str) and not tag_id_or_name.isdigit():
        tags = list_tags()
        matched = next((t for t in tags if t.get("name", "").lower() == tag_id_or_name.lower()), None)
        if not matched:
            return {"success": False, "error": f"Tag '{tag_id_or_name}' não encontrada no BotConversa."}
        tag_id = matched.get("id")

    res = _request(f"subscriber/{subscriber_id}/tags/{tag_id}/", method="POST")
    return {"success": True, "tag_id": tag_id, "response": res}


def remove_tag_from_contact(subscriber_id: int, tag_id_or_name: str | int) -> Dict[str, Any]:
    """Remove uma etiqueta do contato."""
    tag_id = tag_id_or_name
    if isinstance(tag_id_or_name, str) and not tag_id_or_name.isdigit():
        tags = list_tags()
        matched = next((t for t in tags if t.get("name", "").lower() == tag_id_or_name.lower()), None)
        if not matched:
            return {"success": False, "error": f"Tag '{tag_id_or_name}' não encontrada."}
        tag_id = matched.get("id")

    res = _request(f"subscriber/{subscriber_id}/tags/{tag_id}/", method="DELETE")
    return {"success": True, "tag_id": tag_id, "response": res}


def create_subscriber(phone: str, first_name: str = "Lead Instagram", last_name: str = "MAJ") -> Dict[str, Any]:
    """Cria um novo assinante com opt-in ativo no BotConversa."""
    clean_phone = re.sub(r"\D", "", phone)
    if not clean_phone.startswith("55") and len(clean_phone) in (10, 11):
        clean_phone = f"55{clean_phone}"

    payload = {
        "phone": clean_phone,
        "first_name": first_name,
        "last_name": last_name,
        "has_opt_in_whatsapp": True,
    }
    return _request("subscriber/", method="POST", payload=payload)


def onboard_instagram_lead(
    phone: str,
    first_name: str = "Lead Instagram",
    segment: str = "varejo",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Rotina completa de transbordo do lead do Instagram para o WhatsApp:
    1. Localiza ou cadastra o contato no BotConversa.
    2. Aplica as tags reais da MAJ (VAREJO-INTERESSE ou atacado_revenda).
    3. Aplica a tag do modelo de interesse (se fornecido).
    4. Inscreve no fluxo rotativo correspondente (Varejo ou Atacado).
    """
    clean_segment = segment.strip().lower()
    contact = get_contact_by_phone(phone)
    created = False

    if not contact:
        create_res = create_subscriber(phone, first_name=first_name)
        if isinstance(create_res, dict) and "id" in create_res:
            contact = create_res
            created = True
        else:
            # Tenta buscar novamente caso já existisse
            contact = get_contact_by_phone(phone)

    if not contact or "id" not in contact:
        return {"success": False, "error": f"Não foi possível localizar ou cadastrar o contato {phone}."}

    subscriber_id = contact["id"]
    actions_taken = []

    # 1. Tag de Segmento (usando tags ativas da MAJ)
    segment_tag_id = 17539826 if clean_segment == "varejo" else 15396318
    segment_tag_name = "VAREJO-INTERESSE" if clean_segment == "varejo" else "atacado_revenda"
    tag_res = _request(f"subscriber/{subscriber_id}/tags/{segment_tag_id}/", method="POST")
    actions_taken.append(f"Tag aplicada: {segment_tag_name} ({segment_tag_id})")

    # 2. Tag de Modelo (se fornecido)
    if model:
        model_clean = model.strip().upper()
        if "V20" in model_clean:
            m_tag = 17705472  # OUTLET MAJ - V20 ULTRA
            m_name = "OUTLET MAJ - V20 ULTRA"
        elif "M50" in model_clean:
            m_tag = 17705471  # OUTLET MAJ - M50 PRO
            m_name = "OUTLET MAJ - M50 PRO"
        elif "MAX" in model_clean:
            m_tag = 17705459  # OUTLET MAJ - MAX 12
            m_name = "OUTLET MAJ - MAX 12"
        else:
            m_tag = None

        if m_tag:
            _request(f"subscriber/{subscriber_id}/tags/{m_tag}/", method="POST")
            actions_taken.append(f"Tag de modelo aplicada: {m_name} ({m_tag})")

    # 3. Disparo do Fluxo Rotativo
    flow_id = 9169016 if clean_segment == "varejo" else 9169014
    flow_name = "Atendimento Rotativo Varejo" if clean_segment == "varejo" else "Atendimento Rotativo Atacado"
    flow_res = send_flow_to_contact(subscriber_id, flow_id)
    actions_taken.append(f"Inscrito no fluxo: {flow_name} ({flow_id})")

    return {
        "success": True,
        "subscriber_id": subscriber_id,
        "phone": contact.get("phone", phone),
        "name": contact.get("first_name", first_name),
        "created_new": created,
        "segment": clean_segment,
        "actions": actions_taken,
        "flow_response": flow_res,
    }


def send_flow_to_contact(subscriber_id: int, flow_id_or_name: str | int) -> Dict[str, Any]:
    """Inscreve e dispara um fluxo de conversa para o contato."""
    flow_id = flow_id_or_name
    if isinstance(flow_id_or_name, str) and not flow_id_or_name.isdigit():
        flows = list_flows()
        matched = next((f for f in flows if flow_id_or_name.lower() in f.get("name", "").lower()), None)
        if not matched:
            return {"success": False, "error": f"Fluxo '{flow_id_or_name}' não encontrado."}
        flow_id = matched.get("id")

    res = _request(f"subscriber/{subscriber_id}/send_flow/", method="POST", payload={"flow": int(flow_id)})
    return {"success": True, "flow_id": flow_id, "response": res}


def send_message_to_contact(subscriber_id: int, message: str) -> Dict[str, Any]:
    """Envia uma mensagem de texto direta para o contato no WhatsApp."""
    payload = {"type": "text", "value": message}
    res = _request(f"subscriber/{subscriber_id}/send_message/", method="POST", payload=payload)
    return {"success": True, "response": res}


def main():
    parser = argparse.ArgumentParser(description="BotConversa Integrator CLI for MAJ Mobilidade")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-tags
    subparsers.add_parser("list-tags", help="Lista todas as etiquetas cadastradas")

    # list-flows
    subparsers.add_parser("list-flows", help="Lista todos os fluxos de conversa cadastrados")

    # get-contact
    p_contact = subparsers.add_parser("get-contact", help="Busca contato por telefone")
    p_contact.add_argument("--phone", required=True, help="Número de telefone com DDD (ex: 27999998888)")

    # add-tag
    p_add_tag = subparsers.add_parser("add-tag", help="Aplica etiqueta a um contato")
    p_add_tag.add_argument("--subscriber-id", required=True, type=int, help="ID numérico do contato")
    p_add_tag.add_argument("--tag", required=True, help="Nome ou ID da etiqueta")

    # remove-tag
    p_rem_tag = subparsers.add_parser("remove-tag", help="Remove etiqueta de um contato")
    p_rem_tag.add_argument("--subscriber-id", required=True, type=int, help="ID numérico do contato")
    p_rem_tag.add_argument("--tag", required=True, help="Nome ou ID da etiqueta")

    # send-flow
    p_flow = subparsers.add_parser("send-flow", help="Dispara fluxo para o contato")
    p_flow.add_argument("--subscriber-id", required=True, type=int, help="ID numérico do contato")
    p_flow.add_argument("--flow", required=True, help="Nome ou ID do fluxo")

    # send-message
    p_msg = subparsers.add_parser("send-message", help="Envia mensagem direta de texto")
    p_msg.add_argument("--subscriber-id", required=True, type=int, help="ID numérico do contato")
    p_msg.add_argument("--text", required=True, help="Texto da mensagem")

    # onboard-lead (Instagram -> WhatsApp)
    p_onboard = subparsers.add_parser("onboard-lead", help="Transborda lead do Instagram para o WhatsApp e fila de vendedores")
    p_onboard.add_argument("--phone", required=True, help="Número de WhatsApp com DDD")
    p_onboard.add_argument("--name", default="Lead Instagram", help="Nome do lead")
    p_onboard.add_argument("--segment", choices=["varejo", "atacado"], default="varejo", help="Segmento comercial")
    p_onboard.add_argument("--model", help="Modelo de interesse (ex: V20, M50, MAX12)")

    args = parser.parse_args()

    if args.command == "list-tags":
        tags = list_tags()
        print(json.dumps([{"id": t.get("id"), "name": t.get("name")} for t in tags], indent=2, ensure_ascii=False))

    elif args.command == "list-flows":
        flows = list_flows()
        print(json.dumps([{"id": f.get("id"), "name": f.get("name")} for f in flows], indent=2, ensure_ascii=False))

    elif args.command == "get-contact":
        contact = get_contact_by_phone(args.phone)
        if contact:
            print(json.dumps(contact, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"found": False, "message": f"Nenhum contato encontrado para o número {args.phone}."}, indent=2))

    elif args.command == "add-tag":
        res = add_tag_to_contact(args.subscriber_id, args.tag)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "remove-tag":
        res = remove_tag_from_contact(args.subscriber_id, args.tag)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "send-flow":
        res = send_flow_to_contact(args.subscriber_id, args.flow)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "send-message":
        res = send_message_to_contact(args.subscriber_id, args.text)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.command == "onboard-lead":
        res = onboard_instagram_lead(
            phone=args.phone,
            first_name=args.name,
            segment=args.segment,
            model=args.model,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
