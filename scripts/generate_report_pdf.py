#!/usr/bin/env python3
"""
Script para gerar o Relatório Executivo dos 5 Passos em PDF de alta qualidade.
Utiliza Google Chrome Headless com renderização CSS de impressão.
"""

import os
import subprocess
import tempfile
from datetime import datetime

HTML_CONTENT = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Relatório Executivo — 5 Passos M-One</title>
  <style>
    @page {
      size: A4 portrait;
      margin: 6mm 10mm 6mm 10mm;
    }
    * {
      box-sizing: border-box;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    html, body {
      height: 100%;
      overflow: hidden;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      background: #ffffff;
      margin: 0;
      padding: 0;
      font-size: 9.5pt;
      line-height: 1.3;
    }
    .header-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #0284c7;
      padding-bottom: 8px;
      margin-bottom: 12px;
    }
    .brand-title {
      font-size: 18pt;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.5px;
      margin: 0;
    }
    .brand-subtitle {
      font-size: 9pt;
      color: #0284c7;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-top: 1px;
    }
    .meta-box {
      text-align: right;
      font-size: 8.5pt;
      color: #64748b;
      line-height: 1.25;
    }
    .meta-box b {
      color: #334155;
    }
    .badge {
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 7.5pt;
      font-weight: 700;
      text-transform: uppercase;
    }
    .badge-success {
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #bbf7d0;
    }
    .badge-info {
      background: #e0f2fe;
      color: #0369a1;
      border: 1px solid #bae6fd;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin-bottom: 12px;
    }
    .kpi-card {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 7px 10px;
      border-left: 3.5px solid #0284c7;
    }
    .kpi-card.green {
      border-left-color: #10b981;
    }
    .kpi-card.purple {
      border-left-color: #8b5cf6;
    }
    .kpi-card.amber {
      border-left-color: #f59e0b;
    }
    .kpi-label {
      font-size: 7.5pt;
      text-transform: uppercase;
      font-weight: 700;
      color: #64748b;
      margin-bottom: 2px;
    }
    .kpi-value {
      font-size: 13pt;
      font-weight: 800;
      color: #0f172a;
    }
    .kpi-desc {
      font-size: 7pt;
      color: #64748b;
      margin-top: 1px;
    }
    h2 {
      font-size: 11pt;
      font-weight: 700;
      color: #0f172a;
      margin: 10px 0 6px 0;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 3px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 10px;
      font-size: 8.5pt;
    }
    th {
      background: #f1f5f9;
      color: #334155;
      text-align: left;
      padding: 5px 8px;
      font-weight: 700;
      border-top: 1px solid #cbd5e1;
      border-bottom: 1px solid #cbd5e1;
    }
    td {
      padding: 5px 8px;
      border-bottom: 1px solid #f1f5f9;
      vertical-align: top;
    }
    tr:nth-child(even) td {
      background: #f8fafc;
    }
    .steps-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 10px;
    }
    .step-box {
      border: 1px solid #e2e8f0;
      border-radius: 5px;
      padding: 6px 10px;
      background: #ffffff;
      page-break-inside: avoid;
    }
    .step-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2px;
    }
    .step-title {
      font-size: 9pt;
      font-weight: 700;
      color: #0f172a;
    }
    .step-duration {
      font-size: 7.5pt;
      font-weight: 700;
      color: #0284c7;
      background: #f0f9ff;
      padding: 1px 6px;
      border-radius: 3px;
      border: 1px solid #e0f2fe;
    }
    .step-desc {
      font-size: 8pt;
      color: #475569;
      margin: 0;
      line-height: 1.3;
    }
    .step-bullets {
      margin: 2px 0 0 0;
      padding-left: 14px;
      font-size: 7.5pt;
      color: #475569;
    }
    .step-bullets li {
      margin-bottom: 1px;
    }
    .footer-note {
      margin-top: 8px;
      padding-top: 6px;
      border-top: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 7.5pt;
      color: #94a3b8;
    }
    .code-badge {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 7.5pt;
      background: #f1f5f9;
      padding: 1px 5px;
      border-radius: 3px;
      color: #0f172a;
    }
  </style>
