---
name: permissions_guard
description: Auditor autônomo de cobertura de permissões e controle de acesso RBAC no M-One. Garante que qualquer função, módulo ou Blueprint novo criado na aplicação seja registrado em ALL_PERMISSIONS e no menu de permissões por usuário antes do deploy. Acionado automaticamente nos protocolos [start] e [deploy].
---

# Auditoria Autônoma de Permissões & RBAC — M-One (MAJ OS)

Esta skill define as diretrizes inegociáveis de controle de acesso granular (Role-Based Access Control - RBAC) no M-One.

## Objetivo Central
Garantir que **nenhuma função nova, tela, Blueprint ou canal operacional** entre no M-One sem que os administradores da MAJ Mobilidade possam visualizar, auditar, liberar ou bloquear o acesso individual de cada usuário no **Menu de Permissões** (`templates/user_permissions_modal.html`).

---

## 🛠️ Comando de Auditoria Rápida

Para verificar a conformidade de todas as rotas e funções do M-One a qualquer momento:
```bash
.venv/bin/python3 scripts/permissions_audit.py
```

O auditor verifica:
1. **Todos os Blueprints registrados no Flask** (`app.blueprints`).
2. **Todas as rotas e links no menu lateral** (`templates/components/sidebar.html`).
3. **Paridade com o catálogo oficial** `ALL_PERMISSIONS` em `services/user_permission_service.py`.
4. **Integridade das categorias** (`PERMISSIONS_CATEGORIES`: comercial, logistica, financeiro, governanca, integracoes).

---

## 📋 Checklist Obrigatório ao Criar uma Nova Função no M-One

Sempre que você criar uma rota operacional, tela ou novo Blueprint no M-One, **SIGA ESTES 4 PASSOS**:

### 1. Cadastrar a Permissão em `services/user_permission_service.py`
Adicione a chave no dicionário `ALL_PERMISSIONS`:
```python
    "nome_do_modulo": {
        "category": "comercial",  # comercial | logistica | financeiro | governanca | integracoes
        "label": "Nome Legível do Módulo",
        "icon": "⚡",              # Emoji representativo
        "description": "Explicação executiva clara de 1 linha do que a tela faz",
        "default_roles": ["admin", "support", "sales"],  # Cargos que têm acesso nativo
    },
```

### 2. Mapear o Blueprint em `scripts/permissions_audit.py`
No dicionário `BLUEPRINT_TO_PERMISSION_MAP`:
```python
    "nome_do_blueprint": "nome_do_modulo",
```
*(Se for uma rota legitimamente pública, como canal externo ou webhook de terceiros, adicione em `EXEMPT_BLUEPRINTS`)*.

### 3. Proteger a Rota no Backend
No arquivo da rota (`routes/*_routes.py`):
```python
from routes.helpers import user_has_permission

@modulo_bp.route("")
@login_required
def index():
    me = current_user()
    if not user_has_permission(me, "nome_do_modulo"):
        flash("Você não tem permissão para acessar este módulo.", "error")
        return redirect(url_for("dashboard"))
```

### 4. Proteger o Link na Barra Lateral (`templates/components/sidebar.html`)
```html
{% set can_novo_modulo = me and user_has_permission(me, 'nome_do_modulo') %}

{% if can_novo_modulo %}
<a href="{{ url_for('modulo.index') }}" class="nav-item">
  ...
  <span>Nome do Módulo</span>
</a>
{% endif %}
```

---

## 🔒 Regras de Negócio e Bypass
- **Super Admins (@jam e @fauzer)**: Possuem bypass nativo e irrestrito.
- **Sobreposição Individual (`custom_permissions`)**: Se o Administrador marcar ou desmarcar o switch no modal, essa preferência sobrepõe o cargo natural do usuário.
- **Trava de Deploy**: O comando `[deploy]` executa `scripts/validate.py`, que interrompe o push caso haja qualquer rota ou link sem permissão cadastrada.
