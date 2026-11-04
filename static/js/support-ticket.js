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

    init() {
      this.setupGlobalPasteListener();
      this.initBadgesPolling();
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
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image_base64: base64Data })
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
        const res = await fetch('/api/suporte/upload', {
          method: 'POST',
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

      if (!this.selectedModuleKey) {
        this.errorMessage = 'Por favor, selecione a área ou módulo correspondente.';
        return;
      }
      if (!this.ticketTitle.trim()) {
        this.errorMessage = 'Informe um título resumido para o chamado.';
        return;
      }
      if (!this.ticketDescription.trim()) {
        this.errorMessage = 'Descreva detalhadamente o problema ou alteração desejada.';
        return;
      }

      const modObj = this.availableModules.find(m => m.key === this.selectedModuleKey);
      const moduleLabel = modObj ? modObj.label : this.selectedModuleKey;

      this.isSubmitting = true;
      try {
        const res = await fetch('/api/suporte/tickets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            module_key: this.selectedModuleKey,
            module_label: moduleLabel,
            title: this.ticketTitle.trim(),
            description: this.ticketDescription.trim(),
            urgency: this.ticketUrgency,
            attachments: this.uploadedAttachments
          })
        });
        const data = await res.json();
        if (data.success) {
          this.successMessage = `✅ Chamado ${data.ticket_code} aberto com sucesso! Fauzer foi notificado com prioridade.`;
          this.ticketTitle = '';
          this.ticketDescription = '';
          this.uploadedAttachments = [];
          setTimeout(() => { window.location.reload(); }, 1500);
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
          reopen: this.reopenTicket
        };

        const res = await fetch(`/api/suporte/tickets/${this.activeTicket.id}/reply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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

