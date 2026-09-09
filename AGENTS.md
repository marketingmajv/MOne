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
   - Checar se o servidor local Flask na porta `5001` está ativo.
   - Se não estiver ativo, iniciá-lo imediatamente (`PORT=5001 .venv/bin/python3 app.py` ou `./dev.sh`).
   - Validar com `curl` que o serviço está respondendo HTTP 200.

3. **Passo 03 — Varredura e Auditoria Anti-Monólito**:
   - Executar o auditor de monólitos: `.venv/bin/python3 scripts/monolith_watcher.py --scan`.
   - Identificar arquivos que ultrapassam a marca de 500 linhas (ex: `app.py`).
   - Alertar o usuário e disponibilizar a lista de arquivos para aplicação do padrão de refatoração modular.

4. **Passo 04 — Relatório Consolidado e Links de Teste**:
   - Gerar um relatório claro com:
     - Situação da sincronização do código (commits à frente/atrás, alterações pendentes).
     - Status dos serviços locais e conexão com o Supabase.
     - Diagnóstico de monólitos (arquivos críticos detectados).
     - Link para teste local: `http://localhost:5001`
     - Link oficial de produção: `https://m-one.majmobilidade.com.br`

---

## Protocolo Especial: [deploy]
Sempre que o usuário digitar `[deploy]` ou `deploy`:
O agente DEVE executar imediatamente o **Protocolo DEPLOY** em 3 etapas sequenciais:

1. **Passo 01 — Varredura e Validação de Integridade do Código**:
   - Executar varredura profunda com o script `.venv/bin/python3 scripts/validate.py`.
   - Validar sintaxe Python (`app.py`, `api/index.py`), templates Jinja2 e rotas Flask.
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

---

## Auditoria Anti-Monolito Contínua
Você deve combater ativamente o inchaço e a formação de monólitos de código no M-One:
- **Limite de Linhas**: Arquivos de rotas, scripts e templates não devem ultrapassar a marca de **500 linhas**.
- **Pausa Proativa**: Ao realizar alterações ou adicionar novas funcionalidades em arquivos que ultrapassem 500 linhas (especialmente o `app.py`), a IA deve pausar e propor a extração cirúrgica de rotas em Blueprints modulares (`routes/`).
- **Watcher em Segundo Plano**: O projeto conta com o agente de monitoração `scripts/monolith_watcher.py` (ou `scripts/monolith-watcher.js`), que alerta no terminal e via notificações nativas do sistema operacional sempre que um arquivo exceder o limite.

