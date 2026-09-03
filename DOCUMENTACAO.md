# Documentação Oficial — M-One (MAJ Operating System)

## Visão Geral
O **M-One** é a plataforma de gestão operacional da **MAJ Mobilidade Elétrica**, integrando controle de estoque por chassi, importação de contêineres, gestão de vendas (varejo e atacado), fluxo financeiro e conciliação de recebimentos.

## Arquitetura do Sistema
- **Backend**: Python / Flask (`app.py`).
- **Banco de Dados**: Supabase PostgreSQL conectado via Pooler IPv4 oficial (`aws-0-us-west-2.pooler.supabase.com:6543`).
- **Frontend**: HTML5, Vanilla CSS com componentes responsivos e JavaScript.
- **Hospedagem de Produção**: Vercel Serverless Server (`https://m-one.majmobilidade.com.br`).

## Regras de Segurança e Permissões
- `admin` (Diretoria): Acesso total a relatórios, margens, custos de importação e gerenciamento de usuários.
- `support` (Suporte Técnico): Acesso técnico e de auditoria com visibilidade restrita a dados sigilosos operacionais.
- `finance` (Financeiro): Registro e conferência de pagamentos e liquidações.
- `stock` (Estoque): Cadastro de unidades, leitura de chassis e liberação física.
- `sales` (Vendas): Emissão de pedidos com vinculação mandatória de chassi liberado.

## Execução Local
Para rodar o projeto localmente:
```bash
./dev.sh
```
Servidor disponível em: `http://localhost:5001`
