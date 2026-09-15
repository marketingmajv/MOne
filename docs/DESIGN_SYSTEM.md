# M-One Design System Specification (2026)
**Referência Canônica: Visão Geral (`http://localhost:5001/` — Dashboard / Overview)**

O Design System do **M-One (MAJ Operating System)** foi concebido para o ecossistema executivo e operacional de mobilidade elétrica. Ele combina princípios de **FinTech de Alta Precisão**, **Ergonomia Industrial (Bento UI)** e uma arquitetura inovadora **Dual-Theme com Contraste Invertido no Cockpit**.

---

## 1. Fundamentos & Princípios de Design

| Pilar | Diretriz | Implementação no M-One |
| :--- | :--- | :--- |
| **Cockpit Executivo** | Decisões em 5 segundos | O topo da página destaca o Faturamento Mês, Meta e Radar em tempo real. |
| **Precisão Numérica** | Alinhamento contábil e de chassi | Numerais tabulares obrigatórios (`tnum 1`) para evitar deslocamento de layout. |
| **Arquitetura Dual-Theme** | Adaptação solar e noturna | Alternância instantânea via atributo `data-theme` e evento `mone-theme-changed`. |
| **Microinterações Tácteis** | Sensação física de sistema vivo | Linhas de carga neon (`.charge-line`), pulso em tempo real (`.radar-dot`) e elevação em hover (`translateY(-3px)`). |
| **Zero Dependências Pesadas** | Performance pura | Vanilla CSS modular, tipografia em Plus Jakarta Sans, Alpine.js reativo e Chart.js sem Tailwind. |

---

## 2. Paleta de Cores & Tokens Semânticos

### 2.1 Cores de Marca (Brand Core)
```css
--accent: #00E599;          /* MAJ Electric Green — Sucesso, carga e ação primária */
--accent-hover: #00C885;
--accent-cyan: #00F0FF;     /* Tech Cyan — Gradiente de carregamento e inovação */
--brand-blue: #38BDF8;      /* Sky Blue — Métricas de volume e conexões */
--danger: #EF4444;          /* Red Alert — Erros, cancelamentos e exclusão */
--warning: #F59E0B;         /* Amber Warning — Atenção de estoque e desembaraço */
```

### 2.2 Dual-Theme Tokens

```css
/* ==========================================================================
   TEMA ESCURO (Dark Obsidian Glass) — Padrão do Sistema
   ========================================================================== */
:root, [data-theme="dark"] {
  --bg: #090D16;                  /* Canvas principal Obsidian Profundo */
  --side: #070B13;                /* Rail lateral fixo */
  --panel: #0F172A;               /* Superfície primária dos cards */
  --panel2: #162238;              /* Superfície secundária e inputs */
  --panel-hover: #1E2D4A;
  --surface-card: #0F172A;
  --surface-subtle: #162238;
  
  --text: #F8FAFC;                /* Branco de alto contraste */
  --text-primary: #F8FAFC;
  --text-dim: #E2E8F0;
  --muted: #94A3B8;               /* Rótulos e legendas secundárias */
  --muted-dark: #64748B;
  
  --line: rgba(255, 255, 255, 0.08); /* Linha hairline de vidro */
  --line-light: rgba(255, 255, 255, 0.15);
  --border-subtle: rgba(255, 255, 255, 0.08);
  
  --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.7);
}

/* ==========================================================================
   TEMA CLARO (Porcelain Alabaster & Emerald FinTech)
   ========================================================================== */
[data-theme="light"] {
  --bg: #F4F6F8;                  /* Canvas Porcelana Suave */
  --side: #0C1322;                /* Sidebar escura preservada (Brand Contrast) */
  --panel: #FFFFFF;               /* Superfície pura dos cards */
  --panel2: #F8FAFC;              /* Superfície elevada / inputs suaves */
  --panel-hover: #F1F5F9;
  --surface-card: #FFFFFF;
  --surface-subtle: #F8FAFC;
  
  --text: #0F172A;                /* Azul marinho profundo de alta legibilidade */
  --text-primary: #0F172A;
  --text-dim: #334155;
  --muted: #64748B;               /* Cinza ardósia para labels */
  --muted-dark: #94A3B8;
  
  --line: #E2E8F0;                /* Borda limpa e sutil */
  --line-light: #CBD5E1;
  --border-subtle: #E2E8F0;
  
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 20px -2px rgba(15, 23, 42, 0.07);
  --shadow-lg: 0 16px 36px -4px rgba(15, 23, 42, 0.12);
}
```

