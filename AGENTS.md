# Regras e Diretrizes do Projeto M-One (MAJ Operating System)

## Protocolo Especial: [start]
Sempre que o usuário digitar `[start]` ou `start`:
O agente DEVE executar imediatamente o **Protocolo START** em 3 etapas sequenciais:

1. **Passo 01 — Git Fetch e Análise de Sincronização**:
   - Rodar `git fetch origin`.
   - Comparar `HEAD` local com `origin/main` (`git status -sb`, `git log origin/main..HEAD`, `git log HEAD..origin/main`).
   - Identificar se há necessidade de `git pull` (novos commits na nuvem), `git push` (commits locais pendentes) ou se está 100% sincronizado.
   - Listar arquivos modificados ou unstaged se houver.

2. **Passo 02 — Inicialização do Ambiente**:
   - Checar se o servidor local Flask na porta `5001` está ativo.
   - Se não estiver ativo, iniciá-lo imediatamente (`PORT=5001 .venv/bin/python3 app.py` ou `./dev.sh`).
   - Validar com `curl` que o serviço está respondendo HTTP 200.

3. **Passo 03 — Varredura Anti-Monólito e Auditoria de Permissões RBAC**:
   - Executar o auditor de monólitos: `.venv/bin/python3 scripts/monolith_watcher.py --scan`.
   - Executar o auditor de permissões RBAC: `.venv/bin/python3 scripts/permissions_audit.py`.
   - Alertar o usuário caso haja arquivos > 500 linhas ou funções novas sem cadastro no menu de permissões dos usuários (`ALL_PERMISSIONS`).

4. **Passo 04 — Relatório Consolidado e Links de Teste**:
   - Gerar um relatório claro com:
     - Situação da sincronização do código (commits à frente/atrás, alterações pendentes).
     - Status dos serviços locais e conexão com o Supabase.
     - Diagnóstico de monólitos e cobertura de permissões RBAC.
     - Link para teste local: `http://localhost:5001`
     - Link oficial de produção: `https://m-one.majmobilidade.com.br`

---

## Protocolo Especial: [deploy]
Sempre que o usuário digitar `[deploy]` ou `deploy`:
O agente DEVE executar imediatamente o **Protocolo DEPLOY** em 3 etapas sequenciais:

1. **Passo 01 — Varredura e Validação de Integridade do Código**:
   - Executar varredura profunda com o script `.venv/bin/python3 scripts/validate.py`.
   - Auditar paridade estrita de dependências (AST Scan vs `requirements.txt`), sintaxe recursiva em todos os arquivos `.py`, integridade de templates Jinja2, **auditoria de UX/UI (modais centralizados e paleta de cores via `scripts/ux_audit.py`)**, canais de venda comerciais (`/outlet`, `/atacado`, `/modelos`, `/login`) e **auditoria de cobertura de permissões RBAC (`scripts/permissions_audit.py`)**.
   - Checar integridade da conexão Supabase IPv4 Pooler.
   - **Trava de Segurança**: Se houver qualquer erro de dependência, sintaxe, UX, rota comercial ou **módulo/função sem permissão cadastrada**, **interromper imediatamente**, relatar o erro e NÃO fazer o push.

2. **Passo 02 — Git Commit e Push Automático**:
   - Verificar arquivos alterados ou pendentes (`git status -sb`).
   - Fazer `git add .` dos arquivos alterados na sessão (respeitando `.gitignore`).
   - Criar commit objetivo descrevendo as alterações da sessão.
   - Executar `git push origin main` para acionar o deploy automático na Vercel.

3. **Passo 03 — Relatório de Publicação e Smoke Test Online**:
   - Resumo da varredura preditiva (status das 7 etapas).
   - Detalhes do commit enviado e lista de arquivos atualizados.
   - Executar Smoke Test ao vivo com `curl -sI https://m-one.majmobilidade.com.br/outlet` e `/login` para confirmar HTTP 200 no ar.
   - Link de produção oficial atualizado: `https://m-one.majmobilidade.com.br`

---

## Protocolo Especial: [Relatório Fauzer]
Sempre que o usuário digitar `[Relatório Fauzer]`, `[relatorio fauzer]`, `relatório fauzer` ou `relatorio fauzer`:
O agente DEVE executar imediatamente o **Protocolo RELATÓRIO FAUZER** em 3 etapas sequenciais:

