# Documentação Técnica e Operacional — M-One (MAJ Operating System)

> **Versão**: 1.0.0 (Produção)  
> **Domínio Oficial**: [https://m-one.majmobilidade.com.br](https://m-one.majmobilidade.com.br)  
> **Repositório GitHub**: `https://github.com/marketingmajv/MOne.git`  
> **Data de Atualização**: Março / 2026

---

## 1. Visão Geral e Propósito

O **M-One** é o sistema operacional e ERP leve desenvolvido sob medida para a **MAJ Mobilidade Elétrica**. 

### Princípios Fundamentais:
1. **Operação Simples, Informação Uma Vez Só**: Interface fluida, direta e sem burocracias de ERPs legados.
2. **Fonte Única da Verdade no Chassi**: Cada veículo (moto, scooter, patinete) é uma unidade viva e única no banco de dados.
3. **Regra Inegociável de Venda**: Nenhuma venda ou nota fiscal é cadastrada sem chassi válido, conferido e liberado.
4. **Sigilo Financeiro**: Custos de importação, desembaraço, frete internacional e câmbio são restritos à Diretoria.
5. **Registro de Pagamentos Realizados**: O módulo financeiro registra apenas o que já foi efetivamente pago com comprovante anexado.

---

## 2. Arquitetura e Infraestrutura

```mermaid
graph TD
    Client["Navegador Web (Desktop / Mobile)"] -->|HTTPS| DNS["DNS Registro.br"]
    DNS -->|m-one.majmobilidade.com.br| Vercel["Vercel Serverless Platform"]
    Vercel -->|api/index.py| FlaskApp["Flask Web Application (Python 3)"]
    FlaskApp -->|PgBouncer IPv4 :6543| Supabase["Supabase PostgreSQL Database (us-west-2)"]
    
    DevClient["Desenvolvimento Local (Mac Studio)"] -->|dev.sh| LocalFlask["Flask Local (:5001)"]
    LocalFlask -->|PgBouncer IPv4 :6543| Supabase
```

| Componente | Tecnologia / Serviço | Detalhes |
| :--- | :--- | :--- |
| **Linguagem / Framework** | Python 3.9+ / Flask 3.1 | Microframework rápido com arquitetura modular |
| **Banco de Dados** | PostgreSQL no **Supabase** | Conectado via Pooler PgBouncer IPv4 (`aws-0-us-west-2.pooler.supabase.com:6543`) com SSL |
| **Frontend** | HTML5 Semântico + CSS3 Moderno | Dark Mode com padrão visual elegante, responsivo e sem dependências pesadas |
| **Hospedagem Produção** | **Vercel** Serverless | Entrypoint em [`api/index.py`](file:///Users/macstudio-maj/Documents/Desenvolvimento/Aplicativos/MOne/api/index.py) |
| **Domínio Oficial** | `m-one.majmobilidade.com.br` | Apontamento CNAME no Registro.br com SSL emitido automaticamente |
| **Ambiente Local** | Flask na porta 5001 | Script [`dev.sh`](file:///Users/macstudio-maj/Documents/Desenvolvimento/Aplicativos/MOne/dev.sh) com auto-reloading |

---

## 3. Perfis de Acesso e Permissões (RBAC)

O sistema possui controle rigoroso de papéis (`roles`):

| Perfil (`role`) | Descrição | Acessos e Responsabilidades | Usuários Exemplo |
| :--- | :--- | :--- | :--- |
| **Diretoria** (`admin`) | Gestão Executiva | **Acesso irrestrito**: Importações, custos sigilosos, liberação de lotes de chassis para venda, relatórios e gestão de usuários. | `jean`, `geysa` |
| **Suporte Técnico** (`support`) | Suporte & Diagnóstico | Acesso operacional completo, gestão de colaboradores, reset de senhas, auditoria e conferência de chassis. | `fauzer` |
| **Financeiro** (`finance`) | Gestão Financeira | Acesso a vendas, registro de pagamentos realizados com comprovante, catálogo de produtos, preços e exportação de relatórios. | `marisa` |
| **Estoque** (`stock`) | Controle Físico | Cadastro unitário de veículos, consulta e histórico de chassis, upload de planilhas de contêineres e produtos. | `jhon` |
| **Vendas** (`sales`) | Comercial | Dashboard, registro de vendas atreladas a chassis liberados, pedidos Bling, notas fiscais e múltiplos recebimentos. | `luisa`, `leo`, `gabriel` |

---

## 4. Regras de Negócio e Módulos do Sistema

### 4.1. Módulo de Estoque e Chassis (`/stock`)
- **Status do Chassi**:
  - `unreleased` (*Em conferência*): Unidade recém-importada aguardando liberação documental da Diretoria. **Bloqueada para venda**.
  - `available` (*Disponível*): Unidade liberada e apta para venda.
  - `sold` (*Vendido*): Unidade vinculada a uma venda registrada.
- **Formato da Planilha de Importação de Chassis** (CSV ou Excel `.xlsx`):
  | MODELO | CHASSI | MOTOR | COR |
  | :--- | :--- | :--- | :--- |
  | V80 PRO | 9C2xxxxxxx | MTR-001 | Preto |
  *(Cabeçalhos flexíveis: aceita maiúsculas/minúsculas. Modelo e Chassi são obrigatórios).*

### 4.2. Módulo de Importações e Contêineres (`/imports`)
- Acesso restrito à **Diretoria** e **Suporte Técnico**.
- Exige dados de controle: Número do Contêiner/Referência, Invoice, Bill of Lading (BL) e NF de Entrada.
- **Liberação de Estoque**: Só é permitida após carregamento da planilha de chassis e conferência da Invoice e do BL.
- **Custos Aduaneiros**: Permite cadastrar despesas atreladas ao contêiner em BRL (R$) ou USD ($) com taxa de câmbio informada e comprovante anexo.

### 4.3. Módulo de Vendas (`/sales`)
- Cada venda exige: Pedido Bling, Nota Fiscal, Canal (Varejo / Atacado), Cliente e **um ou mais chassis válidos**.
- **Travas Automáticas**:
  - Chassi inexistente na base ➔ **Bloqueado**.
  - Chassi em status `unreleased` (não liberado) ➔ **Bloqueado**.
  - Chassi já com status `sold` (já vendido) ➔ **Bloqueado**.
- **Múltiplos Recebimentos**: Uma venda pode ter mais de uma forma de pagamento (ex.: Entrada no Cartão + Saldo via Boleto Sicoob + Fonton Pay).

### 4.4. Módulo de Pagamentos Realizados (`/payments`)
- **Regra**: Somente pagamentos já quitados são registrados. Não funciona como contas a pagar futuro.
- Suporta captura ao vivo pela câmera do celular/computador ou upload de comprovante (PDF/Imagem).

### 4.5. Produtos e Oportunidades (`/products` e `/dashboard`)
- Cadastro de produtos com Preço de Custo, Atacado e Varejo.
- **Radar de Oportunidades**: O dashboard alerta automaticamente unidades com mais de 90 dias em estoque e sugere preço promocional (`Custo + 10%`).

---

## 5. Guia Operacional (Passo a Passo)

### Como Liberar um Novo Contêiner de Motos para Venda:
1. Acesse com usuário de **Diretoria** ou **Suporte Técnico**.
2. Vá em **Importações** ➔ clique em **+ Nova importação**.
3. Preencha a Referência (ex.: `CONT-2026-03`), Invoice, BL e NF de Entrada.
4. No card da importação criada, clique em **Importar planilha de chassis** e selecione o arquivo Excel ou CSV.
5. Verifique a quantidade de chassis carregados.
6. Clique no botão verde **Liberar estoque para venda**. Imediatamente as unidades mudam para `Disponível` e os vendedores podem registrar vendas.

### Como Cadastrar um Novo Colaborador:
1. Acesse **Usuários** no menu lateral.
2. Clique em **+ Criar Usuário**.
3. Preencha Nome completo, nome de usuário (minúsculo, sem espaços) e selecione o Perfil desejado.
4. A senha inicial padrão é `MOne2026!`.
5. O colaborador poderá alterar a própria senha a qualquer momento clicando em **Alterar senha** no rodapé do menu lateral.

---

## 6. Guia do Desenvolvedor e Manutenção

### 6.1. Variáveis de Ambiente Necessárias (`.env` e Vercel)
```env
DATABASE_URL=postgresql://postgres.ztbmnzwrpigcohwobrig:%40Jammajjam24@aws-0-us-west-2.pooler.supabase.com:6543/postgres?sslmode=require
SECRET_KEY=maj-m-one-production-fixed-secret-key-2026-v1
```
> ⚠️ **Nota Crítica sobre Supabase & Vercel**:  
> A URL direta `db.<ref>.supabase.co` opera apenas em IPv6, incompatível com o AWS Lambda da Vercel. **Sempre utilize o host do pooler IPv4**:  
> `aws-0-us-west-2.pooler.supabase.com` com a porta `6543` e usuário `postgres.<ref>`.

### 6.2. Como Rodar Localmente com Túnel Online de Testes:
No terminal do Mac Studio:
```bash
./dev.sh
```
O script iniciará:
- Servidor Flask na porta `5001` com recarregamento automático a cada alteração de código (`http://localhost:5001`).

### 6.3. Protocolos Automatizados do Assistente:

#### 🟢 Protocolo `[start]` (Inicialização da Sessão de Trabalho)
Ao digitar `[start]` ou `start`:
1. Executa `git fetch origin` e compara status de sincronização (commits pendentes de push/pull).
2. Inicializa o servidor local na porta `5001` se não estiver ativo.
3. Exibe relatório da sincronização e entrega links de teste (ambiente local e produção).

#### 🚀 Protocolo `[deploy]` (Validação e Publicação em Produção)
Ao digitar `[deploy]` ou `deploy`:
1. **Varredura de Integridade**: Executa verificação de sintaxe Python, compilação de templates Jinja2, inicialização de rotas Flask e validação do pooler Supabase IPv4 via [`scripts/validate.py`](file:///Users/macstudio-maj/Documents/Desenvolvimento/Aplicativos/MOne/scripts/validate.py).
2. **Trava de Segurança**: Se qualquer erro de tipagem/sintaxe for detectado, o deploy é abortado imediatamente.
3. **Deploy Automático**: Se aprovado, faz `git add .`, `git commit` com resumo das alterações da sessão e `git push origin main` para acionar a publicação imediata na Vercel em **`https://m-one.majmobilidade.com.br`**.
4. **Relatório**: Entrega o resumo do que foi publicado e confirmação do ambiente.

---

## 7. Suporte e Contatos Internos

- **Suporte Técnico**: Fauzer (`fauzer`)
- **Diretoria**: Jean (`jean`) / Geysa (`geysa`)
- **Administrador de Infraestrutura / Git**: `marketingmajv`
