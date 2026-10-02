"""
Script para zerar o campo location de todos os itens do Outlet no banco de dados.
"""

from __future__ import annotations
from database import db

def clear_locations():
    with db() as conn:
        is_pg = hasattr(conn, "conn") or type(conn).__name__ == "PGConnWrapper"
        sql = "UPDATE outlet_items SET location = ''"
        conn.execute(sql)
        conn.commit()
        cnt_row = conn.execute("SELECT count(*) as count FROM outlet_items").fetchone()
        c = cnt_row["count"] if isinstance(cnt_row, dict) else cnt_row[0]
        print(f"✅ Campo location zerado com sucesso em todos os {c} produtos do Outlet.")

if __name__ == "__main__":
    clear_locations()
