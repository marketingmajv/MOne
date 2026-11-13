/**
 * M-One Master Product Hub (static/js/product-hub.js)
 * Componentes Alpine.js para Central de Produtos Mestre,
 * Detecção de Novos Produtos com IA e Atualização Contínua via Planilhas.
 */

window.masterProductModalInstance = null;
window.newProductAiModalInstance = null;
window.productSourcesModalInstance = null;

function getCsrfToken() {
  const input = document.querySelector('input[name="csrf_token"]');
  return input ? input.value : '';
}

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
    isSyncingAi: false,
    aiUpdateNotice: false,
    aiDiffSummary: [],
    highlightedFields: {},
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
      this.aiUpdateNotice = false;
      this.aiDiffSummary = [];
      this.highlightedFields = {};
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
      this.aiUpdateNotice = false;
      this.aiDiffSummary = [];
      this.highlightedFields = {};
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

    async syncCurrentProductWithAi() {
      if (!this.form.id && !this.form.slug) return;
      this.isSyncingAi = true;
      this.aiUpdateNotice = false;
      this.aiDiffSummary = [];
      this.highlightedFields = {};

      try {
        const resp = await fetch('/admin/central-produtos/ai/sync-from-sheets', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({
            product_id: this.form.id,
            slug: this.form.slug
          })
        });

        const data = await resp.json();
        if (!data.success) {
          alert(data.error || 'Não foi possível analisar atualizações deste produto.');
          return;
        }

        if (!data.has_updates) {
          alert('✅ A ficha técnica deste modelo já está totalmente atualizada com os dados das planilhas.');
          return;
        }

        const uf = data.updated_fields || {};
        if (uf.category) {
          this.form.category = uf.category;
          this.highlightedFields['category'] = true;
        }
        if (uf.copy_showroom) {
          this.form.copy_showroom = uf.copy_showroom;
          this.highlightedFields['copy_showroom'] = true;
        }
        if (uf.copy_atacado) {
          this.form.copy_atacado = uf.copy_atacado;
          this.highlightedFields['copy_atacado'] = true;
        }
        if (uf.copy_outlet) {
          this.form.copy_outlet = uf.copy_outlet;
          this.highlightedFields['copy_outlet'] = true;
        }

        if (uf.specs && typeof uf.specs === 'object') {
          Object.keys(uf.specs).forEach(sk => {
            const val = uf.specs[sk];
            if (STANDARD_KEYS.includes(sk)) {
              this.specs[sk] = val;
              this.highlightedFields['specs_' + sk] = true;
            } else {
              const existing = this.customSpecs.find(c => c.key === sk);
              if (existing) {
                existing.value = val;
              } else {
                this.customSpecs.push({ key: sk, value: val });
              }
              this.highlightedFields['specs_' + sk] = true;
            }
          });
        }

        this.aiDiffSummary = data.diff_summary || [];
        this.aiUpdateNotice = true;
        this.activeTab = 'specs'; // Leva o usuário para revisar a ficha
      } catch (err) {
        alert('Falha na comunicação com a IA: ' + err.message);
      } finally {
        this.isSyncingAi = false;
      }
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
        const resp = await fetch('/admin/central-produtos/api/upload-gallery', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
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

function newProductAiModalComponent() {
  return {
    isOpen: false,
    isScanning: false,
    isApproving: false,
    detectedList: [],
    currentIndex: 0,
    activeTab: 'specs',
    syncAtacado: true,
    syncOutlet: true,

    get currentProduct() {
      return this.detectedList[this.currentIndex] || null;
    },

    init() {
      window.newProductAiModalInstance = this;
      window.triggerAiProductDetection = (customSources = []) => this.scan(customSources);
    },

    close() {
      this.isOpen = false;
    },

    prevProduct() {
      if (this.currentIndex > 0) this.currentIndex--;
    },

    nextProduct() {
      if (this.currentIndex < this.detectedList.length - 1) this.currentIndex++;
    },

    async scan(customSources = []) {
      this.isOpen = true;
      this.isScanning = true;
      this.detectedList = [];
      this.currentIndex = 0;
      this.activeTab = 'specs';

      try {
        const resp = await fetch('/admin/central-produtos/ai/detect', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ custom_sources: customSources })
        });
        const data = await resp.json();
        if (data.success) {
          this.detectedList = data.detected || [];
        } else {
          alert('Erro na varredura: ' + (data.error || 'Falha desconhecida'));
        }
      } catch (err) {
        alert('Falha ao conectar com o motor de IA: ' + err.message);
      } finally {
        this.isScanning = false;
      }
    },

    async approveCurrentProduct() {
      const prod = this.currentProduct;
      if (!prod) return;

      this.isApproving = true;
      try {
        const payload = {
          name: prod.name,
          slug: prod.slug,
          category: prod.category,
          brand: prod.brand || 'MAJ',
          sku: prod.sku || '',
          status: 'inactive',
          specs: prod.specs || {},
          copy_showroom: prod.copy_showroom || '',
          copy_atacado: prod.copy_atacado || '',
          copy_outlet: prod.copy_outlet || '',
          notes: prod.notes || '',
          image_main: prod.image_main || '',
          banner_widescreen: prod.banner_widescreen || '',
          gallery: prod.gallery || [],
          sync_atacado: this.syncAtacado,
          sync_outlet: this.syncOutlet
        };

        const resp = await fetch('/admin/central-produtos/ai/approve-new', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify(payload)
        });

        const data = await resp.json();
        if (data.success) {
          alert(`🎉 Produto '${prod.name}' cadastrado com sucesso na Central Mestre!`);
          this.detectedList.splice(this.currentIndex, 1);
          if (this.detectedList.length === 0) {
            this.close();
            window.location.reload();
          } else if (this.currentIndex >= this.detectedList.length) {
            this.currentIndex = this.detectedList.length - 1;
          }
        } else {
          alert('Erro ao cadastrar produto: ' + (data.error || 'Falha no banco de dados.'));
        }
      } catch (err) {
        alert('Erro ao aprovar produto: ' + err.message);
      } finally {
        this.isApproving = false;
      }
    }
  };
}

function productSourcesModalComponent() {
  return {
    isOpen: false,
    sources: [],
    customUrl: '',

    init() {
      window.productSourcesModalInstance = this;
      window.openProductSourcesModal = () => this.open();
    },

    async open() {
      this.isOpen = true;
      try {
        const resp = await fetch('/admin/central-produtos/ai/sources');
        const data = await resp.json();
        if (data.success) {
          this.sources = data.sources || [];
        }
      } catch (err) {
        console.error('Falha ao listar fontes:', err);
      }
    },

    close() {
      this.isOpen = false;
    },

    scanWithCustomUrl() {
      const url = (this.customUrl || '').trim();
      if (!url) {
        alert('Por favor, informe a URL da planilha Google Sheets.');
        return;
      }
      this.close();
      if (window.newProductAiModalInstance) {
        window.newProductAiModalInstance.scan([url]);
      }
    }
  };
}

// Fallback global de inicialização imediata
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

window.triggerAiProductDetection = function (customSources = []) {
  if (window.newProductAiModalInstance) {
    window.newProductAiModalInstance.scan(customSources);
  } else {
    setTimeout(() => {
      window.newProductAiModalInstance?.scan(customSources);
    }, 150);
  }
};
