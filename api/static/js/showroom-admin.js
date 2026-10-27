/**
 * Gestão do Showroom M-One (static/js/showroom-admin.js)
 * Controle de abas setorizadas, ordenação drag-and-drop de modelos e chamadas de API.
 */

let draggedItem = null;
let currentMenuMode = window.SHOWROOM_ADMIN_CONFIG?.mode || 'category';
let currentCategoryOrder = window.SHOWROOM_ADMIN_CONFIG?.categoryOrder || ['Scooter', 'Bike'];

function switchMainTab(tabKey, updateUrl = true) {
  const tabs = ['modelos', 'promo', 'tv'];
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

async function toggleModelActive(slug, isActive) {
  const lbl = document.getElementById(`lbl-status-${slug}`);
  try {
    const res = await fetch(`/api/models/${slug}/toggle-active`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: isActive })
    });
    if (res.ok) {
      if (lbl) {
        lbl.textContent = isActive ? 'Ativo' : 'Inativo';
        lbl.style.color = isActive ? '#2e7d32' : '#c62828';
      }
      showToast(`Modelo ${slug} ${isActive ? 'ativado' : 'inativado'} com sucesso!`, true);
    } else {
      showToast('Erro ao atualizar status do modelo', false);
    }
  } catch (err) {
    showToast('Erro de conexão: ' + err.message, false);
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
  const validTabs = ['modelos', 'promo', 'tv'];
  const initialTab = validTabs.includes(hash) ? hash : (validTabs.includes(savedTab) ? savedTab : 'modelos');
  switchMainTab(initialTab, false);
});
