"""
M-One Freight Google Drive & Google Sheets Sync Service (services/freight_google_drive_sync_service.py)
Serviço autônomo para exportar tarifas, converter para Google Planilhas no Drive oficial da MAJ
e manter permissões de leitura pública ativa para auditoria dos operadores.
"""

from __future__ import annotations

import datetime
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from database import db
from routes.helpers import UPLOAD_DIR

logger = logging.getLogger(__name__)

# ID da pasta 'TRASPORTADORAS CADASTRADAS' no Google Drive oficial da MAJ (marketingmajv@gmail.com)
DRIVE_CARRIERS_FOLDER_ID = "14XfE6rwzcritiWCQZcx9WsWPo_jZDgKr"


def find_gdrive_binary() -> Optional[str]:
    """Localiza o binário do gdrive no PATH do sistema ou nos plugins instalados."""
    cand = shutil.which("gdrive")
    if cand:
        return cand
    
    # Busca em caminhos conhecidos de plugins do Antigravity
    known_paths = [
        "/Users/macstudio-maj/.gemini/config/plugins/gdrive/skills/gdrive/scripts/gdrive",
        "/var/folders/hy/rrsjg_m57rx2vf7blc29044w0000gn/T/agy-plugin-cli-4164611089/gdrive",
    ]
    for p_str in known_paths:
        p = Path(p_str)
        if p.exists() and p.is_file():
            return str(p)
    return None


