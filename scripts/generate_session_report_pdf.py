"""
Script gerador do Relatório Executivo em PDF da sessão M-One (11/09/2026).
Gera documento diagramado profissionalmente com ReportLab.
"""

import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

PDF_OUTPUT_PATH = "/Users/macstudio-maj/Documents/Desenvolvimento/Aplicativos/MOne/relatorio_sessao_2026-09-11.pdf"
ARTIFACT_DIR = "/Users/macstudio-maj/.gemini/antigravity-ide/brain/0ab92a19-2abf-4663-a882-8a105cbe882f"
ARTIFACT_PDF_PATH = os.path.join(ARTIFACT_DIR, "relatorio_sessao_2026-09-11.pdf")


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
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "M-One • MAJ Operating System — Relatório Executivo de Engenharia")
            self.setStrokeColor(colors.HexColor("#334155"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)

        # Footer
        footer_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(558, 36, footer_text)
        self.drawString(54, 36, "MAJ Mobilidade Elétrica — Confidencial & Uso Interno")
        self.setStrokeColor(colors.HexColor("#334155"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        self.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        PDF_OUTPUT_PATH,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#0284c7")
    dark_bg = colors.HexColor("#0f172a")
    accent_green = colors.HexColor("#10b981")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0369a1"),
        spaceBefore=14,
        spaceAfter=6,
    )

    h3_style = ParagraphStyle(
        "Heading3_Custom",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    callout_style = ParagraphStyle(
        "Callout",
        parent=body_style,
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0f766e"),
    )

    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0f172a"),
    )

    table_cell_header = ParagraphStyle(
        "TableHeader",
        parent=table_cell,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    story = []

    # Document Header Box
    header_data = [
        [
            Paragraph("<b>M-ONE (MAJ OPERATING SYSTEM)</b>", ParagraphStyle("HdrB", parent=table_cell_header, fontSize=13, leading=16)),
            Paragraph("<b>RELATÓRIO DE ENGENHARIA</b>", ParagraphStyle("HdrR", parent=table_cell_header, alignment=2, fontSize=9, leading=12))
        ],
        [
            Paragraph("Sessão de Implementação: Arquitetura Autônoma, Permissões & RBAC", ParagraphStyle("HdrSub", parent=table_cell_header, fontSize=9, textColor=colors.HexColor("#93c5fd"))),
            Paragraph("Data: 11/09/2026", ParagraphStyle("HdrDate", parent=table_cell_header, alignment=2, fontSize=8.5, textColor=colors.HexColor("#bfdbfe")))
        ]
    ]
    hdr_table = Table(header_data, colWidths=[360, 144])
    hdr_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 10),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 14))

    # Executive Summary
    story.append(Paragraph("1. Resumo Executivo da Sessão", h2_style))
    story.append(Paragraph(
        "Nesta sessão de trabalho, foram atingidos marcos estratégicos e de infraestrutura fundamentais para o M-One. "
        "A MAJ Mobilidade Elétrica alcançou a <b>completa autonomia operacional</b> no ecossistema de WhatsApp, eliminando "
        "a dependência e os custos de ferramentas SaaS de terceiros (como Botconversa). Em paralelo, a governança de acesso "
        "foi refinada com a promoção de Fauzer a Administrador, a disponibilização do Copilot IA para a equipe comercial, "
        "o isolamento de visualização de vendas e a criação de um painel de permissões granulares por colaborador.",
        body_style
    ))

    # Key Milestones Table
    story.append(Spacer(1, 6))
    milestones = [
        [
            Paragraph("Módulo / Iniciativa", table_cell_header),
            Paragraph("Tipo", table_cell_header),
            Paragraph("Impacto Estratégico", table_cell_header),
            Paragraph("Status", table_cell_header)
        ],
        [
            Paragraph("<b>Padronização de Nomenclatura</b>", table_cell_bold),
            Paragraph("Identidade", table_cell),
            Paragraph("Transição oficial e auditada de Jean para Jam em todo o banco e código.", table_cell),
            Paragraph("<font color='#059669'><b>Concluído</b></font>", table_cell)
        ],
        [
            Paragraph("<b>WhatsApp Autônomo (Evolution)</b>", table_cell_bold),
            Paragraph("Infraestrutura", table_cell),
            Paragraph("Microserviço open-source próprio de conexão via QR Code sem SaaS intermediário.", table_cell),
            Paragraph("<font color='#059669'><b>Concluído</b></font>", table_cell)
        ],
        [
            Paragraph("<b>Transcrição de Áudio Groq IA</b>", table_cell_bold),
            Paragraph("Inteligência", table_cell),
            Paragraph("Transcrição de notas de voz em milissegundos (~300ms) em PT-BR para auditoria.", table_cell),
            Paragraph("<font color='#059669'><b>Concluído</b></font>", table_cell)
        ],
        [
            Paragraph("<b>Promoção de Administrador</b>", table_cell_bold),
            Paragraph("Governança", table_cell),
            Paragraph("Fauzer promovido a Administrador pleno junto a Jam no Supabase e RBAC.", table_cell),
            Paragraph("<font color='#059669'><b>Concluído</b></font>", table_cell)
        ],
        [
            Paragraph("<b>Painel de Permissões (/users)</b>", table_cell_bold),
            Paragraph("Gestão", table_cell),
            Paragraph("Controle granular de ativação de módulos específicos por vendedor.", table_cell),
            Paragraph("<font color='#059669'><b>Concluído</b></font>", table_cell)
        ],
        [
            Paragraph("<b>Canal WhatsApp no Perfil</b>", table_cell_bold),
            Paragraph("Usabilidade", table_cell),
            Paragraph("Pareamento de QR Code diretamente no rodapé da sidebar de cada vendedor.", table_cell),
            Paragraph("<font color='#059669'><b>Concluído</b></font>", table_cell)
        ],
        [
            Paragraph("<b>Isolamento de Vendas</b>", table_cell_bold),
            Paragraph("Privacidade", table_cell),
            Paragraph("Vendedores enxergam apenas suas vendas pessoais; gestores enxergam tudo.", table_cell),
            Paragraph("<font color='#059669'><b>Concluído</b></font>", table_cell)
        ],
    ]
    t_milestones = Table(milestones, colWidths=[120, 75, 235, 74])
    t_milestones.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0284c7")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_milestones)

    story.append(Spacer(1, 14))

    # Section 2: Detalhamento Técnico
    story.append(Paragraph("2. Detalhamento das Entregas Técnicas", h2_style))

    story.append(Paragraph("2.1 Arquitetura Autônoma de WhatsApp (Espelho Auditor Passivo)", h3_style))
    story.append(Paragraph(
        "A empresa não depende mais do Botconversa para capturar atendimentos. Implementamos o modelo "
        "<b>Espelho Auditor Passivo</b> através de um microserviço dedicado baseado na <b>Evolution API (open-source)</b>. "
        "Os vendedores continuam atendendo seus clientes pelo aplicativo WhatsApp em seus celulares normalmente, "
        "enquanto o M-One espelha 100% dos eventos através do endpoint <code>/webhook/evolution</code>:",
        body_style
    ))
    story.append(Paragraph("• <b>MESSAGES_UPSERT</b>: Captura mensagens de texto, mídias e notas de voz (inbound e outbound), catalogando automaticamente o lead no CRM e o histórico em <code>whatsapp_messages</code>.", bullet_style))
    story.append(Paragraph("• <b>CONNECTION_UPDATE</b>: Sincroniza em tempo real o status da conexão da linha e o nível de bateria do smartphone do vendedor.", bullet_style))
    story.append(Paragraph("• <b>Transcrição Groq Whisper</b>: Mensagens de áudio são decodificadas e transcritas instantaneamente via IA (modelo <code>whisper-large-v3-turbo</code>), permitindo que o Copilot do Analisador de Chats leia e audite as falas da equipe.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(PageBreak())
    story.append(Paragraph("2.2 Matriz de Governança e Permissões da Barra Lateral", h3_style))
    story.append(Paragraph(
        "Para garantir foco operacional aos vendedores e resguardar dados sigilosos e relatórios estratégicos, "
        "a barra lateral foi reestruturada conforme a matriz abaixo:",
        body_style
    ))

    sidebar_data = [
        [Paragraph("Item da Barra Lateral", table_cell_header), Paragraph("Gestores (Admin/Suporte)", table_cell_header), Paragraph("Vendedores (Comercial)", table_cell_header), Paragraph("Regra de Negócio", table_cell_header)],
        [Paragraph("<b>Visão geral</b>", table_cell), Paragraph("🟢 Total da Empresa", table_cell), Paragraph("🟡 Apenas suas vendas", table_cell), Paragraph("Vendedor não vê faturamento global ou pagamentos.", table_cell)],
        [Paragraph("<b>Vendas</b>", table_cell), Paragraph("🟢 Todas as vendas", table_cell), Paragraph("🟡 Apenas suas vendas", table_cell), Paragraph("Gestores auditam e cancelam; vendedor cadastra as suas.", table_cell)],
        [Paragraph("<b>CRM & WhatsApp</b>", table_cell), Paragraph("🟢 Acesso Total", table_cell), Paragraph("🔴 Oculto (personalizável)", table_cell), Paragraph("Monitor ao vivo reservado para gestão comercial.", table_cell)],
        [Paragraph("<b>Análise de Chats</b>", table_cell), Paragraph("🟢 Acesso Total", table_cell), Paragraph("🔴 Oculto (personalizável)", table_cell), Paragraph("Auditoria IA e scoring executivo restrito a Jam e Fauzer.", table_cell)],
        [Paragraph("<b>Copilot IA</b>", table_cell), Paragraph("🟢 Acesso Total", table_cell), Paragraph("🟢 Assistente Comercial", table_cell), Paragraph("Apoia o vendedor na redação de mensagens e produtos.", table_cell)],
        [Paragraph("<b>Fretes</b>", table_cell), Paragraph("🟢 Acesso Total", table_cell), Paragraph("🟢 Cotador Liberado", table_cell), Paragraph("Ferramenta operacional diária de cotações.", table_cell)],
        [Paragraph("<b>Estoque / Chassis</b>", table_cell), Paragraph("🟢 Gestão & Lotes", table_cell), Paragraph("🟢 Consulta Liberada", table_cell), Paragraph("Vendedor consulta chassis liberados para venda.", table_cell)],
        [Paragraph("<b>Produtos / Preços</b>", table_cell), Paragraph("🟢 Gestão Total", table_cell), Paragraph("🔴 Oculto (personalizável)", table_cell), Paragraph("Custos e margens sigilosos protegidos.", table_cell)],
        [Paragraph("<b>Gestão (Import/Finan/Users)</b>", table_cell), Paragraph("🟢 Acesso Total", table_cell), Paragraph("🔴 Bloqueado", table_cell), Paragraph("Módulos sensíveis restritos à Diretoria.", table_cell)],
        [Paragraph("<b>Meu Perfil / WhatsApp</b>", table_cell), Paragraph("🟢 Acesso Total", table_cell), Paragraph("🟢 Canal QR Code", table_cell), Paragraph("Acessível no rodapé da sidebar de qualquer usuário.", table_cell)],
    ]
    t_sidebar = Table(sidebar_data, colWidths=[120, 110, 110, 164])
    t_sidebar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ('PADDING', (0, 0), (-1, -1), 4.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_sidebar)

    story.append(Spacer(1, 14))

    # Section 3: Qualidade e Auditoria Anti-Monólito
    story.append(Paragraph("3. Engenharia, Qualidade e Auditoria Anti-Monólito", h2_style))
    story.append(Paragraph(
        "Todas as adições foram desenvolvidas em conformidade com as rigorosas diretrizes do projeto M-One:",
        body_style
    ))
    story.append(Paragraph("• <b>Testes Automatizados (5/5 OK)</b>: Cobertura completa de empacotamento RFC multipart/form-data, tolerância a falhas na transcrição, persistência de configuração e eventos de webhook.", bullet_style))
    story.append(Paragraph("• <b>Validação de Integridade</b>: Execução do script <code>scripts/validate.py</code> com 100% de aprovação em sintaxe Python, templates Jinja2 e conexão com o pooler IPv4 do Supabase.", bullet_style))
    story.append(Paragraph("• <b>Auditoria Anti-Monólito (< 500 linhas)</b>: Graças à extração cirúrgica de componentes parciais (<code>chat_analyzer_lines.html</code>, <code>connections_evolution_tab.html</code>, <code>crm_whatsapp_modal.html</code>, <code>profile_modal.html</code> e <code>user_permissions_modal.html</code>), o arquivo crítico <code>chat_analyzer.html</code> foi reduzido de 497 para <b>445 linhas</b>, e todos os arquivos permanecem bem abaixo do limite máximo.", bullet_style))

    story.append(Spacer(1, 16))

    # Sign-off box
    sign_data = [
        [
            Paragraph("<b>Aprovado por:</b><br/>Jam Penitenti — Diretoria Executiva<br/>Fauzer — Diretoria / Tecnologia", table_cell),
            Paragraph("<b>Engenharia de Software:</b><br/>Antigravity AI Assistant<br/>MAJ Mobilidade Elétrica", table_cell_bold),
            Paragraph("<b>Ambiente:</b><br/>Produção: m-one.majmobilidade.com.br<br/>Local: localhost:5001", table_cell)
        ]
    ]
    sign_table = Table(sign_data, colWidths=[180, 170, 154])
    sign_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(sign_table)

    doc.build(story, canvasmaker=NumberedCanvas)

    # Copiar também para o diretório de artefatos
    import shutil
    shutil.copy2(PDF_OUTPUT_PATH, ARTIFACT_PDF_PATH)
    print(f"PDF gerado com sucesso em: {PDF_OUTPUT_PATH}")
    print(f"PDF copiado para artefatos em: {ARTIFACT_PDF_PATH}")


if __name__ == "__main__":
    build_pdf()
