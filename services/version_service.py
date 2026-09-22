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
    "version": "1.1.0",
    "display_version": "v1.1",
    "build": "20260922.1",
    "release_date": "2026-09-22",
    "title": "M-One v1.1 • Fretes Cubados & Modal Avançado",
    "subtitle": "Cálculo de peso cubado para veículos elétricos, modal cadastral em 4 abas e ergonomia visual aprimorada.",
    "highlights": [
        {
            "icon": "⚖️",
            "category": "Regra do Peso Cubado",
            "summary": "Motor de cálculo atualizado para aplicar max(peso bruto, volume * 300kg/m³), evitando perdas em fretes de bikes e scooters."
        },
        {
            "icon": "🏢",
            "category": "Modal em 4 Abas",
            "summary": "Ficha Cadastral, Regras & Taxas (TEC/TAS/POS), Faixas Tarifárias com busca por cidade e Auditoria IA."
        },
        {
            "icon": "🎨",
            "category": "Ergonomia & Tipografia",
            "summary": "Base de tipografia ajustada para 14px (padrão Stripe/Linear) com melhor contraste e legibilidade em todas as telas."
        },
        {
            "icon": "🛡️",
            "category": "Segurança & Integridade",
            "summary": "Proteção anti-CSRF global, autenticação PBKDF2:SHA256 com rehash transparente e 100% anti-monólito."
        }
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
