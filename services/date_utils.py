"""
M-One Date and Time Utilities (services/date_utils.py)
Garante a padronização oficial no Horário Oficial de Brasília (America/Sao_Paulo / UTC-3),
evitando distorções causadas por servidores na nuvem (Render, AWS) operando em UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def get_brasilia_now() -> datetime:
    """
    Retorna o momento atual no Horário Oficial de Brasília (America/Sao_Paulo).
    Retorna como datetime naive para compatibilidade estrita com colunas
    TIMESTAMP WITHOUT TIME ZONE do PostgreSQL/SQLite.
    """
    return datetime.now(BRAZIL_TZ).replace(tzinfo=None)


def to_brasilia_naive(dt: Any) -> Optional[datetime]:
    """
    Normaliza qualquer objeto datetime, timestamp ou string ISO para um
    datetime naive no Horário Oficial de Brasília.
    """
    if dt is None:
        return None

    if isinstance(dt, str):
        cleaned = dt.strip().replace("T", " ")
        if not cleaned:
            return None
        # Remove sufixo Z se presente
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1]
            try:
                parsed = datetime.fromisoformat(cleaned).replace(tzinfo=timezone.utc)
                return parsed.astimezone(BRAZIL_TZ).replace(tzinfo=None)
            except Exception:
                pass
        try:
            # Tenta converter string ISO direta
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is not None:
                return parsed.astimezone(BRAZIL_TZ).replace(tzinfo=None)
            return parsed
        except Exception:
            try:
                # Tenta formato padrão SQL
                return datetime.strptime(cleaned[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            return dt.astimezone(BRAZIL_TZ).replace(tzinfo=None)
        return dt

    return None


def format_brasilia_dt(dt: Any, fmt: str = "%d/%m/%Y às %H:%M") -> str:
    """
    Formata com segurança qualquer datetime para exibição amigável em pt-BR.
    Exemplo: '13/11/2026 às 15:05'
    """
    if not dt:
        return ""

    dt_obj = to_brasilia_naive(dt)
    if not dt_obj:
        return str(dt)[:16] if dt else ""

    try:
        return dt_obj.strftime(fmt)
    except Exception:
        return str(dt_obj)[:16]
