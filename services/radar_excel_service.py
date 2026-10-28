"""
M-One Radar Excel Export Service (services/radar_excel_service.py)
Geração de planilhas executivas Excel (.xlsx) multi-abas por cidade para o Radar de Mercado.
Segregação modular estrita (< 500 linhas).
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from database import db


def sanitizar_nome_aba(nome: str, abas_usadas: Set[str]) -> str:
    """Higieniza o nome da cidade para os limites do Excel (max 31 chars e sem caracteres proibidos)."""
    if not nome:
        nome = "Cidade"
    limpo = re.sub(r'[\\/*?:\[\]]', '', str(nome)).strip()
    limpo = limpo[:31] if len(limpo) > 31 else limpo
    if not limpo:
        limpo = "Cidade"
    
    base = limpo
    contador = 2
    while limpo in abas_usadas:
        sufixo = f"_{contador}"
        limpo = f"{base[:31-len(sufixo)]}{sufixo}"
        contador += 1

    abas_usadas.add(limpo)
    return limpo


def obter_metricas_cidade_export(cidade: str, apenas_wa: bool = False, status_filtro: str = "all") -> Dict[str, Any]:
    """Retorna métricas consolidadas da cidade para a aba de resumo."""
    where_clauses = ["cidade ILIKE %s"]
    params: List[Any] = [f"%{cidade.strip()}%"]

    if apenas_wa:
        where_clauses.append("(whatsapp IS NOT NULL OR telefone_google IS NOT NULL)")
    if status_filtro and status_filtro != "all":
        where_clauses.append("status_contato = %s")
        params.append(status_filtro)

    where_sql = " AND ".join(where_clauses)
    sql = f"""
        SELECT 
            COUNT(*) as total_lojas,
            COUNT(whatsapp) as total_wa,
            MAX(uf) as uf,
            COUNT(CASE WHEN status_contato = 'novo' THEN 1 END) as total_novo,
            COUNT(CASE WHEN status_contato = 'prospectado' THEN 1 END) as total_prospectado,
            COUNT(CASE WHEN status_contato = 'em_negociacao' THEN 1 END) as total_em_negociacao,
            COUNT(CASE WHEN status_contato = 'convertido' THEN 1 END) as total_convertido,
            COUNT(CASE WHEN status_contato = 'descartado' THEN 1 END) as total_descartado
        FROM prospeccao.leads
        WHERE {where_sql};
    """
    with db() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else {
            "total_lojas": 0, "total_wa": 0, "uf": "ES",
            "total_novo": 0, "total_prospectado": 0, "total_em_negociacao": 0,
            "total_convertido": 0, "total_descartado": 0
        }


def buscar_leads_cidade_export(cidade: str, apenas_wa: bool = False, status_filtro: str = "all") -> List[Dict[str, Any]]:
    """Busca todos os leads pertencentes à cidade respeitando os filtros."""
    where_clauses = ["cidade ILIKE %s"]
    params: List[Any] = [f"%{cidade.strip()}%"]

    if apenas_wa:
        where_clauses.append("(whatsapp IS NOT NULL OR telefone_google IS NOT NULL)")
    if status_filtro and status_filtro != "all":
        where_clauses.append("status_contato = %s")
        params.append(status_filtro)

    where_sql = " AND ".join(where_clauses)
    sql = f"""
        SELECT *
        FROM prospeccao.leads
        WHERE {where_sql}
        ORDER BY score DESC, nome ASC
        LIMIT 5000;
    """
    with db() as conn:
        rows = conn.execute(sql, params).fetchall() or []
        return [dict(r) for r in rows]


def gerar_planilha_radar_multi_abas(
    cidades_selecionadas: List[str],
    apenas_wa: bool = False,
    status_filtro: str = "all"
) -> io.BytesIO:
    """
    Cria uma pasta de trabalho Excel (.xlsx) contendo:
    1. Aba de Resumo Executivo Geral consolidando as cidades.
    2. Uma aba detalhada individual para cada cidade selecionada.
    """
    wb = openpyxl.Workbook()
    abas_usadas: Set[str] = set()

    # Estilos Padronizados M-One
    font_titulo = Font(name="Calibri", size=14, bold=True, color="0F172A")
    font_subtitulo = Font(name="Calibri", size=9.5, italic=True, color="64748B")
    font_cabecalho = Font(name="Calibri", size=10.5, bold=True, color="FFFFFF")
    font_dados = Font(name="Calibri", size=10, color="0F172A")
    font_link = Font(name="Calibri", size=10, color="0070F3", underline="single")
    font_total = Font(name="Calibri", size=10.5, bold=True, color="0F172A")

    fill_cabecalho_geral = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    fill_cabecalho_cidade = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_total = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    borda_fina = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )
    borda_dupla_total = Border(
        top=Side(style="thin", color="0F172A"),
        bottom=Side(style="double", color="0F172A"),
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1")
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    # =========================================================================
    # 1. ABA DE RESUMO GERAL
    # =========================================================================
    ws_resumo = wb.active
    ws_resumo.title = sanitizar_nome_aba("Resumo Geral", abas_usadas)
    ws_resumo.views.sheetView[0].showGridLines = True

    # Bloco de Cabeçalho do Documento
    ws_resumo["A1"] = "M-ONE RADAR DE MERCADO — RELATÓRIO EXECUTIVO DE LEADS"
    ws_resumo["A1"].font = font_titulo
    
    agora_fmt = datetime.now().strftime("%d/%m/%Y às %H:%M")
    filtro_desc = []
    if apenas_wa:
        filtro_desc.append("Apenas contatos com WhatsApp")
    if status_filtro and status_filtro != "all":
        filtro_desc.append(f"Status: {status_filtro.title()}")
    filtro_txt = " • ".join(filtro_desc) if filtro_desc else "Todos os leads mapeados"
    
    ws_resumo["A2"] = f"Extração gerada em {agora_fmt} | Filtros: {filtro_txt}"
    ws_resumo["A2"].font = font_subtitulo

    # Cabeçalho da Tabela de Resumo
    headers_resumo = [
        "Cidade", "UF", "Total Lojas", "Com WhatsApp", "% WhatsApp",
        "Novos", "Prospectados", "Em Negociação", "Convertidos", "Descartados"
    ]
    row_idx = 4
    for col_idx, h in enumerate(headers_resumo, start=1):
        cell = ws_resumo.cell(row=row_idx, column=col_idx, value=h)
        cell.font = font_cabecalho
        cell.fill = fill_cabecalho_geral
        cell.alignment = align_center if col_idx > 1 else align_left
        cell.border = borda_fina
    ws_resumo.row_dimensions[row_idx].height = 24

    totais_resumo = {
        "lojas": 0, "wa": 0, "novos": 0, "prospectados": 0,
        "negociacao": 0, "convertidos": 0, "descartados": 0
    }

    # Linhas de Dados das Cidades
    for cidade in cidades_selecionadas:
        row_idx += 1
        m = obter_metricas_cidade_export(cidade, apenas_wa=apenas_wa, status_filtro=status_filtro)
        total_lojas = m.get("total_lojas", 0)
        total_wa = m.get("total_wa", 0)
        uf = m.get("uf", "ES") or "ES"
        pct_wa = f"{(total_wa / total_lojas * 100):.1f}%" if total_lojas > 0 else "0.0%"

        totais_resumo["lojas"] += total_lojas
        totais_resumo["wa"] += total_wa
        totais_resumo["novos"] += m.get("total_novo", 0)
        totais_resumo["prospectados"] += m.get("total_prospectado", 0)
        totais_resumo["negociacao"] += m.get("total_em_negociacao", 0)
        totais_resumo["convertidos"] += m.get("total_convertido", 0)
        totais_resumo["descartados"] += m.get("total_descartado", 0)

        dados_linha = [
            cidade, uf, total_lojas, total_wa, pct_wa,
            m.get("total_novo", 0), m.get("total_prospectado", 0),
            m.get("total_em_negociacao", 0), m.get("total_convertido", 0),
            m.get("total_descartado", 0)
        ]

        for col_idx, val in enumerate(dados_linha, start=1):
            cell = ws_resumo.cell(row=row_idx, column=col_idx, value=val)
            cell.font = font_dados
            cell.border = borda_fina
            cell.alignment = align_left if col_idx == 1 else align_center
            if row_idx % 2 == 1:
                cell.fill = fill_zebra
        ws_resumo.row_dimensions[row_idx].height = 20

    # Linha Totalizadora
    row_idx += 1
    pct_total_wa = f"{(totais_resumo['wa'] / totais_resumo['lojas'] * 100):.1f}%" if totais_resumo["lojas"] > 0 else "0.0%"
    totais_linha = [
        "TOTAL CONSOLIDADO", "-", totais_resumo["lojas"], totais_resumo["wa"], pct_total_wa,
        totais_resumo["novos"], totais_resumo["prospectados"], totais_resumo["negociacao"],
        totais_resumo["convertidos"], totais_resumo["descartados"]
    ]
    for col_idx, val in enumerate(totais_linha, start=1):
        cell = ws_resumo.cell(row=row_idx, column=col_idx, value=val)
        cell.font = font_total
        cell.fill = fill_total
        cell.border = borda_dupla_total
        cell.alignment = align_left if col_idx == 1 else align_center
    ws_resumo.row_dimensions[row_idx].height = 22

    # Auto-ajuste de colunas do Resumo
    for col in ws_resumo.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(c.value or '')) for c in col)
        ws_resumo.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # =========================================================================
    # 2. ABAS INDIVIDUAIS POR CIDADE
    # =========================================================================
    colunas_cidade = [
        "Classe", "Score", "Nome Comercial (Loja)", "Razão Social", "CNPJ",
        "Decisor / Sócio", "Cargo", "WhatsApp", "Telefone Fixo", "E-mail",
        "Cidade", "UF", "Endereço", "Site Oficial", "Instagram",
        "Google Maps", "Status", "Gancho Comercial IA"
    ]

    for cidade in cidades_selecionadas:
        nome_aba = sanitizar_nome_aba(cidade, abas_usadas)
        ws = wb.create_sheet(title=nome_aba)
        ws.views.sheetView[0].showGridLines = True

        # Título da Cidade
        ws["A1"] = f"LEADS: {cidade.upper()}"
        ws["A1"].font = font_titulo
        leads = buscar_leads_cidade_export(cidade, apenas_wa=apenas_wa, status_filtro=status_filtro)
        ws["A2"] = f"Total de {len(leads)} lojas catalogadas | Exportado do M-One em {agora_fmt}"
        ws["A2"].font = font_subtitulo

        # Cabeçalho da Tabela
        r_idx = 4
        for c_idx, h in enumerate(colunas_cidade, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=h)
            cell.font = font_cabecalho
            cell.fill = fill_cabecalho_cidade
            cell.alignment = align_center if c_idx in (1, 2, 8, 9, 12, 17) else align_left
            cell.border = borda_fina
        ws.row_dimensions[r_idx].height = 24

        # Linhas de Leads
        for l in leads:
            r_idx += 1
            wa_num = str(l.get("whatsapp") or "").strip()
            site_url = str(l.get("site") or "").strip()
            insta_url = str(l.get("instagram") or "").strip()
            maps_url = str(l.get("google_maps_url") or "").strip()

            linha_lead = [
                l.get("classificacao", "-"),
                l.get("score", 0),
                l.get("nome", ""),
                l.get("razao_social", ""),
                l.get("cnpj", ""),
                l.get("decisor_nome", ""),
                l.get("decisor_cargo", ""),
                wa_num,
                l.get("telefone_google", ""),
                l.get("email", ""),
                l.get("cidade", cidade),
                l.get("uf", "ES"),
                l.get("endereco", ""),
                site_url,
                insta_url,
                maps_url,
                (l.get("status_contato") or "novo").replace("_", " ").title(),
                l.get("gancho_comercial", "")
            ]

            for c_idx, val in enumerate(linha_lead, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                cell.font = font_dados
                cell.border = borda_fina
                cell.alignment = align_center if c_idx in (1, 2, 8, 9, 12, 17) else align_left
                if r_idx % 2 == 1:
                    cell.fill = fill_zebra

                # Links interativos para WhatsApp e Canais Digitais
                if c_idx == 8 and wa_num:
                    clean_wa = re.sub(r'\D', '', wa_num)
                    cell.hyperlink = f"https://wa.me/{clean_wa}"
                    cell.font = font_link
                    try:
                        cell.hyperlink.tooltip = "Clique para abrir conversa no WhatsApp"
                    except Exception:
                        pass
                elif c_idx == 14 and site_url and site_url.startswith("http"):
                    cell.hyperlink = site_url
                    cell.font = font_link
                elif c_idx == 15 and insta_url and ("instagram" in insta_url or insta_url.startswith("http")):
                    cell.hyperlink = insta_url if insta_url.startswith("http") else f"https://{insta_url}"
                    cell.font = font_link
                elif c_idx == 16 and maps_url and maps_url.startswith("http"):
                    cell.hyperlink = maps_url
                    cell.font = font_link

            ws.row_dimensions[r_idx].height = 20

        # Auto-ajuste de colunas
        for col in ws.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = 0
            for c in col:
                val_str = str(c.value or '')
                if len(val_str) > max_len:
                    max_len = len(val_str)
            # Limita largura razoável para textos longos (ex: gancho comercial)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 11), 50)

    # Serialização para BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