def export_rates_to_excel(table_id: int, target_path: Optional[Path] = None) -> Optional[Path]:
    """Gera uma planilha Excel oficial (.xlsx) estruturada e estilizada a partir das taxas do banco."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    with db() as conn:
        t_cur = conn.execute(
            """SELECT t.id, t.name AS table_name, t.origin_city, t.cubing_factor,
                      t.tec_percent, t.tas_fixed, t.pos_fixed, t.min_gris_value,
                      c.name AS carrier_name, c.trade_name, c.phone, c.sales_rep_name
               FROM freight_tables t
               JOIN carriers c ON c.id = t.carrier_id
               WHERE t.id = %s""",
            (table_id,)
        )
        t_info = t_cur.fetchone()
        if not t_info:
            logger.error("Tabela de frete ID %s não encontrada.", table_id)
            return None

        r_cur = conn.execute(
            """SELECT uf, city, cep_start, cep_end, min_weight, max_weight,
                      fixed_price, weight_price_per_kg, ad_valorem_percent,
                      gris_percent, delivery_days, notes
               FROM freight_rates
               WHERE table_id = %s
               ORDER BY uf ASC, city ASC, min_weight ASC""",
            (table_id,)
        )
        rates = r_cur.fetchall()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tarifas e Prazos"

    # Estilos
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    meta_font = Font(name="Calibri", size=10, bold=True, color="1E293B")
    data_font = Font(name="Calibri", size=10)
    border_thin = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # Bloco de Metadados
    ws.append(["M-ONE MAJ MOBILIDADE — TABELA OFICIAL DE FRETE"])
    ws.cell(row=1, column=1).font = Font(name="Calibri", size=14, bold=True, color="0F172A")
    ws.append([f"Transportadora: {t_info['carrier_name']} ({t_info['trade_name'] or t_info['carrier_name']})"])
    ws.cell(row=2, column=1).font = meta_font
    ws.append([f"Tabela: {t_info['table_name']} | Origem: {t_info['origin_city'] or 'Cariacica'}/ES | Cubagem: {float(t_info['cubing_factor'] or 300):.0f} kg/m³"])
    ws.append([f"Taxas Acessórias: TEC {float(t_info['tec_percent'] or 0):.2f}% | TAS R$ {float(t_info['tas_fixed'] or 0):.2f} | Pedágio/POS R$ {float(t_info['pos_fixed'] or 0):.2f} | GRIS Mín R$ {float(t_info['min_gris_value'] or 0):.2f}"])
    ws.append([f"Atendimento Comercial: {t_info['sales_rep_name'] or 'Comercial'} — Tel: {t_info['phone'] or 'Não informado'} | Total Regras: {len(rates)}"])
    ws.append([])  # Linha vazia

    # Cabeçalho da Tabela
    headers = [
        "UF", "Cidade / Praça", "CEP Inicial", "CEP Final",
        "Peso Até (kg)", "Frete Fixo (R$)", "Excedente/kg (R$)",
        "Ad-Valorem %", "GRIS %", "Prazo SLA (dias)", "Observações"
    ]
    ws.append(headers)
    header_row_idx = 7

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Linhas de Dados
    for r in rates:
        row_vals = [
            r["uf"] or "",
            r["city"] or "Padrão",
            r["cep_start"] or "",
            r["cep_end"] or "",
            float(r["max_weight"] or 0.0),
            float(r["fixed_price"] or 0.0),
            float(r["weight_price_per_kg"] or 0.0),
            float(r["ad_valorem_percent"] or 0.0),
            float(r["gris_percent"] or 0.0),
            int(r["delivery_days"] or 1),
            r["notes"] or ""
        ]
        ws.append(row_vals)
        cur_row = ws.max_row
        for col_idx in range(1, len(row_vals) + 1):
            c = ws.cell(row=cur_row, column=col_idx)
            c.font = data_font
            c.border = border_thin
            if col_idx in [5, 6, 7, 8, 9, 10]:
                c.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in [1, 3, 4]:
                c.alignment = Alignment(horizontal="center", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center")

    # Ajuste automático de largura das colunas
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 10)

    slug = re.sub(r"[^a-z0-9]+", "_", str(t_info["carrier_name"]).lower()).strip("_")
    if not target_path:
        target_path = UPLOAD_DIR / f"freight_{slug}_oficial.xlsx"

    wb.save(str(target_path))
    logger.info("Planilha Excel gerada com sucesso: %s (%s regras)", target_path, len(rates))
    return target_path


def upload_and_share_google_sheet(file_path: Path, sheet_title: str) -> Optional[str]:
    """Faz upload da planilha para o Google Drive oficial da MAJ convertendo em Google Planilhas e libera link leitor."""
    gdrive_bin = find_gdrive_binary()
    if not gdrive_bin:
        logger.warning("Binário do gdrive não encontrado. Upload para o Google Drive ignorado.")
        return None

    try:
        # 1. Upload e conversão automática para Google Planilhas
        cmd_upload = [
            gdrive_bin, "mutate", "upload",
            str(file_path),
            "--mime-type", "application/vnd.google-apps.spreadsheet",
            "--parent", DRIVE_CARRIERS_FOLDER_ID
        ]
        res_up = subprocess.run(cmd_upload, capture_output=True, text=True, check=True)
        m = re.search(r"\(ID:\s*([A-Za-z0-9_-]+)\)", res_up.stdout)
        if not m:
            logger.error("Não foi possível capturar o ID do arquivo no retorno: %s", res_up.stdout)
            return None
        
        file_id = m.group(1)

        # 2. Renomeia com o padrão executivo MAJ
        subprocess.run([gdrive_bin, "mutate", "rename", file_id, sheet_title], capture_output=True, text=True)

        # 3. Libera acesso como leitor para qualquer pessoa com o link
        subprocess.run([gdrive_bin, "mutate", "share", file_id, "--type", "anyone", "--role", "reader"], capture_output=True, text=True)

        sheet_url = f"https://docs.google.com/spreadsheets/d/{file_id}/edit?usp=drivesdk"
        logger.info("Google Planilha criada e compartilhada: %s (ID: %s)", sheet_title, file_id)
        return sheet_url
    except Exception as e:
        logger.error("Erro ao subir planilha para o Google Drive via gdrive: %s", e)
        return None


def auto_create_and_link_google_sheet(
    table_id: int,
    carrier_name: str,
    table_name: str,
    uploaded_paths: Optional[list[Path]] = None
) -> Optional[str]:
    """
    Fluxo autônomo completo:
    Pega os documentos importados pela IA (ou gera um Excel padronizado das regras no banco),
    envia ao Google Drive da MAJ, cria o Google Planilhas, libera permissão pública e salva a URL.
    """
    date_str = datetime.datetime.now().strftime("%d%m%y")
    slug = re.sub(r"[^a-z0-9]+", "_", carrier_name.lower()).strip("_")
    sheet_title = f"FRETE_{slug}_oficial - {date_str}"

    # 1. Identificar se há um arquivo Excel de origem ou gerar um oficial a partir das taxas do banco
    xlsx_to_upload = None
    if uploaded_paths:
        for p in uploaded_paths:
            if p.suffix.lower() in [".xlsx", ".xls", ".csv"] and p.exists():
                xlsx_to_upload = p
                break

    if not xlsx_to_upload:
        # Se foi apenas PDF ou texto, gera o Excel padronizado com todas as taxas extraídas pela IA
        xlsx_to_upload = export_rates_to_excel(table_id)

    if not xlsx_to_upload or not xlsx_to_upload.exists():
        logger.warning("Nenhum arquivo Excel disponível para sincronização com o Google Drive.")
        return None

    # 2. Upload para o Google Drive e geração do link
    sheet_url = upload_and_share_google_sheet(xlsx_to_upload, sheet_title)
    if not sheet_url:
        return None

    # 3. Gravação e commit no banco de dados Supabase
    with db() as conn:
        conn.execute("UPDATE freight_tables SET file_url = %s WHERE id = %s", (sheet_url, table_id))
        if hasattr(conn, "commit"):
            conn.commit()

    logger.info("Tabela ID %s atualizada com o link oficial do Google Planilhas: %s", table_id, sheet_url)
    return sheet_url
