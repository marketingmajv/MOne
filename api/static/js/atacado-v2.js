function atacadoV2App() {
  const serverItems = (typeof window !== "undefined" && window.V2_ITEMS_DATA) ? window.V2_ITEMS_DATA : [];
  const serverWaNumber = (typeof window !== "undefined" && window.V2_WA_NUMBER) ? window.V2_WA_NUMBER : "5527996051538";
  return {
    items: serverItems,
    waNumber: serverWaNumber,
    searchQuery: "",
    selectedTrack: "all",
    
    // Modal
    modalOpen: false,
    selectedItem: null,
    activeImage: "",

    // Montador de Lote Misto (Armazenado localmente)
    lot: {},

    init() {
      // Carregar lote salvo no LocalStorage
      try {
        const savedLot = localStorage.getItem("maj_atacado_v2_lot");
        if (savedLot) {
          this.lot = JSON.parse(savedLot);
        }
      } catch (e) {
        console.warn("Erro ao restaurar lote salvo:", e);
        this.lot = {};
      }

      // Suporte a abertura direta de modal via URL (?modal=slug ou ?modelo=slug)
      const urlParams = new URLSearchParams(window.location.search);
      const targetModal = urlParams.get("modal") || urlParams.get("modelo");
      if (targetModal) {
        setTimeout(() => this.openModal(targetModal), 60);
      }
    },

    saveLot() {
      try {
        localStorage.setItem("maj_atacado_v2_lot", JSON.stringify(this.lot));
      } catch (e) {
        console.warn("Erro ao persistir lote:", e);
      }
    },

    // Controle de Quantidade no Card
    getQty(itemId) {
      return this.lot[itemId] ? this.lot[itemId].qty : 0;
    },

    setQty(item, newQty) {
      const qty = parseInt(newQty, 10);
      if (isNaN(qty) || qty <= 0) {
        delete this.lot[item.id];
      } else {
        this.lot[item.id] = {
          id: item.id,
          name: item.name,
          slug: item.slug,
          price_outlet: parseFloat(item.price_outlet) || 0,
          price_original: parseFloat(item.price_retail_suggested || item.price_original) || 0,
          margin_reais: parseFloat(item.margin_reais) || 0,
          has_trunk: !!item.has_trunk,
          qty: qty
        };
      }
      this.saveLot();
    },

    incrementQty(item) {
      const current = this.getQty(item.id);
      this.setQty(item, current + 1);
    },

    decrementQty(item) {
      const current = this.getQty(item.id);
      if (current > 0) {
        this.setQty(item, current - 1);
      }
    },

    addDirect(item) {
      const current = this.getQty(item.id);
      this.setQty(item, current > 0 ? current + 1 : 1);
    },

    clearLot() {
      if (confirm("Deseja realmente limpar todos os itens do seu lote de atacado?")) {
        this.lot = {};
        this.saveLot();
      }
    },

    // Regra de Desconto Escalonado por Volume Global do Lote
    getActiveTier() {
      const total = this.getTotalVehicles();
      if (total >= 21) return 3; // Acima de 20 un (-R$ 200/un)
      if (total >= 11) return 2; // De 11 a 20 un (-R$ 100/un)
      return 1; // Até 10 un (Preço Base Coluna B)
    },

    getUnitDiscount() {
      const tier = this.getActiveTier();
      if (tier === 3) return 200.00;
      if (tier === 2) return 100.00;
      return 0.00;
    },

    getItemCurrentPrice(item) {
      if (!item) return 0;
      const base = parseFloat(item.price_outlet) || 0;
      const discount = this.getUnitDiscount();
      return Math.max(0, base - discount);
    },

    getItemCurrentMarginReais(item) {
      if (!item) return 0;
      const currentPrice = this.getItemCurrentPrice(item);
      const retail = parseFloat(item.price_retail_suggested || item.price_original) || (currentPrice * 1.35);
      return Math.max(0, retail - currentPrice);
    },

    getItemCurrentMarginPct(item) {
      if (!item) return 0;
      const currentPrice = this.getItemCurrentPrice(item);
      if (currentPrice <= 0) return 0;
      const marginReais = this.getItemCurrentMarginReais(item);
      return Math.round((marginReais / currentPrice) * 100);
    },

    getTotalVolumeSavings() {
      return this.getTotalVehicles() * this.getUnitDiscount();
    },

    getNextTierIncentive() {
      const total = this.getTotalVehicles();
      if (total === 0) {
        return "Monte seu lote misto a partir de 3 unidades";
      }
      if (total <= 10) {
        const needed = 11 - total;
        return `Adicione mais ${needed} ${needed === 1 ? 'veículo' : 'veículos'} no lote para liberar -R$ 100,00/un em todos os modelos!`;
      }
      if (total <= 20) {
        const needed = 21 - total;
        return `🔥 Desconto de -R$ 100/un ativo! Faltam apenas ${needed} ${needed === 1 ? 'veículo' : 'veículos'} para o desconto máximo de -R$ 200,00/un!`;
      }
      return "🚀 DESCONTO MÁXIMO ATIVO: -R$ 200,00 por veículo em todo o lote!";
    },

    // Cálculos Consolidados do Lote
    hasLotItems() {
      return Object.keys(this.lot).length > 0;
    },

    getTotalVehicles() {
      return Object.values(this.lot).reduce((sum, item) => sum + item.qty, 0);
    },

    getTotalCost() {
      const discount = this.getUnitDiscount();
      return Object.values(this.lot).reduce((sum, item) => {
        const unitPrice = Math.max(0, item.price_outlet - discount);
        return sum + (unitPrice * item.qty);
      }, 0);
    },

    getTotalTurnover() {
      return Object.values(this.lot).reduce((sum, item) => sum + (item.price_original * item.qty), 0);
    },

    getTotalProfit() {
      return Math.max(0, this.getTotalTurnover() - this.getTotalCost());
    },

    // Formatação de Preço
    formatPrice(val) {
      const num = parseFloat(val) || 0;
      return num.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },

    // Geração do Link WhatsApp com o Lote Misto Consolidado
    getLotWhatsAppUrl() {
      const itemsList = Object.values(this.lot);
      if (itemsList.length === 0) return "#";
      const unitDiscount = this.getUnitDiscount();

      let text = "🏢 *PEDIDO DE LOTE ATACADO CNPJ • MAJ MOBILIDADE*\n";
      text += "----------------------------------------\n";
      text += "*Itens Selecionados no Lote:*\n";

      itemsList.forEach((item) => {
        const itemEffectivePrice = Math.max(0, item.price_outlet - unitDiscount);
        const itemMargin = Math.max(0, item.price_original - itemEffectivePrice);
        text += `• *${item.qty}x ${item.name}*\n`;
        text += `  Atacado Líquido: R$ ${this.formatPrice(itemEffectivePrice)}/un`;
        if (unitDiscount > 0) {
          text += ` (Preço Base: R$ ${this.formatPrice(item.price_outlet)} com desconto de -R$ ${this.formatPrice(unitDiscount)})`;
        }
        text += `\n  Sugerido Varejo: R$ ${this.formatPrice(item.price_original)} | Lucro: +R$ ${this.formatPrice(itemMargin * item.qty)}\n`;
        if (item.has_trunk) {
          text += `  🎁 _Acessório: Baú incluso de fábrica_\n`;
        }
      });

      text += "----------------------------------------\n";
      text += `*Total de Veículos:* ${this.getTotalVehicles()} unidades\n`;
      if (unitDiscount > 0) {
        text += `🔥 *DESCONTO DE VOLUME APLICADO:* -R$ ${this.formatPrice(unitDiscount)} por veículo\n`;
        text += `💰 *ECONOMIA DE VOLUME NO LOTE:* R$ ${this.formatPrice(this.getTotalVolumeSavings())}\n`;
      }
      text += `*Investimento Total:* R$ ${this.formatPrice(this.getTotalCost())}\n`;
      text += `*Faturamento Estimado:* R$ ${this.formatPrice(this.getTotalTurnover())}\n`;
      text += `🚀 *LUCRO ESTIMADO DA MINHA LOJA: +R$ ${this.formatPrice(this.getTotalProfit())}*\n`;
      text += "----------------------------------------\n";
      text += "Olá! Montei este lote de atacado pelo catálogo oficial com desconto de volume e gostaria de confirmar a disponibilidade e o frete para o meu CNPJ.";

      return `https://wa.me/${this.waNumber}?text=${encodeURIComponent(text)}`;
    },

    // Link individual por modelo (se o usuário quiser falar de um modelo isolado)
    getItemWhatsAppUrl(item) {
      let text = `Olá! Tenho interesse no modelo *${item.name}* no Atacado MAJ (CNPJ).\n`;
      text += `Preço Atacado: R$ ${this.formatPrice(item.price_outlet)}\n`;
      text += `Preço Sugerido: R$ ${this.formatPrice(item.price_retail_suggested || item.price_original)}\n`;
      text += `Margem Estimada: +R$ ${this.formatPrice(item.margin_reais)} (${item.margin_percent}%)\n`;
      if (item.has_trunk) {
        text += `🎁 _Com Baú Traseiro Incluso de Fábrica_\n`;
      }
      text += `Gostaria de verificar a disponibilidade e opções de lote.`;
      return `https://wa.me/${this.waNumber}?text=${encodeURIComponent(text)}`;
    },

    // Modal & Galeria de Fotos
    openModal(itemId) {
      const found = this.items.find(i => String(i.id) === String(itemId) || i.slug === itemId);
      if (found) {
        this.selectedItem = found;
        const gal = this.getItemGallery(found);
        this.activeImage = gal[0] || found.image_main || "/static/logo.png";
        this.modalOpen = true;
      }
    },

    closeModal() {
      this.modalOpen = false;
      this.selectedItem = null;
      this.activeImage = null;
    },

    finishModalAdd() {
      this.modalOpen = false;
      this.selectedItem = null;
      this.activeImage = null;
    },

    getItemGallery(item) {
      if (!item) return [];
      const gallery = [];
      if (item.image_main && typeof item.image_main === "string") {
        gallery.push(item.image_main);
      }
      let list = item.images_gallery;
      if (typeof list === "string") {
        try { list = JSON.parse(list); } catch (e) { list = []; }
      }
      if (Array.isArray(list)) {
        list.forEach(img => {
          if (img && typeof img === "string" && !gallery.includes(img)) {
            gallery.push(img);
          }
        });
      }
      return gallery;
    },

    nextImage() {
      const gallery = this.getItemGallery(this.selectedItem);
      if (gallery.length <= 1) return;
      const curIdx = gallery.indexOf(this.activeImage);
      const nextIdx = (curIdx + 1) % gallery.length;
      this.activeImage = gallery[nextIdx];
    },

    prevImage() {
      const gallery = this.getItemGallery(this.selectedItem);
      if (gallery.length <= 1) return;
      const curIdx = gallery.indexOf(this.activeImage);
      const prevIdx = (curIdx - 1 + gallery.length) % gallery.length;
      this.activeImage = gallery[prevIdx];
    },

    getActiveImageIndex() {
      const gallery = this.getItemGallery(this.selectedItem);
      const idx = gallery.indexOf(this.activeImage);
      return idx >= 0 ? idx + 1 : 1;
    }
  };
}
