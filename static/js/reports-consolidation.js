/**
 * M-One Reports Consolidation & Sectorized Analysis App (static/js/reports-consolidation.js)
 * Organiza a Análise Interna em 5 Setores Oficiais e habilita o Histórico Multi-Ciclos.
 * Modular e estritamente < 500 linhas.
 */

window.CANONICAL_MAJ_SECTORS = [
  {
    key: 'financeiro',
    label: 'Financeiro & Faturamento',
    shortLabel: 'Financeiro',
    icon: '💰',
    color: '#10b981',
    responsibles: 'Marisa',
    employees: [{ key: 'marisa', name: 'Marisa' }]
  },
  {
    key: 'estoque',
    label: 'Estoque & Galpões',
    shortLabel: 'Estoque',
    icon: '📦',
    color: '#f59e0b',
    responsibles: 'Jhon',
    employees: [{ key: 'jhon', name: 'Jhon' }]
  },
  {
    key: 'oficina',
    label: 'Oficina & Pós-Venda',
    shortLabel: 'Oficina & Pós-Venda',
    icon: '🔧',
    color: '#06b6d4',
    responsibles: 'Ricardo & Léo',
    employees: [{ key: 'ricardo', name: 'Ricardo' }, { key: 'leo', name: 'Léo' }]
  },
  {
    key: 'comercial',
    label: 'Comercial & Atacado',
    shortLabel: 'Comercial & Atacado',
    icon: '🤝',
    color: '#8b5cf6',
    responsibles: 'Luiza, Gabriel & Gustavo',
    employees: [{ key: 'luiza', name: 'Luiza' }, { key: 'gabriel', name: 'Gabriel' }, { key: 'gustavo', name: 'Gustavo' }]
  },
  {
    key: 'marketing_sistemas',
    label: 'Marketing & Sistemas',
    shortLabel: 'Marketing & Sistemas',
    icon: '⚡',
    color: '#38bdf8',
    responsibles: 'Fauzer',
    employees: [{ key: 'fauzer', name: 'Fauzer' }]
  }
];

