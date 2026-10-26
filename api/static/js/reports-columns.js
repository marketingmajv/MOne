/**
 * M-One Reports Dashboard Table Column & Action Customizer (static/js/reports-columns.js)
 * Recursos:
 *  1. Drag & Drop nativo para reordenar colunas no thead
 *  2. Redimensionamento manual de largura de coluna (Column Resizing com cursor col-resize)
 *  3. Popover de personalização em abas:
 *     - Aba 'Colunas': Ocultar/exibir e reordenar colunas com trava em colunas obrigatórias
 *     - Aba 'Botões Rápidos': Escolher quais botões de ação fixar na linha vs menu suspenso
 *  4. Persistência integral no localStorage (ordem, larguras e botões visíveis)
 *  5. Botão de reset rápido para o padrão de fábrica da MAJ
 * Segregação modular estrita (< 500 linhas).
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'mone_reports_columns_v2';

  const REPORTS_COLUMNS = [
    { key: 'colaborador', label: 'Colaborador', fixed: true, defaultVisible: true, defaultWidth: '220px' },
    { key: 'area', label: 'Área & Função', fixed: false, defaultVisible: true, defaultWidth: '180px' },
    { key: 'status', label: 'Status da Entrega', fixed: false, defaultVisible: true, defaultWidth: '150px' },
    { key: 'preenchimento', label: 'Preenchimento', fixed: false, defaultVisible: true, defaultWidth: '130px' },
    { key: 'data_envio', label: 'Data/Hora Envio', fixed: false, defaultVisible: true, defaultWidth: '140px' },
    { key: 'acoes', label: 'Ações da Diretoria', fixed: true, defaultVisible: true, defaultWidth: '310px' }
  ];

  const ACTION_BUTTONS = [
    { key: 'ver_respostas', label: 'Ver Respostas', icon: '👁️', defaultVisible: true, fixed: false },
    { key: 'afericao_ia', label: 'Aferição IA', icon: '🎯', defaultVisible: true, fixed: false },
    { key: 'sync_doc', label: 'Sincronizar Google Doc', icon: '⚡', defaultVisible: false, fixed: false },
    { key: 'subir_arquivo', label: 'Subir Arquivo (PDF/DOCX)', icon: '📤', defaultVisible: false, fixed: false },
    { key: 'baixar_arquivo', label: 'Baixar Arquivo Entregue', icon: '📥', defaultVisible: false, fixed: false },
    { key: 'cobrar_whatsapp', label: 'Cobrar via WhatsApp', icon: '💬', defaultVisible: false, fixed: false },
    { key: 'menu_mais', label: 'Menu ⋯ (Mais Opções)', icon: '⋯', defaultVisible: true, fixed: true }
  ];

  const DEFAULT_ORDER = REPORTS_COLUMNS.map(c => c.key);
  const DEFAULT_VISIBLE_BUTTONS = ACTION_BUTTONS.filter(b => b.defaultVisible).map(b => b.key);
  const DEFAULT_WIDTHS = {};
  REPORTS_COLUMNS.forEach(c => {
    DEFAULT_WIDTHS[c.key] = c.defaultWidth;
  });

  function getStoredConfig() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
          // 1. Ordem de Colunas
          let order = Array.isArray(parsed.order) ? parsed.order : [...DEFAULT_ORDER];
          const validKeys = new Set(DEFAULT_ORDER);
          order = order.filter(k => validKeys.has(k));
          DEFAULT_ORDER.forEach(k => {
            if (!order.includes(k)) order.push(k);
          });

          // 2. Colunas Ocultas
          const hidden = Array.isArray(parsed.hidden)
            ? parsed.hidden.filter(k => {
                const col = REPORTS_COLUMNS.find(c => c.key === k);
                return col && !col.fixed;
              })
            : [];

          // 3. Larguras Personalizadas
          const widths = (parsed.widths && typeof parsed.widths === 'object')
            ? { ...DEFAULT_WIDTHS, ...parsed.widths }
            : { ...DEFAULT_WIDTHS };

          // 4. Botões de Ação Visíveis
          let visibleButtons = Array.isArray(parsed.visibleButtons)
            ? parsed.visibleButtons
            : [...DEFAULT_VISIBLE_BUTTONS];
          if (!visibleButtons.includes('menu_mais')) visibleButtons.push('menu_mais');

          return { order, hidden, widths, visibleButtons };
        }
      }
    } catch (e) {
      console.warn('[Reports Columns] Erro ao ler localStorage:', e);
    }
    return {
      order: [...DEFAULT_ORDER],
      hidden: [],
      widths: { ...DEFAULT_WIDTHS },
      visibleButtons: [...DEFAULT_VISIBLE_BUTTONS]
    };
  }

  function saveStoredConfig(config) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch (e) {
      console.warn('[Reports Columns] Erro ao salvar localStorage:', e);
    }
  }

  function applyColumnsToTable() {
    const table = document.querySelector('.reports-table');
    if (!table) return;

    const config = getStoredConfig();
    const theadRow = table.querySelector('thead tr');
    const tbodyRows = table.querySelectorAll('tbody tr.employee-row');
    const emptyStateTd = table.querySelector('tbody tr td.empty-state');

    // 1. Reordena e ajusta largura/visibilidade dos TH no thead
    if (theadRow) {
      const thMap = {};
      theadRow.querySelectorAll('th[data-col]').forEach(th => {
        thMap[th.getAttribute('data-col')] = th;
      });

      config.order.forEach(colKey => {
        const th = thMap[colKey];
        if (th) {
          theadRow.appendChild(th);
          const isHidden = config.hidden.includes(colKey);
          th.classList.toggle('col-hidden', isHidden);
          if (config.widths && config.widths[colKey]) {
            th.style.width = config.widths[colKey];
            th.style.minWidth = config.widths[colKey];
          }
        }
      });
    }

    // 2. Reordena e ajusta visibilidade dos TD no tbody
    tbodyRows.forEach(row => {
      const tdMap = {};
      row.querySelectorAll('td[data-col]').forEach(td => {
        tdMap[td.getAttribute('data-col')] = td;
      });

      config.order.forEach(colKey => {
        const td = tdMap[colKey];
        if (td) {
          row.appendChild(td);
          const isHidden = config.hidden.includes(colKey);
          td.classList.toggle('col-hidden', isHidden);
        }
      });
    });

    // 3. Colspan de empty state se houver
    if (emptyStateTd) {
      const visibleColsCount = config.order.filter(k => !config.hidden.includes(k)).length;
      emptyStateTd.setAttribute('colspan', visibleColsCount || 1);
    }

    // 4. Aplica visibilidade dos botões de ação nas células de ações
    applyButtonsToTable();

    // 5. Atualiza a interface do popover
    updatePopoverUI();
  }

  function applyButtonsToTable() {
    const table = document.querySelector('.reports-table');
    if (!table) return;

    const config = getStoredConfig();
    const actionBtns = table.querySelectorAll('[data-action-btn]');

    actionBtns.forEach(btn => {
      const btnKey = btn.getAttribute('data-action-btn');
      const isVisible = config.visibleButtons.includes(btnKey);
      btn.classList.toggle('btn-action-hidden', !isVisible);
    });
  }

  let draggedColKey = null;

  function initDragAndDrop() {
    const table = document.querySelector('.reports-table');
    if (!table) return;

    const ths = table.querySelectorAll('thead th[data-col]');
    ths.forEach(th => {
      th.setAttribute('draggable', 'true');
      th.classList.add('th-draggable');

      // Ícone visual de arraste
      if (!th.querySelector('.drag-handle-icon')) {
        const grip = document.createElement('span');
        grip.className = 'drag-handle-icon';
        grip.innerHTML = '⋮⋮';
        grip.title = 'Clique e arraste para reordenar esta coluna';
        th.prepend(grip);
      }

      th.ondragstart = function (e) {
        draggedColKey = th.getAttribute('data-col');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', draggedColKey);
        th.classList.add('is-dragging');
        table.classList.add('table-col-dragging');
      };

      th.ondragover = function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const targetCol = th.getAttribute('data-col');
        if (targetCol === draggedColKey) return;

        const rect = th.getBoundingClientRect();
        const midX = rect.left + rect.width / 2;
        const isBefore = e.clientX < midX;

        th.classList.toggle('drag-over-left', isBefore);
        th.classList.toggle('drag-over-right', !isBefore);
      };

      th.ondragleave = function () {
        th.classList.remove('drag-over-left', 'drag-over-right');
      };

      th.ondrop = function (e) {
        e.preventDefault();
        th.classList.remove('drag-over-left', 'drag-over-right');
        const targetCol = th.getAttribute('data-col');
        if (!draggedColKey || draggedColKey === targetCol) return;

        const rect = th.getBoundingClientRect();
        const isBefore = e.clientX < (rect.left + rect.width / 2);

        const config = getStoredConfig();
        const fromIdx = config.order.indexOf(draggedColKey);
        if (fromIdx === -1) return;

        config.order.splice(fromIdx, 1);
        let toIdx = config.order.indexOf(targetCol);
        if (!isBefore) toIdx += 1;

        config.order.splice(toIdx, 0, draggedColKey);
        saveStoredConfig(config);
        applyColumnsToTable();
      };

      th.ondragend = function () {
        draggedColKey = null;
        table.classList.remove('table-col-dragging');
        ths.forEach(t => t.classList.remove('is-dragging', 'drag-over-left', 'drag-over-right'));
      };
    });
  }

  function initColumnResizers() {
    const table = document.querySelector('.reports-table');
    if (!table) return;

    const ths = table.querySelectorAll('thead th[data-col]');
    ths.forEach(th => {
      // Evita duplicar resizer na mesma célula
      if (th.querySelector('.col-resizer')) return;

      const resizer = document.createElement('div');
      resizer.className = 'col-resizer';
      resizer.title = 'Arraste para redimensionar a largura desta coluna';
      th.appendChild(resizer);

      // Trava para evitar conflito com drag & drop
      resizer.addEventListener('mousedown', function (e) {
        e.stopPropagation();
        e.preventDefault();

        const colKey = th.getAttribute('data-col');
        const startX = e.pageX;
        const startWidth = th.offsetWidth;

        document.body.classList.add('table-col-resizing');
        th.classList.add('is-resizing');
        resizer.classList.add('resizing-active');

        function onMouseMove(moveEvent) {
          moveEvent.preventDefault();
          const diff = moveEvent.pageX - startX;
          const newWidth = Math.max(70, startWidth + diff);
          th.style.width = newWidth + 'px';
          th.style.minWidth = newWidth + 'px';
        }

        function onMouseUp() {
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
          document.body.classList.remove('table-col-resizing');
          th.classList.remove('is-resizing');
          resizer.classList.remove('resizing-active');

          const finalWidth = th.offsetWidth + 'px';
          const config = getStoredConfig();
          if (!config.widths) config.widths = {};
          config.widths[colKey] = finalWidth;
          saveStoredConfig(config);
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    });
  }

  function toggleColumn(colKey) {
    const colDef = REPORTS_COLUMNS.find(c => c.key === colKey);
    if (!colDef || colDef.fixed) return;

    const config = getStoredConfig();
    const idx = config.hidden.indexOf(colKey);
    if (idx > -1) {
      config.hidden.splice(idx, 1);
    } else {
      config.hidden.push(colKey);
    }
    saveStoredConfig(config);
    applyColumnsToTable();
  }

  function toggleButton(btnKey) {
    const btnDef = ACTION_BUTTONS.find(b => b.key === btnKey);
    if (!btnDef || btnDef.fixed) return;

    const config = getStoredConfig();
    const idx = config.visibleButtons.indexOf(btnKey);
    if (idx > -1) {
      config.visibleButtons.splice(idx, 1);
    } else {
      config.visibleButtons.push(btnKey);
    }
    saveStoredConfig(config);
    applyButtonsToTable();
  }

  function resetColumnsToDefault() {
    const config = {
      order: [...DEFAULT_ORDER],
      hidden: [],
      widths: { ...DEFAULT_WIDTHS },
      visibleButtons: [...DEFAULT_VISIBLE_BUTTONS]
    };
    saveStoredConfig(config);
    applyColumnsToTable();
  }

  function updatePopoverUI() {
    const colsContainer = document.getElementById('reports-columns-list');
    const btnsContainer = document.getElementById('reports-buttons-list');
    const config = getStoredConfig();

    // 1. Aba Colunas
    if (colsContainer) {
      colsContainer.innerHTML = '';
      config.order.forEach(colKey => {
        const col = REPORTS_COLUMNS.find(c => c.key === colKey);
        if (!col) return;

        const isChecked = !config.hidden.includes(col.key);
        const isFixed = col.fixed;

        const item = document.createElement('label');
        item.className = 'col-config-item' + (isFixed ? ' is-fixed' : '');
        item.innerHTML = `
          <div class="col-item-left">
            <input type="checkbox" 
                   ${isChecked ? 'checked' : ''} 
                   ${isFixed ? 'disabled' : ''} 
                   data-col-key="${col.key}">
            <span class="col-item-label">${col.label}</span>
          </div>
          ${isFixed ? '<span class="col-fixed-badge" title="Coluna protegida">Obrigatória</span>' : ''}
        `;

        const input = item.querySelector('input');
        if (!isFixed) {
          input.addEventListener('change', () => toggleColumn(col.key));
        }
        colsContainer.appendChild(item);
      });
    }

    // 2. Aba Botões de Ação
    if (btnsContainer) {
      btnsContainer.innerHTML = '';
      ACTION_BUTTONS.forEach(btn => {
        const isChecked = config.visibleButtons.includes(btn.key);
        const isFixed = btn.fixed;

        const item = document.createElement('label');
        item.className = 'col-config-item' + (isFixed ? ' is-fixed' : '');
        item.innerHTML = `
          <div class="col-item-left">
            <input type="checkbox" 
                   ${isChecked ? 'checked' : ''} 
                   ${isFixed ? 'disabled' : ''} 
                   data-btn-key="${btn.key}">
            <span style="font-size: 0.95rem;">${btn.icon}</span>
            <span class="col-item-label">${btn.label}</span>
          </div>
          ${isFixed ? '<span class="col-fixed-badge" title="Menu padrão">Sempre Visível</span>' : ''}
        `;

        const input = item.querySelector('input');
        if (!isFixed) {
          input.addEventListener('change', () => toggleButton(btn.key));
        }
        btnsContainer.appendChild(item);
      });
    }
  }

  function init() {
    applyColumnsToTable();
    initDragAndDrop();
    initColumnResizers();
    updatePopoverUI();

    const resetBtn = document.getElementById('btn-reset-reports-columns');
    if (resetBtn) {
      resetBtn.onclick = function (e) {
        e.preventDefault();
        resetColumnsToDefault();
      };
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.MOneReportsColumns = {
    apply: applyColumnsToTable,
    toggleColumn: toggleColumn,
    toggleButton: toggleButton,
    reset: resetColumnsToDefault,
    getConfig: getStoredConfig,
    COLUMNS: REPORTS_COLUMNS,
    BUTTONS: ACTION_BUTTONS
  };
})();
