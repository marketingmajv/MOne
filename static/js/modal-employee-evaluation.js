/**
 * M-One Executive Employee Evaluation Modal Component (Alpine.js)
 * Gerencia a diagramação em 1 coluna por pergunta, ativação por pills/chips
 * (Registrado, Demanda Jam, Demanda Geysa, Demanda Fauzer) e geração dos 4 Relatórios WhatsApp.
 */

function employeeEvaluationModal() {
  return {
    isOpen: false,
    loadingData: false,
    loading: false,
    saving: false,
    loadingSuggestion: null,
    toastMsg: '',
    toastSuccess: true,
    cycleId: null,
    employeeKey: '',
    employeeData: {},
    qActions: {},
    agreementsJamGeysa: '',
    agreementsFauzer: '',
    activeReportTab: 'employee',
    copiedTab: null,

    init() {
      window.openEvaluationModal = (cycleId, empKey) => {
        this.openModal({ cycleId: cycleId, employeeKey: empKey });
      };
      window.addEventListener('open-evaluation-modal', (e) => {
        if (e && e.detail) {
          this.openModal(e.detail);
        }
      });
    },

    openModal(detail) {
      this.cycleId = detail.cycleId;
      this.employeeKey = detail.employeeKey;
      this.isOpen = true;
      this.toastMsg = '';
      this.activeReportTab = 'employee';
      this.fetchDetails();
    },

    closeModal() {
      this.isOpen = false;
      this.toastMsg = '';
    },

    showToast(msg, success = true) {
      this.toastMsg = msg;
      this.toastSuccess = success;
      setTimeout(() => { this.toastMsg = ''; }, 4500);
    },

    async fetchDetails() {
      if (!this.cycleId || !this.employeeKey) return;
      this.loadingData = true;
      try {
        const resp = await fetch(`/api/relatorio/detalhes/${this.cycleId}/${this.employeeKey}`);
        const result = await resp.json();
        if (result.success && result.data) {
          this.employeeData = result.data;
          this.qActions = {};

          const rawActions = this.employeeData.director_actions || {};
          const questions = this.employeeData.triad_questions || [];

          questions.forEach(q => {
            const qId = String(q.id);
            const act = rawActions[qId] || {};
            const dJam = act.demand_jam || '';
            const dGeysa = act.demand_geysa || '';
            const dFauzer = act.demand_fauzer || '';

            this.qActions[qId] = {
              acknowledged: !!act.acknowledged,
              employee_feedback: act.employee_feedback || '',
              has_jam: !!(dJam && dJam.trim()),
              demand_jam: dJam,
              has_geysa: !!(dGeysa && dGeysa.trim()),
              demand_geysa: dGeysa,
              has_fauzer: !!(dFauzer && dFauzer.trim()),
              demand_fauzer: dFauzer
            };
          });

          this.agreementsJamGeysa = this.employeeData.agreements_jam_geysa || '';
          this.agreementsFauzer = this.employeeData.agreements_fauzer || '';
        } else {
          this.showToast(result.error || 'Erro ao carregar dados.', false);
        }
      } catch (e) {
        this.showToast('Erro de conexão ao buscar detalhes.', false);
      } finally {
        this.loadingData = false;
      }
    },

    toggleAction(qId, type) {
      const id = String(qId);
      if (!this.qActions[id]) {
        this.qActions[id] = {
          acknowledged: false, employee_feedback: '',
          has_jam: false, demand_jam: '',
          has_geysa: false, demand_geysa: '',
          has_fauzer: false, demand_fauzer: ''
        };
      }

      if (type === 'acknowledged') {
        this.qActions[id].acknowledged = !this.qActions[id].acknowledged;
      } else if (type === 'jam') {
        this.qActions[id].has_jam = !this.qActions[id].has_jam;
      } else if (type === 'geysa') {
        this.qActions[id].has_geysa = !this.qActions[id].has_geysa;
      } else if (type === 'fauzer') {
        this.qActions[id].has_fauzer = !this.qActions[id].has_fauzer;
      }
    },

    preparePayload() {
      const commentsPayload = {};
      for (const qId in this.qActions) {
        const a = this.qActions[qId];
        commentsPayload[qId] = {
          acknowledged: !!a.acknowledged,
          employee_feedback: a.employee_feedback || '',
          demand_jam: a.has_jam ? (a.demand_jam || '') : '',
          demand_geysa: a.has_geysa ? (a.demand_geysa || '') : '',
          demand_fauzer: a.has_fauzer ? (a.demand_fauzer || '') : ''
        };
      }
      return commentsPayload;
    },

    async saveAlignment(silent = false) {
      this.saving = true;
      try {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
        const commentsPayload = this.preparePayload();

        const resp = await fetch('/api/relatorio/salvar-alinhamento', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
            cycle_id: this.cycleId,
            employee_key: this.employeeKey,
            director_comments: commentsPayload,
            agreements_jam_geysa: this.agreementsJamGeysa,
            agreements_fauzer: this.agreementsFauzer
          })
        });
        const res = await resp.json();
        if (res.success) {
          if (!silent) this.showToast('Rascunho de pareceres e demandas salvo com sucesso!', true);
          if (res.data) {
            this.employeeData = res.data;
          }
          return true;
        } else {
          this.showToast(res.error || 'Erro ao salvar pareceres.', false);
          return false;
        }
      } catch (e) {
        this.showToast('Falha na conexão ao salvar.', false);
        return false;
      } finally {
        this.saving = false;
      }
    },

    async finalizeAlignment() {
      const ok = await this.saveAlignment(true);
      if (!ok) return;

      // Se o feedback não estava liberado, libera automaticamente ao finalizar
      if (!this.employeeData.is_feedback_released) {
        await this.toggleFeedbackRelease(true);
      }
      this.showToast('✅ Aferição finalizada! Os 4 relatórios foram atualizados e estão prontos para envio.', true);
    },

    async suggestIdea(q) {
      if (!q) return;
      this.loadingSuggestion = q.id;
      const qId = String(q.id);
      try {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
        const resp = await fetch('/api/relatorio/sugerir-comentario', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
            question_label: q.label,
            provided_answer: q.provided_answer,
            role_title: this.employeeData.role_title,
            employee_name: this.employeeData.employee_name
          })
        });
        const res = await resp.json();
        if (res.success && res.suggestion) {
          if (!this.qActions[qId]) this.toggleAction(qId, 'acknowledged');
          this.qActions[qId].acknowledged = true;
          const cur = (this.qActions[qId].employee_feedback || '').trim();
          this.qActions[qId].employee_feedback = cur ? (cur + ' ' + res.suggestion) : res.suggestion;
          this.showToast('Sugestão aplicada no campo de feedback!', true);
        } else {
          this.showToast(res.error || 'Não foi possível gerar a sugestão.', false);
        }
      } catch (e) {
        this.showToast('Falha ao conectar ao serviço de sugestão.', false);
      } finally {
        this.loadingSuggestion = null;
      }
    },

    async toggleFeedbackRelease(forceVal = null) {
      const nextVal = forceVal !== null ? forceVal : !this.employeeData.is_feedback_released;
      this.loading = true;
      try {
        const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
        const resp = await fetch('/api/relatorio/toggle-liberacao', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
            cycle_id: this.cycleId,
            employee_key: this.employeeKey,
            is_released: nextVal
          })
        });
        const res = await resp.json();
        if (res.success) {
          this.employeeData.is_feedback_released = res.is_feedback_released;
          this.showToast(res.message, true);
        } else {
          this.showToast(res.error || 'Erro ao alterar liberação.', false);
        }
      } catch (e) {
        this.showToast('Falha ao alternar modo de liberação.', false);
      } finally {
        this.loading = false;
      }
    },

    buildWhatsAppText(type) {
      const empName = this.employeeData.employee_name || this.employeeKey.toUpperCase();
      const role = this.employeeData.role_title || 'Colaborador';
      const cycleTitle = this.employeeData.cycle_title || 'Alinhamento Semanal';
      const questions = this.employeeData.triad_questions || [];

      if (type === 'employee') {
        const firstName = empName.split(' ')[0] || 'Colaborador';
        let txt = `📋 *DEVOLUTIVA DE ALINHAMENTO SEMANAL — MAJ MOBILIDADE*\n`;
        txt += `👤 *Colaborador:* ${empName} (${role})\n`;
        txt += `📅 *Ciclo:* ${cycleTitle}\n\n`;
        txt += `Olá, *${firstName}*! A Diretoria analisou seu relatório semanal. Segue o parecer e orientações:\n\n`;

        questions.forEach((q, idx) => {
          const act = this.qActions[String(q.id)] || {};
          const ans = (q.provided_answer || '').trim();
          if (ans || act.employee_feedback || act.acknowledged) {
            txt += `*${idx + 1}. ${q.label}*\n`;
            if (ans) {
              const shortAns = ans.replace(/\n+/g, ' ').substring(0, 160);
              txt += `📥 *Seu relato:* _${shortAns}${ans.length > 160 ? '...' : ''}_\n`;
            }
            if (act.employee_feedback) {
              txt += `💬 *Parecer da Gerência:* ${act.employee_feedback}\n`;
            } else if (act.acknowledged) {
              txt += `✅ *Parecer da Gerência:* Registrado e acompanhado pela Diretoria.\n`;
            }
            txt += `\n`;
          }
        });

        if (this.agreementsJamGeysa || this.agreementsFauzer) {
          txt += `📌 *Combinados para a Próxima Semana:*\n`;
          if (this.agreementsJamGeysa) txt += `• ${this.agreementsJamGeysa.trim()}\n`;
          if (this.agreementsFauzer) txt += `• ${this.agreementsFauzer.trim()}\n`;
          txt += `\n`;
        }
        txt += `Contamos com seu empenho e foco em excelência! 🚀`;
        return txt.trim();
      }

      const leaderConfig = {
        jam: { name: 'Jam Penitenti', icon: '👔', field: 'demand_jam', check: 'has_jam', general: this.agreementsJamGeysa },
        geysa: { name: 'Geysa', icon: '💼', field: 'demand_geysa', check: 'has_geysa', general: this.agreementsJamGeysa },
        fauzer: { name: 'Fauzer', icon: '⚡', field: 'demand_fauzer', check: 'has_fauzer', general: this.agreementsFauzer }
      };

      const cfg = leaderConfig[type];
      if (!cfg) return '';

      let txt = `${cfg.icon} *PAUTA DE DEMANDAS — ${cfg.name.toUpperCase()}*\n`;
      txt += `👤 *Colaborador de Origem:* ${empName} (${role})\n`;
      txt += `📅 *Ciclo:* ${cycleTitle}\n\n`;
      txt += `Ações atribuídas na reunião de aferição sob sua responsabilidade:\n\n`;

      let count = 0;
      questions.forEach((q) => {
        const act = this.qActions[String(q.id)] || {};
        const demand = act[cfg.check] ? (act[cfg.field] || '').trim() : '';
        if (demand) {
          count++;
          txt += `*[${count}] ${q.label}*\n`;
          txt += `📝 *Ação ${cfg.name}:* ${demand}\n`;
          const ans = (q.provided_answer || '').trim();
          if (ans) {
            const shortAns = ans.replace(/\n+/g, ' ').substring(0, 130);
            txt += `📥 *Contexto Colaborador:* _${shortAns}${ans.length > 130 ? '...' : ''}_\n`;
          }
          txt += `\n`;
        }
      });

      if (count === 0) {
        txt += `• Nenhuma demanda específica atribuída para ${cfg.name} neste colaborador.\n\n`;
      }

      if (cfg.general && cfg.general.trim()) {
        txt += `📌 *Acordos Gerais de Alinhamento da Semana:*\n• ${cfg.general.trim()}\n`;
      }
      return txt.trim();
    },

    copyReport(tab) {
      const text = this.buildWhatsAppText(tab);
      if (!text) return;
      navigator.clipboard.writeText(text).then(() => {
        this.copiedTab = tab;
        this.showToast('📋 Texto copiado para a Área de Transferência!', true);
        setTimeout(() => { this.copiedTab = null; }, 2500);
      }).catch(() => {
        this.showToast('Não foi possível copiar automaticamente.', false);
      });
    },

    dispatchWhatsApp(tab) {
      const text = this.buildWhatsAppText(tab);
      if (!text) return;
      const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;
      window.open(url, '_blank');
    },

    getStatusLabel(status) {
      if (status === 'submitted_on_time') return '🟢 Entregue no Prazo';
      if (status === 'submitted_late') return '🟡 Entregue com Atraso';
      if (status === 'draft') return '⚪ Em Rascunho';
      return '🔴 Pendente de Envio';
    },

    getScoreBadgeStyle(badge) {
      if (badge === 'green') return 'background: rgba(0, 229, 153, 0.15); color: #00e599; border: 1px solid rgba(0, 229, 153, 0.4);';
      if (badge === 'yellow') return 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);';
      if (badge === 'red') return 'background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);';
      return 'background: rgba(255, 255, 255, 0.08); color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.15);';
    },

    getScoreBadgeIcon(badge) {
      if (badge === 'green') return '🟢';
      if (badge === 'yellow') return '🟡';
      if (badge === 'red') return '🔴';
      return '⚪';
    },

    formatAnswerHtml(text) {
      if (typeof window.formatReportAnswerHtml === 'function') {
        return window.formatReportAnswerHtml(text);
      }
      return text || '<span style="color: #94a3b8; font-style: italic;">Colaborador não preencheu este campo no fechamento semanal.</span>';
    }
  };
}
