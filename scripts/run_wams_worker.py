#!/usr/bin/env python3
"""
M-One WhatsApp Automation Engine Worker CLI (scripts/run_wams_worker.py)
Executa o processamento assíncrono de WAMs pendentes (inbound/outbound) e delays/timeouts agendados.

Uso:
  python3 scripts/run_wams_worker.py
  python3 scripts/run_wams_worker.py --loop --interval 5
  python3 scripts/run_wams_worker.py --worker-id worker_01
"""

import argparse
import os
import signal
import sys
import time

# Adiciona diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.automation.workers import (
    process_delays_worker,
    process_pending_wams_worker,
)

running = True

def handle_signal(sig, frame):
    global running
    print("\n[WAMS Worker CLI] Sinal de interrupção recebido. Encerrando worker...")
    running = False

def main():
    parser = argparse.ArgumentParser(description="M-One WAMS Worker CLI")
    parser.add_argument("--loop", action="store_true", help="Executa o worker em loop contínuo")
    parser.add_argument("--interval", type=int, default=5, help="Intervalo em segundos entre ciclos no modo loop (default: 5s)")
    parser.add_argument("--worker-id", type=str, default="wams_cli_worker", help="Identificador único deste worker (default: wams_cli_worker)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"[WAMS Worker CLI] Worker '{args.worker_id}' iniciado.")
    print(f"[WAMS Worker CLI] Modo: {'Loop (intervalo=' + str(args.interval) + 's)' if args.loop else 'One-shot'}")

    cycle = 0
    while running:
        cycle += 1
        now_ts = int(time.time())
        print(f"\n--- Ciclo #{cycle} [{time.strftime('%Y-%m-%d %H:%M:%S')}] ---")

        try:
            # 1. Processar WAMs pendentes
            wam_results = process_pending_wams_worker(worker_id=args.worker_id, now_ts=now_ts)
            print(f"[WAM Worker] WAMs processados neste ciclo: {len(wam_results)}")
            for item in wam_results:
                print(f"  - WAM {item.get('wam_id')}: status={item.get('result', {}).get('status')}")

            # 2. Processar Delays/Timeouts agendados
            delay_results = process_delays_worker(worker_id=args.worker_id, now_ts=now_ts)
            print(f"[Delay Worker] Sessões agendadas processadas: {len(delay_results)}")
            for item in delay_results:
                print(f"  - Sessão #{item.get('session_id')}: status={item.get('result', {}).get('status')}")

        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as ex:
            print(f"[WAMS Worker CLI Error] Erro ao executar ciclo #{cycle}: {ex!s}")

        if not args.loop or not running:
            break

        time.sleep(args.interval)

    print(f"[WAMS Worker CLI] Worker '{args.worker_id}' encerrado com sucesso.")

if __name__ == "__main__":
    main()
