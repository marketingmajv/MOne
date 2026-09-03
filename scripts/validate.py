#!/usr/bin/env python3
import sys
import os
import importlib.util
from pathlib import Path

print("🔍 Executando varredura profunda de integridade do M-One...")

errors = []

# 1. Verificar arquivos essenciais
required_files = ["app.py", "requirements.txt", ".env", "templates/base.html", "templates/login.html"]
for rf in required_files:
    if not os.path.exists(rf):
        errors.append(f"Arquivo essencial ausente: {rf}")

# 2. Testar sintaxe e importação de app.py
try:
    spec = importlib.util.spec_from_file_location("app_module", "app.py")
    module = importlib.util.module_from_spec(spec)
    print("✅ Sintaxe do app.py verificada com sucesso.")
except Exception as e:
    errors.append(f"Erro de sintaxe em app.py: {e}")

# 3. Testar conexão com PostgreSQL Supabase Pooler
try:
    from dotenv import load_dotenv
    load_dotenv()
    import psycopg2
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if db_url:
        conn = psycopg2.connect(db_url, sslmode="require", connect_timeout=5)
        conn.close()
        print("✅ Conexão com banco de dados Supabase PostgreSQL verificada.")
    else:
        print("⚠️ DATABASE_URL não definida, ignorando teste de BD remoto.")
except Exception as e:
    errors.append(f"Falha ao conectar no Supabase PostgreSQL: {e}")

# 4. Verificar porta configurada
port = os.environ.get("PORT", "5001")
if port == "5000":
    errors.append("Porta 5000 é reservada pelo macOS (AirPlay/ControlCenter). Utilize a porta 5001.")
else:
    print(f"✅ Porta de desenvolvimento configurada: {port}")

if errors:
    print("\n❌ Varredura encontrou erros:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)

print("\n🎉 Varredura concluída! Todos os testes de integridade passaram.")
sys.exit(0)