1. **Passo 01 — Varredura Híbrida de Atividades do Dia**:
   - Vasculhar o Git: rodar `git log --since="today 00:00" --oneline` (ou `git log -n 15 --since="midnight" --stat`) para listar commits realizados no dia.
   - Vasculhar o Workspace: rodar `git status -sb` e `git diff --stat` para capturar alterações em andamento.
   - Vasculhar o Chat da Sessão: rastrear todas as demandas, problemas investigados, diagnósticos e soluções aprovadas durante o dia.
   - Vasculhar a Central de Agentes de IA (Google Drive): `/Users/macstudio-maj/Library/CloudStorage/GoogleDrive-marketingmajv@gmail.com/Meu Drive/TRABALHOS - START | MAJ MOBILIDADE/AGENTES DE IA - MAJ` (`[AGENTE DE MARKETING - MAJ MOBILIDADE]`, `[BOT CONVERSA - AGENTE]`, `[REMOTION SKILL - MAJ]`).

2. **Passo 02 — Estruturação do Relatório Técnico & Executivo Detalhado**:
   - Gerar relatório Markdown completo contendo:
     - 🎯 **Demandas e Problemas Endereçados**: Contexto operacional e dores resolvidas.
     - 🛠️ **Entregas e Implementações Técnicas**: Arquivos modificados (`file://`) e detalhamento das soluções.
     - 🛡️ **Qualidade e Validações**: Status dos testes de integridade, UX/UI e monólitos.
     - 🚀 **Status de Deploy**: Confirmação da publicação e links oficiais.

3. **Passo 03 — Geração do Bloco WhatsApp (Para Envio à Gerência)**:
   - Apresentar, ao final, um bloco formatado exclusivamente para WhatsApp (`*negrito*`, marcadores `•` e emojis executivos).
   - Redigido em **1ª pessoa** por Fauzer (*"Hoje entreguei...", "Ajustei...", "Subi em produção..."*).
   - Foco executivo em **valor entregue**, agilidade e benefícios para a operação da MAJ Mobilidade, sem excesso de jargões herméticos, pronto para copiar e colar para a gerência.

---

