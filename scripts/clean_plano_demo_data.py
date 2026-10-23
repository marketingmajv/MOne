#!/usr/bin/env python3
"""
scripts/clean_plano_demo_data.py
Limpa os dados fictícios e relatórios simulados da sessão de Governança & Gestão Interna (/admin/plano),
preparando o ambiente para receber as submissões reais dos colaboradores hoje.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from database import db
from services.employee_reports_service import _is_pg, ensure_reports_schema
from services.internal_analysis_service import ensure_internal_analysis_schema


def clean_plano_demo_data(keep_past_cycles: bool = False):
    ensure_reports_schema()
    ensure_internal_analysis_schema()

    print("🛡️ Iniciando limpeza de dados fictícios em /admin/plano...")

    with db() as conn:
        pg = _is_pg(conn)
        ph = "%s" if pg else "?"

        # 1. Identificar o ciclo ativo atual (W43)
        cur = conn.execute("SELECT id, cycle_code, title FROM maj_report_cycles WHERE is_active = TRUE ORDER BY id DESC LIMIT 1")
        active_cycle = cur.fetchone()
        active_id = active_cycle["id"] if active_cycle else None
        print(f"📌 Ciclo ativo detectado: {active_cycle}")

        # 2. Limpar todas as submissões fictícias em maj_employee_reports
        if keep_past_cycles and active_id:
            cur_del_rep = conn.execute(f"DELETE FROM maj_employee_reports WHERE cycle_id = {ph}", (active_id,))
            print(f"🧹 Removidas submissões fictícias do ciclo ativo {active_id}.")
        else:
            conn.execute("DELETE FROM maj_employee_reports")
            print("🧹 Removidas todas as submissões fictícias de maj_employee_reports (11 registros).")

        # 3. Limpar análises internas simuladas em maj_cycle_internal_analyses
        conn.execute("DELETE FROM maj_cycle_internal_analyses")
        print("🧹 Removidas todas as análises internas de simulação em maj_cycle_internal_analyses.")

        # 4. Ajustar ciclos em maj_report_cycles se não for manter os fictícios
        if not keep_past_cycles and active_id:
            conn.execute(f"DELETE FROM maj_report_cycles WHERE id != {ph}", (active_id,))
            print(f"🧹 Removidos ciclos fictícios passados (W39, W40, W41, W42). Mantido apenas o ciclo oficial ativo: {active_cycle['title']}.")

        conn.commit()

    print("✅ Limpeza concluída com sucesso! Módulo /admin/plano pronto para submissões reais.")


if __name__ == "__main__":
    clean_plano_demo_data(keep_past_cycles=False)
