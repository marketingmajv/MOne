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
        "label": "VIN CHASSI (Relação de Chassis)",
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
        "doc_type": "ICMS_GUIDE",
        "label": "Guias de ICMS / Comprovante de ICMS",
        "required_on_water": False,
        "required_cleared": True,
        "allow_post_attach": True,
        "order_num": 8,
    },
    {
        "doc_type": "NF_FRETE_CARRETA",
        "label": "Nota Fiscal FRETE, CARRETA",
        "required_on_water": False,
        "required_cleared": True,
        "allow_post_attach": True,
        "order_num": 9,
    },
    {
        "doc_type": "AGENTE_CARGA_BR",
        "label": "AGENTE DE CARGA BRASIL",
        "required_on_water": False,
        "required_cleared": True,
        "allow_post_attach": True,
        "order_num": 10,
    },
    {
        "doc_type": "FECHAMENTO_DESPACHANTE",
        "label": "Fechamento Despachante",
        "required_on_water": False,
        "required_cleared": True,
        "allow_post_attach": True,
        "order_num": 11,
    },
    {
        "doc_type": "AJUDANTES_PAGTO",
        "label": "AJUDANTES (comprovante de pagamento)",
        "required_on_water": False,
        "required_cleared": False,
        "allow_post_attach": True,
        "order_num": 12,
    },
    {
        "doc_type": "EXCHANGE_CONTRACT",
        "label": "Comprovantes de Câmbio",
        "required_on_water": False,
        "required_cleared": False,
        "allow_post_attach": True,
        "order_num": 13,
    },
    {
        "doc_type": "SUPPLIER_PAYMENT",
        "label": "Comprovantes Fornecedor",
        "required_on_water": False,
        "required_cleared": False,
        "allow_post_attach": True,
        "order_num": 14,
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


CORE_DOC_TYPES = {"PI", "CI", "BL", "PL", "CHASSIS_LIST"}


def add_custom_document_rule(
    doc_type: str,
    label: str,
    required_on_water: bool = False,
    required_cleared: bool = False,
    allow_post_attach: bool = True,
    user_id: int | None = None,
) -> tuple[bool, str]:
    """Cadastra uma nova categoria de documento nas regras."""
    init_document_rules_table()
    doc_type = (doc_type or "").strip().upper().replace(" ", "_")
    label = (label or "").strip()

    if not doc_type or not label:
        return False, "Código e nome do documento são obrigatórios."

    try:
        with db() as conn:
            existing = conn.execute("SELECT doc_type FROM import_document_rules WHERE doc_type = %s", (doc_type,)).fetchone()
            if existing:
                return False, f"Já existe uma categoria cadastrada com o código '{doc_type}'."

            max_order_row = conn.execute("SELECT COALESCE(MAX(order_num), 0) AS max_o FROM import_document_rules").fetchone()
            next_order = (max_order_row["max_o"] if max_order_row else 0) + 1

            conn.execute(
                """
                INSERT INTO import_document_rules 
                (doc_type, label, required_on_water, required_cleared, allow_post_attach, order_num, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                """,
                (doc_type, label, bool(required_on_water), bool(required_cleared), bool(allow_post_attach), next_order),
            )
            try:
                from routes.helpers import audit
                audit("import.rule_category_created", f"Categoria '{label}' ({doc_type}) criada por user_id={user_id}")
            except Exception:
                pass
        return True, "Categoria adicionada com sucesso!"
    except Exception as e:
        logger.error("[add_custom_document_rule] Erro ao adicionar: %s", e)
        return False, f"Erro interno ao salvar: {e}"


def delete_document_rule(doc_type: str, user_id: int | None = None, is_admin_override: bool = False) -> tuple[bool, str]:
    """Exclui uma categoria de documento. Documentos essenciais exigem autorização explícita de admin."""
    doc_type = (doc_type or "").strip().upper()
    if doc_type in CORE_DOC_TYPES and not is_admin_override:
        return False, f"O documento essencial '{doc_type}' exige autorização com senha de administrador para exclusão."

    try:
        with db() as conn:
            res = conn.execute("DELETE FROM import_document_rules WHERE doc_type = %s", (doc_type,))
            if res.rowcount == 0:
                return False, "Categoria não encontrada."
            try:
                from routes.helpers import audit
                audit("import.rule_category_deleted", f"Categoria '{doc_type}' excluída por user_id={user_id} (override={is_admin_override})")
            except Exception:
                pass
        return True, "Categoria removida com sucesso!"
    except Exception as e:
        logger.error("[delete_document_rule] Erro ao excluir: %s", e)
        return False, f"Erro ao excluir categoria: {e}"


def update_document_rule_details(
    doc_type: str,
    label: str,
    required_on_water: bool,
    required_cleared: bool,
    allow_post_attach: bool,
    user_id: int | None = None,
) -> tuple[bool, str]:
    """Atualiza o nome e flags de uma categoria existente."""
    doc_type = (doc_type or "").strip().upper()
    label = (label or "").strip()
    if not doc_type or not label:
        return False, "Código e nome do documento são obrigatórios."

    try:
        with db() as conn:
            res = conn.execute(
                """
                UPDATE import_document_rules
                SET label = %s, required_on_water = %s, required_cleared = %s, allow_post_attach = %s, updated_at = CURRENT_TIMESTAMP
                WHERE doc_type = %s;
                """,
                (label, bool(required_on_water), bool(required_cleared), bool(allow_post_attach), doc_type),
            )
            if res.rowcount == 0:
                return False, "Categoria não encontrada para atualização."
            try:
                from routes.helpers import audit
                audit("import.rule_category_updated", f"Categoria '{doc_type}' atualizada para '{label}' por user_id={user_id}")
            except Exception:
                pass
        return True, "Categoria atualizada com sucesso!"
    except Exception as e:
        logger.error("[update_document_rule_details] Erro ao atualizar: %s", e)
        return False, f"Erro ao atualizar categoria: {e}"


def duplicate_document_rule(
    source_doc_type: str,
    new_doc_type: str,
    new_label: str,
    user_id: int | None = None,
) -> tuple[bool, str]:
    """Duplica uma categoria existente gerando uma nova regra parametrizada."""
    source_doc_type = (source_doc_type or "").strip().upper()
    new_doc_type = (new_doc_type or "").strip().upper().replace(" ", "_")
    new_label = (new_label or "").strip()

    if not new_doc_type or not new_label:
        return False, "Código e nome da nova categoria são obrigatórios."

    try:
        with db() as conn:
            source = conn.execute("SELECT * FROM import_document_rules WHERE doc_type = %s", (source_doc_type,)).fetchone()
            if not source:
                return False, "Documento de origem não encontrado."

            existing = conn.execute("SELECT doc_type FROM import_document_rules WHERE doc_type = %s", (new_doc_type,)).fetchone()
            if existing:
                return False, f"Já existe uma categoria cadastrada com o código '{new_doc_type}'."

            max_order_row = conn.execute("SELECT COALESCE(MAX(order_num), 0) AS max_o FROM import_document_rules").fetchone()
            next_order = (max_order_row["max_o"] if max_order_row else 0) + 1

            conn.execute(
                """
                INSERT INTO import_document_rules
                (doc_type, label, required_on_water, required_cleared, allow_post_attach, order_num, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                """,
                (
                    new_doc_type,
                    new_label,
                    bool(source["required_on_water"]),
                    bool(source["required_cleared"]),
                    bool(source["allow_post_attach"]),
                    next_order,
                ),
            )
            try:
                from routes.helpers import audit
                audit("import.rule_category_duplicated", f"Categoria '{new_label}' ({new_doc_type}) duplicada a partir de '{source_doc_type}' por user_id={user_id}")
            except Exception:
                pass
        return True, "Categoria duplicada com sucesso!"
    except Exception as e:
        logger.error("[duplicate_document_rule] Erro ao duplicar: %s", e)
        return False, f"Erro ao duplicar categoria: {e}"

