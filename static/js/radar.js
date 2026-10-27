/**
 * M-One Radar de Mercado (static/js/radar.js)
 * Controlador Alpine.js Ultra-Limpo para Rastreamento Georreferenciado por Cidade.
 * Segregação modular estrita (< 500 linhas).
 */

function radarApp(cidadeSelecionada, jobStatusInitial, defaultNicho) {
  const cidade = (typeof cidadeSelecionada !== 'undefined' && cidadeSelecionada !== null && cidadeSelecionada !== '') 
    ? cidadeSelecionada 
    : (window.radarCidadeFiltro || 'all');
  const jobStatus = (typeof jobStatusInitial !== 'undefined' && jobStatusInitial !== null && Object.keys(jobStatusInitial).length > 0)
    ? jobStatusInitial
    : (window.radarJobStatus || {});
  const nicho = (typeof defaultNicho !== 'undefined' && defaultNicho !== null && defaultNicho !== '')
    ? defaultNicho
    : (window.radarDefaultNicho || 'revenda-motos');

  return {
    cidadeSelecionada: cidade,
    disparoEmProgresso: false,
    alertaMsg: '',
    jobStatus: jobStatus,
    formDisparo: {
      praca: (cidade && cidade !== 'all') ? cidade : 'Linhares - ES',
      nicho: nicho,
      limite: 25
    },
    modalAbordagemAberto: false,
    leadSelecionado: null,
    mensagemAbordagem: '',

    init() {
      if (this.jobStatus && this.jobStatus.running) {
        this.iniciarPollingStatus();
      }
    },

    async dispararMissao() {
      if (!this.formDisparo.praca || !this.formDisparo.praca.trim()) {
        alert('Por favor, informe a Cidade que deseja rastrear (Ex: Linhares - ES).');
        return;
      }
      this.disparoEmProgresso = true;
      try {
        const resp = await fetch('/radar/api/disparar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.formDisparo)
        });
        const data = await resp.json();
        if (data.status === 'success') {
          this.alertaMsg = `Rastreando ${this.formDisparo.praca}... O robô está varrendo as empresas locais agora.`;
          this.jobStatus.running = true;
          this.iniciarPollingStatus();
        } else {
          alert(data.message || 'Erro ao iniciar rastreamento.');
        }
      } catch (e) {
        alert('Falha na comunicação com o servidor: ' + e);
      } finally {
        this.disparoEmProgresso = false;
      }
    },

    iniciarPollingStatus() {
      const timer = setInterval(async () => {
        try {
          const resp = await fetch('/radar/api/status');
          const data = await resp.json();
          if (data.status === 'success') {
            this.jobStatus = data.job;
            if (!this.jobStatus.running) {
              clearInterval(timer);
              if (this.jobStatus.completed) {
                this.alertaMsg = 'Rastreamento concluído com sucesso! Atualizando tela...';
                const pracaAlvo = this.formDisparo.praca.replace(' - ES', '').replace(' - SP', '').replace(' - MG', '').trim();
                setTimeout(() => {
                  window.location.href = `/radar?cidade=${encodeURIComponent(pracaAlvo)}`;
                }, 1000);
              }
            }
          }
        } catch (e) {
          clearInterval(timer);
        }
      }, 3000);
    },

    abrirModalAbordagem(lead) {
      this.leadSelecionado = lead;
      this.mensagemAbordagem = lead.gancho_comercial || `Olá, equipe da ${lead.nome}! Tudo bem? 😊 Aqui é da MAJ Mobilidade Elétrica.`;
      this.modalAbordagemAberto = true;
    },

    async enviarWhatsAppModal() {
      if (!this.leadSelecionado) return;
      const lead = this.leadSelecionado;
      const url = `https://wa.me/${lead.whatsapp}?text=${encodeURIComponent(this.mensagemAbordagem)}`;
      window.open(url, '_blank');

      try {
        await fetch(`/radar/api/lead/${lead.id}/prospectar`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mensagem: this.mensagemAbordagem })
        });
        this.alertaMsg = `Abordagem registrada para ${lead.nome}!`;
      } catch (e) {}

      this.modalAbordagemAberto = false;
      setTimeout(() => window.location.reload(), 1000);
    },

    async marcarProspectado(leadId, leadNome) {
      try {
        await fetch(`/radar/api/lead/${leadId}/prospectar`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
      } catch (e) {}
    },

    async atualizarStatusLead(leadId, novoStatus) {
      try {
        const resp = await fetch(`/radar/api/lead/${leadId}/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: novoStatus })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          this.alertaMsg = 'Status do lead atualizado!';
        }
      } catch (e) {
        alert('Erro ao atualizar status: ' + e);
      }
    }
  };
}
