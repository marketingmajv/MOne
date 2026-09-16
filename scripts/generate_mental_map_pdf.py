#!/usr/bin/env python3
"""
Gera o PDF Executivo do Mapa Mental e Arquitetura de Valor do M-One.
Salva em: PDF/Mapa_Mental_M-One_Arquitetura_de_Valor.pdf
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent.parent
PDF_DIR = BASE_DIR / "PDF"
PDF_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = PDF_DIR / "Mapa_Mental_M-One_Arquitetura_de_Valor.pdf"

USABLE_WIDTH = 523  # A4 (595.27) - 2 * 36 (margens)


class NumberedCanvas(canvas.Canvas):
    """Canvas de duas passadas para numeração precisa de páginas e cabeçalho executivo."""
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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Cabeçalho na página 2 em diante
        if self._pageNumber > 1:
            self.drawString(36, A4[1] - 30, "M-ONE OPERATING SYSTEM • MAPA MENTAL & ARQUITETURA DE VALOR")
            self.drawRightString(A4[0] - 36, A4[1] - 30, "MAJ MOBILIDADE ELÉTRICA")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.6)
            self.line(36, A4[1] - 35, A4[0] - 36, A4[1] - 35)
        
        # Rodapé elegante em todas as páginas
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.6)
        self.line(36, 34, A4[0] - 36, 34)
        
        self.setFont("Helvetica", 7.5)
        self.drawString(36, 22, "M-One OS — Documento Institucional & Comercial • Confidencial e Estruturado para Apresentações")
        page_str = f"Página {self._pageNumber} de {total_pages}"
        self.drawRightString(A4[0] - 36, 22, page_str)
        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_FILE),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()

    h1_style = ParagraphStyle(
        'Heading1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0F172A")
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#334155")
    )

    bullet_style = ParagraphStyle(
        'BulletDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=11.8,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=10
    )

    card_header_style = ParagraphStyle(
        'CardHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=colors.HexColor("#0F172A")
    )

    quote_style = ParagraphStyle(
        'QuoteText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0284C7")
    )

    elements = []

    # ==========================================
    # CABEÇALHO HERO EXECUTIVO (PÁGINA 1)
    # ==========================================
    header_content = [
        [
            Paragraph("<b>M-ONE OPERATING SYSTEM</b>", ParagraphStyle(
                'HeroSuper', fontName='Helvetica-Bold', fontSize=8, leading=9, textColor=colors.HexColor("#00E599")
            )),
            Paragraph("<b>VERSÃO EXECUTIVA 2026</b>", ParagraphStyle(
                'HeroDate', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.HexColor("#94A3B8"), alignment=2
            ))
        ],
        [
            Paragraph("Mapa Mental & Arquitetura de Valor", ParagraphStyle(
                'HeroMain', fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=colors.white
            )),
            ""
        ],
        [
            Paragraph("Sistema Operacional de Ponta a Ponta para Mobilidade Elétrica • Fonte Única da Verdade MAJ", ParagraphStyle(
                'HeroSub', fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=colors.HexColor("#CBD5E1")
            )),
            ""
        ]
    ]

    header_table = Table(header_content, colWidths=[383, 140])
    header_table.setStyle(TableStyle([
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 2), (1, 2)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0B132B")),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('LINEBELOW', (0, 2), (-1, 2), 2.5, colors.HexColor("#00E599")),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 10))

    # INTRODUÇÃO
    intro_p = Paragraph(
        "<b>Visão Geral Executiva:</b> O M-One é o ERP vertical inteligente da MAJ que unifica <b>Comércio Exterior</b>, "
        "<b>Rastreabilidade Unitária de Chassis</b>, <b>Vendas com IA</b> e <b>Motor de Fretes Multimodal</b>. "
        "Elimina 'vendas sem estoque físico', audita comprovantes bancários via visão computacional e garante conformidade fiscal e operacional.",
        body_style
    )
    elements.append(intro_p)
    elements.append(Spacer(1, 10))

    # OS 5 PILARES
    elements.append(Paragraph("<b>1. Os 5 Pilares Estratégicos do M-One</b>", h1_style))
    elements.append(Spacer(1, 6))

    pillars = [
        {
            "badge": "PILAR 01",
            "title": "Rastreabilidade de Chassi & Pátio Operacional",
            "concept": "« Nenhum veículo é genérico: cada chassi tem identidade e histórico únicos »",
            "bullets": [
                "<b>Chassi Atômico:</b> Registro individual desde o porto de origem na Ásia até a entrega na garagem do comprador.",
                "<b>Regra de Ouro Inegociável:</b> Nenhuma venda ou nota fiscal entra sem chassi físico existente, liberado e não duplicado.",
                "<b>Inteligência de Giro (60-90 dias):</b> Alertas de veículos com giro lento com sugestão de preço promocional para liquidez."
            ]
        },
        {
            "badge": "PILAR 02",
            "title": "Comércio Exterior & Gestão Aduaneira (Import Hub)",
            "concept": "« O frete marítimo e desembaraço aduaneiro conectados diretamente ao estoque faturável »",
            "bullets": [
                "<b>Controle de Lotes & Contêineres:</b> Vinculação direta de Invoices, Bill of Lading (BL), Packing Lists e DI.",
                "<b>Rateio de Custos & Sigilo Blindado:</b> Custos portuários, impostos e fretes internacionais sob sigilo da Diretoria.",
                "<b>Nacionalização Automática:</b> Desembaraço concluído migra os chassis instantaneamente para o pátio disponível."
            ]
        },
        {
            "badge": "PILAR 03",
            "title": "Gestão Comercial & IA Financeira (Sales Hub)",
            "concept": "« Vendas integradas ao Bling ERP e blindadas contra comprovantes falsos via Inteligência Artificial »",
            "bullets": [
                "<b>Integração Oficial Bling ERP:</b> Conexão bidirecional em tempo real para pedidos e notas fiscais via OAuth 2.0.",
                "<b>Validação de Comprovantes por IA:</b> Leitura de comprovantes PIX/TED por visão computacional atestando dados e valores.",
                "<b>Cockpit Executivo em Tempo Real:</b> Métricas de faturamento do mês, liquidações e progresso de metas com 1 clique."
            ]
        },
        {
            "badge": "PILAR 04",
            "title": "Motor Logístico & Cotação de Fretes (Freight Engine)",
            "concept": "« Cotação multi-transportadoras com cálculo automático da regra de seguro e envio direto no WhatsApp »",
            "bullets": [
                "<b>Simulador Multi-Transportadoras:</b> Compara na hora tabelas tarifárias (Jamef, Braspress, etc.) saindo de Vitória/ES.",
                "<b>Regra de Seguro Obrigatória (1/3 do Atacado):</b> Aplica a regra matemática automaticamente, prevenindo prejuízos.",
                "<b>Leitor de Tabelas por IA:</b> Importação automatizada de tabelas complexas de frete em PDF e planilhas via Gemini IA.",
                "<b>Proposta em 30 Segundos:</b> Geração de proposta PDF consolidada e mensagem pronta para WhatsApp em 1 clique."
            ]
        },
        {
            "badge": "PILAR 05",
            "title": "Copilot Executivo & Governança Blindada",
            "concept": "« IA atuando como copiloto analítico da operação e auditoria imutável de todas as ações »",
            "bullets": [
                "<b>Copilot IA Estratégico:</b> Assistente conversacional para consultas de estoque, diagnósticos de clientes e inteligência de vendas.",
                "<b>Trilha de Auditoria Imutável:</b> Registro detalhado de logins, alterações de chassis, downloads e aprovações com timestamp.",
                "<b>Segurança Baseada em Papéis (RBAC):</b> Perfis hierárquicos rígidos (Diretoria, Vendas, Financeiro e Suporte)."
            ]
        }
    ]

    for p in pillars:
        bullet_pars = [Paragraph(f"• {b}", bullet_style) for b in p["bullets"]]
        
        card_content = [
            [
                Paragraph(
                    f"<font color='#0070F3'><b>{p['badge']}</b></font> &nbsp;•&nbsp; <b>{p['title']}</b>",
                    card_header_style
                )
            ],
            [
                Paragraph(p["concept"], quote_style)
            ],
            [
                bullet_pars
            ]
        ]
        
        card_table = Table(card_content, colWidths=[USABLE_WIDTH])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor("#E2E8F0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 6),
        ]))
        
        elements.append(card_table)
        elements.append(Spacer(1, 5))

    elements.append(PageBreak())

    # ==========================================
    # PÁGINA 2: JORNADA DO CHASSI & ARGUMENTOS PITCH
    # ==========================================
    elements.append(Paragraph("<b>2. O Ciclo de Vida do Chassi no M-One (Do Porto à Entrega)</b>", h1_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "Roteiro de storytelling para demonstrar aos clientes como a governança do M-One opera na prática cotidiana:",
        body_style
    ))
    elements.append(Spacer(1, 7))

    journey_steps = [
        ("1. Chegada Marítima", "Contêiner desembarca no porto. Invoices, BL e chassis registrados no módulo Comex com status 'Em Trânsito'."),
        ("2. Desembaraço Alfandegário", "Conclusão aduaneira e DI aprovada. Sistema migra automaticamente os chassis para o status 'Disponível em Pátio'."),
        ("3. Negociação & Venda", "Comercial seleciona o cliente e vincula o chassi específico. Pedido integrado ao Bling ERP em tempo real."),
        ("4. Validação por IA", "Comprovante PIX/TED enviado pelo cliente é auditado e validado pelo Gemini Vision antes da liberação do faturamento."),
        ("5. Cotação de Frete", "Motor logístico calcula o frete com seguro obrigatório de 1/3 do atacado e gera proposta em PDF e texto para WhatsApp."),
        ("6. Despacho & Entrega", "Logística aprova a cotação, despacha a mercadoria pela transportadora e o chassi é baixado para 'Vendido/Entregue'.")
    ]

    journey_table_data = []
    for step_title, step_desc in journey_steps:
        journey_table_data.append([
            Paragraph(f"<b>{step_title}</b>", ParagraphStyle('JStep', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor("#0F172A"))),
            Paragraph(step_desc, ParagraphStyle('JDesc', fontName='Helvetica', fontSize=8.2, leading=11.5, textColor=colors.HexColor("#334155")))
        ])

    journey_table = Table(journey_table_data, colWidths=[145, 378])
    journey_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
        ('BACKGROUND', (1, 0), (1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(journey_table)
    elements.append(Spacer(1, 14))

    # ARGUMENTOS DE PITCH
    elements.append(Paragraph("<b>3. Argumentos-Chave para a Apresentação Comercial (Pitch Deck)</b>", h1_style))
    elements.append(Spacer(1, 6))

    pitch_bullets = [
        ("« Fim da Venda Fantasma »", "Nenhum vendedor consegue registrar ou faturar pedido sem vincular um chassi físico real, existente e desembaraçado."),
        ("« Inteligência Artificial Aplicada ao Lucro »", "IA prática que previne golpes financeiros conferindo comprovantes bancários e lê tabelas complexas de frete em segundos."),
        ("« Agilidade no Fechamento Comercial »", "Cotação multi-transportadora instantânea, aplicação da regra de seguro e proposta no WhatsApp em menos de 30 segundos."),
        ("« Infraestrutura Escalável e em Nuvem »", "Banco de dados em nuvem Supabase com pooler IPv4 dedicado e hospedagem serverless Vercel de alta velocidade."),
        ("« Auditoria e Governança 100% Blindada »", "Trilha completa e imutável de quem fez cada ação, em qual horário e com qual endereço IP.")
    ]

    pitch_table_data = []
    for title, desc in pitch_bullets:
        pitch_table_data.append([
            Paragraph(f"<b>{title}</b>", ParagraphStyle('PTitle', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor("#065F46"))),
            Paragraph(desc, ParagraphStyle('PDesc', fontName='Helvetica', fontSize=8.2, leading=11.5, textColor=colors.HexColor("#1E293B")))
        ])

    pitch_table = Table(pitch_table_data, colWidths=[170, 353])
    pitch_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor("#BBF7D0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DCFCE7")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(pitch_table)
    elements.append(Spacer(1, 14))

    # ASSINATURA TÉCNICA E OFICIAL
    footer_table_data = [
        [
            Paragraph(
                "<b>MAJ Mobilidade Elétrica — Inovação & Tecnologia Automotiva</b><br/>"
                "<font color='#64748B'>Plataforma Oficial: <u>https://m-one.majmobilidade.com.br</u> • Matriz: Vitória/ES</font>",
                ParagraphStyle('SignText', fontName='Helvetica', fontSize=8, leading=11, alignment=1)
            )
        ]
    ]
    footer_table = Table(footer_table_data, colWidths=[USABLE_WIDTH])
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(footer_table)

    # Build
    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"PDF executivo de 2 páginas gerado com sucesso em: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_pdf()
