/**
 * M-One Version Manager & Changelog Modal Controller
 * Gerencia a exibição automática de novidades em primeira abertura e acesso contínuo pela sidebar.
 */
(function () {
  'use strict';

  function getCurrentBuild() {
    const metaTag = document.querySelector('meta[name="mone-build"]');
    return metaTag ? metaTag.content : '1.0.0';
  }

  function getStorageKey() {
    return 'mone_last_seen_build';
  }

  window.switchVersionView = function (viewName) {
    const summaryView = document.getElementById('versionSummaryView');
    const detailsView = document.getElementById('versionDetailsView');
    const tabSummary = document.getElementById('versionTabSummary');
    const tabDetails = document.getElementById('versionTabDetails');
    const toggleBtn = document.getElementById('versionAltToggleBtn');

    if (!summaryView || !detailsView) return;

    if (viewName === 'details') {
      summaryView.style.display = 'none';
      detailsView.style.display = 'block';
      if (tabSummary) tabSummary.classList.remove('active');
      if (tabDetails) tabDetails.classList.add('active');
      if (toggleBtn) toggleBtn.innerHTML = '📋 Ver destaques resumidos';
    } else {
      summaryView.style.display = 'block';
      detailsView.style.display = 'none';
      if (tabSummary) tabSummary.classList.add('active');
      if (tabDetails) tabDetails.classList.remove('active');
      if (toggleBtn) toggleBtn.innerHTML = '🔍 Ver changelog completo';
    }
  };

  window.toggleVersionView = function () {
    const detailsView = document.getElementById('versionDetailsView');
    if (!detailsView) return;
    const isDetailsVisible = detailsView.style.display !== 'none';
    window.switchVersionView(isDetailsVisible ? 'summary' : 'details');
  };

  window.openVersionModal = function (showDetails = false) {
    const modal = document.getElementById('versionModal');
    if (!modal) return;

    window.switchVersionView(showDetails ? 'details' : 'summary');
    modal.classList.add('show');
    modal.style.display = 'flex';
    modal.style.alignItems = 'center';
    modal.style.justifyContent = 'center';
    document.body.style.overflow = 'hidden';
  };

  window.closeVersionModal = function (markSeen = true) {
    const modal = document.getElementById('versionModal');
    if (!modal) return;

    modal.classList.remove('show');
    modal.style.display = 'none';
    document.body.style.overflow = '';

    if (markSeen) {
      try {
        const currentBuild = getCurrentBuild();
        localStorage.setItem(getStorageKey(), currentBuild);
      } catch (err) {
        console.warn('[M-One Version] Falha ao salvar no localStorage:', err);
      }
    }
  };

  // Fechar no ESC
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      const modal = document.getElementById('versionModal');
      if (modal && modal.style.display !== 'none') {
        window.closeVersionModal(true);
      }
    }
  });

  // Verificação de primeira abertura após nova versão/build
  document.addEventListener('DOMContentLoaded', function () {
    try {
      const currentBuild = getCurrentBuild();
      const lastSeen = localStorage.getItem(getStorageKey());

      // Se é a primeira vez que o usuário acessa esta build
      if (lastSeen !== currentBuild) {
        // Pequeno delay para suavidade após o carregamento inicial da página
        setTimeout(function () {
          window.openVersionModal(false);
        }, 700);
      }
    } catch (err) {
      console.warn('[M-One Version] Erro na checagem de versão:', err);
    }
  });
})();
