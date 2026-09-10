"""
M-One Chat Analyzer & Sales Intelligence Service (services/chat_analyzer_service.py)
Agrupa histórico de conversas do WhatsApp por período e executa auditoria comercial com Google Gemini.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from database import db
from gemini_service import get_gemini_api_key

logger = logging.getLogger(__name__)


def get_chats_by_period(
    period: str = "7d",
    status_filter: Optional[str] = None,
    seller_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Recupera e agrupa todas as conversas do WhatsApp no período selecionado."""
    now = datetime.now()
    if period == "1d":
        since_date = now - timedelta(days=1)
        period_label = "Últimas 24 Horas (01 Dia)"
    elif period == "30d":
        since_date = now - timedelta(days=30)
        period_label = "Últimos 30 Dias (01 Mês)"
    else:  # default 7d
        period = "7d"
        since_date = now - timedelta(days=7)
        period_label = "Últimos 7 Dias (01 Semana)"

    chats_dict = {}

    try:
        with db() as conn:
            # Buscar mensagens do período com dados do lead
            query = """
                SELECT m.id, m.phone, m.direction, m.message_type, m.body, m.sent_at,
                       l.id as lead_id, l.name as lead_name, l.status as lead_status,
                       l.product_interest, l.ad_id, l.ad_headline, l.traffic_source,
                       u.name as seller_name, u.id as seller_user_id
                FROM whatsapp_messages m
                LEFT JOIN crm_leads l ON (l.phone = m.phone OR l.phone = REPLACE(m.phone, '55', ''))
                LEFT JOIN users u ON u.id = l.assigned_to
                WHERE m.sent_at >= %s
                ORDER BY m.sent_at ASC
            """
            rows = conn.execute(query, (since_date,)).fetchall()

            for r in rows:
                phone = r["phone"]
                if phone not in chats_dict:
                    chats_dict[phone] = {
                        "phone": phone,
                        "lead_id": r["lead_id"],
                        "lead_name": r["lead_name"] or "Cliente WhatsApp",
                        "lead_status": r["lead_status"] or "novo",
                        "seller_name": r["seller_name"] or "Não atribuído",
                        "seller_user_id": r["seller_user_id"],
                        "product_interest": r["product_interest"] or "Geral",
                        "ad_id": r["ad_id"],
                        "ad_headline": r["ad_headline"],
                        "traffic_source": r["traffic_source"] or "WhatsApp Orgânico",
                        "messages": [],
                        "total_messages": 0,
                        "inbound_count": 0,
                        "outbound_count": 0,
                        "first_sent_at": None,
                        "last_sent_at": None,
                        "last_direction": None,
                        "last_message_body": "",
                        "silence_hours": 0.0,
                        "situation": "active",  # active, waiting_seller, lead_stopped
                    }

                item = chats_dict[phone]
                sent_at_dt = r["sent_at"]
                body_text = r["body"] or ""
                direction = r["direction"]

                item["messages"].append({
                    "id": r["id"],
                    "direction": direction,
                    "body": body_text,
                    "sent_at": sent_at_dt.strftime("%d/%m %H:%M") if sent_at_dt else "",
                    "sent_at_raw": sent_at_dt,
                })
                item["total_messages"] += 1
                if direction == "inbound":
                    item["inbound_count"] += 1
                else:
                    item["outbound_count"] += 1

                if not item["first_sent_at"]:
                    item["first_sent_at"] = sent_at_dt
                item["last_sent_at"] = sent_at_dt
                item["last_direction"] = direction
                item["last_message_body"] = body_text

    except Exception as e:
        logger.error("[get_chats_by_period error]: %s", e)

    chats_list = list(chats_dict.values())

    # Calcular indicadores de silêncio e situação da negociação
    active_count = 0
    waiting_seller_count = 0
    lead_stopped_count = 0

    for c in chats_list:
        if c["last_sent_at"]:
            try:
                # normalizar timezone se necessário
                now_aware = datetime.now(c["last_sent_at"].tzinfo) if c["last_sent_at"].tzinfo else datetime.now()
                delta = now_aware - c["last_sent_at"]
                hours = round(delta.total_seconds() / 3600, 1)
                c["silence_hours"] = hours
            except Exception:
                c["silence_hours"] = 0.0

        # Classificação de situação
        if c["lead_status"] in ["fechado", "perdido"]:
            c["situation"] = c["lead_status"]
        elif c["last_direction"] == "outbound" and c["silence_hours"] >= 24:
            c["situation"] = "lead_stopped"  # Lead parou de responder
            lead_stopped_count += 1
        elif c["last_direction"] == "inbound" and c["silence_hours"] >= 2:
            c["situation"] = "waiting_seller"  # Vendedor ainda não respondeu
            waiting_seller_count += 1
        else:
            c["situation"] = "active"
            active_count += 1

    # Ordenar pelos chats mais recentes
    chats_list.sort(key=lambda x: x["last_sent_at"] or datetime.min, reverse=True)

    # Filtrar por status ou vendedor se solicitado
    if status_filter:
        chats_list = [c for c in chats_list if c["lead_status"] == status_filter or c["situation"] == status_filter]
    if seller_id and seller_id.isdigit():
        chats_list = [c for c in chats_list if str(c["seller_user_id"]) == str(seller_id)]

    return {
        "period": period,
        "period_label": period_label,
        "total_chats": len(chats_list),
        "active_count": active_count,
        "waiting_seller_count": waiting_seller_count,
        "lead_stopped_count": lead_stopped_count,
        "chats": chats_list,
    }


