"""
Script para sincronizar os Preços Oficiais de Tabela (DE R$) do catálogo de produtos com o Outlet,
permitindo que o percentual OFF seja calculado estritamente entre o Preço DE e o Preço POR real.
"""

from __future__ import annotations

from database import db
from services.outlet_service import run_exec


def sync_real_de_prices():
    print("🔄 Sincronizando Preços de Tabela (DE R$) e recalculando percentuais de desconto (% OFF)...")
    with db() as conn:
        out_rows = run_exec(conn, "SELECT id, name, price_original, price_outlet FROM outlet_items").fetchall()
        prod_rows = run_exec(conn, "SELECT name, retail_price FROM products").fetchall()
        
        prods = [dict(p) for p in prod_rows]
        updated_count = 0

        for r in out_rows:
            d = dict(r)
            item_id = d["id"]
            name = d["name"]
            p_out = float(d["price_outlet"] or 0)
            p_orig = float(d["price_original"] or 0)

            # Tentar dar match com a tabela de produtos oficiais
            match_p = None
            for p in prods:
                p_name = p["name"].lower().strip()
                item_name = name.lower().strip()
                if p_name in item_name or item_name in p_name:
                    match_p = p
                    break

            real_de = p_orig
            if match_p and match_p.get("retail_price"):
                v = float(match_p["retail_price"])
                if v > p_out:
                    real_de = v

            # Recalcular desconto real
            disc = 0
            if real_de > p_out and real_de > 0:
                disc = int(round(((real_de - p_out) / real_de) * 100))

            run_exec(
                conn,
                "UPDATE outlet_items SET price_original = ?, discount_percent = ? WHERE id = ?",
                (real_de, disc, item_id)
            )
            updated_count += 1
            print(f"  ✓ {name:<16}: DE R$ {real_de:>9,.2f} | POR R$ {p_out:>9,.2f} ➔ -{disc}% OFF")

        conn.commit()
    print(f"\n✅ Sincronização concluída! {updated_count} produtos atualizados com os descontos reais do DE/POR.")


if __name__ == "__main__":
    sync_real_de_prices()
