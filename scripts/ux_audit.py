#!/usr/bin/env python3
"""
M-One Automated UX & UI Integrity Auditor (scripts/ux_audit.py)
Varre templates HTML/Jinja2 e componentes de interface para garantir:
1. Centralização e isolamento correto de Modais (evita deslocamento lateral / CSS containment trap dentro do .app-shell).
2. Consistência e contraste do esquema de cores (sem inputs brancos estourados em tema escuro).
3. Legibilidade de tipografia (sem texto escuro sobre fundo escuro).
4. Ergonomia e classes padrão M-One (form-input, modal, modal-card).
5. Alinhamento e centralização milimétrica do botão 'X' de fechar modal (sem padding assimétrico de .btn sm).
Em estrita conformidade com a política anti-monólito (< 500 linhas).
"""

import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Cores do terminal
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

# Fundos vibrantes/claros onde texto preto (#000) é intencional e correto
LIGHT_BG_PATTERNS = [
    "background: #e5a93b",
    "background: #00cc88",
    "background: #00e599",
    "background: #10b981",
    "background: #25d366",
    "background: #f59e0b",
    "background: #fbbf24",
    "background: var(--accent)",
    "background: var(--primary)",
    "btn primary",
]


def scan_modals(content: str, rel_path: str):
    """Verifica se os modais no app-shell estão isolados via x-teleport='body'."""
    critical_errors = []
    warnings = []
    lines = content.splitlines()

    is_app_page = '{% extends "base.html" %}' in content or "{% extends 'base.html' %}" in content

    for idx, line in enumerate(lines, 1):
        # 1. Detecta modais Alpine em páginas com base.html / app-shell
        if is_app_page and re.search(r'x-show\s*=\s*["\'].*modal.*["\']', line, re.IGNORECASE):
            # Olhar as 12 linhas anteriores em busca do x-teleport
            start_window = max(0, idx - 12)
            preceding_context = "\n".join(lines[start_window:idx])
            if "x-teleport=\"body\"" not in preceding_context and "x-teleport='body'" not in preceding_context:
                critical_errors.append({
                    "file": rel_path,
                    "line": idx,
                    "type": "MODAL_CONTAINMENT_TRAP",
                    "message": "Modal com Alpine.js dentro do layout .app-shell sem <template x-teleport=\"body\">. Causa deslocamento lateral para o canto esquerdo da tela.",
                    "snippet": line.strip()
                })

        # 2. Avisos de classes legadas
        if "modal-backdrop" in line and "modal-card" not in line and not line.strip().startswith("/*") and not line.strip().startswith("."):
            warnings.append({
                "file": rel_path,
                "line": idx,
                "type": "LEGACY_MODAL_CLASS",
                "message": "Modal utilizando classe legada '.modal-backdrop'. Recomenda-se migrar para .modal e .modal-card do M-One.",
                "snippet": line.strip()
            })

    return critical_errors, warnings


def scan_color_palette(content: str, rel_path: str):
    """Detecta cores hardcoded colidentes e inputs com fundo branco em temas escuros."""
    critical_errors = []
    warnings = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, 1):
        # 1. Detectar inputs ou selects com background branco hardcoded colidindo com tema escuro
        if re.search(r'<(input|select|textarea)[^>]+style\s*=\s*["\'][^"\']*(background\s*:\s*(#fff|#ffffff|white))', line, re.IGNORECASE):
            critical_errors.append({
                "file": rel_path,
                "line": idx,
                "type": "HARSH_WHITE_INPUT",
                "message": "Input com fundo branco hardcoded em tema escuro. Use 'class=\"form-input\"' ou 'background: var(--panel2)'.",
                "snippet": line.strip()
            })

        # 2. Detectar textos escuros com hardcoded black sem fundo claro garantido
        if re.search(r'style\s*=\s*["\'][^"\']*(color\s*:\s*(#000|#000000|black|#0f172a|#1e1e24|#111))', line, re.IGNORECASE):
            has_light_bg = any(pat in line for pat in LIGHT_BG_PATTERNS)
            if not has_light_bg:
                warnings.append({
                    "file": rel_path,
                    "line": idx,
                    "type": "ILLEGIBLE_DARK_TEXT",
                    "message": "Texto com cor preta/escura hardcoded sem fundo claro contrastante. Risco de invisibilidade.",
                    "snippet": line.strip()
                })

        # 3. Detectar 'form-control' do Bootstrap não mapeado no sistema de design do M-One
        if "class=\"form-control\"" in line or "class='form-control'" in line:
            if "outlet/catalog.html" not in rel_path and "privacy_policy.html" not in rel_path:
                warnings.append({
                    "file": rel_path,
                    "line": idx,
                    "type": "UNMAPPED_FORM_CONTROL",
                    "message": "Uso de classe 'form-control'. No M-One, utilize 'form-input' para herdar ergonomia de var(--panel2).",
                    "snippet": line.strip()
                })

    return critical_errors, warnings


