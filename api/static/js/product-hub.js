/**
 * M-One Master Product Hub (static/js/product-hub.js)
 * Componente Alpine.js do Modal Central Mestre com <template x-teleport="body">.
 * Gestão de Identificação, Ficha Técnica Ouro e Copys contextuais.
 */

window.masterProductModalInstance = null;

function masterProductModalComponent() {
  const STANDARD_KEYS = [
    'Motor',
    'Velocidade Máxima',
    'Autonomia',
    'Bateria',
    'Carga Máxima',
    'Freios',
    'Diferencial'
  ];

  return {
    isOpen: false,
    activeTab: 'midia',
    isEditing: false,
    form: {
      id: '',
      name: '',
      slug: '',
      category: 'Bicicletas Elétricas',
      brand: 'MAJ',
      status: 'active',
      image_main: '',
      banner_widescreen: '',
      copy_atacado: '',
      copy_outlet: '',
      copy_showroom: '',
      propagate_now: true
    },
    specs: {
      'Motor': '',
      'Velocidade Máxima': '',
      'Autonomia': '',
      'Bateria': '',
      'Carga Máxima': '',
      'Freios': '',
      'Diferencial': ''
    },
    customSpecs: [],

    init() {
      window.masterProductModalInstance = this;
      window.openMasterProductNewModal = () => this.openCreate();
      window.openMasterProductEditModal = (id) => this.openEdit(id);
      window.closeMasterProductModal = () => this.close();
    },

    openCreate() {
      this.isEditing = false;
      this.activeTab = 'midia';
      this.form = {
        id: '',
        name: '',
        slug: '',
        category: 'Bicicletas Elétricas',
        brand: 'MAJ',
        status: 'active',
        image_main: '',
        banner_widescreen: '',
        copy_atacado: '',
        copy_outlet: '',
        copy_showroom: '',
        propagate_now: true
      };
      this.specs = {
        'Motor': '',
        'Velocidade Máxima': '',
        'Autonomia': '',
        'Bateria': '',
        'Carga Máxima': '',
        'Freios': '',
        'Diferencial': ''
      };
      this.customSpecs = [];
      this.isOpen = true;
    },

    openEdit(identifier) {
      const list = window.MASTER_PRODUCTS_LIST || [];
      const p = list.find(item => String(item.id) === String(identifier) || item.slug === String(identifier) || item.name === String(identifier));
      if (!p) {
        alert('Produto não encontrado na Central Mestre.');
        return;
      }

      this.isEditing = true;
      this.activeTab = 'midia';
      this.form = {
        id: p.id || '',
        name: p.name || '',
        slug: p.slug || '',
        category: p.category || 'Bicicletas Elétricas',
        brand: p.brand || 'MAJ',
        status: p.status || 'active',
        image_main: p.image_main || '',
        banner_widescreen: p.banner_widescreen || '',
        copy_atacado: p.copy_atacado || '',
        copy_outlet: p.copy_outlet || '',
        copy_showroom: p.copy_showroom || '',
        propagate_now: true
      };

      const sp = (typeof p.specs_json === 'object' && p.specs_json !== null) ? p.specs_json : {};
      this.specs = {
        'Motor': sp['Motor'] || '',
        'Velocidade Máxima': sp['Velocidade Máxima'] || '',
        'Autonomia': sp['Autonomia'] || '',
        'Bateria': sp['Bateria'] || '',
        'Carga Máxima': sp['Carga Máxima'] || '',
        'Freios': sp['Freios'] || '',
        'Diferencial': sp['Diferencial'] || ''
      };

      this.customSpecs = [];
      Object.keys(sp).forEach(k => {
        if (!STANDARD_KEYS.includes(k) && k !== 'color_prices') {
          const val = sp[k];
          if (typeof val === 'string' || typeof val === 'number') {
            this.customSpecs.push({ key: k, value: String(val) });
          }
        }
      });

      this.isOpen = true;
    },

    close() {
      this.isOpen = false;
    },

    addCustomSpec(k = '', v = '') {
      this.customSpecs.push({ key: k, value: v });
    },

    removeCustomSpec(idx) {
      this.customSpecs.splice(idx, 1);
    },

    submitForm(e) {
      const allSpecs = { ...this.specs };
      this.customSpecs.forEach(cs => {
        const k = (cs.key || '').trim();
        const v = (cs.value || '').trim();
        if (k && v) allSpecs[k] = v;
      });

      const hidden = document.getElementById('master_form_specs_json');
      if (hidden) hidden.value = JSON.stringify(allSpecs);
    }
  };
}

// Fallback global de inicialização imediata (caso o usuário clique antes de Alpine terminar init)
window.openMasterProductEditModal = function (id) {
  if (window.masterProductModalInstance) {
    window.masterProductModalInstance.openEdit(id);
  } else {
    setTimeout(() => {
      window.masterProductModalInstance?.openEdit(id);
    }, 100);
  }
};

window.openMasterProductNewModal = function () {
  if (window.masterProductModalInstance) {
    window.masterProductModalInstance.openCreate();
  } else {
    setTimeout(() => {
      window.masterProductModalInstance?.openCreate();
    }, 100);
  }
};

window.closeMasterProductModal = function () {
  window.masterProductModalInstance?.close();
};
