#!/usr/bin/env python3
"""
M-One Permissions & RBAC Auditor (scripts/permissions_audit.py)
Audita a cobertura do catálogo de permissões por usuário (ALL_PERMISSIONS):
- Varre todos os Blueprints e rotas operacionais do Flask.
- Varre os links e travas na barra lateral (templates/components/sidebar.html).
- Identifica módulos novos ou órfãos sem chave no menu de permissões.
- Valida integridade das categorias e papéis padrão.
Anti-monólito: rigorosamente < 500 linhas.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Adicionar raiz do projeto ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Módulos do sistema/públicos/sub-rotas legitimamente isentos de permissão direta
EXEMPT_BLUEPRINTS: Set[str] = {
    # Autenticação e telas básicas
    "auth",              # /login, /logout (público)
    "dashboard",         # /dashboard (ponto de entrada de todos os logados)
    "maintenance",       # Telas de manutenção
    
    # Canais Comerciais Públicos / Vitrines externas
    "outlet",            # /outlet (canal promocional B2C público)
    "atacado",           # /atacado (catálogo B2B para lojistas)
    "showroom",          # /show-room (modo TV e vitrine)
    "custom_catalog",    # /c/<slug> (catálogos externos para clientes)

    # Webhooks, Integrações de Mensageria e APIs externas públicas
    "webhook",           # /webhook/* (recebimento de terceiros)
    "botconversa",       # Webhooks de automação de WhatsApp

    # Autoatendimento / Portais individuais dos colaboradores
    "employee_portal",   # /relatorio (cada colaborador acessa seus relatórios)
    "employee_alignment",# Alinhamentos individuais

    # Sub-Blueprints subordinados a um módulo operacional pai
    "freight_data_source",# Subordinado a 'freight'
    "import_lifecycle",   # Subordinado a 'imports'
    "import_financial",   # Subordinado a 'imports'
    "import_document",    # Subordinado a 'imports'
    "import_rules",       # Subordinado a 'imports'
    "import_settlement",  # Subordinado a 'imports'
    "import_repository",  # Subordinado a 'imports'
}

# Mapeamento oficial de Blueprints operacionais para suas respectivas chaves de permissão
BLUEPRINT_TO_PERMISSION_MAP: Dict[str, str] = {
    "sales": "sales",
    "stock": "stock",
    "freight": "freight",
    "products": "products",
    "finance": "payments",
    "fiscal_pricing": "fiscal",
    "mpay": "mpay",
    "document_center": "document_center",
    "data_sources": "data_sources",
    "bling": "bling",
    "copilot": "copilot",
    "user": "users",
    "infra": "infra",
    "connections": "connections",
    "backups": "backups",
    "implementation_plan": "implementation_plan",
    "prospector": "prospector",
    "radar": "radar",
    "imports": "imports",
}


def audit_permissions(verbose: bool = True) -> Tuple[bool, List[str], List[str]]:
    """
    Executa a varredura completa de RBAC do M-One.
    Retorna: (is_ok, list_of_errors, list_of_warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        from app import app
        from services.user_permission_service import (
            ALL_PERMISSIONS,
            PERMISSIONS_CATEGORIES,
        )
    except Exception as e:
        return False, [f"Falha ao carregar contexto do app ou user_permission_service: {e}"], []

    cat_ids = {c["id"] for c in PERMISSIONS_CATEGORIES}

    # 1. Validar integridade interna do catálogo ALL_PERMISSIONS
    for p_key, meta in ALL_PERMISSIONS.items():
        if not isinstance(meta, dict):
            errors.append(f"Permissão '{p_key}' não é um dicionário válido.")
            continue
        cat = meta.get("category")
        if cat not in cat_ids:
            errors.append(f"Permissão '{p_key}' tem categoria inválida '{cat}'. Esperadas: {cat_ids}")
        for req_field in ["label", "icon", "description", "default_roles"]:
            if req_field not in meta or not meta[req_field]:
                errors.append(f"Permissão '{p_key}' está sem o campo obrigatório '{req_field}'.")

    # 2. Auditar Blueprints do Flask
    registered_blueprints = set(app.blueprints.keys())
    for bp in sorted(registered_blueprints):
        if bp in EXEMPT_BLUEPRINTS:
            continue
        if bp not in BLUEPRINT_TO_PERMISSION_MAP:
            errors.append(
                f"NOVA FUNÇÃO DETECTADA: Blueprint '{bp}' não possui chave de permissão mapeada em BLUEPRINT_TO_PERMISSION_MAP!"
            )
        else:
            perm_key = BLUEPRINT_TO_PERMISSION_MAP[bp]
            if perm_key not in ALL_PERMISSIONS:
                errors.append(
                    f"FALTA NO MENU DE PERMISSÕES: Blueprint '{bp}' aponta para a chave '{perm_key}', "
                    f"mas ela NÃO está cadastrada em ALL_PERMISSIONS (services/user_permission_service.py)!"
                )

    # 3. Auditar chamadas user_has_permission em templates/components/sidebar.html
    sidebar_path = BASE_DIR / "templates" / "components" / "sidebar.html"
    if sidebar_path.exists():
        content = sidebar_path.read_text(encoding="utf-8")
        # Regex para capturar chaves passadas a user_has_permission(me, 'chave')
        matches = re.findall(r"user_has_permission\s*\(\s*me\s*,\s*['\"]([^'\"]+)['\"]\s*\)", content)
        for perm_in_sidebar in set(matches):
            if perm_in_sidebar not in ALL_PERMISSIONS:
                errors.append(
                    f"SIDEBAR DESALINHADA: O menu lateral consulta a permissão '{perm_in_sidebar}', "
                    f"mas ela não existe no catálogo ALL_PERMISSIONS!"
                )

    is_ok = len(errors) == 0
    return is_ok, errors, warnings


def main():
    print("\n" + "=" * 54)
    print("🔐 [M-One RBAC & Permissions Guard]")
    print("Iniciando auditoria de cobertura de permissões...")
    print("=" * 54)

    is_ok, errors, warnings = audit_permissions(verbose=True)

    from services.user_permission_service import ALL_PERMISSIONS, PERMISSIONS_CATEGORIES
    print(f"  • Catálogo Oficial: {len(ALL_PERMISSIONS)} permissões em {len(PERMISSIONS_CATEGORIES)} categorias temáticas.")
    print(f"  • Blueprints Auditados: {len(BLUEPRINT_TO_PERMISSION_MAP)} operacionais, {len(EXEMPT_BLUEPRINTS)} isentos.")

    if warnings:
        print(f"\n⚠️  {len(warnings)} aviso(s) detectado(s):")
        for w in warnings:
            print(f"  • {w}")

    if not is_ok:
        print(f"\n❌ FALHA NA AUDITORIA: {len(errors)} problema(s) de permissões detectado(s)!\n")
        for err in errors:
            print(f"  🚨 {err}")

        print("\n💡 Como resolver:")
        print("  1. Se for uma nova função operacional, adicione a respectiva chave em ALL_PERMISSIONS")
        print("     (no arquivo services/user_permission_service.py) com categoria, ícone e default_roles.")
        print("  2. Mapeie o Blueprint em BLUEPRINT_TO_PERMISSION_MAP (em scripts/permissions_audit.py).")
        print("  3. Se for uma rota legitimamente pública ou webhook, adicione em EXEMPT_BLUEPRINTS.")
        print("=" * 54 + "\n")
        sys.exit(1)

    print("\n" + "=" * 54)
    print("✨ SUCESSO: Todas as funções do M-One possuem permissões!")
    print("Nenhum módulo órfão ou desprotegido detectado.")
    print("=" * 54 + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
