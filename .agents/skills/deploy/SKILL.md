---
name: deploy
description: Protocolo DEPLOY de validação, encerramento e publicação do M-One em produção. Executa varredura de integridade (sintaxe, tipagem, templates e rotas), faz git commit e git push para o repositório oficial na Vercel e gera relatório de publicação. Ativado sempre que o usuário digitar [deploy] ou deploy.
---

# Protocolo DEPLOY — Encerramento e Publicação M-One

Este protocolo deve ser executado obrigatoriamente e imediatamente sempre que o usuário digitar `[deploy]`, `deploy`, ou solicitar o encerramento da sessão com publicação online.

## Etapas Obrigatórias de Execução:

### Passo 01 — Varredura de Integridade do Código (Pre-Deploy Checks)
Executar rotina de verificação profunda para identificar erros de tipagem, sintaxe e configurações antes de publicar:
1. **Compilação e Sintaxe Python**:
   - `python3 -m py_compile app.py api/index.py`
2. **Validação de Templates Jinja2/HTML**:
   - Parsear todos os arquivos em `templates/*.html` com `jinja2.Environment` para garantir que não há tags não fechadas, blocos quebrados ou variáveis inexistentes.
3. **Instanciação e Rotas do Flask**:
   - Importar o app e executar teste do endpoint `/login` via `app.test_client()`.
4. **Verificação de Banco de Dados**:
   - Validar que o pooler IPv4 do Supabase (`aws-0-us-west-2.pooler.supabase.com:6543`) está configurado como fallback ou DSN principal, prevenindo falha de conexão na Vercel.
5. **Critério de Parada**:
   - Se QUALQUER verificação falhar, o deploy é **IMEDIATAMENTE INTERROMPIDO**. O agente deve reportar o erro exato e sugerir a correção antes de prosseguir.

### Passo 02 — Sincronização e Git Push (Deploy Online)
1. Verificar status do repositório (`git status -sb`).
2. Se houver arquivos modificados ou untracked (respeitando `.gitignore`):
   - Executar `git add .`
   - Gerar commit claro e descritivo resumindo as melhorias/ajustes feitos na sessão (ex: `git commit -m "..."`).
3. Se houver commits locais não enviados (ou commits criados agora):
   - Executar `git push origin main`.
4. Se o repositório já estiver 100% atualizado e sem alterações locais:
   - Registrar que não houve necessidade de push adicional.

### Passo 03 — Relatório de Publicação e Links
Apresentar ao usuário um relatório de encerramento contendo:
1. **Resultado da Varredura**:
   - Código Python: Aprovado.
   - Templates HTML/Jinja: Aprovados.
   - Rotas e inicialização Flask: Aprovadas.
2. **Resumo do Envio Git**:
   - Hash do commit enviado para a nuvem.
   - Lista resumida dos arquivos publicados.
3. **Status de Produção e Links**:
   - 🚀 **Link Oficial em Produção**: `https://m-one.majmobilidade.com.br`
   - 🌐 **Status Vercel**: Compilação automática disparada via GitHub.
   - 💻 **Ambiente Local**: Informar se o servidor local continua ativo ou se a sessão pode ser encerrada.
