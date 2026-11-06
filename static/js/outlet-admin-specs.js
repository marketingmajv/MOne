/**
 * M-One Outlet Admin - Módulo de Gestão de Ficha Técnica & Especificações
 * Gerencia a renderização, edição, campos extras e auto-preenchimento canônico
 * das especificações técnicas dos produtos do Outlet MAJ.
 */

(function () {
  'use strict';

  const STANDARD_SPEC_KEYS = [
    'Motor',
    'Velocidade Máxima',
    'Autonomia',
    'Bateria',
    'Carga Máxima',
    'Freios',
    'Diferencial'
  ];

  let isSpecsSectionOpen = true;

  function toggleOutletSpecsSection() {
    const content = document.getElementById('outlet_specs_content');
    const chevron = document.getElementById('outlet_specs_chevron');
    const toggleText = document.getElementById('outlet_specs_toggle_text');
    if (!content) return;

    isSpecsSectionOpen = !isSpecsSectionOpen;
    if (isSpecsSectionOpen) {
      content.style.display = 'block';
      if (chevron) chevron.style.transform = 'none';
      if (toggleText) toggleText.textContent = 'Recolher';
    } else {
      content.style.display = 'none';
      if (chevron) chevron.style.transform = 'rotate(180deg)';
      if (toggleText) toggleText.textContent = 'Expandir';
    }
  }

  function updateOutletSpecsBadge() {
    const badge = document.getElementById('outlet_specs_badge');
    if (!badge) return;

    let count = 0;
    const motor = document.getElementById('outlet_spec_motor')?.value.trim();
    const vel = document.getElementById('outlet_spec_velocidade')?.value.trim();
    const aut = document.getElementById('outlet_spec_autonomia')?.value.trim();
    const bat = document.getElementById('outlet_spec_bateria')?.value.trim();
    const carga = document.getElementById('outlet_spec_carga')?.value.trim();
    const freios = document.getElementById('outlet_spec_freios')?.value.trim();
    const dif = document.getElementById('outlet_spec_diferencial')?.value.trim();

    if (motor) count++;
    if (vel) count++;
    if (aut) count++;
    if (bat) count++;
    if (carga) count++;
    if (freios) count++;
    if (dif) count++;

    const customRows = document.querySelectorAll('#outlet_custom_specs_container .outlet-custom-spec-row');
    customRows.forEach(row => {
      const k = row.querySelector('.spec-custom-k')?.value.trim();
      const v = row.querySelector('.spec-custom-v')?.value.trim();
      if (k && v) count++;
    });

    badge.textContent = `${count} preenchido${count === 1 ? '' : 's'}`;
    if (count > 0) {
      badge.style.color = '#00cc88';
      badge.style.background = 'rgba(0, 204, 136, 0.15)';
      badge.style.borderColor = 'rgba(0, 204, 136, 0.35)';
    } else {
      badge.style.color = '#60a5fa';
      badge.style.background = 'rgba(0, 112, 243, 0.18)';
      badge.style.borderColor = 'rgba(0, 112, 243, 0.3)';
    }
  }

  function addOutletCustomSpecRow(key = '', val = '') {
    const container = document.getElementById('outlet_custom_specs_container');
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'outlet-custom-spec-row';
    row.style.display = 'grid';
    row.style.gridTemplateColumns = '1.2fr 1.8fr auto';
    row.style.gap = '8px';
    row.style.alignItems = 'center';

    const inputKey = document.createElement('input');
    inputKey.type = 'text';
    inputKey.className = 'form-input spec-custom-k';
    inputKey.placeholder = 'Nome (Ex: Suspensão, Quadro)';
    inputKey.value = key || '';
    inputKey.style.width = '100%';
    inputKey.oninput = updateOutletSpecsBadge;

    const inputVal = document.createElement('input');
    inputVal.type = 'text';
    inputVal.className = 'form-input spec-custom-v';
    inputVal.placeholder = 'Valor (Ex: Dianteira invertida, Alumínio 6061)';
    inputVal.value = val || '';
    inputVal.style.width = '100%';
    inputVal.oninput = updateOutletSpecsBadge;

    const btnRemove = document.createElement('button');
    btnRemove.type = 'button';
    btnRemove.className = 'btn sm';
    btnRemove.title = 'Remover especificação';
    btnRemove.innerHTML = '&times;';
    btnRemove.style.color = '#ef4444';
    btnRemove.style.fontWeight = 'bold';
    btnRemove.style.padding = '4px 10px';
    btnRemove.style.fontSize = '16px';
    btnRemove.onclick = function () {
      removeOutletCustomSpecRow(this);
    };

    row.appendChild(inputKey);
    row.appendChild(inputVal);
    row.appendChild(btnRemove);
    container.appendChild(row);

    updateOutletSpecsBadge();
  }

  function removeOutletCustomSpecRow(btn) {
    const row = btn?.closest('.outlet-custom-spec-row');
    if (row) {
      row.remove();
      updateOutletSpecsBadge();
    }
  }

  function renderOutletSpecs(specsInput) {
    let specs = specsInput || {};
    if (typeof specs === 'string') {
      try {
        specs = JSON.parse(specs);
      } catch (e) {
        specs = {};
      }
    }

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || '';
    };

    setVal('outlet_spec_motor', specs['Motor']);
    setVal('outlet_spec_velocidade', specs['Velocidade Máxima']);
    setVal('outlet_spec_autonomia', specs['Autonomia']);
    setVal('outlet_spec_bateria', specs['Bateria']);
    setVal('outlet_spec_carga', specs['Carga Máxima']);
    setVal('outlet_spec_freios', specs['Freios']);
    setVal('outlet_spec_diferencial', specs['Diferencial']);

    const container = document.getElementById('outlet_custom_specs_container');
    if (container) container.innerHTML = '';

    if (specs && typeof specs === 'object') {
      Object.entries(specs).forEach(([k, v]) => {
        if (k === 'color_prices' || STANDARD_SPEC_KEYS.includes(k)) return;
        if (typeof v === 'string' && v.trim()) {
          addOutletCustomSpecRow(k, v);
        }
      });
    }

    updateOutletSpecsBadge();
  }

  function resetOutletSpecs() {
    renderOutletSpecs({});
  }

  function serializeOutletSpecs() {
    const specs = {};
    const getVal = id => document.getElementById(id)?.value?.trim() || '';

    const motor = getVal('outlet_spec_motor');
    if (motor) specs['Motor'] = motor;

    const vel = getVal('outlet_spec_velocidade');
    if (vel) specs['Velocidade Máxima'] = vel;

    const aut = getVal('outlet_spec_autonomia');
    if (aut) specs['Autonomia'] = aut;

    const bat = getVal('outlet_spec_bateria');
    if (bat) specs['Bateria'] = bat;

    const carga = getVal('outlet_spec_carga');
    if (carga) specs['Carga Máxima'] = carga;

    const freios = getVal('outlet_spec_freios');
    if (freios) specs['Freios'] = freios;

    const dif = getVal('outlet_spec_diferencial');
    if (dif) specs['Diferencial'] = dif;

    const customRows = document.querySelectorAll('#outlet_custom_specs_container .outlet-custom-spec-row');
    customRows.forEach(row => {
      const k = row.querySelector('.spec-custom-k')?.value?.trim();
      const v = row.querySelector('.spec-custom-v')?.value?.trim();
      if (k && v) specs[k] = v;
    });

    const hidden = document.getElementById('outlet_form_specs_json');
    if (hidden) {
      hidden.value = JSON.stringify(specs);
    }
    return specs;
  }

  function populateSpecsFromCanonical() {
    const nameInput = document.getElementById('outlet_form_name');
    const rawName = (nameInput?.value || '').trim();
    if (!rawName) {
      alert('Por favor, informe primeiro o Nome do Modelo para buscar na base canônica.');
      if (nameInput) nameInput.focus();
      return;
    }

    const canon = window.CANONICAL_MODELS || {};
    const norm = str => (str || '').toUpperCase().replace(/[-_]/g, ' ').replace(/\s+/g, ' ').trim();
    const query = norm(rawName);

    // 1. Busca exata ou por alias
    let match = canon[query] || canon[rawName.toUpperCase()];

    // 2. Busca parcial
    if (!match) {
      const keys = Object.keys(canon);
      for (const k of keys) {
        const normK = norm(k);
        if (normK === query || query.includes(normK) || normK.includes(query)) {
          match = canon[k];
          break;
        }
      }
    }

    if (!match || !match.specs) {
      alert(`Nenhuma ficha canônica encontrada para "${rawName}". Preencha os campos manualmente.`);
      return;
    }

    const sp = match.specs || {};
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val) el.value = val;
    };

    setVal('outlet_spec_motor', sp['Motor']);
    setVal('outlet_spec_velocidade', sp['Velocidade Máxima']);
    setVal('outlet_spec_autonomia', sp['Autonomia']);
    setVal('outlet_spec_bateria', sp['Bateria']);
    setVal('outlet_spec_carga', sp['Carga Máxima']);
    setVal('outlet_spec_freios', sp['Freios']);
    setVal('outlet_spec_diferencial', sp['Diferencial']);

    // Preenche descrição se vazia
    const descEl = document.getElementById('outlet_form_description');
    if (descEl && !descEl.value.trim() && match.description) {
      descEl.value = match.description;
    }

    // Preenche categoria se vazia
    const catEl = document.getElementById('outlet_form_category');
    if (catEl && !catEl.value.trim() && match.category) {
      catEl.value = match.category;
    }

    updateOutletSpecsBadge();
    alert(`⚡ Ficha Canônica de "${match.name || rawName}" aplicada com sucesso!`);
  }

  // Exportação Global para eventos inline do DOM e outros scripts
  Object.assign(window, {
    toggleOutletSpecsSection,
    updateOutletSpecsBadge,
    addOutletCustomSpecRow,
    removeOutletCustomSpecRow,
    renderOutletSpecs,
    resetOutletSpecs,
    serializeOutletSpecs,
    populateSpecsFromCanonical
  });
})();

