"""
M-One Document Rules Service (services/import_rules_service.py)
Gerencia as regras de obrigatoriedade de documentos e permissão de anexo posterior
para os diferentes estágios da importação (Embarcado vs Desembaraçado).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from database import db

logger = logging.getLogger(__name__)

# Configuração Padrão Oficial (Exatamente conforme diretriz do sistema)
DEFAULT_DOCUMENT_RULES = [
    {
        "doc_type": "PI",
        "label": "Proforma Invoice (PI)",
        "required_on_water": True,
        "required_cleared": True,
        "allow_post_attach": False,
        "order_num": 1,
    },
    {
        "doc_type": "CI",
        "label": "Commercial Invoice (CI)",
        "required_on_water": True,
        "required_cleared": True,
        "allow_post_attach": False,
        "order_num": 2,
    },
    {
        "doc_type": "BL",
        "label": "Bill of Lading (BL)",
        "required_on_water": True,
        "required_cleared": True,
        "allow_post_attach": False,
        "order_num": 3,
    },
    {
        "doc_type": "PL",
        "label": "Packing List (PL)",
        "required_on_water": True,
        "required_cleared": True,
        "allow_post_attach": False,
        "order_num": 4,
    },
    {
        "doc_type": "CHASSIS_LIST",
        "label": "Relação de Chassis",
        "required_on_water": True,
        "required_cleared": True,
        "allow_post_attach": False,
        "order_num": 5,
    },
    {
        "doc_type": "DUIMP_DI",
        "label": "DUIMP / DI",
        "required_on_water": False,
        "required_cleared": True,
        "allow_post_attach": True,
        "order_num": 6,
    },
    {
        "doc_type": "ENTRY_NF",
        "label": "Nota Fiscal de Entrada",
        "required_on_water": False,
        "required_cleared": True,
        "allow_post_attach": True,
        "order_num": 7,
    },
    {
        "doc_type": "NUMERARIO_TAX",
        "label": "Guias / Numerário",
        "required_on_water": False,
        "required_cleared": True,
        "allow_post_attach": True,
        "order_num": 8,
    },
    {
        "doc_type": "EXCHANGE_CONTRACT",
        "label": "Comprovantes de Câmbio",
        "required_on_water": False,
        "required_cleared": False,
        "allow_post_attach": True,
        "order_num": 9,
    },
    {
        "doc_type": "SUPPLIER_PAYMENT",
        "label": "Comprovantes Fornecedor",
        "required_on_water": False,
        "required_cleared": False,
        "allow_post_attach": True,
        "order_num": 10,
    },
]


def init_document_rules_table() -> None:
    """Garante a existência da tabela e o povoamento com as regras padrão se estiver vazia."""
    try:
        with db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS import_document_rules (
                    doc_type VARCHAR(50) PRIMARY KEY,
                    label VARCHAR(100) NOT NULL,
                    required_on_water BOOLEAN DEFAULT FALSE,
                    required_cleared BOOLEAN DEFAULT FALSE,
                    allow_post_attach BOOLEAN DEFAULT TRUE,
                    order_num INTEGER DEFAULT 99,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            count_res = conn.execute("SELECT COUNT(*) AS cnt FROM import_document_rules;").fetchone()
            cnt = count_res["cnt"] if count_res else 0
            if cnt == 0:
                for r in DEFAULT_DOCUMENT_RULES:
                    conn.execute(
                        """
                        INSERT INTO import_document_rules 
                        (doc_type, label, required_on_water, required_cleared, allow_post_attach, order_num)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (doc_type) DO NOTHING;
                        """,
                        (
                            r["doc_type"],
                            r["label"],
                            r["required_on_water"],
                            r["required_cleared"],
                            r["allow_post_attach"],
                            r["order_num"],
                        ),
                    )
    except Exception as e:
        logger.error("[init_document_rules_table] Erro ao inicializar regras: %s", e)


def get_document_rules() -> list[dict[str, Any]]:
    """Retorna todas as regras configuradas ordenadas."""
    init_document_rules_table()
    try:
        with db() as conn:
            rows = conn.execute(
                """
                SELECT doc_type, label, required_on_water, required_cleared, allow_post_attach, order_num
                FROM import_document_rules
                ORDER BY order_num ASC, label ASC;
                """
            ).fetchall()
            if rows:
                return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("[get_document_rules] Falha ao ler banco, usando default em memória: %s", e)
    return list(DEFAULT_DOCUMENT_RULES)


def get_document_rules_map() -> dict[str, dict[str, Any]]:
    """Retorna um dicionário indexado por doc_type."""
    rules = get_document_rules()
    return {r["doc_type"]: r for r in rules}


def save_document_rules(rules: list[dict[str, Any]], user_id: int | None = None) -> bool:
    """Atualiza a tabela de regras documentais."""
    init_document_rules_table()
    try:
        with db() as conn:
            for r in rules:
                conn.execute(
                    """
                    INSERT INTO import_document_rules 
                    (doc_type, label, required_on_water, required_cleared, allow_post_attach, order_num, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (doc_type) DO UPDATE SET
                        required_on_water = EXCLUDED.required_on_water,
                        required_cleared = EXCLUDED.required_cleared,
                        allow_post_attach = EXCLUDED.allow_post_attach,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (
                        r["doc_type"],
                        r.get("label", r["doc_type"]),
                        bool(r.get("required_on_water")),
                        bool(r.get("required_cleared")),
                        bool(r.get("allow_post_attach")),
                        int(r.get("order_num", 99)),
                    ),
                )
            try:
                from routes.helpers import audit
                audit("import.rules_updated", f"Regras documentais atualizadas por user_id={user_id}")
            except Exception:
                pass
        return True
    except Exception as e:
        logger.error("[save_document_rules] Erro ao salvar regras: %s", e)
        return False


def reset_document_rules_to_default(user_id: int | None = None) -> list[dict[str, Any]]:
    """Restaura as regras para a configuração padrão oficial."""
    init_document_rules_table()
    try:
        with db() as conn:
            conn.execute("DELETE FROM import_document_rules;")
            for r in DEFAULT_DOCUMENT_RULES:
                conn.execute(
                    """
                    INSERT INTO import_document_rules 
                    (doc_type, label, required_on_water, required_cleared, allow_post_attach, order_num)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        r["doc_type"],
                        r["label"],
                        r["required_on_water"],
                        r["required_cleared"],
                        r["allow_post_attach"],
                        r["order_num"],
                    ),
                )
            try:
                from routes.helpers import audit
                audit("import.rules_reset_default", f"Regras documentais restauradas para padrão por user_id={user_id}")
            except Exception:
                pass
        return list(DEFAULT_DOCUMENT_RULES)
    except Exception as e:
        logger.error("[reset_document_rules_to_default] Erro ao restaurar: %s", e)
        return list(DEFAULT_DOCUMENT_RULES)
