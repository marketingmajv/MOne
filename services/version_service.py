"""
Serviço de gerenciamento de versão e changelog do sistema M-One.
Lê os dados estruturados de version.json e disponibiliza para injeção global em templates e APIs.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger("mone.version")

_VERSION_CACHE: Dict[str, Any] | None = None
_LAST_MTIME: float = 0.0

DEFAULT_VERSION_INFO: Dict[str, Any] = {
    "version": "1.0.0",
    "display_version": "v1.0",
    "build": "20260921.1",
    "release_date": "2026-09-21",
    "title": "M-One v1.0 • Oficial",
    "subtitle": "Versão oficial estável do sistema M-One.",
    "highlights": [
        {"icon": "🛡️", "category": "Segurança", "summary": "Proteção ativa e auditoria reforçada."},
        {"icon": "🎨", "category": "Interface", "summary": "Visual modernizado e responsivo."},
        {"icon": "🚚", "category": "Fretes", "summary": "Cotações inteligentes e seleção para propostas."},
        {"icon": "⚡", "category": "Performance", "summary": "Conexões otimizadas e arquitetura modular."}
    ],
    "changelog": []
}


def get_version_info(force_reload: bool = False) -> Dict[str, Any]:
    """
    Retorna os dados de versão do sistema.
    Recarrega caso o arquivo version.json tenha sido modificado.
    """
    global _VERSION_CACHE, _LAST_MTIME

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    version_file = os.path.join(root_dir, "version.json")

    try:
        if not os.path.isfile(version_file):
            return DEFAULT_VERSION_INFO

        mtime = os.path.getmtime(version_file)
        if not force_reload and _VERSION_CACHE is not None and mtime == _LAST_MTIME:
            return _VERSION_CACHE

        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return DEFAULT_VERSION_INFO

        # Garante campos essenciais
        info = {**DEFAULT_VERSION_INFO, **data}
        _VERSION_CACHE = info
        _LAST_MTIME = mtime
        return _VERSION_CACHE

    except Exception as e:
        logger.warning("Falha ao ler version.json: %s. Usando fallback padrão.", e)
        return _VERSION_CACHE or DEFAULT_VERSION_INFO
