/**
 * M-One Showroom Model Form Modal (static/js/showroom-model-modal.js)
 * Gerenciador interativo com Banners Panorâmicos Widescreen 16:9 de Estúdio
 * (Atemporal vs Promocional) e persistência soberana híbrida.
 */

window.showroomModelModalInstance = null;

function showroomModelModal() {
  return {
    isOpen: false,
    activeTab: 'identificacao',
    isEditing: false,
    saving: false,
    bannerAtemporalFile: null,
    previewBannerAtemporal: null,
    bannerPromoFile: null,
    previewBannerPromo: null,
    form: {
      modelo: '',
      categoria: 'Scooter',
      slug: '',
      marca: 'MAJ',
      versao_ano: '2026',
      codigo_interno: '',
      is_active: true,
      banner_image: '',
      promo_banner_image: '',
      active_banner_type: 'atemporal',
      potencia_nominal_w: '1000',
      velocidade_max_kmh: '32',
      modos_conducao: '3 níveis',
      possui_re: 'Sim',
      voltagem_v: '60v',
      capacidade_ah: '20ah',
      capacidade_wh: '1200Wh',
      autonomia_conservadora_km: '35km',
      autonomia_maxima_km: '50',
      quimica_bateria: 'LiFePO₄ (LFP)',
      carga_maxima_kg: '180',
      peso_kg: '75',
      freios: 'Diant: Hidráulico / Tras: Hidráulico',
      suspensao: 'Dupla dianteira e traseira',
      aro_pneu: 'Aro 12 tubeless',
      diferencial: '',
      pontos_fortes: '',
      descricao_livre: '',
    },

    init() {
      window.showroomModelModalInstance = this;
      window.addEventListener('open-showroom-create', () => this.openCreate());
      window.addEventListener('open-showroom-edit', (e) => this.openEdit(e.detail?.slug));
    },

    openCreate() {
      this.isEditing = false;
      this.activeTab = 'identificacao';
      this.bannerAtemporalFile = null;
      this.previewBannerAtemporal = null;
      this.bannerPromoFile = null;
      this.previewBannerPromo = null;
      this.form = {
        modelo: '',
        categoria: 'Scooter',
        slug: '',
        marca: 'MAJ',
        versao_ano: '2026',
        codigo_interno: '',
        is_active: true,
        banner_image: '',
        promo_banner_image: '',
        active_banner_type: 'atemporal',
        potencia_nominal_w: '1000',
        velocidade_max_kmh: '32',
        modos_conducao: '3 níveis',
        possui_re: 'Sim',
        voltagem_v: '60v',
        capacidade_ah: '20ah',
        capacidade_wh: '1200Wh',
        autonomia_conservadora_km: '',
        autonomia_maxima_km: '',
        quimica_bateria: 'LiFePO₄ (LFP)',
        carga_maxima_kg: '180',
        peso_kg: '75',
        freios: 'Diant: Hidráulico / Tras: Hidráulico',
        suspensao: 'Dupla dianteira e traseira',
        aro_pneu: 'Aro 12 tubeless',
        diferencial: '',
        pontos_fortes: '',
        descricao_livre: '',
      };
      this.isOpen = true;
    },

    async openEdit(slug) {
      if (!slug) return;
      this.isEditing = true;
      this.activeTab = 'identificacao';
      this.bannerAtemporalFile = null;
      this.previewBannerAtemporal = null;
      this.bannerPromoFile = null;
      this.previewBannerPromo = null;

      try {
        const res = await fetch(`/api/models/${encodeURIComponent(slug)}/full`);
        if (!res.ok) throw new Error('Não foi possível carregar os dados do modelo.');
        const data = await res.json();
        this.form = Object.assign({}, this.form, data);
        this.previewBannerAtemporal = data.banner_image || null;
        this.previewBannerPromo = data.promo_banner_image || null;
        this.form.active_banner_type = data.active_banner_type || 'atemporal';
        this.isOpen = true;
      } catch (err) {
        alert('Erro ao carregar modelo: ' + err.message);
      }
    },

    close() {
      if (this.saving) return;
      this.isOpen = false;
      this.bannerAtemporalFile = null;
      this.previewBannerAtemporal = null;
      this.bannerPromoFile = null;
      this.previewBannerPromo = null;
    },

    onNameInput() {
      if (!this.isEditing) {
        const clean = (this.form.modelo || '')
          .toLowerCase()
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g, '')
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-+|-+$/g, '');
        this.form.slug = clean;
      }
    },

    calcWh() {
      const vMatch = (this.form.voltagem_v || '').match(/\d+/);
      const ahMatch = (this.form.capacidade_ah || '').match(/\d+/);
      if (vMatch && ahMatch) {
        const v = parseInt(vMatch[0], 10);
        const ah = parseInt(ahMatch[0], 10);
        if (v > 0 && ah > 0) {
          this.form.capacidade_wh = `${v * ah}Wh`;
        }
      }
    },

    onBannerAtemporalSelected(event) {
      const file = event.target.files?.[0];
      if (!file) return;
      this.bannerAtemporalFile = file;
      this.form.active_banner_type = 'atemporal';

      const reader = new FileReader();
      reader.onload = (e) => {
        this.previewBannerAtemporal = e.target.result;
      };
      reader.readAsDataURL(file);
    },

    onBannerPromoSelected(event) {
      const file = event.target.files?.[0];
      if (!file) return;
      this.bannerPromoFile = file;
      this.form.active_banner_type = 'promocional';

      const reader = new FileReader();
      reader.onload = (e) => {
        this.previewBannerPromo = e.target.result;
      };
      reader.readAsDataURL(file);
    },

    async submitForm() {
      if (!this.form.modelo || !this.form.modelo.trim()) {
        alert('Por favor, informe o nome do modelo.');
        this.activeTab = 'identificacao';
        return;
      }

      this.saving = true;
      if (window.MOnePreloader) {
        window.MOnePreloader.show('Salvando modelo e otimizando banners (16:9)...', 'SHOWROOM MAJ', true);
      }
      try {
        const fd = new FormData();
        Object.keys(this.form).forEach((k) => {
          fd.append(k, this.form[k] !== undefined && this.form[k] !== null ? this.form[k] : '');
        });

        if (this.bannerAtemporalFile) {
          fd.append('banner_atemporal', this.bannerAtemporalFile);
        }
        if (this.bannerPromoFile) {
          fd.append('banner_promocional', this.bannerPromoFile);
        }

        const res = await fetch('/api/models/save', {
          method: 'POST',
          body: fd,
        });

        const json = await res.json();
        if (!res.ok) {
          throw new Error(json.error || 'Erro ao salvar modelo.');
        }

        this.isOpen = false;
        window.location.reload();
      } catch (err) {
        if (window.MOnePreloader) window.MOnePreloader.hide();
        alert('Falha ao salvar: ' + err.message);
      } finally {
        this.saving = false;
      }
    },
  };
}

// Funções de gatilho para os botões do HTML
function openCreateModelModal() {
  if (window.showroomModelModalInstance) {
    window.showroomModelModalInstance.openCreate();
  } else {
    window.dispatchEvent(new CustomEvent('open-showroom-create'));
  }
}

function openEditModelModal(slug) {
  if (window.showroomModelModalInstance) {
    window.showroomModelModalInstance.openEdit(slug);
  } else {
    window.dispatchEvent(new CustomEvent('open-showroom-edit', { detail: { slug } }));
  }
}
