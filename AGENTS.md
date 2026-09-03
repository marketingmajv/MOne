# Diretrizes Oficiais de Desenvolvimento — M-One (MAJ Operating System)

Este documento estabelece as regras de desenvolvimento, arquitetura, segurança e protocolos para o projeto M-One.

## 1. Regras de Ambiente e Infraestrutura
- **Porta Local de Desenvolvimento**: Sempre porta `5001`. A porta 5000 do macOS é reservada pelo sistema (`ControlCenter`/`AirPlay`).
- **Banco de Dados**: Supabase PostgreSQL conectado via Pooler IPv4 oficial (`aws-0-us-west-2.pooler.supabase.com:6543`).
- **Ambiente de Produção**: Vercel com domínio próprio oficial em `https://m-one.majmobilidade.com.br`.

## 2. Regras Negociais Inegociáveis
- **Chassi Obrigatório**: Nenhuma venda ou nota fiscal é cadastrada sem chassi válido, conferido e liberado (`status = 'available'`).
- **Sigilo**: Custos aduaneiros, taxas de importação e margens sigilosas são visíveis exclusivamente para as funções `admin` (Diretoria) e `support` (Suporte Técnico).

## 3. Protocolos Especiais Ativos
- `[start]`: Executa `git fetch`, compara a sincronização do código, inicia o servidor local na porta 5001 (`./dev.sh`) e apresenta o relatório de sincronização com o link de testes local.
- `[deploy]`: Executa a varredura profunda de integridade (`python scripts/validate.py`), realiza commit e push para o GitHub e atualiza a produção na Vercel.
