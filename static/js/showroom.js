/**
 * MAJ MOBILIDADE — SHOWROOM ENGINE (SHOWROOM.JS)
 * Controla a navegação estilo Apple/Tesla, transições entre os 13 modelos,
 * simulação do cockpit iQ Touch HD, faróis Matrix e comparador dinâmico.
 */

(function () {
  'use strict';

  // Estado Global do Mostruário
  let allModels = [];
  let currentModel = null;
  let currentCategory = 'all';

  // 1. Inicialização do Wave Canvas em Background
  function initWaveCanvas() {
    const canvas = document.getElementById('waveCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let width, height;
    let step = 0;

    function resize() {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resize);
    resize();

    function render() {
      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = 'rgba(0, 215, 255, 0.22)';
      ctx.lineWidth = 1;

      const lines = 6;
      for (let l = 0; l < lines; l++) {
        ctx.beginPath();
        for (let x = 0; x < width; x += 20) {
          const y =
            height * 0.45 +
            Math.sin(x * 0.003 + step * 0.015 + l * 0.8) * 75 +
            Math.cos(x * 0.001 - step * 0.008) * 35;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      step++;
      requestAnimationFrame(render);
    }
    render();
  }

  // 2. Carregamento dos Modelos da API /api/models
  async function loadModels() {
    try {
      const response = await fetch('/api/models');
      const data = await response.json();
      allModels = data.models || [];

      if (allModels.length > 0) {
        renderModelCarousel(allModels);
        selectModel(allModels[0].slug);
        initComparisonSelects();
      }
    } catch (err) {
      console.error('Erro ao carregar modelos da API:', err);
    }
  }

  // 3. Renderização da Barra Seletora de Modelos (Apple/Tesla Style)
  function renderModelCarousel(modelsToRender) {
    const nav = document.getElementById('modelsCarouselNav');
    if (!nav) return;
    nav.innerHTML = '';

    modelsToRender.forEach((m) => {
      const btn = document.createElement('button');
      btn.className = `model-pill-item ${currentModel && currentModel.slug === m.slug ? 'active' : ''}`;
      btn.id = `pill-${m.slug}`;
      btn.innerHTML = `
        <span class="model-pill-dot"></span>
        <span class="model-pill-name">${m.modelo}</span>
      `;
      btn.addEventListener('click', () => selectModel(m.slug));
      nav.appendChild(btn);
    });
  }

  // 4. Seleção Dinâmica do Modelo (Zero Reload)
  function selectModel(slug) {
    const found = allModels.find((m) => m.slug === slug);
    if (!found) return;
    currentModel = found;

    // Atualizar classe ativa nas pílulas
    document.querySelectorAll('.model-pill-item').forEach((el) => el.classList.remove('active'));
    const activePill = document.getElementById(`pill-${slug}`);
    if (activePill) {
      activePill.classList.add('active');
      activePill.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }

    // 1. Atualizar Hero
    const catLabel = document.getElementById('heroCategoryLabel');
    if (catLabel) catLabel.textContent = `MAJ ELECTRIC ${found.categoria.toUpperCase()}`;

    const titleElem = document.getElementById('heroModelTitle');
    if (titleElem) {
      titleElem.style.opacity = '0';
      setTimeout(() => {
        titleElem.textContent = found.modelo;
        titleElem.style.opacity = '1';
      }, 150);
    }

    const descElem = document.getElementById('heroModelDesc');
    if (descElem) {
      descElem.textContent =
        found.metrics.diferencial ||
        found.metrics.descricao_livre ||
        'Projeto de mobilidade elétrica urbana de alta eficiência, robustez estrutural e pilotagem suave.';
    }

    // Atualizar Foto Hero (Cutout Transparente) e Reflexo
    const imgElem = document.getElementById('heroVehicleImg');
    const reflElem = document.getElementById('heroVehicleReflection');
    const heroSrc = found.cutout_image || (found.images && found.images[0]) || '/static/images/hero-fallback.png';

    if (imgElem) {
      imgElem.style.opacity = '0';
      imgElem.style.transform = 'scale(0.96)';
      setTimeout(() => {
        imgElem.src = heroSrc + (heroSrc.includes('?') ? '&' : '?') + 'v=3';
        imgElem.alt = found.modelo;
        imgElem.style.opacity = '1';
        imgElem.style.transform = 'scale(1)';
      }, 160);
    }

    if (reflElem) {
      reflElem.src = heroSrc;
    }

    // Atualizar Taglines do Hero
    const taglineHead = document.getElementById('heroTaglineHeadline');
    if (taglineHead) {
      const typeLabel = found.categoria.toUpperCase() === 'BIKE' ? 'E-BIKE' : 'SCOOTER';
      taglineHead.textContent = `THE HYPER URBAN ${typeLabel}.`;
    }

    // 2. Atualizar Telemetria Hero (Potência Nominal, Vel, Autonomia)
    const heroPot = document.getElementById('heroTelemetryPower');
    if (heroPot) heroPot.textContent = found.metrics.potencia_nominal_w ? `${found.metrics.potencia_nominal_w}W` : '1.000W';

    const heroVel = document.getElementById('heroTelemetrySpeed');
    if (heroVel) heroVel.textContent = found.metrics.velocidade_max_kmh ? `${found.metrics.velocidade_max_kmh} km/h` : '32 km/h';

    const heroAut = document.getElementById('heroTelemetryRange');
    if (heroAut) heroAut.textContent = found.metrics.autonomia_conservadora_km ? `${found.metrics.autonomia_conservadora_km}` : '35 km';

    // 3. Atualizar Big Cards da Seção de Telemetria
    const bigPot = document.getElementById('bigMetricPower');
    if (bigPot) bigPot.textContent = found.metrics.potencia_nominal_w || '1.000';

    const bigVel = document.getElementById('bigMetricSpeed');
    if (bigVel) bigVel.textContent = found.metrics.velocidade_max_kmh || '32';

    const bigAut = document.getElementById('bigMetricRange');
    if (bigAut) bigAut.textContent = found.metrics.autonomia_conservadora_km ? found.metrics.autonomia_conservadora_km.replace('km', '').trim() : '35';

    const bigAutSub = document.getElementById('bigMetricRangeSub');
    if (bigAutSub) {
      bigAutSub.textContent = `Autonomia conservadora estimada para rotas urbanas (até ${found.metrics.autonomia_maxima_km || '50'} km em condições ideais).`;
    }

    // 4. Atualizar Cockpit HD
    updateCockpitForModel(found);

    // 5. Atualizar Gaveta Técnica
    renderTechDrawerCards(found);

    // 6. Atualizar Galeria de Fotos
    renderGalleryPhotos(found);

    // 7. Atualizar Linha do Comparador
    updateComparisonActiveCol(found);
  }

  // 5. Atualização do Cockpit HD
  function updateCockpitForModel(model) {
    const hudSpeed = document.getElementById('hudSpeedVal');
    if (hudSpeed) hudSpeed.textContent = model.metrics.velocidade_max_kmh || '32';

    const hudModelName = document.getElementById('hudModelName');
    if (hudModelName) hudModelName.textContent = `MAJ ${model.modelo.toUpperCase()}`;

    const hudBattery = document.getElementById('hudBatteryInfo');
    if (hudBattery) {
      const volt = model.metrics.voltagem_v || '60V';
      const ah = model.metrics.capacidade_ah || '20Ah';
      hudBattery.textContent = `BATERIA: ${volt} ${ah}`;
    }
  }

  // 6. Alternância de Modos do Cockpit
  window.setCockpitMode = function (mode, speed, badgeText, color) {
    const speedVal = document.getElementById('hudSpeedVal');
    if (speedVal) speedVal.textContent = speed;

    const badge = document.getElementById('hudModeBadge');
    if (badge) {
      badge.textContent = badgeText;
      badge.style.color = color;
      badge.style.borderColor = color;
    }

    document.querySelectorAll('.cockpit-mode-btn').forEach((b) => b.classList.remove('active'));
    if (event && event.target) event.target.classList.add('active');
  };

  // 7. Renderização dos Cards Técnicos na Gaveta
  function renderTechDrawerCards(model) {
    const container = document.getElementById('techCardsCarousel');
    if (!container) return;
    container.innerHTML = '';

    const sections = model.sections || {};

    const cardsData = [
      {
        title: 'Motorização & Desempenho',
        icon: '⚡',
        items: [
          { lbl: 'Potência Nominal', val: `${model.metrics.potencia_nominal_w || '1.000'}W` },
          { lbl: 'Velocidade Máxima', val: `${model.metrics.velocidade_max_kmh || '32'} km/h` },
          { lbl: 'Modos de Condução', val: sections['Desempenho']?.['Modos de condução'] || '3 níveis' },
          { lbl: 'Possui Marcha a Ré?', val: sections['Desempenho']?.['Possui ré?'] || 'Não' },
        ],
      },
      {
        title: 'Bateria & Autonomia',
        icon: '🔋',
        items: [
          { lbl: 'Voltagem / Capacidade', val: `${model.metrics.voltagem_v || '60V'} • ${model.metrics.capacidade_ah || '20Ah'}` },
          { lbl: 'Capacidade Total', val: model.metrics.capacidade_wh || '1200Wh' },
          { lbl: 'Bateria Removível?', val: sections['Bateria e autonomia']?.['Bateria removível?'] || 'Sim' },
          { lbl: 'Autonomia Estimada', val: `${model.metrics.autonomia_conservadora_km || '35km'} (até ${model.metrics.autonomia_maxima_km || '50km'})` },
        ],
      },
      {
        title: 'Estrutura & Conforto',
        icon: '🛡️',
        items: [
          { lbl: 'Carga Máxima Suportada', val: `${model.metrics.carga_maxima_kg || '180'} kg` },
          { lbl: 'Peso do Veículo', val: model.metrics.peso_kg || '75 kg' },
          { lbl: 'Ocupantes Recomendados', val: sections['Estrutura e conforto']?.['Ocupantes recomendados'] || '1 a 2' },
          { lbl: 'Compartimento / Baú', val: sections['Estrutura e conforto']?.['Porta-objetos / baú'] || 'Incluso' },
        ],
      },
      {
        title: 'Segurança & Freios',
        icon: '🛑',
        items: [
          { lbl: 'Sistema de Frenagem', val: model.metrics.freios || 'Disco / Hidráulico' },
          { lbl: 'Suspensão Dianteira', val: sections['Segurança e componentes']?.['Suspensão dianteira'] || 'Hidráulica' },
          { lbl: 'Suspensão Traseira', val: sections['Segurança e componentes']?.['Suspensão traseira'] || 'Duplo amortecedor' },
          { lbl: 'Iluminação', val: sections['Segurança e componentes']?.['Iluminação'] || 'Full LED' },
        ],
      },
    ];

    cardsData.forEach((cd) => {
      const card = document.createElement('div');
      card.className = 'tech-spec-card';
      let listHtml = '';
      cd.items.forEach((it) => {
        listHtml += `<li><span class="lbl">${it.lbl}</span><span class="val">${it.val}</span></li>`;
      });
      card.innerHTML = `
        <span class="tech-spec-card-icon">${cd.icon}</span>
        <h4 class="tech-spec-card-title">${cd.title}</h4>
        <ul class="tech-spec-card-list">${listHtml}</ul>
      `;
      container.appendChild(card);
    });
  }

  // 8. Renderização da Galeria de Fotos com Vinheta
  function renderGalleryPhotos(model) {
    const scroller = document.getElementById('galleryScroller');
    if (!scroller) return;
    scroller.innerHTML = '';

    const imgs = model.images || [];
    if (imgs.length === 0) {
      scroller.innerHTML = '<p style="color: var(--text-muted); padding: 40px;">Fotos do ensaio em processamento.</p>';
      return;
    }

    imgs.forEach((url) => {
      const card = document.createElement('div');
      card.className = 'gallery-photo-card';
      card.innerHTML = `
        <img src="${url}" alt="${model.modelo}" loading="lazy">
        <div class="gallery-vignette-overlay"></div>
      `;
      scroller.appendChild(card);
    });
  }

  // 9. Alternância da Gaveta Técnica
  window.toggleTechDrawer = function () {
    const drawer = document.getElementById('techDrawer');
    if (!drawer) return;
    drawer.classList.toggle('open');
    const btn = document.querySelector('.drawer-toggle-btn span');
    if (btn) {
      btn.textContent = drawer.classList.contains('open') ? 'Recolher Engenharia' : 'Explorar Ficha Técnica e Engenharia';
    }
  };

  // 10. Filtro por Categoria
  window.filterCategory = function (cat) {
    currentCategory = cat;
    document.querySelectorAll('.cat-filter-btn, .cat-tab-btn').forEach((b) => b.classList.remove('active'));
    if (window.event && window.event.target) window.event.target.classList.add('active');

    const filtered = cat === 'all' ? allModels : allModels.filter((m) => m.categoria.toLowerCase() === cat.toLowerCase());
    renderModelCarousel(filtered);
    if (filtered.length > 0) {
      selectModel(filtered[0].slug);
    }
  };

  // 11. Comparador Dinâmico
  function initComparisonSelects() {
    const sel = document.getElementById('compareModelSelect');
    if (!sel) return;
    sel.innerHTML = '';

    allModels.forEach((m) => {
      const opt = document.createElement('option');
      opt.value = m.slug;
      opt.textContent = `${m.categoria}: ${m.modelo}`;
      sel.appendChild(opt);
    });

    if (allModels.length > 1) {
      sel.selectedIndex = 1;
      updateComparisonSecondCol(allModels[1]);
    }

    sel.addEventListener('change', (e) => {
      const chosen = allModels.find((m) => m.slug === e.target.value);
      if (chosen) updateComparisonSecondCol(chosen);
    });
  }

  function updateComparisonActiveCol(model) {
    const colHeader = document.getElementById('compColActiveHeader');
    if (colHeader) colHeader.textContent = model.modelo;

    const fields = ['potencia_nominal_w', 'velocidade_max_kmh', 'autonomia_conservadora_km', 'carga_maxima_kg', 'peso_kg', 'freios'];
    fields.forEach((f) => {
      const el = document.getElementById(`comp-active-${f}`);
      if (el) el.textContent = model.metrics[f] || '—';
    });
  }

  function updateComparisonSecondCol(model) {
    const colHeader = document.getElementById('compColSecondHeader');
    if (colHeader) colHeader.textContent = model.modelo;

    const fields = ['potencia_nominal_w', 'velocidade_max_kmh', 'autonomia_conservadora_km', 'carga_maxima_kg', 'peso_kg', 'freios'];
    fields.forEach((f) => {
      const el = document.getElementById(`comp-second-${f}`);
      if (el) el.textContent = model.metrics[f] || '—';
    });
  }

  // Inicialização no DOM Ready
  document.addEventListener('DOMContentLoaded', () => {
    initWaveCanvas();
    loadModels();
  });
})();
