"""
M-One Telemetry & Render Container Monitoring Service (services/telemetry_service.py)
Coletor em memória (< 0.05 ms overhead), métricas thread-safe de concorrência,
latência p95/média, leitura nativa de RAM/CPU e persistência seletiva de incidentes.
Segregação anti-monólito (< 500 linhas).
"""

from __future__ import annotations

import collections
import json
import logging
import os
import platform
import resource
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import db

logger = logging.getLogger(__name__)

# Configurações padrão do plano Render Free
DEFAULT_RAM_CEILING_MB = 512.0
DEFAULT_LATENCY_THRESHOLD_MS = 3000
DEFAULT_CONCURRENCY_ROUTE_THRESHOLD = 3
DEFAULT_CONCURRENCY_GLOBAL_THRESHOLD = 8
DEFAULT_RAM_THRESHOLD_PCT = 80
COOLDOWN_ALERT_SECONDS = 900  # 15 minutos entre alertas de mesmo tipo


class TelemetryCollector:
    """Coletor em memória thread-safe para monitoramento em tempo real do M-One."""

    def __init__(self, sample_window: int = 300):
        self._lock = threading.Lock()
        self.sample_window = sample_window
        self.in_flight_total: int = 0
        self.in_flight_by_route: Dict[str, int] = collections.defaultdict(int)
        self.samples: collections.deque = collections.deque(maxlen=sample_window)
        self.last_alerts: Dict[str, float] = {}  # {incident_type: timestamp}
        self._render_cache: Dict[str, Any] = {"data": None, "ts": 0.0}

    def start_request(self, route_endpoint: str) -> float:
        """Chamado no before_request: incrementa requisições in-flight de forma atômica."""
        t0 = time.monotonic()
        with self._lock:
            self.in_flight_total += 1
            self.in_flight_by_route[route_endpoint] += 1
        return t0

    def end_request(self, route_endpoint: str, status_code: int, t0: float) -> float:
        """Chamado no after_request/teardown: registra métrica e decrementa in-flight."""
        dur_ms = round((time.monotonic() - t0) * 1000, 2)
        now_ts = time.time()
        with self._lock:
            self.in_flight_total = max(0, self.in_flight_total - 1)
            if route_endpoint in self.in_flight_by_route:
                self.in_flight_by_route[route_endpoint] = max(0, self.in_flight_by_route[route_endpoint] - 1)
                if self.in_flight_by_route[route_endpoint] == 0:
                    del self.in_flight_by_route[route_endpoint]

            self.samples.append((now_ts, route_endpoint, status_code, dur_ms))

        # Avaliação de incidentes críticos de forma não-bloqueante
        if dur_ms > DEFAULT_LATENCY_THRESHOLD_MS or status_code >= 500:
            self._evaluate_threshold_incident(route_endpoint, dur_ms, status_code)

        return dur_ms

    def get_memory_usage_mb(self) -> Tuple[float, float, float]:
        """Lê o consumo de RAM nativo sem psutil. Retorna (usado_mb, teto_mb, percentual)."""
        used_mb = 0.0
        teto_mb = DEFAULT_RAM_CEILING_MB

        # 1. No Linux (Render/Docker): leitura de /proc/self/status para VmRSS real
        try:
            if os.path.exists("/proc/self/status"):
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                used_mb = round(float(parts[1]) / 1024.0, 2)
                            break
        except Exception as e:
            logger.debug("[Telemetry RAM Procfs error]: %s", e)

        # 2. Fallback via módulo nativo resource
        if used_mb <= 0.0:
            try:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                # No macOS ru_maxrss é em bytes; no Linux é em kilobytes
                if platform.system() == "Darwin":
                    used_mb = round(usage.ru_maxrss / (1024.0 * 1024.0), 2)
                else:
                    used_mb = round(usage.ru_maxrss / 1024.0, 2)
            except Exception as e:
                logger.debug("[Telemetry RAM Resource error]: %s", e)
                used_mb = 120.0  # estimativa base se ambos falharem

        pct = round((used_mb / teto_mb) * 100.0, 1)
        return used_mb, teto_mb, pct

    def get_snapshot(self) -> Dict[str, Any]:
        """Calcula métricas agregadas da janela atual (latência p95, média, ranking)."""
        now = time.time()
        with self._lock:
            current_in_flight = self.in_flight_total
            routes_in_flight = dict(self.in_flight_by_route)
            raw_samples = list(self.samples)

        used_mb, teto_mb, ram_pct = self.get_memory_usage_mb()

        # Filtrar amostras dos últimos 15 minutos (900s)
        recent_samples = [s for s in raw_samples if (now - s[0]) <= 900]
        count = len(recent_samples)

        latencies = [s[3] for s in recent_samples]
        if latencies:
            latencies.sort()
            avg_latency = round(sum(latencies) / len(latencies), 1)
            p95_idx = int(len(latencies) * 0.95)
            p95_latency = round(latencies[min(p95_idx, len(latencies) - 1)], 1)
            max_latency = round(latencies[-1], 1)
        else:
            avg_latency = 0.0
            p95_latency = 0.0
            max_latency = 0.0

        # Erros 5xx e cálculo de RPM
        errors_5xx = sum(1 for s in recent_samples if s[2] >= 500)
        time_span_min = max(1.0, (now - recent_samples[0][0]) / 60.0) if recent_samples else 1.0
        rpm = round(count / time_span_min, 1)

        # Ranking de rotas congestionadas / lentas
        route_stats: Dict[str, List[float]] = collections.defaultdict(list)
        for s in recent_samples:
            route_stats[s[1]].append(s[3])

        top_slow_routes = []
        for r_name, r_lats in route_stats.items():
            r_lats.sort()
            r_avg = round(sum(r_lats) / len(r_lats), 1)
            r_p95 = round(r_lats[int(len(r_lats) * 0.95)], 1) if r_lats else 0.0
            top_slow_routes.append({
                "route": r_name,
                "count": len(r_lats),
                "avg_ms": r_avg,
                "p95_ms": r_p95,
                "active_now": routes_in_flight.get(r_name, 0)
            })
        top_slow_routes.sort(key=lambda x: (x["active_now"] * 1000 + x["p95_ms"]), reverse=True)

        # Estado do sistema
        status = "normal"
        status_label = "Saudável"
        status_color = "#10b981"
        is_stressed = False

        if ram_pct >= DEFAULT_RAM_THRESHOLD_PCT or current_in_flight >= DEFAULT_CONCURRENCY_GLOBAL_THRESHOLD or p95_latency >= DEFAULT_LATENCY_THRESHOLD_MS:
            status = "critical"
            status_label = "Crítico / Alto Tráfego"
            status_color = "#ef4444"
            is_stressed = True
        elif ram_pct >= 70.0 or current_in_flight >= 4 or p95_latency >= 1500.0:
            status = "warning"
            status_label = "Atenção / Pico Moderado"
            status_color = "#f59e0b"
            is_stressed = True

        return {
            "status": status,
            "status_label": status_label,
            "status_color": status_color,
            "is_stressed": is_stressed,
            "in_flight_total": current_in_flight,
            "in_flight_routes": routes_in_flight,
            "ram_used_mb": used_mb,
            "ram_ceiling_mb": teto_mb,
            "ram_pct": ram_pct,
            "rpm": rpm,
            "sample_count": count,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "max_latency_ms": max_latency,
            "errors_5xx": errors_5xx,
            "top_routes": top_slow_routes[:10],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def is_high_load(self) -> bool:
        """Determina se o banner de lentidão deve ser exibido."""
        with self._lock:
            inflight = self.in_flight_total
            if inflight >= DEFAULT_CONCURRENCY_GLOBAL_THRESHOLD:
                return True
            for route_count in self.in_flight_by_route.values():
                if route_count >= DEFAULT_CONCURRENCY_ROUTE_THRESHOLD:
                    return True
        _, _, ram_pct = self.get_memory_usage_mb()
        if ram_pct >= DEFAULT_RAM_THRESHOLD_PCT:
            return True
        return False

    def _evaluate_threshold_incident(self, route: str, dur_ms: float, status_code: int):
        """Dispara registro de incidente seletivo e notificação no WhatsApp de Fauzer com cooldown."""
        now = time.time()
        incident_type = "high_latency" if dur_ms > DEFAULT_LATENCY_THRESHOLD_MS else "server_error"
        last_t = self.last_alerts.get(incident_type, 0.0)

        if (now - last_t) < COOLDOWN_ALERT_SECONDS:
            return

        self.last_alerts[incident_type] = now
        used_mb, _, ram_pct = self.get_memory_usage_mb()

        # Executa em thread separada para não impactar o tempo de resposta da requisição
        threading.Thread(
            target=self._persist_and_notify_incident,
            args=(incident_type, route, dur_ms, ram_pct, used_mb, self.in_flight_total),
            daemon=True,
        ).start()

    def _persist_and_notify_incident(
        self, inc_type: str, route: str, dur_ms: float, ram_pct: float, ram_mb: float, inflight: int
    ):
        """Salva incidente no banco e envia mensagem no WhatsApp de Fauzer."""
        try:
            with db() as conn:
                ensure_incidents_table(conn)
                conn.execute(
                    """INSERT INTO infra_incidents 
                       (incident_type, severity, offensive_route, p95_latency_ms, ram_pct, ram_used_mb, in_flight_peak, details)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        inc_type,
                        "critical" if ram_pct >= 85 or dur_ms > 5000 else "warning",
                        route,
                        dur_ms,
                        ram_pct,
                        ram_mb,
                        inflight,
                        json.dumps({"env": "Render Free", "threads": 4, "workers": 1}),
                    ),
                )
                # Mantém histórico enxuto (últimos 100 incidentes)
                conn.execute(
                    """DELETE FROM infra_incidents 
                       WHERE id NOT IN (SELECT id FROM infra_incidents ORDER BY id DESC LIMIT 100)"""
                )
                conn.commit()
        except Exception as e:
            logger.error("[Telemetry Persist Incident Error]: %s", e)

        # Envio de Alerta no WhatsApp exclusivo para Fauzer
        try:
            from services.vercel_service import get_infra_config
            from services.whatsapp_service import send_whatsapp_message

            cfg = get_infra_config()
            phone_fauzer = cfg.get("phone_fauzer") or "+55 27 99999-9999"

            msg = (
                f"🚨 *[M-One Telemetria • Alerta de Estresse no Render]*\n\n"
                f"Olá Fauzer, detectamos lentidão ou alta concorrência no servidor:\n"
                f"• *Incidente:* {inc_type.upper()}\n"
                f"• *Rota Ofensora:* `{route}`\n"
                f"• *Latência:* {dur_ms} ms (limiar: > {DEFAULT_LATENCY_THRESHOLD_MS} ms)\n"
                f"• *RAM do Container:* {ram_mb} MB ({ram_pct}% de 512 MB)\n"
                f"• *Requisições Simultâneas:* {inflight} ativas\n\n"
                f"👉 Acesse o painel de telemetria:\n"
                f"https://m-one.majmobilidade.com.br/infra/performance"
            )
            send_whatsapp_message(phone_fauzer, msg)
            logger.info("[Telemetry WhatsApp Alert Sent to Fauzer]: %s", phone_fauzer)
        except Exception as e:
            logger.error("[Telemetry WhatsApp Alert Error]: %s", e)


def ensure_incidents_table(conn) -> None:
    """Garante a existência da tabela de incidentes de infraestrutura."""
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS infra_incidents (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                incident_type VARCHAR(64) NOT NULL,
                severity VARCHAR(20) NOT NULL DEFAULT 'warning',
                offensive_route VARCHAR(255),
                p95_latency_ms NUMERIC(10, 2),
                ram_pct NUMERIC(5, 2),
                ram_used_mb NUMERIC(10, 2),
                in_flight_peak INTEGER,
                details JSONB
            );
            CREATE INDEX IF NOT EXISTS idx_infra_incidents_created ON infra_incidents(created_at DESC);
        """
        )
        conn.commit()
    except Exception as e:
        logger.debug("[Telemetry Incidents Table Schema Check]: %s", e)


def fetch_recent_incidents(limit: int = 15) -> List[Dict[str, Any]]:
    """Consulta os últimos incidentes registrados no banco."""
    try:
        with db() as conn:
            ensure_incidents_table(conn)
            rows = conn.execute(
                """SELECT id, created_at, incident_type, severity, offensive_route,
                          p95_latency_ms, ram_pct, ram_used_mb, in_flight_peak, details
                   FROM infra_incidents
                   ORDER BY id DESC LIMIT %s""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows] if rows else []
    except Exception as e:
        logger.error("[Telemetry Fetch Incidents Error]: %s", e)
        return []


def send_test_render_alert_whatsapp(phone: str, recipient_name: str = "Fauzer") -> Dict[str, Any]:
    """Envia um alerta imediato de teste de estresse do Render via WhatsApp."""
    from services.whatsapp_service import send_whatsapp_message

    snap = telemetry.get_snapshot()
    msg = (
        f"🧪 *[M-One Telemetria • Teste de Alerta do Render]*\n\n"
        f"Olá {recipient_name}, este é um teste disparado pelo painel /infra/performance:\n\n"
        f"• *Status Atual:* {snap['status_label']}\n"
        f"• *RAM Utilizada:* {snap['ram_used_mb']} MB / {snap['ram_ceiling_mb']} MB ({snap['ram_pct']}%)\n"
        f"• *Latência p95:* {snap['p95_latency_ms']} ms\n"
        f"• *Requisições Ativas:* {snap['in_flight_total']} threads ocupadas\n"
        f"• *Ambiente:* Render Free (0.1 CPU, 512 MB, 1 worker / 4 threads)\n\n"
        f"✅ Disparo de telemetria configurado com sucesso!"
    )
    res = send_whatsapp_message(phone, msg)
    return {"success": True, "res": res}


# Instância singleton global do coletor
telemetry = TelemetryCollector()
