/**
 * M-One Radar Table Column Customizer (static/js/radar-columns.js)
 * Permite arrastar colunas diretamente no cabeçalho (Drag & Drop nativo) e
 * ocultar/exibir colunas através de popover com persistência em localStorage.
 * Segregação modular estrita (< 500 linhas).
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'mone_radar_columns_v1';

  const RADAR_COLUMNS = [
    { key: 'classe', label: 'Classe / Score', fixed: false, defaultVisible: true, width: '70px' },
    { key: 'empresa', label: 'Empresa & Decisor', fixed: true, defaultVisible: true, width: '200px' },
    { key: 'localizacao', label: 'Localização', fixed: false, defaultVisible: true, width: '140px' },
    { key: 'contato', label: 'Contato Telefônico', fixed: false, defaultVisible: true, width: '170px' },
    { key: 'canais', label: 'Canais Digitais', fixed: false, defaultVisible: true, width: '95px' },
    { key: 'status', label: 'Status', fixed: false, defaultVisible: true, width: '135px' },
    { key: 'acoes', label: 'Ação Comercial', fixed: true, defaultVisible: true, width: '115px' }
  ];

  const DEFAULT_ORDER = RADAR_COLUMNS.map(c => c.key);

  function getStoredConfig() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && Array.isArray(parsed.order)) {
          // Garante que todas as colunas oficiais estejam presentes
          const validKeys = new Set(DEFAULT_ORDER);
          const sanitizedOrder = parsed.order.filter(k => validKeys.has(k));
          DEFAULT_ORDER.forEach(k => {
            if (!sanitizedOrder.includes(k)) sanitizedOrder.push(k);
          });
          // Garante que colunas protegidas (fixed) nunca estejam em hidden
          const sanitizedHidden = Array.isArray(parsed.hidden)
            ? parsed.hidden.filter(k => {
                const col = RADAR_COLUMNS.find(c => c.key === k);
                return col && !col.fixed;
              })
            : [];
          return { order: sanitizedOrder, hidden: sanitizedHidden };
        }
      }
    } catch (e) {
      console.warn('[Radar Columns] Erro ao ler localStorage:', e);
    }
    return { order: [...DEFAULT_ORDER], hidden: [] };
  }

  function saveStoredConfig(config) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch (e) {
      console.warn('[Radar Columns] Erro ao salvar localStorage:', e);
    }
  }

  function applyColumnsToTable() {
    const table = document.querySelector('.leads-table');
    if (!table) return;

    const config = getStoredConfig();
    const theadRow = table.querySelector('thead tr');
    const tbodyRows = table.querySelectorAll('tbody tr.lead-row');
    const emptyStateTd = table.querySelector('tbody tr td.empty-state');

    // 1. Reordena os TH no thead
    if (theadRow) {
      const thMap = {};
      theadRow.querySelectorAll('th[data-col]').forEach(th => {
        thMap[th.getAttribute('data-col')] = th;
      });

      config.order.forEach(colKey => {
        const th = thMap[colKey];
        if (th) theadRow.appendChild(th);
      });

      // Aplica visibilidade nos TH
      config.order.forEach(colKey => {
        const th = thMap[colKey];
        if (!th) return;
        const isHidden = config.hidden.includes(colKey);
        th.classList.toggle('col-hidden', isHidden);
      });
    }

    // 2. Reordena os TD em cada linha do tbody
    tbodyRows.forEach(row => {
      const tdMap = {};
      row.querySelectorAll('td[data-col]').forEach(td => {
        tdMap[td.getAttribute('data-col')] = td;
      });

      config.order.forEach(colKey => {
        const td = tdMap[colKey];
        if (td) row.appendChild(td);
      });

      // Aplica visibilidade nos TD
      config.order.forEach(colKey => {
        const td = tdMap[colKey];
        if (!td) return;
        const isHidden = config.hidden.includes(colKey);
        td.classList.toggle('col-hidden', isHidden);
      });
    });

    // 3. Atualiza colspan se houver mensagem de tabela vazia
    if (emptyStateTd) {
      const visibleColsCount = config.order.filter(k => !config.hidden.includes(k)).length;
      emptyStateTd.setAttribute('colspan', visibleColsCount || 1);
    }

    // 4. Atualiza os checkboxes do popover de colunas
    updatePopoverUI();
  }

  let draggedColKey = null;

  function initDragAndDrop() {
    const table = document.querySelector('.leads-table');
    if (!table) return;

    const ths = table.querySelectorAll('thead th[data-col]');
    ths.forEach(th => {
      th.setAttribute('draggable', 'true');
      th.classList.add('th-draggable');

      // Garante indicador visual de arraste (drag grip)
      if (!th.querySelector('.drag-handle-icon')) {
        const grip = document.createElement('span');
        grip.className = 'drag-handle-icon';
        grip.innerHTML = '⋮⋮';
        grip.title = 'Clique e arraste para reordenar esta coluna';
        th.prepend(grip);
      }

      // Handlers de Drag & Drop
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

  function toggleColumn(colKey) {
    const colDef = RADAR_COLUMNS.find(c => c.key === colKey);
    if (!colDef || colDef.fixed) return; // Protegida contra ocultação

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

  function resetColumnsToDefault() {
    const config = { order: [...DEFAULT_ORDER], hidden: [] };
    saveStoredConfig(config);
    applyColumnsToTable();
  }

  function updatePopoverUI() {
    const container = document.getElementById('radar-columns-list');
    if (!container) return;

    const config = getStoredConfig();
    container.innerHTML = '';

    // Renderiza itens na ordem atual para facilitar a leitura do usuário
    config.order.forEach(colKey => {
      const col = RADAR_COLUMNS.find(c => c.key === colKey);
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
        ${isFixed ? '<span class="col-fixed-badge" title="Coluna essencial: protegida para garantir identificação e ação do lead">Obrigatória</span>' : ''}
      `;

      const input = item.querySelector('input');
      if (!isFixed) {
        input.addEventListener('change', () => {
          toggleColumn(col.key);
        });
      }

      container.appendChild(item);
    });
  }

  // Inicialização autônoma ao carregar DOM
  function init() {
    applyColumnsToTable();
    initDragAndDrop();
    updatePopoverUI();

    // Vincula botão de Resetar se existir
    const resetBtn = document.getElementById('btn-reset-radar-columns');
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

  // Expõe API global no window para consumo e integração
  window.MOneRadarColumns = {
    apply: applyColumnsToTable,
    toggle: toggleColumn,
    reset: resetColumnsToDefault,
    getConfig: getStoredConfig,
    COLUMNS: RADAR_COLUMNS
  };
})();
