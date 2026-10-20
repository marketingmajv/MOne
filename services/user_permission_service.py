"""
M-One User Permissions & RBAC Service (services/user_permission_service.py)
Auditoria e Catálogo Completo de Permissões Operacionais do M-One:
- 22 permissões mapeadas divididas em 5 categorias temáticas
- Suporte a sobreposição granular por usuário (custom_permissions)
- Predefinições inteligentes por cargo (Diretoria, Financeiro, Estoque, Vendas, Suporte)
- Bypass estrito exclusivo para fundadores mestre (@jam e @fauzer)
Segregação estrita modular (< 500 linhas).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# Fundadores com acesso mestre irrestrito
SUPER_ADMINS = {"jam", "fauzer"}

PERMISSIONS_CATEGORIES = [
    {
        "id": "comercial",
        "label": "Comercial & Vendas",
        "icon": "💼",
        "description": "Módulos de vendas, esteira de leads, catálogos e vitrines",
    },
    {
        "id": "logistica",
        "label": "Logística & Estoque",
        "icon": "🚚",
        "description": "Controle físico de veículos, fretes e importações marítimas",
    },
    {
        "id": "financeiro",
        "label": "Financeiro & Fiscal",
        "icon": "💰",
        "description": "Controle de liquidações, quitações e inteligência tributária",
    },
    {
        "id": "governanca",
        "label": "Governança & Equipe",
        "icon": "🛡️",
        "description": "Documentos unificados, relatórios executivos e auditoria",
    },
    {
        "id": "integracoes",
        "label": "Integrações & Sistema",
        "icon": "⚙️",
        "description": "Automações 24/7, conexões de APIs, ERP Bling e infraestrutura",
    },
]

ALL_PERMISSIONS = {
    # ---------------- COMERCIAL (8) ----------------
    "copilot": {
        "category": "comercial",
        "label": "Copilot IA Assistente",
        "icon": "⚡",
        "description": "Assistente comercial inteligente e de produtos",
        "default_roles": ["admin", "support", "sales", "finance", "stock"],
    },
    "sales": {
        "category": "comercial",
        "label": "Vendas & Pedidos",
        "icon": "📈",
        "description": "Acesso ao painel de pedidos e propostas comerciais",
        "default_roles": ["admin", "support", "sales", "finance"],
    },
    "all_sales": {
        "category": "comercial",
        "label": "Ver Vendas de Toda Equipe",
        "icon": "👥",
        "description": "Se desligado, visualiza apenas os próprios pedidos",
        "default_roles": ["admin", "support", "finance"],
    },
    "custom_catalogs": {
        "category": "comercial",
        "label": "Gestão de Catálogos Personalizados",
        "icon": "📑",
        "description": "Permite clonar matrizes, configurar margem e distribuir links (/c/)",
        "default_roles": ["admin", "support"],
    },
    "outlet": {
        "category": "comercial",
        "label": "Gestão do Outlet MAJ",
        "icon": "🏷️",
        "description": "Catálogo promocional B2C e queima de estoque",
        "default_roles": ["admin", "support"],
    },
    "atacado": {
        "category": "comercial",
        "label": "MAJ Atacado CNPJ",
        "icon": "🏢",
        "description": "Catálogo de atacado para revendedores corporativos B2B",
        "default_roles": ["admin", "support"],
    },
    "showroom": {
        "category": "comercial",
        "label": "Modelos & Showroom",
        "icon": "📺",
        "description": "Gestão de modelos e painel de vitrine Modo TV",
        "default_roles": ["admin", "support", "sales"],
    },
    "prospector": {
        "category": "comercial",
        "label": "Prospecção de Leads",
        "icon": "🎯",
        "description": "Máquina automatizada de descoberta e abordagem B2B",
        "default_roles": ["admin", "support", "sales"],
    },

    # ---------------- LOGÍSTICA & ESTOQUE (4) ----------------
    "stock": {
        "category": "logistica",
        "label": "Estoque & Chassis",
        "icon": "📦",
        "description": "Consulta e alocação de veículos disponíveis",
        "default_roles": ["admin", "support", "stock", "sales", "finance"],
    },
    "freight": {
        "category": "logistica",
        "label": "Cotador de Fretes & Expedição",
        "icon": "🚚",
        "description": "Simulação com regras de cubagem e transportadoras",
        "default_roles": ["admin", "support", "sales", "stock", "finance"],
    },
    "imports": {
        "category": "logistica",
        "label": "Importações China",
        "icon": "🚢",
        "description": "Processos aduaneiros, PI, CI, câmbio, despesas Brasil e navios",
        "default_roles": ["admin", "support"],
    },
    "products": {
        "category": "logistica",
        "label": "Catálogo de Produtos & Fichas",
        "icon": "📋",
        "description": "Tabela de preços, pesos cubados e especificações técnicas",
        "default_roles": ["admin", "support", "stock", "finance"],
    },

    # ---------------- FINANCEIRO & FISCAL (2) ----------------
    "payments": {
        "category": "financeiro",
        "label": "Pagamentos & Quitações",
        "icon": "💳",
        "description": "Controle de liquidações financeiras e baixas",
        "default_roles": ["admin", "support", "finance"],
    },
    "fiscal": {
        "category": "financeiro",
        "label": "Precificação Fiscal",
        "icon": "⚖️",
        "description": "Simulador tributário, MVAs e créditos interestaduais",
        "default_roles": ["admin", "support", "finance"],
    },

    # ---------------- GOVERNANÇA & EQUIPE (4) ----------------
    "document_center": {
        "category": "governanca",
        "label": "Central Unificada de Documentos",
        "icon": "📁",
        "description": "Repositório oficial de contratos, certidões e arquivos",
        "default_roles": ["admin", "support"],
    },
    "implementation_plan": {
        "category": "governanca",
        "label": "Relatórios & Governança",
        "icon": "📊",
        "description": "Relatórios de status e governança operacional MAJ",
        "default_roles": ["admin", "support", "finance", "sales", "stock"],
    },
    "users": {
        "category": "governanca",
        "label": "Gestão de Usuários & Senhas",
        "icon": "🔐",
        "description": "Cadastro de equipe e controle de acessos individuais",
        "default_roles": ["admin"],
    },
    "audit_logs": {
        "category": "governanca",
        "label": "Trilha de Auditoria",
        "icon": "🛡️",
        "description": "Rastreamento forense de ações e segurança do sistema",
        "default_roles": ["admin", "support"],
    },

    # ---------------- INTEGRAÇÕES & SISTEMA (5) ----------------
    "data_sources": {
        "category": "integracoes",
        "label": "Fontes de Dados (24/7)",
        "icon": "⚡",
        "description": "Mapeamento de planilhas e motores contínuos de sincronização",
        "default_roles": ["admin", "support"],
    },
    "connections": {
        "category": "integracoes",
        "label": "Central de Conexões & APIs",
        "icon": "🔌",
        "description": "Gerenciamento de chaves e webhooks de serviços externos",
        "default_roles": ["admin", "support"],
    },
    "bling": {
        "category": "integracoes",
        "label": "Integração Bling ERP",
        "icon": "🔄",
        "description": "Sincronização de pedidos de venda e notas fiscais",
        "default_roles": ["admin", "support"],
    },
    "backups": {
        "category": "integracoes",
        "label": "Backups Físicos & Snapshots",
        "icon": "💾",
        "description": "Download e auditoria de cópias de segurança do banco",
        "default_roles": ["admin", "support"],
    },
    "infra": {
        "category": "integracoes",
        "label": "Monitor de Infra & Vercel",
        "icon": "📡",
        "description": "Telemetria de logs, tempo de resposta e integridade da nuvem",
        "default_roles": ["admin", "support"],
    },
}


def parse_custom_permissions(raw: Any) -> Dict[str, bool]:
    """Converte formato do banco (string json ou dict) em dicionário padronizado."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): bool(v) for k, v in raw.items()}
    if isinstance(raw, str):
        try:
            d = json.loads(raw)
            return {str(k): bool(v) for k, v in d.items()} if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}


