"""
M-One Copilot Operational Context Builder (services/copilot_context.py)
Coleta métricas e dados operacionais reais das tabelas oficiais do M-One
para enriquecer os prompts do assistente Copilot com segurança e controle de permissões.
"""

from __future__ import annotations

from datetime import date, datetime


def build_operational_context(db_conn, role: str, name: str) -> str:
    """Coleta métricas e dados operacionais reais das tabelas oficiais do M-One."""
    lines: list[str] = []
    today = date.today().isoformat()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    lines.append(f"DATA E HORA DO SISTEMA: {now_str}")
    lines.append(f"USUÁRIO ATUAL: {name} (Perfil de acesso: {role})")

    try:
        # 1. Estoque por Produto e Chassis
        stock_summary = db_conn.execute("""
            SELECT p.name as product_name,
                   COUNT(CASE WHEN st.status = 'available' THEN 1 END) as available,
                   COUNT(CASE WHEN st.status = 'sold' THEN 1 END) as sold,
                   COUNT(CASE WHEN st.status = 'unreleased' THEN 1 END) as unreleased,
                   COUNT(st.id) as total_units
            FROM products p
            LEFT JOIN stock_units st ON st.product_id = p.id
            GROUP BY p.id, p.name
            HAVING COUNT(st.id) > 0
            ORDER BY available DESC, product_name ASC
        """).fetchall()

        lines.append("\n=== ESTOQUE POR MODELO / PRODUTO ===")
        total_disp = 0
        total_vend = 0
        total_unrel = 0
        for s in stock_summary:
            disp = s["available"] or 0
            vend = s["sold"] or 0
            unrel = s["unreleased"] or 0
            total_disp += disp
            total_vend += vend
            total_unrel += unrel
            lines.append(f"- {s['product_name']}: {disp} liberados para venda, {vend} vendidos, {unrel} em importação aguardando liberação.")
        lines.append(f"TOTAL GERAL DO ESTOQUE: {total_disp} chassis liberados para venda imediata, {total_vend} vendidos, {total_unrel} aguardando liberação.")

        # 2. Produtos e Tabela de Preços Atuais
        products = db_conn.execute("""
            SELECT name, category, unit_cost, wholesale_price, retail_price
            FROM products
            ORDER BY name
        """).fetchall()
        lines.append("\n=== TABELA DE PRODUTOS E PREÇOS VIGENTES ===")
        for p in products:
            p_ret = f"R$ {float(p['retail_price']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if p.get("retail_price") else "N/D"
            p_who = f"R$ {float(p['wholesale_price']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if p.get("wholesale_price") else "N/D"
            lines.append(f"- {p['name']} ({p.get('category') or 'Sem categoria'}): Varejo {p_ret} | Atacado {p_who}")

        # 3. Vendas Realizadas (Hoje e Mês Atual)
        month_start = today[:7] + "-01"
        sales_today = db_conn.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total_value), 0) as total
            FROM sales
            WHERE sold_at = %s
        """, (today,)).fetchone()

        sales_month = db_conn.execute("""
            SELECT COUNT(*) as qtd, COALESCE(SUM(total_value), 0) as total
            FROM sales
            WHERE sold_at >= %s
        """, (month_start,)).fetchone()

        lines.append("\n=== DESEMPENHO DE VENDAS ===")
        tot_today = f"R$ {float(sales_today['total']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        tot_month = f"R$ {float(sales_month['total']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lines.append(f"- Hoje ({today}): {sales_today['qtd']} venda(s), Total: {tot_today}")
        lines.append(f"- Mês atual (desde {month_start}): {sales_month['qtd']} venda(s), Total: {tot_month}")

        # 5 vendas mais recentes
        recent_sales = db_conn.execute("""
            SELECT s.sold_at, s.customer, s.invoice_number, s.total_value, s.channel, u.name as seller
            FROM sales s
            LEFT JOIN users u ON u.id = s.created_by
            ORDER BY s.id DESC
            LIMIT 5
        """).fetchall()
        if recent_sales:
            lines.append("- Últimas vendas cadastradas:")
            for rs in recent_sales:
                val = f"R$ {float(rs['total_value']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                lines.append(f"  • Data: {rs['sold_at']} | NF: {rs['invoice_number']} | Cliente: {rs.get('customer') or 'Consumidor'} | Canal: {rs['channel']} | Valor: {val} | Vendedor: {rs['seller'] or 'N/D'}")

        # 4. Importações e Custos (Restrito a Diretoria e Suporte Técnico)
        if role in ["admin", "support"]:
            imports = db_conn.execute("""
                SELECT i.id, i.reference, i.invoice_no, i.bl_no, i.arrival_date, i.usd_rate, i.status,
                       COUNT(st.id) as chassis_total,
                       COALESCE(SUM(ic.amount * CASE WHEN ic.currency='USD' THEN COALESCE(NULLIF(ic.usd_rate,0), NULLIF(i.usd_rate,0), 1) ELSE 1 END), 0) as costs_brl
                FROM imports i
                LEFT JOIN stock_units st ON st.import_id = i.id
                LEFT JOIN import_costs ic ON ic.import_id = i.id
                GROUP BY i.id, i.reference, i.invoice_no, i.bl_no, i.arrival_date, i.usd_rate, i.status
                ORDER BY i.id DESC
                LIMIT 5
            """).fetchall()
            lines.append("\n=== IMPORTAÇÕES RECENTES (CONFIDENCIAL: DIRETORIA/SUPORTE) ===")
            for imp in imports:
                c_brl = f"R$ {float(imp['costs_brl']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                status_desc = "Estoque liberado" if imp["status"] == "released" else "Rascunho / Aguardando liberação"
                lines.append(f"- Importação #{imp['id']} ({imp['reference']}): Chegada {imp['arrival_date'] or 'N/D'} | Invoice {imp['invoice_no'] or 'N/D'} | BL {imp['bl_no'] or 'N/D'} | Câmbio USD R$ {float(imp['usd_rate'] or 0):.4f} | Status: {status_desc} | Chassis: {imp['chassis_total']} un | Custos apurados: {c_brl}")
        else:
            lines.append("\n[IMPORTAÇÕES: Acesso restrito. Custos de compra e despesas aduaneiras são estritamente confidenciais da Diretoria.]")

    except Exception as e:
        lines.append(f"\n[Nota de leitura do banco: {str(e)}]")

    return "\n".join(lines)
