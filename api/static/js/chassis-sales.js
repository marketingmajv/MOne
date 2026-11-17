/**
 * M-One Chassis Sales & Separation Controller (static/js/chassis-sales.js)
 * Fluxo Financeiro/Vendas (Marisa): busca suspensa que recolhe ao bipar chassi
 * e exibe formulário de baixa (NF Venda, NF Transf. 1/2, Cliente, Valor) ou Separação.
 */

function chassisSalesApp() {
  return {
    open: false,
    searchQuery: '',
    searching: false,
    candidates: [],
    selectedUnit: null,
    actionMode: 'checkout', // 'checkout' | 'separate'
    saving: false,
    feedback: null,

    form: {
      transfer_nf_1: '',
      transfer_nf_2: '',
      invoice_number: '',
      customer: '',
      total_value: '',
      order_number: '',
      sold_at: new Date().toISOString().slice(0, 10),
    },

    openModal() {
      this.open = true;
      this.resetToSearch();
      this.$nextTick(() => this.focusSearch());
    },

    closeModal() {
      this.open = false;
    },

    focusSearch() {
      const el = document.getElementById('marisa_chassis_search_input');
      if (el) el.focus();
    },

    resetToSearch() {
      this.selectedUnit = null;
      this.searchQuery = '';
      this.candidates = [];
      this.actionMode = 'checkout';
      this.form = {
        transfer_nf_1: '',
        transfer_nf_2: '',
        invoice_number: '',
        customer: '',
        total_value: '',
        order_number: '',
        sold_at: new Date().toISOString().slice(0, 10),
      };
      this.$nextTick(() => this.focusSearch());
    },

    async doSearch(autoSelectExact = false) {
      const q = (this.searchQuery || '').trim();
      if (!q) {
        this.candidates = [];
        return;
      }
      this.searching = true;
      try {
        const res = await fetch(`/api/chassis/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        if (data.ok) {
          this.candidates = data.items || [];
          if (autoSelectExact && this.candidates.length > 0) {
            const exact = this.candidates.find(
              (c) => c.chassis.toUpperCase() === q.toUpperCase()
            );
            if (exact) {
              this.selectUnit(exact);
            } else if (this.candidates.length === 1) {
              this.selectUnit(this.candidates[0]);
            }
          }
        }
      } catch (e) {
        console.error('Erro ao buscar chassi:', e);
      } finally {
        this.searching = false;
      }
    },

    selectUnit(unit) {
      if (unit.status === 'sold') {
        this.feedback = {
          type: 'error',
          text: `Chassi ${unit.chassis} já consta como VENDIDO.`,
        };
        return;
      }
      this.feedback = null;
      this.selectedUnit = unit;
      this.candidates = [];
      if (unit.separated_order_number) {
        this.form.order_number = unit.separated_order_number;
      }
    },

    async submitAction() {
      if (!this.selectedUnit) return;
      this.saving = true;
      this.feedback = null;

      try {
        let url = '/sales/chassis-checkout';
        let payload = {
          chassis: this.selectedUnit.chassis,
          ...this.form,
        };
        if (this.actionMode === 'separate') {
          url = '/sales/chassis-separate';
          payload = {
            chassis: this.selectedUnit.chassis,
            order_number: this.form.order_number,
          };
        }

        const csrf = document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('input[name="csrf_token"]')?.value || '';
        payload.csrf_token = csrf;
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.ok) {
          this.feedback = {
            type: 'ok',
            text:
              this.actionMode === 'separate'
                ? `✅ Chassi ${data.chassis} marcado como SEPARADO (Pedido #${data.order_number}).`
                : `✅ Venda faturada para ${data.customer} (NF ${data.invoice_number} | Chassi ${data.chassis}).`,
          };
          this.resetToSearch();
        } else {
          this.feedback = { type: 'error', text: data.error || 'Erro ao salvar.' };
        }
      } catch (e) {
        this.feedback = { type: 'error', text: 'Erro de conexão ao salvar.' };
      } finally {
        this.saving = false;
      }
    },
  };
}

window.chassisSalesApp = chassisSalesApp;
