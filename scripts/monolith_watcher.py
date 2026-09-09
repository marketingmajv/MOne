#!/usr/bin/env python3
"""
M-One Anti-Monolith Watcher (scripts/monolith_watcher.py)
Monitora arquivos Python, HTML e JS do projeto M-One contra crescimento descontrolado.
Emite alertas coloridos no terminal e notificações nativas no macOS via osascript.

Uso:
  python3 scripts/monolith_watcher.py          # Executa varredura e fica observando alterações
  python3 scripts/monolith_watcher.py --scan   # Executa varredura única (auditoria) e sai
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

LINE_LIMIT = 500
BASE_DIR = Path(__file__).resolve().parent.parent

# Diretórios e extensões monitoradas
WATCH_PATTERNS = [
    ("app.py",),
    ("database.py",),
    ("routes", "*.py"),
    ("templates", "*.html"),
    ("static/js", "*.js"),
]


def notify_macos(title: str, message: str):
    """Envia notificação nativa para o macOS com som de alerta."""
    try:
        script = f'display notification "{message}" with title "{title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def count_lines(filepath: Path) -> int:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def collect_target_files() -> list[Path]:
    files = []
    # Arquivos raiz
    for root_file in ["app.py", "database.py"]:
        p = BASE_DIR / root_file
        if p.is_file():
            files.append(p)

    # Diretórios
    for folder, pattern in [("routes", "*.py"), ("templates", "*.html"), ("static/js", "*.js")]:
        d = BASE_DIR / folder
        if d.is_dir():
            files.extend(d.glob(pattern))

    return sorted(set(files))


def check_file(filepath: Path, silent_if_ok: bool = True) -> bool:
    lines = count_lines(filepath)
    rel_path = filepath.relative_to(BASE_DIR)

    if lines > LINE_LIMIT:
        print(f"\n\033[41m\033[37m ⚠️  ALERTA DE MONÓLITO M-ONE ⚠️  \033[0m")
        print(f"\033[31mO arquivo \033[1m{rel_path}\033[0m\033[31m ultrapassou o limite estabelecido!\033[0m")
        print(f"Linhas atuais: \033[1m{lines}\033[0m / Limite: {LINE_LIMIT}")
        print(f"\033[33mRecomendação: Ativar skill de Refatoração Proativa para modularizar em Blueprints.\033[0m\n")

        notify_macos(
            "⚠️ M-One: Alerta de Monólito!",
            f"O arquivo {filepath.name} atingiu {lines} linhas. Considere modularizar.",
        )
        return False
    else:
        if not silent_if_ok:
            print(f"  ✓ {rel_path}: {lines} linhas (dentro do limite)")
        return True


def run_audit():
    print(f"\033[36m[Anti-Monolith Watcher]\033[0m Varrendo arquivos do projeto (limite: {LINE_LIMIT} linhas)...")
    files = collect_target_files()
    violators = 0

    for f in files:
        if not check_file(f, silent_if_ok=False):
            violators += 1

    print("\n" + "=" * 50)
    if violators == 0:
        print("\033[32m✅ Nenhum monólito crítico encontrado!\033[0m")
    else:
        print(f"\033[33m⚠️  Total de arquivos acima de {LINE_LIMIT} linhas: {violators}\033[0m")
    print("=" * 50 + "\n")


def watch_loop():
    print(f"\033[36m[Anti-Monolith Watcher]\033[0m Observando alterações em tempo real (Ctrl+C para sair)...")
    mtimes: dict[Path, float] = {}

    for f in collect_target_files():
        try:
            mtimes[f] = f.stat().st_mtime
        except OSError:
            pass

    while True:
        try:
            time.sleep(2)
            current_files = collect_target_files()
            for f in current_files:
                try:
                    current_mtime = f.stat().st_mtime
                    last_mtime = mtimes.get(f)
                    if last_mtime is None or current_mtime > last_mtime:
                        mtimes[f] = current_mtime
                        check_file(f, silent_if_ok=True)
                except OSError:
                    pass
        except KeyboardInterrupt:
            print("\n[Anti-Monolith Watcher] Encerrado.")
            break


def main():
    parser = argparse.ArgumentParser(description="M-One Anti-Monolith Watcher")
    parser.add_argument("--scan", action="store_true", help="Executa varredura única e finaliza")
    args = parser.parse_args()

    run_audit()
    if not args.scan:
        watch_loop()


if __name__ == "__main__":
    main()
