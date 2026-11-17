"""
M-One Stock Audit Service (services/stock_audit_service.py)
Motor de conferência física por bipagem contínua, classificação de divergências
e histórico de auditorias por galpão.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import db
from services.stock_sync_service import ensure_stock_audit_schema


def _get_expected_units(conn, location_scope: str) -> List[Dict[str, Any]]:
    """Retorna unidades fisicamente esperadas na conferência do galpão (available, separated, unreleased)."""
    params: List[Any] = []
    where = ["st.status IN ('available', 'separated', 'unreleased')"]
    if location_scope and location_scope != "Todos":
        where.append("UPPER(TRIM(st.location)) = UPPER(TRIM(%s))")
        params.append(location_scope)

    rows = conn.execute(
        f"""
        SELECT st.id, st.chassis, st.color, st.motor_no, st.status, st.location,
               st.separated_order_number, p.name AS product_name
        FROM stock_units st
        JOIN products p ON p.id = st.product_id
        WHERE {' AND '.join(where)}
        ORDER BY p.name, st.color, st.chassis
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_active_audit() -> Optional[Dict[str, Any]]:
    """Retorna sessão de conferência em andamento, se existir."""
    ensure_stock_audit_schema()
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM stock_audits WHERE status = 'in_progress' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def start_stock_audit(location_scope: str, user_id: Optional[int], user_name: str) -> Dict[str, Any]:
    """Inicia uma nova sessão de conferência física para o galpão selecionado."""
    ensure_stock_audit_schema()
    scope = (location_scope or "Todos").strip()
    with db() as conn:
        expected = _get_expected_units(conn, scope)
        expected_count = len(expected)
        is_pg = type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            row = conn.execute(
                """
                INSERT INTO stock_audits (location_scope, status, started_by, started_by_name, expected_count)
                VALUES (%s, 'in_progress', %s, %s, %s)
                RETURNING *
                """,
                (scope, user_id, user_name, expected_count),
            ).fetchone()
            audit_data = dict(row)
        else:
            cur = conn.execute(
                """
                INSERT INTO stock_audits (location_scope, status, started_by, started_by_name, expected_count)
                VALUES (?, 'in_progress', ?, ?, ?)
                """,
                (scope, user_id, user_name, expected_count),
            )
            audit_data = dict(
                conn.execute("SELECT * FROM stock_audits WHERE id = ?", (cur.lastrowid,)).fetchone()
            )
        conn.commit()
    return audit_data


