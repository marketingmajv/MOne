/**
 * M-One MAJ OS Creative Preloader Controller (static/js/preloader.js)
 * Gerencia transições visuais com anti-flicker (150ms), micro-status contextuais e suporte dual-theme.
 */
(function () {
  'use strict';

  let preloaderEl = null;
  let textEl = null;
  let badgeEl = null;
  let timeoutId = null;
  let messageCycleInterval = null;
  let safetyTimeout = null;

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

  function show(customText, customBadge) {
    if (!getElements()) return;

    clearTimeout(timeoutId);
    clearInterval(messageCycleInterval);
    clearTimeout(safetyTimeout);

    // Anti-flicker delay de 150ms
    timeoutId = setTimeout(() => {
      if (textEl && customText) {
        textEl.textContent = customText;
      }
      if (badgeEl && customBadge) {
        badgeEl.textContent = customBadge;
      }

      preloaderEl.classList.add('active');
      preloaderEl.setAttribute('aria-hidden', 'false');

      // Ciclo de frases contextuais do MAJ OS se a latência persistir (> 1.2s)
      let msgIndex = 0;
      messageCycleInterval = setInterval(() => {
        if (textEl && preloaderEl.classList.contains('active')) {
          textEl.style.opacity = '0';
          setTimeout(() => {
            textEl.textContent = STATUS_MESSAGES[msgIndex % STATUS_MESSAGES.length];
            textEl.style.opacity = '1';
            msgIndex++;
          }, 180);
        }
      }, 1400);

      // Trava de segurança contra downloads ou links abortados
      safetyTimeout = setTimeout(() => {
        hide();
      }, 10000);
    }, 150);
  }

  function hide() {
    clearTimeout(timeoutId);
    clearInterval(messageCycleInterval);
    clearTimeout(safetyTimeout);

    if (!getElements()) return;
    preloaderEl.classList.remove('active');
    preloaderEl.setAttribute('aria-hidden', 'true');
  }

  function extractContextFromLink(a) {
    const text = (a.innerText || a.textContent || '').trim();
    if (text) {
      if (text.toLowerCase().includes('visão geral') || text.toLowerCase().includes('dashboard')) return 'Abrindo Visão Geral...';
      if (text.toLowerCase().includes('vendas')) return 'Abrindo Vendas...';
      if (text.toLowerCase().includes('fretes')) return 'Sincronizando Fretes...';
      if (text.toLowerCase().includes('estoque')) return 'Carregando Estoque & Chassis...';
      if (text.toLowerCase().includes('produtos')) return 'Carregando Catálogo de Produtos...';
      if (text.toLowerCase().includes('pagamentos')) return 'Abrindo Módulo Financeiro...';
      if (text.toLowerCase().includes('importações')) return 'Acessando Importações & Contêineres...';
      if (text.toLowerCase().includes('usuários')) return 'Gerenciando Usuários & Acessos...';
      if (text.toLowerCase().includes('auditoria')) return 'Carregando Logs de Auditoria...';
      if (text.toLowerCase().includes('copilot')) return 'Conectando ao Copilot IA...';
      if (text.toLowerCase().includes('infra')) return 'Acessando Painel de Infraestrutura...';
      if (text.toLowerCase().includes('conexões')) return 'Abrindo Hub de Conexões...';
      if (text.toLowerCase().includes('bling')) return 'Sincronizando com Bling ERP...';
      return `Carregando ${text}...`;
    }
    return 'Carregando...';
  }

  function initInterceptors() {
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a');
      if (!link) return;

      const href = link.getAttribute('href');
      if (!href) return;
      if (href.startsWith('#') || href.startsWith('javascript:') || link.target === '_blank') return;
      if (link.hasAttribute('download') || link.dataset.noPreloader !== undefined) return;

      // Se for o mesmo caminho da URL atual, ignorar
      if (link.pathname === window.location.pathname && link.search === window.location.search) return;

      const contextText = extractContextFromLink(link);
      show(contextText, 'MAJ OS');
    });

    document.addEventListener('submit', (e) => {
      const form = e.target;
      if (form.target === '_blank' || form.dataset.noPreloader !== undefined) return;
      show('Processando dados...', 'MAJ OS');
    });

    window.addEventListener('pageshow', () => {
      hide();
    });
  }

  // Inicialização no DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      getElements();
      initInterceptors();
      hide();
    });
  } else {
    getElements();
    initInterceptors();
    hide();
  }

  window.MOnePreloader = { show, hide };
})();
