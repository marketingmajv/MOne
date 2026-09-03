---
name: start
description: Protocolo START de inicialização e implementação do M-One. Executa git fetch, sincronização git push/pull, inicialização do servidor local e relatório com links de teste. Ativado sempre que o usuário digitar [start] ou start.
---

# Protocolo START — Inicialização de Implementação M-One

Este protocolo deve ser executado obrigatoriamente e imediatamente sempre que o usuário digitar `[start]`, `start`, ou solicitar o início dos trabalhos no projeto M-One.

## Etapas Obrigatórias de Execução:

### Passo 01 — Sincronização e Diagnóstico Git (`git fetch`)
1. Executar `git fetch origin` no diretório do projeto.
2. Analisar o status comparativo entre o branch local e o remoto:
   - Executar `git status -sb`
   - Verificar commits locais não enviados: `git log origin/main..HEAD --oneline`
   - Verificar commits remotos não baixados: `git log HEAD..origin/main --oneline`
3. Determinar o diagnóstico:
   - **Precisa de git pull**: Se houver novos commits na nuvem.
   - **Precisa de git push**: Se houver commits locais pendentes de deploy.
   - **Sincronizado**: Se local e remoto estiverem no mesmo commit.
   - **Arquivos modificados**: Listar arquivos alterados ou pendentes de commit.

### Passo 02 — Inicialização do Servidor Local
1. Verificar se o servidor local na porta `5001` está ativo (`lsof -i :5001`).
2. Se não estiver rodando, iniciar o servidor Flask em background na porta 5001:
   ```bash
   PORT=5001 .venv/bin/python3 app.py
   ```
   *(Ou executar `./dev.sh`)*.
3. Validar se a rota `/login` responde com HTTP 200 via `curl -sI http://localhost:5001/login`.

### Passo 03 — Relatório de Sincronização e Links de Teste
Apresentar ao usuário um relatório estruturado contendo:
1. **Status de Sincronização Git**:
   - Resumo do `git fetch` (Commits locais x Remotos).
   - Ação sugerida ou realizada (`git push` ou `git pull`).
   - Arquivos modificados recentemente.
2. **Status dos Serviços**:
   - Servidor local (porta 5001) ➔ Ativo.
   - Banco de Dados (Supabase PostgreSQL) ➔ Conectado.
3. **Links Diretos para Teste**:
   - 💻 **Ambiente Local**: `http://localhost:5001`
   - 🚀 **Produção Oficial**: `https://m-one.majmobilidade.com.br`
4. **Credenciais Rápidas**:
   - `fauzer` / `MOne2026!` (Suporte Técnico)
   - `jean` / `MOne2026!` (Diretoria)