---

## 3. Tipografia & Escala Visual

* **Família Primária:** `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif`
* **Família Mono/Técnica:** `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`
* **Regra Global de Tabular Figures (Obrigatória em Finanças e Chassis):**
```css
.metric strong, .bento-hero strong, .bento-metric strong, 
.mono, .tabular-nums, .price-tag, .rank-row strong {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
}
```

### Escala de Tamanhos
| Nível | Tamanho | Peso | Uso Típico na Visão Geral |
| :--- | :--- | :--- | :--- |
| **Display Hero** | `2.0rem` (32px) | 800 (ExtraBold) | Valor consolidado do Faturamento Mês no Cockpit |
| **KPI Big** | `1.65rem` (26px) | 800 (ExtraBold) | Números principais dos 4 Bento Metrics |
| **Título H2** | `1.35rem` (21px) | 800 (ExtraBold) | Saudação executiva ("Bom dia, Gestor") |
| **Título H3** | `1.05rem` (16px) | 700 (Bold) | Cabeçalhos de painéis (Gráfico, Mais Vendidos, Estoque) |
| **Subtítulos / Body** | `0.88rem` (14px) | 400 - 500 | Descrições e parágrafos contextuais |
| **Data Row Value** | `0.82rem` - `0.90rem` | 600 - 700 | Itens de ranking, feeds e linhas de dados |
| **Labels & Micro-KPI** | `0.72rem` - `0.75rem` | 700 (Bold) | `text-transform: uppercase`, rastreadores e metas |

---

## 4. Anatomia dos Componentes da Visão Geral

### 4.1 Shell de Aplicação (`app-shell`)
- **Sidebar Fixa (Rail 250px)**:  
  Fundo ultra-escuro constante `#080D1A` em **ambos os temas**, preservando a identidade visual da montadora. O item ativo recebe fundo verde neon sutil (`rgba(0, 229, 153, 0.12)`), borda com `box-shadow: inset 3px 0 0 #00E599` e texto branco luminoso.
- **Topbar & Header**:  
  Exibe o título da página, subtítulo e o botão comutador de tema:
  ```html
  <button type="button" class="theme-toggle-btn" id="themeToggleBtn" onclick="toggleMOneTheme()">
    <span id="themeToggleIcon">☀️</span>
    <span id="themeToggleText">Tema</span>
  </button>
  ```

---

### 4.2 Top Cockpit Grid (`cockpit-top-grid`)
Estrutura de 2 colunas assimétricas (`1.7fr 1fr`) com alinhamento vertical uniforme:

```
+----------------------------------------------------+----------------------------+
| COCKPIT HERO (1.7fr)                                | RADAR AO VIVO (1.0fr)      |
| • Saudação + Badge de Chassis Prontos               | • Dot pulsante             |
| • KPI Faturamento Mês (Display 2rem)                | • Feed de eventos em tempo |
| • Barra de Meta com gradiente elétrico              |   real com scroll interno  |
+----------------------------------------------------+----------------------------+
```

#### Regra Exclusiva: Contraste Invertido do Cockpit Hero (`.bento-hero`)
Para chamar atenção imediata para o KPI mais importante do negócio, o card Hero inverte a polaridade do fundo:
- **No Tema Claro:** É um box **Stealth Escuro** (`linear-gradient(135deg, #10192C 0%, #080D1A 100%)`) sobre o fundo porcelana, com texto branco e reflexo radial esmeralda.
- **No Tema Escuro:** É um box **Porcelana Alabaster** (`linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)`) sobre o fundo obsidian, com texto grafite escuro e brilho envolvente.

