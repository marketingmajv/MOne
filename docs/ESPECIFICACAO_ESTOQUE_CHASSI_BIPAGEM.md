# Especificação Técnica & Operacional — Controle de Estoque, Conferência por Bipagem e Baixa por Chassi (M-One)

**Status:** Aprovado para Implementação  
**Data:** 17/11/2026  
**Módulos Impactados:** `/stock` (Estoque & Conferência), `/sales` (Vendas), `/finance` (Financeiro/Baixa)  
**Fonte de Dados Externa:** Google Sheets COLVIX (`16csh8zLt8OjRER-3TnDrpq34sQX5J17sue4Cuq8txSY`) + futuras abas/importações  

---

## 1. Visão Geral & Objetivo Operacional

Substituir o controle manual fragmentado em planilhas por um fluxo auditável, rápido e integrado dentro do **M-One**, eliminando furos de estoque entre faturamento, separação física e conferência de galpão.

O sistema opera em **duas frentes conectadas à mesma fonte única da verdade (`stock_units` + `sales`)**:

1. **Frente Estoque / Conferente (Jhonzin — `/stock`)**:
   - Conferência física contínua via leitor de código de barras (*bip*).
   - Seleção de Galpão/Local alvo antes de iniciar (`Galpão MAJ`, `COLVIX`, `Depósito Consolação` ou `Todos`).
   - Bipagem contínua sem necessidade de cliques (lê o código ➔ registra ➔ limpa o campo e mantém o foco).
   - Finalização com geração automática de **Relatório Executivo em PDF** (`reportlab`) destacando:
     - Chassis não bipados no galpão auditado (para checagem dos 3 motivos: *sem lançamento financeiro*, *produto montado*, *pulado*).
     - Alertas críticos de chassis bipados que constavam como **Separado para Venda**, **Vendido**, **De Outro Galpão**, ou **Não Cadastrados**.
   - Ação rápida de 1 clique para marcar veículo como **Montado (Exposição/Loja)**.

2. **Frente Financeiro / Faturamento (Marisa — `/sales` e `/finance`)**:
   - Acesso direto via aba/modal **"Baixa & Separação por Chassi"** dentro de **Vendas** e **Financeiro** (sem precisar acessar o módulo de Estoque).
   - Busca suspensa inteligente: ao bipar/selecionar o chassi, **o campo de busca se recolhe**, exibe automaticamente **Chassi, Modelo e Cor**, e libera as ações:
     - **Faturar / Baixar Venda**: `NF-e de Transferência 1` (opcional), `NF-e de Transferência 2` (opcional), `NF-e de Venda`, `Cliente`, `Valor Total da Venda`. Cria/vincula registro em `sales` e altera `stock_units.status = 'sold'`.
     - **Marcar como Separada para Venda**: Informa o `Nº do Pedido` e trava o chassi com status `separated`, gerando alerta automático caso o conferente bipe esse chassi no galpão.

---

## 2. Fonte da Verdade e Sincronização 24/7 (Regra Anti-Reset)

* **M-One como Fonte Principal**: Todas as conferências (`stock_audits`), separações, montagens e baixas de vendas são persistidas no PostgreSQL do M-One.
* **Sincronização de Entrada (Google Sheets ➔ M-One)**:
  * O serviço `services/stock_sync_service.py` lê a planilha COLVIX (`16csh8zLt8OjRER-3TnDrpq34sQX5J17sue4Cuq8txSY`) e futuras fontes cadastradas para **importar novos chassis** (modelo, cor, motor, importação, localização inicial).
  * **Regra Inegociável Anti-Reset**: A sincronização nunca sobrescreve status operacionais (`separated`, `assembled`, `sold`), conferências ou dados lançados manualmente no M-One.

---

## 3. Modelagem de Banco de Dados (PostgreSQL / SQLite)

### 3.1. Evolução de `stock_units`
Status suportados:
* `available` — Disponível (Na Caixa)
* `assembled` — Montado (Exposição / Loja)
* `separated` — Separado para Venda (com `separated_order_number`)
* `sold` — Vendido (vinculado a `sale_id`)
* `unreleased` — Em conferência / Não liberado

Colunas adicionais em `stock_units`:
* `separated_order_number TEXT`
* `separated_at TIMESTAMP`
* `separated_by BIGINT`
* `last_audited_at TIMESTAMP`
* `last_audited_by BIGINT`

