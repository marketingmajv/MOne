/**
 * Gestão do Showroom M-One (static/js/showroom-admin.js)
 * Controle de abas setorizadas, ordenação drag-and-drop de modelos e chamadas de API.
 */

let draggedItem = null;
let currentMenuMode = window.SHOWROOM_ADMIN_CONFIG?.mode || 'category';
let currentCategoryOrder = window.SHOWROOM_ADMIN_CONFIG?.categoryOrder || ['Scooter', 'Bike'];

function switchMainTab(tabKey, updateUrl = true) {
  const tabs = ['modelos', 'inativos', 'promo', 'tv'];
  if (!tabs.includes(tabKey)) tabKey = 'modelos';

  tabs.forEach(t => {
    const btn = document.getElementById('tabNav' + t.charAt(0).toUpperCase() + t.slice(1));
    const sec = document.getElementById('sector' + t.charAt(0).toUpperCase() + t.slice(1));
    if (btn) btn.classList.toggle('active', t === tabKey);
    if (sec) sec.style.display = (t === tabKey) ? 'block' : 'none';
  });

  const btnTop = document.getElementById('btnSaveOrderTop');
  if (btnTop) {
    btnTop.style.display = (tabKey === 'modelos') ? 'inline-flex' : 'none';
  }

  localStorage.setItem('admin_models_active_tab', tabKey);
  if (updateUrl && window.history && window.history.replaceState) {
    window.history.replaceState(null, '', '#' + tabKey);
  }
}

function setMenuMode(mode) {
  currentMenuMode = mode;
  const isFree = mode === 'free';
  const btnCat = document.getElementById('tabBtnCategory');
  const btnFree = document.getElementById('tabBtnFree');
  const panCat = document.getElementById('panelMenuCategory');
  const panFree = document.getElementById('panelMenuFree');
  const txtActive = document.getElementById('modeActiveText');

  if (btnCat) btnCat.className = `btn ${!isFree ? 'primary' : 'secondary'}`;
  if (btnFree) btnFree.className = `btn ${isFree ? 'primary' : 'secondary'}`;
  if (panCat) panCat.style.display = !isFree ? 'block' : 'none';
  if (panFree) panFree.style.display = isFree ? 'block' : 'none';
  if (txtActive) txtActive.textContent = isFree ? 'Livre / Aleatório' : 'Por Categoria';
}

function invertCategoryGroups() {
  currentCategoryOrder.reverse();
  const wrapper = document.getElementById('categoryGroupsWrapper');
  if (wrapper && wrapper.children.length >= 2) {
    wrapper.insertBefore(wrapper.children[1], wrapper.children[0]);
  }
  updatePositionBadges();
  showToast(`Ordem dos grupos invertida: ${currentCategoryOrder.join(' ⇄ ')}. Clique em salvar para aplicar.`, true);
}

function shuffleFreeModelsList() {
  const container = document.getElementById('sortableFreeModelsList');
  if (!container) return;
  const items = Array.from(container.children);
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    container.appendChild(items[j]);
    items.splice(j, 1);
  }
  updatePositionBadges();
  showToast('Ordem aleatória sorteada! Clique em salvar para aplicar na vitrine.', true);
}

function initSortable() {
  document.querySelectorAll('.sortable-models-container').forEach(container => {
    container.addEventListener('dragstart', (e) => {
      const item = e.target.closest('.model-sort-item');
      if (!item) return;
      draggedItem = item;
      item.style.opacity = '0.4';
      e.dataTransfer.effectAllowed = 'move';
    });

    container.addEventListener('dragend', (e) => {
      const item = e.target.closest('.model-sort-item');
      if (item) item.style.opacity = '1';
      document.querySelectorAll('.model-sort-item').forEach(el => el.classList.remove('drag-over'));
      draggedItem = null;
      updatePositionBadges();
    });

    container.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const targetItem = e.target.closest('.model-sort-item');
      if (!targetItem || targetItem === draggedItem) return;

      const bounding = targetItem.getBoundingClientRect();
      const offset = bounding.y + bounding.height / 2;
      if (e.clientY - offset > 0) {
        targetItem.after(draggedItem);
      } else {
        targetItem.before(draggedItem);
      }
    });
  });
}

