/**
 * M-One Support & Tickets Controller (static/js/support-ticket.js)
 * Gerencia a Central de Suporte, captura de prints via Ctrl+V / Cmd+V,
 * drag-and-drop de imagens, timeline de atendimento e alertas reativos.
 * Anti-monólito: < 500 linhas.
 */

window.supportTicketApp = function(initialConfig = {}) {
  let modules = initialConfig.availableModules || [];
  if (!modules || modules.length === 0) {
    const el = document.getElementById('supportModulesData');
    if (el) {
      try {
        modules = JSON.parse(el.textContent);
      } catch (e) {
        console.warn('Erro ao carregar supportModulesData:', e);
      }
    }
  }
  return {
    isStaff: initialConfig.isStaff || false,
    currentUserId: initialConfig.currentUserId || null,
    availableModules: modules,
    selectedModuleKey: '',
    selectedModuleKeys: ['atacado'],
    ticketItems: [''],
    ticketTitle: '',
    ticketDescription: '',
    ticketUrgency: 'urgente',
    uploadedAttachments: [],
    isSubmitting: false,
    errorMessage: '',
    successMessage: '',
    
    // Modal de Detalhes / Timeline
    activeTicket: null,
    isDetailModalOpen: false,
    isLoadingTicket: false,
    replyText: '',
    replyStatus: '',
    resolutionNotes: '',
    replyAttachments: [],
    isSendingReply: false,
    reopenTicket: false,

    // Lightbox de Imagens
    lightboxImage: null,

    // Gestão de Ocultação Temporária de Chamados (na sessão atual)
    hiddenTicketIds: [],
    isUrgentBannerDismissed: false,

    // Modal de Cadastro de Correções Internas (exclusivo Fauzer)
    isInternalModalOpen: false,

    getCsrfToken() {
      return document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('input[name="csrf_token"]')?.value || '';
    },

    init() {
      try {
        this.isUrgentBannerDismissed = (sessionStorage.getItem('m_one_urgent_banner_dismissed') === 'true');
      } catch (e) {}
      this.setupGlobalPasteListener();
      this.initBadgesPolling();
    },

    toggleModuleKey(key) {
      const idx = this.selectedModuleKeys.indexOf(key);
      if (idx > -1 && this.selectedModuleKeys.length > 1) {
        this.selectedModuleKeys.splice(idx, 1);
      } else if (idx === -1) {
        this.selectedModuleKeys.push(key);
      }
      this.selectedModuleKey = this.selectedModuleKeys[0] || '';
    },
    isModuleSelected(key) { return this.selectedModuleKeys.includes(key); },
    addTicketItem() { this.ticketItems.push(''); },
    removeTicketItem(idx) { if (this.ticketItems.length > 1) this.ticketItems.splice(idx, 1); },

    async toggleItemCompletion(item) {
      if (!this.activeTicket || !item) return;
      try {
        const res = await fetch(`/api/suporte/tickets/${this.activeTicket.id}/items/${item.id}/toggle`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.getCsrfToken() },
          body: JSON.stringify({ completed: !item.completed, csrf_token: this.getCsrfToken() })
        });
        const data = await res.json();
        if (data.success) {
          item.completed = data.completed;
          if (data.all_completed && this.activeTicket.status !== 'resolvido') {
            const wantResolve = confirm('🎉 Todas as alterações deste chamado foram marcadas como concluídas!\n\nDeseja alterar o status do chamado para "Resolvido" agora?');
            if (wantResolve) {
              this.replyStatus = 'resolvido';
              this.resolutionNotes = 'Todas as alterações foram concluídas.';
              await this.sendReply();
            }
          }
        }
      } catch (err) {
        console.error('Erro ao alternar item:', err);
      }
    },

    setupGlobalPasteListener() {
      // Captura prints via Ctrl+V / Cmd+V em qualquer lugar da tela
      document.addEventListener('paste', (e) => {
        const items = (e.clipboardData || e.originalEvent.clipboardData)?.items;
        if (!items) return;

        for (let i = 0; i < items.length; i++) {
          if (items[i].type.indexOf('image') !== -1) {
            const file = items[i].getAsFile();
            if (file) {
              e.preventDefault();
              this.handlePastedImage(file);
              break;
            }
          }
        }
      });
    },

    handlePastedImage(file) {
      const reader = new FileReader();
      reader.onload = async (event) => {
        const base64Data = event.target.result;
        await this.uploadPrintBase64(base64Data);
      };
      reader.readAsDataURL(file);
    },

    async handleFileInput(e, isReply = false) {
      const files = e.target.files;
      if (!files || files.length === 0) return;
      for (let i = 0; i < files.length; i++) {
        await this.uploadPrintFile(files[i], isReply);
      }
      e.target.value = '';
    },

    async handleDrop(e, isReply = false) {
      e.preventDefault();
      const files = e.dataTransfer?.files;
      if (!files || files.length === 0) return;
      for (let i = 0; i < files.length; i++) {
        if (files[i].type.startsWith('image/')) {
          await this.uploadPrintFile(files[i], isReply);
        }
      }
    },

    async uploadPrintBase64(base64Data) {
      try {
        const res = await fetch('/api/suporte/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.getCsrfToken() },
          body: JSON.stringify({ image_base64: base64Data, csrf_token: this.getCsrfToken() })
        });
        const data = await res.json();
        if (data.success && data.url) {
          if (this.isDetailModalOpen) {
            this.replyAttachments.push(data.url);
          } else {
            this.uploadedAttachments.push(data.url);
          }
        } else {
          alert('Erro ao enviar print: ' + (data.error || 'Falha no processamento'));
        }
      } catch (err) {
        console.error('Falha ao subir print:', err);
        alert('Falha ao enviar print da área de transferência.');
      }
    },

    async uploadPrintFile(file, isReply = false) {
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('csrf_token', this.getCsrfToken());
        const res = await fetch('/api/suporte/upload', {
          method: 'POST',
          headers: { 'X-CSRF-Token': this.getCsrfToken() },
          body: formData
        });
        const data = await res.json();
        if (data.success && data.url) {
          if (isReply || this.isDetailModalOpen) {
            this.replyAttachments.push(data.url);
          } else {
            this.uploadedAttachments.push(data.url);
          }
        } else {
          alert('Erro ao carregar print: ' + (data.error || 'Falha no upload'));
        }
      } catch (err) {
        console.error('Erro no upload de imagem:', err);
        alert('Erro de conexão ao carregar imagem.');
      }
    },

    removeAttachment(idx, isReply = false) {
      if (isReply) {
        this.replyAttachments.splice(idx, 1);
      } else {
        this.uploadedAttachments.splice(idx, 1);
      }
    },

    openLightbox(url) {
      this.lightboxImage = url;
    },

    closeLightbox() {
      this.lightboxImage = null;
    },

    async submitTicket() {
      this.errorMessage = '';
      this.successMessage = '';

      if (this.selectedModuleKeys.length === 0 && this.selectedModuleKey) {
        this.selectedModuleKeys = [this.selectedModuleKey];
      }
      if (this.selectedModuleKeys.length === 0) {
        this.errorMessage = 'Selecione ao menos um setor/área afetada.';
        return;
      }
      if (!this.ticketTitle.trim()) {
        this.errorMessage = 'Informe um título resumido para o chamado.';
        return;
      }
      const validItems = this.ticketItems.map(t => t.trim()).filter(Boolean);
      if (!this.ticketDescription.trim() && validItems.length === 0) {
        this.errorMessage = 'Descreva a solicitação ou adicione ao menos uma alteração.';
        return;
      }

      const selectedMods = this.availableModules
        .filter(m => this.selectedModuleKeys.includes(m.key))
        .map(m => ({ key: m.key, label: m.label }));

      this.isSubmitting = true;
      try {
        const res = await fetch('/api/suporte/tickets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.getCsrfToken() },
          body: JSON.stringify({
            modules: selectedMods,
            module_key: selectedMods[0]?.key || '',
            module_label: selectedMods.map(m => m.label).join(', '),
            items: validItems,
            title: this.ticketTitle.trim(),
            description: this.ticketDescription.trim(),
            urgency: this.ticketUrgency,
            attachments: this.uploadedAttachments,
            csrf_token: this.getCsrfToken()
          })
        });
        const data = await res.json();
        if (data.success) {
          this.successMessage = `✅ Chamado ${data.ticket_code} aberto com sucesso!`;
          this.ticketTitle = '';
          this.ticketDescription = '';
          this.ticketItems = [''];
          this.uploadedAttachments = [];
          setTimeout(() => { window.location.reload(); }, 1200);
        } else {
          this.errorMessage = data.error || 'Falha ao abrir chamado.';
        }
      } catch (err) {
        this.errorMessage = 'Erro de comunicação ao abrir chamado: ' + err.message;
      } finally {
        this.isSubmitting = false;
      }
    },

    async openTicketDetails(ticketId) {
      this.isLoadingTicket = true;
      this.isDetailModalOpen = true;
      this.replyText = '';
      this.replyAttachments = [];
      this.reopenTicket = false;

      try {
        const res = await fetch(`/api/suporte/tickets/${ticketId}`);
        const data = await res.json();
        if (data.success) {
          this.activeTicket = data.ticket;
          this.replyStatus = this.activeTicket.status;
          this.resolutionNotes = this.activeTicket.resolution_notes || '';
          this.$nextTick(() => {
            const thread = document.getElementById('ticketMessagesThread');
            if (thread) thread.scrollTop = thread.scrollHeight;
          });
        } else {
          alert(data.error || 'Erro ao carregar detalhes do chamado.');
          this.isDetailModalOpen = false;
        }
      } catch (err) {
        alert('Erro ao carregar chamado: ' + err.message);
        this.isDetailModalOpen = false;
      } finally {
        this.isLoadingTicket = false;
      }
    },

    closeTicketDetails() {
      this.isDetailModalOpen = false;
      this.activeTicket = null;
    },

    async sendReply() {
      if (!this.activeTicket) return;
      if (!this.replyText.trim() && !this.resolutionNotes.trim() && this.replyStatus === this.activeTicket.status && !this.reopenTicket) {
        alert('Digite uma mensagem ou atualize o status.');
        return;
      }

      this.isSendingReply = true;
      try {
        const payload = {
          message_text: this.replyText.trim(),
          attachments: this.replyAttachments,
          new_status: this.isStaff ? this.replyStatus : (this.reopenTicket ? 'pendente' : null),
          resolution_notes: this.isStaff ? this.resolutionNotes.trim() : null,
          reopen: this.reopenTicket,
          csrf_token: this.getCsrfToken()
        };

        const res = await fetch(`/api/suporte/tickets/${this.activeTicket.id}/reply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.getCsrfToken() },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          // Recarrega detalhes para atualizar linha do tempo
          await this.openTicketDetails(this.activeTicket.id);
          this.replyText = '';
          this.replyAttachments = [];
          this.reopenTicket = false;
        } else {
          alert('Erro ao responder: ' + (data.error || 'Falha no envio'));
        }
      } catch (err) {
        alert('Erro de comunicação: ' + err.message);
      } finally {
        this.isSendingReply = false;
      }
    },

    // Ocultar / Restaurar Chamados e Alertas da Visão
    dismissUrgentBanner() {
      this.isUrgentBannerDismissed = true;
      try {
        sessionStorage.setItem('m_one_urgent_banner_dismissed', 'true');
      } catch (e) {}
    },

    hideTicket(id) {
      if (!this.hiddenTicketIds.includes(id)) {
        this.hiddenTicketIds.push(id);
      }
    },

    unhideAllTickets() {
      this.hiddenTicketIds = [];
      this.isUrgentBannerDismissed = false;
      try {
        sessionStorage.removeItem('m_one_urgent_banner_dismissed');
      } catch (e) {}
    },

    isTicketHidden(id) {
      return this.hiddenTicketIds.includes(id);
    },

    getVisibleCount(total) {
      return Math.max(0, total - this.hiddenTicketIds.length);
    },

    // Modal de Cadastro de Correções Internas
    openInternalCorrectionModal() {
      this.selectedModuleKeys = ['atacado'];
      this.ticketItems = [''];
      this.ticketTitle = '';
      this.ticketDescription = '';
      this.ticketUrgency = 'urgente';
      this.uploadedAttachments = [];
      this.errorMessage = '';
      this.successMessage = '';
      this.isInternalModalOpen = true;
    },

    closeInternalCorrectionModal() {
      this.isInternalModalOpen = false;
    },

    async submitInternalCorrection() {
      const validItems = this.ticketItems.map(t => t.trim()).filter(Boolean);
      if (this.selectedModuleKeys.length === 0 && this.selectedModuleKey) {
        this.selectedModuleKeys = [this.selectedModuleKey];
      }
      if (this.selectedModuleKeys.length === 0 || !this.ticketTitle.trim() || (!this.ticketDescription.trim() && validItems.length === 0)) {
        this.errorMessage = 'Preencha os setores, o título e a descrição ou alterações.';
        return;
      }
      this.isSubmitting = true;
      this.errorMessage = '';
      try {
        const selectedMods = this.availableModules
          .filter(m => this.selectedModuleKeys.includes(m.key))
          .map(m => ({ key: m.key, label: m.label }));
        const payload = {
          modules: selectedMods,
          module_key: selectedMods[0]?.key || '',
          module_label: selectedMods.map(m => m.label).join(', '),
          items: validItems,
          title: this.ticketTitle.trim(),
          description: this.ticketDescription.trim(),
          urgency: this.ticketUrgency,
          attachments: this.uploadedAttachments,
          notify_whatsapp: false,
          csrf_token: this.getCsrfToken()
        };
        const res = await fetch('/api/suporte/tickets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': this.getCsrfToken() },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          this.successMessage = 'Correção interna cadastrada com sucesso!';
          setTimeout(() => {
            window.location.reload();
          }, 600);
        } else {
          this.errorMessage = data.error || 'Erro ao cadastrar correção.';
        }
      } catch (err) {
        this.errorMessage = 'Erro de comunicação: ' + err.message;
      } finally {
        this.isSubmitting = false;
      }
    },

    initBadgesPolling() {
      // Atualiza badges da sidebar a cada 45 segundos
      setInterval(() => {
        fetch('/api/suporte/badges')
          .then(r => r.json())
          .then(data => {
            if (data.success) {
              const badgeElem = document.getElementById('supportSidebarBadge');
              if (badgeElem) {
                if (data.badge_count > 0) {
                  badgeElem.textContent = data.badge_count;
                  badgeElem.style.display = 'inline-flex';
                } else {
                  badgeElem.style.display = 'none';
                }
              }
              const banner = document.getElementById('fauzerUrgentSupportBanner');
              if (banner) {
                if (data.has_urgent_pending) {
                  banner.style.display = 'flex';
                  const titleElem = document.getElementById('urgentTicketTitle');
                  if (titleElem && data.latest_urgent) {
                    titleElem.textContent = `${data.latest_urgent.ticket_code}: ${data.latest_urgent.title} (${data.latest_urgent.module_label})`;
                  }
                } else {
                  banner.style.display = 'none';
                }
              }
            }
          })
          .catch(() => {});
      }, 45000);
    }
  };
};

