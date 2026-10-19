"""
M-One Prospector 24/7 Automation & Rotation Service (services/prospector_sync_service.py)
Motor de Automação Contínua para Prospecção de Leads:
- Alternância dinâmica entre 4 modos de intervalo:
    1. 'turnos': 3x ao dia (08:15, 13:15, 17:45) - ~25 leads/ciclo
    2. 'rotacao': Rotação horária (a cada 2h das 08h às 18h) alternando cidades
    3. 'noturno': Lote diário único às 06:00 - ~60 a 80 leads
    4. 'custom': Intervalo personalizado em minutos (ex: 60 min)
- Carrossel cíclico inteligente de praças/cidades
- Auditoria e gravação na tabela prospeccao.config
Segregação estrita modular (< 500 linhas).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

FUSO_BRASILIA = timezone(timedelta(hours=-3))


def obter_agora_brasilia() -> datetime:
    """Retorna datetime no fuso horário oficial de Brasília (UTC-3)."""
    return datetime.now(FUSO_BRASILIA)

from database import db
from services.prospector_service import (
    executar_prospeccao_assincrona,
    get_prospector_config,
    obter_status_job,
    set_prospector_config,
)

logger = logging.getLogger(__name__)

PRACAS_PADRAO = [
    "Vitória ES",
    "Vila Velha ES",
    "Serra ES",
    "Cariacica ES",
    "Belo Horizonte MG",
    "Campinas SP",
]

MODOS_INFO = {
    "turnos": {
        "rotulo": "Turnos Comerciais (Recomendado)",
        "descricao": "3 disparos ao dia (08:15, 13:15 e 17:45) — ~25 leads por ciclo.",
        "horarios": ["08:15", "13:15", "17:45"],
        "limite_sugerido": 25,
    },
    "rotacao": {
        "rotulo": "Rotação Horária Regional",
        "descricao": "A cada 2 horas (08:00 às 18:00) alternando a praça/cidade cadastrada.",
        "horarios": ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00"],
        "limite_sugerido": 15,
    },
    "noturno": {
        "rotulo": "Lote Noturno (Madrugada)",
        "descricao": "1 disparo diário às 06:00 com lote maior para a esteira amanhecer cheia.",
        "horarios": ["06:00"],
        "limite_sugerido": 70,
    },
    "custom": {
        "rotulo": "Personalizado / Sob Demanda",
        "descricao": "Intervalo em minutos e volume customizável.",
        "horarios": [],
        "limite_sugerido": 20,
    },
}


def obter_config_automacao() -> Dict[str, Any]:
    """Recupera todas as preferências e telemetria da automação 24/7."""
    ativo_str = get_prospector_config("automacao_ativo", "false")
    modo = get_prospector_config("automacao_modo", "turnos")
    if modo not in MODOS_INFO:
        modo = "turnos"

    pracas_raw = get_prospector_config("automacao_pracas", "")
    if pracas_raw:
        try:
            pracas = json.loads(pracas_raw) if pracas_raw.startswith("[") else [p.strip() for p in pracas_raw.split(",") if p.strip()]
        except Exception:
            pracas = PRACAS_PADRAO
    else:
        pracas = PRACAS_PADRAO

    limite_str = get_prospector_config("automacao_limite", "")
    limite = int(limite_str) if limite_str.isdigit() else MODOS_INFO[modo]["limite_sugerido"]

    intervalo_min_str = get_prospector_config("automacao_intervalo_min", "120")
    intervalo_min = int(intervalo_min_str) if intervalo_min_str.isdigit() else 120

    indice_str = get_prospector_config("automacao_indice_rotacao", "0")
    indice = int(indice_str) if indice_str.isdigit() else 0

    return {
        "ativo": (ativo_str.lower() in ["true", "1", "yes"]),
        "modo": modo,
        "modos_info": MODOS_INFO,
        "limite": limite,
        "intervalo_min": intervalo_min,
        "pracas": pracas,
        "nicho_slug": get_prospector_config("automacao_nicho", "revenda-motos"),
        "ultimo_ciclo": get_prospector_config("automacao_ultimo_ciclo", ""),
        "ultima_praca": get_prospector_config("automacao_ultima_praca", ""),
        "ultimo_resultado": get_prospector_config("automacao_ultimo_resultado", ""),
        "total_auto": int(get_prospector_config("automacao_total_auto", "0") or "0"),
        "indice_rotacao": indice,
        "proxima_praca": pracas[indice % len(pracas)] if pracas else "Vitória ES",
    }


def salvar_config_automacao(dados: Dict[str, Any]) -> None:
    """Atualiza as diretrizes da automação 24/7."""
    if "ativo" in dados:
        set_prospector_config("automacao_ativo", "true" if dados["ativo"] else "false", "Status da Automação 24/7")
    if "modo" in dados and dados["modo"] in MODOS_INFO:
        set_prospector_config("automacao_modo", dados["modo"], "Modo de Frequência da Automação")
    if "limite" in dados:
        set_prospector_config("automacao_limite", str(max(5, int(dados["limite"]))), "Volume de leads por ciclo")
    if "intervalo_min" in dados:
        set_prospector_config("automacao_intervalo_min", str(max(15, int(dados["intervalo_min"]))), "Intervalo em min (modo custom)")
    if "pracas" in dados:
        pracas_val = dados["pracas"]
        if isinstance(pracas_val, list):
            pracas_str = ", ".join(pracas_val)
        else:
            pracas_str = str(pracas_val).strip()
        set_prospector_config("automacao_pracas", pracas_str, "Cidades/Praças para Carrossel")
    if "nicho_slug" in dados and dados["nicho_slug"]:
        set_prospector_config("automacao_nicho", str(dados["nicho_slug"]).strip(), "Nicho da Automação")


def verificar_se_deve_executar(cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """Avalia se o momento atual é oportuno para disparar um ciclo com base no modo selecionado."""
    if not cfg.get("ativo"):
        return False, "Automação desativada."

    job = obter_status_job()
    if job.get("running"):
        return False, "Já existe uma busca em execução no momento."

    agora = obter_agora_brasilia()
    ultimo_ciclo_str = cfg.get("ultimo_ciclo")
    ultimo_dt = None
    if ultimo_ciclo_str:
        try:
            ultimo_dt = datetime.fromisoformat(ultimo_ciclo_str)
            if ultimo_dt.tzinfo is None:
                ultimo_dt = ultimo_dt.replace(tzinfo=FUSO_BRASILIA)
        except Exception:
            ultimo_dt = None

    modo = cfg.get("modo", "turnos")

    if modo == "turnos":
        # Janelas: 08:15-09:15, 13:15-14:15, 17:45-18:45
        hora_atual = agora.hour
        minuto_atual = agora.minute
        hora_dec = hora_atual + (minuto_atual / 60.0)
        janelas = [(8.25, 9.25), (13.25, 14.25), (17.75, 18.75)]
        na_janela = any(ini <= hora_dec <= fim for ini, fim in janelas)
        if not na_janela:
            return False, f"Fora das janelas de turno (08:15, 13:15, 17:45). Hora atual: {agora.strftime('%H:%M')}."
        if ultimo_dt and (agora - ultimo_dt).total_seconds() < 7200:
            return False, "Ciclo deste turno já executado nas últimas 2 horas."
        return True, "Janela de turno comercial ativa."

    elif modo == "rotacao":
        # Das 08h às 18h, a cada 2 horas
        if not (8 <= agora.hour < 19):
            return False, f"Fora do horário comercial (08:00 às 18:00). Hora atual: {agora.strftime('%H:%M')}."
        if ultimo_dt and (agora - ultimo_dt).total_seconds() < 6600:
            return False, f"Último ciclo executado há menos de 1h50m ({ultimo_dt.strftime('%H:%M')})."
        return True, "Ciclo da rotação horária liberado."

    elif modo == "noturno":
        # Entre 05:30 e 07:00
        if not (5 <= agora.hour <= 7):
            return False, f"Fora da janela de lote noturno (05:30 às 07:00). Hora atual: {agora.strftime('%H:%M')}."
        if ultimo_dt and ultimo_dt.date() == agora.date():
            return False, "Lote noturno de hoje já foi executado."
        return True, "Janela de lote noturno liberada."

    elif modo == "custom":
        intervalo_s = cfg.get("intervalo_min", 120) * 60
        if ultimo_dt and (agora - ultimo_dt).total_seconds() < intervalo_s:
            restante_m = int((intervalo_s - (agora - ultimo_dt).total_seconds()) / 60)
            return False, f"Aguardando intervalo customizado (restam ~{restante_m} min)."
        return True, "Intervalo customizado atingido."

    return False, "Modo não reconhecido."


def executar_ciclo_automacao(forcar: bool = False) -> Dict[str, Any]:
    """Executa um ciclo automático, alternando a praça e registrando telemetria."""
    cfg = obter_config_automacao()
    if not forcar:
        deve, motivo = verificar_se_deve_executar(cfg)
        if not deve:
            return {"status": "skipped", "message": motivo, "config": cfg}

    pracas = cfg.get("pracas") or PRACAS_PADRAO
    indice = cfg.get("indice_rotacao", 0)
    praca_alvo = pracas[indice % len(pracas)]
    nicho_slug = cfg.get("nicho_slug") or "revenda-motos"
    limite = cfg.get("limite") or 20

    logger.info("[Automação Prospector] Iniciando ciclo para '%s' em '%s' (Limite: %d)...", nicho_slug, praca_alvo, limite)

    # Dispara a busca assíncrona do prospector
    executar_prospeccao_assincrona(nicho_slug, praca_alvo, limite=limite)

    # Atualiza carrossel e telemetria
    proximo_indice = indice + 1
    agora_iso = obter_agora_brasilia().isoformat()
    total_auto = cfg.get("total_auto", 0) + limite

    set_prospector_config("automacao_indice_rotacao", str(proximo_indice), "Índice do Carrossel de Cidades")
    set_prospector_config("automacao_ultimo_ciclo", agora_iso, "Timestamp do Último Ciclo Executado")
    set_prospector_config("automacao_ultima_praca", praca_alvo, "Última Praça Varrida pelo Robô")
    set_prospector_config("automacao_ultimo_resultado", f"Disparada varredura de {limite} leads para {praca_alvo}", "Resultado do Último Ciclo")
    set_prospector_config("automacao_total_auto", str(total_auto), "Total Histórico de Leads Capturados em Automação")

    proxima_praca = pracas[proximo_indice % len(pracas)]

    return {
        "status": "success",
        "message": f"Varredura iniciada com sucesso para '{praca_alvo}' ({limite} leads)!",
        "praca_executada": praca_alvo,
        "proxima_praca": proxima_praca,
        "nicho": nicho_slug,
        "limite": limite,
        "timestamp": agora_iso,
    }
