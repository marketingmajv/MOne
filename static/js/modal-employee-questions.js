/**
 * M-One Employee Questions Editor Modal Controller (static/js/modal-employee-questions.js)
 * Gerencia no frontend o Modal Executivo de Edição das Perguntas dos Colaboradores:
 * - Troca rápida entre colaboradores (Abas / Seletor)
 * - Ocultar / Exibir pergunta com renumeração automática (1., 2., 3...)
 * - Adicionar nova pergunta, Duplicar na mesma lista, Espelhar para outro colaborador
 * - Reordenar (Subir / Descer), Editar (Título, Dica, Placeholder, Gabarito IA) e Excluir
 * - Restaurar Cartilha Original de fábrica
 */

function employeeQuestionsModal() {
  return {
    isOpen: false,
    loading: false,
    saving: false,
    hasUnsavedChanges: false,
    employees: [],
    selectedEmployeeKey: 'marisa',
    currentQuestions: [],
    editingIndex: null,
    copyDropdownIndex: null,
    toastMessage: '',
    toastSuccess: true,

    get currentEmployee() {
      return this.employees.find((e) => e.key === this.selectedEmployeeKey) || {};
    },

    get activeCount() {
      return this.currentQuestions.filter((q) => !q.hidden).length;
    },

    get hiddenCount() {
      return this.currentQuestions.filter((q) => q.hidden).length;
    },

    get otherEmployees() {
      return this.employees.filter((e) => e.key !== this.selectedEmployeeKey);
    },

    showToast(msg, isSuccess = true) {
      this.toastMessage = msg;
      this.toastSuccess = isSuccess;
      setTimeout(() => {
        if (this.toastMessage === msg) {
          this.toastMessage = '';
        }
      }, 4000);
    },

    async openModal(detail = {}) {
      const targetKey = (detail && detail.employeeKey) ? String(detail.employeeKey).toLowerCase().trim() : '';
      if (targetKey) {
        this.selectedEmployeeKey = targetKey;
      }
      this.isOpen = true;
      this.editingIndex = null;
      this.copyDropdownIndex = null;
      await this.loadQuestions(this.selectedEmployeeKey);
    },

    closeModal() {
      if (this.saving) return;
      if (this.hasUnsavedChanges) {
        if (!confirm('Existem alterações não salvas nas perguntas deste colaborador. Deseja fechar mesmo assim?')) {
          return;
        }
      }
      this.isOpen = false;
      this.hasUnsavedChanges = false;
      this.editingIndex = null;
      this.copyDropdownIndex = null;
    },

    async loadQuestions(empKey = '') {
      this.loading = true;
      try {
        const qParam = empKey ? `?employee_key=${encodeURIComponent(empKey)}` : '';
        const resp = await fetch(`/api/gestao-interna/perguntas${qParam}`);
        const res = await resp.json();
        if (res.success && res.data) {
          this.employees = res.data.employees || [];
          this.selectedEmployeeKey = res.data.selected_employee_key || empKey || 'marisa';
          this.syncCurrentQuestionsFromEmployees();
          this.hasUnsavedChanges = false;
        } else {
          this.showToast(res.error || 'Erro ao carregar perguntas.', false);
        }
      } catch (err) {
        this.showToast('Falha de comunicação ao carregar perguntas: ' + err.message, false);
      } finally {
        this.loading = false;
      }
    },

    syncCurrentQuestionsFromEmployees() {
      const emp = this.employees.find((e) => e.key === this.selectedEmployeeKey);
      const raw = emp && Array.isArray(emp.questions) ? emp.questions : [];
      this.currentQuestions = JSON.parse(JSON.stringify(raw));
      this.renumberQuestions();
    },

    async selectEmployee(empKey) {
      if (empKey === this.selectedEmployeeKey) return;
      if (this.hasUnsavedChanges) {
        if (!confirm(`Você possui alterações não salvas em @${this.selectedEmployeeKey}. Deseja descartá-las e trocar para @${empKey}?`)) {
          return;
        }
      }
      this.selectedEmployeeKey = empKey;
      this.editingIndex = null;
      this.copyDropdownIndex = null;
      this.hasUnsavedChanges = false;
      this.syncCurrentQuestionsFromEmployees();
    },

    stripNumberPrefix(str) {
      if (!str) return '';
      return String(str).trim().replace(/^\s*\d+\s*[\.\-\)]\s*/, '');
    },

    renumberQuestions() {
      let visNum = 1;
      this.currentQuestions.forEach((q) => {
        const clean = this.stripNumberPrefix(q.raw_title || q.label || 'Nova Pergunta');
        q.raw_title = clean;
        if (!q.hidden) {
          q.display_number = visNum;
          q.label = `${visNum}. ${clean}`;
          visNum += 1;
        } else {
          q.display_number = null;
          q.label = `[Oculta] ${clean}`;
        }
      });
    },

    markChanged() {
      this.hasUnsavedChanges = true;
      this.renumberQuestions();
    },

    toggleEdit(idx) {
      this.copyDropdownIndex = null;
      this.editingIndex = this.editingIndex === idx ? null : idx;
    },

    toggleHideQuestion(idx) {
      const q = this.currentQuestions[idx];
      if (!q) return;
      if (!q.hidden && this.activeCount <= 1) {
        alert('O colaborador precisa manter pelo menos 1 pergunta visível ativa no formulário.');
        return;
      }
      q.hidden = !q.hidden;
      this.markChanged();
      this.showToast(
        q.hidden
          ? '🙈 Pergunta ocultada (clique em Salvar Alterações para confirmar).'
          : '👁️ Pergunta reexibida e renumerada!'
      );
    },

    moveQuestion(idx, direction) {
      const targetIdx = idx + direction;
      if (targetIdx < 0 || targetIdx >= this.currentQuestions.length) return;
      const temp = this.currentQuestions[idx];
      this.currentQuestions.splice(idx, 1);
      this.currentQuestions.splice(targetIdx, 0, temp);
      if (this.editingIndex === idx) {
        this.editingIndex = targetIdx;
      } else if (this.editingIndex === targetIdx) {
        this.editingIndex = idx;
      }
      this.markChanged();
    },

    addNewQuestion() {
      const newQ = {
        id: 'new_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
        raw_title: 'Nova Pergunta da Rotina Semanal',
        label: '',
        help: 'Orientação sobre o que deve ser informado neste tópico.',
        placeholder: 'Descreva os resultados, números e observações da semana...',
        desired_answer: 'Relato objetivo, completo e com dados verificáveis conforme padrão da cartilha MAJ.',
        hidden: false,
      };
      this.currentQuestions.push(newQ);
      this.markChanged();
      this.editingIndex = this.currentQuestions.length - 1;
      this.showToast('➕ Nova pergunta adicionada! Edite os campos abaixo e clique em Salvar.');
    },

    duplicateQuestion(idx) {
      const orig = this.currentQuestions[idx];
      if (!orig) return;
      const copyQ = {
        id: 'new_' + Date.now() + '_' + Math.floor(Math.random() * 1000),
        raw_title: this.stripNumberPrefix(orig.raw_title || orig.label) + ' (Cópia)',
        label: '',
        help: orig.help || '',
        placeholder: orig.placeholder || '',
        desired_answer: orig.desired_answer || '',
        hidden: false,
      };
      this.currentQuestions.splice(idx + 1, 0, copyQ);
      this.markChanged();
      this.editingIndex = idx + 1;
      this.showToast('📋 Pergunta duplicada abaixo da original! Ajuste o título e salve.');
    },

    deleteQuestion(idx) {
      const q = this.currentQuestions[idx];
      if (!q) return;
      if (this.currentQuestions.length <= 1) {
        alert('Não é permitido excluir todas as perguntas. O colaborador deve possuir ao menos 1 pergunta.');
        return;
      }
      const title = q.raw_title || q.label;
      if (!confirm(`Deseja excluir a pergunta "${title}"?\n\nNota de Segurança: Caso existam respostas já salvas para esta pergunta em ciclos anteriores, elas continuarão preservadas no histórico.`)) {
        return;
      }
      this.currentQuestions.splice(idx, 1);
      if (this.editingIndex === idx) {
        this.editingIndex = null;
      }
      this.markChanged();
      this.showToast('🗑️ Pergunta removida da lista. Clique em Salvar Alterações para efetivar.');
    },

    async copyQuestionToOtherEmployee(idx, targetEmpKey) {
      const q = this.currentQuestions[idx];
      if (!q || !targetEmpKey) return;
      this.copyDropdownIndex = null;
      this.saving = true;
      try {
        const resp = await fetch('/api/gestao-interna/perguntas/copiar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_employee_key: targetEmpKey,
            question: q,
          }),
        });
        const res = await resp.json();
        if (res.success && res.data) {
          const targetEmp = this.employees.find((e) => e.key === targetEmpKey);
          const updatedTarget = (res.data.employees || []).find((e) => e.key === targetEmpKey);
          if (targetEmp && updatedTarget) {
            Object.assign(targetEmp, updatedTarget);
          }
          this.showToast(`📤 Pergunta copiada com sucesso para ${targetEmp ? targetEmp.name : '@' + targetEmpKey}!`, true);
        } else {
          this.showToast(res.error || 'Erro ao copiar pergunta.', false);
        }
      } catch (err) {
        this.showToast('Falha ao copiar pergunta: ' + err.message, false);
      } finally {
        this.saving = false;
      }
    },

    async saveQuestions(reloadAfter = false) {
      if (this.currentQuestions.length === 0) {
        alert('Adicione pelo menos 1 pergunta antes de salvar.');
        return;
      }
      for (let i = 0; i < this.currentQuestions.length; i++) {
        const t = this.stripNumberPrefix(this.currentQuestions[i].raw_title || '');
        if (!t) {
          alert(`A pergunta na posição #${i + 1} está sem título. Preencha o título antes de salvar.`);
          this.editingIndex = i;
          return;
        }
      }

      this.saving = true;
      try {
        const resp = await fetch('/api/gestao-interna/perguntas/salvar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            employee_key: this.selectedEmployeeKey,
            questions: this.currentQuestions,
          }),
        });
        const res = await resp.json();
        if (res.success && res.data) {
          this.employees = res.data.employees || [];
          this.syncCurrentQuestionsFromEmployees();
          this.hasUnsavedChanges = false;
          this.editingIndex = null;
          this.showToast(res.message || '✅ Alterações salvas com sucesso!', true);
          if (reloadAfter) {
            setTimeout(() => window.location.reload(), 500);
          }
        } else {
          this.showToast(res.error || 'Erro ao salvar perguntas.', false);
        }
      } catch (err) {
        this.showToast('Erro de comunicação ao salvar: ' + err.message, false);
      } finally {
        this.saving = false;
      }
    },

    async restoreDefaults() {
      const empName = this.currentEmployee.name || this.selectedEmployeeKey;
      if (!confirm(`Deseja restaurar as perguntas originais da cartilha de fábrica para ${empName}?\n\nTodas as customizações (perguntas adicionadas ou ocultadas) deste colaborador voltarão ao padrão inicial.`)) {
        return;
      }
      this.saving = true;
      try {
        const resp = await fetch('/api/gestao-interna/perguntas/restaurar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ employee_key: this.selectedEmployeeKey }),
        });
        const res = await resp.json();
        if (res.success && res.data) {
          this.employees = res.data.employees || [];
          this.syncCurrentQuestionsFromEmployees();
          this.hasUnsavedChanges = false;
          this.editingIndex = null;
          this.showToast(res.message || '🔄 Cartilha original restaurada!', true);
        } else {
          this.showToast(res.error || 'Erro ao restaurar padrão.', false);
        }
      } catch (err) {
        this.showToast('Falha ao restaurar cartilha: ' + err.message, false);
      } finally {
        this.saving = false;
      }
    }
  };
}

window.employeeQuestionsModal = employeeQuestionsModal;

