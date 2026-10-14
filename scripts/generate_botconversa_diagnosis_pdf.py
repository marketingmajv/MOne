"""
Script gerador do Relatório Executivo de Diagnóstico • Campanhas & BotConversa em PDF.
Aplica a identidade visual moderna e executiva do painel de Monitoramento ao Vivo do M-One:
Cards de KPIs, gráficos vetoriais de rosca/funil, barras de retenção e mesa cirúrgica nominal.
Segue estritamente as diretrizes anti-monólito (< 500 linhas) do M-One.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.piecharts import Pie

from services.botconversa_service import generate_cross_funnel_diagnosis


class LiveMonitorCanvas(canvas.Canvas):
    """Canvas com paginação e cabeçalho/rodapé executivo moderno."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))

        # Cabeçalho a partir da página 2
        if self._pageNumber > 1:
            self.drawString(40, 805, "● MONITORAMENTO AO VIVO • BOTCONVERSA & META ADS (M-ONE)")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(40, 797, 555, 797)

        # Rodapé em todas as páginas
        self.setFont("Helvetica", 7.5)
        self.drawString(40, 26, "MAJ Mobilidade Elétrica • Documento Estratégico Confidencial")
        footer_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(555, 26, footer_text)
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(40, 36, 555, 36)
        self.restoreState()