def import_external_chat_log(text_content: str, default_phone: str, lead_name: str) -> Dict[str, Any]:
    """Importa transcrição de conversa externa do WhatsApp para análise no M-One."""
    clean_phone = "".join(ch for ch in default_phone if ch.isdigit())
    if not clean_phone:
        return {"success": False, "message": "Telefone do lead é obrigatório."}

    lines = text_content.strip().splitlines()
    if not lines:
        return {"success": False, "message": "Nenhum conteúdo informado."}

    imported_count = 0
    now = datetime.now()

    try:
        with db() as conn:
            # Garantir lead no CRM
            lead = conn.execute("SELECT id FROM crm_leads WHERE phone = %s", (clean_phone,)).fetchone()
            if not lead:
                conn.execute(
                    """
                    INSERT INTO crm_leads (name, phone, channel, status, notes)
                    VALUES (%s, %s, 'WhatsApp Importado', 'em_negociacao', 'Conversa importada externamente')
                    """,
                    (lead_name or "Cliente Importado", clean_phone),
                )

            # Regex para mensagens típicas de WhatsApp:
            # [10/09/2026, 14:02:15] Nome: Mensagem ou 10/09/2026 14:02 - Nome: Mensagem
            pattern = re.compile(r"^(?:\[?(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*[-:]?\s*)([^:]+):\s*(.*)$")

            for line in lines:
                m = pattern.match(line.strip())
                if m:
                    date_str, time_str, sender, msg_body = m.groups()
                    sender_lower = sender.strip().lower()
                    direction = "outbound" if any(w in sender_lower for w in ["vendedor", "maj", "eu", "atendente", "loja"]) else "inbound"
                    wam_id = f"import_{clean_phone}_{imported_count}_{int(now.timestamp())}"

                    conn.execute(
                        """
                        INSERT INTO whatsapp_messages (wam_id, phone, direction, message_type, body, status, sent_at)
                        VALUES (%s, %s, %s, 'text', %s, 'received', CURRENT_TIMESTAMP)
                        """,
                        (wam_id, clean_phone, direction, msg_body.strip()),
                    )
                    imported_count += 1
                elif line.strip() and imported_count > 0:
                    # Linha de continuação
                    pass

            # Se não bateu na regex (ex: texto livre colado sem formatação rígida)
            if imported_count == 0:
                wam_id = f"import_blob_{clean_phone}_{int(now.timestamp())}"
                conn.execute(
                    """
                    INSERT INTO whatsapp_messages (wam_id, phone, direction, message_type, body, status, sent_at)
                    VALUES (%s, %s, 'inbound', 'text', %s, 'received', CURRENT_TIMESTAMP)
                    """,
                    (wam_id, clean_phone, text_content[:1500].strip()),
                )
                imported_count = 1

            conn.commit()
            return {"success": True, "imported_count": imported_count, "phone": clean_phone}
    except Exception as e:
        logger.error("[import_external_chat_log error]: %s", e)
        return {"success": False, "message": str(e)}