def scan_chassis_in_audit(audit_id: int, chassis_raw: str, user_id: Optional[int]) -> Dict[str, Any]:
    """
    Processa 1 bipagem na sessão ativa.
    Nunca bloqueia a fila: classifica imediatamente (ok, alert_separated, alert_sold,
    alert_assembled, alert_other_location, unknown) e atualiza last_audited_at.
    """
    ensure_stock_audit_schema()
    chassis = (chassis_raw or "").strip().upper()
    if not chassis:
        return {"ok": False, "error": "Chassi vazio."}

    with db() as conn:
        audit_row = conn.execute("SELECT * FROM stock_audits WHERE id = %s", (audit_id,)).fetchone()
        if not audit_row:
            return {"ok": False, "error": "Sessão de conferência não encontrada."}
        if audit_row["status"] != "in_progress":
            return {"ok": False, "error": "Esta conferência já foi finalizada."}

        # Evitar duplicidade na mesma conferência
        dup = conn.execute(
            "SELECT * FROM stock_audit_items WHERE audit_id = %s AND UPPER(TRIM(chassis)) = %s",
            (audit_id, chassis),
        ).fetchone()
        if dup:
            return {
                "ok": True,
                "duplicate": True,
                "item": dict(dup),
                "message": f"Chassi {chassis} já foi bipado nesta conferência.",
            }

        unit = conn.execute(
            """
            SELECT st.*, p.name AS product_name
            FROM stock_units st
            JOIN products p ON p.id = st.product_id
            WHERE UPPER(TRIM(st.chassis)) = %s
            LIMIT 1
            """,
            (chassis,),
        ).fetchone()

        scope = audit_row["location_scope"] or "Todos"
        if not unit:
            scan_result = "unknown"
            unit_id = None
            unit_status = None
            unit_loc = None
            order_snap = None
            prod_snap = "Não Cadastrado"
            color_snap = None
            msg = f"❓ Chassi {chassis} NÃO encontrado no cadastro!"
        else:
            unit_id = unit["id"]
            unit_status = unit["status"]
            unit_loc = unit["location"]
            order_snap = unit.get("separated_order_number")
            prod_snap = unit["product_name"]
            color_snap = unit["color"]

            if unit_status == "separated":
                scan_result = "alert_separated"
                msg = f"⚠️ ATENÇÃO: {chassis} ({prod_snap}) está SEPARADO PARA VENDA (Pedido #{order_snap or 'S/N'})!"
            elif unit_status == "sold":
                scan_result = "alert_sold"
                msg = f"🔴 DIVERGÊNCIA: {chassis} ({prod_snap}) consta como VENDIDO no sistema!"
            elif unit_status == "assembled":
                scan_result = "alert_assembled"
                msg = f"🛠️ {chassis} ({prod_snap}) constava como MONTADO e foi bipado no estoque."
            elif scope != "Todos" and (unit_loc or "").strip().upper() != scope.strip().upper():
                scan_result = "alert_other_location"
                msg = f"📍 ALERTA LOCAL: {chassis} pertence a '{unit_loc}', mas a conferência é de '{scope}'."
            else:
                scan_result = "ok"
                if unit_status == "unreleased":
                    msg = f"✅ {chassis} • {prod_snap} ({color_snap or 'S/Cor'}) — Liberado para Disponível!"
                else:
                    msg = f"✅ {chassis} • {prod_snap} ({color_snap or 'S/Cor'})"

            if scan_result == "ok" and unit_status == "unreleased":
                conn.execute(
                    "UPDATE stock_units SET status = 'available', last_audited_at = CURRENT_TIMESTAMP, last_audited_by = %s WHERE id = %s",
                    (user_id, unit_id),
                )
            else:
                conn.execute(
                    "UPDATE stock_units SET last_audited_at = CURRENT_TIMESTAMP, last_audited_by = %s WHERE id = %s",
                    (user_id, unit_id),
                )

        is_pg = type(conn).__name__ == "PGConnWrapper"
        if is_pg:
            inserted_item = dict(
                conn.execute(
                    """
                    INSERT INTO stock_audit_items (
                        audit_id, chassis, stock_unit_id, scan_result,
                        unit_status_at_scan, unit_location_at_scan, order_number_snapshot,
                        product_name_snapshot, color_snapshot, scanned_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        audit_id, chassis, unit_id, scan_result,
                        unit_status, unit_loc, order_snap,
                        prod_snap, color_snap, user_id,
                    ),
                ).fetchone()
            )
        else:
            cur = conn.execute(
                """
                INSERT INTO stock_audit_items (
                    audit_id, chassis, stock_unit_id, scan_result,
                    unit_status_at_scan, unit_location_at_scan, order_number_snapshot,
                    product_name_snapshot, color_snapshot, scanned_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id, chassis, unit_id, scan_result,
                    unit_status, unit_loc, order_snap,
                    prod_snap, color_snap, user_id,
                ),
            )
            inserted_item = dict(
                conn.execute("SELECT * FROM stock_audit_items WHERE id = ?", (cur.lastrowid,)).fetchone()
            )

        # Atualizar contadores parciais da sessão
        counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total_scanned,
                SUM(CASE WHEN scan_result <> 'ok' THEN 1 ELSE 0 END) AS total_alerts
            FROM stock_audit_items
            WHERE audit_id = %s
            """,
            (audit_id,),
        ).fetchone()
        conn.execute(
            "UPDATE stock_audits SET scanned_count = %s, alerts_count = %s WHERE id = %s",
            (counts["total_scanned"] or 0, counts["total_alerts"] or 0, audit_id),
        )
        conn.commit()

    return {
        "ok": True,
        "duplicate": False,
        "item": inserted_item,
        "message": msg,
        "scanned_count": counts["total_scanned"] or 0,
        "alerts_count": counts["total_alerts"] or 0,
    }


def get_audit_summary(audit_id: int) -> Optional[Dict[str, Any]]:
    """Retorna detalhe completo de uma conferência: metadados, bipados, alertas e não-bipados."""
    ensure_stock_audit_schema()
    with db() as conn:
        audit = conn.execute("SELECT * FROM stock_audits WHERE id = %s", (audit_id,)).fetchone()
        if not audit:
            return None
        audit_dict = dict(audit)

        scanned_rows = conn.execute(
            "SELECT * FROM stock_audit_items WHERE audit_id = %s ORDER BY id DESC",
            (audit_id,),
        ).fetchall()
        scanned_items = [dict(r) for r in scanned_rows]
        scanned_set = {r["chassis"].strip().upper() for r in scanned_items}

        expected_units = _get_expected_units(conn, audit_dict["location_scope"])
        missing_units = [u for u in expected_units if u["chassis"].strip().upper() not in scanned_set]
        alerts = [i for i in scanned_items if i["scan_result"] != "ok"]

        return {
            "audit": audit_dict,
            "scanned_items": scanned_items,
            "alerts": alerts,
            "missing_units": missing_units,
            "expected_count": len(expected_units),
            "scanned_count": len(scanned_items),
            "missing_count": len(missing_units),
            "alerts_count": len(alerts),
        }


def finish_stock_audit(audit_id: int) -> Optional[Dict[str, Any]]:
    """Finaliza a sessão de conferência e consolida os números finais para o PDF."""
    summary = get_audit_summary(audit_id)
    if not summary:
        return None
    with db() as conn:
        conn.execute(
            """
            UPDATE stock_audits
            SET status = 'finished',
                finished_at = CURRENT_TIMESTAMP,
                expected_count = %s,
                scanned_count = %s,
                missing_count = %s,
                alerts_count = %s
            WHERE id = %s
            """,
            (
                summary["expected_count"],
                summary["scanned_count"],
                summary["missing_count"],
                summary["alerts_count"],
                audit_id,
            ),
        )
        conn.commit()
    return get_audit_summary(audit_id)


def list_recent_audits(limit: int = 20) -> List[Dict[str, Any]]:
    """Lista histórico das conferências realizadas."""
    ensure_stock_audit_schema()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM stock_audits ORDER BY id DESC LIMIT %s",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
