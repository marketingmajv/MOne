"""
M-One Database Migration & Schema CLI (scripts/migrate.py)
Executa a criação/migração de schema, DDL de tabelas, introspecção de colunas e índices.
Pode ser executado diretamente pelo terminal via `python3 scripts/migrate.py`.
"""

import sys
from pathlib import Path

# Adicionar o diretório pai ao sys.path para importação de módulos do app
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database import db, ensure_indexes
from services.automation.schema import (
    ensure_automation_schema,
    seed_default_flows_if_empty,
)


def run_migrations():
    print("🚀 [1/3] Executando migração de esquema de automações & CRM...")
    ensure_automation_schema(force=True)
    print("  ✓ Tabelas e colunas verificadas via introspecção com sucesso.")

    print("⚡ [2/3] Aplicando índices de alta performance no banco de dados...")
    with db() as conn:
        ensure_indexes(conn)
    print("  ✓ Índices aplicados.")

    print("🌱 [3/3] Semeando dados padrão de fluxos se necessário...")
    seed_default_flows_if_empty()
    print("  ✓ Fluxos padrão verificados.")

    print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")


if __name__ == "__main__":
    run_migrations()
