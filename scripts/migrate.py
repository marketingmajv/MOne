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
    print("⚡ [1/3] Aplicando índices de alta performance no banco de dados...")
    with db() as conn:
        ensure_indexes(conn)
    print("  ✓ Índices verificados e aplicados.")

    print("📊 [2/3] Verificando e adicionando colunas de atribuição de anúncios no CRM...")
    attribution_columns = [
        ("campaign_id", "TEXT"),
        ("campaign_name", "TEXT"),
        ("ad_id", "TEXT"),
        ("ad_headline", "TEXT"),
        ("ctwa_clid", "TEXT"),
        ("traffic_source", "TEXT"),
    ]
    with db() as conn:
        for col, col_type in attribution_columns:
            try:
                conn.execute(f"ALTER TABLE crm_leads ADD COLUMN IF NOT EXISTS {col} {col_type};")
            except Exception as e:
                print(f"  ⚠️ Coluna {col}: {e}")
        conn.commit()
    print("  ✓ Colunas de atribuição em crm_leads validadas.")

    print("📡 [3/3] Criando tabela de log de eventos de webhooks para o Centro de Conexões...")
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS webhook_event_logs (
                id SERIAL PRIMARY KEY,
                service TEXT NOT NULL DEFAULT 'meta_whatsapp',
                event_type TEXT DEFAULT 'message',
                sender TEXT,
                summary TEXT,
                payload JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_webhook_logs_service ON webhook_event_logs(service);
            CREATE INDEX IF NOT EXISTS idx_webhook_logs_created_at ON webhook_event_logs(created_at DESC);
        """)
        conn.commit()
    print("  ✓ Tabela webhook_event_logs pronta.")

    print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")


if __name__ == "__main__":
    run_migrations()
