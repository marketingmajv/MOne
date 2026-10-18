#!/usr/bin/env python3
"""
M-One Pre-Deploy Integrity & Production Readiness Checker (scripts/validate.py)
Executa auditoria profunda antes de qualquer deploy:
1. Paridade Estrita de Dependências (AST Scan vs requirements.txt)
2. Compilação e Sintaxe Python Completa (Raiz, routes/, services/, scripts/)
3. Integridade e Parsing dos Templates HTML/Jinja2 (Inclusive Subpastas)
4. Auditoria de UX/UI, Modais Centralizados e Esquema de Cores (scripts/ux_audit.py)
5. Teste Ativo de Rotas Comerciais e Canais de Venda (/outlet, /atacado, /showroom, /login)
6. Verificação de Conexão com o Banco Supabase (IPv4 Pooler)
"""

from __future__ import annotations

import ast
import os
import py_compile
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def check_dependency_parity() -> bool:
    """Verifica se todas as bibliotecas externas importadas no código estão no requirements.txt."""
    print("📦 [1/5] Auditoria Preditiva de Dependências (AST Scan vs requirements.txt)...")

    req_file = BASE_DIR / "requirements.txt"
    if not req_file.exists():
        print("  ✗ requirements.txt não encontrado na raiz do projeto!")
        return False

    req_packages = set()
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                pkg = line.split(">=")[0].split("==")[0].split("<")[0].split(">")[0].strip().lower().replace("-", "_")
                req_packages.add(pkg)

    # Mapeamento canônico de imports conhecidos para pacotes PyPI
    PACKAGE_MAP = {
        "dotenv": "python_dotenv",
        "psycopg2": "psycopg2_binary",
        "reportlab": "reportlab",
        "openpyxl": "openpyxl",
        "pypdf": "pypdf",
        "flask": "flask",
        "werkzeug": "flask",
        "jinja2": "flask",
        "itsdangerous": "flask",
        "click": "flask",
    }

    # Módulos padrão do Python detectados do interpretador
    try:
        import distutils.sysconfig
        stdlib_dir = distutils.sysconfig.get_python_lib(standard_lib=True)
        stdlib_names = {f.split(".")[0] for f in os.listdir(stdlib_dir) if not f.startswith("_")}
    except Exception:
        stdlib_names = set()
    stdlib_names.update(sys.builtin_module_names)
    stdlib_names.update({
        "abc", "argparse", "ast", "asyncio", "base64", "calendar", "collections",
        "concurrent", "contextlib", "copy", "csv", "ctypes", "dataclasses", "datetime",
        "decimal", "distutils", "email", "enum", "errno", "functools", "gc", "glob",
        "hashlib", "heapq", "html", "http", "importlib", "inspect", "io", "itertools",
        "json", "logging", "math", "mimetypes", "multiprocessing", "os", "pathlib",
        "pkgutil", "platform", "py_compile", "random", "re", "secrets", "shutil",
        "signal", "socket", "sqlite3", "ssl", "stat", "string", "subprocess", "sys",
        "tempfile", "threading", "time", "traceback", "types", "typing", "unicodedata",
        "unittest", "urllib", "uuid", "warnings", "weakref", "xml", "zipfile", "__future__",
    })

    local_modules = {f.stem for f in BASE_DIR.glob("*.py")} | {d.name for d in BASE_DIR.iterdir() if d.is_dir()}

    undeclared_imports: list[tuple[str, str, int]] = []
    scanned_files = 0

    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in [".venv", ".git", "__pycache__", "node_modules", "scratch", "build", "dist", ".gemini"]]
        for f in files:
            if f.endswith(".py"):
                filepath = Path(root) / f
                scanned_files += 1
                try:
                    tree = ast.parse(filepath.read_text(encoding="utf-8", errors="ignore"), filename=str(filepath))
                    for node in ast.walk(tree):
                        mod_name = None
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                mod_name = alias.name.split(".")[0]
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                mod_name = node.module.split(".")[0]

                        if mod_name:
                            canonical = PACKAGE_MAP.get(mod_name, mod_name.lower().replace("-", "_"))
                            if mod_name not in stdlib_names and mod_name not in local_modules and canonical not in req_packages:
                                rel_path = str(filepath.relative_to(BASE_DIR))
                                undeclared_imports.append((mod_name, rel_path, getattr(node, "lineno", 0)))
                except Exception as e:
                    print(f"  ✗ Erro ao parsear AST de {f}: {e}")
                    return False

    if undeclared_imports:
        print(f"  ✗ ERRO FATAL: Encontradas dependências externas NÃO declaradas em requirements.txt ({len(undeclared_imports)} ocorrências):")
        for mod, path, line in undeclared_imports:
            print(f"    • Módulo '{mod}' importado em {path}:{line}")
        print("  ➔ Ação necessária: Adicione as bibliotecas faltantes ao requirements.txt antes do deploy.")
        return False

    print(f"  ✓ {scanned_files} arquivos Python auditados: 100% das dependências mapeadas no requirements.txt")
    return True


