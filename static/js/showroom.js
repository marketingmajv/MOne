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

  // 1. Carregamento dos Modelos da API /api/models
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

  // 2. Renderização da Barra Seletora de Modelos
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

  // 3. Seleção Dinâmica do Modelo (Zero Reload)
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

    // Atualizar Banner Panorâmico Widescreen (Exclusivo MAX 12 MAJ)
    const bannerElem = document.getElementById('max12PanoramicBanner');
    const heroStageElem = document.getElementById('hero');
    const isMax12 = slug === 'max-12' || (found.modelo && found.modelo.toUpperCase().includes('MAX 12'));
    if (bannerElem) {
      bannerElem.style.display = isMax12 ? 'block' : 'none';
      bannerElem.style.opacity = isMax12 ? '1' : '0';
      if (heroStageElem) heroStageElem.style.display = isMax12 ? 'none' : 'flex';
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
      taglineHead.textContent = `ALTA PERFORMANCE ${found.categoria.toUpperCase() === 'BIKE' ? 'E-BIKE' : 'SCOOTER'}.`;
    }

    // 2. Atualizar Telemetria Hero (Potência Nominal, Vel, Autonomia)
    const heroPot = document.getElementById('heroTelemetryPower');
    if (heroPot) heroPot.textContent = found.metrics.potencia_nominal_w ? `${found.metrics.potencia_nominal_w}W` : '1.000W';

    const heroVel = document.getElementById('heroTelemetrySpeed');
    if (heroVel) heroVel.textContent = found.metrics.velocidade_max_kmh ? `${found.metrics.velocidade_max_kmh} km/h` : '32 km/h';

    const heroAut = document.getElementById('heroTelemetryRange');
    if (heroAut) heroAut.textContent = found.metrics.autonomia_maxima_km ? `Até ${found.metrics.autonomia_maxima_km} km` : 'Até 50 km';

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
    const s = model.sections || {}, m = model.metrics || {};
    const topSpeed = parseInt(m.velocidade_max_kmh || '32', 10) || 32;

    const hudModelName = document.getElementById('hudModelName');
    if (hudModelName) hudModelName.textContent = `MAJ ${model.modelo.toUpperCase()}`;

    const hudBattery = document.getElementById('hudBatteryInfo');
    if (hudBattery) {
      const volt = m.voltagem_v || '60V';
      const ah = m.capacidade_ah || '20Ah';
      const quim = (s['Bateria e autonomia']?.['Química / tipo'] || '').includes('LiFePO') ? 'LiFePO₄' : 'Lítio';
      hudBattery.textContent = `BATERIA: ${volt} ${ah} • ${quim}`;
    }

    const hudChassis = document.getElementById('hudChassisInfo');
    if (hudChassis) hudChassis.textContent = `ESTRUTURA: AÇO CARBONO • CARGA ${m.carga_maxima_kg || '180'} KG`;

    const hudBrakes = document.getElementById('hudBrakesInfo');
    if (hudBrakes) hudBrakes.textContent = `FREIOS: ${m.freios || 'HIDRÁULICOS D/T'}`.toUpperCase();

    const btnLevel3 = document.getElementById('btnCockpitLevel3');
    if (btnLevel3) {
      btnLevel3.setAttribute('onclick', `setCockpitMode('level3', '${topSpeed}', 'NÍVEL 3 (MÁXIMA)', '#e1ff32')`);
      btnLevel3.textContent = `Nível 3 (${topSpeed} km/h)`;
    }

    const hasReverse = (s['Desempenho']?.['Possui ré?'] || '').toLowerCase().includes('sim');
    const revBtn = document.getElementById('btnCockpitReverse');
    if (revBtn) revBtn.style.display = hasReverse ? 'inline-flex' : 'none';

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
    const s = model.sections || {}, m = model.metrics || {};
    const cL = s['Estrutura e conforto']?.['Comprimento (cm)'] || '170';
    const lG = s['Estrutura e conforto']?.['Largura (cm)'] || '76';
    const alt = s['Estrutura e conforto']?.['Altura (cm)'] || '130';
    const ass = s['Estrutura e conforto']?.['Altura do assento (cm)'] || '76';
    const quim = (s['Bateria e autonomia']?.['Química / tipo'] || '').includes('LiFePO') ? 'LiFePO₄ (LFP)' : (s['Bateria e autonomia']?.['Química / tipo'] || 'Lítio');

    const cardsData = [
      {
        title: 'Motorização & Desempenho', icon: '⚡', items: [
          { lbl: 'Potência Nominal', val: `${m.potencia_nominal_w || '1000'}W` }, { lbl: 'Velocidade Máxima', val: `${m.velocidade_max_kmh || '32'} km/h` },
          { lbl: 'Modos de Condução', val: s['Desempenho']?.['Modos de condução'] || '3 níveis' }, { lbl: 'Possui Marcha a Ré?', val: s['Desempenho']?.['Possui ré?'] || 'Sim' },
          { lbl: 'Subidas / Relevo', val: s['Uso e comercial']?.['Subidas: limite e condições'] || 'Subidas íngremes' },
        ],
      },
      {
        title: 'Bateria & Autonomia', icon: '🔋', items: [
          { lbl: 'Química da Bateria', val: quim }, { lbl: 'Voltagem / Capacidade', val: `${m.voltagem_v || '60V'} • ${m.capacidade_ah || '20Ah'}` },
          { lbl: 'Capacidade Total', val: m.capacidade_wh || '1200Wh' }, { lbl: 'Bateria Removível?', val: s['Bateria e autonomia']?.['Bateria removível?'] || 'Sim' },
          { lbl: 'Carregador Oficial', val: s['Bateria e autonomia']?.['Carregador'] || '60V 2A' }, { lbl: 'Autonomia Estimada', val: `Até ${m.autonomia_maxima_km || '50'} km de autonomia` },
        ],
      },
      {
        title: 'Chassi & Dimensões', icon: '🛡️', items: [
          { lbl: 'Dimensões (C × L × A)', val: `${cL} × ${lG} × ${alt} cm` }, { lbl: 'Altura do Assento', val: `${ass} cm` },
          { lbl: 'Carga Máxima', val: `${m.carga_maxima_kg || '180'} kg` }, { lbl: 'Peso do Veículo', val: m.peso_kg || '75 kg' },
          { lbl: 'Ocupantes Homologados', val: `${s['Estrutura e conforto']?.['Ocupantes homologados'] || '2'} pessoas` }, { lbl: 'Estrutura do Chassi', val: 'Aço carbono de alta qualidade' },
        ],
      },
      {
        title: 'Segurança & Freios', icon: '🛑', items: [
          { lbl: 'Freio Dianteiro', val: s['Segurança e componentes']?.['Freio dianteiro'] || 'Hidráulico' }, { lbl: 'Freio Traseiro', val: s['Segurança e componentes']?.['Freio traseiro'] || 'Hidráulico' },
          { lbl: 'Suspensão Diant. / Tras.', val: 'Hidráulica com duplo amortecedor' }, { lbl: 'Pneus / Rodagem', val: s['Segurança e componentes']?.['Pneu / aro'] || 'Pneus largos' },
          { lbl: 'Alarme & Iluminação', val: 'Alarme sonoro ativo e Iluminação LED' },
        ],
      },
      {
        title: 'Uso, Ergonomia & Conforto', icon: '🛵', items: [
          { lbl: 'Porta-Objetos / Baú', val: s['Estrutura e conforto']?.['Porta-objetos / baú'] || 'Porta-Objetos' }, { lbl: 'Ergonomia', val: 'Pilotagem ereta e confortável' },
          { lbl: 'Perfil de Uso', val: 'Deslocamentos urbanos e trabalho diário' }, { lbl: 'Restrições de Uso', val: s['Uso e comercial']?.['Não recomendado para'] || 'Menores de 16 anos' },
        ],
      },
      {
        title: 'Garantia & Regulamentação', icon: '📜', items: [
          { lbl: 'Garantia do Veículo', val: s['Uso e comercial']?.['Garantia do veículo'] || '180 dias' }, { lbl: 'Garantia da Bateria', val: '1 ano com revisões (90 dias revenda)' },
          { lbl: 'Assistência Técnica', val: 'Autorizada Maj Mobilidade Elétrica' }, { lbl: 'Exige CNH?', val: 'Não exigido' },
          { lbl: 'Exige Emplacamento?', val: 'Não (Resolução CONTRAN nº 996/2023)' },
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
    const m = model.metrics || {};
    const map = {
      potencia_nominal_w: m.potencia_nominal_w ? `${m.potencia_nominal_w}W` : '1000W',
      velocidade_max_kmh: m.velocidade_max_kmh ? `${m.velocidade_max_kmh} km/h` : '32 km/h',
      autonomia_maxima_km: `Até ${m.autonomia_maxima_km || '50'} km`,
      carga_maxima_kg: m.carga_maxima_kg ? `${m.carga_maxima_kg} kg` : '180 kg',
      peso_kg: m.peso_kg || '75 kg',
      freios: m.freios || 'Hidráulico',
    };
    Object.entries(map).forEach(([f, val]) => {
      const el = document.getElementById(`comp-${prefix}-${f}`);
      if (el) el.textContent = val;
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
    const m = currentModel.metrics || {};
    const potVal = parseInt(String(m.potencia_nominal_w || '1000').replace(/[^\d]/g, ''), 10) || 1000;
    const velVal = parseInt(String(m.velocidade_max_kmh || '32').replace(/[^\d]/g, ''), 10) || 32;
    const autVal = parseInt(String(m.autonomia_maxima_km || '50').replace(/[^\d]/g, ''), 10) || 50;

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
    const s = model.sections || {}, m = model.metrics || {};
    const potSub = document.getElementById('bigMetricPowerSub');
    if (potSub) potSub.textContent = s['Desempenho']?.['Observações de desempenho'] || 'Motor de alta performance calibrado para rendimento e subidas urbanas.';

    const speedSub = document.getElementById('bigMetricSpeedSub');
    if (speedSub) {
      const topSpeed = m.velocidade_max_kmh || '32';
      speedSub.textContent = `Velocidade máxima homologada de ${topSpeed} km/h. Dispensa CNH e emplacamento conforme a Resolução CONTRAN nº 996/2023.`;
    }

    const rangeSub = document.getElementById('bigMetricRangeSub');
    if (rangeSub) {
      rangeSub.textContent = `(Até ${m.autonomia_maxima_km || '50'} km de autonomia). Avaliação realizada com piloto de ~75 kg em piso plano, seco e pavimentado.`;
    }

    const potVal = parseInt(String(m.potencia_nominal_w || '1000').replace(/[^\d]/g, ''), 10) || 1000;
    const velVal = parseInt(String(m.velocidade_max_kmh || '32').replace(/[^\d]/g, ''), 10) || 32;
    const autVal = parseInt(String(m.autonomia_maxima_km || '50').replace(/[^\d]/g, ''), 10) || 50;

    if (telemetryHasBeenRevealed) {
      animateTelemetryCountUp(false);
    } else {
      const p = document.getElementById('bigMetricPower'); if (p) p.textContent = potVal;
      const v = document.getElementById('bigMetricSpeed'); if (v) v.textContent = velVal;
      const a = document.getElementById('bigMetricRange'); if (a) a.textContent = autVal;
    }
  }

  // Inicialização no DOM Ready
  document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    initShowroomScrollObservers();
  });
})();
