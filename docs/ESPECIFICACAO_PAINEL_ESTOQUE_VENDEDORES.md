# Especificação Técnica & Funcional — Projeto **SYNC-STOCK**
*(Painel de Estoque em Tempo Real para Vendedores & Fluxo Contínuo Marisa / Jhonzin — V2)*

**Codinome Oficial:** `SYNC-STOCK`  
**Status:** Documentado / Backlog Prioritário (Aguardando saneamento inicial de chassis na planilha)  
**Data da Especificação:** 18/11/2026  
**Evolução de:** [ESPECIFICACAO_ESTOQUE_CHASSI_BIPAGEM.md](file:///c:/Users/Start/m-one/docs/ESPECIFICACAO_ESTOQUE_CHASSI_BIPAGEM.md)  
**Módulos Impactados:** `/stock` (Nova aba `📊 Resumo p/ Vendedores`), `/sales`, `/finance`, `services/stock_*`  
**Fonte de Dados Externa:** Google Sheets COLVIX (`16csh8zLt8OjRER-3TnDrpq34sQX5J17sue4Cuq8txSY`)

---

## 1. Objetivo de Negócio

Eliminar perguntas repetitivas diárias dos vendedores no WhatsApp (*"Quantas X15 vermelhas tem em caixa?"*, *"Tem montada?"*, *"Essas unidades estão livres ou já separadas?"*) entregando dentro do **M-One** uma **visão executiva resumida por Modelo + Cor + Quantidade**, alimentada em tempo real por dois motores que já existem no sistema:
1. **Dia a dia (Marisa — Financeiro/Vendas):** Cada baixa (`sold`) ou separação (`separated`) por chassi atualiza o painel no mesmo segundo.
2. **Conferência Semanal (Jhonzin — Toda sexta-feira):** Conferência física por bipagem (`stock_audits`) reconcilia todo o pátio e carimba o selo de **Última Conferência Geral** para gerar confiança absoluta ao time comercial.

---

## 2. Decisões Arquiteturais Alinhadas

1. **Tratamento de Unidades sem Chassi (Regra de Entrada):**
   - **Decisão:** Cadastrar os chassis reais na planilha/M-One antes de liberar o painel como fonte oficial (preservando a regra inegociável de negócio: *toda venda e separação exige chassi válido*). Um modo híbrido temporário por quantidade só deve ser adotado se houver bloqueio operacional prolongado.
2. **Escopo de Exibição para Vendedores (`Galpão MAJ + COLVIX`):**
   - Exibir **estoque unificado para venda** (`Galpão MAJ` + `COLVIX` + `Showroom`), com **filtro rápido por galpão**.
   - **Ocultar** unidades com status `unreleased` (*Em conferência*), evitando que o comercial venda mercadoria ainda não liberada/conferida.
3. **Sub-motivos Obrigatórios na Separação (`separated`):**
   - Evoluir o status `separated` para exigir um **sub-motivo estruturado**, disponível tanto para a **Marisa** (`/sales` e `/finance`) quanto para o **Jhonzin** (`/stock`):
     - `awaiting_payment` ➔ 💳 **Esperando pagamento**
     - `awaiting_pickup` ➔ 🚚 **Esperando coleta**
     - `showroom_assembly` ➔ 🛠️ **Separado p/ montagem loja/showroom**
4. **Normalizador Inteligente de Modelo e Cor:**
   - Criar camada de normalização na exibição (e saneamento opcional na planilha) para evitar fragmentação no agrupamento `Modelo → Cor → Qtd`:
     - Unificar variações de caixa/grafia (`PRETO` / `preta` ➔ `Preto`; `Max 12` / `MAX12` ➔ `Max 12`; `Flow on` / `FLOW ON` ➔ `Flow On`).
     - Traduzir nomes importados em chinês/inglês (ex.: `星宝 出口（三轮）` ➔ `Triciclo Garo`; `RED + BROWN SEAT` ➔ `Vermelha Banco Marrom`).
     - Extrair observações técnicas do campo Cor (ex.: `carbono faltando peça` ➔ Cor `Carbono` + badge de alerta `⚠️ Faltando peça` ou remoção do disponível para venda até reparo).
5. **Experiência & Navegação (`/stock`):**
   - Criar **nova aba `📊 Resumo p/ Vendedores`** dentro de `/stock` ([templates/stock.html](file:///c:/Users/Start/m-one/templates/stock.html)):
     - **Visão padrão** ao acessar `/stock` para usuários com perfil `sales` (vendedores), com botão/aba visível para alternar para a tabela detalhada por chassi quando precisarem.
     - Para `admin`, `stock` e `support`, mantém acesso imediato às duas abas (`📊 Resumo p/ Vendedores` e `📋 Chassis Detalhado`).
   - **Selos de Atualização em Tempo Real no topo da aba:**
     - `✅ Última Conferência Geral (Jhonzin)`: data/hora + nome do conferente da última auditoria finalizada (`stock_audits`).
     - `🔄 Última Movimentação (Marisa / Estoque)`: data/hora da última baixa, separação, montagem ou sync registrado.
6. **Fonte Única & Sincronização Inteligente (Planilha ↔ M-One):**
   - **M-One como fonte única** para baixas e separações operacionais da Marisa.
   - Aprimorar `sync_colvix_sheets_to_stock()` em [services/stock_sync_service.py](file:///c:/Users/Start/m-one/services/stock_sync_service.py): além de inserir novos chassis, se um chassi já existente no banco ainda não estiver `sold` e a planilha trouxer `NF de venda` ou `Cliente` preenchidos, marcar automaticamente como `sold` (respeitando a **Regra Anti-Reset**: nunca reverter um chassi já baixado/separado/montado no M-One).

---

## 3. Especificação Técnica de Implementação (Anti-Monólito < 500 linhas)

### 3.1. Alterações de Banco de Dados (`services/stock_sync_service.py` — `ensure_stock_audit_schema`)
Adicionar de forma idempotente em `stock_units`:
- `separation_reason TEXT` (`awaiting_payment`, `awaiting_pickup`, `showroom_assembly`)
- `separation_notes TEXT`
- `updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`

### 3.2. Novos Serviços / Evoluções de Back-end
1. **`services/sync_stock_service.py` (Novo — < 300 linhas):**
   - `normalize_model_name(raw_name)` e `normalize_color_name(raw_color)` (dicionário de sinônimos e traduções + extração de flags como `faltando peça` / `sem bateria`).
   - `get_seller_stock_summary(location_filter="all")`:
     - Retorna 3 blocos agregados (`in_box`, `assembled`, `separated_by_reason`) agrupados por `Modelo -> [{color, qty, flags}]` e totalizadores por modelo.
     - Retorna metadados de confiabilidade (`last_audit`: data/usuário da última conferência finalizada; `last_movement`: data/ação da última baixa/separação/montagem/sync).
2. **`services/stock_chassis_action_service.py` (Atualização):**
   - Atualizar `separate_chassis_for_sale(chassis_raw, order_number, user_id, reason="awaiting_pickup", notes="")` para persistir `separation_reason`, `separation_notes` e `updated_at`.
   - Atualizar `mark_chassis_assembled` e `checkout_chassis_sale` para atualizar `updated_at = CURRENT_TIMESTAMP`.
   - Expor ação para liberar/retornar um chassi separado de volta para `available` ou `assembled` caso um pedido seja cancelado (`unseparate_chassis`).
3. **`services/stock_sync_service.py` (Atualização):**
   - No loop de `sync_colvix_sheets_to_stock()`, quando `chassis in existing_chassis` e o registro no banco estiver `available` / `assembled` / `unreleased` enquanto a linha da planilha tiver `customer` ou `nf_venda`, atualizar para `status = 'sold'` e atualizar `updated_at`.
4. **`routes/sales_routes.py` (Correção de paridade):**
   - Em `add_sale()` (linha ~95), permitir faturamento de chassis com status `available`, `assembled` ou `separated` (atualmente trava se for diferente de `available`, impedindo venda manual de motos montadas ou previamente separadas).
5. **`routes/stock_routes.py` & `routes/stock_chassis_sales_routes.py` (Atualização):**
   - Em `routes/stock_routes.py`: passar `view_tab` (`summary` padrão para `role == 'sales'`, ou via query `?tab=summary|details`) e carregar `sync_stock_summary`.
   - Permitir ação rápida de **Separar Chassi** também na tela `/stock` (para o Jhonzin marcar *Montagem loja/showroom* ou *Esperando coleta* sem depender da tela de Vendas).

### 3.3. Interface Front-end (Dark Theme & `ux_audit.py`)
1. **`templates/components/stock_seller_summary.html` (Novo):**
   - Barra de status no topo com os **2 selos de atualização** (Última Conferência Geral + Última Movimentação) e filtro por galpão (`Todos`, `Galpão MAJ`, `COLVIX`, `Showroom`).
   - 3 seções claras com busca instantânea em Alpine.js (digitou `X15` ou `marrom`, filtra na hora):
     - 📦 **Disponível em Caixa** (cards por modelo com lista `Cor → Qtd` e total do modelo)
     - 🛠️ **Disponível Montada** (cards por modelo com lista `Cor → Qtd`)
     - ⏳ **Separados / Reservados** (sub-abas/colunas: *Esperando Pagamento*, *Esperando Coleta*, *Montagem Loja/Showroom*, exibindo `Modelo • Cor • Qtd` e opção de ver pedidos).
2. **`templates/components/chassis_sales_modal.html` + `static/js/chassis-sales.js` (Atualização):**
   - No modo **Separar**, incluir seletor obrigatório dos 3 sub-motivos (`Esperando pagamento`, `Esperando coleta`, `Separado p/ montagem loja/showroom`). Quando `showroom_assembly`, o Nº do Pedido torna-se opcional.
   - Modal deve manter `<template x-teleport="body">` e `.modal-close-btn` com SVG.

---

## 4. Checklist de Validação Antes do Deploy (Quando for Implementado)
- [ ] `C:\Python314\python.exe scripts/monolith_watcher.py --scan` (nenhum arquivo > 500 linhas; atenção especial a `routes/stock_routes.py`, `templates/stock.html`, `services/stock_sync_service.py`).
- [ ] `C:\Python314\python.exe scripts/permissions_audit.py` (garantir cobertura RBAC caso novos endpoints sejam criados).
- [ ] `C:\Python314\python.exe scripts/ux_audit.py` (garantir modais centralizados e contraste Dark Theme).
- [ ] `C:\Python314\python.exe scripts/validate.py` (validação completa pré-deploy).
