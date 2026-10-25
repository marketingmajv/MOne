/**
 * M-One Implementation Plan & Governance Dashboard (static/js/implementation-plan.js)
 * Componente reativo Alpine.js para o Painel da Diretoria e Governança MAJ.
 * Segregação estrita (< 500 linhas).
 */

function implementationPlanApp() {
  return {
    activeTab: window.__ACTIVE_TAB__ || 'dashboard',
    searchMember: '',
    showDeadlineModal: false,
    showReportModal: false,
    showDocLinksModal: false,
    showMismatchModal: false,
    mismatchData: {},
    isSyncingDoc: false,
    syncingStatusTitle: 'Sincronizando com IA...',
    syncingStatusDesc: 'Lendo o Google Doc e extraindo as respostas...',
    selectedEmployee: 'marisa',
    selectedHistoryCycleId: null,
    employeesData: window.__EMPLOYEES_DATA__ || [],
    docLinksData: window.__DOC_LINKS__ || {},
    currentCycleId: window.__CYCLE_ID__ || 0,

    get currentEmployee() {
      return (this.employeesData || []).find(e => e.key === this.selectedEmployee) || null;
    },

    get activeReportData() {
      if (!this.currentEmployee) return null;
      const hist = this.currentEmployee.history || [];
      if (!hist.length) return this.currentEmployee;
      if (!this.selectedHistoryCycleId) return hist[0];
      return hist.find(h => h.cycle_id === this.selectedHistoryCycleId) || hist[0];
    },

    init() {
      if (!this.activeTab) {
        this.activeTab = (window.__ACTIVE_TAB__ && window.__ACTIVE_TAB__.trim()) ? window.__ACTIVE_TAB__.trim() : 'dashboard';
      }
    },

    openReport(key) {
      if (!key) return;
      this.selectedEmployee = key;
      this.selectedHistoryCycleId = null;
      this.showReportModal = true;
    },

    openEvaluation(key) {
      if (!key) return;
      if (typeof window.openEvaluationModal === 'function') {
        window.openEvaluationModal(this.currentCycleId, key);
      } else {
        window.dispatchEvent(new CustomEvent('open-evaluation-modal', {
          detail: { cycleId: this.currentCycleId, employeeKey: key }
        }));
      }
    },

    async analyzeAllAI() {
      if (!confirm('Deseja iniciar a aferição com IA para todos os colaboradores deste ciclo?')) return;
      this.isSyncingDoc = true;
      this.syncingStatusTitle = 'Aferição em Lote com IA (Gemini)';
      this.syncingStatusDesc = 'Confrontando Respostas Fornecidas vs Desejadas para os 7 colaboradores...';
      try {
        const csrfEl = document.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfEl ? csrfEl.value : '';
        const res = await fetch('/api/relatorio/analisar-todos', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({ cycle_id: this.currentCycleId })
        });
        const data = await res.json();
        this.isSyncingDoc = false;
        if (data.success) {
          alert('✅ ' + (data.message || 'Aferição concluída!'));
          window.location.reload();
        } else {
          alert('❌ ' + (data.error || 'Erro ao processar'));
        }
      } catch (err) {
        this.isSyncingDoc = false;
        alert('Falha na comunicação: ' + err);
      }
    },

    async saveDocLink(key, url) {
      if (!url) {
        alert('Informe a URL do Google Doc.');
        return;
      }
      try {
        const res = await fetch('/admin/plano/api/doc-links', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ employee_key: key, google_doc_url: url })
        });
        const data = await res.json();
        if (data.status === 'success') {
          this.docLinksData = data.links || this.docLinksData;
          alert('Link do Google Doc salvo com sucesso!');
        } else {
          alert(data.message || 'Erro ao salvar link.');
        }
      } catch (err) {
        alert('Falha na comunicação: ' + err);
      }
    },

    async syncEmployeeDoc(key, force = false) {
      this.isSyncingDoc = true;
      this.syncingStatusTitle = 'Sincronizando com IA';
      this.syncingStatusDesc = 'Conectando ao Google Docs, auditando atribuições e extraindo respostas...';
      try {
        const res = await fetch('/admin/plano/api/sync-doc', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cycle_id: this.currentCycleId, employee_key: key, force: force })
        });
        const data = await res.json();
        this.isSyncingDoc = false;

        if (data.status === 'blank') {
          alert('ℹ️ ' + data.message);
        } else if (data.status === 'mismatch') {
          this.mismatchData = data;
          this.showMismatchModal = true;
        } else if (data.status === 'success') {
          alert('✅ ' + data.message);
          window.location.reload();
        } else {
          alert('❌ ' + (data.message || 'Erro ao sincronizar documento.'));
        }
      } catch (err) {
        this.isSyncingDoc = false;
        alert('Erro ao sincronizar: ' + err);
      }
    },

    forceSyncMismatch() {
      this.showMismatchModal = false;
      if (this.mismatchData && this.mismatchData.employee_key) {
        this.syncEmployeeDoc(this.mismatchData.employee_key, true);
      }
    },

    async saveAndResyncMismatch() {
      const input = document.getElementById('mismatch-corrected-url');
      const newUrl = input ? input.value.trim() : '';
      if (!newUrl) {
        alert('Informe a URL correta do Google Doc.');
        return;
      }
      const empKey = this.mismatchData.employee_key;
      if (!empKey) {
        alert('Chave do colaborador não identificada.');
        return;
      }

      this.showMismatchModal = false;
      this.isSyncingDoc = true;
      this.syncingStatusTitle = 'Atualizando Link & Ressincronizando';
      this.syncingStatusDesc = 'Salvando o novo link oficial e extraindo respostas com IA...';

      try {
        const resSave = await fetch('/admin/plano/api/doc-links', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ employee_key: empKey, google_doc_url: newUrl })
        });
        const saveResult = await resSave.json();
        if (saveResult.status !== 'success') {
          this.isSyncingDoc = false;
          alert('Erro ao salvar novo link: ' + (saveResult.message || 'Falha'));
          return;
        }
        this.docLinksData = saveResult.links || this.docLinksData;

        const resSync = await fetch('/admin/plano/api/sync-doc', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cycle_id: this.currentCycleId, employee_key: empKey, custom_url: newUrl, force: false })
        });
        const syncResult = await resSync.json();
        this.isSyncingDoc = false;

        if (syncResult.status === 'blank') {
          alert('ℹ️ Link atualizado! ' + syncResult.message);
          window.location.reload();
        } else if (syncResult.status === 'mismatch') {
          this.mismatchData = syncResult;
          this.showMismatchModal = true;
        } else if (syncResult.status === 'success') {
          alert('✅ ' + syncResult.message);
          window.location.reload();
        } else {
          alert('❌ ' + (syncResult.message || 'Erro ao sincronizar documento.'));
        }
      } catch (err) {
        this.isSyncingDoc = false;
        alert('Erro na operação: ' + err);
      }
    },

    triggerDocxUpload(employeeKey) {
      const el = document.getElementById('docx-file-input-' + employeeKey);
      if (el) {
        el.click();
      } else {
        const globalInput = document.getElementById('docx-file-input-global');
        if (globalInput) {
          globalInput.dataset.empKey = employeeKey;
          globalInput.click();
        }
      }
    },

    async handleDocxSelected(event, specificKey = null) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;

      const empKey = specificKey || event.target.dataset.empKey;
      if (!empKey) {
        alert('Colaborador não identificado para upload.');
        return;
      }

      const lowerName = file.name.toLowerCase();
      const isDocx = lowerName.endsWith('.docx');
      const isTxt = lowerName.endsWith('.txt');
      if (!isDocx && !isTxt) {
        alert('Por favor, selecione um arquivo válido (.docx ou .txt).');
        event.target.value = '';
        return;
      }

      this.isSyncingDoc = true;
      this.syncingStatusTitle = isTxt ? 'Processando Relatório TXT' : 'Processando Relatório DOCX';
      this.syncingStatusDesc = `Lendo o arquivo '${file.name}', extraindo texto e auditando com IA...`;

      const formData = new FormData();
      formData.append('cycle_id', this.currentCycleId);
      formData.append('employee_key', empKey);
      formData.append('file', file);
      formData.append('force', 'false');

      try {
        const res = await fetch('/admin/plano/api/upload-docx', {
          method: 'POST',
          headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: formData
        });

        const contentType = res.headers.get('content-type') || '';
        let data = null;
        if (contentType.includes('application/json')) {
          data = await res.json();
        } else {
          const text = await res.text();
          if (res.status === 401 || res.status === 403 || text.includes('<!doctype') || text.includes('<html')) {
            throw new Error('Sua sessão de login expirou ou você não possui permissão. Recarregue a página e faça login novamente.');
          } else {
            throw new Error(`Resposta inesperada do servidor (HTTP ${res.status}): ${text.substring(0, 120)}`);
          }
        }

        this.isSyncingDoc = false;
        event.target.value = '';

        if (data.status === 'blank') {
          alert('ℹ️ ' + data.message);
        } else if (data.status === 'mismatch') {
          this.mismatchData = data;
          this.showMismatchModal = true;
        } else if (data.status === 'success') {
          alert('✅ ' + data.message);
          window.location.reload();
        } else {
          alert('❌ ' + (data.message || 'Erro ao processar arquivo.'));
        }
      } catch (err) {
        this.isSyncingDoc = false;
        event.target.value = '';
        alert('Falha no upload do relatório: ' + (err.message || err));
      }
    },

    async syncAllDocs() {
      if (!confirm('Deseja iniciar a sincronização automática de todos os Google Docs com IA?')) return;
      this.isSyncingDoc = true;
      this.syncingStatusTitle = 'Sincronização em Lote com IA';
      this.syncingStatusDesc = 'Processando documentos de todos os colaboradores...';
      try {
        const res = await fetch('/admin/plano/api/sync-all-docs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cycle_id: this.currentCycleId })
        });
        const data = await res.json();
        this.isSyncingDoc = false;

        let msg = `Sincronização em Lote Concluída!\n\n` +
                  `✓ Relatórios Entregues: ${data.sucessos}\n` +
                  `📝 Em Branco (Aguardando preenchimento): ${data.em_branco || 0}\n` +
                  `⚠️ Incompatibilidades/Divergências: ${data.divergencias}\n` +
                  `❌ Erros de Conexão: ${data.erros}`;
        alert(msg);
        window.location.reload();
      } catch (err) {
        this.isSyncingDoc = false;
        alert('Erro no lote: ' + err);
      }
    },

    openEvaluation(employeeKey) {
      if (typeof window.openEvaluationModal === 'function') {
        window.openEvaluationModal(this.currentCycleId, employeeKey);
      } else {
        window.dispatchEvent(new CustomEvent('open-evaluation-modal', {
          detail: { cycleId: this.currentCycleId, employeeKey: employeeKey }
        }));
      }
    },

    async analyzeAllAI() {
      if (!confirm('Deseja confrontar respostas e aferir com IA todos os colaboradores deste ciclo?')) return;
      this.isSyncingDoc = true;
      this.syncingStatusTitle = 'Aferição Executiva em Lote com IA';
      this.syncingStatusDesc = 'Confrontando respostas desejadas vs fornecidas com o Gemini...';
      try {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
        const res = await fetch('/api/relatorio/analisar-todos', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({ cycle_id: this.currentCycleId })
        });
        const data = await res.json();
        this.isSyncingDoc = false;
        if (data.success) {
          alert(`✅ Aferição em Lote Concluída!\n\n${data.message || 'Todos os colaboradores foram avaliados.'}`);
          window.location.reload();
        } else {
          alert('❌ ' + (data.error || 'Erro ao processar aferição em lote.'));
        }
      } catch (err) {
        this.isSyncingDoc = false;
        alert('Erro de conexão na aferição em lote: ' + (err.message || err));
      }
    }
  };
}