function reportsConsolidationApp() {
  return {
    analysis: window.__INTERNAL_ANALYSIS__ || {},
    isCurator: window.__IS_CURATOR__ || false,
    isGenerating: false,
    isSaving: false,
    isSimulating: false,
    isPublishing: false,
    curatorEditMode: false,
    statusMsg: '',

    // Navegação Setorizada & Multi-Ciclos
    viewMode: 'cycle', // 'cycle' | 'history'
    activeSector: 'all', // 'all' | sectorKey
    sectionFilter: 'all', // 'all' | 'gargalos' | 'observacoes' | 'decisoes' | 'destaques'
    showMasterReport: false,
    canonicalSectors: window.CANONICAL_MAJ_SECTORS,

    // Histórico Multi-Ciclos
    loadingHistory: false,
    historyData: null,
    historyError: '',
    historySectorFilter: 'all',
    historyTypeFilter: 'all',

    getCsrfToken() {
      const meta = document.querySelector('meta[name="csrf-token"]');
      if (meta && meta.content) return meta.content;
      const inp = document.querySelector('input[name="csrf_token"]');
      return inp ? inp.value : '';
    },

    get status() {
      return (this.analysis && this.analysis.status) ? this.analysis.status : 'curating';
    },

    get isPublished() {
      return this.status === 'published';
    },

    get currentData() {
      if (!this.analysis) return {};
      return this.analysis.curated_data || this.analysis.ai_summary || {};
    },

    get radarAlerts() {
      return (this.currentData && Array.isArray(this.currentData.radar_alerts)) ? this.currentData.radar_alerts : [];
    },

    get pautaDecisoes() {
      return (this.currentData && Array.isArray(this.currentData.pauta_decisoes)) ? this.currentData.pauta_decisoes : [];
    },

    get pilares() {
      return (this.currentData && this.currentData.pilares && typeof this.currentData.pilares === 'object') ? this.currentData.pilares : {};
    },

    get gargalosCronicos() { return (this.currentData && this.currentData.gargalos_cronicos) || []; },
    get evolucaoColaboradores() { return (this.currentData && this.currentData.evolucao_colaboradores) || []; },
    get relatorioMasterColaboradores() { return (this.currentData && this.currentData.relatorio_master_colaboradores) || []; },
    get whatsappBlock() { return (this.currentData && (this.currentData.whatsapp_executive_block || this.currentData.whatsapp_block)) || ''; },
    get whatsappMasterBlock() { return (this.currentData && this.currentData.whatsapp_master_block) || ''; },

    _copyToClipboard(text, successMsg, emptyMsg) {
      if (!text) { alert(emptyMsg); return; }
      navigator.clipboard.writeText(text).then(() => alert(successMsg)).catch(err => alert('Erro ao copiar: ' + err));
    },
    copyWhatsappBlock() {
      this._copyToClipboard(this.whatsappBlock, '📋 Pauta Executiva copiada para o WhatsApp!', 'Nenhum resumo executivo de WhatsApp disponível.');
    },
    copyWhatsappMasterBlock() {
      this._copyToClipboard(this.whatsappMasterBlock, '📋 Relatório MASTER copiado para o WhatsApp!', 'Nenhum Relatório MASTER disponível. Gere a síntese de IA primeiro.');
    },

    get hasAnyContent() {
      if (this.radarAlerts.length || this.pautaDecisoes.length) return true;
      return this.canonicalSectors.some(s =>
        this.getSectorObservacoes(s.key).length > 0 || this.getSectorDestaques(s.key).length > 0
      );
    },

    get visibleSectors() {
      if (this.activeSector === 'all') return this.canonicalSectors;
      return this.canonicalSectors.filter(s => s.key === this.activeSector);
    },

    normalizeSectorKey(rawPilar, envolvidos, extraText) {
      const val = String(rawPilar || '').toLowerCase().trim();
      const valid = this.canonicalSectors.map(s => s.key);
      if (valid.includes(val)) return val;

      const people = Array.isArray(envolvidos) ? envolvidos.join(' ').toLowerCase() : '';
      const hay = `${val} ${people} ${String(extraText || '').toLowerCase()}`;

      if (val.includes('financ') || val.includes('caixa') || val.includes('faturam') || val.includes('marisa')) return 'financeiro';
      if (val.includes('estoq') || val.includes('galp') || val.includes('patio') || val.includes('jhon')) return 'estoque';
      if (val.includes('oficina') || val.includes('pos_venda') || val.includes('pós-venda') || val.includes('peca') || val.includes('peça') || val.includes('ricardo') || val.includes('leo') || val.includes('léo')) return 'oficina';
      if (val.includes('comercial') || val.includes('venda') || val.includes('atacado') || val.includes('luiza') || val.includes('gabriel') || val.includes('gustavo')) return 'comercial';
      if (val.includes('market') || val.includes('sistem') || val.includes('ti') || val.includes('process') || val.includes('fauzer')) return 'marketing_sistemas';

      if (hay.includes('marisa') || hay.includes('boleto') || hay.includes('mercado pago') || hay.includes('caixa')) return 'financeiro';
      if (hay.includes('jhon') || hay.includes('chassi') || hay.includes('contagem') || hay.includes('galpão')) return 'estoque';
      if (hay.includes('ricardo') || hay.includes('léo') || hay.includes('leo') || hay.includes('bateria') || hay.includes('oficina')) return 'oficina';
      if (hay.includes('luiza') || hay.includes('gabriel') || hay.includes('gustavo') || hay.includes('revenda') || hay.includes('atacado')) return 'comercial';
      if (hay.includes('fauzer') || hay.includes('meta ads') || hay.includes('botconversa') || hay.includes('m-one') || hay.includes('gmb')) return 'marketing_sistemas';
      return 'comercial';
    },

    ensureSectorPilar(sectorKey) {
      const target = this.analysis.curated_data ? this.analysis.curated_data : (this.analysis.ai_summary || {});
      if (!target.pilares) target.pilares = {};
      if (!target.pilares[sectorKey]) {
        const meta = this.canonicalSectors.find(s => s.key === sectorKey) || {};
        target.pilares[sectorKey] = {
          titulo: meta.label || sectorKey,
          responsavel: meta.responsibles || '',
          destaques: [],
          pontos_atencao: []
        };
      }
      if (!Array.isArray(target.pilares[sectorKey].destaques)) target.pilares[sectorKey].destaques = [];
      if (!Array.isArray(target.pilares[sectorKey].pontos_atencao)) target.pilares[sectorKey].pontos_atencao = [];
      return target.pilares[sectorKey];
    },

    getSectorGargalos(sectorKey) {
      return this.radarAlerts.filter(a =>
        this.normalizeSectorKey(a.pilar || a.pilar_label, a.envolvidos, `${a.title || ''} ${a.description || ''}`) === sectorKey
      );
    },

    getSectorDecisoes(sectorKey) {
      return this.pautaDecisoes.filter(d =>
        this.normalizeSectorKey(d.pilar, null, `${d.title || ''} ${d.context || ''}`) === sectorKey
      );
    },

    getSectorObservacoes(sectorKey) {
      const p = this.pilares[sectorKey];
      return (p && Array.isArray(p.pontos_atencao)) ? p.pontos_atencao : [];
    },

    getSectorDestaques(sectorKey) {
      const p = this.pilares[sectorKey];
      return (p && Array.isArray(p.destaques)) ? p.destaques : [];
    },

    get totalGargalosCount() {
      return this.radarAlerts.length;
    },

    get highGargalosCount() {
      return this.radarAlerts.filter(a => a.severity === 'high').length;
    },

    get totalObservacoesCount() {
      return this.canonicalSectors.reduce((acc, s) => acc + this.getSectorObservacoes(s.key).length, 0);
    },

    get totalDestaquesCount() {
      return this.canonicalSectors.reduce((acc, s) => acc + this.getSectorDestaques(s.key).length, 0);
    },

    get pendingDecisoesCount() {
      return this.pautaDecisoes.filter(d => !d.status || d.status === 'pending' || d.status === 'postponed').length;
    },

    getSectorHealth(sectorKey) {
      const gargalos = this.getSectorGargalos(sectorKey);
      const obs = this.getSectorObservacoes(sectorKey);
      const decs = this.getSectorDecisoes(sectorKey).filter(d => !d.status || d.status === 'pending');

      if (gargalos.some(g => g.severity === 'high')) {
        return { level: 'critical', badgeClass: 'rc-badge-red', label: '🔴 Crítico' };
      }
      if (gargalos.length > 0 || obs.length > 0 || decs.length > 0) {
        return { level: 'warning', badgeClass: 'rc-badge-amber', label: '🟡 Atenção' };
      }
      return { level: 'stable', badgeClass: 'rc-badge-green', label: '🟢 Estável' };
    },

    sectorMatchesFilter(sectorKey) {
      if (this.sectionFilter === 'all') return true;
      if (this.sectionFilter === 'gargalos') return this.getSectorGargalos(sectorKey).length > 0 || this.curatorEditMode;
      if (this.sectionFilter === 'observacoes') return this.getSectorObservacoes(sectorKey).length > 0 || this.curatorEditMode;
      if (this.sectionFilter === 'decisoes') return this.getSectorDecisoes(sectorKey).length > 0 || this.curatorEditMode;
      if (this.sectionFilter === 'destaques') return this.getSectorDestaques(sectorKey).length > 0 || this.curatorEditMode;
      return true;
    },

    toggleSectionFilter(type) {
      this.sectionFilter = (this.sectionFilter === type) ? 'all' : type;
    },

    selectSector(sectorKey) {
      this.activeSector = sectorKey;
      this.viewMode = 'cycle';
    },

    // --- Edição do Curador ---
    addAlert(sectorKey) {
      if (!this.currentData.radar_alerts) this.currentData.radar_alerts = [];
      const meta = this.canonicalSectors.find(s => s.key === sectorKey) || {};
      this.currentData.radar_alerts.push({
        id: 'alert_' + Date.now(),
        pilar: sectorKey,
        pilar_label: meta.shortLabel || sectorKey,
        severity: 'high',
        title: 'Novo gargalo identificado',
        description: '',
        envolvidos: meta.employees ? [meta.employees[0].name] : []
      });
    },

    removeAlert(alertObj) {
      const idx = this.radarAlerts.indexOf(alertObj);
      if (idx > -1) this.currentData.radar_alerts.splice(idx, 1);
    },

    addDecision(sectorKey) {
      if (!this.currentData.pauta_decisoes) this.currentData.pauta_decisoes = [];
      this.currentData.pauta_decisoes.push({
        id: 'dec_' + Date.now(),
        pilar: sectorKey,
        title: 'Nova deliberação para Diretoria',
        context: '',
        proposta: '',
        status: 'pending',
        deliberacao_texto: ''
      });
    },

    removeDecision(decObj) {
      const idx = this.pautaDecisoes.indexOf(decObj);
      if (idx > -1) this.currentData.pauta_decisoes.splice(idx, 1);
    },

    addObservacao(sectorKey) {
      const p = this.ensureSectorPilar(sectorKey);
      p.pontos_atencao.push('Nova observação / ponto de atenção');
    },

    removeObservacao(sectorKey, idx) {
      const p = this.ensureSectorPilar(sectorKey);
      p.pontos_atencao.splice(idx, 1);
    },

    addDestaque(sectorKey) {
      const p = this.ensureSectorPilar(sectorKey);
      p.destaques.push('Novo destaque positivo da semana');
    },

    removeDestaque(sectorKey, idx) {
      const p = this.ensureSectorPilar(sectorKey);
      p.destaques.splice(idx, 1);
    },

    // --- Histórico Multi-Ciclos ---
    async switchToHistory() {
      this.viewMode = 'history';
      if (!this.historyData && !this.loadingHistory) {
        await this.loadHistory();
      }
    },

    async loadHistory(forceReload) {
      if (this.historyData && !forceReload) return;
      this.loadingHistory = true;
      this.historyError = '';
      try {
        const res = await fetch('/admin/plano/api/analise-interna/historico-ciclos');
        const data = await res.json();
        if (data.status === 'success') {
          this.historyData = data.history;
        } else {
          this.historyError = data.message || 'Erro ao carregar histórico.';
        }
      } catch (e) {
        this.historyError = 'Falha de comunicação ao carregar histórico: ' + e;
      } finally {
        this.loadingHistory = false;
      }
    },

    get filteredRecurringGargalos() {
      const list = (this.historyData && this.historyData.recurring_gargalos) ? this.historyData.recurring_gargalos : [];
      if (this.historySectorFilter === 'all') return list;
      return list.filter(item => item.sector_key === this.historySectorFilter);
    },

    get filteredUnresolvedDecisions() {
      const list = (this.historyData && this.historyData.unresolved_decisions) ? this.historyData.unresolved_decisions : [];
      if (this.historySectorFilter === 'all') return list;
      return list.filter(item => item.sector_key === this.historySectorFilter);
    },

    getHistoryCycleSectors(cycleItem) {
      const sectors = cycleItem && cycleItem.sectors ? cycleItem.sectors : {};
      const keys = this.historySectorFilter === 'all'
        ? this.canonicalSectors.map(s => s.key)
        : [this.historySectorFilter];

      return keys
        .map(k => sectors[k])
        .filter(sec => {
          if (!sec) return false;
          if (this.historyTypeFilter === 'gargalos') return sec.gargalos && sec.gargalos.length > 0;
          if (this.historyTypeFilter === 'observacoes') return sec.observacoes && sec.observacoes.length > 0;
          if (this.historyTypeFilter === 'decisoes') return sec.decisoes && sec.decisoes.length > 0;
          return (sec.gargalos && sec.gargalos.length > 0) ||
                 (sec.observacoes && sec.observacoes.length > 0) ||
                 (sec.decisoes && sec.decisoes.length > 0);
        });
    },

    // --- Ações da API ---
    async gerarIA() {
      if (!confirm('Deseja executar a síntese setorizada dos relatórios com IA?')) return;
      this.isGenerating = true;
      this.statusMsg = 'Lendo relatórios e setorizando em 5 áreas...';
      try {
        const res = await fetch('/admin/plano/api/analise-interna/gerar-ia', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
          body: JSON.stringify({ cycle_id: window.__CYCLE_ID__ })
        });
        const data = await res.json();
        this.isGenerating = false;
        if (data.status === 'success') {
          this.analysis = data.analysis;
          this.historyData = null;
          alert('✅ ' + data.message);
        } else {
          alert('❌ ' + (data.message || 'Erro ao gerar síntese.'));
        }
      } catch (e) {
        this.isGenerating = false;
        alert('Falha na comunicação: ' + e);
      }
    },

    async salvarCuradoria() {
      this.isSaving = true;
      try {
        const res = await fetch('/admin/plano/api/analise-interna/salvar-curadoria', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
          body: JSON.stringify({ cycle_id: window.__CYCLE_ID__, curated_data: this.currentData })
        });
        const data = await res.json();
        this.isSaving = false;
        if (data.status === 'success') {
          this.analysis = data.analysis;
          this.curatorEditMode = false;
          this.historyData = null;
          alert('✅ ' + data.message);
        } else {
          alert('❌ ' + (data.message || 'Erro ao salvar.'));
        }
      } catch (e) {
        this.isSaving = false;
        alert('Erro ao salvar: ' + e);
      }
    },

    async liberarParaDiretoria() {
      if (!confirm('Deseja homologar e LIBERAR a Análise Interna para Jam e Geysa?')) return;
      this.isPublishing = true;
      try {
        const res = await fetch('/admin/plano/api/analise-interna/liberar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
          body: JSON.stringify({ cycle_id: window.__CYCLE_ID__, curated_data: this.currentData })
        });
        const data = await res.json();
        this.isPublishing = false;
        if (data.status === 'success') {
          this.analysis = data.analysis;
          this.historyData = null;
          alert('🚀 ' + data.message);
        } else {
          alert('❌ ' + (data.message || 'Erro ao liberar.'));
        }
      } catch (e) {
        this.isPublishing = false;
        alert('Erro ao liberar: ' + e);
      }
    },

    async salvarDeliberacoes() {
      this.isSaving = true;
      try {
        const res = await fetch('/admin/plano/api/analise-interna/salvar-deliberacoes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
          body: JSON.stringify({ cycle_id: window.__CYCLE_ID__, meeting_decisions: this.pautaDecisoes })
        });
        const data = await res.json();
        this.isSaving = false;
        if (data.status === 'success') {
          this.historyData = null;
          alert('✅ Deliberações da reunião registradas com sucesso no banco!');
        } else {
          alert('❌ ' + (data.message || 'Erro ao salvar deliberações.'));
        }
      } catch (e) {
        this.isSaving = false;
        alert('Erro: ' + e);
      }
    },

    async simularDados() {
      if (!confirm('Deseja carregar dados de demonstração realistas para os colaboradores para teste?')) return;
      this.isSimulating = true;
      try {
        const res = await fetch('/admin/plano/api/analise-interna/simular-dados', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrfToken() },
          body: JSON.stringify({ cycle_id: window.__CYCLE_ID__ })
        });
        const data = await res.json();
        this.isSimulating = false;
        if (data.status === 'success') {
          this.analysis = data.analysis;
          this.historyData = null;
          alert('🧪 ' + data.message);
          window.location.reload();
        } else {
          alert('❌ ' + (data.message || 'Erro na simulação.'));
        }
      } catch (e) {
        this.isSimulating = false;
        alert('Erro na simulação: ' + e);
      }
    }
  };
}

