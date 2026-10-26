---
name: deploy
description: Protocolo DEPLOY de validação, encerramento e publicação do M-One em produção. Executa varredura de integridade (sintaxe, tipagem, templates e rotas), faz git commit e git push para o repositório oficial na Vercel e gera relatório de publicação. Ativado sempre que o usuário digitar [deploy] ou deploy.
---

# Protocolo DEPLOY — Encerramento e Publicação M-One

Este protocolo deve ser executado obrigatoriamente e imediatamente sempre que o usuário digitar `[deploy]`, `deploy`, ou solicitar o encerramento da sessão com publicação online.

## Etapas Obrigatórias de Execução:

### Passo 01 — Varredura de Integridade do Código (Pre-Deploy Checks)
Executar rotina de verificação profunda para identificar erros de dependência, tipagem, sintaxe e canais comerciais antes de publicar:
1. Executar `.venv/bin/python3 scripts/validate.py`, que audita:
   - **Paridade Estrita de Dependências**: AST Scan em 100% dos arquivos Python contra `requirements.txt` (impede erro de pacotes não declarados).
   - **Compilação e Sintaxe Python Completa**: Compilação recursiva da raiz, `routes/`, `services/`, `scripts/` e `api/`.
   - **Validação de Templates Jinja2**: Parsing em todos os templates e subpastas.
   - **Auditoria de UX/UI**: Modais centralizados, contraste dark-first e botão fechar (`scripts/ux_audit.py`).
   - **Teste Ativo de Canais Comerciais**: Valida `/outlet`, `/atacado`, `/modelos` e `/login` retornando HTTP 200.
   - **Verificação de Banco de Dados**: Valida DSN do Pooler IPv4 Supabase (`aws-0-us-west-2.pooler.supabase.com:6543`).
   - **Auditoria de Permissões & RBAC**: Garante que 100% dos Blueprints e links de menu possuam permissão no catálogo `ALL_PERMISSIONS` (`scripts/permissions_audit.py`).
2. **Critério de Parada**:
   - Se QUALQUER verificação falhar (incluindo rota nova sem permissão), o deploy é **IMEDIATAMENTE INTERROMPIDO**. O agente deve reportar o erro exato e sugerir a correção antes de prosseguir.

### Passo 02 — Sincronização e Git Push (Deploy Online)
1. Verificar status do repositório (`git status -sb`).
2. Se houver arquivos modificados ou untracked (respeitando `.gitignore`):
   - Executar `git add .`
   - Gerar commit claro e descritivo resumindo as melhorias/ajustes feitos na sessão (ex: `git commit -m "..."`).
3. Se houver commits locais não enviados (ou commits criados agora):
   - Executar `git push origin main`.
4. Se o repositório já estiver 100% atualizado e sem alterações locais:
   - Registrar que não houve necessidade de push adicional.

### Passo 03 — Relatório de Publicação e Smoke Test Online
Apresentar ao usuário um relatório de encerramento contendo:
1. **Resultado da Varredura Preditiva**:
   - Dependências, sintaxe, templates, canais comerciais e DB: Aprovados.
2. **Resumo do Envio Git**:
   - Hash do commit enviado para a nuvem e lista de arquivos.
3. **Smoke Test em Produção**:
   - Testar rotas ao vivo via `curl -sI https://m-one.majmobilidade.com.br/outlet` e `/login` para confirmar HTTP 200 online.
4. **Status de Produção e Links**:
   - 🚀 **Link Oficial em Produção**: `https://m-one.majmobilidade.com.br`
   - 🌐 **Status Vercel**: Compilação automática confirmada.
   - 💻 **Ambiente Local**: Status do servidor local.
