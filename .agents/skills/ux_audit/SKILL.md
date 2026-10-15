---
name: ux_audit
description: Auditoria contínua e pré-entrega de UX/UI, centralização de modais e harmonia da paleta de cores no M-One. Previne modais desalinhados, containment traps com Alpine.js e inputs brancos em tema escuro. Acione sempre após implementar novas telas, modais ou componentes visuais.
---

# Auditoria Contínua de UX/UI — M-One

Esta skill define as diretrizes inegociáveis de ergonomia visual, centralização de modais e consistência cromática no ecossistema M-One.

## Checklist Obrigatório de Interface Antes de Qualquer Entrega

Sempre que criar ou modificar páginas, formulários ou modais, o agente **DEVE VERIFICAR**:

### 1. Centralização e Isolamento de Modais
- **CSS Containment Trap**: Modais criados dentro de `.app-shell` ou containers roláveis sofrem deslocamento para o canto esquerdo da tela devido ao contexto de posicionamento do elemento pai.
- **Regra**: Todo modal que use Alpine.js dentro de templates do sistema **DEVE** utilizar `<template x-teleport="body">`:
  ```html
  <template x-teleport="body">
    <div x-show="showModal" x-cloak class="modal show" style="position: fixed; inset: 0; z-index: 9999; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px); padding: 16px;" @click.self="showModal = false">
      <div class="modal-card" style="width: min(680px, 94vw); max-height: 90vh; overflow-y: auto; background: var(--panel, #121722); border: 1px solid var(--line, rgba(255,255,255,0.14)); border-radius: 16px; padding: 26px; box-shadow: 0 24px 50px rgba(0,0,0,0.8);">
        <div class="modal-head">
          <h3 style="color: var(--text, #f8fafc);">Título</h3>
          <button type="button" @click="showModal = false" class="modal-close-btn" title="Fechar modal" aria-label="Fechar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        ...
      </div>
    </div>
  </template>
  ```

### 2. Esquema de Cores & Contraste (Dark Theme First)
- **Inputs**: Nunca deixe inputs sem classe ou com `background: #ffffff`. Use `class="form-input"` ou aplique:
  ```css
  background: var(--panel2, #182030);
  color: var(--text, #f8fafc);
  border: 1px solid var(--line, rgba(255,255,255,0.14));
  border-radius: 8px;
  ```
- **Textos e Rótulos**:
  - Labels principais: `color: var(--text, #f8fafc); font-weight: 700;`
  - Subtítulos e helpers: `color: var(--muted, #94a3b8); font-size: 0.75rem;`
  - Nunca use texto escuro (`#000` ou `#1e1e24`) sobre fundos escuros.

### 3. Alinhamento e Centralização do Botão 'X' de Fechar Modal
- **Proibido usar `.btn.sm` ou `.btn` no botão de fechar**: classes de botão de texto possuem padding assimétrico (`padding: 5px 12px;`) que empurra o `x` para o canto inferior direito.
- **Proibido usar caracteres tipográficos crus (`&times;`, `×`, `x`)**: sofrem distorção ótica de baseline na fonte.
- **Padrão Obrigatório**:
  ```html
  <button type="button" @click="showModal = false" class="modal-close-btn" title="Fechar modal" aria-label="Fechar">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"></line>
      <line x1="6" y1="6" x2="18" y2="18"></line>
    </svg>
  </button>
  ```

### 4. Execução da Auditoria Automatizada
Antes de responder ao usuário ou rodar o deploy, execute:
```bash
.venv/bin/python3 scripts/ux_audit.py
```
Se qualquer erro for apontado, corrija-o imediatamente antes de considerar a tarefa finalizada.
