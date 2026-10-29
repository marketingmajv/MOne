/**
 * MAJ Atacado B2B v3 - Script de Lógica e Reatividade (Alpine.js)
 * Base sólida da diagramação Atacado com evolução progressiva de elementos V2.
 */

function atacadoV3App() {
  const itemsData = window.V3_ITEMS_DATA || [];
  const waNumber = (window.V3_WA_NUMBER || "").replace(/\D/g, "") || "5527996051538";
  const waTemplate = window.V3_WA_TEMPLATE || "Olá! Tenho interesse no modelo {model} no Atacado MAJ Mobilidade (CNPJ) por {price} (valor a partir de 3 unidades). Gostaria de solicitar uma cotação/pedido.";
  const waFloatingMsg = window.V3_WA_FLOATING_MSG || "Olá! Estou navegando no Catálogo MAJ Atacado (CNPJ) e gostaria de falar com um consultor comercial de vendas no atacado.";
  const showPrices = window.V3_SHOW_PRICES !== false;

  return {
    showPrices: showPrices,
    searchQuery: "",
    activeCategory: "all",
    currentFilter: "all", // 'all' | 'mais_vendidos' | 'mais_baratos'
    sortBy: "stock_desc",
    items: itemsData,
    modalOpen: false,
    selectedItem: null,
    activeImage: "",
    selectedInstallment: 12,

    setFilter(filterName) {
      this.currentFilter = filterName;
      if (filterName === "mais_baratos") {
        this.sortBy = "price_asc";
      } else if (filterName === "all" && this.sortBy === "price_asc") {
        this.sortBy = "stock_desc";
      }
      const el = document.getElementById("catalogo");
      if (el && window.scrollY > 300) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },

    filteredItems() {
      let result = this.items.filter(item => {
        const q = this.searchQuery.toLowerCase().trim();
        const matchesQuery = !q || 
          (item.name && item.name.toLowerCase().includes(q)) || 
          (item.category && item.category.toLowerCase().includes(q)) || 
          (item.color && item.color.toLowerCase().includes(q)) ||
          (item.slug && item.slug.toLowerCase().includes(q));
        
        const matchesCat = this.activeCategory === "all" || 
          (item.category && item.category.toLowerCase().includes(this.activeCategory.toLowerCase()));
        
        let matchesFilter = true;
        if (this.currentFilter === "mais_vendidos") {
          const CAMPEOES_SLUGS = ["max-12", "flow-one", "m2", "classic-1000", "gp1000", "classic"];
          matchesFilter = !!item.is_best_seller || item.track === "campeoes" || CAMPEOES_SLUGS.includes(item.slug);
        }
        
        return matchesQuery && matchesCat && matchesFilter;
      });

      if (this.currentFilter === "mais_baratos" || this.sortBy === "price_asc") {
        result.sort((a, b) => (parseFloat(a.price_outlet) || 0) - (parseFloat(b.price_outlet) || 0));
      } else if (this.sortBy === "price_desc") {
        result.sort((a, b) => (parseFloat(b.price_outlet) || 0) - (parseFloat(a.price_outlet) || 0));
      } else if (this.sortBy === "stock_desc") {
        result.sort((a, b) => (parseInt(b.stock_qty) || 0) - (parseInt(a.stock_qty) || 0));
      } else if (this.sortBy === "name_asc") {
        result.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
      }

      return result;
    },

    clearFilters() {
      this.searchQuery = "";
      this.activeCategory = "all";
      this.currentFilter = "all";
      this.sortBy = "stock_desc";
    },

    hasActiveFilters() {
      return this.searchQuery.trim() !== "" || this.activeCategory !== "all" || this.currentFilter !== "all" || this.sortBy !== "stock_desc";
    },

    openModal(id) {
      const item = this.items.find(i => i.id === id);
      if (item) {
        this.selectedItem = item;
        this.activeImage = item.image_main;
        this.selectedInstallment = 12;
        this.modalOpen = true;
      }
    },

    getItemGallery(item) {
      if (!item) return [];
      let gal = item.images_gallery || [];
      if (typeof gal === "string") {
        try { gal = JSON.parse(gal); } catch(e) { gal = []; }
      }
      if (!Array.isArray(gal)) gal = [];
      return [...new Set([item.image_main, ...gal].filter(Boolean))];
    },

    formatPrice(val) {
      if (!val) return "0,00";
      return Number(val).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },

    getTieredWhatsAppUrl(item) {
      if (!item) return "";
      const model = item.name || "Veículo MAJ";
      const p1 = this.formatPrice(item.price_tier_1 || item.price_outlet);
      const p3 = this.formatPrice(item.price_tier_3 || (Math.max(0, parseFloat(item.price_outlet || 0) - 200)));
      
      let msg = "";
      if (this.showPrices && item.price_outlet > 0) {
        msg = `Olá! Tenho interesse no modelo ${model} no Catálogo de Atacado MAJ Mobilidade (CNPJ). Vi a tabela escalonada (R$ ${p3} a R$ ${p1} por unidade conforme volume a partir de 3 un). Gostaria de solicitar uma cotação/pedido.`;
      } else {
        msg = `Olá! Tenho interesse no modelo ${model} no Catálogo de Atacado MAJ Mobilidade (CNPJ). Gostaria de solicitar uma cotação para lote de atacado.`;
      }
      return `https://wa.me/${waNumber}?text=${encodeURIComponent(msg)}`;
    },

    getWhatsAppUrl(model, price) {
      let msg = "";
      if (this.showPrices && price && price !== "0,00" && price !== "Sob consulta") {
        msg = waTemplate.replace("{model}", model).replace("{price}", "R$ " + price);
      } else {
        msg = `Olá! Tenho interesse no modelo ${model} no Catálogo de Atacado MAJ Mobilidade (CNPJ). Gostaria de solicitar uma cotação.`;
      }
      return `https://wa.me/${waNumber}?text=${encodeURIComponent(msg)}`;
    },

    getFloatingWhatsAppUrl() {
      const msg = waFloatingMsg || "Olá! Estou navegando no Catálogo MAJ Atacado (CNPJ) e gostaria de falar com um consultor comercial de vendas no atacado.";
      return `https://wa.me/${waNumber}?text=${encodeURIComponent(msg)}`;
    }
  };
}

