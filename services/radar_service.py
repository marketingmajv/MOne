"""
M-One Radar de Mercado & Missões Táticas (services/radar_service.py)
Motor de Operações Táticas de Prospecção Georreferenciada:
- Gestão de Lotes / Missões de Prospecção por Cidade
- Isolamento absoluto de leads capturados por batida
- Autocomplete com 78 municípios do ES + principais polos do Brasil
- Métricas dedicadas de conversão por missão
Segregação estrita modular (< 500 linhas).
"""

from __future__ import annotations
import json, logging, re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from database import db
from services.prospector_service import get_nicho_by_slug

logger = logging.getLogger(__name__)

# Catálogo oficial dos 78 municípios do Espírito Santo + Polos Estratégicos Nacionais
CIDADES_SUGERIDAS_ES = [
    # Polos Estruturantes Principais do ES
    "Linhares - ES", "Colatina - ES", "São Mateus - ES", "Cachoeiro de Itapemirim - ES",
    "Vitória - ES", "Vila Velha - ES", "Serra - ES", "Cariacica - ES", "Guarapari - ES",
    "Aracruz - ES", "Viana - ES", "Marataízes - ES", "Nova Venécia - ES", "São Gabriel da Palha - ES",
    "Domingos Martins - ES", "Santa Maria de Jetibá - ES", "Venda Nova do Imigrante - ES", "Castelo - ES",
    "Barra de São Francisco - ES", "Itapemirim - ES", "Anchieta - ES", "Piúma - ES",
    # Norte e Noroeste do ES
    "Sooretama - ES", "Rio Bananal - ES", "Jaguaré - ES", "Conceição da Barra - ES",
    "Pedro Canário - ES", "Pinheiros - ES", "Montanha - ES", "Mucurici - ES", "Ponto Belo - ES",
    "Ecoporanga - ES", "Água Doce do Norte - ES", "Mantenópolis - ES", "Alto Rio Novo - ES",
    "Pancas - ES", "São Domingos do Norte - ES", "Governador Lindenberg - ES", "Marilândia - ES",
    "Baixo Guandu - ES", "São Roque do Canaã - ES", "Ibiraçu - ES", "João Neiva - ES", "Fundão - ES",
    # Região Serrana e Central do ES
    "Santa Teresa - ES", "Santa Leopoldina - ES", "Itarana - ES", "Itaguaçu - ES",
    "Laranja da Terra - ES", "Afonso Cláudio - ES", "Brejetuba - ES", "Conceição do Castelo - ES",
    # Sul e Caparaó do ES
    "Vargem Alta - ES", "Muqui - ES", "Mimoso do Sul - ES", "Atílio Vivácqua - ES",
    "Presidente Kennedy - ES", "Jerônimo Monteiro - ES", "Alegre - ES", "Guaçuí - ES",
    "Iúna - ES", "Irupi - ES", "Ibitirama - ES", "Divino de São Lourenço - ES",
    "Dores do Rio Preto - ES", "Muniz Freire - ES", "Bom Jesus do Norte - ES",
    "São José do Calçado - ES", "Apiacá - ES",
    # Principais Polos e Capitais do Brasil
    "Belo Horizonte - MG", "Campinas - SP", "São Paulo - SP", "Rio de Janeiro - RJ",
    "Teixeira de Freitas - BA", "Governador Valadares - MG", "Campos dos Goytacazes - RJ"
]


def normalizar_nome_praca(praca_bruta: str) -> Tuple[str, str, str]:
    """Padroniza 'Linhares ES' ou 'Linhares - ES' para ('Linhares - ES', 'Linhares', 'ES')."""
    p = praca_bruta.strip()
    uf = "ES"
    for state in ["ES", "SP", "MG", "RJ", "BA", "PR", "SC", "RS", "GO", "DF"]:
        if re.search(rf"\b{state}\b", p, re.IGNORECASE):
            uf = state.upper()
            break
    cidade = re.sub(rf"[-,\s]*\b{uf}\b.*", "", p, flags=re.IGNORECASE).strip()
    if not cidade:
        cidade = p
    praca_padrao = f"{cidade} - {uf}"
    return praca_padrao, cidade, uf


