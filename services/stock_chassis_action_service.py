"""
M-One Stock Chassis Action Service (services/stock_chassis_action_service.py)
Operações transacionais por chassi: busca rápida/bipagem, marcação como Montado,
Separação para Venda (com Nº Pedido) e Baixa/Faturamento integrada a Vendas (sales).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from database import db
from services.stock_sync_service import ensure_stock_audit_schema


def search_chassis_candidates(q: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Busca rápida por chassi, modelo ou motor para dropdown suspenso e bipagem."""
    ensure_stock_audit_schema()
    term = (q or "").strip()
    if not term:
        return []
    like_term = f"%{term}%"
    exact_term = term.upper()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT st.id, st.chassis, st.color, st.motor_no, st.status, st.location,
                   st.separated_order_number, p.name AS product_name
            FROM stock_units st
            JOIN products p ON p.id = st.product_id
            WHERE st.chassis ILIKE %s OR st.motor_no ILIKE %s OR p.name ILIKE %s
            ORDER BY CASE WHEN UPPER(TRIM(st.chassis)) = %s THEN 0 ELSE 1 END, st.created_at DESC
            LIMIT %s
            """,
            (like_term, like_term, like_term, exact_term, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_chassis_assembled(chassis_raw: str, user_id: Optional[int]) -> Dict[str, Any]:
    """Marca um chassi como Montado (Exposição/Loja) com 1 clique."""
    ensure_stock_audit_schema()
    chassis = (chassis_raw or "").strip().upper()
    if not chassis:
        return {"ok": False, "error": "Chassi obrigatório."}

    with db() as conn:
        unit = conn.execute(
            "SELECT id, status FROM stock_units WHERE UPPER(TRIM(chassis)) = %s",
            (chassis,),
        ).fetchone()
        if not unit:
            return {"ok": False, "error": "Chassi não encontrado."}
        if unit["status"] == "sold":
            return {"ok": False, "error": "Chassi já consta como vendido e não pode ser marcado como montado."}

        conn.execute(
            "UPDATE stock_units SET status = 'assembled', last_audited_by = %s WHERE id = %s",
            (user_id, unit["id"]),
        )
        conn.commit()
    return {"ok": True, "chassis": chassis, "status": "assembled"}


def separate_chassis_for_sale(
    chassis_raw: str, order_number: str, user_id: Optional[int]
) -> Dict[str, Any]:
    """Marca um chassi como 'Separado para Venda' vinculado ao Nº do Pedido."""
    ensure_stock_audit_schema()
    chassis = (chassis_raw or "").strip().upper()
    order_no = (order_number or "").strip()
    if not chassis or not order_no:
        return {"ok": False, "error": "Chassi e Nº do Pedido são obrigatórios para separar."}

    with db() as conn:
        unit = conn.execute(
            """
            SELECT st.id, st.status, p.name AS product_name
            FROM stock_units st
            JOIN products p ON p.id = st.product_id
            WHERE UPPER(TRIM(st.chassis)) = %s
            """,
            (chassis,),
        ).fetchone()
        if not unit:
            return {"ok": False, "error": "Chassi não encontrado na base."}
        if unit["status"] == "sold":
            return {"ok": False, "error": "Este chassi já foi faturado/vendido."}

        conn.execute(
            """
            UPDATE stock_units
            SET status = 'separated',
                separated_order_number = %s,
                separated_at = CURRENT_TIMESTAMP,
                separated_by = %s
            WHERE id = %s
            """,
            (order_no, user_id, unit["id"]),
        )
        conn.commit()

    return {
        "ok": True,
        "chassis": chassis,
        "status": "separated",
        "order_number": order_no,
        "product_name": unit["product_name"],
    }


def checkout_chassis_sale(data: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
    """
    Baixa de Venda por Chassi (Fluxo Marisa - Financeiro/Vendas):
    Cria o registro na tabela 'sales' (incluindo NF Transferência 1 e 2)
    e baixa o chassi em 'stock_units' como 'sold'.
    """
    ensure_stock_audit_schema()
    chassis = (data.get("chassis") or "").strip().upper()
    invoice_number = (data.get("invoice_number") or "").strip()
    transfer_nf_1 = (data.get("transfer_nf_1") or "").strip()
    transfer_nf_2 = (data.get("transfer_nf_2") or "").strip()
    customer = (data.get("customer") or "").strip()
    order_number = (data.get("order_number") or "").strip()
    channel = (data.get("channel") or "Financeiro/Chassi").strip()
    sold_at = (data.get("sold_at") or date.today().isoformat()).strip()

    try:
        raw_val = str(data.get("total_value") or "0").replace("R$", "").strip()
        if "," in raw_val and "." in raw_val:
            raw_val = raw_val.replace(".", "").replace(",", ".")
        elif "," in raw_val:
            raw_val = raw_val.replace(",", ".")
        total_value = float(raw_val or 0)
    except ValueError:
        return {"ok": False, "error": "Valor total da venda inválido."}

    if not chassis or not invoice_number or not customer:
        return {
            "ok": False,
            "error": "Chassi, NF-e de venda e Cliente são obrigatórios para faturar.",
        }

    with db() as conn:
        unit = conn.execute(
            """
            SELECT st.id, st.status, st.separated_order_number, p.name AS product_name
            FROM stock_units st
            JOIN products p ON p.id = st.product_id
            WHERE UPPER(TRIM(st.chassis)) = %s
            """,
            (chassis,),
        ).fetchone()
        if not unit:
            return {"ok": False, "error": f"Chassi {chassis} não encontrado."}
        if unit["status"] == "sold":
            return {"ok": False, "error": f"Chassi {chassis} já consta como vendido."}

        final_order = order_number or unit.get("separated_order_number") or f"NF-{invoice_number}"
        is_pg = type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            sale_row = conn.execute(
                """
                INSERT INTO sales (
                    order_number, invoice_number, transfer_nf_1, transfer_nf_2,
                    channel, customer, sold_at, total_value, vehicle_model, created_by, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    final_order,
                    invoice_number,
                    transfer_nf_1 or None,
                    transfer_nf_2 or None,
                    channel,
                    customer,
                    sold_at,
                    total_value,
                    unit["product_name"],
                    user_id,
                    f"Baixa direta por chassi {chassis}",
                ),
            ).fetchone()
            sale_id = sale_row["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO sales (
                    order_number, invoice_number, transfer_nf_1, transfer_nf_2,
                    channel, customer, sold_at, total_value, vehicle_model, created_by, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    final_order,
                    invoice_number,
                    transfer_nf_1 or None,
                    transfer_nf_2 or None,
                    channel,
                    customer,
                    sold_at,
                    total_value,
                    unit["product_name"],
                    user_id,
                    f"Baixa direta por chassi {chassis}",
                ),
            )
            sale_id = cur.lastrowid

        conn.execute(
            """
            UPDATE stock_units
            SET status = 'sold',
                sale_id = %s,
                sold_at = %s
            WHERE id = %s
            """,
            (sale_id, sold_at, unit["id"]),
        )
        conn.commit()

    return {
        "ok": True,
        "sale_id": sale_id,
        "chassis": chassis,
        "invoice_number": invoice_number,
        "customer": customer,
        "total_value": total_value,
    }
