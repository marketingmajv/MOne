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
    modalExportAberto: false,
    cidadesSelecionadasExport: [],
    exportApenasWa: false,
    exportStatusFiltro: 'all',
    exportandoExcel: false,

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
    },

    abrirModalExport(cidadesLista) {
      if (this.cidadesSelecionadasExport.length === 0) {
        if (this.cidadeSelecionada && this.cidadeSelecionada !== 'all') {
          this.cidadesSelecionadasExport = [this.cidadeSelecionada];
        } else if (Array.isArray(cidadesLista)) {
          this.cidadesSelecionadasExport = cidadesLista.map(c => typeof c === 'string' ? c : c.cidade).filter(Boolean);
        }
      }
      this.modalExportAberto = true;
    },

    marcarTodasCidades(cidadesLista) {
      if (Array.isArray(cidadesLista)) {
        this.cidadesSelecionadasExport = cidadesLista.map(c => typeof c === 'string' ? c : c.cidade).filter(Boolean);
      }
    },

    desmarcarTodasCidades() {
      this.cidadesSelecionadasExport = [];
    },

    toggleCidadeExport(cidadeNome) {
      const idx = this.cidadesSelecionadasExport.indexOf(cidadeNome);
      if (idx > -1) {
        this.cidadesSelecionadasExport.splice(idx, 1);
      } else {
        this.cidadesSelecionadasExport.push(cidadeNome);
      }
    },

    isCidadeSelecionada(cidadeNome) {
      return this.cidadesSelecionadasExport.includes(cidadeNome);
    },

    async baixarPlanilhaExcel() {
      if (!this.cidadesSelecionadasExport || this.cidadesSelecionadasExport.length === 0) {
        alert('Selecione ao menos uma cidade para exportar a planilha.');
        return;
      }
      this.exportandoExcel = true;
      try {
        const payload = {
          cidades: this.cidadesSelecionadasExport,
          whatsapp_only: this.exportApenasWa,
          status: this.exportStatusFiltro
        };
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        const headers = { 'Content-Type': 'application/json' };
        if (csrfToken) headers['X-CSRF-Token'] = csrfToken;

        const resp = await fetch('/radar/exportar-excel', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error('Falha ao gerar o arquivo Excel.');
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        const agora = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        a.download = `radar_leads_multi_abas_${agora}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        this.modalExportAberto = false;
        this.alertaMsg = `Planilha gerada com sucesso! (${this.cidadesSelecionadasExport.length} abas de cidades)`;
      } catch (err) {
        alert('Erro ao exportar planilha Excel: ' + err.message);
      } finally {
        this.exportandoExcel = false;
      }
    }
  };
}