def get_default_permission_for_role(role: str, perm_key: str) -> bool:
    """Verifica se a permissão é concedida por padrão para o cargo especificado."""
    meta = ALL_PERMISSIONS.get(perm_key)
    if not meta:
        return False
    return role in meta.get("default_roles", [])


def user_has_permission_check(u: Optional[Dict[str, Any]], permission_key: str, default_for_sales: bool = False) -> bool:
    """
    Avalia se o usuário tem permissão para acessar determinado módulo.
    Regra acordada:
    1. Fundadores mestre (@jam e @fauzer) têm acesso 100% irrestrito sempre.
    2. Se a permissão estiver explicitamente gravada em 'custom_permissions', ela SOBREPÕE
       qualquer cargo (mesmo Diretoria/admin ou Vendas).
    3. Se não estiver configurada no custom_permissions, assume o padrão natural do cargo.
    """
    if not u:
        return False

    username = str(u.get("username", "")).strip().lower()
    if username in SUPER_ADMINS:
        return True

    perms = parse_custom_permissions(u.get("custom_permissions"))

    # Sobreposição explícita tem prioridade máxima
    if permission_key in perms:
        return bool(perms[permission_key])

    # Se não foi personalizada, assume o padrão do cargo
    role = str(u.get("role", "sales")).strip().lower()
    return get_default_permission_for_role(role, permission_key)


def get_user_effective_permissions(u: Dict[str, Any]) -> Dict[str, bool]:
    """Retorna o estado efetivo (True/False) de todas as 22 permissões para um usuário."""
    res: Dict[str, bool] = {}
    for perm_key in ALL_PERMISSIONS:
        res[perm_key] = user_has_permission_check(u, perm_key)
    return res


def get_role_preset(role: str) -> Dict[str, bool]:
    """Gera o mapa padrão de permissões ativas para um determinado cargo."""
    preset: Dict[str, bool] = {}
    for perm_key, meta in ALL_PERMISSIONS.items():
        preset[perm_key] = (role in meta.get("default_roles", []))
    return preset
