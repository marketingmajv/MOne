# M-One — MVP operacional da MAJ

Primeira versão funcional do sistema definido nesta conversa.

## O que já está implementado

- Login e permissões por função.
- Dashboard com:
  - vendas do dia e do mês;
  - pagamentos realizados no mês;
  - estoque disponível;
  - produtos mais vendidos;
  - produtos de oportunidade;
  - sugestão de preço promocional = custo + 10%.
- Cadastro de produtos com custo, varejo, atacado e elegibilidade para promoção.
- Importações com acesso exclusivo da Diretoria:
  - Invoice;
  - BL;
  - NF de entrada;
  - planilha de chassis;
  - custos/pagamentos da importação;
  - câmbio;
  - botão de liberação do estoque.
- Importação de chassis por CSV/XLSX contendo ao menos MODELO e CHASSI; MOTOR e COR são opcionais.
- Estoque unitário por chassi.
- Regra inegociável: **nenhuma venda/nota é cadastrada sem chassi válido**.
- Bloqueio de chassi inexistente, duplicado, já vendido ou pertencente a importação ainda não liberada.
- Vendas de varejo ou atacado com Pedido Bling + NF + um ou vários chassis.
- Um ou vários recebimentos por venda (ex.: Sicoob + Fonton Pay, cartão, dinheiro, consignado).
- Registro simples de pagamentos já realizados — não é contas a pagar futuro.
- Custos de importação ocultos para quem não é Diretoria.
- Auditoria básica das principais ações.

## Usuários iniciais

Todos usam a senha temporária `MOne2026!` e devem alterá-la no primeiro uso operacional.

- jean — Diretoria
- geysa — Diretoria
- marisa — Financeiro
- jhon — Estoque
- luisa — Vendas
- leo — Vendas
- gabriel — Vendas
- fauzer — Suporte Técnico

## Rodar no computador

### Windows / macOS / Linux

1. Instale Python 3.11 ou superior.
2. Abra um terminal dentro desta pasta.
3. Crie um ambiente virtual:

```bash
python -m venv .venv
```

4. Ative o ambiente.
5. Instale as dependências:

```bash
pip install -r requirements.txt
```

6. Inicie:

```bash
python app.py
```

7. Abra no navegador:

```text
http://localhost:5000
```

## Formato da planilha de chassis

CSV ou XLSX. Cabeçalhos aceitos:

| MODELO | CHASSI | MOTOR | COR |
|---|---|---|---|
| V80 PRO | ABC123 | MTR001 | Preto |
| V80 PRO | ABC124 | MTR002 | Branco |

`MODELO` e `CHASSI` são obrigatórios. `MOTOR` e `COR` são opcionais.

## Próximas integrações planejadas

- API Bling: sincronizar pedido, NF e catálogo sem digitação dupla.
- WhatsApp Business API: radar de atendimento, perguntas sem resposta, tempo de atendimento e indicadores por vendedor.
- Upload de comprovante por câmera do celular com leitura automática.
- BI avançado de margem real e giro.
- Criativo automático para produto de oportunidade.
- PWA instalável no celular.

## Importante antes de colocar em produção

Este MVP é funcional, mas ainda é uma versão de validação. Antes de expor na internet, deve receber hospedagem adequada, HTTPS, backup, gestão segura de segredos/senhas, banco de dados de produção e política de acesso/privacidade.
