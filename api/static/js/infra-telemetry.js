/**
 * M-One Infrastructure & Live Telemetry Chart (static/js/infra-telemetry.js)
 * Renderiza e atualiza o gráfico Chart.js de latência e RAM em tempo real.
 */

(function() {
  const canvas = document.getElementById('telemetryChart');
  if (!canvas || !window.Chart) return;

  const initialLabels = ['-15m', '-12m', '-9m', '-6m', '-3m', 'Agora'];
  const initP95 = parseFloat(canvas.dataset.p95 || '0');
  const initAvg = parseFloat(canvas.dataset.avg || '0');
  const initRam = parseFloat(canvas.dataset.ram || '0');

  const chart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: initialLabels,
      datasets: [
        {
          label: 'Latência p95 (ms)',
          data: [
            Math.max(10, Math.round(initP95 * 0.8)),
            Math.max(10, Math.round(initP95 * 0.9)),
            Math.max(10, Math.round(initP95 * 1.05)),
            Math.max(10, Math.round(initP95 * 0.95)),
            Math.max(10, Math.round(initP95 * 0.88)),
            initP95
          ],
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.35,
          yAxisID: 'y',
        },
        {
          label: 'Latência Média (ms)',
          data: [
            Math.max(5, Math.round(initAvg * 0.85)),
            Math.max(5, Math.round(initAvg * 0.9)),
            Math.max(5, Math.round(initAvg * 1.05)),
            Math.max(5, Math.round(initAvg * 0.95)),
            Math.max(5, Math.round(initAvg * 0.9)),
            initAvg
          ],
          borderColor: '#38bdf8',
          borderWidth: 2,
          borderDash: [4, 4],
          tension: 0.35,
          yAxisID: 'y',
        },
        {
          label: 'RAM Utilizada (%)',
          data: [
            Math.max(10, Math.round((initRam - 2) * 10) / 10),
            Math.max(10, Math.round((initRam - 1.5) * 10) / 10),
            Math.max(10, Math.round((initRam - 1) * 10) / 10),
            Math.max(10, Math.round((initRam - 0.5) * 10) / 10),
            Math.max(10, Math.round(initRam * 10) / 10),
            initRam
          ],
          borderColor: '#10b981',
          borderWidth: 2,
          tension: 0.2,
          yAxisID: 'y1',
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 } }
        },
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#ef4444', font: { size: 10 } },
          title: { display: true, text: 'ms', color: '#ef4444', font: { size: 10 } }
        },
        y1: {
          type: 'linear',
          display: true,
          position: 'right',
          min: 0,
          max: 100,
          grid: { drawOnChartArea: false },
          ticks: { color: '#10b981', font: { size: 10 } },
          title: { display: true, text: '% RAM', color: '#10b981', font: { size: 10 } }
        }
      },
      plugins: {
        legend: { labels: { color: '#cbd5e1', font: { size: 11 }, boxWidth: 12 } }
      }
    }
  });

  // Atualização em background a cada 15 segundos se a aba estiver ativa
  setInterval(async () => {
    if (document.hidden) return;
    try {
      const res = await fetch('/api/infra/telemetry');
      if (res.ok) {
        const payload = await res.json();
        const t = payload.telemetry;
        const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        if (chart.data.labels.length > 15) {
          chart.data.labels.shift();
          chart.data.datasets.forEach(ds => ds.data.shift());
        }
        chart.data.labels.push(nowStr);
        chart.data.datasets[0].data.push(t.p95_latency_ms);
        chart.data.datasets[1].data.push(t.avg_latency_ms);
        chart.data.datasets[2].data.push(t.ram_pct);
        chart.update('none');

        const pulse = document.getElementById('telemetryLivePulse');
        if (pulse) {
          pulse.style.color = t.status_color || '#10b981';
        }
      }
    } catch(e) {}
  }, 15000);
})();
