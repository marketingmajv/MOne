/**
 * M-One Showroom Promo Banner Admin Helpers (static/js/showroom-promo-admin.js)
 */

async function onPromoEnabledChange(checked) {
  const badge = document.getElementById('promoStatusBadge');
  const tabIndicator = document.getElementById('tabPromoStatusIndicator');

  // Feedback visual otimista imediato
  if (badge) {
    if (checked) {
      badge.textContent = '🟢 ATIVO NO SHOWROOM';
      badge.style.background = '#059669';
      badge.style.color = '#ffffff';
      badge.style.border = '1px solid #047857';
      badge.style.boxShadow = '0 2px 6px rgba(5,150,105,0.25)';
    } else {
      badge.textContent = '⚪ DESATIVADO (OCULTO)';
      badge.style.background = '#64748b';
      badge.style.color = '#ffffff';
      badge.style.border = '1px solid #475569';
      badge.style.boxShadow = 'none';
    }
  }
  if (tabIndicator) {
    tabIndicator.textContent = checked ? '🟢 Ativo' : '⚪ Oculto';
  }

  try {
    const res = await fetch('/api/models/promo-banner/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: checked }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro ao alternar status do banner.');

    const toast = document.getElementById('saveToast');
    const toastMsg = document.getElementById('saveToastMsg');
    if (toast && toastMsg) {
      toastMsg.textContent = checked 
        ? '🟢 Banner Black November LIGADO no Showroom!' 
        : '⚪ Banner Black November DESLIGADO no Showroom!';
      toast.style.display = 'flex';
      setTimeout(() => { toast.style.display = 'none'; }, 3000);
    }
  } catch (err) {
    alert('Erro ao alternar status do banner: ' + err.message);
    const cb = document.getElementById('promoEnabled');
    if (cb) cb.checked = !checked;
  }
}

function onStickyTopChange(checked) {
  const badge = document.getElementById('promoStickyTopBadge');
  if (badge) {
    if (checked) {
      badge.textContent = '🟢 CONGELADO NO TOPO';
      badge.style.background = '#d1fae5';
      badge.style.color = '#047857';
      badge.style.border = '1px solid #6ee7b7';
    } else {
      badge.textContent = '⚪ LIVRE (ROLA COM A PÁGINA)';
      badge.style.background = '#f1f5f9';
      badge.style.color = '#64748b';
      badge.style.border = '1px solid #cbd5e1';
    }
  }
}

function onContainerHeightChange(val) {
  const num = Math.max(160, Math.min(360, parseInt(val, 10) || 210));
  const badgeCh = document.getElementById('promoContainerHeightBadge');
  if (badgeCh) badgeCh.textContent = num + 'px';
}

function setContainerHeightPreset(val) {
  const slider = document.getElementById('promoContainerHeight');
  if (slider) {
    slider.value = val;
    onContainerHeightChange(val);
  }
}

function onTickerHeightChange(val) {
  const num = Math.max(20, Math.min(50, parseInt(val, 10) || 35));
  const badgeTh = document.getElementById('promoTickerHeightBadge');
  if (badgeTh) badgeTh.textContent = num + 'px';
}

function setTickerHeightPreset(val) {
  const slider = document.getElementById('promoTickerHeight');
  if (slider) {
    slider.value = val;
    onTickerHeightChange(val);
  }
}

function onTickerSpeedChange(val) {
  const num = Math.max(10, Math.min(60, parseInt(val, 10) || 24));
  const badgeSpd = document.getElementById('promoTickerSpeedBadge');
  if (badgeSpd) badgeSpd.textContent = num + 's por volta';
}

function setTickerSpeedPreset(val) {
  const slider = document.getElementById('promoTickerSpeed');
  if (slider) {
    slider.value = val;
    onTickerSpeedChange(val);
  }
}

function onTickerColorChange(hex) {
  const preview = document.getElementById('promoTickerColorPreview');
  const inputHex = document.getElementById('promoTickerColorHex');
  if (preview) preview.style.color = hex;
  if (inputHex && inputHex.value !== hex) inputHex.value = hex;
}

