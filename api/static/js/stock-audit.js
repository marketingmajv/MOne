/**
 * M-One Stock Audit Controller (static/js/stock-audit.js)
 * Gerencia conferência contínua por bipagem, feedback sonoro/visual e relatório PDF.
 */

function stockAuditApp() {
  return {
    open: false,
    loading: false,
    locationScope: 'COLVIX',
    locations: ['Galpão MAJ', 'COLVIX', 'Depósito Consolação'],
    activeSummary: null,
    recentAudits: [],
    scanInput: '',
    lastFeedback: null,
    finishing: false,

    async openAuditModal() {
      this.open = true;
      await this.loadState();
      this.$nextTick(() => this.focusScan());
    },

    closeAuditModal() {
      this.open = false;
    },

    focusScan() {
      const el = document.getElementById('stock_audit_scan_input');
      if (el) {
        el.focus();
      }
    },

    async loadState() {
      this.loading = true;
      try {
        const res = await fetch('/stock/audit/state');
        const data = await res.json();
        if (data.ok) {
          this.locations = data.locations || this.locations;
          this.activeSummary = data.active || null;
          this.recentAudits = data.recent || [];
        }
      } catch (e) {
        console.error('Erro ao carregar conferência:', e);
      } finally {
        this.loading = false;
      }
    },

    getCsrf() {
      return document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('input[name="csrf_token"]')?.value || '';
    },

    async startAudit() {
      this.loading = true;
      this.lastFeedback = null;
      const csrf = this.getCsrf();
      try {
        const res = await fetch('/stock/audit/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ location_scope: this.locationScope, csrf_token: csrf }),
        });
        const data = await res.json();
        if (data.ok) {
          this.activeSummary = data.summary;
          this.$nextTick(() => this.focusScan());
        }
      } catch (e) {
        alert('Erro ao iniciar conferência.');
      } finally {
        this.loading = false;
      }
    },

    async submitScan() {
      const ch = (this.scanInput || '').trim();
      if (!ch || !this.activeSummary) return;
      this.scanInput = ''; // Limpa imediatamente para o próximo bip contínuo
      const auditId = this.activeSummary.audit.id;

      try {
        const csrf = this.getCsrf();
        const res = await fetch('/stock/audit/scan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ audit_id: auditId, chassis: ch, csrf_token: csrf }),
        });
        const data = await res.json();
        if (data.ok) {
          this.lastFeedback = {
            type: data.item?.scan_result === 'ok' ? 'ok' : 'alert',
            text: data.message,
          };
          if (!data.duplicate && data.item) {
            this.activeSummary.scanned_items.unshift(data.item);
            this.activeSummary.scanned_count = data.scanned_count;
            this.activeSummary.alerts_count = data.alerts_count;
            this.activeSummary.missing_count = Math.max(
              0,
              (this.activeSummary.expected_count || 0) - data.scanned_count
            );
          }
        } else {
          this.lastFeedback = { type: 'alert', text: data.error || 'Falha ao bipar.' };
        }
      } catch (e) {
        this.lastFeedback = { type: 'alert', text: 'Erro de conexão ao registrar bip.' };
      } finally {
        this.$nextTick(() => this.focusScan());
      }
    },

    async finishAudit() {
      if (!this.activeSummary) return;
      if (!confirm('Finalizar conferência agora e gerar o relatório PDF de divergências?')) return;
      this.finishing = true;
      const auditId = this.activeSummary.audit.id;
      try {
        const csrf = this.getCsrf();
        const res = await fetch(`/stock/audit/${auditId}/finish`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ csrf_token: csrf }),
        });
        const data = await res.json();
        if (data.ok) {
          window.open(`/stock/audit/${auditId}/pdf`, '_blank');
          this.activeSummary = null;
          this.lastFeedback = null;
          await this.loadState();
        } else {
          alert(data.error || 'Erro ao finalizar.');
        }
      } catch (e) {
        alert('Erro de rede ao finalizar conferência.');
      } finally {
        this.finishing = false;
      }
    },

    resultLabel(code) {
      const map = {
        ok: '✅ OK',
        alert_separated: '⚠️ SEPARADO P/ VENDA',
        alert_sold: '🔴 CONSTAVA VENDIDO',
        alert_assembled: '🛠️ MONTADO',
        alert_other_location: '📍 OUTRO GALPÃO',
        unknown: '❓ NÃO CADASTRADO',
      };
      return map[code] || code;
    },
  };
}

async function markChassisAssembled(chassis) {
  if (!confirm(`Marcar o chassi ${chassis} como MONTADO (Exposição/Loja)?`)) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('input[name="csrf_token"]')?.value || '';
  try {
    const res = await fetch('/stock/chassis/assemble', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify({ chassis, csrf_token: csrf }),
    });
    const data = await res.json();
    if (data.ok) {
      window.location.reload();
    } else {
      alert(data.error || 'Erro ao marcar como montado.');
    }
  } catch (e) {
    alert('Erro ao comunicar com o servidor.');
  }
}

window.stockAuditApp = stockAuditApp;
window.markChassisAssembled = markChassisAssembled;