def scan_button_redundancies(content: str, rel_path: str):
    """Detecta redundâncias em botões como ícone SVG de '+' seguido de texto que já começa com '+'."""
    critical_errors = []
    warnings = []

    btn_pattern = re.compile(
        r'(<button\b[^>]*>[\s\S]*?</button>|<a\b[^>]*class=["\'][^"\']*\bbtn\b[^"\']*["\'][^>]*>[\s\S]*?</a>)',
        re.IGNORECASE
    )

    for match in btn_pattern.finditer(content):
        btn_html = match.group(0)
        line_num = content[:match.start()].count("\n") + 1

        # Caso 1: Botão tem SVG e texto de span/link começa com '+' gerando '+ +' visual
        if "<svg" in btn_html:
            after_svg = btn_html.split("</svg>", 1)[-1]
            if re.search(r'>\s*(\+|\+|➕)\s*[A-Za-z0-9]', after_svg):
                critical_errors.append({
                    "file": rel_path,
                    "line": line_num,
                    "type": "DUPLICATE_BUTTON_ICON_TEXT",
                    "message": "Ícone SVG de adição (+) duplicado com símbolo '+' no texto do botão (renderiza visualmente como '+ +'). Remova o '+' do texto.",
                    "snippet": " ".join(btn_html.split())[:110]
                })

        # Caso 2: Texto literal contendo '+ +' ou '++'
        if re.search(r'\+\s*\+\s*[A-Za-z]', btn_html):
            critical_errors.append({
                "file": rel_path,
                "line": line_num,
                "type": "DUPLICATE_PLUS_SIGN",
                "message": "Sinal de adição duplicado (++ ou + +) encontrado no texto do botão.",
                "snippet": " ".join(btn_html.split())[:110]
            })

    return critical_errors, warnings


def scan_modal_close_buttons(content: str, rel_path: str):
    """
    Audita botões de fechar modal (close button 'X').
    Garante alinhamento milimétrico e centralização perfeita:
    1. Bloqueia classes com padding assimétrico (.btn, .btn.sm, .btn.small) em botões de fechar com 'X'.
    2. Bloqueia inline styles com padding não-nulo (ex: padding: 4px 10px, padding: 4px 8px) que empurram o 'X' para o canto.
    3. Alerta sobre o uso de caracteres tipográficos crus (&times;, ×, ✕, x) que sofrem distorção de baseline em fontes web.
    4. Recomenda/valida o uso da classe padronizada '.modal-close-btn' com SVG geométrico (<svg viewBox="0 0 24 24">).
    """
    critical_errors = []
    warnings = []

    # Procura blocos <button> que fecham modais ou estão dentro de .modal-head
    btn_pattern = re.compile(
        r'<button\b([^>]*)>([\s\S]*?)</button>',
        re.IGNORECASE
    )

    for match in btn_pattern.finditer(content):
        attrs = match.group(1)
        inner = match.group(2).strip()
        line_num = content[:match.start()].count("\n") + 1

        # Identifica se é um botão de fechar modal com ícone/X (e não um botão de texto como "Cancelar")
        is_modal_closer = any(k in attrs for k in ["closeModal", "modalOpen = false", "showModal = false", "closeOutletModal", "closeAtacadoModal", "closeSettlementModal", "modal-close-btn"])
        is_in_modal_head = False
        if not is_modal_closer:
            # Checar se as 6 linhas anteriores contêm modal-head
            start_window = max(0, match.start() - 300)
            if "modal-head" in content[start_window:match.start()]:
                is_in_modal_head = True

        if not (is_modal_closer or is_in_modal_head):
            continue

        # Ignorar botões normais de rodapé com texto longo (ex: Cancelar, Salvar, Fechar)
        clean_text = re.sub(r'<[^>]+>', '', inner).strip()
        if len(clean_text) > 4 and any(w in clean_text.lower() for w in ["cancelar", "salvar", "confirmar", "voltar", "fechar"]):
            continue

        # 1. Erro Crítico: Uso de classes que injetam padding retangular (.btn, .btn sm, etc.)
        if re.search(r'class\s*=\s*["\'][^"\']*\bbtn\b(?!\s*primary|\s*secondary|\s*danger)[^"\']*["\']', attrs):
            if "modal-close-btn" not in attrs:
                critical_errors.append({
                    "file": rel_path,
                    "line": line_num,
                    "type": "UNALIGNED_MODAL_CLOSE_BUTTON",
                    "message": "Botão de fechar modal utilizando classe com padding assimétrico (.btn / .btn sm). Isso empurra o 'X' para o canto inferior direito. Use 'class=\"modal-close-btn\"' com SVG geométrico.",
                    "snippet": match.group(0)[:110]
                })

        # 2. Erro Crítico: Padding inline não-nulo
        pad_match = re.search(r'padding\s*:\s*([^;"]+)', attrs)
        if pad_match:
            pad_val = pad_match.group(1).strip()
            if pad_val not in ["0", "0px", "0 !important", "0px !important"]:
                critical_errors.append({
                    "file": rel_path,
                    "line": line_num,
                    "type": "UNALIGNED_MODAL_CLOSE_BUTTON",
                    "message": f"Botão de fechar modal com padding inline assimétrico ('padding: {pad_val}'). Use 'padding: 0;' e display flex centralizado.",
                    "snippet": match.group(0)[:110]
                })

        # 3. Aviso: Caractere tipográfico cru (&times;, ×, ✕, x) em vez de SVG geométrico
        has_svg = "<svg" in inner
        has_glyph = any(g in inner for g in ["&times;", "&#215;", "×", "✕"]) or clean_text.lower() == "x"
        if has_glyph and not has_svg:
            warnings.append({
                "file": rel_path,
                "line": line_num,
                "type": "TYPOGRAPHIC_MODAL_CLOSE_GLYPH",
                "message": "Botão de fechar modal utilizando caractere de fonte (&times;/×/x). Caracteres tipográficos sofrem distorção de baseline. Recomenda-se SVG geométrico (<svg viewBox='0 0 24 24'><line x1='18' y1='6' x2='6' y2='18'/><line x1='6' y1='6' x2='18' y2='18'/></svg>) para alinhamento sub-pixel perfeito.",
                "snippet": match.group(0)[:110]
            })

    return critical_errors, warnings


