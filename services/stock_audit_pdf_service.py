"""
M-One Stock Audit PDF Service (services/stock_audit_pdf_service.py)
Gera o Relatório Executivo de Conferência de Estoque em PDF via ReportLab,
destacando alertas críticos (separados/divergências) e chassis não bipados.
"""

from __future__ import annotations

import io
from collections import defaultdict
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


SCAN_RESULT_LABELS = {
    "alert_separated": "SEPARADO P/ VENDA",
    "alert_sold": "CONSTAVA VENDIDO",
    "alert_assembled": "CONSTAVA MONTADO",
    "alert_other_location": "OUTRO GALPÃO",
    "unknown": "NÃO CADASTRADO",
}


def build_stock_audit_pdf(summary: Dict[str, Any]) -> io.BytesIO:
    """Constrói PDF em memória a partir do resumo retornado por get_audit_summary."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Conferência Estoque #{summary['audit']['id']}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MOneTitle",
        parent=styles["Heading1"],
        fontSize=15,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "MOneSub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "MOneSection",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6,
    )

    audit = summary["audit"]
    elements = [
        Paragraph(f"M-One • Relatório de Conferência de Estoque #{audit['id']}", title_style),
        Paragraph(
            f"<b>Galpão:</b> {audit.get('location_scope', 'Todos')} &nbsp;|&nbsp; "
            f"<b>Responsável:</b> {audit.get('started_by_name') or 'Operador'} &nbsp;|&nbsp; "
            f"<b>Início:</b> {str(audit.get('started_at') or '')[:16]} &nbsp;|&nbsp; "
            f"<b>Fim:</b> {str(audit.get('finished_at') or 'Em andamento')[:16]}",
            subtitle_style,
        ),
    ]

    # 1. Resumo numérico
    kpi_data = [
        ["Esperados no Galpão", "Total Bipados", "Não Bipados (Investigar)", "Alertas / Divergências"],
        [
            str(summary["expected_count"]),
            str(summary["scanned_count"]),
            str(summary["missing_count"]),
            str(summary["alerts_count"]),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[45 * mm, 45 * mm, 46 * mm, 46 * mm])
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 13),
                ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#b45309")),
                ("TEXTCOLOR", (3, 1), (3, 1), colors.HexColor("#dc2626")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.extend([kpi_table, Spacer(1, 8)])

    # 1b. Resumo por Aba / Contêiner Detectado
    tab_breakdown = summary.get("tab_breakdown") or []
    if tab_breakdown:
        elements.append(Paragraph(f"📁 Abas / Contêineres Identificados ({len(tab_breakdown)})", section_style))
        tab_rows = [["Aba / Contêiner / Local", "Bipados", "Não Bipados", "Alertas"]]
        for tb in tab_breakdown:
            tab_rows.append([
                str(tb.get("tab") or "Geral")[:45],
                str(tb.get("scanned", 0)),
                str(tb.get("missing", 0)),
                str(tb.get("alerts", 0)),
            ])
        t_tabs = Table(tab_rows, colWidths=[88 * mm, 30 * mm, 32 * mm, 32 * mm], repeatRows=1)
        t_tabs.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.extend([t_tabs, Spacer(1, 8)])

    # 2. Alertas Críticos (Separados para venda bipados, vendidos, outro galpão, desconhecidos)
    alerts = summary.get("alerts") or []
    elements.append(Paragraph(f"⚠️ Alertas Críticos na Bipagem ({len(alerts)})", section_style))
    if alerts:
        alert_rows = [["Chassi", "Modelo / Cor", "Ocorrência", "Aba / Pedido"]]
        for a in alerts:
            occ = SCAN_RESULT_LABELS.get(a.get("scan_result"), a.get("scan_result") or "")
            det = []
            if a.get("source_tab_snapshot"):
                det.append(str(a["source_tab_snapshot"])[:22])
            if a.get("order_number_snapshot"):
                det.append(f"Ped. #{a['order_number_snapshot']}")
            alert_rows.append(
                [
                    a.get("chassis", ""),
                    f"{a.get('product_name_snapshot') or ''} ({a.get('color_snapshot') or '—'})",
                    occ,
                    " | ".join(det) or "—",
                ]
            )
        t_alerts = Table(alert_rows, colWidths=[44 * mm, 52 * mm, 40 * mm, 46 * mm], repeatRows=1)
        t_alerts.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#fca5a5")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fef2f2")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.extend([t_alerts, Spacer(1, 8)])
    else:
        elements.append(Paragraph("Nenhum alerta crítico registrado nesta conferência.", subtitle_style))

    # 3. Chassis Não Bipados (agrupados por modelo)
    missing = summary.get("missing_units") or []
    elements.append(
        Paragraph(
            f"🔍 Chassis Não Bipados — Para Investigação ({len(missing)})",
            section_style,
        )
    )
    elements.append(
        Paragraph(
            "Motivos esperados: (1) Sem lançamento na aba de vendas | (2) Produto montado | (3) Pulado na conferência.",
            subtitle_style,
        )
    )

    if missing:
        grouped = defaultdict(list)
        for m in missing:
            tab_lbl = (m.get("source_tab") or m.get("location") or "Geral").strip()
            grouped[(tab_lbl, m.get("product_name") or "Sem Modelo")].append(m)

        missing_rows = [["Aba / Modelo", "Chassi", "Cor / Status", "Motivo / Investigação"]]
        for tab_lbl, model_name in sorted(grouped.keys()):
            for u in grouped[(tab_lbl, model_name)]:
                st_label = "Separado" if u.get("status") == "separated" else "Disponível"
                missing_rows.append(
                    [
                        f"{tab_lbl[:22]}\n{model_name[:22]}",
                        u.get("chassis", ""),
                        f"{u.get('color') or '—'} ({st_label})",
                        "[ ] S/ Venda  [ ] Montado  [ ] Pulado",
                    ]
                )
        t_missing = Table(missing_rows, colWidths=[42 * mm, 42 * mm, 38 * mm, 60 * mm], repeatRows=1)
        t_missing.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(t_missing)
    else:
        elements.append(Paragraph("100% dos chassis esperados neste galpão foram bipados!", subtitle_style))

    doc.build(elements)
    buf.seek(0)
    return buf
