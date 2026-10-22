/**
 * M-One Module Maintenance Handler (static/js/module-maintenance.js)
 * Permite que administradores aprovem e personalizem mensagens de WhatsApp
 * antes de alternar o modo manutenção de qualquer módulo.
 * Segregação estrita modular (< 500 linhas).
 */

function moduleMaintenanceAdmin(slug, initialMaintenance, initialTime, initialReason, moduleName) {
  return {
    slug: slug,
    moduleName: moduleName || (slug === 'prospeccao' ? 'Prospecção' : (slug.charAt(0).toUpperCase() + slug.slice(1))),
    inMaintenance: Boolean(initialMaintenance),
    expectedTime: initialTime || '',
    reason: initialReason || '',
    notifyWhatsApp: true,
    customMessage: '',
    isCustomized: false,
    recipients: [],
    loadingRecipients: false,
    modalAberto: false,
    salvando: false,
    statusMsg: '',

    init() {
      window.addEventListener('abrir-modal-manutencao', () => {
        this.openModal();
      });
      this.syncDefaultMessage();
    },

    openModal() {
      this.modalAberto = true;
      this.statusMsg = '';
      if (!this.isCustomized) {
        this.syncDefaultMessage();
      }
      this.loadRecipients();
    },

    fecharModal() {
      this.modalAberto = false;
    },

    buildDefaultMessage(targetInMaintenance) {
      if (targetInMaintenance) {
        const timeStr = this.expectedTime.trim() ? `⏳ *Previsão de retorno:* ${this.expectedTime.trim()}\n\n` : '';
        const reasonStr = this.reason.trim() ? `📌 *Detalhes:* ${this.reason.trim()}\n\n` : '';
        return `🛠️ *[M-One] Aviso de Manutenção Técnica*\n\nOlá, {nome}!\n\nO módulo de *${this.moduleName}* do M-One está temporariamente em manutenção técnica para melhorias e atualizações.\n\n${timeStr}${reasonStr}Você receberá uma nova notificação por aqui assim que o sistema estiver 100% liberado para uso. Obrigado pela compreensão!`;
      } else {
        const routePath = this.slug === 'prospeccao' ? 'prospeccao' : (this.slug === 'fiscal_pricing' ? 'fiscal/pricing' : this.slug);
        return `🚀 *[M-One] Módulo Operacional Liberado!*\n\nOlá, {nome}!\n\nAs atualizações no módulo de *${this.moduleName}* foram concluídas com sucesso. O sistema já está 100% operacional e liberado para uso.\n\n🔗 Acesse em: https://m-one.majmobilidade.com.br/${routePath}\n\nBom trabalho e ótimas vendas!`;
      }
    },

    syncDefaultMessage() {
      if (!this.isCustomized) {
        // Alvo: se está operacional, a próxima ação é entrar em manutenção (true); se em manutenção, é liberar (false)
        const targetState = !this.inMaintenance;
        this.customMessage = this.buildDefaultMessage(targetState);
      }
    },

    onMessageInput() {
      this.isCustomized = true;
    },

    resetToDefault() {
      this.isCustomized = false;
      const targetState = !this.inMaintenance;
      this.customMessage = this.buildDefaultMessage(targetState);
    },

    async loadRecipients() {
      this.loadingRecipients = true;
      try {
        const resp = await fetch(`/api/manutencao/recipients/${this.slug}`);
        const data = await resp.json();
        if (data.status === 'success') {
          this.recipients = data.recipients || [];
        }
      } catch (err) {
        console.warn('Falha ao carregar destinatários:', err);
      } finally {
        this.loadingRecipients = false;
      }
    },

    async toggleMaintenance(targetState) {
      if (this.salvando) return;
      this.salvando = true;
      this.statusMsg = 'Atualizando status e disparando notificações via WhatsApp...';

      try {
        const resp = await fetch('/api/manutencao/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            slug: this.slug,
            in_maintenance: targetState,
            expected_time: this.expectedTime,
            reason: this.reason,
            notify_whatsapp: this.notifyWhatsApp,
            custom_message: this.notifyWhatsApp ? this.customMessage : null
          })
        });

        const data = await resp.json();
        this.salvando = false;

        if (data.status === 'success') {
          this.inMaintenance = targetState;
          let extraMsg = '';
          if (data.notifications && data.notifications.total_sent > 0) {
            extraMsg = `\n\n📱 ${data.notifications.total_sent} colaboradores notificados via WhatsApp!`;
          }
          alert(`✅ ${data.message}${extraMsg}`);
          this.fecharModal();
          window.location.reload();
        } else {
          alert('❌ ' + (data.message || 'Erro ao alterar manutenção.'));
        }
      } catch (err) {
        this.salvando = false;
        alert('Falha na comunicação com o servidor: ' + err);
      }
    }
  };
}
