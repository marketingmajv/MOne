"""
M-One Prospector Export & Integration Service (services/prospector_export_service.py)
Gerencia a sincronização com Google Sheets via Webhook Apps Script
e a exportação de dados padronizados para o Meta Ads (Lookalike / Custom Audiences).
Segregação estrita modular (< 500 linhas).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services.prospector_service import get_prospector_config, set_prospector_config

logger = logging.getLogger(__name__)


def get_sheets_webhook_url() -> str:
    """Retorna a URL do Google Apps Script configurada."""
    return get_prospector_config("sheets_webhook_url", "")


def set_sheets_webhook_url(url: str) -> None:
    """Grava a URL do Google Apps Script."""
    set_prospector_config("sheets_webhook_url", url, "URL do Webhook do Google Apps Script para a Planilha de Leads")


# -------------------------------------------------------------------------
# 1. SINCRONIZAÇÃO COM GOOGLE SHEETS (APPS SCRIPT WEBHOOK)
# -------------------------------------------------------------------------

def formatar_lead_para_sheets(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Formata colunas estruturadas para a planilha de trabalho da equipe de vendas."""
    socios = lead.get("socios") or []
    if isinstance(socios, str):
        try:
            socios = json.loads(socios)
        except Exception:
            socios = []
    socios_str = ", ".join([s.get("nome_socio") or s.get("nome") or "" for s in socios[:3] if s])

    emails = lead.get("emails") or []
    if isinstance(emails, str):
        emails = [emails]

    return {
        "id": str(lead.get("id")),
        "data_captura": str(lead.get("created_at") or "")[:10],
        "nicho": lead.get("nicho_slug"),
        "empresa": lead.get("nome_fantasia") or lead.get("nome"),
        "razao_social": lead.get("razao_social") or "",
        "decisor": lead.get("decisor_nome") or "",
        "decisor_cargo": lead.get("decisor_cargo") or "",
        "outros_socios": socios_str,
        "whatsapp": lead.get("whatsapp") or lead.get("telefone_google") or "",
        "email": lead.get("email") or (emails[0] if emails else ""),
        "site": lead.get("site") or "",
        "instagram": lead.get("instagram") or "",
        "cnpj": lead.get("cnpj") or "",
        "porte": lead.get("porte") or lead.get("porte_estimado") or "",
        "cidade": lead.get("cidade") or "",
        "uf": lead.get("uf") or "",
        "endereco": lead.get("endereco") or "",
        "score": lead.get("score") or 0,
        "classe": lead.get("classificacao") or "D",
        "resumo_ia": lead.get("resumo_ia") or "",
        "gancho_comercial": lead.get("gancho_comercial") or "",
        "status_contato": lead.get("status_contato") or "novo",
    }


