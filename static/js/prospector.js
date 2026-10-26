/* M-One Prospector Frontend Logic (static/js/prospector.js & api/static/js/prospector.js) */
function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

function prospectorApp(initialTab, initialNicho, sheetsUrl, vendedorId, vendedorNome, vendedorPhone, isSeller) {
  return {
    tab: initialTab || 'capturados',
    isSeller: !!isSeller,
    vendedorId: vendedorId || 0,
    vendedorNome: vendedorNome || 'Vendedor',
    vendedorPhone: vendedorPhone || '',
    vendedorPhoneTemp: vendedorPhone || '',
    radarLoading: false,
    syncLoading: false,
    prospectandoLoading: false,
    modalAberto: false,
    modalSheetsAberto: false,
    scriptCopiado: false,
    salvandoWebhookModal: false,
    webhookModalInput: sheetsUrl || '',
    leadSelecionado: null,
    mensagemEditavel: '',
    alertaMsg: '',
    alertaTipo: '',
    radarForm: {
      nicho: initialNicho || 'revenda-motos',
      praca: 'Vitória ES',
      limite: 10
    },
    configForm: {
      sheets_url: sheetsUrl || '',
      apify_token: ''
    },
    automacao: {
      ativo: false,
      modo: 'turnos',
      limite: 25,
      intervalo_min: 120,
      pracas: ['Vitória ES', 'Vila Velha ES', 'Serra ES', 'Cariacica ES', 'Belo Horizonte MG', 'Campinas SP'],
      pracas_str: 'Vitória ES, Vila Velha ES, Serra ES, Cariacica ES, Belo Horizonte MG, Campinas SP',
      nicho_slug: 'revenda-motos',
      ultimo_ciclo: '',
      ultima_praca: '',
      ultimo_resultado: '',
      total_auto: 0,
      indice_rotacao: 0,
      proxima_praca: 'Vitória ES'
    },
    automacaoSalvando: false,
    automacaoExecutando: false,
    jobStatus: {
      running: false,
      completed: false,
      processed: 0,
      total: 0,
      current_lead: '',
      nicho: '',
      praca: '',
      error: null
    },

    init() {
      const urlParams = new URLSearchParams(window.location.search);
      const tabParam = urlParams.get('tab');
      if (tabParam && ['capturados', 'radar', 'integracoes'].includes(tabParam) && !this.isSeller) {
        this.tab = tabParam;
      }

      if (!this.isSeller) {
        this.checarStatusJob();
        this.carregarConfigAutomacao();
        setInterval(() => {
          if (this.jobStatus.running) {
            this.checarStatusJob();
          }
        }, 2000);
      }
    },

    setTab(t) {
      if (this.isSeller && t !== 'capturados') return;
      this.tab = t;
      const url = new URL(window.location.href);
      url.searchParams.set('tab', t);
      window.history.replaceState({}, '', url.toString());
    },

    async iniciarBusca() {
      if (!this.radarForm.praca || !this.radarForm.praca.trim()) {
        alert('Por favor, informe a cidade/praça desejada.');
        return;
      }
      this.radarLoading = true;
      this.alertaMsg = '';
      try {
        const csrf = getCsrfToken();
        const resp = await fetch('/admin/prospeccao/api/buscar', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf
          },
          body: JSON.stringify({
            ...this.radarForm,
            csrf_token: csrf
          })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          this.jobStatus.running = true;
          this.jobStatus.error = null;
          this.jobStatus.current_lead = 'Iniciando varredura...';
          this.alertaMsg = '⚡ Varredura iniciada! Acompanhe o progresso no monitor abaixo.';
          this.alertaTipo = 'success';
          this.checarStatusJob();
        } else {
          alert('Erro ao iniciar busca: ' + (data.message || data.error));
        }
      } catch (err) {
        alert('Falha na requisição: ' + err);
      } finally {
        this.radarLoading = false;
      }
    },

    async checarStatusJob() {
      try {
        const resp = await fetch('/admin/prospeccao/api/status');
        const data = await resp.json();
        if (data.status === 'success' && data.job) {
          const wasRunning = this.jobStatus.running;
          this.jobStatus = data.job;
          if (wasRunning && !data.job.running && data.job.completed) {
            this.alertaMsg = '✅ Varredura concluída com sucesso! Atualizando lista...';
            setTimeout(() => {
              window.location.href = '/admin/prospeccao?tab=capturados';
            }, 1000);
          }
        }
      } catch (e) {}
    },

    async sincronizarSheets() {
      // Se não houver webhook configurado, abre diretamente o assistente guiado
      if (!this.configForm.sheets_url && !this.webhookModalInput) {
        this.modalSheetsAberto = true;
        return;
      }
      this.syncLoading = true;
      try {
        const csrf = getCsrfToken();
        const resp = await fetch('/admin/prospeccao/api/sync-sheets', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf
          },
          body: JSON.stringify({ apenas_pendentes: false, csrf_token: csrf })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          alert('✅ ' + data.message);
          window.location.reload();
        } else {
          // Se for pendência de configuração do webhook, abre o assistente amigável
          if ((data.message || '').toLowerCase().includes('webhook')) {
            this.modalSheetsAberto = true;
          } else {
            alert('Erro na sincronização: ' + (data.message || data.error));
          }
        }
      } catch (err) {
        alert('Falha na conexão: ' + err);
      } finally {
        this.syncLoading = false;
      }
    },

    copiarScriptAppsScript() {
      const code = `function doPost(e) {\\n  try {\\n    const rawData = e.postData.contents;\\n    const payload = JSON.parse(rawData);\\n    const leads = payload.leads || [];\\n    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();\\n    if (sheet.getLastRow() === 0) {\\n      sheet.appendRow([\\n        "ID M-One", "Data Captura", "Classe", "Score", "Empresa", "Decisor / Sócio",\\n        "Cargo Decisor", "Outros Sócios", "WhatsApp", "E-mail", "Nicho", "Cidade",\\n        "UF", "Endereço", "Site", "Instagram", "CNPJ", "Porte", "Raio-X (Resumo IA)",\\n        "Gancho Comercial", "Status do Contato", "Notas do Vendedor"\\n      ]);\\n      sheet.getRange(1, 1, 1, 22).setFontWeight("bold").setBackground("#0f172a").setFontColor("#38bdf8");\\n    }\\n    const lastRow = sheet.getLastRow();\\n    const existingIds = lastRow > 1 ? sheet.getRange(2, 1, lastRow - 1, 1).getValues().flat().map(String) : [];\\n    leads.forEach(lead => {\\n      const idStr = String(lead.id);\\n      const rowIdx = existingIds.indexOf(idStr);\\n      const rowData = [\\n        idStr, lead.data_captura || "", lead.classe || "D", lead.score || 0,\\n        lead.empresa || "", lead.decisor || "", lead.decisor_cargo || "",\\n        lead.outros_socios || "", lead.whatsapp || "", lead.email || "",\\n        lead.nicho || "", lead.cidade || "", lead.uf || "", lead.endereco || "",\\n        lead.site || "", lead.instagram || "", lead.cnpj || "", lead.porte || "",\\n        lead.resumo_ia || "", lead.gancho_comercial || "", lead.status_contato || "Novo", ""\\n      ];\\n      if (rowIdx !== -1) {\\n        sheet.getRange(rowIdx + 2, 1, 1, rowData.length).setValues([rowData]);\\n      } else {\\n        sheet.appendRow(rowData);\\n      }\\n    });\\n    return ContentService.createTextOutput(JSON.stringify({ status: "success", count: leads.length })).setMimeType(ContentService.MimeType.JSON);\\n  } catch (err) {\\n    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() })).setMimeType(ContentService.MimeType.JSON);\\n  }\\n}`;
      navigator.clipboard.writeText(code);
      this.scriptCopiado = true;
      setTimeout(() => { this.scriptCopiado = false; }, 3000);
    },

    async salvarWebhookEExecutar() {
      if (!this.webhookModalInput || !this.webhookModalInput.trim()) {
        alert('Por favor, cole a URL do Webhook do Google Apps Script.');
        return;
      }
      this.salvandoWebhookModal = true;
      try {
        const csrf = getCsrfToken();
        const resp = await fetch('/admin/prospeccao/api/google-sheets', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ sheets_webhook_url: this.webhookModalInput, csrf_token: csrf })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          this.configForm.sheets_url = this.webhookModalInput;
          this.modalSheetsAberto = false;
          // Dispara a sincronização imediatamente com a nova URL
          await this.sincronizarSheets();
        } else {
          alert('Erro ao salvar: ' + data.message);
        }
      } catch (e) {
        alert('Erro: ' + e);
      } finally {
        this.salvandoWebhookModal = false;
      }
    },

    async salvarConfiguracoes() {
      try {
        const csrf = getCsrfToken();
        const resp = await fetch('/admin/prospeccao/api/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf
          },
          body: JSON.stringify({
            sheets_webhook_url: this.configForm.sheets_url,
            apify_token: this.configForm.apify_token,
            csrf_token: csrf
          })
        });
        const data = await resp.json();
        alert(data.message || 'Configurações gravadas com sucesso!');
        window.location.reload();
      } catch (err) {
        alert('Erro ao gravar: ' + err);
      }
    },

    async abrirProspectar(leadId) {
      try {
        const resp = await fetch(`/admin/prospeccao/api/lead/${leadId}`);
        const data = await resp.json();
        if (data.status === 'success' && data.lead) {
          this.leadSelecionado = data.lead;
          this.montarMensagemInicial(data.lead);
          this.modalAberto = true;
        } else {
          alert('Erro ao carregar dados do lead.');
        }
      } catch (e) {
        alert('Falha na conexão com o servidor.');
      }
    },

    montarMensagemInicial(lead) {
      // Identifica o primeiro nome do vendedor atual
      const nomeCompleto = (this.vendedorNome || '').trim();
      const primeiroNome = nomeCompleto && nomeCompleto.toLowerCase() !== 'vendedor'
        ? nomeCompleto.split(' ')[0]
        : '';

      const artigo = ['geysa', 'luiza', 'marisa'].includes(primeiroNome.toLowerCase()) ? 'a ' : 'o ';
      const introVendedor = primeiroNome
        ? `Aqui é ${artigo}${primeiroNome} da MAJ Mobilidade`
        : `Aqui é da MAJ Mobilidade`;

      let base = lead.mensagem_enviada ? lead.mensagem_enviada : (lead.gancho_comercial || '');

      if (!base) {
        const nomeLoja = (lead.nome_fantasia || lead.nome || 'Loja').trim();
        base = `Olá, equipe da ${nomeLoja}! Tudo bem? 😊\n\n${introVendedor}.\n\nVimos que vocês são referência no segmento de duas rodas na região e estamos ampliando nossos parceiros lojistas com condições exclusivas de atacado direto de fábrica para revenda de scooters e motos elétricas MAJ.\n\nCom quem da equipe comercial ou de compras poderíamos conversar por aqui? 🚀`;
      } else {
        // Regex abrangente que captura qualquer apresentação prévia de consultor (genérica ou com outro vendedor)
        const regexIntroExistente = /Aqui é (?:da|do|represento a|(?:[oa]\s+[A-Za-zÀ-Úà-ú]+))\s+da\s+MAJ\s+Mobilidade(?:\s+Elétrica)?\.?\s*/gi;
        const matches = [...base.matchAll(regexIntroExistente)];

        if (matches.length > 0) {
          // Substitui o primeiro match pela assinatura do consultor atual e remove ocorrências duplicadas subsequentes
          let result = '';
          let lastIndex = 0;
          matches.forEach((m, idx) => {
            result += base.slice(lastIndex, m.index);
            if (idx === 0) {
              result += `${introVendedor}. `;
            }
            lastIndex = m.index + m[0].length;
          });
          result += base.slice(lastIndex);
          base = result.replace(/[ ]{2,}/g, ' ').trim();
        } else if (primeiroNome && !base.toLowerCase().includes(primeiroNome.toLowerCase())) {
          // Se não possui apresentação de vendedor, adiciona logo após a saudação inicial
          const matchSaudacao = base.match(/^(Olá[,!]?( equipe da [^!]+!)?|Bom dia[,!]?|Boa tarde[,!]?)/i);
          if (matchSaudacao) {
            const saudacao = matchSaudacao[0].replace(/[!, ]+$/, '');
            const resto = base.slice(matchSaudacao[0].length).trim();
            const restoCap = resto ? (resto.charAt(0).toUpperCase() + resto.slice(1)) : '';
            base = `${saudacao}! ${introVendedor}. ${restoCap}`;
          } else {
            base = `Olá! ${introVendedor}. ${base}`;
          }
        }
      }

      // Remove estritamente assinaturas formais inadequadas para WhatsApp (Att, Atenciosamente, etc)
      base = base.replace(/\n*Att,[\s\S]*$/i, '').trim();
      base = base.replace(/\n*Atenciosamente,[\s\S]*$/i, '').trim();

      // Sanitização anti-duplicação: assegura que não há dois "Aqui é" no texto
      const regexSanity = /Aqui é (?:da|do|represento a|(?:[oa]\s+[A-Za-zÀ-Úà-ú]+))\s+da\s+MAJ\s+Mobilidade(?:\s+Elétrica)?\.?\s*/gi;
      const sanityMatches = [...base.matchAll(regexSanity)];
      if (sanityMatches.length > 1) {
        let clean = '';
        let lastEnd = 0;
        sanityMatches.forEach((m, i) => {
          clean += base.slice(lastEnd, m.index);
          if (i === 0) {
            clean += `${introVendedor}. `;
          }
          lastEnd = m.index + m[0].length;
        });
        clean += base.slice(lastEnd);
        base = clean.replace(/[ ]{2,}/g, ' ').trim();
      }

      this.mensagemEditavel = base.trim();
    },

    restaurarGanchoPadrao() {
      if (!this.leadSelecionado) return;
      this.montarMensagemInicial({ ...this.leadSelecionado, mensagem_enviada: null });
    },

    copiarTextoMensagem() {
      if (this.mensagemEditavel) {
        navigator.clipboard.writeText(this.mensagemEditavel);
        alert('Texto da mensagem copiado com sucesso!');
      }
    },

    async salvarMeuTelefone() {
      if (!this.vendedorPhoneTemp || !this.vendedorPhoneTemp.trim()) {
        alert('Por favor, informe seu número de WhatsApp com DDD.');
        return;
      }
      try {
        const csrf = getCsrfToken();
        const resp = await fetch('/profile/phone', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ phone: this.vendedorPhoneTemp.trim(), csrf_token: csrf })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          this.vendedorPhone = data.phone || this.vendedorPhoneTemp.trim();
          alert('✅ ' + data.message);
          if (this.leadSelecionado) {
            this.montarMensagemInicial(this.leadSelecionado);
          }
        } else {
          alert('Erro ao salvar: ' + (data.message || data.error));
        }
      } catch (e) {
        alert('Falha ao comunicar com o servidor.');
      }
    },

    async enviarWhatsAppEProspectar() {
      if (!this.leadSelecionado) return;

      if (!this.vendedorPhone) {
        alert('⚠️ Você ainda não cadastrou seu WhatsApp Comercial no seu perfil. Por favor, cadastre seu número para iniciar abordagens.');
        if (typeof openProfileModal === 'function') openProfileModal();
        return;
      }

      // Validação estrita de número celular apto para WhatsApp
      if (!this.leadSelecionado.whatsapp) {
        if (this.leadSelecionado.telefone_google) {
          alert(`⚠️ Atenção: O lead '${this.leadSelecionado.nome}' possui apenas Telefone Fixo Comercial (${this.leadSelecionado.telefone_google}).\n\nTelefones fixos convencionais normalmente não possuem WhatsApp ativo. Recomendamos ligar para a loja e solicitar o WhatsApp do responsável de compras/comercial.`);
        } else {
          alert('Este lead não possui número de WhatsApp ou telefone registrado.');
        }
        return;
      }

      const rawPhone = this.leadSelecionado.whatsapp;
      const cleanPhone = String(rawPhone).replace(/\D/g, '');
      if (cleanPhone.length < 10) {
        alert('Número de celular inválido para WhatsApp: ' + rawPhone);
        return;
      }

      // Trava de confirmação contra conflito e ruído de equipe
      if (!this.mesmoVendedor()) {
        const respNome = this.leadSelecionado.prospectado_por_nome || 'outro consultor';
        const prosseguir = confirm(`⚠️ ALERTA DE CONFLITO COMERCIAL:\n\nEste lead já foi abordado por ${respNome}.\n\nPara evitar ruídos com o cliente ou sobreposição com seu colega, confirme se você alinhou esta reatribuição.\n\nDeseja realmente assumir e disparar pelo seu WhatsApp?`);
        if (!prosseguir) return;
      }

      this.prospectandoLoading = true;
      try {
        const csrf = getCsrfToken();
        const resp = await fetch(`/admin/prospeccao/api/lead/${this.leadSelecionado.id}/prospectar`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({
            mensagem: this.mensagemEditavel,
            vendedor_phone: this.vendedorPhone || this.vendedorPhoneTemp,
            csrf_token: csrf
          })
        });
        const data = await resp.json();

        // Atualiza estado reativo local
        this.leadSelecionado.status_contato = 'prospectado';
        this.leadSelecionado.prospectado_por_nome = this.vendedorNome;

        // Atualiza a linha da tabela se estiver visível no DOM
        const row = document.getElementById(`lead-row-${this.leadSelecionado.id}`);
        if (row) {
          const statusCell = row.children[5];
          if (statusCell) {
            statusCell.innerHTML = `
              <div class="prospectado-cell">
                <span class="status-badge status-prospectado">💬 Prospectado</span>
                <small class="vendedor-nome-sub">👤 ${this.vendedorNome}</small>
              </div>
            `;
          }
        }

        // Abre WhatsApp em nova aba com o texto codificado
        const waUrl = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(this.mensagemEditavel)}`;
        window.open(waUrl, '_blank');

        this.modalAberto = false;
        this.alertaMsg = `🚀 Lead '${this.leadSelecionado.nome}' marcado como Prospectado por você e WhatsApp iniciado!`;
      } catch (err) {
        alert('Erro ao registrar prospecção: ' + err);
      } finally {
        this.prospectandoLoading = false;
      }
    },

    fecharModal() {
      this.modalAberto = false;
      this.leadSelecionado = null;
      this.mensagemEditavel = '';
    },

    async salvarStatus(novoStatus) {
      if (!this.leadSelecionado) return;
      try {
        const csrf = getCsrfToken();
        const resp = await fetch(`/admin/prospeccao/api/lead/${this.leadSelecionado.id}/status`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrf
          },
          body: JSON.stringify({ status_contato: novoStatus, csrf_token: csrf })
        });
        const data = await resp.json();
        if (data.status === 'success') {
          this.leadSelecionado.status_contato = novoStatus;
        }
      } catch (e) {
        alert('Erro ao atualizar status.');
      }
    },

    mesmoVendedor() {
      if (!this.leadSelecionado?.prospectado_por_nome || !this.vendedorNome) return true;
      const p1 = this.leadSelecionado.prospectado_por_nome.toLowerCase().trim();
      const p2 = this.vendedorNome.toLowerCase().trim();
      return p1.includes(p2) || p2.includes(p1);
    },

    formatarDataLead(dtStr) {
      if (!dtStr) return '';
      try {
        const d = new Date(dtStr);
        return d.toLocaleDateString('pt-BR') + ' às ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        return dtStr;
      }
    },

    ...(typeof getProspectorAutomacaoMethods === 'function' ? getProspectorAutomacaoMethods() : {})
  };
}
