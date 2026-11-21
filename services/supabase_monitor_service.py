"""
M-One Supabase Monitoring & Alert Service (services/supabase_monitor_service.py)
Gerencia telemetria de saúde, consumo de disco, saturação de conexões e alertas WhatsApp para o Supabase.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta

from database import db
from services.vercel_service import get_infra_config
from services.whatsapp_service import send_whatsapp_message

logger = logging.getLogger(__name__)

# Cache em memória para evitar queries repetitivas em acessos frequentes
_metrics_cache: dict = {}
_cache_ttl_seconds = 60.0  # Atualiza métricas pesadas a cada 60s


def ensure_supabase_infra_columns(conn) -> None:
    """Garante a existência das colunas de configuração do Supabase na tabela infra_config."""
    try:
        conn.execute("""
            ALTER TABLE infra_config 
            ADD COLUMN IF NOT EXISTS supabase_plan TEXT DEFAULT 'free',
            ADD COLUMN IF NOT EXISTS supabase_disk_limit_mb INTEGER DEFAULT 500,
            ADD COLUMN IF NOT EXISTS supabase_last_alert_sent_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS supabase_last_alert_milestone INTEGER;
        """)
        conn.commit()
    except Exception as e:
        logger.debug("[Supabase Config Schema Check]: %s", e)


def fetch_supabase_health_metrics(force_refresh: bool = False) -> dict:
    """Coleta métricas detalhadas de armazenamento, pool de conexões e performance do Supabase."""
    now = time.monotonic()
    if not force_refresh and _metrics_cache and (now - _metrics_cache.get("_timestamp", 0) < _cache_ttl_seconds):
        return _metrics_cache["data"]

    t0 = time.monotonic()
    try:
        with db() as conn:
            ensure_supabase_infra_columns(conn)

            # 1. Medir latência de ping básico
            ping_t0 = time.monotonic()
            conn.execute("SELECT 1;").fetchone()
            ping_latency_ms = round((time.monotonic() - ping_t0) * 1000, 1)

            # 2. Tamanho total do banco
            db_size_row = conn.execute("""
                SELECT pg_database_size(current_database()) as raw_bytes,
                       pg_size_pretty(pg_database_size(current_database())) as pretty;
            """).fetchone()
            raw_bytes = int(db_size_row["raw_bytes"]) if db_size_row else 0
            size_mb = round(raw_bytes / (1024 * 1024), 2)
            size_pretty = db_size_row["pretty"] if db_size_row else "0 MB"

            # 3. Divisão de tabelas e índices
            schema_row = conn.execute("""
                SELECT 
                    COALESCE(sum(pg_table_size(c.oid)), 0) as tables_bytes,
                    COALESCE(sum(pg_indexes_size(c.oid)), 0) as indexes_bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r';
            """).fetchone()
            tables_mb = round(int(schema_row["tables_bytes"]) / (1024 * 1024), 2) if schema_row else 0
            indexes_mb = round(int(schema_row["indexes_bytes"]) / (1024 * 1024), 2) if schema_row else 0

            # 4. Conexões e limite do pool
            max_conn_row = conn.execute("SHOW max_connections;").fetchone()
            max_connections = int(list(max_conn_row.values())[0]) if max_conn_row else 60

            conn_stats = conn.execute("""
                SELECT 
                    count(*) as total,
                    count(*) FILTER (WHERE state = 'active') as active,
                    count(*) FILTER (WHERE state = 'idle') as idle
                FROM pg_stat_activity;
            """).fetchone()
            total_conn = int(conn_stats["total"]) if conn_stats else 1
            active_conn = int(conn_stats["active"]) if conn_stats else 1
            idle_conn = int(conn_stats["idle"]) if conn_stats else 0

            # 5. Cache hit ratio
            stat_db = conn.execute("""
                SELECT blks_read, blks_hit 
                FROM pg_stat_database 
                WHERE datname = current_database();
            """).fetchone()
            hit_ratio = 100.0
            if stat_db and (stat_db["blks_hit"] + stat_db["blks_read"]) > 0:
                hit_ratio = round((stat_db["blks_hit"] / (stat_db["blks_hit"] + stat_db["blks_read"])) * 100, 2)

            # 6. Top 5 Maiores Tabelas
            top_tables_rows = conn.execute("""
                SELECT relname,
                       pg_size_pretty(pg_total_relation_size(c.oid)) as total_pretty,
                       pg_total_relation_size(c.oid) as total_bytes,
                       reltuples::bigint as rows_count
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                ORDER BY pg_total_relation_size(c.oid) DESC
                LIMIT 5;
            """).fetchall()

            top_tables = []
            for t in top_tables_rows:
                top_tables.append({
                    "name": t["relname"],
                    "size_pretty": t["total_pretty"],
                    "size_mb": round(int(t["total_bytes"]) / (1024 * 1024), 2),
                    "rows": int(t["rows_count"] or 0)
                })

            # Configurações de limite do plano
            cfg = get_infra_config(conn)
            plan = cfg.get("supabase_plan") or "free"
            disk_limit_mb = int(cfg.get("supabase_disk_limit_mb") or (500 if plan == "free" else 8192))
            threshold_pct = int(cfg.get("alert_threshold_pct") or 75)

            pct_disk = min(round((size_mb / disk_limit_mb) * 100, 1), 100.0)
            pct_conn = min(round((total_conn / max_connections) * 100, 1), 100.0)

            is_critical = pct_disk >= threshold_pct or pct_conn >= threshold_pct or ping_latency_ms >= 3000

            data = {
                "online": True,
                "project_ref": "ztbmnzwrpigcohwobrig",
                "pooler_host": "aws-0-us-west-2.pooler.supabase.com:6543",
                "plan": plan.upper(),
                "size_mb": size_mb,
                "size_pretty": size_pretty,
                "disk_limit_mb": disk_limit_mb,
                "pct_disk": pct_disk,
                "tables_mb": tables_mb,
                "indexes_mb": indexes_mb,
                "max_connections": max_connections,
                "total_connections": total_conn,
                "active_connections": active_conn,
                "idle_connections": idle_conn,
                "pct_conn": pct_conn,
                "hit_ratio": hit_ratio,
                "ping_latency_ms": ping_latency_ms,
                "top_tables": top_tables,
                "is_critical": is_critical,
                "threshold_pct": threshold_pct,
                "status_zone": "ZONA DE ALERTA SUPABASE" if is_critical else "ZONA SEGURA SUPABASE",
                "status_color": "#ef4444" if is_critical else "#22c55e",
                "last_alert_sent_at": cfg.get("supabase_last_alert_sent_at"),
                "checked_at": datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
            }

            _metrics_cache["_timestamp"] = now
            _metrics_cache["data"] = data
            return data

    except Exception as e:
        logger.error("[Supabase Health Metrics Error]: %s", e)
        return {
            "online": False,
            "error": str(e),
            "project_ref": "ztbmnzwrpigcohwobrig",
            "pooler_host": "aws-0-us-west-2.pooler.supabase.com:6543",
            "is_critical": True,
            "pct_disk": 100.0,
            "pct_conn": 100.0,
            "ping_latency_ms": -1,
            "status_zone": "BANCO INACESSÍVEL / ERRO",
            "status_color": "#ef4444",
            "checked_at": datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
        }


def check_and_trigger_supabase_alerts_if_needed() -> dict:
    """Verifica métricas do Supabase e dispara WhatsApp para Jam e Fauzer aos 75% ou falha."""
    metrics = fetch_supabase_health_metrics()
    if not metrics.get("is_critical"):
        return {"alert_sent": False, "reason": "Métricas dentro dos limites seguros"}

    cfg = get_infra_config()
    threshold = int(cfg.get("alert_threshold_pct") or 75)
    max_pct = max(metrics.get("pct_disk", 0), metrics.get("pct_conn", 0))

    milestone = 95 if max_pct >= 95 else (85 if max_pct >= 85 else threshold)
    last_milestone = cfg.get("supabase_last_alert_milestone") or 0
    last_sent = cfg.get("supabase_last_alert_sent_at")

    now = datetime.utcnow()
    if last_sent:
        last_dt = datetime.fromisoformat(str(last_sent).replace("Z", "")) if isinstance(last_sent, str) else last_sent
        if (now - last_dt) < timedelta(hours=24) and milestone <= last_milestone:
            return {"alert_sent": False, "reason": "Cooldown de 24h ativo para este marco"}

    phones = []
    if cfg.get("phone_jam"):
        phones.append(("Jam Penitenti", cfg.get("phone_jam")))
    if cfg.get("phone_fauzer"):
        phones.append(("Fauzer", cfg.get("phone_fauzer")))

    if not phones:
        return {"alert_sent": False, "reason": "Nenhum telefone configurado"}

    if not metrics.get("online"):
        msg = (
            f"🚨 *ALERTA CRÍTICO: SUPABASE FORA DO AR* 🚨\n\n"
            f"Não foi possível conectar ao banco de dados Supabase (`ztbmnzwrpigcohwobrig`).\n"
            f"Erro: {metrics.get('error', 'Timeout de conexão')}\n\n"
            f"⚠️ As páginas públicas e o painel administrativo podem estar indisponíveis!\n"
            f"Verifique o status do Supabase: https://supabase.com/dashboard/project/ztbmnzwrpigcohwobrig"
        )
    else:
        msg = (
            f"🚨 *ALERTA DE CAPACIDADE SUPABASE (M-ONE)* 🚨\n\n"
            f"O cluster Supabase atingiu *{max_pct:.1f}%* do limite operacional configurado (Limiar: {threshold}%).\n\n"
            f"📊 *Indicadores Atuais*:\n"
            f"• 💾 Espaço em Disco: *{metrics['size_mb']} MB / {metrics['disk_limit_mb']} MB* ({metrics['pct_disk']}%)\n"
            f"• 🔌 Conexões do Pool: *{metrics['total_connections']} / {metrics['max_connections']}* ({metrics['pct_conn']}%)\n"
            f"• ⏱️ Latência do Pooler: *{metrics['ping_latency_ms']} ms*\n"
            f"• 🧠 Cache Hit Ratio: *{metrics['hit_ratio']}%*\n\n"
            f"⚠️ *Ação Recomendada*: Avaliar upgrade para o plano Pro ou limpeza preventiva.\n"
            f"Acesse o painel: https://m-one.majmobilidade.com.br/infra/performance"
        )

    for name, p in phones:
        try:
            send_whatsapp_message(p, msg)
        except Exception as e:
            logger.error("Erro ao enviar alerta WhatsApp Supabase para %s (%s): %s", name, p, e)

    with db() as conn:
        conn.execute("""
            UPDATE infra_config
            SET supabase_last_alert_sent_at = CURRENT_TIMESTAMP,
                supabase_last_alert_milestone = %s
            WHERE id = %s
        """, (milestone, cfg["id"]))
        conn.commit()

    return {"alert_sent": True, "milestone": milestone, "max_pct": max_pct}


def send_test_supabase_alert_whatsapp(target_phone: str, target_name: str = "Gestor") -> dict:
    """Dispara um teste imediato de alerta de monitoramento do Supabase via WhatsApp."""
    if not target_phone:
        return {"success": False, "error": "Telefone não informado"}

    metrics = fetch_supabase_health_metrics(force_refresh=True)

    msg = (
        f"🧪 *TESTE DE ALERTA SUPABASE — M-ONE*\n\n"
        f"Olá, {target_name}!\n"
        f"O monitor de saúde e capacidade do **Supabase PostgreSQL** está ativo e operacional.\n\n"
        f"📊 *Diagnóstico Atual do Banco*:\n"
        f"• Status: 🟢 Conectado via Pooler IPv4\n"
        f"• Disco Utilizado: *{metrics['size_mb']} MB* de {metrics['disk_limit_mb']} MB ({metrics['pct_disk']}%)\n"
        f"• Conexões Ativas: *{metrics['total_connections']} / {metrics['max_connections']}* ({metrics['pct_conn']}%)\n"
        f"• Latência de Query: *{metrics['ping_latency_ms']} ms*\n"
        f"• Cache em RAM: *{metrics['hit_ratio']}%*\n\n"
        f"✅ Alertas automáticos serão disparados se o consumo atingir {metrics['threshold_pct']}%.\n"
        f"Painel: https://m-one.majmobilidade.com.br/infra/performance"
    )

    return send_whatsapp_message(target_phone, msg)

