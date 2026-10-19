/* M-One Prospector 24/7 Automation & Mode Switcher Methods (static/js/prospector-automacao.js)
   Módulo desacoplado para manter o padrão anti-monólito (< 500 linhas). */

function getProspectorAutomacaoMethods() {
  return {
    async carregarConfigAutomacao() {
      try {
        const resp = await fetch('/admin/prospeccao/api/automacao');
        const data = await resp.json();
        if (data.status === 'success' && data.config) {
          const cfg = data.config;
          this.automacao.ativo = !!cfg.ativo;
          this.automacao.modo = cfg.modo || 'turnos';
          this.automacao.limite = cfg.limite || 25;
          this.automacao.intervalo_min = cfg.intervalo_min || 120;
          this.automacao.pracas = cfg.pracas || [];
          this.automacao.pracas_str = (cfg.pracas || []).join(', ');
          this.automacao.nicho_slug = cfg.nicho_slug || this.radarForm.nicho || 'revenda-motos';
          this.automacao.ultimo_ciclo = cfg.ultimo_ciclo || '';
          this.automacao.ultima_praca = cfg.ultima_praca || '';
          this.automacao.ultimo_resultado = cfg.ultimo_resultado || '';
          this.automacao.total_auto = cfg.total_auto || 0;
          this.automacao.indice_rotacao = cfg.indice_rotacao || 0;
          this.automacao.proxima_praca = cfg.proxima_praca || '';
        }
      } catch (err) {
        console.error('Erro ao carregar automação:', err);
      }
    },

    selecionarModo(novoModo) {
      this.automacao.modo = novoModo;
      if (novoModo === 'turnos') {
        this.automacao.limite = 25;
      } else if (novoModo === 'rotacao') {
        this.automacao.limite = 15;
      } else if (novoModo === 'noturno') {
        this.automacao.limite = 60;
      } else if (novoModo === 'custom') {
        if (!this.automacao.intervalo_min) this.automacao.intervalo_min = 120;
      }
    },

    async salvarAutomacao(mostrarToast = true) {
      this.automacaoSalvando = true;
      try {
        const csrf = getCsrfToken();
        const pracasArr = (this.automacao.pracas_str || '')
          .split(',')
          .map(p => p.trim())
          .filter(Boolean);

        const payload = {
          ativo: !!this.automacao.ativo,
          modo: this.automacao.modo,
          limite: parseInt(this.automacao.limite, 10) || 20,
          intervalo_min: parseInt(this.automacao.intervalo_min, 10) || 120,
          pracas: pracasArr,
          nicho_slug: this.automacao.nicho_slug,
          csrf_token: csrf
        };

        const resp = await fetch('/admin/prospeccao/api/automacao', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.status === 'success') {
          if (data.config) {
            this.automacao.proxima_praca = data.config.proxima_praca;
            this.automacao.indice_rotacao = data.config.indice_rotacao;
          }
          if (mostrarToast) {
            this.alertaMsg = '✅ Configuração da Automação 24/7 gravada com sucesso!';
            this.alertaTipo = 'success';
          }
        } else {
          alert('Erro ao salvar automação: ' + (data.message || data.error));
        }
      } catch (err) {
        alert('Falha na comunicação: ' + err);
      } finally {
        this.automacaoSalvando = false;
      }
    },

    async executarAutomacaoAgora() {
      if (this.jobStatus.running) {
        alert('Já existe um processo de busca ativo no momento.');
        return;
      }
      this.automacaoExecutando = true;
      try {
        const csrf = getCsrfToken();
        const resp = await fetch('/admin/prospeccao/api/automacao/executar-agora', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ csrf_token: csrf })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          this.jobStatus.running = true;
          this.jobStatus.error = null;
          this.jobStatus.nicho = data.nicho;
          this.jobStatus.praca = data.praca_executada;
          this.jobStatus.current_lead = `Iniciando ciclo automático para ${data.praca_executada}...`;
          this.automacao.ultima_praca = data.praca_executada;
          this.automacao.proxima_praca = data.proxima_praca;
          this.alertaMsg = `⚡ Ciclo automático disparado com sucesso para '${data.praca_executada}' (${data.limite} leads)!`;
          this.alertaTipo = 'success';
          this.checarStatusJob();
        } else {
          alert(data.message || 'Não foi possível executar o ciclo no momento.');
        }
      } catch (err) {
        alert('Erro ao disparar ciclo: ' + err);
      } finally {
        this.automacaoExecutando = false;
      }
    },

    getRotuloCurtoModo(modo) {
      const mapa = {
        turnos: 'Turnos (3x/dia)',
        rotacao: 'Rotação 2h',
        noturno: 'Lote Noturno',
        custom: 'Custom'
      };
      return mapa[modo] || 'Automação';
    },

    formatarDataIso(isoStr) {
      if (!isoStr) return '—';
      try {
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return isoStr;
        const dia = String(d.getDate()).padStart(2, '0');
        const mes = String(d.getMonth() + 1).padStart(2, '0');
        const hora = String(d.getHours()).padStart(2, '0');
        const min = String(d.getMinutes()).padStart(2, '0');
        return `${dia}/${mes} às ${hora}:${min}`;
      } catch (e) {
        return isoStr;
      }
    }
  };
}
