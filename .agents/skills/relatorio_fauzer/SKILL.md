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
- **Regras de Formatação**:
  - Usar `*texto*` para negritos (e não `**texto**`).
  - Usar marcadores de lista `•` ou `-`.
  - Sem tags HTML ou blocos de código markdown desnecessários.
- **Tom e Perspectiva**:
  - Redigido em **1ª pessoa** por Fauzer (*"Hoje finalizei...", "Implementei...", "Ajustei..."*).
  - Linguagem executiva, clara e focada em **valor de negócio**, impacto na operação e melhoria da experiência dos clientes/parceiros, sem excesso de jargões técnicos herméticos.
- **Estrutura Padrão do WhatsApp**:
  ```text
  *Resumo Diário de Atividades — M-One*
  *Data:* [Data de Hoje]
  *Profissional:* Fauzer

  *Principais Entregas de Hoje:*
  • *[Item 1]:* [Breve descrição do valor entregue]
  • *[Item 2]:* [Breve descrição do valor entregue]
  • *[Item 3]:* [Breve descrição do valor entregue]

  *Status Operacional:*
  • Testes de integridade e UX: Aprovados ✅
  • Deploy em produção: Realizado e operando no ar 🚀
  • Link do sistema: https://m-one.majmobilidade.com.br
  ```
