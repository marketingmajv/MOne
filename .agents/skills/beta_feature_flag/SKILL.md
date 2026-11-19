---
name: beta_feature_flag
description: Protocolo de Feature Flag Beta Restrito e ciclo de vida de testes controlados no M-One. Acionada obrigatoriamente na fase de escopo/planejamento de toda nova funcionalidade para perguntar se entra em Beta Restrito (exclusivo @jam/@fauzer e delegável por eles em /users) ou Liberação Geral, além de padronizar a promoção segura de Beta para Produção Geral.
---

# Protocolo `beta_feature_flag` — Lançamento em Beta Restrito & Go-Live (M-One)

Esta skill padroniza o lançamento seguro de novas funcionalidades diretamente em produção (`main`) sem impactar a operação da equipe, usando a arquitetura nativa de RBAC do M-One (`ALL_PERMISSIONS` + `custom_permissions` + `super_admin_only`).

---

## 1. Regra de Gatilho na Fase de Escopo (Obrigatório)

**Sempre que entrar na fase de escopo ou planejamento de uma nova funcionalidade/melhoria** (incluindo `/grill-me`, `/plan` ou pedidos como *"vamos criar X"*), **ANTES de iniciar a implementação**, o agente **DEVE** perguntar ao usuário:

> **Estratégia de Liberação:** Como esta nova funcionalidade deve entrar no ar?
> 1. **🧪 Beta Restrito (Recomendada para features novas/críticas):** Visível apenas para `@jam` e `@fauzer`, com possibilidade de delegar o teste a colaboradores específicos via `/users` (`🔐 Permissões`), mantendo os demais usuários 100% no fluxo atual.
> 2. **🚀 Liberação Geral Imediata:** Disponível para todos os usuários elegíveis do módulo logo após o deploy.

---

## 2. Padrão Técnico de Implementação — Modo Beta Restrito

Quando o usuário escolher **Beta Restrito**, aplicar estritamente os 4 pilares abaixo (referência oficial: `freight_retail_mode`):

### Pilar 1 — Chave Exclusiva no Catálogo (`services/user_permission_service.py`)
Registrar a permissão da nova feature em `ALL_PERMISSIONS`:
```python
    "<chave_da_feature>": {
        "category": "logistica",  # comercial | logistica | financeiro | governanca | integracoes
        "label": "<Nome Curto> (Beta)",
        "icon": "🧪",
        "description": "Libera <descrição curta> em modo de teste (delegação exclusiva Jam/Fauzer)",
        "default_roles": ["super_admin"],  # Nunca usar [] pois scripts/permissions_audit.py exige lista não-vazia; 'super_admin' não bate com nenhum cargo comum
        "super_admin_only": True,
    },
```
- **`SUPER_ADMINS = {"jam", "fauzer"}`**: ambos recebem `True` automaticamente via `user_has_permission_check`.
- **Demais usuários (inclusive outros `admin`)**: recebem `False` por padrão, a menos que `@jam` ou `@fauzer` ativem manualmente o switch no modal de `/users`.
- **Blindagem de delegação (já ativa em `templates/user_permissions_modal.html` e `routes/user_routes.py`)**: qualquer permissão com `"super_admin_only": True` só aparece e só pode ser alterada por `@jam` ou `@fauzer`.

### Pilar 2 — Trava no Back-end (Segurança Real, Não Apenas Visual)
Na rota ou serviço da feature, validar via `user_has_permission(me, "<chave_da_feature>")` (ou `user_has_permission_check`):
- Se `False`: ignorar parâmetros da nova feature, aplicar o fallback seguro legado ou retornar `403`/`redirect` conforme o caso.
- Nunca confiar apenas em botão escondido no HTML/JS.

### Pilar 3 — Interface Condicional + Atalho de Delegação (`templates/*.html`)
Passar `can_<feature> = user_has_permission(me, "<chave_da_feature>")` para o template:
- Renderizar os novos botões/blocos/abas dentro de `{% if can_<feature> %} ... {% endif %}`.
- Exibir ao lado do título do recurso:
  - Badge discreta: `🧪 Beta Restrito`
  - Para `@jam` e `@fauzer` (`(me.username or '')|lower in ['jam', 'fauzer']`), atalho direto:
    `<a href="{{ url_for('users') }}">👥 Delegar testador</a>`
