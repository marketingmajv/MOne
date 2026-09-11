"""
M-One Audio Transcription Service (services/audio_transcription_service.py)
Transcreve mensagens de voz do WhatsApp em tempo real via Groq Whisper Cloud (ultra-rápido).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from typing import Optional, Union

from database import db

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_WHISPER_MODEL = "whisper-large-v3-turbo"


def get_groq_api_key() -> str:
    """Recupera a chave de API da Groq do ambiente ou do banco de dados."""
    env_key = os.environ.get("GROQ_API_KEY")
    if env_key:
        return env_key.strip()
    try:
        with db() as conn:
            row = conn.execute(
                "SELECT access_token FROM integrations WHERE service_name = 'groq' LIMIT 1"
            ).fetchone()
            if row and row.get("access_token"):
                return str(row["access_token"]).strip()
    except Exception as e:
        logger.debug("Falha ao buscar chave Groq no banco: %s", e)
    return ""


def _encode_multipart_form(fields: dict, file_bytes: bytes, filename: str, content_type: str = "audio/ogg") -> tuple[bytes, str]:
    """Codifica formulário multipart/form-data usando apenas a biblioteca padrão."""
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    lines = []

    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        lines.append(f"{value}\r\n".encode("utf-8"))

    lines.append(f"--{boundary}\r\n".encode("utf-8"))
    lines.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    lines.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    lines.append(file_bytes)
    lines.append(b"\r\n")

    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(lines)
    header_content_type = f"multipart/form-data; boundary={boundary}"
    return body, header_content_type


def transcribe_audio(
    audio_source: Union[bytes, str],
    filename: str = "audio.ogg",
    mimetype: str = "audio/ogg"
) -> Optional[str]:
    """
    Transcreve um áudio (bytes, base64 ou URL HTTP) usando a API do Whisper na Groq.
    Retorna a string transcrita em PT-BR ou None se falhar.
    """
    api_key = get_groq_api_key()
    if not api_key:
        logger.warning("[Audio Transcription] GROQ_API_KEY não configurada. Áudio não transcrito.")
        return None

    raw_bytes: bytes = b""
    try:
        if isinstance(audio_source, bytes):
            raw_bytes = audio_source
        elif isinstance(audio_source, str):
            if audio_source.startswith("data:") and ";base64," in audio_source:
                _, b64data = audio_source.split(";base64,", 1)
                raw_bytes = base64.b64decode(b64data)
            elif audio_source.startswith("http://") or audio_source.startswith("https://"):
                req = urllib.request.Request(audio_source, headers={"User-Agent": "M-One/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    raw_bytes = resp.read()
            else:
                # Tratar como base64 puro
                raw_bytes = base64.b64decode(audio_source)
    except Exception as read_err:
        logger.error("[Audio Transcription] Falha ao ler bytes do áudio: %s", read_err)
        return None

    if not raw_bytes or len(raw_bytes) < 32:
        return None

    fields = {
        "model": DEFAULT_WHISPER_MODEL,
        "language": "pt",
        "response_format": "json",
        "temperature": "0.0",
    }

    try:
        body_bytes, content_type_header = _encode_multipart_form(fields, raw_bytes, filename, mimetype)
        req = urllib.request.Request(
            GROQ_TRANSCRIPTION_URL,
            data=body_bytes,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": content_type_header,
                "User-Agent": "M-One-Voice-Transcriber/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = (data.get("text") or "").strip()
            return text if text else None
    except urllib.error.HTTPError as http_err:
        err_msg = http_err.read().decode("utf-8", errors="ignore")
        logger.error("[Groq Whisper HTTP %d]: %s", http_err.code, err_msg)
        return None
    except Exception as e:
        logger.error("[Groq Whisper Error]: %s", e)
        return None