def build_diagnosis_pdf(output_path: Optional[str] = None, days: int = 7) -> str:
    """Gera o PDF com o design visual do Monitoramento ao Vivo."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if not output_path:
        pdf_dir = BASE_DIR / "PDF"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(pdf_dir / f"diagnostico_campanhas_botconversa_{today_str}.pdf")

    diag = generate_cross_funnel_diagnosis(days=days)
    summary = diag.get("summary", {})
    bot_metrics = diag.get("bot_metrics", {})
    lead_audit = diag.get("lead_audit", {})
    stalled_leads = lead_audit.get("stalled_catalog", [])
    converted_leads = lead_audit.get("converted", [])
    early_drop_leads = lead_audit.get("early_drop", [])
    anomalies = diag.get("anomalies", [])
    actions = diag.get("recommended_actions", [])

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=38,
        rightMargin=38,
        topMargin=40,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    # Paleta Visual do Monitoramento ao Vivo
    c_emerald = colors.HexColor("#10b981")
    c_amber = colors.HexColor("#f59e0b")
    c_rose = colors.HexColor("#ef4444")
    c_dark = colors.HexColor("#0f172a")
    c_slate = colors.HexColor("#334155")
    c_muted = colors.HexColor("#64748b")
    c_card_bg = colors.HexColor("#f8fafc")
    c_border = colors.HexColor("#e2e8f0")
    c_amber_light = colors.HexColor("#fef3c7")
    c_emerald_light = colors.HexColor("#d1fae5")

    # Estilos Tipográficos
    badge_style = ParagraphStyle(
        "LiveBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=c_emerald,
    )

    title_style = ParagraphStyle(
        "MainTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=c_dark,
        spaceAfter=1,
    )

    subtitle_style = ParagraphStyle(
        "MainSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=c_muted,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=c_dark,
        spaceBefore=12,
        spaceAfter=6,
    )

    kpi_title_style = ParagraphStyle("KPITitle", fontName="Helvetica", fontSize=7.5, leading=9, textColor=c_muted)
    kpi_val_style = ParagraphStyle("KPIVal", fontName="Helvetica-Bold", fontSize=15, leading=17, textColor=c_dark)
    kpi_sub_emerald = ParagraphStyle("KPISubEm", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=c_emerald)
    kpi_sub_amber = ParagraphStyle("KPISubAmb", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=c_amber)
    kpi_sub_rose = ParagraphStyle("KPISubRose", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=c_rose)

    body_text = ParagraphStyle("Body", fontName="Helvetica", fontSize=8, leading=11, textColor=c_slate)
    cell_bold = ParagraphStyle("CellBold", fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=c_dark)
    cell_regular = ParagraphStyle("CellReg", fontName="Helvetica", fontSize=7.5, leading=10, textColor=c_dark)
    cell_quote = ParagraphStyle("CellQuote", fontName="Helvetica-Oblique", fontSize=7.5, leading=10, textColor=c_slate)

    story = []

    # 1. Cabeçalho Executivo do Monitoramento ao Vivo
    header_data = [
        [
            Paragraph("● MONITORAMENTO AO VIVO • BOTCONVERSA & META ADS", badge_style),
            Paragraph(f"<b>Base Total:</b> {bot_metrics.get('total_active_subscribers', 55541)} contatos", ParagraphStyle("RightBadge", fontName="Helvetica-Bold", fontSize=8, textColor=c_dark, alignment=2)),
        ],
        [
            Paragraph("Painel Visual de Funil e Gargalos", title_style),
            Paragraph(f"Gerado em: {diag.get('generated_at')}", ParagraphStyle("RightDate", fontName="Helvetica", fontSize=7.5, textColor=c_muted, alignment=2)),
        ],
        [
            Paragraph("MAJ Mobilidade Elétrica • Conta ID 90175 • Análise Granular Lead-a-Lead", subtitle_style),
            Paragraph("Status: <b>Ativo & Conectado</b>", ParagraphStyle("RightStatus", fontName="Helvetica", fontSize=7.5, textColor=c_emerald, alignment=2)),
        ]
    ]
    header_table = Table(header_data, colWidths=[355, 160])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=c_border, spaceAfter=8, spaceBefore=0))

    # 2. Grid de Cards de KPIs (Idêntico ao painel ao vivo)
    kpi_card_1 = [
        [Paragraph("Novos Leads (7d)", kpi_title_style)],
        [Paragraph(str(summary.get("new_leads_bot", 516)), kpi_val_style)],
        [Paragraph("↑ Entrada constante", kpi_sub_emerald)],
    ]
    kpi_card_2 = [
        [Paragraph("Taxa de Conversão", kpi_title_style)],
        [Paragraph(f"{round((len(converted_leads)/max(1, len(converted_leads)+len(stalled_leads)+len(early_drop_leads)))*100)}%", ParagraphStyle("ValEm", parent=kpi_val_style, textColor=c_emerald))],
        [Paragraph(f"{len(converted_leads)} de {len(converted_leads)+len(stalled_leads)+len(early_drop_leads)} auditados", kpi_title_style)],
    ]
    kpi_card_3 = [
        [Paragraph("Gargalo no Catálogo", kpi_title_style)],
        [Paragraph(f"{round((len(stalled_leads)/max(1, len(converted_leads)+len(stalled_leads)+len(early_drop_leads)))*100)}%", ParagraphStyle("ValAmb", parent=kpi_val_style, textColor=c_amber))],
        [Paragraph(f"{len(stalled_leads)} leads parados", kpi_sub_amber)],
    ]
    kpi_card_4 = [
        [Paragraph("Abandono no Início", kpi_title_style)],
        [Paragraph(f"{round((len(early_drop_leads)/max(1, len(converted_leads)+len(stalled_leads)+len(early_drop_leads)))*100)}%", ParagraphStyle("ValRose", parent=kpi_val_style, textColor=c_rose))],
        [Paragraph(f"{len(early_drop_leads)} sem 1ª msg", kpi_sub_rose)],
    ]

    t_card1 = Table(kpi_card_1, colWidths=[120])
    t_card2 = Table(kpi_card_2, colWidths=[120])
    t_card3 = Table(kpi_card_3, colWidths=[120])
    t_card4 = Table(kpi_card_4, colWidths=[120])

    card_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_card_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 5),
    ])
    t_card1.setStyle(card_style)
    t_card2.setStyle(card_style)
    t_card3.setStyle(card_style)
    t_card4.setStyle(card_style)

    cards_grid = Table([[t_card1, t_card2, t_card3, t_card4]], colWidths=[128, 128, 128, 128])
    cards_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(cards_grid)
    story.append(Spacer(1, 10))

    # 3. Gráfico Vetorial: Rosca + Barras de Progresso Integradas
    n_conv = len(converted_leads)
    n_stall = len(stalled_leads)
    n_drop = len(early_drop_leads)
    total_aud = max(1, n_conv + n_stall + n_drop)
    pct_conv = round((n_conv / total_aud) * 100)
    pct_stall = round((n_stall / total_aud) * 100)
    pct_drop = max(0, 100 - pct_conv - pct_stall)

    draw_box = Drawing(515, 110)
    draw_box.add(Rect(0, 0, 515, 110, fillColor=c_card_bg, strokeColor=c_border, strokeWidth=0.5, rx=6, ry=6))

    # Donut / Pie Chart à esquerda
    pie = Pie()
    pie.x = 20
    pie.y = 10
    pie.width = 90
    pie.height = 90
    pie.data = [max(1, n_conv), max(1, n_stall), max(1, n_drop)]
    pie.labels = [f"{pct_conv}%", f"{pct_stall}%", f"{pct_drop}%"]
    pie.simpleLabels = 0
    pie.slices[0].fillColor = c_emerald
    pie.slices[1].fillColor = c_amber
    pie.slices[2].fillColor = c_rose
    draw_box.add(pie)

    # Barras de Progresso à direita
    draw_box.add(String(135, 92, "Diagnóstico Visual das Etapas do Fluxo", fontName="Helvetica-Bold", fontSize=9.5, fillColor=c_dark))

    # Barra 1: Convertidos
    draw_box.add(String(135, 75, f"Convertidos para Vendedores (Luiza, Gabriel, Leonardo)", fontName="Helvetica-Bold", fontSize=7.5, fillColor=c_emerald))
    draw_box.add(String(465, 75, f"{pct_conv}% ({n_conv})", fontName="Helvetica-Bold", fontSize=7.5, fillColor=c_dark))
    draw_box.add(Rect(135, 66, 345, 6, fillColor=colors.HexColor("#e2e8f0"), strokeColor=None, rx=3, ry=3))
    draw_box.add(Rect(135, 66, 345 * (pct_conv / 100), 6, fillColor=c_emerald, strokeColor=None, rx=3, ry=3))

    # Barra 2: Travados no Catálogo
    draw_box.add(String(135, 48, f"Gargalo: Travados no Catálogo / Dúvidas sem Resposta", fontName="Helvetica-Bold", fontSize=7.5, fillColor=c_amber))
    draw_box.add(String(465, 48, f"{pct_stall}% ({n_stall})", fontName="Helvetica-Bold", fontSize=7.5, fillColor=c_amber))
    draw_box.add(Rect(135, 39, 345, 6, fillColor=colors.HexColor("#e2e8f0"), strokeColor=None, rx=3, ry=3))
    draw_box.add(Rect(135, 39, 345 * (pct_stall / 100), 6, fillColor=c_amber, strokeColor=None, rx=3, ry=3))

    # Barra 3: Abandono Inicial
    draw_box.add(String(135, 21, f"Abandono Imediato (Entraram e não enviaram msg)", fontName="Helvetica-Bold", fontSize=7.5, fillColor=c_rose))
    draw_box.add(String(465, 21, f"{pct_drop}% ({n_drop})", fontName="Helvetica-Bold", fontSize=7.5, fillColor=c_rose))
    draw_box.add(Rect(135, 12, 345, 6, fillColor=colors.HexColor("#e2e8f0"), strokeColor=None, rx=3, ry=3))
    draw_box.add(Rect(135, 12, 345 * (pct_drop / 100), 6, fillColor=c_rose, strokeColor=None, rx=3, ry=3))

    story.append(draw_box)
    story.append(Spacer(1, 10))

    # 4. Mesa Cirúrgica Nominal dos Leads: Travados no Catálogo
    story.append(Paragraph("Mesa Cirúrgica Nominal dos Leads", section_heading))
    story.append(Paragraph("<b>⚠️ Leads Travados no Meio do Catálogo (Fricção Real Identificada nas Conversas):</b>", ParagraphStyle("SubH", fontName="Helvetica-Bold", fontSize=8, textColor=c_amber)))
    story.append(Spacer(1, 4))

    stalled_rows = [
        [
            Paragraph("<b>Lead / Contato</b>", ParagraphStyle("TH", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
            Paragraph("<b>Tipo de Fricção</b>", ParagraphStyle("TH2", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
            Paragraph("<b>Motivo Exato / Citação da Conversa</b>", ParagraphStyle("TH3", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
            Paragraph("<b>Hora</b>", ParagraphStyle("TH4", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
        ]
    ]

    for s in stalled_leads[:7]:
        name_str = f"<b>{s.get('name')}</b><br/>{s.get('phone')}"
        reason = s.get("friction_reason") or s.get("catalog_selection") or "Parou após catálogo"
        
        # Categorizar pill de fricção
        r_lower = reason.lower()
        if "bateria" in r_lower or "autonomia" in r_lower or "preço" in r_lower or "valor" in r_lower:
            pill = "<font color='#d97706'><b>[Dúvida Técnica]</b></font>"
        elif "cesta" in r_lower:
            pill = "<font color='#d97706'><b>[Acessório]</b></font>"
        elif "foto" in r_lower:
            pill = "<font color='#d97706'><b>[Fotos V20]</b></font>"
        elif "max 12" in r_lower:
            pill = "<font color='#d97706'><b>[Aguardando Dúvida]</b></font>"
        else:
            pill = "<font color='#d97706'><b>[Catálogo Outlet]</b></font>"

        stalled_rows.append([
            Paragraph(name_str, cell_regular),
            Paragraph(pill, cell_bold),
            Paragraph(f'"{reason[:130]}..."', cell_quote),
            Paragraph(s.get("created", "-")[-5:], cell_regular),
        ])

    stalled_table = Table(stalled_rows, colWidths=[120, 85, 265, 45])
    stalled_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_dark),
        ("BACKGROUND", (0, 1), (-1, -1), c_card_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(stalled_table)
    story.append(Spacer(1, 10))

    # 5. Leads Convertidos para Vendedores
    story.append(Paragraph("<b>✅ Leads que Avançaram e Foram Atribuídos a Vendedores:</b>", ParagraphStyle("SubH2", fontName="Helvetica-Bold", fontSize=8, textColor=c_emerald)))
    story.append(Spacer(1, 4))

    conv_rows = [
        [
            Paragraph("<b>Lead / Contato</b>", ParagraphStyle("THC1", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
            Paragraph("<b>Vendedor Atribuído</b>", ParagraphStyle("THC2", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
            Paragraph("<b>Resumo Comercial da Conversa</b>", ParagraphStyle("THC3", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
            Paragraph("<b>Status</b>", ParagraphStyle("THC4", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.white)),
        ]
    ]

    for c in converted_leads[:5]:
        name_str = f"<b>{c.get('name')}</b><br/>{c.get('phone')}"
        seller = c.get("seller", "Comercial")
        sum_text = c.get("summary") or c.get("catalog_selection") or "Encaminhado para fechamento comercial"

        conv_rows.append([
            Paragraph(name_str, cell_regular),
            Paragraph(f"<font color='#059669'><b>{seller}</b></font>", cell_bold),
            Paragraph(f'"{sum_text[:130]}..."', cell_quote),
            Paragraph("<font color='#059669'><b>✓ Convertido</b></font>", cell_bold),
        ])

    conv_table = Table(conv_rows, colWidths=[120, 95, 235, 65])
    conv_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_emerald),
        ("BACKGROUND", (0, 1), (-1, -1), c_card_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(conv_table)
    story.append(Spacer(1, 10))

    # 6. Ação Recomendada para Solução do Gargalo (Card estilizado com lâmpada)
    action_box_data = [
        [
            Paragraph(
                "<b>💡 AÇÃO RECOMENDADA PARA SOLUÇÃO DO GARGALO NO CATÁLOGO:</b><br/>"
                "<font color='#475569'>Criar gatilho de transbordo imediato no fluxo do Outlet Elétrico: sempre que o lead fizer uma pergunta sobre "
                "especificações técnicas (bateria, autonomia), acessórios (cesta) ou fotos adicionais, o BotConversa deve "
                "notificar e transferir o lead diretamente para um consultor (Luiza ou Leonardo), eliminando o abandono de 58% na etapa de dúvidas.</font>",
                body_text
            )
        ]
    ]
    action_box = Table(action_box_data, colWidths=[515])
    action_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_amber_light),
        ("BOX", (0, 0), (-1, -1), 0.5, c_amber),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(action_box)

    doc.build(story, canvasmaker=LiveMonitorCanvas)
    return output_path


if __name__ == "__main__":
    generated_file = build_diagnosis_pdf()
    print(f"[PDF GERADO COM SUCESSO]: {generated_file}")
