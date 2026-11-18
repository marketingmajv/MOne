# Relatório de Pendências Técnicas e Operacionais — Estoque / Chassi (Para Jhonzin)

**Projeto:** `SYNC-STOCK` (Aba Resumida de Estoque para Vendedores no M-One)  
**Data da Auditoria na Planilha & Sistema:** 18/11/2026  
**Planilha Auditada:** COLVIX / Galpão MAJ (`16csh8zLt8OjRER-3TnDrpq34sQX5J17sue4Cuq8txSY`)  
**Objetivo:** Liberar no M-One uma aba resumida para os vendedores (**Disponível em Caixa**, **Disponível Montada** e **Separados**: *Esperando coleta*, *Esperando pagamento* e *Montagem loja/showroom*), atualizada pelas baixas da Marisa e pela conferência das sextas-feiras.

---

## 1. Resumo Executivo

A construção da aba para os vendedores no M-One é **100% viável** com a estrutura que já temos hoje (inclusive o fluxo da Marisa e o módulo de bipagem das sextas já estão no sistema).

Porém, **antes de colocar essa aba no ar para os vendedores confiarem nos números**, existem **pendências reais na planilha** e **4 ajustes técnicos no M-One** que precisam ser alinhados e resolvidos.

---

## 2. Pendências na Planilha (Ação Operacional — Jhonzin / Equipe)

Sem corrigir estes pontos na planilha, o M-One não consegue enxergar todas as motos reais do estoque nem permitir que a Marisa dê baixa nelas:

### 🔴 Pendência 1 — 172 unidades SEM chassi cadastrado na planilha
O M-One só importa e permite baixa/conferência de veículos com **chassi único válido**. Hoje, na planilha oficial:

1. **Aba `GALPAO CAIXA` (242 linhas de produtos):**
   - Apenas **93** têm chassi preenchido.
   - **149 unidades estão SEM chassi** (apenas Modelo e Cor preenchidos) e ficam invisíveis no M-One:
     - `M9 PRO` (`banco marrom`): **59 unidades** sem chassi
     - `V20 ULTRA` (`banco marrom`): **42 unidades** sem chassi
     - `V20 ULTRA` (`banco preto`): **24 unidades** sem chassi
     - `M9 PRO` (`banco preto`): **19 unidades** sem chassi
     - `M9 PRO S/ BATERIA` (`banco preto`): **3 unidades** sem chassi
     - `Mantis` (`preta`): **1 unidade** sem chassi
     - `Mantis` (`bege`): **1 unidade** sem chassi
   - Além disso, existem **9 linhas com chassi incompleto/duplicado** (só o prefixo de 8 letras):
     - Linhas **9 e 10**: `LKKTWKEA` (`nova` cinza com preto) — **2 unidades** com o mesmo prefixo incompleto.
     - Linhas **237 a 243**: `LKKTWHEA` (`Ride on` laranja/sem cor) — **7 unidades** com o mesmo prefixo incompleto (e linhas 238–243 também estão sem Cor preenchida).

2. **Aba `SHOW ROOM` (23 linhas de produtos):**
   - **Todas as 23 unidades estão SEM chassi preenchido** (`0` importadas no M-One).
   - Inclui modelos como `Max 12`, `Max 12 NV`, `GP 1000 NV`, `Ride On`, `RZ110`, `JM 125`, `Flow One`, `M2 NV`, `Vittória`, `Nova`, `M9 Pro`, `V20 Ultra`, `M50`, `Q8`, `Mantis`, etc.

> **O que precisa ser feito:** Preencher ou bipar o **chassi completo** dessas 149 unidades da `GALPAO CAIXA`, corrigir os 9 prefixos incompletos (`LKKTWKEA` / `LKKTWHEA`) e preencher os 23 chassis da aba `SHOW ROOM`.

---

### 🟡 Pendência 2 — Padronização de Nomes de Modelos, Cores e Observações
Para que a aba dos vendedores agrupe corretamente (ex.: *X15 Vermelha banco marrom -> 10*), os dados precisam seguir um padrão limpo:

- **Observações dentro da coluna Cor:**
  - Na aba `GALPÃO MONTADAS`:
    - Linha **18** (`R2WSE3000TA160935`, `X15 PRO`): Cor preenchida como `"verde militar faltando peça"`.
    - Linha **19** (`R2WSE3000TA160917`, `X15 PRO`): Cor preenchida como `"carbono faltando peça"`.
  - **Ação:** Definir se unidades *faltando peça* devem ficar **bloqueadas/separadas para manutenção** (não exibidas como disponíveis para venda imediata) e deixar apenas a cor na coluna `Cor`.