---

### 4.3 Bento Grid de 4 Métricas (`bento-grid-4`)
Grid responsivo de 4 colunas (`repeat(4, 1fr)` no desktop, 2 colunas no tablet, 1 coluna no mobile).

* **Estrutura de cada card (`.bento-metric`):**
  - Rótulo superior em caixa alta e fonte sutil (`0.75rem`, Bold).
  - Número consolidado tabular (`1.65rem`, ExtraBold).
  - Subtítulo de status com seta contextual (`↗ Consolidado no período`).
  - **Linha de Carga (`.charge-line`):** Fita horizontal neon na base inferior com gradiente de `--accent` (#00E599) para `--accent-cyan` (#00F0FF) e glow `box-shadow: 0 0 10px rgba(0, 229, 153, 0.4)`.
  - Microinteração: `transform: translateY(-3px)` no hover.

---

### 4.4 Radar de Operações ao Vivo (`.radar-panel`)
- **Indicador de Status Pulsante (`.radar-dot`):**  
  Círculo de 8x8px verde esmeralda com sombra de neon `box-shadow: 0 0 8px var(--accent)`.
- **Feed Itens (`.radar-item`):**  
  Cards compactos com borda fina e hover suave que desloca 2px para a direita (`transform: translateX(2px)`).

---

### 4.5 Painel de Analytics & Gráficos (`.panel`)
- Integração de **Chart.js** responsivo dentro de um container com altura fixa de `260px`.
- **Pill Selector de Períodos:** Seletor de pílulas (`7 Dias`, `30 Dias`, `Mês`, `Ano`) encapsulado em fundo `--panel2` com cantos arredondados de 99px.
- **Adaptação Dinâmica do Gráfico:** O script reage ao evento `mone-theme-changed` ajustando em tempo real a cor das linhas de grade (`gridColor`) e dos rótulos (`tickColor`).

---

### 4.6 Ranking de Mais Vendidos (`.rank-list`)
- Cada linha (`.rank-row`) possui um badge numérico (`.rank`) com fundo `--primary`, nome do veículo, quantidade faturada e valor financeiro alinhado à direita em `--accent` e numerais tabulares.

---

### 4.7 Inteligência de Estoque & Giro Comercial (`.opportunity`)
- Grade responsiva automática (`repeat(auto-fill, minmax(280px, 1fr))`).
- Destaca veículos com mais de 60 dias em estoque e sugere precificação dinâmica para desova e rotação de pátio.

---

### 4.8 Matriz de Ações Rápidas (`.quick-grid`)
- 4 atalhos operacionais diretos: *Registrar Venda*, *Consultar Chassi*, *Cotar Frete* e *Importações*.
- Ícones em badges translúcidos com borda e títulos em negrito.

---

## 5. Geometria de Bordas e Elevação

```css
--radius-xs: 6px;    /* Badges de tabela, pílulas minúsculas */
--radius-sm: 8px;    /* Inputs, selects, botões pequenos */
--radius: 14px;      /* Bento metrics, cards de gráfico, panels */
--radius-lg: 18px;   /* Cockpit hero, modais executivos */
--radius-xl: 24px;   /* Containers externos */
```

---

## 6. Heurísticas de Usabilidade e Regras de Implementação

1. **Nunca quebrar o Contraste do Dual-Theme:**  
   Não utilizar cores absolutas como `color: #FFFFFF` ou `background: #000000` em textos e superfícies genéricas. Sempre utilizar tokens semânticos (`var(--text-primary)`, `var(--surface-card)`, `var(--border-subtle)`).
2. **Formatação Monetária Consistente:**  
   Todos os valores em Reais devem passar pelo filtro Jinja `|money` (ex: `{{ sales_month|money }}`) ou pela função Javascript `formatMoney()`, garantindo o formato brasileiro `R$ 1.234.567,89`.
3. **Limite Estrito Anti-Monólito:**  
   Manter qualquer partial de tela abaixo de 500 linhas. O `dashboard.html` possui exatamente 348 linhas, servindo de modelo exemplar de arquitetura limpa.
