/**
 * M-One Employee Portal Script (static/js/employee-portal.js)
 * Controla o cronômetro vivo, auto-save com debouncing, upload de DOCX/TXT e submissão com CSRF.
 * Segregação modular estrita (< 500 linhas).
 */

function employeePortal() {
  const cfg = window.__PORTAL_CONFIG__ || {};
  const isFauzer = Boolean(cfg.isFauzer);
  return {
    currentTab: 'form',
    cycleId: cfg.cycleId,
    employeeKey: cfg.employeeKey,
    deadlineIso: cfg.deadlineIso,
    isFauzer: isFauzer,
    isEditable: isFauzer ? true : Boolean(cfg.isEditable),
    csrfToken: cfg.csrfToken || '',
    answers: cfg.answers || {},
    reportStatus: cfg.reportStatus || 'draft',
    pointsAwarded: cfg.pointsAwarded || 0,
    reviewedAt: cfg.reviewedAt || '',
    reviewedBy: cfg.reviewedBy || '',
    profile: cfg.profile || {},
    isSaving: false,
    isUploading: false,
    autoSaveMessage: '✓ Salvo na nuvem',
    autoSaveTimer: null,
    timeRemaining: { days: 0, hours: '00', minutes: '00', seconds: '00', isExpired: false, isWarning: false },

    initPortal() {
      this.updateCountdown();
      setInterval(() => this.updateCountdown(), 1000);
    },

    updateCountdown() {
      if (!this.deadlineIso) return;
      const deadline = new Date(this.deadlineIso).getTime();
      const now = new Date().getTime();
      const diff = deadline - now;

      if (diff <= 0) {
        this.timeRemaining = { days: 0, hours: '00', minutes: '00', seconds: '00', isExpired: true, isWarning: false };
        return;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      this.timeRemaining = {
        days: days,
        hours: String(hours).padStart(2, '0'),
        minutes: String(minutes).padStart(2, '0'),
        seconds: String(seconds).padStart(2, '0'),
        isExpired: false,
        isWarning: diff < (24 * 60 * 60 * 1000)
      };
    },

    debounceAutoSave() {
      this.autoSaveMessage = 'Digitando...';
      clearTimeout(this.autoSaveTimer);
      this.autoSaveTimer = setTimeout(() => {
        if (this.isEditable) this.saveDraft(true);
      }, 2500);
    },

    async saveDraft(isSilent = false) {
      if (this.isSaving) return;
      this.isSaving = true;
      if (!isSilent) this.autoSaveMessage = 'Salvando rascunho...';

      try {
        const res = await fetch('/api/meu-relatorio/salvar', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRF-Token': this.csrfToken
          },
          body: JSON.stringify({
            cycle_id: this.cycleId,
            answers: this.answers,
            is_draft: true,
            csrf_token: this.csrfToken
          })
        });
        const data = await res.json();
        this.isSaving = false;
        if (data.status === 'success') {
          const nowStr = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
          this.autoSaveMessage = `✓ Rascunho salvo às ${nowStr}`;
          if (data.report && data.report.status) {
            this.reportStatus = data.report.status;
          }
          if (!isSilent) alert('💾 Rascunho salvo com sucesso na nuvem!');
        } else {
          this.autoSaveMessage = 'Falha ao salvar';
          if (!isSilent) alert('Erro ao salvar rascunho: ' + (data.message || ''));
        }
      } catch (err) {
        this.isSaving = false;
        this.autoSaveMessage = 'Falha de conexão';
        if (!isSilent) alert('Erro de conexão ao salvar rascunho.');
      }
    },

    async submitOfficial() {
      if (!confirm('Deseja enviar seu relatório oficial agora?\n\nEle será protocolado e submetido para a Reunião da Diretoria.')) return;
      this.isSaving = true;
      this.autoSaveMessage = 'Protocolando relatório oficial...';

      try {
        const res = await fetch('/api/meu-relatorio/salvar', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CSRF-Token': this.csrfToken
          },
          body: JSON.stringify({
            cycle_id: this.cycleId,
            answers: this.answers,
            is_draft: false,
            csrf_token: this.csrfToken
          })
        });
        const data = await res.json();
        this.isSaving = false;

        if (data.status === 'success') {
          alert(data.message || '🎉 Relatório entregue com sucesso!');
          window.location.reload();
        } else {
          alert('❌ Erro ao enviar relatório: ' + (data.message || ''));
        }
      } catch (err) {
        this.isSaving = false;
        alert('Falha na comunicação ao enviar relatório.');
      }
    },

    async handleFileUpload(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('cycle_id', this.cycleId);
      formData.append('file', file);
      formData.append('force', 'false');
      formData.append('csrf_token', this.csrfToken);

      this.isUploading = true;
      try {
        const res = await fetch('/api/meu-relatorio/upload', {
          method: 'POST',
          headers: {
            'Accept': 'application/json',
            'X-CSRF-Token': this.csrfToken
          },
          body: formData
        });
        const data = await res.json();
        this.isUploading = false;
        event.target.value = '';

        if (data.status === 'success') {
          alert('✅ ' + data.message);
          window.location.reload();
        } else {
          alert('❌ ' + (data.message || 'Erro ao processar arquivo.'));
        }
      } catch (err) {
        this.isUploading = false;
        event.target.value = '';
        alert('Erro ao enviar arquivo para extração.');
      }
    }
  };
}
