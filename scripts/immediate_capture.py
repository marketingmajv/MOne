#!/usr/bin/env python3
"""
M-One Immediate Prospector Lead Generator (scripts/immediate_capture.py)
Executa a captura e enriquecimento imediato de um lote de 60 a 80 leads
diretamente no banco de dados Supabase da MAJ Mobilidade Elétrica.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database import db
from services.gemini_client import execute_gemini_payload
from services.prospector_service import calcular_score_lead, normalizar_email, normalizar_telefone

from services.prospector_service import (
    buscar_google_maps_apify,
    calcular_score_lead,
    classificar_telefone,
    consultar_dados_cnpj,
    escanear_site,
    normalizar_email,
    normalizar_telefone,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TARGET_PRACAS = [
    ("Vitória ES", "ES"),
    ("Vila Velha ES", "ES"),
    ("Serra ES", "ES"),
    ("Cariacica ES", "ES"),
    ("Belo Horizonte MG", "MG"),
    ("Campinas SP", "SP"),
]


def buscar_lote_empresas_reais(termo: str, praca: str, uf: str, nicho_slug: str, quantidade: int = 12) -> List[Dict[str, Any]]:
    """Consulta o Google Maps oficial via Apify para coletar empresas comerciais reais ativas."""
    query = f"{termo} em {praca}"
    logger.info(f"Buscando comércios reais no Google Maps via Apify: '{query}'...")
    try:
        results = buscar_google_maps_apify(query, max_results=quantidade)
        logger.info(f"Retornadas {len(results)} empresas reais pelo Google Places para {praca}.")
        return results
    except Exception as e:
        logger.error(f"Erro ao buscar no Google Places para {praca} - {termo}: {e}")
        return []


def salvar_leads_no_banco(leads_raw: List[Dict[str, Any]], nicho_slug: str, praca: str, termo: str) -> int:
    """Insere os leads reais coletados com classificação estrita de WhatsApp vs Fixo."""
    salvos = 0
    with db() as conn:
        for idx, item in enumerate(leads_raw):
            nome = item.get("nome") or "Empresa"
            gid = item.get("google_id") or f"gplace_{abs(hash(nome + praca))}_{int(time.time())}_{idx}"

            site_url = item.get("site")
            site_info = escanear_site(site_url) if site_url else {}

            tel_g, tipo_g = classificar_telefone(item.get("telefone_google") or item.get("telefone"))
            site_wa, tipo_site = classificar_telefone(site_info.get("whatsapp") or item.get("whatsapp"))

            # Regra estrita: WhatsApp só é gravado se for celular brasileiro verificado (com 9)
            whatsapp = site_wa if tipo_site == "celular" else (tel_g if tipo_g == "celular" else None)
            tel_principal = tel_g or site_wa

            email = normalizar_email(item.get("email") or (site_info.get("emails") or [None])[0])
            emails = [email] if email else []

            gancho = (
                f"Olá, equipe da {nome}! Tudo bem? 😊 Aqui é da MAJ Mobilidade Elétrica. "
                "Vimos que vocês são referência na região e temos condições exclusivas de atacado "
                "direto de fábrica para revenda de scooters e motos elétricas MAJ. "
                "Com quem da equipe comercial ou de compras poderíamos conversar por aqui? 🚀"
            )

            lead_dict = {
                "nome": nome,
                "site_vivo": bool(site_url),
                "whatsapp": whatsapp,
                "telefone_google": tel_principal,
                "cnpj": site_info.get("cnpj"),
                "decisor_nome": None,
                "instagram": site_info.get("instagram"),
                "email": email,
                "emails": emails,
                "avaliacao": float(item.get("avaliacao") or 4.5),
                "total_avaliacoes": int(item.get("total_avaliacoes") or 10),
            }

            pesos_padrao = {
                "site_vivo": 20, "whatsapp": 20, "cnpj_decisor": 20,
                "instagram": 15, "email": 10, "reputacao": 15
            }
            score, classe, sinais = calcular_score_lead(lead_dict, pesos_padrao)
            maps_url = item.get("google_maps_url") or f"https://www.google.com/maps/search/?api=1&query={nome.replace(' ', '+')}+{praca.replace(' ', '+')}"

            conn.execute(
                """
                INSERT INTO prospeccao.leads (
                    google_id, nicho_slug, praca, termo_busca, nome, categoria, endereco, cidade, uf,
                    google_maps_url, avaliacao, total_avaliacoes, telefone_google, site, site_status, site_vivo,
                    whatsapp, email, emails, instagram, cnpj, razao_social, nome_fantasia,
                    decisor_nome, decisor_cargo, resumo_ia, porte_estimado, do_nicho, motivo_aderencia,
                    gancho_comercial, score, classificacao, sinais_score, status_contato
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, 200, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    NULL, NULL, %s, 'pequena', TRUE, 'Empresa real ativa identificada no Google Maps.',
                    %s, %s, %s, %s, 'novo'
                )
                ON CONFLICT (google_id) DO NOTHING;
                """,
                [
                    gid, nicho_slug, praca, termo, nome, item.get("categoria", "Revenda"), item.get("endereco", praca), item.get("cidade", praca.split()[0]), "ES",
                    maps_url, float(item.get("avaliacao") or 4.5), int(item.get("total_avaliacoes") or 10), tel_principal, site_url, bool(site_url),
                    whatsapp, email, emails, site_info.get("instagram"), site_info.get("cnpj"), nome, nome,
                    f"Comércio ativo em {praca} no segmento {item.get('categoria', 'duas rodas')}.",
                    gancho, score, classe, json.dumps(sinais)
                ]
            )
            salvos += 1
        conn.commit()
    return salvos


def executar_captura_imediata(meta_leads: int = 70) -> None:
    """Executa a captação completa distribuída pelas praças alvo."""
    logger.info(f"=== INICIANDO CAPTURA IMEDIATA DE {meta_leads} LEADS QUALIFICADOS ===")
    total_gerados = 0

    queries = [
        ("Vitória ES", "ES", "revenda-motos", "loja de motos e revenda multimarcas"),
        ("Vila Velha ES", "ES", "revenda-motos", "concessionária de motos e scooters"),
        ("Serra ES", "ES", "revenda-motos", "loja de veículos elétricos e motos"),
        ("Cariacica ES", "ES", "revenda-motos", "revenda de motos multimarcas"),
        ("Belo Horizonte MG", "MG", "revenda-motos", "lojas de motos e scooters elétricas"),
        ("Campinas SP", "SP", "revenda-motos", "boutique de motos e revenda multimarcas"),
    ]

    por_query = max(10, (meta_leads // len(queries)) + 2)

    for praca, uf, nicho, termo in queries:
        if total_gerados >= meta_leads:
            break
        logger.info(f"Capturando lote em {praca} para '{termo}' (Meta: {por_query})...")
        lote = buscar_lote_empresas_reais(termo, praca, uf, nicho, quantidade=por_query)
        if lote:
            qtd = salvar_leads_no_banco(lote, nicho, praca, termo)
            total_gerados += qtd
            logger.info(f"✓ {qtd} leads gravados para {praca}. Total acumulado: {total_gerados}")
        time.sleep(1)

    # Atualizar telemetria em prospeccao.config
    agora_iso = datetime.now().isoformat()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO prospeccao.config (chave, valor, descricao, updated_at)
            VALUES ('automacao_ultimo_ciclo', %s, 'Timestamp do Último Ciclo Executado', NOW())
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, updated_at = NOW();
            """,
            [agora_iso]
        )
        conn.execute(
            """
            INSERT INTO prospeccao.config (chave, valor, descricao, updated_at)
            VALUES ('automacao_ultimo_resultado', %s, 'Resultado do Último Ciclo', NOW())
            ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, updated_at = NOW();
            """,
            [f"Lote imediato executado com sucesso: {total_gerados} novos leads capturados."]
        )
    # Opcional: Sincronização automática com a planilha Google Sheets se configurada
    try:
        from services.prospector_export_service import sincronizar_com_google_sheets
        ok, msg, count = sincronizar_com_google_sheets(apenas_pendentes=True)
        if count > 0:
            logger.info(f"✓ Sincronizados {count} novos leads com a planilha Google Sheets!")
    except Exception as ex:
        logger.debug(f"Sincronização Google Sheets ignorada/não configurada: {ex}")

    logger.info(f"=== CAPTURA CONCLUÍDA! TOTAL DE {total_gerados} LEADS DISPONÍVEIS NA ESTEIRA ===")


if __name__ == "__main__":
    meta = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 70
    executar_captura_imediata(meta)
