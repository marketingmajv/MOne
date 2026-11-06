/**
 * M-One MAJ OS Creative Preloader Controller (static/js/preloader.js)
 * Sistema de Pré-Loader Soberano com Handoff Contínuo via SessionStorage.
 * Elimina o vazio entre recargas de página, telas brancas e encerramentos prematuros.
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'mone_preloader_pending';
  const MAX_PENDING_AGE_MS = 12000;

  let preloaderEl = null;
  let textEl = null;
  let badgeEl = null;
  let timeoutId = null;
  let messageCycleInterval = null;
  let safetyTimeout = null;
  let showStartTime = 0;

  const STATUS_MESSAGES = [
    'Sincronizando com MAJ Operating System...',
    'Otimizando dados operacionais...',
    'Conectando ao banco de dados...',
    'Preparando ambiente de trabalho...',
    'Validando integridade de dados...'
  ];

  function getElements() {
    if (!preloaderEl) {
      preloaderEl = document.getElementById('monePreloader');
      if (preloaderEl) {
        textEl = preloaderEl.querySelector('.mone-preloader-text');
        badgeEl = preloaderEl.querySelector('.mone-preloader-badge');
      }
    }
    return !!preloaderEl;
  }

  function setPendingStorage(text, badge) {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          text: text || 'Processando...',
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

  function show(customText, customBadge, immediate = false, persist = true) {
    if (!getElements()) return;

    clearTimeout(timeoutId);
    clearInterval(messageCycleInterval);
    clearTimeout(safetyTimeout);
    showStartTime = Date.now();

    const text = customText || (textEl ? textEl.textContent : 'Carregando...');
    const badge = customBadge || (badgeEl ? badgeEl.textContent : 'MAJ OS');

    if (persist) {
      setPendingStorage(text, badge);
    }

    const activate = () => {
      if (textEl && text) textEl.textContent = text;
      if (badgeEl && badge) badgeEl.textContent = badge;

      document.documentElement.classList.add('mone-preloader-active');
      preloaderEl.classList.add('active');
      preloaderEl.setAttribute('aria-hidden', 'false');

      // Ciclo contextual se demorar > 1.4s
      let msgIndex = 0;
      messageCycleInterval = setInterval(() => {
        if (textEl && (preloaderEl.classList.contains('active') || document.documentElement.classList.contains('mone-preloader-active'))) {
          textEl.style.opacity = '0';
          setTimeout(() => {
            textEl.textContent = STATUS_MESSAGES[msgIndex % STATUS_MESSAGES.length];
            textEl.style.opacity = '1';
            msgIndex++;
          }, 180);
        }
      }, 1500);

      // Trava de segurança contra downloads ou conexões abortadas
      safetyTimeout = setTimeout(() => {
        hide(true);
      }, MAX_PENDING_AGE_MS);
    };

    if (immediate) {
      activate();
    } else {
      timeoutId = setTimeout(activate, 120);
    }
  }

  function hide(force = false) {
    clearTimeout(timeoutId);
    clearInterval(messageCycleInterval);
    clearTimeout(safetyTimeout);
    clearPendingStorage();

    const doDismiss = () => {
      document.documentElement.classList.remove('mone-preloader-active');
      if (getElements()) {
        preloaderEl.classList.remove('active');
        preloaderEl.setAttribute('aria-hidden', 'true');
      }
    };

    if (force) {
      doDismiss();
      return;
    }

    // Garante tempo mínimo visível de 260ms se acabou de ser acionado, para não piscar
    const elapsed = Date.now() - showStartTime;
    const minWait = 260;
    if (elapsed < minWait && showStartTime > 0) {
      setTimeout(doDismiss, minWait - elapsed);
    } else {
      doDismiss();
    }
  }

  /**
   * Dispara recarga de página mantendo o pré-loader ativo de ponta a ponta sem vazio
   */
  function reload(customText = 'Atualizando página...', customBadge = 'MAJ OS') {
    show(customText, customBadge, true, true);
    setTimeout(() => {
      window.location.reload();
    }, 40);
  }

  /**
   * Navega para outra rota com transição suave imediata
   */
  function navigate(url, customText = 'Carregando...', customBadge = 'MAJ OS') {
    if (!url) return;
    show(customText, customBadge, true, true);
    setTimeout(() => {
      window.location.href = url;
    }, 40);
  }

  function extractContextFromLink(a) {
    const text = (a.innerText || a.textContent || '').trim();
    if (text) {
      const lower = text.toLowerCase();
      if (lower.includes('visão geral') || lower.includes('dashboard')) return 'Abrindo Visão Geral...';
      if (lower.includes('vendas')) return 'Abrindo Vendas...';
      if (lower.includes('fretes')) return 'Sincronizando Fretes...';
      if (lower.includes('estoque')) return 'Carregando Estoque & Chassis...';
      if (lower.includes('produtos')) return 'Carregando Catálogo de Produtos...';
      if (lower.includes('central de produtos')) return 'Abrindo Central de Produtos Mestre...';
      if (lower.includes('pagamentos') || lower.includes('financeiro')) return 'Abrindo Módulo Financeiro...';
      if (lower.includes('importações')) return 'Acessando Importações & Contêineres...';
      if (lower.includes('usuários')) return 'Gerenciando Usuários & Acessos...';
      if (lower.includes('auditoria')) return 'Carregando Logs de Auditoria...';
      if (lower.includes('copilot')) return 'Conectando ao Copilot IA...';
      if (lower.includes('infra')) return 'Acessando Painel de Infraestrutura...';
      if (lower.includes('conexões')) return 'Abrindo Hub de Conexões...';
      if (lower.includes('bling')) return 'Sincronizando com Bling ERP...';
      return `Carregando ${text}...`;
    }
    return 'Carregando...';
  }

  function initInterceptors() {
    // Intercepta cliques de navegação em links reais
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a');
      if (!link) return;

      const href = link.getAttribute('href');
      if (!href) return;
      if (href.startsWith('#') || href.startsWith('javascript:') || link.target === '_blank') return;
      if (link.hasAttribute('download') || link.dataset.noPreloader !== undefined) return;
      if (link.pathname === window.location.pathname && link.search === window.location.search) return;

      const contextText = extractContextFromLink(link);
      show(contextText, 'MAJ OS', false, true);
    });

    // Intercepta submissões normais de formulário
    document.addEventListener('submit', (e) => {
      const form = e.target;
      if (form.target === '_blank' || form.dataset.noPreloader !== undefined) return;

      // Se a validação HTML5 falhar (ex: campo required vazio), não dispara o pré-loader
      if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
        return;
      }

      const hasFiles = !!form.querySelector('input[type="file"]');
      const msg = hasFiles ? 'Enviando arquivos e processando...' : 'Processando alterações...';
      show(msg, 'MAJ OS', true, true);
    });

    // Ao voltar pelo histórico do navegador (bfcache)
    window.addEventListener('pageshow', (event) => {
      if (event.persisted) {
        hide(true);
      }
    });
  }

  // Inicialização inteligente e encerramento com Handoff Suave
  function handleInitialLoad() {
    getElements();
    initInterceptors();

    let isPending = false;
    try {
      const pendingRaw = sessionStorage.getItem(STORAGE_KEY);
      if (pendingRaw) {
        const data = JSON.parse(pendingRaw);
        if (data && Date.now() - (data.ts || 0) < MAX_PENDING_AGE_MS) {
          isPending = true;
          if (textEl && data.text) textEl.textContent = data.text;
          if (badgeEl && data.badge) badgeEl.textContent = data.badge;
        }
      }
    } catch (e) {}

    if (isPending) {
      // Se veio de uma ação anterior, mantém o pré-loader na tela até o carregamento completo
      const finalizeDismissal = () => {
        setTimeout(() => {
          hide();
        }, 300); // 300ms de exibição confirmada para o usuário ter certeza do sucesso
      };

      if (document.readyState === 'complete') {
        finalizeDismissal();
      } else {
        window.addEventListener('load', finalizeDismissal, { once: true });
        // Fallback de segurança caso window.load demore por causa de imagens terciárias
        setTimeout(finalizeDismissal, 2000);
      }
    } else {
      // Visita direta inicial: fecha imediatamente
      hide(true);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', handleInitialLoad);
  } else {
    handleInitialLoad();
  }

  // API Global Soberana do MAJ OS
  window.MOnePreloader = {
    show,
    hide,
    reload,
    navigate
  };
})();
