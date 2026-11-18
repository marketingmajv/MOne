/**
 * M-One Support Banner Toggle (static/js/support-banner-toggle.js)
 * Controla a preferência persistente do banner urgente de suporte no painel administrativo.
 */

window.toggleSupportBannerPref = async function (btn) {
  if (!btn) return;
  const current = btn.dataset.enabled === 'true';
  const next = !current;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('input[name="csrf_token"]')?.value || '';
  btn.disabled = true;
  try {
    const res = await fetch('/api/suporte/banner-toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify({ enabled: next, csrf_token: csrf }),
    });
    const data = await res.json();
    if (data.success) {
      const enabled = !!data.banner_enabled;
      btn.dataset.enabled = enabled ? 'true' : 'false';
      btn.innerHTML = enabled ? '🔔 Banner: Ativo' : '🔕 Banner: Oculto';
      btn.style.borderColor = enabled ? '#10b981' : 'var(--line)';
      btn.style.color = enabled ? '#10b981' : 'var(--muted)';
      try { sessionStorage.removeItem('mone_support_badges_cache'); } catch (e) {}
    } else {
      alert(data.error || 'Não foi possível alterar a preferência do banner.');
    }
  } catch (e) {
    console.error('Erro ao alternar banner:', e);
  } finally {
    btn.disabled = false;
  }
};