function moveModelItem(btn, direction) {
  const item = btn.closest('.model-sort-item');
  if (!item) return;
  if (direction === -1 && item.previousElementSibling) {
    item.parentNode.insertBefore(item, item.previousElementSibling);
  } else if (direction === 1 && item.nextElementSibling) {
    item.parentNode.insertBefore(item.nextElementSibling, item);
  }
  updatePositionBadges();
}

function moveModelToTop(btn) {
  const item = btn.closest('.model-sort-item');
  if (!item || !item.parentNode) return;
  item.parentNode.insertBefore(item, item.parentNode.firstElementChild);
  updatePositionBadges();
}

function updatePositionBadges() {
  const activeContainer = currentMenuMode === 'free' 
    ? [document.getElementById('sortableFreeModelsList')]
    : document.querySelectorAll('.cat-sortable-list');

  let globalPos = 1;
  activeContainer.forEach(container => {
    if (!container) return;
    Array.from(container.children).forEach(card => {
      const badge = card.querySelector('.model-pos-badge');
      if (badge) badge.textContent = `#${globalPos}`;
      globalPos++;
    });
  });
}

function refreshTabAndCategoryCounts() {
  const freeList = document.getElementById('sortableFreeModelsList');
  const inactiveList = document.getElementById('inactiveModelsList');
  const emptyInactive = document.getElementById('inactiveEmptyState');
  const activeCount = freeList ? freeList.querySelectorAll('.model-sort-item').length : 0;
  const inactiveCount = inactiveList ? inactiveList.querySelectorAll('.model-sort-item').length : 0;

  const badgeActive = document.getElementById('tabActiveModelsBadge');
  const badgeInactive = document.getElementById('tabInactiveModelsBadge');
  if (badgeActive) badgeActive.textContent = `${activeCount} ativos`;
  if (badgeInactive) badgeInactive.textContent = `${inactiveCount} inativos`;
  if (emptyInactive) emptyInactive.style.display = inactiveCount > 0 ? 'none' : 'block';

  document.querySelectorAll('.cat-sortable-list').forEach(container => {
    const cat = container.dataset.cat;
    const count = container.querySelectorAll('.model-sort-item').length;
    const catBadge = document.querySelector(`[data-cat-count="${cat}"]`);
    if (catBadge) catBadge.textContent = `${count} modelos`;
  });
}

async function toggleModelActive(slug, isActive) {
  try {
    const res = await fetch(`/api/models/${slug}/toggle-active`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: isActive })
    });
    if (!res.ok) {
      showToast('Erro ao atualizar status do modelo', false);
      return;
    }

    const inactiveList = document.getElementById('inactiveModelsList');
    const freeList = document.getElementById('sortableFreeModelsList');

    if (!isActive) {
      const activeCards = document.querySelectorAll(`#sectorModelos .model-sort-item[data-slug="${slug}"]`);
      if (activeCards.length > 0 && inactiveList) {
        const cardClone = activeCards[0].cloneNode(true);
        cardClone.querySelectorAll(`.status-chk-${slug}`).forEach(chk => { chk.checked = false; });
        cardClone.querySelectorAll(`.lbl-status-${slug}`).forEach(lbl => {
          lbl.textContent = 'Inativo';
          lbl.style.color = '#c62828';
        });
        inactiveList.appendChild(cardClone);
        activeCards.forEach(c => c.remove());
      }
      showToast(`Modelo ${slug.toUpperCase()} movido para a aba 📦 Modelos Inativos!`, true);
    } else {
      const inactiveCard = document.querySelector(`#inactiveModelsList .model-sort-item[data-slug="${slug}"]`);
      if (inactiveCard) {
        const cat = inactiveCard.dataset.categoria || 'Scooter';
        const catContainer = document.querySelector(`.cat-sortable-list[data-cat="${cat}"]`) || document.querySelector('.cat-sortable-list');
        inactiveCard.querySelectorAll(`.status-chk-${slug}`).forEach(chk => { chk.checked = true; });
        inactiveCard.querySelectorAll(`.lbl-status-${slug}`).forEach(lbl => {
          lbl.textContent = 'Ativo';
          lbl.style.color = '#2e7d32';
        });
        if (catContainer) catContainer.appendChild(inactiveCard.cloneNode(true));
        if (freeList) freeList.appendChild(inactiveCard.cloneNode(true));
        inactiveCard.remove();
      }
      showToast(`Modelo ${slug.toUpperCase()} reativado e devolvido à lista principal!`, true);
    }

    refreshTabAndCategoryCounts();
    updatePositionBadges();
  } catch (err) {
    showToast('Erro de conexão: ' + err.message, false);
  }
}