### 3.2. Evolução de `sales`
Colunas adicionais em `sales`:
* `transfer_nf_1 TEXT`
* `transfer_nf_2 TEXT`

### 3.3. Novas Tabelas de Auditoria
1. **`stock_audits`** (Sessões de Conferência):
   * `id`, `location_scope` (galpão auditado), `status` (`in_progress`, `finished`), `started_by`, `started_at`, `finished_at`, `expected_count`, `scanned_count`, `missing_count`, `alerts_count`, `notes`.
2. **`stock_audit_items`** (Itens Bipados na Sessão):
   * `id`, `audit_id`, `chassis`, `stock_unit_id`, `scan_result` (`ok`, `alert_separated`, `alert_sold`, `alert_other_location`, `unknown`), `unit_status_at_scan`, `unit_location_at_scan`, `order_number_snapshot`, `scanned_at`, `scanned_by`.

---

## 4. Arquitetura Modular (Anti-Monólito < 500 linhas)

Para respeitar o limite máximo de 500 linhas por arquivo, a implementação é dividida em módulos especializados:

| Camada | Arquivo | Responsabilidade |
| :--- | :--- | :--- |
| **Service (Schema & Sync)** | `services/stock_sync_service.py` | Migração idempotente de schema + sincronização anti-reset da planilha COLVIX. |
| **Service (Conferência)** | `services/stock_audit_service.py` | Iniciar/finalizar conferência, processar bipagem contínua, classificar alertas e listar histórico. |
| **Service (PDF)** | `services/stock_audit_pdf_service.py` | Geração do Relatório Executivo em PDF (`reportlab`) com não-bipados e alertas críticos. |
| **Service (Baixa/Separação)** | `services/stock_chassis_action_service.py` | Baixa de venda por chassi (integrada a `sales`), separação para venda e marcação como `assembled` (Montado). |
| **Blueprint (Conferência/Sync)** | `routes/stock_audit_routes.py` | Endpoints `/stock/audit/*`, `/stock/sync-sheets`, `/stock/chassis/assemble`, download de PDF. |
| **Blueprint (Baixa Financeiro)** | `routes/stock_chassis_sales_routes.py` | Endpoints `/api/chassis/search`, `/sales/chassis-checkout` para Marisa (`/sales` e `/finance`). |
| **UI (Conferência Estoque)** | `templates/components/stock_audit_modal.html` + `static/js/stock-audit.js` | Modal/painel de conferência contínua (`<template x-teleport="body">`, `.modal-close-btn` SVG). |
| **UI (Baixa Marisa)** | `templates/components/chassis_sales_modal.html` + `static/js/chassis-sales.js` | Busca suspensa que recolhe ao bipar e exibe formulário de baixa/separação em `/sales` e `/finance`. |

---

## 5. Segurança RBAC (`ALL_PERMISSIONS`)

* **`stock`** (Estoque & Chassis): Acesso à tela `/stock`, conferência física por bipagem, histórico e marcação de Montado.
* **`chassis_sales`** (Baixa & Separação por Chassi — Financeiro/Vendas): Nova permissão específica em `ALL_PERMISSIONS` (`default_roles: ["admin", "support", "finance", "sales"]`), permitindo que a Marisa execute baixas de venda e separações diretamente de `/sales` e `/finance` sem precisar acessar `/stock`.

---

## 6. Plano de Execução por Fases

* **Fase 1 (Base & Dados):** Criar schema idempotente (`stock_audits`, `stock_audit_items`, colunas extras em `stock_units` e `sales`), registrar permissão `chassis_sales` em `ALL_PERMISSIONS`, criar `stock_sync_service.py` para importar/atualizar a planilha COLVIX.
* **Fase 2 (Motor de Conferência & PDF):** Implementar `stock_audit_service.py`, `stock_audit_pdf_service.py` e rotas em `routes/stock_audit_routes.py`.
* **Fase 3 (Baixa/Separação Marisa):** Implementar `stock_chassis_action_service.py` e `routes/stock_chassis_sales_routes.py`.
* **Fase 4 (Interfaces Dark Theme):** Construir os componentes Alpine.js (`stock_audit_modal.html`, `chassis_sales_modal.html`) integrados em `/stock`, `/sales` e `/finance`, seguindo `ux_audit.py`.
* **Fase 5 (Validação):** Rodar `monolith_watcher.py`, `permissions_audit.py`, `ux_audit.py` e `validate.py`, além de testar o fluxo completo localmente.