def scan_route_context():
    """Detecta se alguma rota sobrescreve 'me' indevidamente, ocultando o menu lateral (sidebar)."""
    critical_errors = []
    routes_dir = BASE_DIR / "routes"
    for root, _, files in os.walk(routes_dir):
        for file in files:
            if file.endswith(".py"):
                fp = Path(root) / file
                rel_path = str(fp.relative_to(BASE_DIR))
                with open(fp, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for idx, line in enumerate(lines, 1):
                    if re.search(r'\bme\s*=\s*(session\.get\(["\']user["\']\)|{})', line):
                        critical_errors.append({
                            "file": rel_path,
                            "line": idx,
                            "type": "SIDEBAR_CONTEXT_STRIP",
                            "message": "Sobrescrita de 'me' com chave incorreta ou vazia. Isso remove permissões e oculta a sidebar. Use current_user().",
                            "snippet": line.strip()
                        })
    return critical_errors


def run_ux_audit() -> bool:
    """Executa a auditoria em todos os templates e rotas do projeto."""
    print(f"\n{BOLD}{CYAN}🎨 [UX/UI Integrity Auditor] Iniciando varredura de Modais, Alinhamentos, Cores, Botões e Sidebar...{RESET}")

    total_templates = 0
    all_critical = []
    all_warnings = []

    # 1. Auditoria de integridade de contexto da Sidebar
    all_critical.extend(scan_route_context())

    for root, _, files in os.walk(TEMPLATES_DIR):
        for file in files:
            if file.endswith(".html"):
                total_templates += 1
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(BASE_DIR))

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    modal_crit, modal_warn = scan_modals(content, rel_path)
                    color_crit, color_warn = scan_color_palette(content, rel_path)
                    btn_crit, btn_warn = scan_button_redundancies(content, rel_path)
                    close_crit, close_warn = scan_modal_close_buttons(content, rel_path)

                    all_critical.extend(modal_crit)
                    all_critical.extend(color_crit)
                    all_critical.extend(btn_crit)
                    all_critical.extend(close_crit)
                    all_warnings.extend(modal_warn)
                    all_warnings.extend(color_warn)
                    all_warnings.extend(btn_warn)
                    all_warnings.extend(close_warn)
                except Exception as e:
                    print(f"  {YELLOW}Aviso ao ler {rel_path}: {e}{RESET}")

    print(f"  Auditados {BOLD}{total_templates}{RESET} templates HTML/Jinja2.")

    if all_warnings:
        print(f"\n{YELLOW}⚠️  {len(all_warnings)} aviso(s) de ergonomia não-bloqueantes detectados:{RESET}")
        for warn in all_warnings[:5]:
            print(f"  • {warn['file']}:{warn['line']} [{warn['type']}]: {warn['message']}")
        if len(all_warnings) > 5:
            print(f"  ... e mais {len(all_warnings) - 5} avisos em templates legados.")

    if not all_critical:
        print(f"\n{BOLD}{GREEN}✅ AUDITORIA DE UX APROVADA: Zero problemas críticos de alinhamento ou contraste!{RESET}\n")
        return True

    print(f"\n{BOLD}{RED}❌ FORAM ENCONTRADOS {len(all_critical)} ERRO(S) CRÍTICOS DE UX/UI (DEPLOY BLOQUEADO):{RESET}")
    for issue in all_critical:
        print(f"\n  • {BOLD}{issue['file']}:{issue['line']}{RESET} [{RED}{issue['type']}{RESET}]")
        print(f"    {issue['message']}")
        print(f"    Código: {issue['snippet'][:100]}...")

    return False


if __name__ == "__main__":
    success = run_ux_audit()
    sys.exit(0 if success else 1)
