# Especificação Técnica: Upgrade do Sistema de Alerta e Telemetria em Tempo Real

**Status:** 📋 Documentado para implementação futura (`[upgrade do sistema de alerta]`)  
**Modo de Lançamento Definido:** 🧪 **Beta Restrito** (`super_admin_only: True` — exclusivo `@jam` e `@fauzer`, delegável em `/users`)  
**Módulo Base:** `/infra/performance` (`routes/infra_routes.py` + `templates/infra_performance.html`)

---

## 1. Contexto e Objetivo

Com a migração do M-One para o **Render Free** (`0.1 CPU`, `512 MB RAM`, `gunicorn --workers 1 --threads 4`), picos de acesso simultâneo na mesma rota ou consultas pesadas podem gerar lentidão perceptível para o time interno e risco de estouro de memória.

O objetivo deste upgrade é evoluir o painel atual de infraestrutura (`/infra/performance`) para um **Sistema de Telemetria, Diagnóstico e Alerta em Tempo Real** que atenda dois públicos:

1. **Gestão/Engenharia (`@jam` e `@fauzer`)**: gráficos em tempo real de latência, concorrência por rota, consumo de RAM/CPU, ranking de rotas congestionadas, histórico de incidentes e alertas proativos no WhatsApp.
2. **Usuários Internos**: aviso discreto e automático na interface apenas durante momentos reais de lentidão ou fila, orientando a aguardar sem recarregar a página (evitando "tempestade de F5").

---

## 2. Regras de Liberação e RBAC (`beta_feature_flag`)

- **Fase 1 (Beta Restrito)**:
  - A nova aba/seção de **Telemetria em Tempo Real**, novos endpoints de métricas e o banner de teste entram protegidos com `super_admin_only: True`.
  - Visível exclusivamente para `@jam` e `@fauzer` (e testadores explicitamente delegados via `/users`).
  - Permissões novas registradas obrigatoriamente em `ALL_PERMISSIONS` e auditadas via `scripts/permissions_audit.py`.
- **Fase 2 (Liberação Geral)**:
  - Após validação do overhead e estabilidade dos limiares, o banner de tráfego alto pode ser promovido para todos os usuários autenticados do M-One.

---

## 3. Arquitetura de Coleta (Zero Impacto no Banco)

Para não agravar a lentidão durante picos, **nenhuma requisição HTTP comum deve gravar telemetria no PostgreSQL/Supabase**.

### 3.1. Coletor em Memória (`services/telemetry_service.py`)
- **Overhead alvo:** `< 0.05 ms` por requisição via hooks `before_request` e `after_request` do Flask.
- **Estruturas thread-safe** (protegidas por `threading.Lock` enxuto, compatível com `--workers 1 --threads 4`):
  - `in_flight_total`: contador inteiro de requisições ativas no momento.
  - `in_flight_by_route`: mapa `{endpoint_ou_rota: contagem}` para detectar gargalos específicos (ex.: várias pessoas abrindo o mesmo relatório ou listagem pesada ao mesmo tempo).
  - **Buffer circular (`collections.deque(maxlen=300)` ou janela de 5–15 min)**: armazena amostras leves `(timestamp, rota, status_code, duracao_ms)` para cálculo de:
    - Latência média e **p95** global e por rota.
    - Taxa de requisições por minuto (RPM) e erros `5xx`.
    - Ranking de rotas mais lentas e mais concorridas.
- **Leitura Nativa de RAM e CPU (sem dependências pesadas como `psutil`)**:
  - Leitura direta via módulo padrão `resource` e `/proc/self/status` (`VmRSS`) no Linux (Render), com fallback seguro no macOS para testes locais.
  - Percentual calculado sobre o teto de `512 MB` do plano Render Free.
- **Integração Opcional com API do Render**:
  - Consulta à API oficial usando `RENDER_API_KEY` com **cache em memória de 60 segundos**, evitando chamadas repetidas e rate limit.

### 3.2. Persistência Seletiva de Incidentes
- O banco de dados é acionado **apenas quando um alerta crítico é disparado** (com cooldown configurável para evitar spam), registrando o snapshot do incidente (timestamp, tipo de alerta, rota ofensora, p95, RAM %, concorrência máxima) para alimentar o histórico no painel.

---

## 4. Limiares de Alerta (Editáveis via Painel)

Os valores abaixo serão os padrões iniciais, podendo ser ajustados dinamicamente por `@jam` e `@fauzer` na configuração do painel:

