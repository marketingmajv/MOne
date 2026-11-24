#!/usr/bin/env python3
"""
M-One Client-Side Syntax & Template Tag Balance Auditor (scripts/client_syntax_audit.py)
Audita a integridade de templates Jinja2 e scripts JavaScript inline antes do deploy:
1. Balanceamento estrito de tags <template> e <script> (evita que o DOM seja aprisionado em tags inertes).
2. Validação sintática de JavaScript inline com Node.js (detecta erros de parse, funções e chaves antes do navegador).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def check_template_tag_balance(templates_dir: Path) -> tuple[bool, list[str]]:
    """Verifica se todas as tags <template> abertas possuem fechamento correspondente.</template>"""
    errors: list[str] = []
    total_audited = 0

    for html_file in templates_dir.rglob("*.html"):
        try:
            rel_path = str(html_file.relative_to(BASE_DIR))
        except ValueError:
            rel_path = str(html_file)
        try:
            content = html_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            errors.append(f"{rel_path}: Falha ao ler arquivo: {e}")
            continue

        total_audited += 1

        # Remover comentários Jinja2 e HTML antes de contar
        clean_content = re.sub(r"\{#.*?#\}", "", content, flags=re.DOTALL)
        clean_content = re.sub(r"<!--.*?-->", "", clean_content, flags=re.DOTALL)

        # Contagem de <template> e </template>
        # Procura tags de abertura <template com espaço ou fechando com >
        open_templates = len(re.findall(r"<\s*template(?:\s+[^>]*|\s*)>", clean_content, flags=re.IGNORECASE))
        close_templates = len(re.findall(r"<\s*/\s*template\s*>", clean_content, flags=re.IGNORECASE))

        if open_templates != close_templates:
            errors.append(
                f"{rel_path}: Desbalanceamento de tags <template> detectado! "
                f"Abertas: {open_templates} vs Fechadas: {close_templates} "
                f"(Diferença de {open_templates - close_templates})."
            )

        # Contagem de <script> e </script>
        open_scripts = len(re.findall(r"<\s*script(?:\s+[^>]*|\s*)>", clean_content, flags=re.IGNORECASE))
        close_scripts = len(re.findall(r"<\s*/\s*script\s*>", clean_content, flags=re.IGNORECASE))

        if open_scripts != close_scripts:
            errors.append(
                f"{rel_path}: Desbalanceamento de tags <script> detectado! "
                f"Abertas: {open_scripts} vs Fechadas: {close_scripts}."
            )

    return len(errors) == 0, errors


def sanitize_jinja_for_js_validation(js_code: str) -> str:
    """Substitui expressões Jinja2 por literais JavaScript válidos para teste sintático."""
    # 1. Expressões Jinja já envolvidas por aspas: '{{ ... }}' ou "{{ ... }}"
    sanitized = re.sub(r"'\{\{.*?\}\}'", "'__MOCK_STR__'", js_code)
    sanitized = re.sub(r'"\{\{.*?\}\}"', '"__MOCK_STR__"', sanitized)
    # 2. Expressões Jinja com filtro tojson sem aspas: {{ x | tojson }} -> []
    sanitized = re.sub(r"\{\{\s*.*?\|\s*tojson\s*\}\}", "[]", sanitized)
    # 3. Expressões Jinja unquoted restantes: {{ variavel }} -> 0
    sanitized = re.sub(r"\{\{.*?\}\}", "0", sanitized)
    # 4. Blocos de controle Jinja: {% ... %} -> /* jinja */
    sanitized = re.sub(r"\{%.*?%\}", "/* jinja */", sanitized)
    return sanitized


def check_inline_javascript_syntax(templates_dir: Path) -> tuple[bool, list[str]]:
    """Extrai blocos <script> inline de templates e valida a sintaxe via Node.js."""
    # Verificar se o Node.js está disponível no ambiente
    try:
        subprocess.run(["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception:
        # Se node não estiver disponível, emite aviso não-bloqueante
        print("  ⚠️ Node.js não detectado no PATH; verificação sintática de JS ignorada.")
        return True, []

    errors: list[str] = []
    audited_scripts = 0

    script_pattern = re.compile(
        r"<\s*script(?:\s+([^>]*))?\s*>(.*?)(?:<\s*/\s*script\s*>)",
        flags=re.DOTALL | re.IGNORECASE,
    )

    for html_file in templates_dir.rglob("*.html"):
        try:
            rel_path = str(html_file.relative_to(BASE_DIR))
        except ValueError:
            rel_path = str(html_file)
        try:
            content = html_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for match in script_pattern.finditer(content):
            attrs = match.group(1) or ""
            script_body = match.group(2) or ""

            # Ignorar scripts externos (com src) ou scripts de dados/templates que não sejam JS
            if "src=" in attrs.lower():
                continue
            if 'type="application/ld+json"' in attrs.lower() or "type='application/ld+json'" in attrs.lower():
                continue
            if 'type="text/html"' in attrs.lower() or 'type="text/template"' in attrs.lower():
                continue

            clean_js = script_body.strip()
            if not clean_js:
                continue

            audited_scripts += 1
            mocked_js = sanitize_jinja_for_js_validation(clean_js)

            # Testar sintaxe via node -c com arquivo temporário
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as temp_js:
                temp_js.write(mocked_js)
                temp_js_path = temp_js.name

            try:
                proc = subprocess.run(
                    ["node", "-c", temp_js_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if proc.returncode != 0:
                    err_msg = proc.stderr.strip()
                    # Limpar nome do arquivo temporário da mensagem de erro
                    err_msg = err_msg.replace(temp_js_path, rel_path)
                    # Pegar as 2 primeiras linhas do erro
                    short_err = "\n    ".join(err_msg.splitlines()[:3])
                    errors.append(f"{rel_path}: Erro de sintaxe no JavaScript inline:\n    {short_err}")
            finally:
                if os.path.exists(temp_js_path):
                    try:
                        os.remove(temp_js_path)
                    except Exception:
                        pass

    return len(errors) == 0, errors


def run_client_syntax_audit(verbose: bool = True) -> bool:
    """Executa a auditoria combinada de tags HTML e sintaxe JavaScript inline."""
    templates_dir = BASE_DIR / "templates"
    if not templates_dir.exists():
        if verbose:
            print("  ✗ Diretório templates/ não encontrado!")
        return False

    if verbose:
        print("🌐 [Client-Side Integrity] Auditando balanceamento de tags <template> e sintaxe JS inline...")

    # 1. Balanceamento de tags
    tags_ok, tag_errors = check_template_tag_balance(templates_dir)
    if not tags_ok:
        print("  ✗ FALHA: Desbalanceamento de tags HTML detectado:")
        for err in tag_errors:
            print(f"    • {err}")
        return False

    # 2. Sintaxe JavaScript inline
    js_ok, js_errors = check_inline_javascript_syntax(templates_dir)
    if not js_ok:
        print("  ✗ FALHA: Erro de sintaxe em JavaScript inline detectado:")
        for err in js_errors:
            print(f"    • {err}")
        return False

    if verbose:
        print("  ✓ 100% das tags <template> balanceadas e scripts inline com sintaxe válida.")
    return True


if __name__ == "__main__":
    success = run_client_syntax_audit(verbose=True)
    sys.exit(0 if success else 1)
