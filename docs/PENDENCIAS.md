# Roadmap de Implementação: Padronização Global de Fontes de Dados e Automação 24/7

> **Status**: Pendência Cadastrada / Backlog Prioritário  
> **Referência Visual & Operacional**: Módulo de Fretes (`/freight` - Aba Fontes de Dados) + Módulo Outlet MAJ (`/admin/outlet` - Painel Executivo e Motor de Automação).

---

## 1. Visão Geral e Objetivo

Padronizar a gestão de dados de todas as seções operacionais do **M-One** segundo o modelo híbrido já homologado com sucesso nos módulos de **Fretes** e **Outlet MAJ**:

1. **Gestão de Fontes de Dados (Modelo Frete)**:
   - Estrutura clara e auditável de mapeamento da origem de dados (Google Sheets, CSV/XLSX locais, APIs REST, ERP Bling).
   - Histórico e logs de sincronização, contagem de registros e status de saúde da fonte.
2. **Motor de Automação 24/7 & Painel Executivo (Modelo Outlet)**:
   - Painel compacto e expansível via Alpine.js (`x-data="{ open: false }"`) no topo ou aba de cada seção.
   - Botão de atalho rápido no cabeçalho superior (`⚡ Automação 24/7`) acionando evento customizado (`@toggle-automation-panel.window`).
   - Badges de status executivo: periodicidade, última sincronização com contagem de registros, proteção de integridade.
   - Botão de disparo manual imediato (`⚡ Sincronizar Agora`).
   - Botão de download/visualização da planilha/origem bruta e visualização consolidada.
3. **Regra Inegociável Anti-Reset**:
   - As rotinas automáticas de ingestão **NUNCA DEVE RESETAR** tabelas ou apagar registros manuais.
   - Atualizações devem operar no modo **Upsert Seguro** (insere novos registros e atualiza campos comerciais/estoque, preservando fotos, mídias, vínculos, notas manuais e chassis).
4. **Arquitetura Modular Anti-Monólito**:
   - Toda lógica de ingestão e parse isolada em `services/<modulo>_sync_service.py` (mantendo arquivos estritamente abaixo de 500 linhas).
   - Rotas dedicadas de webhook/cron (ex: `/cron/<modulo>-sync`).

---

## 2. Matriz de Módulos e Escopo de Implementação

| Módulo | Seção | Fonte(s) de Dados Principal(is) | Tipo de Sincronização | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Fretes** | `/freight` | Tabelas de frete transportadoras (TJB, Vinislog, Generoso) | Upload XLSX / Manual / Cache | ✅ Concluído (Padrão 1) |
| **Outlet MAJ** | `/admin/outlet` | Planilha oficial de lotes promocionais (`tabela_precos_outlet.csv`) | Automação Horária + Botão Manual | ✅ Concluído (Padrão 2) |
| **Estoque & Chassis** | `/stock` | Planilhas de contêineres COLVIX, Galpão MAJ e Bling ERP | Agendada / Webhook / Manual | ⏳ **Pendente** |
| **Importações** | `/imports` | Planilhas Despesas Brasil, Pagamentos China (PI/CI), Contratos de Câmbio | Upload / Sincronização / Manual | ⏳ **Pendente** |
| **Produtos & Catálogo** | `/products` / `/atacado` | Catálogo Bling, Pesos Cubados, Dimensões e Fichas Técnicas | Sincronização Contínua / Manual | ⏳ **Pendente** |
| **Vendas & Pedidos** | `/sales` | Pedidos Bling ERP, NF-e e Múltiplos Recebimentos | Webhook Bling / Sincronização | ⏳ **Pendente** |
| **Fiscal & Precificação** | `/fiscal/pricing` | Tabela de Alíquotas Interestaduais, MVA, DIFAL e ICMS | Sincronização Periódica / Manual | ⏳ **Pendente** |

---

## 3. Especificação do Componente Padrão de Automação

### 3.1. Template Front-end (`templates/<modulo>/automation_panel.html`)
- Utiliza variáveis semânticas do tema para compatibilidade nativa com tema escuro e claro:
  - `var(--panel)` para fundo principal.
  - `var(--panel2)` para cards internos.
  - `var(--text)` e `var(--muted)` para tipografia e contraste.
  - `var(--line)` para bordas e separadores.
  - `var(--accent)` para status ativo e destaques.

### 3.2. Back-end Service (`services/<modulo>_sync_service.py`)
- Padrão estrutural do serviço:
```python
def sync_<modulo>_data(source_path_or_url=None, force=False):
    """
    Executa sincronização segura (sem reset) do módulo.
    - Lê fonte de dados (CSV, API ou Sheets)
    - Normaliza dados
    - Realiza upsert no Supabase
    - Registra carimbo de data/hora e resumo em settings
    - Retorna dict com status, total_processado e tempo
    """
    pass
```

### 3.3. Rota de Controle e Webhook (`routes/<modulo>_routes.py`)
- Rota para disparo via interface web (protegida com CSRF e permissão de usuário).
- Rota para disparo via webhook ou cron (`/cron/<modulo>-sync`).
