// MAJ MOBILIDADE — SHOWROOM TV KIOSK ENGINE (MODO VITRINE AUTOMÁTICA)
(function () {
  'use strict';

  let isTvModeActive = false;
  let isPaused = false;
  let intervalSeconds = 30;
  let autoPauseSeconds = 45;
  let pauseCountdownTimer = null;
  let pauseRemainingSeconds = 0;
  let animFrameId = null;
  let slideStartTime = null;

  let progressBarEl = null;
  let tvBadgeEl = null;
  let tvBadgeTextEl = null;

  // 1. Criação dos Elementos Visuais do Modo TV (Barra Neon e Badge)
  function createTvUi() {
    if (document.getElementById('tvProgressTrack')) return;

    const track = document.createElement('div');
    track.id = 'tvProgressTrack';
    track.className = 'tv-progress-track';
    track.innerHTML = '<div id="tvProgressBar" class="tv-progress-bar"></div>';
    document.body.prepend(track);
    progressBarEl = document.getElementById('tvProgressBar');

    const badge = document.createElement('div');
    badge.id = 'tvBadge';
    badge.className = 'tv-kiosk-badge';
    badge.setAttribute('title', 'Clique para pausar ou retomar a vitrine automática (Atalho: Barra de Espaço ou tecla T)');
    badge.innerHTML = `
      <span class="tv-kiosk-dot"></span>
      <span class="tv-kiosk-text" id="tvBadgeText">MODO TV • ${intervalSeconds}s</span>
    `;
    badge.addEventListener('click', () => toggleTvMode());
    document.body.appendChild(badge);

    tvBadgeEl = badge;
    tvBadgeTextEl = document.getElementById('tvBadgeText');
  }

  // 2. Loop de Animação em 60fps da Barra de Progresso e Troca de Modelo
  function startSlideTimer() {
    slideStartTime = performance.now();
    if (animFrameId) cancelAnimationFrame(animFrameId);

    function tick(now) {
      if (!isTvModeActive || isPaused) return;

      const elapsed = now - slideStartTime;
      const progress = Math.min(elapsed / (intervalSeconds * 1000), 1);

      if (progressBarEl) {
        progressBarEl.style.width = (progress * 100).toFixed(2) + '%';
      }

      if (progress >= 1) {
        advanceToNextModel(1);
        slideStartTime = performance.now();
      }

      animFrameId = requestAnimationFrame(tick);
    }

    animFrameId = requestAnimationFrame(tick);
  }

  // 3. Avanço para o Próximo Modelo com Transição Deslize Lateral Apple
  function advanceToNextModel(dir = 1) {
    if (typeof window.getShowroomModels !== 'function' || typeof window.selectShowroomModel !== 'function') return;

    const models = window.getShowroomModels();
    if (!models || models.length === 0) return;

    const current = window.getCurrentShowroomModel();
    let currentIdx = models.findIndex((m) => m.slug === (current ? current.slug : ''));
    if (currentIdx === -1) currentIdx = 0;

    const nextIdx = (currentIdx + dir + models.length) % models.length;
    const nextModel = models[nextIdx];

    if (nextModel) {
      window.selectShowroomModel(nextModel.slug, true, dir);
      if (progressBarEl) progressBarEl.style.width = '0%';
    }
  }

  // 4. Pausa Temporária por Interação Humana (45 segundos de inatividade)
  function handleUserInteraction() {
    if (!isTvModeActive || isPaused) return;

    isPaused = true;
    pauseRemainingSeconds = autoPauseSeconds;
    updateBadgeState();

    if (pauseCountdownTimer) clearInterval(pauseCountdownTimer);

    pauseCountdownTimer = setInterval(() => {
      pauseRemainingSeconds -= 1;
      if (pauseRemainingSeconds <= 0) {
        clearInterval(pauseCountdownTimer);
        pauseCountdownTimer = null;
        isPaused = false;
        slideStartTime = performance.now();
        updateBadgeState();
        startSlideTimer();
      } else {
        updateBadgeState();
      }
    }, 1000);
  }

  function updateBadgeState() {
    if (!tvBadgeEl || !tvBadgeTextEl) return;

    if (!isTvModeActive) {
      tvBadgeEl.classList.add('is-hidden');
      if (progressBarEl) progressBarEl.style.width = '0%';
      return;
    }

    tvBadgeEl.classList.remove('is-hidden');

    if (isPaused) {
      tvBadgeEl.classList.add('is-paused');
      tvBadgeTextEl.textContent = `PAUSADO (${pauseRemainingSeconds}s)`;
    } else {
      tvBadgeEl.classList.remove('is-paused');
      tvBadgeTextEl.textContent = `MODO TV • ${intervalSeconds}s`;
    }
  }

  // 5. Métodos Públicos
  window.startTvMode = function (sec) {
    if (sec && !isNaN(sec)) intervalSeconds = Math.max(5, parseInt(sec, 10));
    createTvUi();
    isTvModeActive = true;
    isPaused = false;
    if (pauseCountdownTimer) clearInterval(pauseCountdownTimer);
    updateBadgeState();
    startSlideTimer();
  };

  window.stopTvMode = function () {
    isTvModeActive = false;
    isPaused = false;
    if (animFrameId) cancelAnimationFrame(animFrameId);
    if (pauseCountdownTimer) clearInterval(pauseCountdownTimer);
    updateBadgeState();
  };

  window.toggleTvMode = function () {
    if (!isTvModeActive) {
      window.startTvMode();
    } else if (isPaused) {
      isPaused = false;
      if (pauseCountdownTimer) clearInterval(pauseCountdownTimer);
      slideStartTime = performance.now();
      updateBadgeState();
      startSlideTimer();
    } else {
      isPaused = true;
      pauseRemainingSeconds = autoPauseSeconds;
      updateBadgeState();
    }
  };

  // 6. Inicialização e Escuta de Eventos
  async function initKiosk() {
    createTvUi();
    const urlParams = new URLSearchParams(window.location.search);
    const pTv = urlParams.get('tv') || urlParams.get('kiosk') || urlParams.get('autoplay');
    const pSec = urlParams.get('sec') || urlParams.get('interval');

    let shouldStart = pTv === '1' || pTv === 'true';

    try {
      const resp = await fetch('/api/models/kiosk-settings');
      if (resp.ok) {
        const settings = await resp.json();
        intervalSeconds = parseInt(pSec || settings.interval_seconds || 30, 10);
        autoPauseSeconds = parseInt(settings.auto_pause_seconds || 45, 10);
        if (shouldStart || settings.enabled) shouldStart = true;
      }
    } catch (e) {
      console.warn('Falha ao carregar configurações do kiosk:', e);
    }

    if (shouldStart) {
      window.startTvMode(intervalSeconds);
    }

    // Escuta de interação nas pílulas de navegação do showroom
    document.addEventListener('click', (e) => {
      if (e.target && e.target.closest('.model-pill-item')) {
        handleUserInteraction();
      }
    });

    // Teclas de atalho na TV/Computador: Espaço/T alterna play/pause; Setas avançam/retrocedem
    document.addEventListener('keydown', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
      if (e.code === 'Space' || e.key.toLowerCase() === 't') {
        e.preventDefault();
        window.toggleTvMode();
      } else if (e.key === 'ArrowRight' && isTvModeActive) {
        advanceToNextModel(1);
        slideStartTime = performance.now();
      } else if (e.key === 'ArrowLeft' && isTvModeActive) {
        advanceToNextModel(-1);
        slideStartTime = performance.now();
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Aguarda levemente o carregamento dos modelos pelo showroom.js
    setTimeout(initKiosk, 600);
  });
})();