</head>
<body>

  <!-- Header -->
  <div class="header-bar">
    <div>
      <h1 class="brand-title">M-One • MAJ Operating System</h1>
      <div class="brand-subtitle">Relatório Executivo de Modernização de Arquitetura</div>
    </div>
    <div class="meta-box">
      <div><b>Data:</b> 09/09/2026</div>
      <div><b>Destinatários:</b> Jam & Fauzer</div>
      <div><b>Status:</b> <span class="badge badge-success">Concluído 100%</span></div>
    </div>
  </div>

  <!-- KPI Grid -->
  <div class="kpi-grid">
    <div class="kpi-card green">
      <div class="kpi-label">Progresso Total</div>
      <div class="kpi-value">5 de 5</div>
      <div class="kpi-desc">100% das etapas executadas</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Duração Global</div>
      <div class="kpi-value">2h 50min</div>
      <div class="kpi-desc">Início 15:22 • Conclusão 18:11</div>
    </div>
    <div class="kpi-card purple">
      <div class="kpi-label">Redução do Monólito</div>
      <div class="kpi-value">-98.1%</div>
      <div class="kpi-desc">app.py: 3.340 para 64 linhas</div>
    </div>
    <div class="kpi-card amber">
      <div class="kpi-label">Banco Padronizado</div>
      <div class="kpi-value">Postgres</div>
      <div class="kpi-desc">Supabase Pooler IPv4 único</div>
    </div>
  </div>

  <!-- Tabela Cronológica -->
  <h2>1. Cronograma de Execução e Durações</h2>
  <table>
    <thead>
      <tr>
        <th style="width: 14%;">Etapa</th>
        <th>Objetivo Estratégico</th>
        <th style="width: 13%;">Horário</th>
        <th style="width: 12%;">Duração</th>
        <th style="width: 14%;">Commit Git</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><b>Passo 1</b></td>
        <td>Segurança imediata, saneamento de chaves e protocolos de governança</td>
        <td>15:22 – 15:28</td>
        <td><b>~6 min</b></td>
        <td><span class="code-badge">77743c5</span></td>
      </tr>
      <tr>
        <td><b>Passo 2</b></td>
        <td>Modularização em 13 Blueprints Flask e agente anti-monólito (&lt;500 linhas)</td>
        <td>15:29 – 16:14</td>
        <td><b>~45 min</b></td>
        <td><span class="code-badge">6180080</span></td>
      </tr>
      <tr>
        <td><b>Passo 3</b></td>
        <td>Aposentadoria de adaptações SQL e adoção nativa do PostgreSQL Supabase</td>
        <td>16:16 – 17:01</td>
        <td><b>~45 min</b></td>
        <td><span class="code-badge">74bb309</span></td>
      </tr>
      <tr>
        <td><b>Passo 4</b></td>
        <td>Modernização leve com HTMX, Alpine.js e gráficos analíticos (Chart.js)</td>
        <td>17:01 – 17:18</td>
        <td><b>~18 min</b></td>
        <td><span class="code-badge">c41acec</span></td>
      </tr>
      <tr>
        <td><b>Passo 5</b></td>
        <td>Telemetria Vercel (/infra/performance) e Alerta WhatsApp Meta aos 75%</td>
        <td>17:26 – 18:11</td>
        <td><b>~45 min</b></td>
        <td><span class="badge badge-info">Pronto Deploy</span></td>
      </tr>
    </tbody>
  </table>

  <!-- Detalhamento dos Passos -->
  <h2>2. Síntese Técnica das Implementações</h2>
  <div class="steps-list">

    <div class="step-box">
      <div class="step-header">
        <span class="step-title">🚀 Passo 1 — Segurança Imediata (Prioridade Zero)</span>
        <span class="step-duration">Duração: ~6 min</span>
      </div>
      <p class="step-desc">Eliminação de vulnerabilidades e estabelecimento de esteira segura de entrega contínua.</p>
      <ul class="step-bullets">
        <li>Saneamento de credenciais e tokens em arquivos de código;</li>
        <li>Remoção definitiva de automações legadas instáveis que causavam travamentos;</li>
        <li>Implementação dos comandos oficiais de governança <b>[start]</b> e <b>[deploy]</b>.</li>
      </ul>
    </div>

    <div class="step-box">
      <div class="step-header">
        <span class="step-title">🧩 Passo 2 — Modularização em Blueprints (Arquitetura Limpa)</span>
        <span class="step-duration">Duração: ~45 min</span>
      </div>
      <p class="step-desc">Fatiamento estrutural do monólito com limite rígido de 500 linhas por arquivo.</p>
      <ul class="step-bullets">
        <li>Criação de 13 módulos coesos em <code>routes/</code> (vendas, fretes, estoque, CRM, importação, etc.);</li>
        <li>Redução drástica do <code>app.py</code> de ~3.340 linhas para <b>64 linhas</b>;</li>
        <li>Instalação do agente auditor automático <code>scripts/monolith_watcher.py</code>.</li>
      </ul>
    </div>

    <div class="step-box">
      <div class="step-header">
        <span class="step-title">🗄️ Passo 3 — Padronização de Banco (PostgreSQL Oficial Supabase)</span>
        <span class="step-duration">Duração: ~45 min</span>
      </div>
      <p class="step-desc">Aposentadoria de compatibilidades SQLite e uso de recursos avançados do PostgreSQL.</p>
      <ul class="step-bullets">
        <li>Eliminação do conversor frágil <code>.replace("?", "%s")</code> em <code>database.py</code>;</li>
        <li>Queries nativas com parâmetros tipados, <code>RETURNING</code> e funções de agregação;</li>
        <li>Conexão de altíssimo desempenho via Pooler IPv4 oficial Supabase em porta 6543.</li>
      </ul>
    </div>

    <div class="step-box">
      <div class="step-header">
        <span class="step-title">💻 Passo 4 — Modernização Leve de Frontend (HTMX + Alpine + Dashboards)</span>
        <span class="step-duration">Duração: ~18 min</span>
      </div>
      <p class="step-desc">Reatividade moderna e fluida sem a complexidade de reconstruir tudo em React/Vue.</p>
      <ul class="step-bullets">
        <li>Kanban do CRM e filtros de estoque atualizam instantaneamente sem recarregar tela;</li>
        <li>Dashboards analíticos enriquecidos com gráficos dinâmicos e responsivos (Chart.js);</li>
        <li>Preservação integral dos templates Jinja2 e performance ultra leve no carregamento.</li>
      </ul>
    </div>

    <div class="step-box">
      <div class="step-header">
        <span class="step-title">🚨 Passo 5 — Hospedagem Futura e Monitor de Desempenho Vercel</span>
        <span class="step-duration">Duração: ~45 min</span>
      </div>
      <p class="step-desc">Visibilidade em tempo real das cotas da Vercel e gatilho inteligente de migração.</p>
      <ul class="step-bullets">
        <li>Painel <code>/infra/performance</code> restrito exclusivamente a <b>Jam</b> e <b>Fauzer</b>;</li>
        <li>Acompanhamento dos 4 limites Hobby: GB-Horas, Bandwidth, Invocação/dia e Latência;</li>
        <li>Gatilho automático aos <b>75%</b> com envio de alerta no WhatsApp via Meta API e botão de teste.</li>
      </ul>
    </div>

  </div>

  <!-- Rodapé -->
  <div class="footer-note">
    <div><b>M-One Operating System</b> • MAJ Mobilidade</div>
    <div>Relatório gerado automaticamente • Antigravity AI Engine</div>
  </div>

</body>
</html>
"""

def generate_pdf():
    output_pdf_path = os.path.abspath("Relatorio_Executivo_5_Passos_MOne.pdf")
    
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(HTML_CONTENT)
        temp_html_path = f.name

    try:
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        cmd = [
            chrome_path,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_pdf_path}",
            f"file://{temp_html_path}"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(output_pdf_path):
            file_size = os.path.getsize(output_pdf_path)
            print(f"SUCCESS: PDF gerado em '{output_pdf_path}' ({file_size} bytes)")
        else:
            print("Erro ao gerar PDF:", res.stderr)
    finally:
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)

if __name__ == "__main__":
    generate_pdf()
