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


def run_migrations():
    print("⚡ [1/1] Aplicando índices de alta performance no banco de dados...")
    with db() as conn:
        ensure_indexes(conn)
    print("  ✓ Índices verificados e aplicados.")

    print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")


if __name__ == "__main__":
    run_migrations()
