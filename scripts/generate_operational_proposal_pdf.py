"""
Script gerador da Apresentação Operacional em PDF para Diretoria / Administradores:
Módulo de Formação de Custos, Gestão Tributária e Precificação Intercompany (COLVIX ➔ M-ONE / PJ)
"""

import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

PDF_OUTPUT_PATH = "/Users/macstudio-maj/Documents/Desenvolvimento/Aplicativos/MOne/Proposta_Operacional_Precificacao_Fiscal_COLVIX_MOne.pdf"
ARTIFACT_DIR = "/Users/macstudio-maj/.gemini/antigravity-ide/brain/2da1332f-bf17-49eb-aecf-e9f4280d1b28"
ARTIFACT_PDF_PATH = os.path.join(ARTIFACT_DIR, "Proposta_Operacional_Precificacao_Fiscal_COLVIX_MOne.pdf")


class NumberedCanvas(canvas.Canvas):
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

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Cabeçalho a partir da página 2
        if self._pageNumber > 1:
            self.drawString(40, 805, "M-ONE • MAJ OPERATING SYSTEM")
            self.setFont("Helvetica", 8)
            self.drawRightString(555, 805, "Módulo de Precificação Fiscal & Intercompany (COLVIX ➔ M-ONE / PJ)")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.7)
            self.line(40, 797, 555, 797)

        # Rodapé em todas as páginas
        footer_text = f"Página {self._pageNumber} de {page_count}"
        self.setFont("Helvetica-Bold", 8)
        self.drawRightString(555, 30, footer_text)
        self.drawString(40, 30, "MAJ MOBILIDADE & COLVIX • DOCUMENTO ESTRATÉGICO OPERACIONAL — CONFIDENCIAL")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.7)
        self.line(40, 42, 555, 42)
        self.restoreState()


