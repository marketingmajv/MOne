/**
 * M-One Product Hub AI Modals (static/js/product-hub-ai.js)
 * Componentes Alpine.js para detecção com IA e fontes de planilhas.
 * Anti-monólito modular (< 500 linhas).
 */

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
            'X-CSRFToken': (typeof getCsrfToken === 'function') ? getCsrfToken() : ''
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
            'X-CSRFToken': (typeof getCsrfToken === 'function') ? getCsrfToken() : ''
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

window.triggerAiProductDetection = function (customSources = []) {
  if (window.newProductAiModalInstance) {
    window.newProductAiModalInstance.scan(customSources);
  } else {
    setTimeout(() => {
      window.newProductAiModalInstance?.scan(customSources);
    }, 150);
  }
};
