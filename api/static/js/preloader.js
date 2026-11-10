/**
 * M-One MAJ OS Hybrid Smart Preloader (static/js/preloader.js)
 * Arquitetura Híbrida (Linear / Vercel / YouTube Style):
 * - Top Neon Progress Bar + Pill Executivo de Status Não-Bloqueante
 * - Sincronizado com o Ciclo Real de Rede (beforeunload + window.fetch + HTMX + window.load)
 * - Nunca encerra enquanto o servidor (TTFB) ou chamadas fetch() iniciais ainda estiverem rodando.
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'mone_preloader_pending';
  const MAX_NAVIGATION_SAFETY_MS = 25000;
  const QUIET_WINDOW_MS = 220;

  let preloaderEl = null;
  let textEl = null;
  let badgeEl = null;
  let barEl = null;

  let trickleTimer = null;
  let messageCycleInterval = null;
  let safetyTimeout = null;
  let quietCheckTimer = null;
  let inPageFetchShowTimer = null;

  let currentProgress = 0;
  let navigationInFlight = false;
  let isInitialBootPending = false;
  let activeFetches = 0;
  let lastNetworkFinishTs = 0;

  const STATUS_MESSAGES = [
    'Sincronizando com MAJ Operating System...',
    'Carregando dados operacionais...',
    'Consultando banco de dados...',
    'Renderizando componentes da tela...'
  ];

  function getElements() {
    if (!preloaderEl) {
      preloaderEl = document.getElementById('monePreloader');
      if (preloaderEl) {
        textEl = preloaderEl.querySelector('.mone-preloader-text');
        badgeEl = preloaderEl.querySelector('.mone-preloader-badge');
        barEl = preloaderEl.querySelector('.mone-preloader-bar');
      }
    }
    return !!preloaderEl;
  }

  function setProgress(pct) {
    currentProgress = Math.max(0, Math.min(100, pct));
    document.documentElement.style.setProperty('--mone-progress', `${currentProgress}%`);
    if (getElements() && barEl) {
      barEl.style.width = `${currentProgress}%`;
    }
  }

  function startTrickle(maxCap = 86) {
    clearInterval(trickleTimer);
    trickleTimer = setInterval(() => {
      if (currentProgress >= maxCap) return;
      const remaining = maxCap - currentProgress;
      const step = Math.max(0.8, remaining * 0.14);
      setProgress(Math.min(maxCap, currentProgress + step));
    }, 240);
  }

  function setPendingStorage(text, badge) {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          text: text || 'Carregando...',
          badge: badge || 'MAJ OS',
          ts: Date.now()
        })
      );
    } catch (e) {}
  }

  function clearPendingStorage() {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  function show(customText, customBadge, immediate = true, persist = true, isNav = false) {
    getElements();
    clearInterval(messageCycleInterval);
    clearTimeout(safetyTimeout);
    clearTimeout(quietCheckTimer);

    if (isNav) {
      navigationInFlight = true;
      document.documentElement.classList.add('mone-content-transitioning');
    }

    const text = customText || (textEl ? textEl.textContent : 'Carregando...');
    const badge = customBadge || (badgeEl ? badgeEl.textContent : 'MAJ OS');

    if (persist) {
      setPendingStorage(text, badge);
    }

    if (textEl && text) textEl.textContent = text;
    if (badgeEl && badge) badgeEl.textContent = badge;

    document.documentElement.classList.add('mone-preloader-active');
    if (preloaderEl) {
      preloaderEl.classList.add('active');
      preloaderEl.setAttribute('aria-hidden', 'false');
    }

    if (currentProgress < 18 || currentProgress >= 98) {
      setProgress(18);
    }
    startTrickle(isNav ? 84 : 90);

    let msgIndex = 0;
    messageCycleInterval = setInterval(() => {
      if (textEl && document.documentElement.classList.contains('mone-preloader-active')) {
        textEl.textContent = STATUS_MESSAGES[msgIndex % STATUS_MESSAGES.length];
        msgIndex++;
      }
    }, 2200);

    safetyTimeout = setTimeout(() => {
      navigationInFlight = false;
      isInitialBootPending = false;
      hide(true);
    }, MAX_NAVIGATION_SAFETY_MS);
  }

  function hide(force = false) {
    // Nunca fecha se uma navegação de página acabou de ser disparada e aguarda o servidor (exceto force)
    if (navigationInFlight && !force) {
      return;
    }
    // Se ainda há requisições fetch() ativas da página e não é force, aguarda concluírem
    if (activeFetches > 0 && !force) {
      scheduleCompletionCheck();
      return;
    }

    clearInterval(trickleTimer);
    clearInterval(messageCycleInterval);
    clearTimeout(safetyTimeout);
    clearTimeout(quietCheckTimer);
    clearPendingStorage();
    navigationInFlight = false;
    isInitialBootPending = false;

    setProgress(100);
    document.documentElement.classList.remove('mone-content-transitioning');

    const doDismiss = () => {
      document.documentElement.classList.remove('mone-preloader-active');
      if (getElements()) {
        preloaderEl.classList.remove('active');
        preloaderEl.setAttribute('aria-hidden', 'true');
      }
      setTimeout(() => {
        if (!document.documentElement.classList.contains('mone-preloader-active')) {
          setProgress(0);
        }
      }, 220);
    };

    if (force) {
      doDismiss();
    } else {
      setTimeout(doDismiss, 180);
    }
  }

  function scheduleCompletionCheck() {
    clearTimeout(quietCheckTimer);
    quietCheckTimer = setTimeout(() => {
      if (navigationInFlight) return;
      if (document.readyState !== 'complete') return;
      if (activeFetches > 0) return;
      const sinceLastNet = Date.now() - lastNetworkFinishTs;
      if (lastNetworkFinishTs > 0 && sinceLastNet < QUIET_WINDOW_MS) {
        scheduleCompletionCheck();
        return;
      }
      hide(false);
    }, QUIET_WINDOW_MS);
  }

  function isIgnoredBackgroundUrl(urlStr) {
    if (!urlStr) return false;
    const s = String(urlStr);
    return s.includes('/api/suporte/badges') || s.includes('viacep.com.br');
  }

  function onNetworkStart(urlStr, label) {
    if (isIgnoredBackgroundUrl(urlStr)) return () => {};
    activeFetches++;

    if (document.documentElement.classList.contains('mone-preloader-active')) {
      if (currentProgress < 68) setProgress(68);
      startTrickle(93);
    } else if (!navigationInFlight) {
      clearTimeout(inPageFetchShowTimer);
      inPageFetchShowTimer = setTimeout(() => {
        if (activeFetches > 0 && !document.documentElement.classList.contains('mone-preloader-active')) {
          show(label || 'Sincronizando dados...', 'MAJ OS', true, false, false);
        }
      }, 220);
    }

    let finished = false;
    return () => {
      if (finished) return;
      finished = true;
      activeFetches = Math.max(0, activeFetches - 1);
      lastNetworkFinishTs = Date.now();
      if (activeFetches === 0) {
        clearTimeout(inPageFetchShowTimer);
        if (document.documentElement.classList.contains('mone-preloader-active') && !navigationInFlight) {
          scheduleCompletionCheck();
        }
      }
    };
  }

  function hookNetworkInterceptors() {
    if (window.__moneFetchHooked) return;
    window.__moneFetchHooked = true;

    const prevFetch = window.fetch;
    if (typeof prevFetch === 'function') {
      window.fetch = function (input, init) {
        const urlStr = typeof input === 'string' ? input : (input && input.url ? input.url : '');
        const done = onNetworkStart(urlStr);
        try {
          const p = prevFetch.apply(this, arguments);
          if (p && typeof p.finally === 'function') {
            return p.finally(done);
          }
          done();
          return p;
        } catch (err) {
          done();
          throw err;
        }
      };
    }

    document.addEventListener('htmx:beforeRequest', (evt) => {
      const path = evt.detail?.pathInfo?.requestPath || '';
      const done = onNetworkStart(path, 'Atualizando visualização...');
      if (evt.detail && evt.detail.xhr) {
        evt.detail.xhr.addEventListener('loadend', done, { once: true });
      } else {
        setTimeout(done, 1500);
      }
    });
  }

  function reload(customText = 'Atualizando página...', customBadge = 'MAJ OS') {
    show(customText, customBadge, true, true, true);
    setTimeout(() => {
      window.location.reload();
    }, 25);
  }

  function navigate(url, customText = 'Carregando...', customBadge = 'MAJ OS') {
    if (!url) return;
    show(customText, customBadge, true, true, true);
    setTimeout(() => {
      window.location.href = url;
    }, 25);
  }

  function extractContextFromLink(a) {
    const text = (a.innerText || a.textContent || '').replace(/\s+/g, ' ').trim();
    if (text) {
      const lower = text.toLowerCase();
      if (lower.includes('visão geral') || lower.includes('dashboard')) return 'Abrindo Visão Geral...';
      if (lower.includes('vendas')) return 'Abrindo Vendas...';
      if (lower.includes('fretes')) return 'Carregando Fretes & Transportadoras...';
      if (lower.includes('estoque')) return 'Carregando Estoque & Chassis...';
      if (lower.includes('central de produtos')) return 'Abrindo Central de Produtos Mestre...';
      if (lower.includes('produtos')) return 'Carregando Catálogo de Produtos...';
      if (lower.includes('pagamentos') || lower.includes('financeiro')) return 'Abrindo Módulo Financeiro...';
      if (lower.includes('importações')) return 'Acessando Importações & Contêineres...';
      if (lower.includes('gestão interna') || lower.includes('governança')) return 'Abrindo Gestão Interna & Governança...';
      if (lower.includes('prospector')) return 'Carregando Prospector B2B...';
      if (lower.includes('radar')) return 'Carregando Radar Comercial...';
      return `Abrindo ${text.slice(0, 32)}...`;
    }
    return 'Carregando...';
  }

  function initDomInterceptors() {
    document.addEventListener('click', (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = e.target.closest('a');
      if (!link) return;

      const href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
      if (link.target === '_blank' || link.hasAttribute('download') || link.dataset.noPreloader !== undefined) return;
      if (link.pathname === window.location.pathname && link.search === window.location.search) return;

      // Feedback instantâneo 0ms no item clicado da Sidebar
      if (link.classList.contains('nav-item')) {
        document.querySelectorAll('.sidebar .nav-item.active').forEach(el => el.classList.remove('active'));
        link.classList.add('active');
      }

      const contextText = extractContextFromLink(link);
      show(contextText, 'MAJ OS', true, true, true);
    });

    document.addEventListener('submit', (e) => {
      if (e.defaultPrevented) return;
      const form = e.target;
      if (!form || form.target === '_blank' || form.dataset.noPreloader !== undefined) return;
      if (typeof form.checkValidity === 'function' && !form.checkValidity()) return;

      const hasFiles = !!form.querySelector('input[type="file"]');
      const msg = hasFiles ? 'Enviando arquivos e processando...' : 'Processando alterações...';
      show(msg, 'MAJ OS', true, true, true);
    });

    window.addEventListener('pageshow', (event) => {
      if (event.persisted) {
        navigationInFlight = false;
        hide(true);
      }
    });
  }

  function handleInitialLoad() {
    getElements();
    initDomInterceptors();

    let isPending = false;
    try {
      const pendingRaw = sessionStorage.getItem(STORAGE_KEY);
      if (pendingRaw) {
        const data = JSON.parse(pendingRaw);
        if (data && Date.now() - (data.ts || 0) < MAX_NAVIGATION_SAFETY_MS) {
          isPending = true;
          if (textEl && data.text) textEl.textContent = data.text;
          if (badgeEl && data.badge) badgeEl.textContent = data.badge;
        }
      }
    } catch (e) {}

    if (isPending || activeFetches > 0) {
      isInitialBootPending = true;
      setProgress(65);
      startTrickle(92);

      const onWindowLoaded = () => {
        setProgress(88);
        scheduleCompletionCheck();
      };

      if (document.readyState === 'complete') {
        onWindowLoaded();
      } else {
        window.addEventListener('load', onWindowLoaded, { once: true });
      }
    } else {
      hide(true);
    }
  }

  // Instala o rastreador de fetch/HTMX imediatamente
  hookNetworkInterceptors();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', handleInitialLoad);
  } else {
    handleInitialLoad();
  }

  window.MOnePreloader = {
    show,
    hide,
    reload,
    navigate
  };
})();
