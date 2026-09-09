---
name: proactive_refactoring
description: ACIONAR SEMPRE que editar, modificar ou adicionar código em arquivos muito grandes (> 500 linhas), como o monólito app.py ou templates extensos.
---

# Instruções de Refatoração Proativa e Anti-Monolito

Você deve atuar ativamente no monitoramento e combate à formação de monólitos de código, garantindo que a arquitetura do M-One se mantenha modular, limpa e de fácil manutenção.

## 1. Gatilho de Ação (PAUSA OBRIGATÓRIA)
- Se a sua tarefa principal exigir que você altere, leia ou adicione código a um arquivo com **mais de 500 linhas** (com destaque para o `app.py` que possui +3.000 linhas), você DEVE **PAUSAR** e avaliar a modularização.
- Alerte o usuário de que um Monólito foi detectado e que a extração para um módulo separado (ex: Blueprint em `routes/` ou componente em `templates/`) é recomendada antes de acumular mais código.
- Proponha um plano de resolução cirúrgico (ex: extração de rotas afins para `routes/sales_routes.py`, `routes/stock_routes.py`, etc.) e pergunte se o usuário deseja realizar a extração agora ou prosseguir com a alteração pontual.

## 2. Padrão de Refatoração Modular no M-One
Se o usuário autorizar a resolução ou extração de partes do monólito:
1. **Checkpoint de Segurança**: Verifique o estado do git e crie um commit de restauração se necessário (`git add . && git commit -m "chore: checkpoint pre-refatoracao"`).
2. **Extração Cirúrgica em Blueprints**:
   - Mover rotas e lógicas afins para arquivos dedicados dentro da pasta `routes/`.
   - Registrar os novos Blueprints no `app.py`.
   - Preservar nomes de endpoints, assinaturas e rotas para não quebrar links existentes nos templates (`url_for(...)`).
3. **Autovalidação Obrigatória**:
   - Executar `.venv/bin/python3 scripts/validate.py` para validar sintaxe Python, templates Jinja2 e resposta HTTP 200 das rotas.
4. **Continuidade**: Após o sucesso da validação, retomar a tarefa original com o código já modularizado e limpo.
