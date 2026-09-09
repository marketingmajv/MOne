"""
M-One WhatsApp Automation Adapters (services/automation/adapters.py)
Formatadores do Meta WhatsApp Cloud API (Mídia, Botões, Listas), Adaptadores de IA Modulares e Webhook HTTP.
Sem mocks disfarçados ou inferência por substrings em URLs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable


class AINotConfiguredError(Exception):
    """Exceção lançada quando o provedor de IA não possui chave de API configurada."""


# ==========================================
# META WHATSAPP CLOUD API TRANSPORT FORMATTERS
# ==========================================

def send_meta_text_message(phone: str, text: str, is_simulation: bool = False, transport_caller: Callable | None = None) -> dict:
    """
    Formata mensagem de texto Meta Cloud API e delega o envio ao transportador oficial do app.
    Em modo de simulação explícito (is_simulation=True), retorna a simulação sem efeito externo.
    """
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {"body": text}
    }

    if is_simulation:
        return {"status": "simulated", "payload": payload}

    try:
        from app import send_whatsapp_message
        res = send_whatsapp_message(clean_phone, payload, http_caller=transport_caller)
        if isinstance(res, dict) and res.get("success") is True:
            status_str = "mock" if res.get("mock") else "sent"
            return {"status": status_str, "payload": payload, "response": res}
        else:
            err = res.get("error") if isinstance(res, dict) else "Falha no envio Meta Texto"
            return {"status": "failed", "payload": payload, "error": str(err)}
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        return {"status": "failed", "payload": payload, "error": str(e)}


def send_meta_media_message(phone: str, media_type: str, media_url: str, caption: str | None = None, is_simulation: bool = False, transport_caller: Callable | None = None) -> dict:
    """
    Formata mensagens de mídia Meta Cloud API (image, document, audio, video) nativamente.
    """
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
    m_type = str(media_type or "image").strip().lower()
    if m_type not in ["image", "document", "audio", "video"]:
        m_type = "image"

    if not media_url or not media_url.startswith(("http://", "https://")):
        return {"status": "validation_failed", "payload": None, "error": f"URL de mídia inválida: '{media_url}'. Deve iniciar com http:// ou https://"}

    media_obj = {"link": media_url}
    if caption and m_type in ["image", "document", "video"]:
        media_obj["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": m_type,
        m_type: media_obj
    }

    if is_simulation:
        return {"status": "simulated", "payload": payload}

    try:
        from app import send_whatsapp_message
        res = send_whatsapp_message(clean_phone, payload, http_caller=transport_caller)
        if isinstance(res, dict) and res.get("success") is True:
            status_str = "mock" if res.get("mock") else "sent"
            return {"status": status_str, "payload": payload, "response": res}
        else:
            err = res.get("error") if isinstance(res, dict) else f"Falha no envio Meta Mídia {m_type}"
            return {"status": "failed", "payload": payload, "error": str(err)}
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        return {"status": "failed", "payload": payload, "error": str(e)}


def send_meta_button_message(phone: str, body_text: str, buttons: list, header_text: str | None = None, is_simulation: bool = False, transport_caller: Callable | None = None) -> dict:
    """
    Formata botões interativos (Interactive Reply Buttons) via Meta Cloud API.
    Se exceder 3 botões ou algum título tiver mais de 20 caracteres, delega para Lista Interativa nativa sem truncar.
    """
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())
    buttons = buttons or []

    should_delegate_list = len(buttons) > 3
    if not should_delegate_list:
        for b in buttons:
            btitle = b.get("text") if isinstance(b, dict) else str(b)
            if len(str(btitle).strip()) > 20:
                should_delegate_list = True
                break

    if should_delegate_list:
        sections = [{
            "title": "Opções",
            "rows": [{"id": (b.get("id") if isinstance(b, dict) else f"opt_{i+1}"), "title": str(b.get("text") if isinstance(b, dict) else b).strip()[:24]} for i, b in enumerate(buttons)]
        }]
        return send_meta_list_message(clean_phone, body_text, "Opções", sections, header_text=header_text, is_simulation=is_simulation, transport_caller=transport_caller)

    btn_objs = []
    for idx, b in enumerate(buttons):
        bid = b.get("id") if isinstance(b, dict) else f"btn_{idx+1}"
        btitle = b.get("text") if isinstance(b, dict) else str(b)
        str_title = str(btitle).strip()
        btn_objs.append({
            "type": "reply",
            "reply": {
                "id": str(bid),
                "title": str_title
            }
        })

    interactive_obj = {
        "type": "button",
        "body": {"text": body_text or ""},
        "action": {"buttons": btn_objs}
    }

    if header_text:
        interactive_obj["header"] = {"type": "text", "text": header_text}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "interactive",
        "interactive": interactive_obj
    }

    if is_simulation:
        return {"status": "simulated", "payload": payload}

    try:
        from app import send_whatsapp_message
        res = send_whatsapp_message(clean_phone, payload, http_caller=transport_caller)
        if isinstance(res, dict) and res.get("success") is True:
            status_str = "mock" if res.get("mock") else "sent"
            return {"status": status_str, "payload": payload, "response": res}
        else:
            err = res.get("error") if isinstance(res, dict) else "Falha no envio Meta Botões"
            return {"status": "failed", "payload": payload, "error": str(err)}
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        return {"status": "failed", "payload": payload, "error": str(e)}


def send_meta_list_message(phone: str, body_text: str, button_title: str, sections: list, header_text: str | None = None, is_simulation: bool = False, transport_caller: Callable | None = None) -> dict:
    """Formata menu de lista interativa (Interactive List Message) via Meta Cloud API com validação estrita."""
    clean_phone = "".join(ch for ch in str(phone) if ch.isdigit())

    btn_lbl = str(button_title or "Opções").strip()
    if len(btn_lbl) > 20:
        return {"status": "validation_failed", "payload": None, "error": f"Título do botão do menu lista '{btn_lbl}' excede 20 caracteres ({len(btn_lbl)} caracteres)."}

    total_rows = 0
    formatted_sections = []
    for s in (sections or []):
        sec_title = s.get("title", "Seção")
        rows = s.get("rows", [])
        sec_rows = []
        for r in rows:
            total_rows += 1
            r_id = r.get("id", f"row_{total_rows}")
            r_title = str(r.get("title") or r.get("text") or "").strip()
            if len(r_title) > 24:
                return {"status": "validation_failed", "payload": None, "error": f"Título do item da lista '{r_title}' excede 24 caracteres ({len(r_title)} caracteres)."}
            r_desc = r.get("description", "")
            row_dict = {"id": str(r_id), "title": r_title}
            if r_desc:
                row_dict["description"] = str(r_desc)
            sec_rows.append(row_dict)
        formatted_sections.append({"title": str(sec_title), "rows": sec_rows})

    if total_rows > 10:
        return {"status": "validation_failed", "payload": None, "error": f"Menu de lista excede o limite máximo de 10 opções ({total_rows} opções fornecidas)."}

    interactive_obj = {
        "type": "list",
        "body": {"text": body_text or ""},
        "action": {
            "button": btn_lbl,
            "sections": formatted_sections
        }
    }

    if header_text:
        interactive_obj["header"] = {"type": "text", "text": header_text}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "interactive",
        "interactive": interactive_obj
    }

    if is_simulation:
        return {"status": "simulated", "payload": payload}

    try:
        from app import send_whatsapp_message
        res = send_whatsapp_message(clean_phone, payload, http_caller=transport_caller)
        if isinstance(res, dict) and res.get("success") is True:
            status_str = "mock" if res.get("mock") else "sent"
            return {"status": status_str, "payload": payload, "response": res}
        else:
            err = res.get("error") if isinstance(res, dict) else "Falha no envio Meta Lista"
            return {"status": "failed", "payload": payload, "error": str(err)}
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
        return {"status": "failed", "payload": payload, "error": str(e)}


# ==========================================
# MODULAR AI PROVIDER ADAPTERS
# ==========================================

class OpenAIAdapter:
    def __init__(self, api_key: str | None = None, api_caller: Callable | None = None):
        self.api_key = (api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        self.api_caller = api_caller

    def is_configured(self) -> bool:
        return bool(self.api_key or self.api_caller)

    def generate_reply(self, prompt: str, context: dict | None = None) -> str:
        if not self.is_configured():
            raise AINotConfiguredError("OpenAI API key ausente")
        if self.api_caller:
            return str(self.api_caller(prompt, context))
        raise AINotConfiguredError("Chave OpenAI configurada mas integração de rede desativada")


class AnthropicAdapter:
    def __init__(self, api_key: str | None = None, api_caller: Callable | None = None):
        self.api_key = (api_key or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
        self.api_caller = api_caller

    def is_configured(self) -> bool:
        return bool(self.api_key or self.api_caller)

    def generate_reply(self, prompt: str, context: dict | None = None) -> str:
        if not self.is_configured():
            raise AINotConfiguredError("Anthropic API key ausente")
        if self.api_caller:
            return str(self.api_caller(prompt, context))
        raise AINotConfiguredError("Chave Anthropic configurada mas integração de rede desativada")


class GeminiAdapter:
    def __init__(self, api_key: str | None = None, api_caller: Callable | None = None):
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.api_caller = api_caller

    def is_configured(self) -> bool:
        return bool(self.api_key or self.api_caller)

    def generate_reply(self, prompt: str, context: dict | None = None) -> str:
        if not self.is_configured():
            raise AINotConfiguredError("Gemini API key ausente")
        if self.api_caller:
            return str(self.api_caller(prompt, context))

        try:
            from gemini_service import ask_gemini_copilot
            db_conn = context.get("db") if isinstance(context, dict) else None
            res = ask_gemini_copilot(prompt, history=[], db_conn=db_conn, user_role="automation", user_name="Bot")
            if isinstance(res, dict) and res.get("success") and res.get("message"):
                return str(res.get("message"))
            err_msg = res.get("message") if isinstance(res, dict) else "Falha na resposta do Gemini"
            raise ValueError(str(err_msg))
        except ImportError:
            raise AINotConfiguredError("Módulo gemini_service indisponível")


class AIProviderAdapterManager:
    """Gerenciador modular de provedores de IA."""

    def __init__(self, openai_caller: Callable | None = None, anthropic_caller: Callable | None = None, gemini_caller: Callable | None = None):
        self.openai = OpenAIAdapter(api_caller=openai_caller)
        self.anthropic = AnthropicAdapter(api_caller=anthropic_caller)
        self.gemini = GeminiAdapter(api_caller=gemini_caller)

    def get_active_adapter(self) -> Any | None:
        if self.openai.is_configured():
            return self.openai
        if self.anthropic.is_configured():
            return self.anthropic
        if self.gemini.is_configured():
            return self.gemini
        return None

    def generate_ai_reply(self, prompt: str, context: dict | None = None) -> tuple[bool, str]:
        """
        Retorna (success: bool, reply_or_error_message: str).
        Nunca gera resposta falsa/fake quando nenhum provedor estiver configurado.
        """
        adapter = self.get_active_adapter()
        if not adapter:
            return False, "⚠️ Provedor de IA não configurado (chave API ausente). Transicionando para atendimento humano."
        try:
            res = adapter.generate_reply(prompt, context)
            return True, str(res)
        except AINotConfiguredError:
            return False, "⚠️ Provedor de IA não configurado (chave API ausente). Transicionando para atendimento humano."
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
            return False, f"⚠️ Erro no provedor de IA: {e!s}"


# ==========================================
# WEBHOOK ADAPTER
# ==========================================

def execute_webhook_adapter(url: str, method: str, payload_str: str, phone: str, is_simulation: bool = False, http_caller: Callable | None = None) -> tuple[int, str]:
    """
    Executa requisição Webhook real.
    Valida URL obrigatoriamente (deve iniciar com http:// ou https://).
    Não infere mock por substrings 'mock' ou 'example.com'.
    """
    if not url or not isinstance(url, str):
        return 400, "URL do Webhook não informada"

    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        return 400, "URL inválida. Webhooks devem iniciar com http:// ou https://"

    if is_simulation:
        return 200, json.dumps({"status": "simulated", "url": clean_url, "method": method, "phone": phone})

    if http_caller:
        res = http_caller(clean_url, method, payload_str, phone)
        if isinstance(res, tuple) and len(res) == 2:
            return int(res[0]), str(res[1])
        return 200, str(res)

    try:
        data_bytes = payload_str.encode("utf-8") if payload_str else None
        req = urllib.request.Request(
            clean_url, 
            data=data_bytes, 
            headers={"Content-Type": "application/json", "User-Agent": "M-One-Automation-Bot/1.0"}, 
            method=method.upper()
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_code = response.getcode()
            res_body = response.read().decode("utf-8", errors="ignore")
            return int(res_code), str(res_body)
    except urllib.error.HTTPError as e:
        return int(e.code), e.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, RuntimeError) as ex:
        return 500, f"Falha na requisição HTTP Webhook: {ex!s}"