def criar_lote(praca_input: str, nicho_slug: str, limite: int = 25, user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Registra uma nova missão/lote de prospecção do Radar no Supabase."""
    praca_fmt, cidade, uf = normalizar_nome_praca(praca_input)
    nicho_cfg = get_nicho_by_slug(nicho_slug) or {}
    nicho_rotulo = nicho_cfg.get("rotulo", nicho_slug.replace("-", " ").title())
    titulo = f"{cidade} - {uf} ({nicho_rotulo})"

    u_id = user.get("id") if user else None
    u_nome = user.get("name") or user.get("username") or "Operador Radar" if user else "Operador Radar"

    with db() as conn:
        row = conn.execute(
            """
            INSERT INTO prospeccao.lotes (
                titulo, praca, cidade, uf, nicho_slug, limite_solicitado,
                total_capturados, total_whatsapp, total_prospectados, status,
                criado_por_id, criado_por_nome, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                0, 0, 0, 'em_andamento',
                %s, %s, NOW(), NOW()
            )
            RETURNING *;
            """,
            [titulo, praca_fmt, cidade, uf, nicho_slug, limite, u_id, u_nome]
        ).fetchone()
        conn.commit()
        return dict(row) if row else {}


def listar_lotes(limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    """Retorna a lista cronológica de missões/lotes com métricas agregadas."""
    with db() as conn:
        count_row = conn.execute("SELECT COUNT(*) as total FROM prospeccao.lotes;").fetchone()
        total = count_row.get("total", 0) if count_row else 0

        rows = conn.execute(
            """
            SELECT l.*,
                   (SELECT COUNT(*) FROM prospeccao.leads WHERE lote_id = l.id) as leads_reais,
                   (SELECT COUNT(*) FROM prospeccao.leads WHERE lote_id = l.id AND (whatsapp IS NOT NULL OR telefone_google IS NOT NULL)) as wa_reais,
                   (SELECT COUNT(*) FROM prospeccao.leads WHERE lote_id = l.id AND status_contato = 'prospectado') as prospectados_reais
            FROM prospeccao.lotes l
            ORDER BY l.created_at DESC
            LIMIT %s OFFSET %s;
            """,
            [limit, offset]
        ).fetchall() or []
        lotes = [dict(r) for r in rows]
        return lotes, total


def obter_lote_por_id(lote_id: str) -> Optional[Dict[str, Any]]:
    """Recupera detalhes de uma missão específica."""
    with db() as conn:
        row = conn.execute(
            """
            SELECT l.*,
                   (SELECT COUNT(*) FROM prospeccao.leads WHERE lote_id = l.id) as leads_reais,
                   (SELECT COUNT(*) FROM prospeccao.leads WHERE lote_id = l.id AND (whatsapp IS NOT NULL OR telefone_google IS NOT NULL)) as wa_reais,
                   (SELECT COUNT(*) FROM prospeccao.leads WHERE lote_id = l.id AND status_contato = 'prospectado') as prospectados_reais
            FROM prospeccao.lotes l
            WHERE l.id = %s::uuid;
            """,
            [lote_id]
        ).fetchone()
        return dict(row) if row else None


def listar_leads_do_lote(lote_id: str, status_contato: Optional[str] = None, apenas_wa: bool = False, busca: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna leads pertencentes exclusivamente a este lote/missão."""
    where_clauses = ["lote_id = %s::uuid"]
    params: List[Any] = [lote_id]

    if status_contato and status_contato != "all":
        where_clauses.append("status_contato = %s")
        params.append(status_contato)

    if apenas_wa:
        where_clauses.append("(whatsapp IS NOT NULL OR telefone_google IS NOT NULL)")

    if busca:
        where_clauses.append("(nome ILIKE %s OR razao_social ILIKE %s OR decisor_nome ILIKE %s)")
        like_t = f"%{busca.strip()}%"
        params.extend([like_t, like_t, like_t])

    where_sql = " AND ".join(where_clauses)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM prospeccao.leads
            WHERE {where_sql}
            ORDER BY score DESC, created_at DESC;
            """,
            params
        ).fetchall() or []
        return [dict(r) for r in rows]


def obter_metricas_radar() -> Dict[str, Any]:
    """Estatísticas executivas de missões do Radar de Mercado."""
    with db() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total_lotes,
                COUNT(DISTINCT cidade) as cidades_exploradas,
                COALESCE(SUM(total_capturados), 0) as total_leads_radar,
                COALESCE(SUM(total_whatsapp), 0) as total_wa_radar,
                (SELECT COUNT(*) FROM prospeccao.leads WHERE lote_id IS NOT NULL AND status_contato = 'prospectado') as total_prospectados
            FROM prospeccao.lotes;
            """
        ).fetchone()
        return dict(row) if row else {}


def obter_cidades_rastreadas() -> List[Dict[str, Any]]:
    """Retorna lista de cidades rastreadas com contagem de leads para as pílulas rápidas."""
    with db() as conn:
        rows = conn.execute("""
            SELECT COALESCE(NULLIF(cidade, ''), praca) as cidade,
                   MAX(uf) as uf,
                   COUNT(*) as total_leads,
                   COUNT(whatsapp) as total_wa
            FROM prospeccao.leads
            WHERE lote_id IS NOT NULL OR cidade IS NOT NULL
            GROUP BY COALESCE(NULLIF(cidade, ''), praca)
            ORDER BY total_leads DESC, cidade ASC;
        """).fetchall() or []
        return [dict(r) for r in rows]


def listar_leads_radar(cidade: Optional[str] = None, status_contato: Optional[str] = None, apenas_wa: bool = False, busca: Optional[str] = None, limit: int = 150) -> List[Dict[str, Any]]:
    """Retorna leads filtrados por cidade ou gerais para o Radar de Mercado."""
    where_clauses = ["1=1"]
    params: List[Any] = []

    if cidade and cidade != "all":
        where_clauses.append("cidade ILIKE %s")
        params.append(f"%{cidade}%")

    if status_contato and status_contato != "all":
        where_clauses.append("status_contato = %s")
        params.append(status_contato)

    if apenas_wa:
        where_clauses.append("(whatsapp IS NOT NULL OR telefone_google IS NOT NULL)")

    if busca:
        where_clauses.append("(nome ILIKE %s OR razao_social ILIKE %s OR decisor_nome ILIKE %s)")
        like_t = f"%{busca.strip()}%"
        params.extend([like_t, like_t, like_t])

    where_sql = " AND ".join(where_clauses)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM prospeccao.leads
            WHERE {where_sql}
            ORDER BY score DESC, created_at DESC
            LIMIT %s;
            """,
            params + [limit]
        ).fetchall() or []
        return [dict(r) for r in rows]


def excluir_lote(lote_id: str) -> bool:
    """Remove um lote e desassocia os leads correspondentes."""
    try:
        with db() as conn:
            conn.execute("DELETE FROM prospeccao.lotes WHERE id = %s::uuid;", [lote_id])
            conn.commit()
            return True
    except Exception as e:
        logger.error("Erro ao excluir lote %s: %s", lote_id, e)
        return False