## Protocolo Especial: [Relatório do Ciclo 2]
Sempre que o usuário digitar `[Relatório do Ciclo Dois]`, `[relatório do ciclo 2]`, `relatório do ciclo dois`, `relatorio do ciclo 2` ou variações:
O agente DEVE:
1. Recuperar e carregar imediatamente o documento oficial [docs/RELATORIO_CICLO_2.md](file:///Users/macstudio-maj/Documents/Desenvolvimento/Aplicativos/MOne/docs/RELATORIO_CICLO_2.md).
2. Apresentar a estrutura executiva consolidada (Demandas, Entregas por Área de Negócio, Confiabilidade Técnica e Indicadores).
3. Disponibilizar o bloco de WhatsApp pronto para cópia e envio à gerência e diretoria.

---

## Regras de Negócio e Desenvolvimento
- **Porta Local**: Usar sempre a porta `5001` (a porta 5000 do macOS é ocupada pelo AirPlay / ControlCenter).
- **Banco de Dados**: Usar sempre o pooler IPv4 oficial do Supabase:
  `aws-0-us-west-2.pooler.supabase.com:6543` com `sslmode=require`.
- **Regra de Vendas**: Toda venda exige chassi existente, liberado (`available`) e não duplicado.
- **Sigilo**: Custos de contêineres e importações são restritos à Diretoria (`admin`) e Suporte Técnico (`support`).
- **Regra de Importação (PI vs CI e Quitação de Compra)**:
  - **PI (Proforma Invoice)**: Valor total pago ao fornecedor (incluindo eventual frete internacional negociado). Representa o montante total da compra.
  - **CI (Commercial Invoice)**: Valor total oficial pago ao fornecedor declarado à Receita Federal para desembaraço aduaneiro.
  - **Equação Fundamental da Compra**:
    $$\mathbf{PI = CI + PAGAMENTO\ EXTRA}$$
    - Portanto, $\mathbf{PAGAMENTO\ EXTRA = PI - CI}$.
    - Qualquer valor desembolsado além da CI (ou a diferença entre a fatura proforma total e a fatura comercial alfandegária) é registrado e auditado como **Pagamento Extra / Outro Lançamento**, completando a compra sem duplicar custos.
    - A presença de **Contrato de Câmbio** e/ou **Comprovante SWIFT** registra e liquida oficialmente a parcela da CI (`ci_payment`), zerando a pendência de dados na auditoria aduaneira.
- **Regra de Exibição de Estoque: Outlet MAJ (OM) vs MAJ Catálogo CNPJ (MCC)**:
  - **Os valores de estoque entre OM e MCC NÃO devem ser necessariamente idênticos**, pois atendem a canais e estratégias comerciais distintas:
  - **OM (Outlet MAJ — Varejo / Consumidor Final B2C)**:
    - Opera com **lotes promocionais específicos de desova** (predominantemente alocados no Galpão MAJ ou cotas restritas de varejo).
    - Utiliza gatilhos comerciais de escassez e exclusividade (*"Últimas unidades"*, *"Peça única"*), evitando expor o volume massivo de atacado para não canibalizar preços de revenda nem comprometer lotes B2B.
  - **MCC (MAJ Catálogo CNPJ — Atacado / Revenda B2B)**:
    - Opera com **Estoque Global Unificado** (Galpão MAJ + Galpão COLVIX / M-One), descontando apenas veículos com cliente/venda já vinculados.
    - Exibe o volume total real de pronta entrega (*"219 em estoque"*, *"73 em estoque"*), demonstrando robustez e capacidade de suprimento para lojistas e revendedores corporativos.

---

## Auditoria Anti-Monolito Contínua
Você deve combater ativamente o inchaço e a formação de monólitos de código no M-One:
- **Limite de Linhas**: Arquivos de rotas, scripts e templates não devem ultrapassar a marca de **500 linhas**.
- **Pausa Proativa**: Ao realizar alterações ou adicionar novas funcionalidades em arquivos que ultrapassem 500 linhas (especialmente o `app.py`), a IA deve pausar e propor a extração cirúrgica de rotas em Blueprints modulares (`routes/`).
- **Watcher em Segundo Plano**: O projeto conta com o agente de monitoração `scripts/monolith_watcher.py` (ou `scripts/monolith-watcher.js`), que alerta no terminal e via notificações nativas do sistema operacional sempre que um arquivo exceder o limite.

---

## Diretrizes Inegociáveis de UX/UI & Auditoria Pré-Entrega (Modais e Cores)
Erros visuais de modais desalinhados e esquemas de cores bagunçados são proibidos no M-One:
1. **Centralização e Isolamento Absoluto de Modais**:
   - Todo modal implementado com Alpine.js dentro do layout administrativo (`base.html`) **DEVE OBRIGATORIAMENTE** ser envolvido com `<template x-teleport="body">`.
   - Isso evita o *CSS containment trap* (quando o modal fica preso dentro de containers com `overflow`, `flex` ou margens, sendo empurrado para o canto esquerdo da tela).
   - Utilizar a estrutura nativa padronizada do M-One:
     - Overlay/Backdrop: `.modal.show` com `background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px);`
     - Caixa de conteúdo: `.modal-card` com `background: var(--panel); border: 1px solid var(--line); border-radius: 16px;`
     - Cabeçalho: `.modal-head` com título `var(--text)` e subtítulo `var(--muted)`
2. **Esquema de Cores & Contraste (Dark Theme First)**:
   - **Proibido inputs brancos estourados**: Nunca usar `background: #fff` ou inputs desestilizados que assumam fundo branco do navegador. Todos os inputs, selects e textareas devem usar `class="form-input"` ou `background: var(--panel2); color: var(--text); border: 1px solid var(--line);`.
   - **Proibido texto escuro sobre fundo escuro**: Todo texto, label e subtítulo deve usar explicitamente `var(--text, #f8fafc)` ou `var(--muted, #94a3b8)`. Texto preto (`#000`) só é permitido sobre fundos com contraste luminoso comprovado (ex: botões dourados/verdes `#e5a93b`, `#00cc88` ou `#00e599`).
   - **Botões**: Ação principal com `class="btn primary"` e ação secundária/cancelar com `class="btn"`.
3. **Alinhamento e Geometria Milimétrica do Botão Fechar ('X')**:
   - **Proibido usar `.btn.sm` ou `.btn` no botão de fechar modal**: essas classes aplicam padding retangular assimétrico (`padding: 5px 12px`), empurrando o `x` para baixo e para a direita.
   - **Proibido usar padding inline não-nulo** ou caracteres tipográficos crus (`&times;`, `×`, `x`) sem SVG geométrico, pois fontes sofrem distorção de baseline.
   - **Padrão Obrigatório**: Utilizar sempre `class="modal-close-btn"` com SVG geométrico perfeitamente centralizado (`viewBox="0 0 24 24"` com duas linhas cruzadas) e `padding: 0; display: flex; align-items: center; justify-content: center;`.
4. **Trava de Qualidade Automática Obrigatória**:
   - Antes de considerar qualquer funcionalidade concluída, o agente **DEVE EXECUTAR**:
     `.venv/bin/python3 scripts/ux_audit.py`
   - Se houver qualquer erro crítico de contenção de modal, contraste ou alinhamento do botão 'X', a entrega é reprovada e deve ser corrigida imediatamente.

---

### 📌 Padronização Global de Fontes de Dados e Automação 24/7 (Padrão Frete + Outlet)
- **Diretriz**: Replicar a arquitetura da aba **Fontes de Dados** (presente no módulo de Fretes `/freight`) combinada com o **Painel Executivo e Motor de Automação 24/7** (desenvolvido no Outlet MAJ `/admin/outlet`) para todas as demais sessões operacionais do app.
- **Componentes Obrigatórios do Padrão em Cada Sessão**:
  1. **Gestão de Fontes de Dados**: Cadastro e mapeamento transparente de origens (Google Sheets, CSV/XLSX, APIs externas, ERP Bling, webhooks).
  2. **Central de Automação & Sincronização**:
     - Painel visual expansível/recolhível com Alpine.js, sem sobrecarregar a tela principal.
     - Botão de atalho rápido no cabeçalho superior (`⚡ Automação 24/7`).
     - Badges de monitoramento: Status de execução, periodicidade (horária/diária), carimbo da última sincronização e resumo numérico de registros afetados.
     - Botão de disparo manual instantâneo (`⚡ Sincronizar Agora`).
     - Acessos diretos para visualização da planilha/origem e visão consolidada.
  3. **Regra Inegociável Anti-Reset**:
     - A rotina de sincronização **NUNCA DEVE RESETAR** o banco de dados. Fotos, mídias cadastradas, campos manuais, chassis vinculados e status operacionais devem ser preservados integralmente.
  4. **Engenharia Modular (Anti-Monólito)**:
     - Lógica de sincronização desacoplada em serviços especializados (`services/*_sync_service.py`), mantendo arquivos abaixo de 500 linhas.
     - Endpoints limpos para gatilho manual e chamadas externas (`/cron/<modulo>-sync`).
- **Módulos no Escopo de Implementação**:
  - `[ ]` **Estoque & Chassis (`/stock`)**: Sincronização automatizada de lotes de contêineres, Galpão MAJ, Galpão COLVIX e Bling ERP.
  - `[ ]` **Importações (`/imports`)**: Automação das faturas China (PI/CI), Despesas Brasil, contratos de câmbio e status de navios.
  - `[ ]` **Produtos & Catálogo (`/products` / `/atacado`)**: Sincronização de catálogo B2B, pesos cubados, dimensões e dados técnicos.
  - `[ ]` **Vendas (`/sales`)**: Sincronização contínua de pedidos Bling, notas fiscais emitidas e status de faturamento.
  - `[ ]` **Fiscal & Precificação (`/fiscal/pricing`)**: Sincronização de regras tributárias, MVAs e alíquotas interestaduais.

---

## Diretriz de Decisão e Comunicação: Opção Recomendada Obrigatória
Sempre que o agente apresentar opções, alternativas, cenários ou caminhos de solução (Opções A, B, C, etc.) ao usuário:
1. **O agente DEVE OBRIGATORIAMENTE indicar e destacar com clareza a Opção Recomendada**.
2. A opção recomendada deve vir sempre destacada como **(Recomendada)** ou posicionada em primeiro lugar, acompanhada de justificativa técnica e operacional objetiva (por que é a mais rápida, segura, eficiente ou alinhada com as melhores práticas de negócio da MAJ).
3. O agente deve assumir uma postura consultiva sênior e assertiva, facilitando a tomada de decisão do usuário e direcionando para a melhor execução prática imediata.
