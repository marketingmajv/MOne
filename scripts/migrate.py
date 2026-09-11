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

    with db() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_permissions JSONB DEFAULT '{}'::jsonb;")
            conn.commit()
        except Exception as e:
            pass
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

    print("📱 [4/4] Criando tabela de linhas e contas monitoradas do WhatsApp...")
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS whatsapp_monitored_lines (
                id SERIAL PRIMARY KEY,
                waba_id TEXT DEFAULT 'evolution',
                account_name TEXT NOT NULL,
                phone_number_id TEXT,
                display_phone_number TEXT,
                quality_rating TEXT DEFAULT 'GREEN',
                is_monitored BOOLEAN DEFAULT TRUE,
                assigned_seller_name TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_monitored_lines_waba_phone ON whatsapp_monitored_lines(waba_id, COALESCE(phone_number_id, ''));
        """)
        conn.commit()

        # Colunas adicionais para suporte a instâncias autônomas (Evolution API / QR Code)
        evolution_line_cols = [
            ("instance_name", "TEXT"),
            ("instance_type", "TEXT DEFAULT 'evolution'"),
            ("connection_status", "TEXT DEFAULT 'disconnected'"),
            ("battery_level", "INTEGER"),
            ("assigned_user_id", "INTEGER"),
            ("profile_pic_url", "TEXT"),
            ("qrcode_base64", "TEXT"),
        ]
        for col, col_def in evolution_line_cols:
            try:
                conn.execute(f"ALTER TABLE whatsapp_monitored_lines ADD COLUMN IF NOT EXISTS {col} {col_def};")
            except Exception as e:
                print(f"  ⚠️ Coluna {col} em whatsapp_monitored_lines: {e}")

        # Tornar waba_id opcional se já existir a tabela
        try:
            conn.execute("ALTER TABLE whatsapp_monitored_lines ALTER COLUMN waba_id DROP NOT NULL;")
        except Exception:
            pass

        # Colunas de vínculo em whatsapp_messages
        msg_cols = [
            ("seller_id", "INTEGER"),
            ("seller_name", "TEXT"),
            ("instance_name", "TEXT"),
        ]
        for col, col_def in msg_cols:
            try:
                conn.execute(f"ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS {col} {col_def};")
            except Exception as e:
                print(f"  ⚠️ Coluna {col} em whatsapp_messages: {e}")

        conn.commit()
    print("  ✓ Tabela whatsapp_monitored_lines e whatsapp_messages atualizadas para Evolution API.")

    print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")


if __name__ == "__main__":
    run_migrations()