def analyze_chats_with_gemini(chats_data: Dict[str, Any], user_prompt: str) -> str:
    """Envia o corpus estruturado das conversas para auditoria comercial estratégica no Gemini."""
    api_key = get_gemini_api_key()
    if not api_key:
        return "⚠️ Chave de API do Gemini não configurada no ambiente (.env). Configure a GEMINI_API_KEY para habilitar a análise de IA."

    chats = chats_data.get("chats", [])
    period_label = chats_data.get("period_label", "Período")

    if not chats:
        return f"Não foram encontradas conversas de WhatsApp registradas no período selecionado ({period_label}). Incentive a equipe a atender os clientes via chat do M-One ou importe conversas externas."

    # Construir corpus analítico compacto
    corpus_lines = [
        f"=== RELATÓRIO OPERACIONAL DE CONVERSAS DE VENDAS ({period_label.upper()}) ===",
        f"Total de conversas ativas: {len(chats)}",
        f"Chats com lead que parou de responder: {chats_data.get('lead_stopped_count', 0)}",
        f"Chats aguardando resposta do vendedor: {chats_data.get('waiting_seller_count', 0)}",
        "\n--- DETALHE DAS CONVERSAS DOS LEADS ---",
    ]

    for idx, c in enumerate(chats[:25], 1):  # Limitar aos 25 chats mais relevantes por chamada
        corpus_lines.append(f"\n[LEAD #{idx}] Nome: {c['lead_name']} | Tel: {c['phone']} | Vendedor: {c['seller_name']}")
        corpus_lines.append(f"Status do Funil: {c['lead_status']} | Situação: {c['situation']} | Silêncio: {c['silence_hours']}h")
        if c.get("ad_headline") or c.get("ad_id"):
            corpus_lines.append(f"Origem Meta Ad: {c.get('ad_headline') or c.get('ad_id')} (Canal: {c.get('traffic_source')})")

        corpus_lines.append("Diálogo:")
        for msg in c["messages"][-8:]:  # últimas 8 mensagens do diálogo
            sender_tag = "CLIENTE" if msg["direction"] == "inbound" else "VENDEDOR"
            corpus_lines.append(f"  [{msg['sent_at']}] {sender_tag}: {msg['body']}")

    corpus_text = "\n".join(corpus_lines)

    system_instruction = """
Você é o Copilot de Inteligência Comercial e Auditoria de Vendas da MAJ Mobilidade Elétrica (M-One).
Sua missão é analisar as conversas reais dos vendedores com os clientes e gerar diagnósticos estratégicos de altíssimo valor.

Diretrizes de Análise:
1. Identifique exatamente ONDE e POR QUE cada lead parou de responder (ex: preço, valor de frete, falta de opções de parcelamento, demora no atendimento, ou resposta fria do vendedor).
2. Avalie a conduta do vendedor: se fez perguntas abertas, se tentou contornar objeções ou se apenas mandou a tabela de preços e deixou o cliente esfriar.
3. Se o usuário pedir scripts ou mensagens de reativação, gere textos humanizados, empáticos e prontos para o vendedor copiar e enviar no WhatsApp.
4. Responda em português brasileiro com formatação rica em Markdown (tópicos, negrito, tabelas e destaques). Seja direto, estratégico e executivo.
"""

    full_prompt = f"{system_instruction}\n\n{corpus_text}\n\nPERGUNTA DO GESTOR:\n{user_prompt}"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode())
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return "A IA processou o pedido, mas não retornou conteúdo textual."
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        logger.error("[Gemini Chat Analyzer HTTPError]: %s %s", e.code, err_msg)
        return f"Erro na consulta à API do Gemini (HTTP {e.code}): {err_msg[:200]}"
    except Exception as ex:
        logger.error("[Gemini Chat Analyzer Error]: %s", ex)
        return f"Erro de comunicação com o Copilot: {str(ex)}"
