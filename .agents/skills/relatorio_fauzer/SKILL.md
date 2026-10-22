---
name: relatorio_fauzer
description: Protocolo RELATÓRIO FAUZER de consolidação diária de atividades. Vascula o histórico do chat, commits git do dia e arquivos modificados para gerar um relatório técnico detalhado e um resumo executivo em formato WhatsApp para a gerência. Ativado sempre que o usuário digitar [Relatório Fauzer] ou variações.
---

# Protocolo RELATÓRIO FAUZER — Consolidação Diária de Atividades

Este protocolo deve ser executado obrigatoriamente e imediatamente sempre que o usuário digitar `[Relatório Fauzer]`, `[relatorio fauzer]`, `relatório fauzer` ou `relatorio fauzer`.

## Objetivo:
Consolidar com fidelidade todas as tarefas, correções, implementações e entregas realizadas por Fauzer ao longo do dia no projeto M-One, gerando duas saídas complementares:
1. **Relatório Técnico & Executivo Detalhado**: Documentação completa das mudanças de código, regras de negócio, testes e commits.
2. **Resumo Executivo para WhatsApp**: Texto enxuto, profissional, redigido em 1ª pessoa com formatação nativa do WhatsApp (`*negrito*`, emojis executivos e tópicos `•`), pronto para copiar e colar para a gerência.

---

## Etapas Obrigatórias de Execução:

### Passo 01 — Varredura Híbrida de Atividades do Dia
O agente deve coletar evidências em 3 fontes essenciais:
1. **Git Commits de Hoje**:
   - Executar `git log --since="today 00:00" --oneline` (ou `git log -n 15 --since="midnight" --stat`).
   - Mapear mensagens de commit, hashs e componentes afetados.
2. **Status do Workspace Atual**:
   - Executar `git status -sb` e `git diff --stat` para identificar tarefas em andamento ou alterações não comitadas.
3. **Histórico do Chat da Sessão**:
   - Rastrear todas as solicitações do usuário no dia, dúvidas tiradas, diagnósticos realizados, testes executados e decisões aprovadas.
4. **Varredura da Central de Agentes de IA (Google Drive)**:
   - Vasculhar o diretório: `/Users/macstudio-maj/Library/CloudStorage/GoogleDrive-marketingmajv@gmail.com/Meu Drive/TRABALHOS - START | MAJ MOBILIDADE/AGENTES DE IA - MAJ`
   - Identificar alterações, scripts de automação, diagnósticos e relatórios recentes nos sub-agentes:
     - `[AGENTE DE MARKETING - MAJ MOBILIDADE]`: Otimizações de tráfego pago (Meta Ads), relatórios de performance diária e scripts (`trafego_maj/`).
     - `[BOT CONVERSA - AGENTE]`: Diagnósticos de automação de WhatsApp, funis de atendimento e relatórios em PDF.
     - `[REMOTION SKILL - MAJ]`: Produção de vídeos programáticos, composições criativas e arquitetura de renderização.

---

### Passo 02 — Estruturação do Relatório Detalhado
Gerar um relatório em Markdown estruturado com:
- 📅 **Data e Identificação**: Data do dia e autor (Fauzer).
- 🎯 **Demandas e Problemas Endereçados**: O que motivou os ajustes (ex: dores de UX, regras de negócio, correções visuais).
- 🛠️ **Entregas e Implementações Técnicas**:
  - Lista de componentes e arquivos alterados com links no formato `file://`.
  - Explicação clara de cada correção ou funcionalidade construída.
- 🛡️ **Qualidade e Validações**:
  - Resultado dos testes de integridade (`scripts/validate.py` e `scripts/ux_audit.py`).
  - Auditoria anti-monólito (`scripts/monolith_watcher.py`).
- 🚀 **Status de Publicação & Links**:
  - Confirmação de deploy online (Vercel) e links de teste.

---

### Passo 03 — Geração do Bloco WhatsApp (Para a Gerência)
Abaixo do relatório detalhado, fornecer o bloco formatado especificamente para WhatsApp:
- **Diretriz de Tamanho**: Versão **ultra-resumida e direta ao ponto**, leitura rápida em menos de 20 segundos para a gerência.
- **Regras de Formatação**:
  - Usar `*texto*` para negritos (e não `**texto**`).
  - Usar marcadores `•`.
  - Redigido em **1ª pessoa** por Fauzer.
  - Foco exclusivo em **resultados práticos e números chave**.
- **Estrutura Padrão Ultra-Resumida**:
  ```text
  *Resumo Diário — Fauzer (DD/MM)*

  Olá! Segue o resumo rápido das entregas de hoje:

  ⚡ *Sistema M-One:*
  • *Catálogos dos Parceiros:* Ajustei o contraste das margens, travei o modal para fechar só no "X" (sem perda de dados) e ativei o logo da MAJ automático quando não for White-Label.
  • *Deploy:* Versão validada e publicada em produção no ar.

  📈 *Tráfego Pago (Meta Ads):*
  • *Leads:* 73 novas conversas no WhatsApp (37 Varejo / 36 Atacado B2B).
  • *Custo por Lead:* Queda de 16% no custo por conversa (CPR médio caiu para R$ 2,54).

  🎬 *Automações:*
  • Esteira de vídeos do Remotion e monitoramento do BotConversa integrados e ativos.

  ✅ *Status:* 100% operacional no ar (https://m-one.majmobilidade.com.br).
  ```
