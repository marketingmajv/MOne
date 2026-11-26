"""
Script de Migração e Correção de Fuso Horário de Relatórios (scripts/fix_reports_timezone.py)
Ajusta os 20 relatórios históricos submetidos no Supabase, convertendo os carimbos
gravados originalmente pelo Render em UTC para o Horário Oficial de Brasília (UTC-3),
e reverte os falsos status de atraso para 'submitted_on_time'.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Adiciona a raiz do projeto ao PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import db


def run_migration():
    print("Iniciando migração de fuso horário dos relatórios para Horário de Brasília (America/Sao_Paulo)...")
    
    with db() as conn:
        cur = conn.execute("""
            SELECT r.id, r.cycle_id, c.cycle_code, c.deadline, r.employee_key, r.employee_name,
                   r.status, r.submitted_at, r.updated_at, r.points_awarded
            FROM maj_employee_reports r
            LEFT JOIN maj_report_cycles c ON r.cycle_id = c.id
            WHERE r.submitted_at IS NOT NULL
            ORDER BY r.id
        """)
        rows = cur.fetchall()
        print(f"Total de relatórios submetidos encontrados: {len(rows)}")
        
        updated_count = 0
        reverted_to_ontime = 0
        
        for row in rows:
            r = dict(row)
            rep_id = r["id"]
            orig_sub = r["submitted_at"]
            orig_up = r.get("updated_at")
            
            # Subtrai 3 horas (de UTC para Brasília)
            corr_sub = orig_sub - timedelta(hours=3)
            corr_up = (orig_up - timedelta(hours=3)) if orig_up else corr_sub
            
            deadline = r.get("deadline")
            # Se for o ciclo piloto 5 (23/10/2026), deadline era 23/10/2026 18:00
            if not deadline and r.get("cycle_id") == 5:
                deadline = datetime(2026, 10, 23, 18, 0, 0)
                
            is_fauzer = (r.get("employee_key") or "").lower().strip() == "fauzer"
            
            if deadline:
                on_time = is_fauzer or (corr_sub <= deadline)
                new_status = "submitted_on_time" if on_time else "submitted_late"
                new_points = 100 if on_time else 50
            else:
                new_status = r["status"]
                new_points = r.get("points_awarded") or 100
                
            if r["status"] == "submitted_late" and new_status == "submitted_on_time":
                reverted_to_ontime += 1
                print(f"  ✓ ID {rep_id:2d} ({r['employee_key']:8s}): Revertido ATRASADO -> NO PRAZO! Submissão Brasília: {corr_sub.strftime('%d/%m/%Y às %H:%M')}")
            else:
                print(f"  • ID {rep_id:2d} ({r['employee_key']:8s}): Submissão Brasília: {corr_sub.strftime('%d/%m/%Y às %H:%M')} (Status: {new_status})")
                
            conn.execute("""
                UPDATE maj_employee_reports
                SET submitted_at = %s,
                    updated_at = %s,
                    status = %s,
                    points_awarded = %s
                WHERE id = %s
            """, (corr_sub, corr_up, new_status, new_points, rep_id))
            updated_count += 1
            
        conn.commit()
        print(f"\nMigração concluída com sucesso!")
        print(f"  • Relatórios com horário ajustado para Brasília: {updated_count}")
        print(f"  • Colaboradores restituídos para 'submitted_on_time': {reverted_to_ontime}")


if __name__ == "__main__":
    run_migration()