| Métrica | Limiar Padrão | Ação / Significado |
| :--- | :--- | :--- |
| **Latência (média ou p95)** | `> 3.000 ms` (`3s`) | Ativa estado de atenção/lentidão e exibe banner discreto para usuários (quando promovido). |
| **Concorrência na mesma rota** | `>= 3` requisições simultâneas | Identifica gargalo localizado na rota e sinaliza no ranking de congestionamento. |
| **Concorrência global** | `>= 8` requisições in-flight | Sinaliza saturação das threads do Gunicorn (`1 worker / 4 threads`). |
| **Consumo de RAM (Render)** | `>= 80%` (`~410 MB / 512 MB`) | Dispara alerta preventivo de memória antes de risco de OOM Kill. |

---

## 5. Experiência de Usuário (UX) e Visualização

### 5.1. Banner Discreto para Usuários Internos (`templates/base.html`)
- **Condição de exibição:** aparece **somente** quando houver lentidão real (`> 3.000 ms`) ou concorrência/fila acima do limiar. Em operação normal, permanece 100% oculto.
- **Mensagem padrão:**
  > `⏳ Sistema com alto tráfego no momento — aguarde alguns segundos sem recarregar a página.`
- **Objetivo:** reduzir cliques repetidos e tempestade de `F5` que multiplicam requisições em fila.

### 5.2. Painel Executivo e Gráficos (`/infra/performance`)
Evolução da página existente (`templates/infra_performance.html`) com aba/seção dedicada de **Telemetria em Tempo Real**:
- **Cards de Pulso Instantâneo:** Requisições ativas agora (`in_flight_total`), Latência p95 atual, Uso de RAM (`MB / 512 MB`), Estado do Sistema (`Normal` / `Atenção` / `Crítico`).
- **Gráficos Temporais (Chart.js / SVG leve em Dark Theme):**
  - Série temporal de Latência (média vs p95).
  - Série temporal de Concorrência simultânea e Uso de RAM.
- **Ranking de Rotas Congestionadas:** Top rotas por latência p95 e picos de requisições simultâneas.
- **Histórico de Incidentes + Alertas WhatsApp:** Log dos últimos eventos críticos e configuração de cooldown/destinatários (reaproveitando o fluxo de alerta existente em `services/vercel_service.py` / `routes/infra_routes.py`).

---

## 6. Plano Modular de Arquivos (Anti-Monólito `< 500` linhas)

Para manter todos os arquivos abaixo do limite de 500 linhas (`scripts/monolith_watcher.py`) e em conformidade com `scripts/ux_audit.py` e `scripts/permissions_audit.py`:

1. **`services/telemetry_service.py`** *(novo)*
   - Buffer circular em memória, contadores thread-safe, leitura nativa de RAM/CPU, cálculo de p95/ranking e avaliação de limiares.
2. **`routes/infra_routes.py`** *(evolução modular)*
   - Novos endpoints protegidos:
     - `GET /api/infra/telemetry` (snapshot JSON em tempo real para gráficos e status de tráfego).
     - `GET /api/infra/status-banner` (endpoint ultraleve para o banner condicional, respeitando Beta Flag).
     - Extensão de `POST /infra/config` para salvar os limiares editáveis de latência, concorrência e RAM.
3. **`app.py`** *(ajuste mínimo)*
   - Registro dos hooks `before_request` e `after_request` chamando `telemetry_service` (com bypass para arquivos estáticos `/public/images/`, `/static/`, `/healthz`).
4. **`templates/infra_performance.html`** e/ou parcial **`templates/partials/infra_telemetry.html`** *(evolução)*
   - Abas/seções em Dark Theme (`var(--surface-card)`, `var(--text-primary)`, `var(--border-subtle)`), gráficos de latência/concorrência/RAM, tabela de ranking e formulário de limiares.
   - Qualquer modal de detalhe de incidente deve usar `<template x-teleport="body">` e `.modal-close-btn` com SVG geométrico.
5. **`templates/base.html`** *(ajuste mínimo)*
   - Inclusão do banner condicional de alto tráfego (controlado por flag Beta na Fase 1).

---

## 7. Fases Sugeridas de Implementação

1. **Fase 1 — Motor de Coleta & API**: Criar `services/telemetry_service.py`, hooks em `app.py` e endpoint `GET /api/infra/telemetry` protegido por `super_admin_only: True`.
2. **Fase 2 — Painel Gráfico em `/infra/performance`**: Adicionar cards em tempo real, gráficos de latência/concorrência/RAM, ranking de rotas e edição de limiares.
3. **Fase 3 — Alertas WhatsApp & Histórico**: Ligar disparo com cooldown nos limiares críticos e persistir apenas eventos de incidente.
4. **Fase 4 — Banner Discreto & Validação**: Ativar o banner em `templates/base.html` para usuários Beta, validar com `scripts/validate.py`, `scripts/ux_audit.py` e `scripts/permissions_audit.py`, e depois promover de Beta para Geral quando aprovado.
