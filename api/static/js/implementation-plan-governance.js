/**
 * static/js/implementation-plan-governance.js
 * Módulo de Governança e Controles de Gestão Interna (M-One)
 * - Liberação de deliberações da gerência (Jam, Geysa, Fauzer)
 * - Liberação/Bloqueio de edição de respostas de ciclos anteriores
 * - Aprovação/Recusa de solicitações de edição de colaboradores
 */

(function (window) {
  'use strict';

  function getCsrfToken() {
    return document.querySelector('input[name="csrf_token"]')?.value || '';
  }

  const ImplementationPlanGovernance = {
    async toggleCycleFeedback(cycleId, release) {
      const verb = release ? 'liberar' : 'ocultar';
      if (!confirm(`Deseja ${verb} a visualização das deliberações e feedbacks da diretoria para todos os colaboradores deste ciclo?`)) {
        return;
      }
      try {
        const res = await fetch('/api/gestao-interna/toggle-feedback-ciclo', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ cycle_id: cycleId, release: Boolean(release) })
        });
        const d = await res.json();
        if (d.success) {
          alert(`✅ Sucesso! Deliberações do Ciclo ${d.released ? 'liberadas para visualização dos colaboradores' : 'ocultadas dos colaboradores'}.`);
          window.location.reload();
        } else {
          alert('❌ Erro: ' + (d.message || 'Falha ao alterar liberação de deliberações.'));
        }
      } catch (err) {
        alert('Erro de conexão ao alterar deliberações: ' + (err.message || err));
      }
    },

    async toggleCycleEdit(cycleId, unlock) {
      const verb = unlock ? 'liberar' : 'bloquear';
      if (!confirm(`Deseja ${verb} a edição em lote de respostas para TODOS os colaboradores deste ciclo?`)) {
        return;
      }
      try {
        const res = await fetch('/api/gestao-interna/toggle-edicao-ciclo', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ cycle_id: cycleId, unlock: Boolean(unlock) })
        });
        const d = await res.json();
        if (d.success) {
          alert(`✅ Sucesso! Edição em lote ${d.unlocked ? 'liberada para todos os colaboradores' : 'bloqueada com sucesso'}.`);
          window.location.reload();
        } else {
          alert('❌ Erro: ' + (d.message || 'Falha ao alterar status de edição do ciclo.'));
        }
      } catch (err) {
        alert('Erro de conexão ao alterar liberação de edição: ' + (err.message || err));
      }
    },

    async toggleEmployeeEdit(cycleId, employeeKey, unlock) {
      const verb = unlock ? 'liberar' : 'bloquear';
      if (!confirm(`Deseja ${verb} a edição do relatório para o colaborador @${employeeKey}?`)) {
        return;
      }
      try {
        const res = await fetch('/api/gestao-interna/toggle-edicao-colaborador', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ cycle_id: cycleId, employee_key: employeeKey, unlock: Boolean(unlock) })
        });
        const d = await res.json();
        if (d.success) {
          alert(`✅ Edição de @${employeeKey} ${d.is_edit_unlocked ? 'liberada com sucesso' : 'bloqueada com sucesso'}!`);
          window.location.reload();
        } else {
          alert('❌ Erro: ' + (d.message || 'Falha ao atualizar liberação do colaborador.'));
        }
      } catch (err) {
        alert('Erro de conexão ao alterar edição do colaborador: ' + (err.message || err));
      }
    },

    async decideEditRequest(cycleId, employeeKey, decision) {
      const actionName = decision === 'approved' ? 'Aprovar e Liberar Edição' : 'Recusar Pedido de Edição';
      if (!confirm(`Deseja confirmar a ação: "${actionName}" para @${employeeKey}?`)) {
        return;
      }
      try {
        const res = await fetch('/api/gestao-interna/decidir-solicitacao-edicao', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          },
          body: JSON.stringify({ cycle_id: cycleId, employee_key: employeeKey, decision: decision })
        });
        const d = await res.json();
        if (d.success) {
          alert(`✅ Solicitação de @${employeeKey}: ${decision === 'approved' ? 'Aprovada e Edição Liberada' : 'Recusada'}!`);
          window.location.reload();
        } else {
          alert('❌ Erro: ' + (d.message || 'Falha ao processar solicitação de edição.'));
        }
      } catch (err) {
        alert('Erro de conexão ao processar solicitação: ' + (err.message || err));
      }
    }
  };

  window.ImplementationPlanGovernance = ImplementationPlanGovernance;
})(window);