async function toggleModelBannerType(slug, btnEl, forcedType = null) {
  const targetType = forcedType || (btnEl?.dataset?.currentType === 'promocional' ? 'atemporal' : 'promocional');
  if (window.MOnePreloader) {
    window.MOnePreloader.show(
      `Aplicando Banner ${targetType === 'promocional' ? 'Promocional' : 'Atemporal'} em ${slug.toUpperCase()}...`,
      'SHOWROOM MAJ',
      true
    );
  }
  try {
    const res = await fetch(`/api/models/${slug}/toggle-banner-type`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: targetType })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro ao alternar banner.');

    if (data.status === 'missing_promo') {
      if (window.MOnePreloader) window.MOnePreloader.hide();
      showToast(data.message || 'Envie o 2º Banner Promocional primeiro.', false);
      if (typeof openEditModelModal === 'function') openEditModelModal(slug);
      return;
    }

    const isPromo = data.effective_banner_type === 'promocional';
    document.querySelectorAll(`[data-banner-group="${slug}"]`).forEach(grp => {
      const btnAtemp = grp.querySelector('[data-banner-opt="atemporal"]');
      const btnPromo = grp.querySelector('[data-banner-opt="promocional"]');
      if (btnAtemp) {
        btnAtemp.innerHTML = `${!isPromo ? '✅ ' : ''}🏛️ ATEMPORAL`;
        btnAtemp.style.background = !isPromo ? '#00e599' : 'transparent';
        btnAtemp.style.color = !isPromo ? '#000' : 'var(--text-muted)';
        btnAtemp.style.border = !isPromo ? '1.5px solid #00e599' : '1px solid transparent';
        btnAtemp.style.boxShadow = !isPromo ? '0 0 10px rgba(0,229,153,0.35)' : 'none';
        btnAtemp.style.opacity = !isPromo ? '1' : '0.48';
      }
      if (btnPromo) {
        btnPromo.innerHTML = `${isPromo ? '✅ ' : ''}⚡ PROMO`;
        btnPromo.style.background = isPromo ? '#ffb703' : 'transparent';
        btnPromo.style.color = isPromo ? '#000' : 'var(--text-muted)';
        btnPromo.style.border = isPromo ? '1.5px solid #ffb703' : '1px solid transparent';
        btnPromo.style.boxShadow = isPromo ? '0 0 10px rgba(255,183,3,0.4)' : 'none';
        btnPromo.style.opacity = isPromo ? '1' : '0.48';
      }
    });

    if (data.display_image) {
      document.querySelectorAll(`img[data-thumb-slug="${slug}"]`).forEach(img => {
        img.src = data.display_image;
      });
    }
    showToast(`Banner de ${slug.toUpperCase()} alterado para ${isPromo ? '⚡ PROMOCIONAL' : '🏛️ ATEMPORAL'}!`, true);
  } catch (err) {
    showToast('Falha ao alternar banner: ' + err.message, false);
  } finally {
    if (window.MOnePreloader) window.MOnePreloader.hide();
  }
}

