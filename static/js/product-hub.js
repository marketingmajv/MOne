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
    uploadingMain: false,
    uploadingBanner: false,
    form: {
      id: '',
      name: '',
      slug: '',
      sku: '',
      category: 'Bicicletas Elétricas',
      brand: 'MAJ',
      status: 'active',
      image_main: '',
      banner_widescreen: '',
      copy_atacado: '',
      copy_outlet: '',
      copy_showroom: '',
      sync_atacado: true,
      sync_outlet: true,
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
        sku: '',
        category: 'Bicicletas Elétricas',
        brand: 'MAJ',
        status: 'active',
        image_main: '',
        banner_widescreen: '',
        copy_atacado: '',
        copy_outlet: '',
        copy_showroom: '',
        sync_atacado: true,
        sync_outlet: true,
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
        sku: p.sku || '',
        category: p.category || 'Bicicletas Elétricas',
        brand: p.brand || 'MAJ',
        status: p.status || 'active',
        image_main: p.image_main || '',
        banner_widescreen: p.banner_widescreen || '',
        copy_atacado: p.copy_atacado || '',
        copy_outlet: p.copy_outlet || '',
        copy_showroom: p.copy_showroom || '',
        sync_atacado: p.sync_atacado !== false,
        sync_outlet: p.sync_outlet !== false,
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

    onNameInput() {
      if (!this.isEditing && this.form.name) {
        this.form.slug = this.form.name
          .toLowerCase()
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/[^\w\s-]/g, '')
          .replace(/[\s_-]+/g, '-')
          .replace(/^-+|-+$/g, '');
      }
    },

    async uploadImage(event, targetField) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      if (targetField === 'image_main') this.uploadingMain = true;
      if (targetField === 'banner_widescreen') this.uploadingBanner = true;

      try {
        const fd = new FormData();
        fd.append('gallery_files', file);
        const csrfInput = document.querySelector('#masterProductForm input[name="csrf_token"]');
        const headers = {};
        if (csrfInput && csrfInput.value) {
          headers['X-CSRFToken'] = csrfInput.value;
        }
        const resp = await fetch('/admin/central-produtos/api/upload-gallery', {
          method: 'POST',
          headers,
          body: fd
        });
        const data = await resp.json();
        if (data.success && Array.isArray(data.urls) && data.urls.length > 0) {
          this.form[targetField] = data.urls[0];
        } else {
          alert('Não foi possível fazer upload da imagem.');
        }
      } catch (err) {
        alert('Falha no upload da imagem: ' + err.message);
      } finally {
        if (targetField === 'image_main') this.uploadingMain = false;
        if (targetField === 'banner_widescreen') this.uploadingBanner = false;
        event.target.value = '';
      }
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