- Garantir que o bloco `{% else %}` mantenha os inputs ocultos ou valores padrão do comportamento legado para que nenhum JS quebre para usuários comuns.

### Pilar 4 — Auditorias Obrigatórias
Executar antes do deploy:
1. `scripts/monolith_watcher.py --scan`
2. `scripts/permissions_audit.py`
3. `scripts/ux_audit.py`
4. `scripts/validate.py`

---

## 3. Protocolo de Go-Live — Promover de Beta para Produção Geral

Quando o usuário pedir para **"liberar para todos"**, **"sair do beta"** ou **"promover `<feature>` para geral"**:

1. **Atualizar `services/user_permission_service.py`:**
   - Alterar `"default_roles"` de `["super_admin"]` para os cargos finais aprovados (ex.: `["admin", "support", "sales"]`).
   - Remover `"super_admin_only": True` e retirar o sufixo `(Beta)` do `label`.
2. **Limpar a UI nos templates (`templates/*.html`):**
   - Remover a badge `🧪 Beta Restrito` e o link `👥 Delegar testador`.
   - Avaliar se o controle ainda deve respeitar `user_has_permission(me, "<chave>")` (recomendado para manter controle granular em `/users`) ou ficar aberto a todos com acesso ao módulo pai.
3. **Saneamento de `custom_permissions` no Banco (Crítico!):**
   - Em `user_has_permission_check`, se um usuário teve suas permissões salvas em `/users` durante o período de Beta **sem** o switch marcado, o JSON `custom_permissions` desse usuário contém `"<chave>": false` — e **custom_permissions sobrepõe `default_roles`**!
   - Verificar no PostgreSQL quais usuários têm `"<chave>": false` em `custom_permissions` e decidir com o usuário: remover a chave (para herdar `default_roles`) ou atualizar para `true` nos cargos elegíveis.
4. **Validar & Publicar:**
   - Rodar `scripts/permissions_audit.py` e `scripts/validate.py` e publicar via protocolo `deploy`.

---

## 4. Regra de Documentação para Implementação Futura (Registro no Painel de Suporte)

Sempre que o usuário solicitar **documentar um escopo para implementação futura** (ex.: *"Documente para implementarmos depois..."*), além de gerar a especificação técnica em `docs/ESPECIFICACAO_<TEMA>.md`, o agente **DEVE obrigatoriamente** registrar um chamado no **Painel de Suporte** (`/admin/suporte`) usando `create_ticket` (`services/support_service.py`):

1. **Parâmetros obrigatórios do chamado:**
   - **Solicitante:** usuário `@fauzer` (ou o super-admin solicitante)
   - **`initial_status`:** `"pendente"`
   - **`urgency`:** `"normal"`
   - **`notify_whatsapp`:** `False` *(não disparar WhatsApp automático para demandas planejadas)*
   - **`module_key` / `module_label`:** área/módulo correspondente à funcionalidade
   - **`items`:** checklist objetivo das fases de implementação
2. **Estrutura obrigatória da `description` (para copiar e implementar):**
   - **Resumo executivo:** objetivo da feature, caminho do arquivo `docs/ESPECIFICACAO_<TEMA>.md` e estratégia definida (`Beta Restrito` ou `Liberação Geral`).
   - **Bloco destacado pronto para copiar e colar:**
     ```text
     === PROMPT PARA IMPLEMENTAÇÃO (COPIAR E COLAR) ===
     Implemente o escopo documentado em docs/ESPECIFICACAO_<TEMA>.md seguindo integralmente:
     1. Modo de lançamento: <Beta Restrito (super_admin_only: True) | Liberação Geral> (skill beta_feature_flag).
     2. Arquitetura, arquivos-alvo, limiares e regras de negócio definidos na especificação.
     3. Anti-monólito (< 500 linhas por arquivo) e validações obrigatórias (ux_audit.py, permissions_audit.py e validate.py).
     === FIM DO PROMPT ===
     ```
3. **Confirmação na resposta:** informar ao usuário o código do chamado criado (`SUP-YYYY-XXXX`) junto com o link `file://` da especificação.