async function saveNewOrder() {
  const btn = document.getElementById('btnSaveOrder');
  const btnTop = document.getElementById('btnSaveOrderTop');
  if (btn) btn.disabled = true;
  if (btnTop) btnTop.disabled = true;

  let order = [];
  if (currentMenuMode === 'free') {
    const items = document.querySelectorAll('#sortableFreeModelsList .model-sort-item');
    order = Array.from(items).map(item => item.dataset.slug);
  } else {
    document.querySelectorAll('.cat-sortable-list').forEach(container => {
      Array.from(container.children).forEach(item => {
        if (item.dataset && item.dataset.slug) order.push(item.dataset.slug);
      });
    });
  }

  const payload = {
    mode: currentMenuMode,
    category_order: currentCategoryOrder,
    order: order,
    updated_at: new Date().toISOString()
  };

  try {
    const res = await fetch('/api/models/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showToast('Ordem e configurações do mostruário salvas com sucesso!', true);
    } else {
      showToast('Erro ao salvar a ordem dos modelos', false);
    }
  } catch (err) {
    showToast('Erro de conexão: ' + err.message, false);
  } finally {
    if (btn) btn.disabled = false;
    if (btnTop) btnTop.disabled = false;
  }
}

async function resetToDefaultOrder() {
  if (!confirm('Deseja realmente restaurar a ordenação padrão original?')) return;
  try {
    const res = await fetch('/api/models/order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'category', category_order: ['Scooter', 'Bike'], order: [] })
    });
    if (res.ok) {
      showToast('Ordem restaurada com sucesso! Recarregando página...', true);
      setTimeout(() => window.location.reload(), 1000);
    }
  } catch (err) {
    showToast('Erro ao resetar: ' + err.message, false);
  }
}

async function saveKioskSettings() {
  const enabled = document.getElementById('kioskEnabled').checked;
  const interval_seconds = parseInt(document.getElementById('kioskInterval').value, 10);
  const auto_pause_seconds = parseInt(document.getElementById('kioskAutoPause').value, 10);
  try {
    const res = await fetch('/api/models/kiosk-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled, interval_seconds, auto_pause_seconds, transition_effect: 'slide_apple' })
    });
    if (res.ok) {
      const badge = document.getElementById('kioskStatusBadge');
      const navBadge = document.getElementById('tabTvStatusIndicator');
      const text = enabled ? '🟢 Autoplay Ativo' : '⚪ Desativado';
      if (badge) {
        badge.textContent = text;
        badge.style.background = enabled ? 'rgba(0,229,153,0.15)' : 'rgba(148,163,184,0.15)';
        badge.style.color = enabled ? '#00e599' : '#94a3b8';
        badge.style.borderColor = enabled ? 'rgba(0,229,153,0.3)' : 'rgba(148,163,184,0.3)';
      }
      if (navBadge) navBadge.textContent = text;
      showToast('Configurações do Modo TV salvas com sucesso!', true);
    } else {
      showToast('Erro ao salvar configurações do Modo TV', false);
    }
  } catch (err) {
    showToast('Erro de conexão: ' + err.message, false);
  }
}

function showToast(msg, isSuccess) {
  const toast = document.getElementById('saveToast');
  const msgEl = document.getElementById('saveToastMsg');
  if (!toast || !msgEl) return;
  toast.style.background = isSuccess ? 'rgba(46,125,50,0.15)' : 'rgba(198,40,40,0.15)';
  toast.style.borderColor = isSuccess ? '#2e7d32' : '#c62828';
  msgEl.textContent = (isSuccess ? '✅ ' : '⚠️ ') + msg;
  toast.style.display = 'flex';
  setTimeout(() => { toast.style.display = 'none'; }, 4000);
}

document.addEventListener('DOMContentLoaded', () => {
  initSortable();
  updatePositionBadges();

  const hash = (window.location.hash || '').replace('#', '').toLowerCase();
  const savedTab = localStorage.getItem('admin_models_active_tab');
  const validTabs = ['modelos', 'inativos', 'promo', 'tv'];
  const initialTab = validTabs.includes(hash) ? hash : (validTabs.includes(savedTab) ? savedTab : 'modelos');
  switchMainTab(initialTab, false);
});