- **Diferenças de escrita no mesmo modelo/cor:**
  - Modelos variados: `Max 12` vs `Max 12 NV` vs `MAX12`; `Flow on` vs `Flow One`.
  - Cores variadas: `PRETO` vs `preta`, `RED + BROWN SEAT` (inglês na COLVIX) vs `vermelha banco marrom`.
  - Aba `Chassi container Triciclos Garo`: **100 unidades** vieram com nome em chinês (`星宝 出口（三轮）`) e cores em inglês (`Buddha's Hand Gold/Warm Coffee`, etc.).
  - *(Obs.: No M-One faremos um tradutor/normalizador automático, mas manter a coluna Cor sem observações misturadas ajuda muito).*

---

### 🟡 Pendência 3 — Conferência de Sexta-Feira e Status "Em Conferência"
- Hoje existem **290 unidades** no M-One com status `Em conferência` (`unreleased` — contêineres `DWSE26070035`, `DWSE26070036` e `CHASSIS TROCADOS`).
- Na conferência registrada em 17/11/2026 (`id=5`), 480 unidades eram esperadas e apenas 8 foram bipadas (teste).
- **Ação:** Realizar a conferência oficial completa na sexta-feira bipando todo o estoque físico para zerar pendências e carimbar oficialmente o selo de **"Conferido por Jhonzin"** para os vendedores.

---

## 3. Pendências Técnicas no M-One (Ação Desenvolvimento — Fauzer)

Enquanto a planilha é saneada, os seguintes ajustes serão feitos no código do M-One no **Projeto `SYNC-STOCK`**:

1. **Criar a aba `📊 Resumo p/ Vendedores` em `/stock`** (padrão para vendedores, com **Caixa**, **Montada**, **Separados**, filtro por galpão e selos de data/hora da última conferência + última baixa da Marisa).
2. **Criar os 3 sub-motivos obrigatórios de Separação** no fluxo da Marisa e do Estoque (`Esperando pagamento`, `Esperando coleta`, `Separado p/ montagem loja/showroom`).
3. **Criar normalizador automático de Modelo/Cor** (traduzindo `星宝 出口（三轮）` para `Triciclo Garo`, unificando `PRETO/preta`, cores em inglês e separando alertas como `faltando peça`).
4. **Atualizar a sincronização da planilha (`sync_colvix_sheets_to_stock`) e `/sales`:**
   - Se a planilha ganhar `NF de venda` / `Cliente` para um chassi já existente, baixar automaticamente para `sold` no M-One (sem desfazer baixas já feitas no sistema).
   - Liberar em `/sales` a venda manual de chassis que já estejam marcados como `Montado` (`assembled`) ou `Separado` (`separated`).

---

## 4. Mensagem Pronta para Enviar ao Jhonzin (WhatsApp)

```text
Fala Jhonzin! Analisei sua ideia da aba resumida pros vendedores (Projeto *SYNC-STOCK* no M-One) junto com a planilha atual.

✅ *Viabilidade:* Dá pra fazer 100% no M-One, ligando direto com as baixas da Marisa no dia a dia e com a sua conferência de sexta-feira (inclusive com selo de data/hora mostrando pros vendedores quando foi a última atualização/conferência).

⚠️ *Porém, fiz um raio-X na planilha hoje e achei algumas pendências que travam a contagem exata se não arrumarmos antes:*

1️⃣ *172 unidades estão SEM chassi na planilha* (o sistema precisa do chassi pra importar e pra Marisa conseguir dar baixa):
• *GALPAO CAIXA:* 149 motos sem chassi (59 M9 PRO banco marrom, 42 V20 ULTRA banco marrom, 24 V20 ULTRA banco preto, 19 M9 PRO banco preto, 3 M9 PRO s/ bateria, 2 Mantis).
• *Chassis incompletos/duplicados na GALPAO CAIXA:* 2x `LKKTWKEA` (Nova) e 7x `LKKTWHEA` (Ride On — 6 delas também sem cor).
• *SHOW ROOM:* Todas as 23 unidades estão sem chassi.

2️⃣ *Observações na coluna Cor (GALPÃO MONTADAS):*
• Linhas 18 e 19 (X15 PRO `...935` e `...917`) estão escritas como _"verde militar faltando peça"_ e _"carbono faltando peça"_. Precisamos definir se moto faltando peça não entra como disponível pra venda.

3️⃣ *Status "Separados" (Coleta / Pagamento / Montagem Loja):*
• No M-One vamos criar exatamente esses 3 motivos na separação pra Marisa e pra você marcarem, além de traduzir/padronizar automático os nomes (ex: os 100 Triciclos Garo que estão em chinês e cores em inglês).

*Resumo pro nosso próximo passo:*
Assim que vocês preencherem os chassis faltantes na `GALPAO CAIXA` e no `SHOW ROOM` (e alinharem as duas X15 faltando peça), a gente já sobe a aba *SYNC-STOCK* pros vendedores testarem na prática!
```
