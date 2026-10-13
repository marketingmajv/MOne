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
    const c = document.getElementById('waveCanvas');
    if (!c) return;
    const ctx = c.getContext('2d');
    let w, h, s = 0;
    const resize = () => { w = c.width = window.innerWidth; h = c.height = window.innerHeight; };
    window.addEventListener('resize', resize);
    resize();
    (function render() {
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = 'rgba(0, 215, 255, 0.22)';
      ctx.lineWidth = 1;
      for (let l = 0; l < 6; l++) {
        ctx.beginPath();
        for (let x = 0; x < w; x += 20) {
          const y = h * 0.45 + Math.sin(x * 0.003 + s * 0.015 + l * 0.8) * 75 + Math.cos(x * 0.001 - s * 0.008) * 35;
          x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      s++;
      requestAnimationFrame(render);
    })();
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
      btn.innerHTML = `<span class="model-pill-dot"></span><span class="model-pill-name">${m.modelo}</span>`;
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

    // Atualizar Banner Panorâmico Full-Width Exclusivo (MAX 12 MAJ)
    const bannerElem = document.getElementById('max12PanoramicBanner');
    const heroStageElem = document.getElementById('hero');
    const isMax12 = slug === 'max-12' || (found.modelo && found.modelo.toUpperCase().includes('MAX 12'));

    if (bannerElem) {
      if (isMax12) {
        bannerElem.style.display = 'block';
        bannerElem.style.opacity = '0';
        requestAnimationFrame(() => {
          bannerElem.style.transition = 'opacity 0.35s ease';
          bannerElem.style.opacity = '1';
        });
        if (heroStageElem) {
          heroStageElem.style.display = 'none';
        }
      } else {
        bannerElem.style.transition = 'opacity 0.25s ease';
        bannerElem.style.opacity = '0';
        setTimeout(() => {
          if (currentModel && currentModel.slug !== 'max-12' && !(currentModel.modelo && currentModel.modelo.toUpperCase().includes('MAX 12'))) {
            bannerElem.style.display = 'none';
          }
        }, 250);
        if (heroStageElem) {
          heroStageElem.style.display = 'flex';
        }
      }
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
    updateTelemetryBigCards(found);

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

    const topSpeed = parseInt(model.metrics.velocidade_max_kmh || '32', 10) || 32;
    const sportBtn = document.querySelector('.cockpit-mode-btn[onclick*="sport"]');
    if (sportBtn) {
      sportBtn.setAttribute('onclick', `setCockpitMode('sport', '${topSpeed}', 'MODO SPORT ATIVO', '#e1ff32')`);
      sportBtn.textContent = `Modo Sport (${topSpeed} km/h)`;
    }

    if (cockpitHasBeenRevealed) {
      animateCockpitSpeedometer(topSpeed);
    } else {
      const hudSpeed = document.getElementById('hudSpeedVal');
      if (hudSpeed) hudSpeed.textContent = topSpeed;
    }
  }

  function animateCockpitSpeedometer(targetSpeed) {
    const el = document.getElementById('hudSpeedVal');
    if (!el) return;
    const target = Math.round(Number(targetSpeed)) || 0;
    const current = Math.round(Number(el.textContent)) || 0;
    if (current === target) return;

    el.classList.remove('tachometer-accel', 'tachometer-brake');
    el.classList.add(target > current ? 'tachometer-accel' : 'tachometer-brake');

    animateCountUp(el, current, target, 750, 0, () => {
      el.classList.remove('tachometer-accel', 'tachometer-brake');
    });
  }

  // 6. Alternância de Modos do Cockpit
  window.setCockpitMode = function (mode, speed, badgeText, color) {
    const badge = document.getElementById('hudModeBadge');
    if (badge) {
      badge.textContent = badgeText;
      badge.style.color = color;
      badge.style.borderColor = color;
    }
    document.querySelectorAll('.cockpit-mode-btn').forEach((b) => b.classList.remove('active'));
    if (window.event && window.event.target) window.event.target.classList.add('active');

    animateCockpitSpeedometer(speed);
  };

  // 7. Renderização dos Cards Técnicos na Gaveta
  function renderTechDrawerCards(model) {
    const container = document.getElementById('techCardsCarousel');
    if (!container) return;
    container.innerHTML = '';
    const s = model.sections || {};
    const m = model.metrics || {};

    const cardsData = [
      {
        title: 'Motorização & Desempenho', icon: '⚡', items: [
          { lbl: 'Potência Nominal', val: `${m.potencia_nominal_w || '1000'}W` },
          { lbl: 'Velocidade Máxima', val: `${m.velocidade_max_kmh || '32'} km/h` },
          { lbl: 'Modos de Condução', val: s['Desempenho']?.['Modos de condução'] || '3 níveis' },
          { lbl: 'Possui Marcha a Ré?', val: s['Desempenho']?.['Possui ré?'] || 'Não' },
        ],
      },
      {
        title: 'Bateria & Autonomia', icon: '🔋', items: [
          { lbl: 'Voltagem / Capacidade', val: `${m.voltagem_v || '60V'} • ${m.capacidade_ah || '20Ah'}` },
          { lbl: 'Capacidade Total', val: m.capacidade_wh || '1200Wh' },
          { lbl: 'Bateria Removível?', val: s['Bateria e autonomia']?.['Bateria removível?'] || 'Sim' },
          { lbl: 'Autonomia Estimada', val: `${m.autonomia_conservadora_km || '35km'} (até ${m.autonomia_maxima_km || '50km'})` },
        ],
      },
      {
        title: 'Estrutura & Conforto', icon: '🛡️', items: [
          { lbl: 'Carga Máxima Suportada', val: `${m.carga_maxima_kg || '180'} kg` },
          { lbl: 'Peso do Veículo', val: m.peso_kg || '75 kg' },
          { lbl: 'Ocupantes Recomendados', val: s['Estrutura e conforto']?.['Ocupantes recomendados'] || '1 a 2' },
          { lbl: 'Compartimento / Baú', val: s['Estrutura e conforto']?.['Porta-objetos / baú'] || 'Incluso' },
        ],
      },
      {
        title: 'Segurança & Freios', icon: '🛑', items: [
          { lbl: 'Sistema de Frenagem', val: m.freios || 'Disco / Hidráulico' },
          { lbl: 'Suspensão Dianteira', val: s['Segurança e componentes']?.['Suspensão dianteira'] || 'Hidráulica' },
          { lbl: 'Suspensão Traseira', val: s['Segurança e componentes']?.['Suspensão traseira'] || 'Duplo amortecedor' },
          { lbl: 'Iluminação', val: s['Segurança e componentes']?.['Iluminação'] || 'Full LED' },
        ],
      },
    ];

    cardsData.forEach((cd) => {
      const card = document.createElement('div');
      card.className = 'tech-spec-card';
      const listHtml = cd.items.map((it) => `<li><span class="lbl">${it.lbl}</span><span class="val">${it.val}</span></li>`).join('');
      card.innerHTML = `<span class="tech-spec-card-icon">${cd.icon}</span><h4 class="tech-spec-card-title">${cd.title}</h4><ul class="tech-spec-card-list">${listHtml}</ul>`;
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

  function updateComparisonCol(prefix, model) {
    const colHeader = document.getElementById(prefix === 'active' ? 'compColActiveHeader' : 'compColSecondHeader');
    if (colHeader) colHeader.textContent = model.modelo;
    ['potencia_nominal_w', 'velocidade_max_kmh', 'autonomia_conservadora_km', 'carga_maxima_kg', 'peso_kg', 'freios'].forEach((f) => {
      const el = document.getElementById(`comp-${prefix}-${f}`);
      if (el) el.textContent = model.metrics[f] || '—';
    });
  }
  function updateComparisonActiveCol(model) { updateComparisonCol('active', model); }
  function updateComparisonSecondCol(model) { updateComparisonCol('second', model); }

  // 7. Animações de Entrada em Cascata & Scroll Observers
  let telemetryHasBeenRevealed = false;
  let cockpitHasBeenRevealed = false;

  function initShowroomScrollObservers() {
    const secTel = document.getElementById('telemetry');
    const grid = document.querySelector('.telemetry-grid-wrapper');
    const cards = document.querySelectorAll('.telemetry-big-card');
    if (secTel && grid && cards.length > 0) {
      grid.classList.add('anim-ready');
      const obsTel = new IntersectionObserver((entries, obs) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !telemetryHasBeenRevealed) {
            telemetryHasBeenRevealed = true;
            cards.forEach((c, idx) => setTimeout(() => c.classList.add('card-revealed'), idx * 150));
            animateTelemetryCountUp(true);
            obs.disconnect();
          }
        });
      }, { threshold: 0.15 });
      obsTel.observe(secTel);
    }

    const secCockpit = document.getElementById('cockpit');
    if (secCockpit) {
      const obsCockpit = new IntersectionObserver((entries, obs) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !cockpitHasBeenRevealed) {
            cockpitHasBeenRevealed = true;
            const top = currentModel ? (parseInt(currentModel.metrics.velocidade_max_kmh || '32', 10) || 32) : 32;
            const hud = document.getElementById('hudSpeedVal');
            if (hud) hud.textContent = '0';
            animateCockpitSpeedometer(top);
            obs.disconnect();
          }
        });
      }, { threshold: 0.2 });
      obsCockpit.observe(secCockpit);
    }
  }

  function animateCountUp(element, startVal, endVal, duration = 1200, delay = 0, onComplete = null) {
    if (!element) return;
    const end = Math.round(endVal), start = Math.round(startVal);
    element.dataset.animTarget = end;

    setTimeout(() => {
      if (parseInt(element.dataset.animTarget, 10) !== end) return;
      let startTime = null;
      function step(timestamp) {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 3);
        element.textContent = Math.floor(start + (end - start) * ease);

        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          element.textContent = end;
          if (typeof onComplete === 'function') onComplete();
        }
      }
      requestAnimationFrame(step);
    }, delay);
  }

  function animateTelemetryCountUp(fromZero = false) {
    if (!currentModel) return;
    const potVal = parseInt(String(currentModel.metrics.potencia_nominal_w || '1000').replace(/[^\d]/g, ''), 10) || 1000;
    const velVal = parseInt(String(currentModel.metrics.velocidade_max_kmh || '32').replace(/[^\d]/g, ''), 10) || 32;
    const autVal = parseInt(String(currentModel.metrics.autonomia_conservadora_km || '35').replace(/[^\d]/g, ''), 10) || 35;

    const bigPot = document.getElementById('bigMetricPower');
    const bigVel = document.getElementById('bigMetricSpeed');
    const bigAut = document.getElementById('bigMetricRange');

    if (fromZero) {
      animateCountUp(bigPot, 0, potVal, 1300, 50);
      animateCountUp(bigVel, 0, velVal, 1200, 200);
      animateCountUp(bigAut, 0, autVal, 1200, 350);
    } else {
      const curPot = bigPot ? (parseInt(bigPot.textContent.replace(/[^\d]/g, ''), 10) || 0) : 0;
      const curVel = bigVel ? (parseInt(bigVel.textContent.replace(/[^\d]/g, ''), 10) || 0) : 0;
      const curAut = bigAut ? (parseInt(bigAut.textContent.replace(/[^\d]/g, ''), 10) || 0) : 0;
      animateCountUp(bigPot, curPot, potVal, 800, 0);
      animateCountUp(bigVel, curVel, velVal, 750, 0);
      animateCountUp(bigAut, curAut, autVal, 750, 0);
    }
  }

  function updateTelemetryBigCards(model) {
    const sub = document.getElementById('bigMetricRangeSub');
    if (sub) sub.textContent = `Autonomia conservadora estimada para rotas urbanas (até ${model.metrics.autonomia_maxima_km || '50'} km em condições ideais).`;

    if (telemetryHasBeenRevealed) {
      animateTelemetryCountUp(false);
    } else {
      const potVal = parseInt(String(model.metrics.potencia_nominal_w || '1000').replace(/[^\d]/g, ''), 10) || 1000;
      const velVal = parseInt(String(model.metrics.velocidade_max_kmh || '32').replace(/[^\d]/g, ''), 10) || 32;
      const autVal = parseInt(String(model.metrics.autonomia_conservadora_km || '35').replace(/[^\d]/g, ''), 10) || 35;
      const p = document.getElementById('bigMetricPower'); if (p) p.textContent = potVal;
      const v = document.getElementById('bigMetricSpeed'); if (v) v.textContent = velVal;
      const a = document.getElementById('bigMetricRange'); if (a) a.textContent = autVal;
    }
  }

  // Inicialização no DOM Ready
  document.addEventListener('DOMContentLoaded', () => {
    initWaveCanvas();
    loadModels();
    initShowroomScrollObservers();
  });
})();