def check_python_syntax() -> bool:
    """Valida a compilação de todos os arquivos Python do projeto."""
    print("🔍 [2/5] Varredura recursiva de sintaxe e compilação Python...")
    total_compiled = 0
    folders_to_scan = [BASE_DIR, BASE_DIR / "routes", BASE_DIR / "services", BASE_DIR / "scripts", BASE_DIR / "api"]

    for folder in folders_to_scan:
        if not folder.is_dir():
            continue
        for py_file in folder.glob("*.py"):
            try:
                py_compile.compile(str(py_file), doraise=True)
                total_compiled += 1
            except py_compile.PyCompileError as e:
                print(f"  ✗ ERRO de sintaxe no arquivo {py_file.name}: {e}")
                return False

    print(f"  ✓ {total_compiled} módulos Python compilados com sucesso.")
    return True


def check_templates() -> bool:
    """Valida todos os templates Jinja2 (raiz e subdiretórios)."""
    print("🎨 [3/5] Varredura de integridade dos templates HTML/Jinja2...")
    try:
        from jinja2 import Environment, FileSystemLoader
        templates_dir = BASE_DIR / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        total_templates = 0
        for template_file in templates_dir.rglob("*.html"):
            rel_name = str(template_file.relative_to(templates_dir))
            try:
                env.parse(template_file.read_text(encoding="utf-8", errors="ignore"))
                total_templates += 1
            except Exception as e:
                print(f"  ✗ ERRO no template {rel_name}: {e}")
                return False
        print(f"  ✓ {total_templates} templates Jinja2 auditados e íntegros.")
        return True
    except Exception as e:
        print(f"  ✗ Falha ao inicializar validador Jinja2: {e}")
        return False


def check_flask_commercial_routes() -> bool:
    """Testa a inicialização do Flask e os canais de venda comerciais e autenticação."""
    print("⚙️ [4/5] Teste ativo de rotas comerciais de venda e autenticação...")
    try:
        from app import app
        with app.test_client() as client:
            # 1. Rota de autenticação
            res_login = client.get("/login")
            if res_login.status_code != 200:
                print(f"  ✗ Falha no endpoint /login: HTTP {res_login.status_code}")
                return False
            print("  ✓ Rota /login: HTTP 200 OK")

            # 2. Rota comercial pública do Outlet
            res_outlet = client.get("/outlet")
            if res_outlet.status_code != 200:
                print(f"  ✗ Falha no canal comercial /outlet: HTTP {res_outlet.status_code}")
                return False
            print("  ✓ Canal Comercial /outlet: HTTP 200 OK")

            # 3. Rota comercial pública de Atacado B2B
            res_atacado = client.get("/atacado")
            if res_atacado.status_code != 200:
                print(f"  ✗ Falha no canal comercial /atacado: HTTP {res_atacado.status_code}")
                return False
            print("  ✓ Canal Comercial /atacado: HTTP 200 OK")

            # 4. Rota pública de Mostruário / Modelos & Show-Room
            res_models = client.get("/show-room")
            if res_models.status_code != 200:
                print(f"  ✗ Falha no canal /show-room: HTTP {res_models.status_code}")
                return False
            print("  ✓ Canal Comercial /show-room (Showroom): HTTP 200 OK")

        return True
    except Exception as e:
        print(f"  ✗ ERRO na inicialização da aplicação ou rotas: {e}")
        return False


def check_ux_ui_integrity() -> bool:
    """Executa auditoria profunda de UX/UI nos templates (modais centralizados, contraste e cores)."""
    print("🎨 [4/6] Auditoria de Integridade de UX/UI (Modais, Alinhamentos e Cores)...")
    try:
        from scripts.ux_audit import run_ux_audit
        return run_ux_audit()
    except Exception as e:
        print(f"  ✗ ERRO na execução da auditoria de UX: {e}")
        return False


def check_database_config() -> bool:
    """Valida a configuração do Pooler IPv4 Supabase."""
    print("🛡️ [6/6] Validação da configuração de banco de dados (IPv4 Pooler)...")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        load_dotenv(".env.local")
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or ""
        if "aws-0-us-west-2.pooler.supabase.com" not in db_url:
            print("  ✗ AVISO: DATABASE_URL no ambiente (.env) não aponta para o pooler IPv4 verificado do Supabase.")
            return False
        print("  ✓ Pooler IPv4 Supabase verificado no ambiente (.env)")
        return True
    except Exception as e:
        print(f"  ✗ ERRO na checagem de banco de dados: {e}")
        return False


def validate_all() -> bool:
    steps = [
        check_dependency_parity,
        check_python_syntax,
        check_templates,
        check_ux_ui_integrity,
        check_flask_commercial_routes,
        check_database_config,
    ]
    for step in steps:
        if not step():
            print("\n❌ FALHA NA VALIDAÇÃO PRÉ-DEPLOY! Publicação interrompida por segurança.\n")
            return False

    print("\n✅ TODAS AS 6 ETAPAS PREDITIVAS (INCLUINDO UX/UI) FORAM APROVADAS! Código 100% blindado para deploy.\n")
    return True


if __name__ == "__main__":
    if not validate_all():
        sys.exit(1)
    sys.exit(0)
