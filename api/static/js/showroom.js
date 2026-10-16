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
      setTimeout(() => { titleElem.textContent = found.modelo; titleElem.style.opacity = '1'; }, 150);
    }

    const descElem = document.getElementById('heroModelDesc');
    if (descElem) descElem.textContent = found.metrics.diferencial || found.metrics.descricao_livre || 'Projeto de mobilidade elétrica urbana de alta eficiência, robustez e pilotagem suave.';

    // Foto Hero e Reflexo
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
    if (reflElem) reflElem.src = heroSrc;

    const taglineHead = document.getElementById('heroTaglineHeadline');
    if (taglineHead) taglineHead.textContent = `ALTA PERFORMANCE ${found.categoria.toUpperCase() === 'BIKE' ? 'E-BIKE' : 'SCOOTER'}.`;

    // 2. Telemetria Hero
    const heroPot = document.getElementById('heroTelemetryPower');
    if (heroPot) heroPot.textContent = found.metrics.potencia_nominal_w ? `${found.metrics.potencia_nominal_w}W` : '1.000W';
    const heroVel = document.getElementById('heroTelemetrySpeed');
    if (heroVel) heroVel.textContent = found.metrics.velocidade_max_kmh ? `${found.metrics.velocidade_max_kmh} km/h` : '32 km/h';
    const heroAut = document.getElementById('heroTelemetryRange');
    if (heroAut) heroAut.textContent = found.metrics.autonomia_maxima_km ? `Até ${found.metrics.autonomia_maxima_km} km` : 'Até 50 km';

    updateTelemetryBigCards(found);

    // 4. Atualizar Cockpit HD & Telemetria de Engenharia
    updateCockpitForModel(found);

    // 5. Atualizar Galeria de Fotos
    renderGalleryPhotos(found);

    // 6. Atualizar Linha do Comparador
    updateComparisonActiveCol(found);
  }

  let activeCockpitCategory = 'motorizacao';

  function getCategoryTelemetryData(model, catKey) {
    const s = model.sections || {}, m = model.metrics || {};
    const cL = s['Estrutura e conforto']?.['Comprimento (cm)'] || '170';
    const lG = s['Estrutura e conforto']?.['Largura (cm)'] || '76';
    const alt = s['Estrutura e conforto']?.['Altura (cm)'] || '130';
    const ass = s['Estrutura e conforto']?.['Altura do assento (cm)'] || '76';
    const quim = (s['Bateria e autonomia']?.['Química / tipo'] || '').includes('LiFePO') ? 'LiFePO₄' : 'Lítio';

    const categories = {
      motorizacao: {
        tag: 'MOTORIZAÇÃO & DESEMPENHO',
        mainVal: parseInt(String(m.potencia_nominal_w || '1000').replace(/[^\d]/g, ''), 10) || 1000,
        unit: 'WATTS',
        badge: 'POTÊNCIA NOMINAL MÁXIMA',
        badgeColor: '#00d7ff',
        items: [
          { lbl: 'Velocidade Máxima', val: `${m.velocidade_max_kmh || '32'} km/h` },
          { lbl: 'Modos de Condução', val: s['Desempenho']?.['Modos de condução'] || '3 níveis' },
          { lbl: 'Marcha a Ré?', val: s['Desempenho']?.['Possui ré?'] || 'Sim' },
          { lbl: 'Subidas / Relevo', val: s['Uso e comercial']?.['Subidas: limite e condições'] || 'Subidas íngremes' },
        ],
      },
      bateria: {
        tag: 'BATERIA & AUTONOMIA',
        mainVal: parseInt(String(m.capacidade_wh || '1200').replace(/[^\d]/g, ''), 10) || 1200,
        unit: 'WH (CAPACIDADE)',
        badge: `BATERIA: ${m.voltagem_v || '60V'} ${m.capacidade_ah || '20Ah'} • ${quim}`,
        badgeColor: '#28e1a5',
        items: [
          { lbl: 'Química da Bateria', val: quim }, { lbl: 'Autonomia Estimada', val: `Até ${m.autonomia_maxima_km || '50'} km` },
          { lbl: 'Bateria Removível?', val: s['Bateria e autonomia']?.['Bateria removível?'] || 'Sim' },
          { lbl: 'Carregador Oficial', val: s['Bateria e autonomia']?.['Carregador'] || '60V 2A' },
        ],
      },
      chassi: {
        tag: 'CHASSI & ESTRUTURA',
        mainVal: parseInt(String(m.carga_maxima_kg || '180').replace(/[^\d]/g, ''), 10) || 180,
        unit: 'KG CARGA MÁXIMA',
        badge: 'ESTRUTURA AÇO CARBONO',
        badgeColor: '#e1ff32',
        items: [
          { lbl: 'Dimensões (C×L×A)', val: `${cL} × ${lG} × ${alt} cm` }, { lbl: 'Altura do Assento', val: `${ass} cm` },
          { lbl: 'Peso do Veículo', val: `${m.peso_kg || '75'} kg` }, { lbl: 'Ocupantes', val: `${s['Estrutura e conforto']?.['Ocupantes homologados'] || '2'} pessoas` },
        ],
      },
      seguranca: {
        tag: 'SEGURANÇA & FREIOS',
        mainVal: 100,
        unit: '% SISTEMA HIDRÁULICO',
        badge: `FREIOS: ${m.freios || 'HIDRÁULICOS D/T'}`.toUpperCase(),
        badgeColor: '#ff5252',
        items: [
          { lbl: 'Freio Dianteiro', val: s['Segurança e componentes']?.['Freio dianteiro'] || 'Hidráulico' },
          { lbl: 'Freio Traseiro', val: s['Segurança e componentes']?.['Freio traseiro'] || 'Hidráulico' },
          { lbl: 'Suspensão', val: 'Duplo amortecedor hidráulico' }, { lbl: 'Alarme / LED', val: 'Alarme sonoro & Faróis LED' },
        ],
      },
      conforto: {
        tag: 'ERGONOMIA & CONFORTO',
        mainVal: 2,
        unit: 'ASSENTOS HOMOLOGADOS',
        badge: 'PILOTAGEM CONFORTÁVEL',
        badgeColor: '#00d7ff',
        items: [
          { lbl: 'Porta-Objetos', val: s['Estrutura e conforto']?.['Porta-objetos / baú'] || 'Porta-objetos' },
          { lbl: 'Ergonomia', val: 'Pilotagem ereta e confortável' }, { lbl: 'Perfil de Uso', val: 'Deslocamentos urbanos' },
          { lbl: 'Restrições', val: s['Uso e comercial']?.['Não recomendado para'] || 'Menores de 16 anos' },
        ],
      },
      garantia: {
        tag: 'GARANTIA & HOMOLOGAÇÃO',
        mainVal: 180,
        unit: 'DIAS GARANTIA OFICIAL',
        badge: 'CONTRAN 996/2023 DISPENSA CNH',
        badgeColor: '#e1ff32',
        items: [
          { lbl: 'Garantia Veículo', val: s['Uso e comercial']?.['Garantia do veículo'] || '180 dias' },
          { lbl: 'Garantia Bateria', val: '1 ano com revisões' }, { lbl: 'Exige CNH?', val: 'Não exigido (Dispensa legal)' },
          { lbl: 'Emplacamento?', val: 'Não exigido' },
        ],
      },
    };

    return categories[catKey] || categories.motorizacao;
  }

  // 5. Atualização do Cockpit Digital & Engenharia
  function updateCockpitForModel(model) {
    if (!model) return;
    const hudModelName = document.getElementById('hudModelName');
    if (hudModelName) hudModelName.textContent = `MAJ ${model.modelo.toUpperCase()}`;

    renderCockpitCategoryView(model, activeCockpitCategory);
  }

  function renderCockpitCategoryView(model, catKey) {
    if (!model) return;
    const data = getCategoryTelemetryData(model, catKey);

    const tagEl = document.getElementById('hudCategoryTag');
    if (tagEl) { tagEl.textContent = data.tag; tagEl.style.color = data.badgeColor || 'var(--maj-cyan)'; }

    const unitEl = document.getElementById('hudUnitLabel');
    if (unitEl) unitEl.textContent = data.unit;

    const badgeEl = document.getElementById('hudModeBadge');
    if (badgeEl) {
      badgeEl.textContent = data.badge;
      badgeEl.style.color = data.badgeColor || 'var(--maj-cyan)';
      badgeEl.style.borderColor = data.badgeColor || 'var(--maj-cyan)';
    }

    const mainValEl = document.getElementById('hudMainVal');
    if (mainValEl) {
      const cur = parseInt(mainValEl.textContent.replace(/[^\d]/g, ''), 10) || 0;
      if (cockpitHasBeenRevealed) animateCountUp(mainValEl, cur, data.mainVal, 750, 0);
      else mainValEl.textContent = data.mainVal;
    }

    const gridEl = document.getElementById('hudSpecsGrid');
    if (gridEl) {
      gridEl.innerHTML = data.items.map((it) => `
        <div class="hud-spec-card">
          <span class="lbl">${it.lbl}</span>
          <span class="val">${it.val}</span>
        </div>
      `).join('');
    }
  }

  window.setCockpitCategory = function (catKey) {
    activeCockpitCategory = catKey;
    document.querySelectorAll('#cockpitTechControls .cockpit-mode-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(catKey));
    });
    if (currentModel) {
      renderCockpitCategoryView(currentModel, catKey);
    }
  };

  // 6. Renderização da Galeria de Fotos em Grid com Lightbox Interativo
  let currentGalleryPhotos = [];
  let currentLightboxIndex = 0;

  function renderGalleryPhotos(model) {
    const grid = document.getElementById('galleryGrid') || document.getElementById('galleryScroller');
    if (!grid) return;
    grid.innerHTML = '';
    currentGalleryPhotos = model.images || [];

    if (currentGalleryPhotos.length === 0) {
      grid.innerHTML = '<p style="color: var(--text-muted); padding: 40px; grid-column: 1 / -1;">Fotos do ensaio em processamento.</p>';
      return;
    }

    currentGalleryPhotos.forEach((url, idx) => {
      const card = document.createElement('div');
      card.className = 'gallery-photo-card';
      card.onclick = () => openGalleryLightbox(idx);
      card.innerHTML = `
        <img src="${url}" alt="${model.modelo} - Foto ${idx + 1}" loading="lazy">
        <div class="gallery-photo-card-hover-icon">
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="11" y1="8" x2="11" y2="14"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
        </div>
      `;
      grid.appendChild(card);
    });
  }

  window.openGalleryLightbox = function (index) {
    if (!currentGalleryPhotos.length) return;
    currentLightboxIndex = (index + currentGalleryPhotos.length) % currentGalleryPhotos.length;
    const img = document.getElementById('galleryLightboxImg');
    const modelName = document.getElementById('galleryLightboxModelName');
    const counter = document.getElementById('galleryLightboxCounter');
    const modal = document.getElementById('galleryLightboxModal');
    if (img) img.src = currentGalleryPhotos[currentLightboxIndex];
    if (modelName && currentModel) modelName.textContent = `MAJ ${currentModel.modelo.toUpperCase()}`;
    if (counter) counter.textContent = `Foto ${currentLightboxIndex + 1} de ${currentGalleryPhotos.length}`;
    if (modal) modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  };

  window.closeGalleryLightbox = function (e) {
    if (e && e.target && e.target.closest('.gallery-lightbox-content') && !e.target.closest('.gallery-lightbox-close')) return;
    const modal = document.getElementById('galleryLightboxModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
  };

  window.navigateGalleryLightbox = (dir) => openGalleryLightbox(currentLightboxIndex + dir);
  window.toggleMobileNav = (isOpen) => {
    const drawer = document.getElementById('mobileNavDrawer');
    if (drawer) drawer.classList.toggle('open', isOpen);
    document.body.style.overflow = isOpen ? 'hidden' : '';
  };

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeGalleryLightbox(); toggleMobileNav(false); }
    const modal = document.getElementById('galleryLightboxModal');
    if (!modal || modal.style.display === 'none') return;
    if (e.key === 'ArrowLeft') openGalleryLightbox(currentLightboxIndex - 1);
    else if (e.key === 'ArrowRight') openGalleryLightbox(currentLightboxIndex + 1);
  });

  // 10. Filtro por Categoria
  window.filterCategory = function (cat) {
    currentCategory = cat;
    document.querySelectorAll('.cat-filter-btn, .cat-tab-btn').forEach((b) => b.classList.remove('active'));
    if (window.event && window.event.target) window.event.target.classList.add('active');

    const filtered = cat === 'all' ? allModels : allModels.filter((m) => m.categoria.toLowerCase() === cat.toLowerCase());
    renderModelCarousel(filtered);
    if (filtered.length > 0) selectModel(filtered[0].slug);
  };

  // 11. Comparador Dinâmico
  function initComparisonSelects() {
    const sel = document.getElementById('compareModelSelect');
    if (!sel) return;
    sel.innerHTML = allModels.map(m => `<option value="${m.slug}">${m.categoria}: ${m.modelo}</option>`).join('');
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
      peso_kg: m.peso_kg || '75 kg', freios: m.freios || 'Hidráulico',
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
            if (currentModel) {
              const data = getCategoryTelemetryData(currentModel, activeCockpitCategory);
              const hud = document.getElementById('hudMainVal');
              if (hud) {
                hud.textContent = '0';
                animateCountUp(hud, 0, data.mainVal, 850, 0);
              }
            }
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
    if (speedSub) speedSub.textContent = `Velocidade máxima homologada de ${m.velocidade_max_kmh || '32'} km/h. Dispensa CNH e emplacamento conforme a Resolução CONTRAN nº 996/2023.`;
    const rangeSub = document.getElementById('bigMetricRangeSub');
    if (rangeSub) rangeSub.textContent = `(Até ${m.autonomia_maxima_km || '50'} km de autonomia). Avaliação realizada com piloto de ~75 kg em piso plano, seco e pavimentado.`;

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