function onTickerColorHexInput(val) {
  if (val.startsWith('#') && (val.length === 4 || val.length === 7)) {
    const inputColor = document.getElementById('promoTickerColor');
    const preview = document.getElementById('promoTickerColorPreview');
    if (inputColor) inputColor.value = val;
    if (preview) preview.style.color = val;
  }
}

function setTickerColorPreset(hex) {
  const inputColor = document.getElementById('promoTickerColor');
  const inputHex = document.getElementById('promoTickerColorHex');
  const preview = document.getElementById('promoTickerColorPreview');
  if (inputColor) inputColor.value = hex;
  if (inputHex) inputHex.value = hex;
  if (preview) preview.style.color = hex;
}

async function savePromoBannerSettings() {
  const btn = document.getElementById('btnSavePromo');
  const origText = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Salvando...';
  }

  const rawContainerHeight = parseInt(document.getElementById('promoContainerHeight')?.value, 10) || 210;
  const clampedContainerHeight = Math.max(160, Math.min(360, rawContainerHeight));
  const stickyTop = document.getElementById('promoStickyTop')?.checked ?? false;
  const rawHeight = parseInt(document.getElementById('promoTickerHeight')?.value, 10) || 35;
  const clampedHeight = Math.max(20, Math.min(50, rawHeight));
  const rawSpeed = parseInt(document.getElementById('promoTickerSpeed')?.value, 10) || 24;
  const clampedSpeed = Math.max(10, Math.min(60, rawSpeed));
  const tickerColor = document.getElementById('promoTickerColor')?.value || '#00e599';

  const payload = {
    enabled: document.getElementById('promoEnabled').checked,
    sticky_top: stickyTop,
    container_height: clampedContainerHeight,
    banner_image: document.getElementById('promoBannerImage')?.value?.trim() || '',
    ticker_height: clampedHeight,
    ticker_speed: clampedSpeed,
    ticker_color: tickerColor,
    tag_text: document.getElementById('promoTagText')?.value?.trim() || '',
    ticker_text: document.getElementById('promoTickerText')?.value?.trim() || '',
    headline: document.getElementById('promoHeadline')?.value?.trim() || '',
    subheadline: document.getElementById('promoSubheadline')?.value?.trim() || '',
    highlight_1: document.getElementById('promoHighlight1')?.value?.trim() ?? '',
    highlight_2: document.getElementById('promoHighlight2')?.value?.trim() ?? '',
    cta_text: document.getElementById('promoCtaText')?.value?.trim() || '',
    cta_url: document.getElementById('promoCtaUrl')?.value?.trim() || '',
  };

  try {
    const res = await fetch('/api/models/promo-banner', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro ao salvar promoção.');

    const badge = document.getElementById('promoStatusBadge');
    const tabIndicator = document.getElementById('tabPromoStatusIndicator');
    if (badge) {
      if (payload.enabled) {
        badge.textContent = '🟢 ATIVO NO SHOWROOM';
        badge.style.background = '#059669';
        badge.style.color = '#ffffff';
        badge.style.border = '1px solid #047857';
        badge.style.boxShadow = '0 2px 6px rgba(5,150,105,0.25)';
      } else {
        badge.textContent = '⚪ DESATIVADO (OCULTO)';
        badge.style.background = '#64748b';
        badge.style.color = '#ffffff';
        badge.style.border = '1px solid #475569';
        badge.style.boxShadow = 'none';
      }
    }
    if (tabIndicator) {
      tabIndicator.textContent = payload.enabled ? '🟢 Ativo' : '⚪ Oculto';
    }

    const toast = document.getElementById('saveToast');
    const toastMsg = document.getElementById('saveToastMsg');
    if (toast && toastMsg) {
      toastMsg.textContent = '✅ Configurações e estilo da faixa Black November salvos com sucesso!';
      toast.style.display = 'flex';
      setTimeout(() => { toast.style.display = 'none'; }, 4000);
    }
  } catch (err) {
    alert('Erro ao salvar promoção: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }
}