def create_pdf():
    os.makedirs(os.path.dirname(PDF_OUTPUT_PATH), exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    doc = SimpleDocTemplate(
        PDF_OUTPUT_PATH,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=48
    )

    styles = getSampleStyleSheet()

    # Cores executivas
    c_primary = colors.HexColor("#0f172a")     # Slate escuro
    c_blue = colors.HexColor("#0284c7")        # Azul M-One
    c_emerald = colors.HexColor("#059669")     # Verde sucesso/economia
    c_amber = colors.HexColor("#d97706")       # Âmbar destaque/alerta
    c_purple = colors.HexColor("#7c3aed")      # Roxo estratégico
    c_slate = colors.HexColor("#475569")       # Texto secundário
    c_light_bg = colors.HexColor("#f8fafc")    # Fundo de card
    c_border = colors.HexColor("#e2e8f0")      # Linha de borda

    # Estilos customizados
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=c_slate,
        spaceAfter=14,
    )

    h1_style = ParagraphStyle(
        "H1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=c_blue,
        spaceBefore=12,
        spaceAfter=6,
    )

    h2_style = ParagraphStyle(
        "H2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=c_primary,
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=c_primary,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=4,
    )

    table_header_style = ParagraphStyle(
        "TH_Style",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=1, # Centralizado
    )

    table_cell_style = ParagraphStyle(
        "TD_Style",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_primary,
    )

    table_cell_bold = ParagraphStyle(
        "TD_Bold",
        parent=table_cell_style,
        fontName="Helvetica-Bold",
    )

    table_cell_right = ParagraphStyle(
        "TD_Right",
        parent=table_cell_style,
        alignment=2,
    )

    table_cell_right_bold = ParagraphStyle(
        "TD_RightBold",
        parent=table_cell_bold,
        alignment=2,
    )

    card_text = ParagraphStyle(
        "CardText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=c_primary,
    )

    story = []

    # ==========================================
    # CAPA / CABEÇALHO DO DOCUMENTO
    # ==========================================
    story.append(Paragraph("PROPOSTA DE IMPLEMENTAÇÃO OPERACIONAL", ParagraphStyle(
        "PreHeader", fontName="Helvetica-Bold", fontSize=9, textColor=c_blue, spaceAfter=2
    )))
    story.append(Paragraph("Formação de Custos, Gestão Tributária e Precificação Intercompany", title_style))
    story.append(Paragraph("Integração da Inteligência da Planilha Fiscal ao M-One: <strong>COLVIX ➔ M-ONE / Clientes PJ</strong>", subtitle_style))
    
    # Barra de Metadados / Resumo Executivo Rápido
    meta_data = [
        [
            Paragraph("<strong>Objetivo:</strong> Automatizar a apuração de custos de importação, gestão de créditos e simulação tributária de vendas.", card_text),
            Paragraph("<strong>Perfil de Operação:</strong> Importação via COLVIX (ES), regime de Lucro Real e vendas B2B/Intercompany.", card_text)
        ],
        [
            Paragraph("<strong>Público-Alvo:</strong> Diretoria, Controladoria Comercial e Emissão Fiscal.", card_text),
            Paragraph("<strong>Data da Proposta:</strong> Setembro / 2026 • Versão Operacional Executiva.", card_text)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[255, 260])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # ==========================================
    # SEÇÃO 1: POR QUE ESSA IMPLEMENTAÇÃO É NECESSÁRIA?
    # ==========================================
    story.append(Paragraph("1. O Desafio Atual e o Objetivo do Módulo", h1_style))
    story.append(Paragraph(
        "Atualmente, os cálculos de custos dos produtos importados pela <strong>COLVIX</strong>, o rateio dos impostos de entrada e a simulação de preços e impostos de venda para a <strong>M-ONE</strong> ou para <strong>Clientes PJ</strong> são realizados em planilhas eletrônicas apartadas do sistema. "
        "Embora ricas em detalhes fiscais, o uso manual em planilhas traz riscos operacionais de digitação, dificuldade no controle histórico de saldos de créditos tributários e morosidade no fechamento comercial.",
        body_style
    ))
    story.append(Paragraph(
        "A proposta é <strong>incorporar toda essa regra fiscal dentro de um novo módulo independente no M-One</strong>, permitindo que a empresa:",
        body_style
    ))
    story.append(Paragraph("• <strong>Alimente os dados com agilidade:</strong> Importando o XML da NF-e de entrada ou selecionando uma importação já existente no sistema com 1 clique.", bullet_style))
    story.append(Paragraph("• <strong>Calcule o custo exato unitário:</strong> Rateando proporcionalmente impostos aduaneiros (II, PIS, COFINS, AFRMM, Siscomex) e respeitando o IPI e ICMS de cada produto.", bullet_style))
    story.append(Paragraph("• <strong>Controle os créditos fiscais:</strong> Mantendo uma conta-corrente de créditos de entrada da COLVIX (Lucro Real) que se abatem conforme as vendas acontecem.", bullet_style))
    story.append(Paragraph("• <strong>Tome a melhor decisão de venda (ICMS-ST):</strong> Comparando na mesma tela o impacto tributário de vender para a M-ONE versus faturar direto da COLVIX para o Cliente PJ.", bullet_style))
    story.append(Paragraph("• <strong>Valide antes de emitir a NF-e:</strong> Gerando um espelho de conferência pronto para comparar com o emissor/Bling, evitando rejeições e divergências fiscais.", bullet_style))

    story.append(Spacer(1, 8))

    # ==========================================
    # SEÇÃO 2: COMO FUNCIONAM OS CÁLCULOS (PASSO A PASSO OPERACIONAL)
    # ==========================================
    story.append(Paragraph("2. Como os Cálculos São Realizados (Metodologia da Planilha)", h1_style))
    story.append(Paragraph(
        "O motor financeiro do sistema reproduz com exatidão a metodologia validada pela assessoria fiscal, dividida em três fases lógicas:",
        body_style
    ))

    # Tabela com as 3 Fases
    fases_data = [
        [
            Paragraph("<strong>FASE 1: CUSTO DE ENTRADA ATÉ A COLVIX</strong>", ParagraphStyle("F1", fontName="Helvetica-Bold", fontSize=8.5, textColor=c_blue)),
            Paragraph("<strong>FASE 2: CONTA DE CRÉDITOS TRIBUTÁRIOS</strong>", ParagraphStyle("F2", fontName="Helvetica-Bold", fontSize=8.5, textColor=c_emerald)),
            Paragraph("<strong>FASE 3: PRECIFICAÇÃO & VENDA (COM ICMS-ST)</strong>", ParagraphStyle("F3", fontName="Helvetica-Bold", fontSize=8.5, textColor=c_amber))
        ],
        [
            Paragraph(
                "<strong>1. Valor Mercadoria:</strong> Soma do produto + frete internacional.<br/>"
                "<strong>2. Rateio Proporcional:</strong> II, PIS, COFINS, AFRMM e Siscomex são rateados com base na participação (%) de cada produto no valor total da NF.<br/>"
                "<strong>3. Impostos por Item:</strong> IPI e ICMS são aplicados por NCM conforme constam no DANFE.<br/>"
                "<strong>➔ Custo Unitário:</strong> Custo total acumulado do item dividido pela quantidade importada.",
                card_text
            ),
            Paragraph(
                "<strong>1. Saldo de Entrada:</strong> A NF gera saldos iniciais de créditos em <strong>PIS, COFINS, IPI e ICMS</strong>.<br/>"
                "<strong>2. Crédito por Unidade:</strong> O sistema divide o crédito de cada tributo pela quantidade de produtos.<br/>"
                "<strong>3. Amortização na Venda:</strong> Ao simular ou efetivar a venda de itens, o sistema calcula a parcela proporcional de crédito consumida e mostra o <strong>saldo restante do lote</strong>.",
                card_text
            ),
            Paragraph(
                "<strong>1. Margem sobre Custo:</strong> Aplica-se a margem de lucro (%) desejada sobre o custo COLVIX.<br/>"
                "<strong>2. Débitos de Saída:</strong> Calcula ICMS próprio (12%), IPI por NCM, PIS (1,65%) e COFINS (7,6%).<br/>"
                "<strong>3. ICMS-ST:</strong> Aplica MVA (34%) sobre a base (venda + IPI) e desconta o ICMS próprio.<br/>"
                "<strong>4. Apuração:</strong> Débitos (-) Créditos = Imposto a Pagar ou Saldo Credor.",
                card_text
            )
        ]
    ]
    fases_table = Table(fases_data, colWidths=[170, 172, 173])
    fases_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#ffffff")),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(fases_table)

    story.append(PageBreak())

    # ==========================================
    # SEÇÃO 3: EXEMPLO PRÁTICO REAL (SCOOTER MAX12 / X13)
    # ==========================================
    story.append(Paragraph("3. Exemplo Prático Real com Dados da Planilha", h1_style))
    story.append(Paragraph(
        "Para ilustrar de forma tangível, vejamos o caso real da importação do lote de <strong>197 Scooters Elétricas Max12/X13 (NCM 8711.60.00)</strong>, comparando a venda intercompany versus venda direta ao PJ:",
        body_style
    ))

    # Tabela de Composição do Custo Unitário
    custo_data = [
        [Paragraph("Composição do Custo de Entrada — 1 Unidade da Scooter", table_header_style), Paragraph("Valor (R$)", table_header_style), Paragraph("Critério Aplicado", table_header_style)],
        [Paragraph("Valor do Produto na NF (com Frete Internacional)", table_cell_style), Paragraph("R$ 1.222,82", table_cell_right), Paragraph("Valor FOB proporcionalizado", table_cell_style)],
        [Paragraph("Imposto de Importação (II rateado)", table_cell_style), Paragraph("R$ 226,93", table_cell_right), Paragraph("Rateio proporcional ao valor (97,11%)", table_cell_style)],
        [Paragraph("PIS de Importação (rateado)", table_cell_style), Paragraph("R$ 25,74", table_cell_right), Paragraph("Crédito fiscal gerado", table_cell_style)],
        [Paragraph("COFINS de Importação (rateada)", table_cell_style), Paragraph("R$ 118,29", table_cell_right), Paragraph("Crédito fiscal gerado", table_cell_style)],
        [Paragraph("Outras Despesas Aduaneiras (AFRMM + Siscomex)", table_cell_style), Paragraph("R$ 17,33", table_cell_right), Paragraph("Despesas diretas no desembaraço", table_cell_style)],
        [Paragraph("IPI do Item (DANFE de Importação)", table_cell_style), Paragraph("R$ 505,03", table_cell_right), Paragraph("Crédito fiscal de IPI gerado", table_cell_style)],
        [Paragraph("ICMS de Importação (DANFE de Importação)", table_cell_style), Paragraph("R$ 287,60", table_cell_right), Paragraph("Crédito fiscal de ICMS gerado", table_cell_style)],
        [Paragraph("<strong>CUSTO UNITÁRIO TOTAL ATÉ A COLVIX</strong>", table_cell_bold), Paragraph("<strong>R$ 2.403,74</strong>", table_cell_right_bold), Paragraph("<strong>Base oficial para formação de preço</strong>", table_cell_bold)],
    ]
    custo_table = Table(custo_data, colWidths=[230, 95, 190])
    custo_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(custo_table)

    story.append(Spacer(1, 10))

    # ==========================================
    # SEÇÃO 4: A DECISÃO ESTRATÉGICA — VENDA M-ONE vs VENDA DIRETA PJ
    # ==========================================
    story.append(Paragraph("4. A Decisão Comercial: Venda para M-ONE vs Venda Direta PJ", h1_style))
    story.append(Paragraph(
        "Um dos pontos mais valiosos destacados pela controladoria é o <strong>tratamento do ICMS-ST (Substituição Tributária)</strong>. "
        "O simulador do M-One colocará lado a lado os dois cenários para cada negociação:",
        body_style
    ))

    comparativo_data = [
        [
            Paragraph("Métrica Operacional / Tributária", table_header_style),
            Paragraph("Cenário A: Venda COLVIX ➔ M-ONE", table_header_style),
            Paragraph("Cenário B: Venda COLVIX ➔ Cliente PJ Direto", table_header_style)
        ],
        [
            Paragraph("Preço de Venda Unitário (com 5% de margem)", table_cell_style),
            Paragraph("R$ 2.523,93", table_cell_right),
            Paragraph("R$ 2.523,93", table_cell_right)
        ],
        [
            Paragraph("Débito de ICMS Próprio (12%)", table_cell_style),
            Paragraph("R$ 302,87", table_cell_right),
            Paragraph("R$ 302,87", table_cell_right)
        ],
        [
            Paragraph("Débito de IPI (35% s/ Scooter)", table_cell_style),
            Paragraph("R$ 883,38", table_cell_right),
            Paragraph("R$ 883,38", table_cell_right)
        ],
        [
            Paragraph("PIS (1,65%) e COFINS (7,6%) Débito", table_cell_style),
            Paragraph("R$ 233,46", table_cell_right),
            Paragraph("R$ 233,46", table_cell_right)
        ],
        [
            Paragraph("<strong>ICMS-ST Retido na Operação</strong>", table_cell_bold),
            Paragraph("<strong style='color:#dc2626;'>R$ 244,79 (Retido pela M-ONE)</strong>", table_cell_right_bold),
            Paragraph("<strong style='color:#059669;'>R$ 0,00 (Recolhido pelo Cliente PJ)</strong>", table_cell_right_bold)
        ],
        [
            Paragraph("Compensação com Créditos da Importação", table_cell_style),
            Paragraph("Amortiza PIS, COFINS, IPI e ICMS de entrada", table_cell_style),
            Paragraph("Amortiza PIS, COFINS, IPI e ICMS de entrada", table_cell_style)
        ],
        [
            Paragraph("<strong>Impacto no Fluxo de Caixa do Grupo</strong>", table_cell_bold),
            Paragraph("Desembolso financeiro de ST retido dentro da M-ONE.", table_cell_style),
            Paragraph("<strong>Economia de caixa imediata de ICMS-ST no grupo.</strong>", table_cell_bold)
        ]
    ]
    comp_table = Table(comparativo_data, colWidths=[185, 165, 165])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0369a1")),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(comp_table)

    story.append(Spacer(1, 8))

    # Box de Destaque Estratégico
    callout_data = [[
        Paragraph(
            "💡 <strong>Conclusão Operacional Estratégica:</strong> Quando um cliente corporativo (PJ) comprar veículos ou peças da MAJ, "
            "o sistema alertará o comercial sobre a vantagem de emitir a venda diretamente pela <strong>COLVIX</strong>. "
            "Isso transfere a responsabilidade do recolhimento do ICMS-ST para o adquirente PJ, preservando o capital de giro da M-ONE.",
            ParagraphStyle("CalloutP", fontName="Helvetica", fontSize=8.5, leading=12, textColor=colors.HexColor("#065f46"))
        )
    ]]
    callout_table = Table(callout_data, colWidths=[515])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ecfdf5")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#6ee7b7")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(callout_table)

    story.append(PageBreak())

    # ==========================================
    # SEÇÃO 5: PRINCIPAIS FUNCIONALIDADES NO SISTEMA
    # ==========================================
    story.append(Paragraph("5. Funcionalidades Entregues no M-One", h1_style))

    func_data = [
        [
            Paragraph("<strong>1. Central de Entrada Multi-Formato</strong>", h2_style),
            Paragraph("<strong>2. Simulador Interativo em Tempo Real</strong>", h2_style)
        ],
        [
            Paragraph(
                "• Upload direto do <strong>XML da NF-e</strong> de importação.<br/>"
                "• Ou seleção de um processo de importação já cadastrado.<br/>"
                "• Ou upload de planilha Excel (.xlsx) no modelo padrão.<br/>"
                "• Preenchimento automático de itens, NCM, quantitativos e taxas.",
                card_text
            ),
            Paragraph(
                "• Ajuste dinâmico de margem (%) por produto.<br/>"
                "• Comparativo lado a lado imediato (M-ONE vs PJ).<br/>"
                "• Apuração em tempo real de imposto a pagar ou saldo credor.<br/>"
                "• Visualização clara do ICMS-ST e IPI gerados.",
                card_text
            )
        ],
        [
            Paragraph("<strong>3. Gestão de Saldos de Crédito Fiscal</strong>", h2_style),
            Paragraph("<strong>4. Espelho de Conferência para NF-e</strong>", h2_style)
        ],
        [
            Paragraph(
                "• Controle do saldo restante de créditos (PIS/COFINS/IPI/ICMS).<br/>"
                "• Modo flexível de simulação avulsa sem travar vendas.<br/>"
                "• Opção de vincular a vendas reais para abater créditos por lote.<br/>"
                "• Histórico de simulações e auditoria de consultas.",
                card_text
            ),
            Paragraph(
                "• Relatório espelho com bases de cálculo, alíquotas e tributos.<br/>"
                "• Conferência obrigatória antes da emissão definitiva no emissor.<br/>"
                "• Exportação do cálculo em PDF ou Excel para a contabilidade.<br/>"
                "• Redução a zero de divergências entre contabilidade e faturamento.",
                card_text
            )
        ]
    ]
    func_table = Table(func_data, colWidths=[255, 260])
    func_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(func_table)

    story.append(Spacer(1, 10))

    # ==========================================
    # SEÇÃO 6: BENEFÍCIOS PARA A DIRETORIA & PRÓXIMOS PASSOS
    # ==========================================
    story.append(Paragraph("6. Benefícios para a Gestão & Próximos Passos", h1_style))
    story.append(Paragraph("• <strong>Governança e Segurança Fiscal:</strong> Elimina erros manuais de cálculo e garante que toda venda utilize a base correta de custos e créditos.", bullet_style))
    story.append(Paragraph("• <strong>Agilidade Comercial:</strong> O time comercial e a diretoria conseguem precificar pedidos especiais em segundos, sabendo exatamente a margem líquida e o ICMS-ST de cada opção.", bullet_style))
    story.append(Paragraph("• <strong>Economia Tributária Concreta:</strong> Identificação clara de quando faturar pela COLVIX ou pela M-ONE para minimizar desembolsos fiscais.", bullet_style))
    story.append(Paragraph("• <strong>Lucro Real e Despesas Operacionais:</strong> O simulador contempla campo para 'Despesas Operacionais / Custos Adicionais' (%), calculando o Lucro Líquido Real de bolso após deduzir os 24% de IRPJ/CSLL sobre a base tributável.", bullet_style))

    story.append(Spacer(1, 14))

    # Assinatura e aprovação
    sign_data = [
        [
            Paragraph("____________________________________________<br/><strong>Administrador Solicitante</strong><br/>MAJ Mobilidade Elétrica", ParagraphStyle("S1", fontName="Helvetica", fontSize=8, alignment=1)),
            Paragraph("____________________________________________<br/><strong>Administrador Revisor / Diretoria</strong><br/>Aprovação de Implementação", ParagraphStyle("S2", fontName="Helvetica", fontSize=8, alignment=1))
        ]
    ]
    sign_table = Table(sign_data, colWidths=[255, 260])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(sign_table)

    doc.build(story, canvasmaker=NumberedCanvas)

    # Copiar para diretório de artefatos
    import shutil
    shutil.copyfile(PDF_OUTPUT_PATH, ARTIFACT_PDF_PATH)
    print(f"PDF gerado com sucesso em: {PDF_OUTPUT_PATH}")
    print(f"Cópia do artefato em: {ARTIFACT_PDF_PATH}")


if __name__ == "__main__":
    create_pdf()
