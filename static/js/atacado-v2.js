function atacadoV2App() {
  const serverItems = (typeof window !== "undefined" && window.V2_ITEMS_DATA) ? window.V2_ITEMS_DATA : [];
  const serverWaNumber = (typeof window !== "undefined" && window.V2_WA_NUMBER) ? window.V2_WA_NUMBER : "5527996051538";
  return {
    items: serverItems,
    waNumber: serverWaNumber,
    searchQuery: "",
    currentFilter: "all", // 'all' | 'mais_vendidos' | 'mais_baratos' | 'scooters' | 'bikes'
    currentBuyerPath: null, // null | 'iniciante' | 'mix' | 'reposicao'
    
    // Modal
    modalOpen: false,
    selectedItem: null,
    activeImage: "",

    // Montador de Lote Misto (Armazenado localmente)
    lot: {},
    itemSelectedTiers: {}, // Seleção individual por produto (default tier 3: mais barato)

    setFilter(filterName) {
      this.currentBuyerPath = null;
      if (this.currentFilter === filterName) {
        this.currentFilter = "all";
      } else {
        this.currentFilter = filterName;
      }
    },

    selectBuyerPath(path) {
      if (this.currentBuyerPath === path) {
        this.currentBuyerPath = null;
      } else {
        this.currentBuyerPath = path;
        this.currentFilter = "all";
      }
    },

    getTrackEyebrow() {
      if (this.currentBuyerPath === "iniciante") return "🌱 SELEÇÃO PARA INICIANTES EM REVENDA";
      if (this.currentBuyerPath === "mix") return "📈 EXPANSÃO DE MIX E MARGEM POTENCIAL";
      if (this.currentBuyerPath === "reposicao") return "📦 ALTA DISPONIBILIDADE IMEDIATA";
      if (this.currentFilter === "mais_vendidos") return "⭐ MODELOS COM MAIOR VELOCIDADE DE SAÍDA";
      if (this.currentFilter === "mais_baratos") return "💰 MENOR TÍQUETE INICIAL DE INVESTIMENTO";
      if (this.currentFilter === "scooters") return "🛵 LINHA COMPLETA DE SCOOTERS ELÉTRICAS";
      if (this.currentFilter === "bikes") return "🚲 BIKES ELÉTRICAS DE ALTA PERFORMANCE";
      return "⚡ ESTOQUE GLOBAL PRONTA ENTREGA CNPJ";
    },

    getTrackTitle() {
      if (this.currentBuyerPath === "iniciante") return "Modelos Recomendados para Início";
      if (this.currentBuyerPath === "mix") return "Mix Diversificado para Sua Loja";
      if (this.currentBuyerPath === "reposicao") return "Reposição Imediata com Maior Estoque";
      if (this.currentFilter === "mais_vendidos") return "Mais Vendidos da Categoria";
      if (this.currentFilter === "mais_baratos") return "Modelos Mais Baratos";
      if (this.currentFilter === "scooters") return "Scooters Elétricas MAJ";
      if (this.currentFilter === "bikes") return "Bikes Elétricas MAJ";
      return "Catálogo Completo Atacado";
    },

    getDisplayItems() {
      let list = [...this.items];
      // Ocultar produtos sem preco na planilha
      list = list.filter(i => (parseFloat(i.price_outlet) || 0) > 0);

      // Trilhas de Decisão B2B (Seção 8 do Estudo)
      if (this.currentBuyerPath === "iniciante") {
        const inicianteSlugs = ["max-12", "flow-one", "v20-ultra", "m9-pro", "v8-mini-ultra"];
        return list.filter(i => inicianteSlugs.includes(i.slug));
      }
      if (this.currentBuyerPath === "mix") {
        const mixSlugs = ["gp1000", "jm-125", "mantis", "nova", "vittoria", "x15-pro", "db-zero", "classic-1000"];
        return list.filter(i => mixSlugs.includes(i.slug));
      }
      if (this.currentBuyerPath === "reposicao") {
        return list.filter(i => (parseInt(i.stock_qty) || 0) >= 10).sort((a, b) => (parseInt(b.stock_qty) || 0) - (parseInt(a.stock_qty) || 0));
      }

      if (this.searchQuery && this.searchQuery.trim()) {
        const q = this.searchQuery.toLowerCase().trim();
        list = list.filter(i => (i.name && i.name.toLowerCase().includes(q)) || (i.slug && i.slug.toLowerCase().includes(q)));
      }

      if (this.currentFilter === "mais_vendidos") {
        return list.filter(i => i.is_best_seller);
      }
      if (this.currentFilter === "mais_baratos") {
        return list.sort((a, b) => (parseFloat(a.price_outlet) || 0) - (parseFloat(b.price_outlet) || 0));
      }
      if (this.currentFilter === "scooters") {
        return list.filter(i => i.vehicle_type === "scooter" || (!i.vehicle_type && !["m9-pro","m50-pro","v20-ultra","v8-mini-ultra","v80-pro"].includes(i.slug)));
      }
      if (this.currentFilter === "bikes") {
        return list.filter(i => i.vehicle_type === "bike" || (i.slug && ["m9-pro","m50-pro","v20-ultra","v8-mini-ultra","v80-pro"].includes(i.slug)));
      }
      return list;
    },

    // Seleção individual por produto (01: padrão no mais barato / 02: individual sem afetar outros)
    getItemTier(item) {
      if (!item) return 3;
      const qty = this.getQty(item.id);
      if (qty >= 21) return 3;
      if (qty >= 11) return 2;
      if (qty >= 1) return 1;
      return this.itemSelectedTiers[item.id] || 3;
    },

    getItemDisplayPrice(item) {
      if (!item) return 0;
      const tier = this.getItemTier(item);
      if (tier === 3) return item.price_tier_3 || item.price_outlet;
      if (tier === 2) return item.price_tier_2 || item.price_outlet;
      return item.price_tier_1 || item.price_outlet;
    },

    getItemDisplayMarginReais(item) {
      if (!item) return 0;
      const price = this.getItemDisplayPrice(item);
      const retail = parseFloat(item.price_retail_suggested || item.price_original) || 0;
      return Math.max(0, retail - price);
    },

    getItemDisplayMarginPct(item) {
      if (!item) return 0;
      const retail = parseFloat(item.price_retail_suggested || item.price_original) || 0;
      if (retail <= 0) return 0;
      const margin = this.getItemDisplayMarginReais(item);
      // Margem Bruta Real sobre a venda sugerida
      return Math.round((margin / retail) * 100);
    },

    selectTierDirect(item, tier) {
      if (!item) return;
      this.itemSelectedTiers[item.id] = tier;
      if (tier === 3) {
        this.setQty(item, 21);
      } else if (tier === 2) {
        this.setQty(item, 11);
      } else {
        this.setQty(item, 3);
      }
    },

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
        delete this.itemSelectedTiers[item.id];
      } else {
        if (qty >= 21) {
          this.itemSelectedTiers[item.id] = 3;
        } else if (qty >= 11) {
          this.itemSelectedTiers[item.id] = 2;
        } else {
          this.itemSelectedTiers[item.id] = 1;
        }
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
        text += `\n  Sugerido Varejo: R$ ${this.formatPrice(item.price_original)} | Margem Bruta: +R$ ${this.formatPrice(itemMargin * item.qty)}\n`;
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
      text += `🚀 *GANHO BRUTO ESTIMADO DA LOJA: +R$ ${this.formatPrice(this.getTotalProfit())}*\n`;
      text += "----------------------------------------\n";
      text += "Olá! Montei este lote de atacado pelo catálogo oficial com desconto de volume e gostaria de confirmar a disponibilidade e a cotação de frete para o meu CNPJ/cidade.";

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