def sincronizar_com_google_sheets(lead_ids: Optional[List[str]] = None, apenas_pendentes: bool = True) -> Tuple[bool, str, int]:
    """Envia lote de leads capturados para a planilha do Google Sheets via Apps Script Webhook."""
    webhook_url = get_sheets_webhook_url()
    if not webhook_url:
        return False, "URL do Webhook do Google Apps Script não configurada.", 0

    with db() as conn:
        if lead_ids:
            query = "SELECT * FROM prospeccao.leads WHERE id = ANY(%s::uuid[])"
            params = [lead_ids]
        elif apenas_pendentes:
            query = "SELECT * FROM prospeccao.leads WHERE sincronizado_sheets = FALSE ORDER BY score DESC, created_at DESC"
            params = []
        else:
            query = "SELECT * FROM prospeccao.leads ORDER BY score DESC, created_at DESC"
            params = []

        rows = conn.execute(query, params).fetchall() or []
        leads = [dict(r) for r in rows]

    if not leads:
        return True, "Nenhum lead pendente para sincronização.", 0

    itens_sheets = [formatar_lead_para_sheets(l) for l in leads]
    payload = {
        "action": "append_or_update_leads",
        "source": "m-one-prospector",
        "total": len(itens_sheets),
        "leads": itens_sheets,
    }

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data_bytes,
            headers={"Content-Type": "application/json", "User-Agent": "MOne-Prospector-Sync/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
            logger.info("Retorno Google Sheets Webhook: %s", resp_body[:200])

        # Atualizar status de sincronização no banco
        ids_sucesso = [l["id"] for l in leads]
        with db() as conn:
            conn.execute(
                """
                UPDATE prospeccao.leads
                SET sincronizado_sheets = TRUE, sincronizado_sheets_em = NOW()
                WHERE id = ANY(%s::uuid[]);
                """,
                [ids_sucesso],
            )
            conn.commit()

        return True, f"{len(leads)} leads sincronizados com sucesso na planilha!", len(leads)

    except Exception as ex:
        logger.error("Erro ao sincronizar com Google Sheets: %s", ex)
        return False, f"Falha na conexão com Google Sheets: {ex}", 0


# -------------------------------------------------------------------------
# 2. EXPORTAÇÃO META ADS LOOKALIKE (CSV)
# -------------------------------------------------------------------------

def exportar_csv_meta_lookalike(classes_permitidas: Optional[List[str]] = None) -> str:
    """Gera string CSV compatível com o padrão do Meta Ads Audience Manager."""
    classes = classes_permitidas or ["A", "B", "C"]

    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM prospeccao.leads
            WHERE classificacao = ANY(%s) AND (whatsapp IS NOT NULL OR telefone_google IS NOT NULL OR emails <> '{}')
            ORDER BY score DESC;
            """,
            [classes]
        ).fetchall() or []
        leads = [dict(r) for r in rows]

    output = io.StringIO()
    # Cabeçalhos canônicos do Meta Ads (Custom Audience / Lookalike)
    writer = csv.writer(output, delimiter=",")
    writer.writerow(["fn", "ln", "phone", "email", "ct", "st", "country", "zip"])

    for l in leads:
        # Nome e sobrenome do decisor ou razão social
        nome_completo = (l.get("decisor_nome") or l.get("nome") or "").strip()
        partes = nome_completo.split()
        fn = partes[0] if partes else ""
        ln = " ".join(partes[1:]) if len(partes) > 1 else ""

        # Telefone no formato internacional E.164 com +
        phone = l.get("whatsapp") or l.get("telefone_google") or ""
        if phone:
            phone = "+" + phone if not phone.startswith("+") else phone

        # Email
        email = (l.get("email") or "").strip().lower()
        if not email:
            emails = l.get("emails") or []
            if isinstance(emails, str):
                emails = [emails]
            email = emails[0].strip().lower() if emails else ""

        # Cidade, Estado e CEP
        city = (l.get("cidade") or "").strip().lower()
        st = (l.get("uf") or "").strip().lower()
        country = "br"
        raw_cep = l.get("cep") or ""
        if not raw_cep and l.get("endereco"):
            import re
            m = re.search(r"\b\d{5}-?\d{3}\b", l["endereco"])
            if m:
                raw_cep = m.group(0)
        zip_code = re.sub(r"\D", "", raw_cep) if raw_cep else ""

        writer.writerow([fn, ln, phone, email, city, st, country, zip_code])

    return output.getvalue()


# -------------------------------------------------------------------------
# 3. CONSULTA CONSOLIDADA DE LEADS CAPTURADOS
# -------------------------------------------------------------------------

def listar_leads_capturados(
    nicho_slug: Optional[str] = None,
    classe: Optional[str] = None,
    status_contato: Optional[str] = None,
    termo_busca: Optional[str] = None,
    apenas_com_whatsapp: bool = False,
    filtro_rapido: Optional[str] = None,
    vendedor_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Retorna leads filtrados e contagem total para a aba 'Leads Qualificados Capturados'."""
    where_clauses = ["1=1"]
    params: List[Any] = []

    if nicho_slug and nicho_slug != "all":
        where_clauses.append("nicho_slug = %s")
        params.append(nicho_slug)

    if classe and classe != "all":
        where_clauses.append("classificacao = %s")
        params.append(classe)

    if status_contato and status_contato != "all":
        where_clauses.append("status_contato = %s")
        params.append(status_contato)

    if filtro_rapido == "disponiveis":
        where_clauses.append("(status_contato = 'novo' OR status_contato IS NULL)")
    elif filtro_rapido == "meus" and vendedor_id:
        where_clauses.append("prospectado_por_id = %s")
        params.append(vendedor_id)
    elif filtro_rapido == "prospectados":
        where_clauses.append("status_contato = 'prospectado'")

    if apenas_com_whatsapp:
        where_clauses.append("(whatsapp IS NOT NULL OR telefone_google IS NOT NULL)")

    if termo_busca:
        where_clauses.append("(nome ILIKE %s OR razao_social ILIKE %s OR decisor_nome ILIKE %s OR cidade ILIKE %s)")
        like_term = f"%{termo_busca.strip()}%"
        params.extend([like_term, like_term, like_term, like_term])

    where_sql = " AND ".join(where_clauses)

    with db() as conn:
        count_row = conn.execute(f"SELECT COUNT(*) as total FROM prospeccao.leads WHERE {where_sql}", params).fetchone()
        total = count_row.get("total", 0) if count_row else 0

        query = f"""
            SELECT * FROM prospeccao.leads
            WHERE {where_sql}
            ORDER BY score DESC, created_at DESC
            LIMIT %s OFFSET %s;
        """
        rows = conn.execute(query, params + [limit, offset]).fetchall() or []
        leads = [dict(r) for r in rows]

    return leads, total


def obter_metricas_resumo() -> Dict[str, Any]:
    """KPIs consolidados para o cabeçalho executivo do módulo."""
    with db() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total_leads,
                COUNT(*) FILTER (WHERE classificacao = 'A') as classe_a,
                COUNT(*) FILTER (WHERE classificacao = 'B') as classe_b,
                COUNT(*) FILTER (WHERE whatsapp IS NOT NULL OR telefone_google IS NOT NULL) as com_whatsapp,
                COUNT(*) FILTER (WHERE (email IS NOT NULL AND email <> '') OR (emails IS NOT NULL AND emails <> '{}')) as com_email,
                COUNT(*) FILTER (WHERE status_contato = 'novo' OR status_contato IS NULL) as disponiveis,
                COUNT(*) FILTER (WHERE status_contato = 'prospectado') as prospectados,
                COUNT(*) FILTER (WHERE cnpj IS NOT NULL) as com_cnpj,
                COUNT(*) FILTER (WHERE sincronizado_sheets = TRUE) as sincronizados_sheets
            FROM prospeccao.leads;
            """
        ).fetchone()
        return dict(row) if row else {
            "total_leads": 0, "classe_a": 0, "classe_b": 0,
            "com_whatsapp": 0, "com_email": 0, "disponiveis": 0, "prospectados": 0,
            "com_cnpj": 0, "sincronizados_sheets": 0
        }
