/**
 * M-One Atacado Admin — Modal 4 Abas (Alpine.js), Vínculo Canônico & Galeria Tradicional
 * Sincroniza dados comerciais B2B (/admin/atacado) com a Ficha Técnica Canônica (maj_models.json)
 * e exibe Modal de Confirmação de Sucesso pós-Preloader.
 * Segregação modular anti-monólito (< 500 linhas).
 */

window.atacadoModalInstance = null;

const ATACADO_TABS_ORDER = ['comercial', 'motor', 'estrutura', 'galeria'];

function slugifyAtacado(text) {
  return (text || '')
    .toString()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function formatBrlCurrency(val) {
  const num = parseFloat(val);
  if (isNaN(num) || num <= 0) return 'Sob consulta';
  return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function defaultAtacadoForm() {
  return {
    id: '',
    slug: '',
    name: '',
    category: 'Scooter Elétrica',
    price_outlet: '',
    price_atacado_plus: '',
    stock_qty: 1,
    color: '',
    badge: '',
    show_on_demand: false,
    is_best_seller: false,
    potencia_nominal_w: '1000W',
    velocidade_max_kmh: '32 km/h',
    modos_conducao: '3 níveis',
    possui_re: 'Sim',
    voltagem_v: '60V',
    capacidade_ah: '20Ah',
    capacidade_wh: '1200Wh',
    quimica_bateria: 'LiFePO₄ (LFP)',
    autonomia_conservadora_km: '35 km',
    autonomia_maxima_km: '50 km',
    freios: 'Diant: Hidráulico / Tras: Hidráulico',
    suspensao: 'Dupla dianteira e traseira',
    aro_pneu: 'Aro 10/12 tubeless',
    carga_maxima_kg: '180 kg',
    peso_kg: '75 kg',
    description: '',
    notes: '',
  };
}

function atacadoModelModal() {
  return {
    isOpen: false,
    isEditing: false,
    saving: false,
    activeTab: 'comercial',
    canonicalLinked: false,
    canonicalSlug: '',
    form: defaultAtacadoForm(),
    imageMain: '',
    gallery: [],
    newPhotoUrl: '',
    uploadStatus: '',
    uploadError: false,
    processingUpload: false,
    feedbackModal: {
      open: false,
      success: true,
      title: 'Produto Atacado Salvo com Sucesso!',
      subtitle: 'Catálogo B2B (CNPJ) e Ficha Técnica Canônica sincronizados.',
      modelName: '',
      priceAndStock: '',
      canonicalSlug: '',
      galleryCount: 0,
      errorMsg: '',
    },

    init() {
      window.atacadoModalInstance = this;
      window.addEventListener('open-atacado-create', () => this.openCreate());
      window.addEventListener('open-atacado-edit', (e) => this.openEdit(e.detail));
    },

    openCreate() {
      this.isEditing = false;
      this.saving = false;
      this.activeTab = 'comercial';
      this.canonicalLinked = false;
      this.canonicalSlug = '';
      this.form = defaultAtacadoForm();
      this.imageMain = '';
      this.gallery = [];
      this.newPhotoUrl = '';
      this.uploadStatus = '';
      this.uploadError = false;
      this.processingUpload = false;
      this.feedbackModal.open = false;
      this.isOpen = true;
    },

    async openEdit(itemOrId) {
      let item = itemOrId;
      if (typeof itemOrId === 'number' || typeof itemOrId === 'string') {
        const list = window.ATACADO_ITEMS_LIST || [];
        item = list.find((i) => String(i.id) === String(itemOrId)) || {};
      }

      this.isEditing = true;
      this.saving = false;
      this.activeTab = 'comercial';
      this.uploadStatus = '';
      this.uploadError = false;
      this.processingUpload = false;
      this.newPhotoUrl = '';
      this.feedbackModal.open = false;

      const cSpecs = item.canonical_specs || {};
      const sJson = (item.specs_json && typeof item.specs_json === 'object') ? item.specs_json : {};

      let resolvedCat = item.category || item.category_display || 'Scooter Elétrica';
      if (resolvedCat === 'Atacado CNPJ' && item.category_display) {
        resolvedCat = item.category_display;
      }

      this.canonicalSlug = cSpecs.canonical_slug || item.slug || slugifyAtacado(item.name || '');
      this.canonicalLinked = Boolean(cSpecs.has_canonical);

      this.form = {
        id: item.id || '',
        slug: item.slug || this.canonicalSlug,
        name: item.name || '',
        category: resolvedCat,
        price_outlet: item.price_outlet !== undefined && item.price_outlet !== null ? item.price_outlet : '',
        price_atacado_plus: item.price_atacado_plus !== undefined && item.price_atacado_plus !== null ? item.price_atacado_plus : '',
        stock_qty: item.stock_qty !== undefined && item.stock_qty !== null ? item.stock_qty : 0,
        color: item.color || '',
        badge: item.differentiator || item.badge || '',
        show_on_demand: Boolean(item.show_on_demand),
        is_best_seller: Boolean(item.is_best_seller),
        potencia_nominal_w: cSpecs.potencia_nominal_w || sJson['Potência Nominal'] || '1000W',
        velocidade_max_kmh: cSpecs.velocidade_max_kmh || sJson['Velocidade Máxima'] || '32 km/h',
        modos_conducao: cSpecs.modos_conducao || sJson['Modos de Condução'] || '3 níveis',
        possui_re: cSpecs.possui_re || sJson['Marcha a Ré'] || 'Sim',
        voltagem_v: cSpecs.voltagem_v || sJson['Voltagem'] || '60V',
        capacidade_ah: cSpecs.capacidade_ah || sJson['Capacidade (Ah)'] || '20Ah',
        capacidade_wh: cSpecs.capacidade_wh || sJson['Capacidade (Wh)'] || '1200Wh',
        quimica_bateria: cSpecs.quimica_bateria || sJson['Química da Bateria'] || 'LiFePO₄ (LFP)',
        autonomia_conservadora_km: cSpecs.autonomia_conservadora_km || sJson['Autonomia Conservadora'] || '35 km',
        autonomia_maxima_km: cSpecs.autonomia_maxima_km || sJson['Autonomia Máxima'] || '50 km',
        freios: cSpecs.freios || sJson['Sistema de Freios'] || 'Diant: Hidráulico / Tras: Hidráulico',
        suspensao: cSpecs.suspensao || sJson['Suspensão'] || 'Dupla dianteira e traseira',
        aro_pneu: cSpecs.aro_pneu || sJson['Aro / Pneu'] || 'Aro 10/12 tubeless',
        carga_maxima_kg: cSpecs.carga_maxima_kg || sJson['Carga Máxima'] || '180 kg',
        peso_kg: cSpecs.peso_kg || sJson['Peso do Veículo'] || '75 kg',
        description: item.description || cSpecs.descricao_livre || '',
        notes: item.notes || '',
      };

      let gal = item.images_gallery || [];
      if (typeof gal === 'string') {
        try { gal = JSON.parse(gal); } catch (e) { gal = []; }
      }
      this.gallery = Array.isArray(gal) ? [...gal] : [];
      this.imageMain = item.image_main || (this.gallery.length > 0 ? this.gallery[0] : '');
      if (this.imageMain && !this.gallery.includes(this.imageMain)) {
        this.gallery.unshift(this.imageMain);
      }

      this.isOpen = true;

      if (!cSpecs.canonical_slug && (this.form.slug || this.form.name)) {
        await this.fetchCanonicalSpecs(false);
      }
    },

    close() {
      if (this.processingUpload || this.saving) return;
      this.isOpen = false;
    },

    nextTab() {
      const idx = ATACADO_TABS_ORDER.indexOf(this.activeTab);
      if (idx >= 0 && idx < ATACADO_TABS_ORDER.length - 1) {
        this.activeTab = ATACADO_TABS_ORDER[idx + 1];
      }
    },

    prevTab() {
      const idx = ATACADO_TABS_ORDER.indexOf(this.activeTab);
      if (idx > 0) {
        this.activeTab = ATACADO_TABS_ORDER[idx - 1];
      }
    },

    onNameChange() {
      if (!this.isEditing) {
        this.form.slug = slugifyAtacado(this.form.name);
      }
    },

    calcWh() {
      const vMatch = String(this.form.voltagem_v || '').match(/\d+/);
      const ahMatch = String(this.form.capacidade_ah || '').match(/\d+/);
      if (vMatch && ahMatch) {
        const v = parseInt(vMatch[0], 10);
        const ah = parseInt(ahMatch[0], 10);
        if (v > 0 && ah > 0) {
          this.form.capacidade_wh = `${v * ah}Wh`;
        }
      }
    },

    async fetchCanonicalSpecs(forceOverwrite = false) {
      const lookup = slugifyAtacado(this.form.slug || this.form.name);
      if (!lookup) return;
      try {
        const url = `/admin/atacado/canonical-specs/${encodeURIComponent(lookup)}?name=${encodeURIComponent(this.form.name || '')}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        const cs = data.canonical_specs;
        if (!cs) return;

        this.canonicalSlug = cs.canonical_slug || lookup;
        this.canonicalLinked = Boolean(cs.has_canonical);

        const techKeys = [
          'potencia_nominal_w', 'velocidade_max_kmh', 'modos_conducao', 'possui_re',
          'voltagem_v', 'capacidade_ah', 'capacidade_wh', 'quimica_bateria',
          'autonomia_conservadora_km', 'autonomia_maxima_km',
          'freios', 'suspensao', 'aro_pneu', 'carga_maxima_kg', 'peso_kg',
        ];
        techKeys.forEach((k) => {
          if (cs[k] && (forceOverwrite || !this.form[k])) {
            this.form[k] = cs[k];
          }
        });
        if (forceOverwrite && cs.diferencial && !this.form.badge) {
          this.form.badge = cs.diferencial;
        }
        if (forceOverwrite && cs.descricao_livre && !this.form.description) {
          this.form.description = cs.descricao_livre;
        }
      } catch (err) {
        console.warn('Aviso ao buscar ficha canônica:', err);
      }
    },

    setCoverPhoto(index) {
      if (this.gallery[index]) {
        this.imageMain = this.gallery[index];
        this.uploadError = false;
        this.uploadStatus = '⭐ Foto principal de capa atualizada!';
      }
    },

    removePhoto(index) {
      const removed = this.gallery.splice(index, 1)[0];
      if (this.imageMain === removed) {
        this.imageMain = this.gallery.length > 0 ? this.gallery[0] : '';
      }
      this.uploadError = false;
      this.uploadStatus = this.gallery.length > 0 ? `✅ ${this.gallery.length} foto(s) na galeria.` : '';
    },

    addPhotoByUrl() {
      const url = (this.newPhotoUrl || '').trim();
      if (!url) return;
      if (!this.gallery.includes(url)) {
        this.gallery.unshift(url);
      }
      this.imageMain = url;
      this.newPhotoUrl = '';
      this.uploadError = false;
      this.uploadStatus = `✅ Foto adicionada e definida como Capa (${this.gallery.length} foto(s)).`;
    },

    handleGalleryUpload(event) {
      const input = event.target;
      const files = input?.files;
      if (!files || files.length === 0) return;

      if (this.gallery.length >= 12) {
        this.uploadError = true;
        this.uploadStatus = '⚠️ Limite máximo de 12 fotos por produto atingido.';
        input.value = '';
        return;
      }

      this.processingUpload = true;
      this.uploadError = false;
      this.uploadStatus = `⏳ Otimizando e comprimindo ${files.length} foto(s)...`;

      let processedCount = 0;
      let firstUploadedCover = null;
      const availableSlots = 12 - this.gallery.length;
      const totalFiles = Math.min(files.length, availableSlots);

      Array.from(files).slice(0, totalFiles).forEach((file, fileIdx) => {
        compressAtacadoImage(file, 640, 0.52, (base64Data) => {
          if (base64Data && !this.gallery.includes(base64Data)) {
            if (fileIdx === 0) {
              this.gallery.unshift(base64Data);
              firstUploadedCover = base64Data;
            } else {
              this.gallery.push(base64Data);
            }
          }
          processedCount++;
          if (processedCount === totalFiles) {
            if (firstUploadedCover) {
              this.imageMain = firstUploadedCover;
            } else if (!this.imageMain && this.gallery.length > 0) {
              this.imageMain = this.gallery[0];
            }
            this.processingUpload = false;
            const totalChars = (this.imageMain || '').length + JSON.stringify(this.gallery).length;
            const totalMb = ((totalChars * 3) / 4) / (1024 * 1024);
            this.uploadError = false;
            this.uploadStatus = `✅ ${this.gallery.length} foto(s) pronta(s) (~${totalMb.toFixed(2)} MB) • Nova foto definida como Capa!`;
            input.value = '';
          }
        });
      });
    },

    async handleFormSubmit(event) {
      if (this.saving || this.processingUpload) return false;

      if (!this.form.name || !String(this.form.name).trim()) {
        this.activeTab = 'comercial';
        alert('Por favor, preencha o Nome do Modelo na Aba 1.');
        return false;
      }

      const mainStr = this.imageMain || '';
      const galStr = JSON.stringify(this.gallery || []);
      const sizeMb = (((mainStr.length + galStr.length) * 3) / 4) / (1024 * 1024);

      if (sizeMb > 3.8) {
        this.activeTab = 'galeria';
        this.uploadError = true;
        this.uploadStatus = `⚠️ Tamanho total da galeria (${sizeMb.toFixed(1)} MB) excede o limite de envio (3.8 MB). Remova 1 ou 2 fotos.`;
        alert(this.uploadStatus);
        return false;
      }

      const formEl = event.target;
      const fd = new FormData(formEl);
      fd.set('image_main', this.imageMain || '');
      fd.set('images_gallery', JSON.stringify(this.gallery || []));
      if (this.form.show_on_demand) {
        fd.set('show_on_demand', '1');
      } else {
        fd.delete('show_on_demand');
      }
      if (this.form.is_best_seller) {
        fd.set('is_best_seller', '1');
      } else {
        fd.delete('is_best_seller');
      }

      const modelLabel = (this.form.name || 'Produto').trim();
      this.saving = true;
      this.isOpen = false;

      if (window.MOnePreloader && typeof window.MOnePreloader.show === 'function') {
        window.MOnePreloader.show(`Salvando ${modelLabel} e sincronizando Ficha Canônica...`, 'MAJ ATACADO', true);
      }

      try {
        const minPreloaderWait = new Promise((resolve) => setTimeout(resolve, 700));
        const saveReq = fetch(formEl.action, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: fd,
        });

        const [res] = await Promise.all([saveReq, minPreloaderWait]);
        const data = await res.json().catch(() => ({}));

        if (window.MOnePreloader && typeof window.MOnePreloader.hide === 'function') {
          window.MOnePreloader.hide();
        }

        if (!res.ok || data.success === false) {
          throw new Error(data.error || 'Não foi possível salvar as alterações do produto.');
        }

        this.feedbackModal = {
          open: true,
          success: true,
          title: 'Produto Atacado Salvo com Sucesso!',
          subtitle: 'Catálogo B2B (CNPJ) e Ficha Técnica Canônica sincronizados.',
          modelName: modelLabel,
          priceAndStock: `${formatBrlCurrency(this.form.price_outlet)} • ${this.form.stock_qty || 0} un`,
          canonicalSlug: this.canonicalSlug || this.form.slug || slugifyAtacado(modelLabel),
          galleryCount: (this.gallery || []).length,
          errorMsg: '',
        };
      } catch (err) {
        if (window.MOnePreloader && typeof window.MOnePreloader.hide === 'function') {
          window.MOnePreloader.hide();
        }
        this.feedbackModal = {
          open: true,
          success: false,
          title: 'Falha ao Salvar Produto',
          subtitle: 'Verifique os dados informados e tente novamente.',
          modelName: modelLabel,
          priceAndStock: '',
          canonicalSlug: '',
          galleryCount: 0,
          errorMsg: err.message || 'Erro inesperado ao salvar.',
        };
      } finally {
        this.saving = false;
      }
      return false;
    },

    confirmFeedbackModal() {
      const wasSuccess = this.feedbackModal.success;
      this.feedbackModal.open = false;
      if (wasSuccess) {
        if (window.MOnePreloader && typeof window.MOnePreloader.reload === 'function') {
          window.MOnePreloader.reload('Atualizando catálogo B2B...', 'MAJ ATACADO');
        } else {
          window.location.reload();
        }
      } else {
        this.isOpen = true;
      }
    },
  };
}

function compressAtacadoImage(file, maxWidth, quality, callback) {
  const reader = new FileReader();
  reader.onload = function (e) {
    const img = new Image();
    img.onload = function () {
      let width = img.width;
      let height = img.height;
      if (width > maxWidth) {
        height = Math.round((height * maxWidth) / width);
        width = maxWidth;
      }
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, width, height);
      callback(canvas.toDataURL('image/jpeg', quality));
    };
    img.onerror = function () { callback(null); };
    img.src = e.target.result;
  };
  reader.onerror = function () { callback(null); };
  reader.readAsDataURL(file);
}

// Gatilhos globais para os botões da tabela em templates/atacado/admin.html
window.openAtacadoModal = function () {
  if (window.atacadoModalInstance) {
    window.atacadoModalInstance.openCreate();
  } else {
    window.dispatchEvent(new CustomEvent('open-atacado-create'));
  }
};

window.editAtacadoItem = function (itemOrId) {
  if (window.atacadoModalInstance) {
    window.atacadoModalInstance.openEdit(itemOrId);
  } else {
    window.dispatchEvent(new CustomEvent('open-atacado-edit', { detail: itemOrId }));
  }
};

window.closeAtacadoModal = function () {
  if (window.atacadoModalInstance) {
    window.atacadoModalInstance.close();
  }
};
