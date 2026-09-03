#!/usr/bin/env python3
"""
M-One Pre-Deploy Integrity Checker
Valida sintaxe Python, templates Jinja2, inicialização Flask e variáveis críticas de DB.
"""
import sys
import py_compile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def validate_all():
    print("🔍 [1/4] Varredura de sintaxe e compilação Python...")
    python_files = ["app.py", "api/index.py"]
    for pf in python_files:
        full_path = BASE_DIR / pf
        if full_path.exists():
            try:
                py_compile.compile(str(full_path), doraise=True)
                print(f"  ✓ {pf}: Sintaxe válida")
            except py_compile.PyCompileError as e:
                print(f"  ✗ ERRO no arquivo {pf}: {e}")
                return False

    print("🎨 [2/4] Varredura de integridade dos templates HTML/Jinja2...")
    try:
        from jinja2 import Environment, FileSystemLoader
        templates_dir = BASE_DIR / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        for template_file in templates_dir.glob("*.html"):
            try:
                env.parse(template_file.read_text(encoding="utf-8"))
                print(f"  ✓ templates/{template_file.name}: Template válido")
            except Exception as e:
                print(f"  ✗ ERRO no template {template_file.name}: {e}")
                return False
    except Exception as e:
        print(f"  ✗ Falha ao carregar Jinja2: {e}")
        return False

    print("⚙️ [3/4] Validação da aplicação Flask e rotas...")
    try:
        from app import app
        with app.test_client() as client:
            res = client.get("/login")
            if res.status_code != 200:
                print(f"  ✗ Falha no endpoint /login: HTTP {res.status_code}")
                return False
            print("  ✓ Instanciação do Flask e rota /login: HTTP 200 OK")
    except Exception as e:
        print(f"  ✗ ERRO na inicialização da aplicação: {e}")
        return False

    print("🛡️ [4/4] Validação da configuração de banco de dados (IPv4 Pooler)...")
    try:
        from app import DEFAULT_DB_URL
        if "aws-0-us-west-2.pooler.supabase.com" not in DEFAULT_DB_URL:
            print("  ✗ AVISO: DEFAULT_DB_URL não aponta para o pooler IPv4 verificado do Supabase.")
            return False
        print("  ✓ Pooler IPv4 Supabase verificado")
    except Exception as e:
        print(f"  ✗ ERRO na checagem de banco de dados: {e}")
        return False

    print("\n✅ TODAS AS VERIFICAÇÕES FORAM APROVADAS! Código pronto para deploy.\n")
    return True

if __name__ == "__main__":
    if not validate_all():
        sys.exit(1)
    sys.exit(0)
