/**
 * M-One Central de Produtos Mestre (static/js/product-hub.js)
 * Single Source of Truth para o ecossistema MAJ Mobilidade.
 * Gerencia modal de 3 abas, edição de ficha técnica canônica,
 * custom specs dinâmicos e copys contextuais para Atacado B2B e Varejo Outlet.
 */

(function () {
  'use strict';

  const STANDARD_SPEC_KEYS = {
    motor: 'Motor',
    velocidade: 'Velocidade Máxima',
    autonomia: 'Autonomia',
    bateria: 'Bateria',
    carga: 'Carga Máxima',
    freios: 'Freios',
    diferencial: 'Diferencial'
  };

  /**
   * Alterna entre as abas do Modal (Mídia, Specs, Copys)
   */
  window.switchMasterTab = function (tabName) {
    const tabs = ['midia', 'specs', 'copys'];
    tabs.forEach(t => {
      const panel = document.getElementById(`master_tab_${t}`);
      const btn = document.getElementById(`tab_btn_${t}`);
      if (panel) {
        panel.style.display = (t === tabName) ? 'block' : 'none';
      }
      if (btn) {
        if (t === tabName) {
          btn.style.fontWeight = '800';
          btn.style.background = '#00cc88';
          btn.style.color = '#000';
        } else {
          btn.style.fontWeight = '700';
          btn.style.background = 'transparent';
          btn.style.color = 'var(--text, #f8fafc)';
        }
      }
    });
  };

  /**
   * Fecha o modal do produto mestre
   */
  window.closeMasterProductModal = function () {
    if (typeof closeModal === 'function') {
      closeModal('masterProductModal');
    } else {
      const el = document.getElementById('masterProductModal');
      if (el) el.classList.remove('show');
    }
  };

  /**
   * Adiciona uma linha de especificação técnica customizada
   */
  window.addMasterCustomSpecRow = function (key = '', val = '') {
    const container = document.getElementById('master_custom_specs_container');
    if (!container) return;

    const row = document.createElement('div');
    row.className = 'master-custom-spec-row';
    row.style.display = 'grid';
    row.style.gridTemplateColumns = '1.2fr 1.8fr auto';
    row.style.gap = '8px';
    row.style.alignItems = 'center';

    const inputKey = document.createElement('input');
    inputKey.type = 'text';
    inputKey.className = 'form-input master-custom-k';
    inputKey.placeholder = 'Nome (Ex: Suspensão, Aro)';
    inputKey.value = key || '';
    inputKey.style.width = '100%';

    const inputVal = document.createElement('input');
    inputVal.type = 'text';
    inputVal.className = 'form-input master-custom-v';
    inputVal.placeholder = 'Valor (Ex: Dianteira invertida)';
    inputVal.value = val || '';
    inputVal.style.width = '100%';

    const btnRemove = document.createElement('button');
    btnRemove.type = 'button';
    btnRemove.className = 'btn sm';
    btnRemove.style.color = '#ef4444';
    btnRemove.style.borderColor = 'rgba(239, 68, 68, 0.3)';
    btnRemove.style.padding = '6px 10px';
    btnRemove.innerHTML = '🗑️';
    btnRemove.title = 'Remover linha';
    btnRemove.onclick = function () {
      row.remove();
    };

    row.appendChild(inputKey);
    row.appendChild(inputVal);
    row.appendChild(btnRemove);
    container.appendChild(row);
  };

  /**
   * Limpa todos os campos do formulário para novo cadastro
   */
  function resetMasterForm() {
    document.getElementById('master_form_id').value = '';
    document.getElementById('master_form_name').value = '';
    document.getElementById('master_form_slug').value = '';
    document.getElementById('master_form_category').value = 'Bicicletas Elétricas';
    document.getElementById('master_form_brand').value = 'MAJ';
    document.getElementById('master_form_status').value = 'active';
    document.getElementById('master_form_image_main').value = '';
    document.getElementById('master_form_banner').value = '';

    // Copys
    document.getElementById('master_form_copy_atacado').value = '';
    document.getElementById('master_form_copy_outlet').value = '';
    document.getElementById('master_form_copy_showroom').value = '';

    // Specs
    document.getElementById('master_spec_motor').value = '';
    document.getElementById('master_spec_velocidade').value = '';
    document.getElementById('master_spec_autonomia').value = '';
    document.getElementById('master_spec_bateria').value = '';
    document.getElementById('master_spec_carga').value = '';
    document.getElementById('master_spec_freios').value = '';
    document.getElementById('master_spec_diferencial').value = '';

    // Custom specs container
    const customContainer = document.getElementById('master_custom_specs_container');
    if (customContainer) customContainer.innerHTML = '';

    document.getElementById('master_form_specs_json').value = '{}';
    document.getElementById('master_form_images_gallery').value = '[]';
  }

  /**
   * Abre o modal para criar um novo Produto Mestre
   */
  window.openMasterProductNewModal = function () {
    resetMasterForm();
    const titleEl = document.getElementById('master_modal_title');
    if (titleEl) titleEl.textContent = 'Novo Produto Mestre';

    switchMasterTab('midia');
    if (typeof openModal === 'function') {
      openModal('masterProductModal');
    } else {
      const el = document.getElementById('masterProductModal');
      if (el) el.classList.add('show');
    }
  };

  /**
   * Abre o modal para editar um Produto Mestre existente
   */
  window.openMasterProductEditModal = function (productId) {
    const list = window.MASTER_PRODUCTS_LIST || [];
    const product = list.find(p => String(p.id) === String(productId));
    if (!product) {
      alert('Produto não localizado.');
      return;
    }

    resetMasterForm();

    const titleEl = document.getElementById('master_modal_title');
    if (titleEl) titleEl.textContent = `Editar: ${product.name}`;

    // Identificação
    document.getElementById('master_form_id').value = product.id || '';
    document.getElementById('master_form_name').value = product.name || '';
    document.getElementById('master_form_slug').value = product.slug || '';
    document.getElementById('master_form_category').value = product.category || 'Bicicletas Elétricas';
    document.getElementById('master_form_brand').value = product.brand || 'MAJ';
    document.getElementById('master_form_status').value = product.status || 'active';
    document.getElementById('master_form_image_main').value = product.image_main || '';
    document.getElementById('master_form_banner').value = product.banner_widescreen || '';

    // Copys contextuais
    document.getElementById('master_form_copy_atacado').value = product.copy_atacado || '';
    document.getElementById('master_form_copy_outlet').value = product.copy_outlet || '';
    document.getElementById('master_form_copy_showroom').value = product.copy_showroom || '';

    // Specs Ouro
    let specs = {};
    if (typeof product.specs_json === 'string') {
      try { specs = JSON.parse(product.specs_json); } catch (e) { specs = {}; }
    } else if (typeof product.specs_json === 'object' && product.specs_json !== null) {
      specs = product.specs_json;
    }

    document.getElementById('master_spec_motor').value = specs['Motor'] || '';
    document.getElementById('master_spec_velocidade').value = specs['Velocidade Máxima'] || '';
    document.getElementById('master_spec_autonomia').value = specs['Autonomia'] || '';
    document.getElementById('master_spec_bateria').value = specs['Bateria'] || '';
    document.getElementById('master_spec_carga').value = specs['Carga Máxima'] || '';
    document.getElementById('master_spec_freios').value = specs['Freios'] || '';
    document.getElementById('master_spec_diferencial').value = specs['Diferencial'] || '';

    // Carregar custom specs (qualquer chave que não seja padrão nem color_prices)
    const stdValues = Object.values(STANDARD_SPEC_KEYS);
    Object.keys(specs).forEach(key => {
      if (!stdValues.includes(key) && key !== 'color_prices') {
        const val = specs[key];
        if (typeof val === 'string' || typeof val === 'number') {
          addMasterCustomSpecRow(key, val);
        }
      }
    });

    // Galeria
    let gallery = [];
    if (typeof product.images_gallery === 'string') {
      try { gallery = JSON.parse(product.images_gallery); } catch (e) { gallery = []; }
    } else if (Array.isArray(product.images_gallery)) {
      gallery = product.images_gallery;
    }
    document.getElementById('master_form_images_gallery').value = JSON.stringify(gallery);

    switchMasterTab('midia');
    if (typeof openModal === 'function') {
      openModal('masterProductModal');
    } else {
      const el = document.getElementById('masterProductModal');
      if (el) el.classList.add('show');
    }
  };

  /**
   * Serializa os dados da Ficha Técnica Ouro em JSON antes do submit
   */
  window.serializeMasterSpecsPayload = function () {
    const specs = {};

    const motor = document.getElementById('master_spec_motor')?.value.trim();
    const vel = document.getElementById('master_spec_velocidade')?.value.trim();
    const aut = document.getElementById('master_spec_autonomia')?.value.trim();
    const bat = document.getElementById('master_spec_bateria')?.value.trim();
    const carga = document.getElementById('master_spec_carga')?.value.trim();
    const freios = document.getElementById('master_spec_freios')?.value.trim();
    const dif = document.getElementById('master_spec_diferencial')?.value.trim();

    if (motor) specs['Motor'] = motor;
    if (vel) specs['Velocidade Máxima'] = vel;
    if (aut) specs['Autonomia'] = aut;
    if (bat) specs['Bateria'] = bat;
    if (carga) specs['Carga Máxima'] = carga;
    if (freios) specs['Freios'] = freios;
    if (dif) specs['Diferencial'] = dif;

    // Custom specs extras
    const customRows = document.querySelectorAll('#master_custom_specs_container .master-custom-spec-row');
    customRows.forEach(row => {
      const k = row.querySelector('.master-custom-k')?.value.trim();
      const v = row.querySelector('.master-custom-v')?.value.trim();
      if (k && v) {
        specs[k] = v;
      }
    });

    const hidden = document.getElementById('master_form_specs_json');
    if (hidden) {
      hidden.value = JSON.stringify(specs);
    }
  };

})();

