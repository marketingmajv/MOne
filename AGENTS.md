# Regras e Diretrizes do Projeto M-One (MAJ Operating System)

## Protocolo Especial: [start]
Sempre que o usuário digitar `[start]` ou `start`:
O agente DEVE executar imediatamente o **Protocolo START** em 3 etapas sequenciais:

1. **Passo 01 — Git Fetch e Análise de Sincronização**:
   - Rodar `git fetch origin`.
   - Comparar `HEAD` local com `origin/main` (`git status -sb`, `git log origin/main..HEAD`, `git log HEAD..origin/main`).
   - Identificar se há necessidade de `git pull` (novos commits na nuvem), `git push` (commits locais pendentes) ou se está 100% sincronizado.
   - Listar arquivos modificados ou unstaged se houver.

2. **Passo 02 — Inicialização do Ambiente**:
   - Checar se o servidor local Flask na porta `5001` e o túnel Cloudflare estão ativos.
   - Se não estiverem ativos, iniciá-los imediatamente (`PORT=5001 .venv/bin/python3 app.py` e `cloudflared tunnel --url http://localhost:5001` ou `./dev.sh`).
   - Validar com `curl` que o serviço está respondendo HTTP 200.

3. **Passo 03 — Relatório e Links de Teste**:
   - Gerar um relatório claro com:
     - Situação da sincronização do código (commits à frente/atrás, alterações pendentes).
     - Status dos serviços locais e conexão com o Supabase.
     - Link para teste local: `http://localhost:5001`
     - Link para teste online imediato (Túnel Cloudflare).
     - Link oficial de produção: `https://m-one.majmobilidade.com.br`

---

## Protocolo Especial: [deploy]
Sempre que o usuário digitar `[deploy]` ou `deploy`:
O agente DEVE executar imediatamente o **Protocolo DEPLOY** em 3 etapas sequenciais:

1. **Passo 01 — Varredura e Validação de Integridade do Código**:
   - Executar compilação estática (`.venv/bin/python3 -m py_compile app.py api/index.py`).
   - Validar sintaxe de todos os templates Jinja2 em `templates/*.html`.
   - Testar instanciação da aplicação Flask e rota `/login` (`app.test_client()`).
   - Checar integridade da conexão Supabase IPv4 Pooler.
   - **Trava de Segurança**: Se houver qualquer erro de sintaxe, importação ou tipagem que prejudique o deploy, **interromper imediatamente**, relatar o erro e NÃO fazer o push.

2. **Passo 02 — Git Commit e Push Automático**:
   - Verificar arquivos alterados ou pendentes (`git status -sb`).
   - Fazer `git add .` dos arquivos alterados na sessão (respeitando `.gitignore`).
   - Criar commit objetivo descrevendo as alterações da sessão.
   - Executar `git push origin main` para acionar o deploy automático na Vercel.

3. **Passo 03 — Relatório de Publicação e Confirmação Online**:
   - Resumo da varredura (status das validações).
   - Detalhes do commit enviado e lista de arquivos atualizados.
   - Link de produção oficial atualizado: `https://m-one.majmobilidade.com.br`

---

## Regras de Negócio e Desenvolvimento
- **Porta Local**: Usar sempre a porta `5001` (a porta 5000 do macOS é ocupada pelo AirPlay / ControlCenter).
- **Banco de Dados**: Usar sempre o pooler IPv4 oficial do Supabase:
  `aws-0-us-west-2.pooler.supabase.com:6543` com `sslmode=require`.
- **Regra de Vendas**: Toda venda exige chassi existente, liberado (`available`) e não duplicado.
- **Sigilo**: Custos de contêineres e importações são restritos à Diretoria (`admin`) e Suporte Técnico (`support`).
