/**
 * M-One Fiscal Pricing - Cost Entry & Apportionment Controller
 */
(function () {
  'use strict';

  let currentItems = [];
  let selectedExcelFile = null;

  window.switchSourceTab = function (tabName) {
    const btnExcel = document.getElementById('btnTabExcel');
    const btnXml = document.getElementById('btnTabXml');
    const btnMone = document.getElementById('btnTabMone');
    const btnManual = document.getElementById('btnTabManual');

    const paneExcel = document.getElementById('paneExcel');
    const paneXml = document.getElementById('paneXml');
    const paneMone = document.getElementById('paneMone');
    const paneManual = document.getElementById('paneManual');

    [btnExcel, btnXml, btnMone, btnManual].forEach(b => {
      if (b) {
        b.classList.remove('active');
        b.style.background = 'transparent';
        b.style.color = 'var(--text-muted, #94a3b8)';
        b.style.borderColor = 'var(--border-subtle, rgba(255,255,255,0.1))';
      }
    });

    [paneExcel, paneXml, paneMone, paneManual].forEach(p => {
      if (p) p.style.display = 'none';
    });

    if (tabName === 'xml') {
      if (btnXml) {
        btnXml.style.background = 'rgba(56, 189, 248, 0.15)';
        btnXml.style.color = '#38bdf8';
        btnXml.style.borderColor = 'rgba(56, 189, 248, 0.3)';
      }
      if (paneXml) paneXml.style.display = 'block';
    } else if (tabName === 'mone') {
      if (btnMone) {
        btnMone.style.background = 'rgba(192, 132, 252, 0.15)';
        btnMone.style.color = '#c084fc';
        btnMone.style.borderColor = 'rgba(192, 132, 252, 0.3)';
      }
      if (paneMone) paneMone.style.display = 'block';
    } else if (tabName === 'manual') {
      if (btnManual) {
        btnManual.style.background = 'rgba(245, 158, 11, 0.15)';
        btnManual.style.color = '#f59e0b';
        btnManual.style.borderColor = 'rgba(245, 158, 11, 0.3)';
      }
      if (paneManual) paneManual.style.display = 'block';
      if (currentItems.length === 0) addManualRow();
    } else {
      if (btnExcel) {
        btnExcel.style.background = 'rgba(0, 229, 153, 0.15)';
        btnExcel.style.color = '#00E599';
        btnExcel.style.borderColor = 'rgba(0, 229, 153, 0.4)';
      }
      if (paneExcel) paneExcel.style.display = 'block';
    }
  };

  window.onExcelFileSelected = function (input) {
    if (!input.files || !input.files[0]) return;
    selectedExcelFile = input.files[0];

    const heroStatus = document.getElementById('heroExcelStatus');
    const tabStatus = document.getElementById('excelStatus');

    const msg = `📄 Planilha Selecionada: ${selectedExcelFile.name}. Clique em "Processar & Analisar".`;
    if (heroStatus) heroStatus.innerText = msg;
    if (tabStatus) tabStatus.innerText = msg;
  };

  window.processSelectedExcel = function () {
    const heroInput = document.getElementById('heroExcelInput');
    const tabInput = document.getElementById('excelFileInput');

    let file = selectedExcelFile;
    if (!file && heroInput && heroInput.files && heroInput.files[0]) {
      file = heroInput.files[0];
    }
    if (!file && tabInput && tabInput.files && tabInput.files[0]) {
      file = tabInput.files[0];
    }

    if (!file) {
      alert('Por favor, selecione primeiro um arquivo de planilha (.xlsx ou .csv).');
      if (heroInput) heroInput.click();
      return;
    }

    const heroStatus = document.getElementById('heroExcelStatus');
    const tabStatus = document.getElementById('excelStatus');
    const btnProcess = document.getElementById('btnProcessExcel');

    if (btnProcess) {
      btnProcess.disabled = true;
      btnProcess.innerHTML = '<span>⏳</span> Processando Planilha...';
    }

    const procMsg = `⏳ Analisando e processando: ${file.name}...`;
    if (heroStatus) heroStatus.innerText = procMsg;
    if (tabStatus) tabStatus.innerText = procMsg;

    const formData = new FormData();
    formData.append('file', file);

    fetch('/fiscal-pricing/api/parse-excel', {
      method: 'POST',
      body: formData,
    })
      .then(res => res.json())
      .then(res => {
        if (btnProcess) {
          btnProcess.disabled = false;
          btnProcess.innerHTML = '<span>⚡</span> 2. PROCESSAR & ANALISAR PLANILHA';
        }

        if (!res.success) {
          alert('Erro no processamento da planilha Excel: ' + (res.message || 'Desconhecido'));
          if (heroStatus) heroStatus.innerText = '❌ Falha no processamento.';
          if (tabStatus) tabStatus.innerText = '❌ Falha no processamento.';
          return;
        }

        const count = res.data.items?.length || 0;
        const okMsg = `✓ Planilha "${file.name}" processada com ${count} itens!`;
        if (heroStatus) heroStatus.innerText = okMsg;
        if (tabStatus) tabStatus.innerText = okMsg;

        populateApportionmentData(res.data);

        // Exibir Banner de Sucesso
        const banner = document.getElementById('processingSuccessBanner');
        const bTitle = document.getElementById('bannerTitle');
        const bSub = document.getElementById('bannerSubtitle');
        if (banner) {
          if (bTitle) bTitle.innerText = `✅ Planilha "${file.name}" Processada e Analisada!`;
          if (bSub) bSub.innerText = `${count} produtos carregados com rateio e Custo Unitário COLVIX apurado.`;
          banner.style.display = 'flex';
        }

        // Auto-scroll suave para a tabela
        window.scrollToTable();
      })
      .catch(err => {
        console.error(err);
        if (btnProcess) {
          btnProcess.disabled = false;
          btnProcess.innerHTML = '<span>⚡</span> 2. PROCESSAR & ANALISAR PLANILHA';
        }
        alert('Erro de conexão ao carregar planilha.');
        if (heroStatus) heroStatus.innerText = '';
        if (tabStatus) tabStatus.innerText = '';
      });
  };

  window.scrollToTable = function () {
    const sec = document.getElementById('sectionItemsTable');
    if (sec) {
      sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  window.handleXmlUpload = function (input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    const status = document.getElementById('xmlStatus');
    if (status) status.innerText = `Lendo arquivo: ${file.name}...`;

    const formData = new FormData();
    formData.append('file', file);

    fetch('/fiscal-pricing/api/parse-xml', {
      method: 'POST',
      body: formData,
    })
      .then(res => res.json())
      .then(res => {
        if (!res.success) {
          alert('Erro no parsing do XML: ' + (res.message || 'Desconhecido'));
          if (status) status.innerText = 'Falha no processamento.';
          return;
        }
        if (status) status.innerText = `✓ XML ${res.data.invoice_number || ''} carregado com sucesso!`;
        populateApportionmentData(res.data);
        window.scrollToTable();
      })
      .catch(err => {
        console.error(err);
        alert('Erro de rede ao ler XML.');
        if (status) status.innerText = '';
      });
  };

  window.loadMoneImport = function () {
    const sel = document.getElementById('moneImportSelect');
    if (!sel || !sel.value) {
      alert('Selecione um lote de importação.');
      return;
    }
    const importId = sel.value;
    fetch(`/fiscal-pricing/api/import-detail/${importId}`)
      .then(res => res.json())
      .then(res => {
        if (!res.success) {
          alert('Erro ao buscar lote: ' + res.message);
          return;
        }
        populateApportionmentData(res.data);
        window.scrollToTable();
      })
      .catch(err => {
        console.error(err);
        alert('Erro ao conectar com a API.');
      });
  };

  function populateApportionmentData(data) {
    if (data.invoice_number) document.getElementById('hdrInvoiceNumber').value = data.invoice_number;
    if (data.source_ref) document.getElementById('hdrBatchCode').value = `LOTE-${data.source_ref}`;
    if (data.totals) {
      document.getElementById('hdrIiTotal').value = data.totals.total_ii_val || 0;
      document.getElementById('hdrPisTotal').value = data.totals.total_pis_val || 0;
      document.getElementById('hdrCofinsTotal').value = data.totals.total_cofins_val || 0;
      document.getElementById('hdrExpensesTotal').value = data.totals.total_other_expenses_val || 0;
    }

    currentItems = data.items || [];
    renderTable();
    updateSummaryCards(data.totals || {});
  }

  window.addManualRow = function () {
    currentItems.push({
      item_code: `ITEM-${currentItems.length + 1}`,
      description: 'Novo Veículo / Peça',
      ncm: '87116000',
      quantity: 1,
      unit_product_val: 5000.0,
      total_product_val: 5000.0,
      participacao_pct: 0,
      ii_rateado: 0,
      pis_rateado: 0,
      cofins_rateado: 0,
      other_expenses_rateadas: 0,
      ipi_item: 0,
      icms_item: 0,
      total_cost_item: 5000.0,
      unit_cost_colvix: 5000.0,
    });
    recalculateApportionment();
  };

  window.removeRow = function (idx) {
    currentItems.splice(idx, 1);
    recalculateApportionment();
  };

  window.recalculateApportionment = function () {
    const totalIi = parseFloat(document.getElementById('hdrIiTotal').value || 0);
    const totalPis = parseFloat(document.getElementById('hdrPisTotal').value || 0);
    const totalCofins = parseFloat(document.getElementById('hdrCofinsTotal').value || 0);
    const totalExp = parseFloat(document.getElementById('hdrExpensesTotal').value || 0);

    const tbody = document.getElementById('itemsTableBody');
    if (tbody) {
      const rows = tbody.querySelectorAll('tr');
      rows.forEach((tr, i) => {
        if (currentItems[i]) {
          const qty = parseFloat(tr.querySelector('.inp-qty')?.value || 1);
          const unitVal = parseFloat(tr.querySelector('.inp-unit')?.value || 0);
          currentItems[i].quantity = qty;
          currentItems[i].unit_product_val = unitVal;
          currentItems[i].total_product_val = qty * unitVal;
          currentItems[i].item_code = tr.querySelector('.inp-code')?.value || currentItems[i].item_code;
          currentItems[i].description = tr.querySelector('.inp-desc')?.value || currentItems[i].description;
          currentItems[i].ncm = tr.querySelector('.inp-ncm')?.value || currentItems[i].ncm;
        }
      });
    }

    fetch('/fiscal-pricing/api/calculate-apportionment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items_raw: currentItems,
        total_ii_val: totalIi,
        total_pis_val: totalPis,
        total_cofins_val: totalCofins,
        general_expenses_header: totalExp,
      }),
    })
      .then(res => res.json())
      .then(res => {
        if (res.success && res.data) {
          currentItems = res.data.items || [];
          renderTable();
          updateSummaryCards(res.data.totals || {});
        }
      });
  };

  function renderTable() {
    const tbody = document.getElementById('itemsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (currentItems.length === 0) {
      tbody.innerHTML = '<tr><td colspan="13" style="text-align:center; padding:20px; color:#94a3b8;">Nenhum item no lote. Clique em "Adicionar Linha Manual" ou suba uma planilha.</td></tr>';
      return;
    }

    currentItems.forEach((it, idx) => {
      const tr = document.createElement('tr');
      tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
      tr.style.color = '#f8fafc';

      tr.innerHTML = `
        <td style="padding:8px;"><input type="text" class="inp-code form-input" value="${it.item_code}" style="width:70px; padding:4px; border-radius:4px; background:rgba(0,0,0,0.3); color:#fff; border:1px solid rgba(255,255,255,0.1);"></td>
        <td style="padding:8px;"><input type="text" class="inp-desc form-input" value="${it.description}" style="width:180px; padding:4px; border-radius:4px; background:rgba(0,0,0,0.3); color:#fff; border:1px solid rgba(255,255,255,0.1);"></td>
        <td style="padding:8px;"><input type="text" class="inp-ncm form-input" value="${it.ncm}" style="width:80px; padding:4px; border-radius:4px; background:rgba(0,0,0,0.3); color:#fff; border:1px solid rgba(255,255,255,0.1);"></td>
        <td style="padding:8px;"><input type="number" class="inp-qty form-input" value="${it.quantity}" onchange="recalculateApportionment()" style="width:50px; padding:4px; border-radius:4px; background:rgba(0,0,0,0.3); color:#fff; border:1px solid rgba(255,255,255,0.1);"></td>
        <td style="padding:8px;"><input type="number" step="0.01" class="inp-unit form-input" value="${it.unit_product_val}" onchange="recalculateApportionment()" style="width:90px; padding:4px; border-radius:4px; background:rgba(0,0,0,0.3); color:#fff; border:1px solid rgba(255,255,255,0.1);"></td>
        <td style="padding:8px; font-weight:600;">R$ ${(it.total_product_val || 0).toFixed(2)}</td>
        <td style="padding:8px; color:#38bdf8;">${(it.participacao_pct || 0).toFixed(2)}%</td>
        <td style="padding:8px;">R$ ${(it.ii_rateado || 0).toFixed(2)}</td>
        <td style="padding:8px;">R$ ${(it.pis_rateado || 0).toFixed(2)}</td>
        <td style="padding:8px;">R$ ${(it.cofins_rateado || 0).toFixed(2)}</td>
        <td style="padding:8px;">R$ ${(it.other_expenses_rateadas || 0).toFixed(2)}</td>
        <td style="padding:8px; font-weight:800; color:#00E599;">R$ ${(it.unit_cost_colvix || 0).toFixed(2)}</td>
        <td style="padding:8px; text-align:center;">
          <button type="button" onclick="removeRow(${idx})" style="background:rgba(239,68,68,0.2); border:1px solid rgba(239,68,68,0.4); color:#ef4444; border-radius:4px; padding:2px 8px; cursor:pointer;">✕</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function updateSummaryCards(totals) {
    const sumTotalCost = document.getElementById('sumTotalCostColvix');
    const sumPis = document.getElementById('sumPisCredit');
    const sumCofins = document.getElementById('sumCofinsCredit');

    if (sumTotalCost) sumTotalCost.innerText = `R$ ${(totals.total_cost_colvix || 0).toFixed(2)}`;
    if (sumPis) sumPis.innerText = `R$ ${(totals.pis_credit_initial || 0).toFixed(2)}`;
    if (sumCofins) sumCofins.innerText = `R$ ${(totals.cofins_credit_initial || 0).toFixed(2)}`;
  }

  window.saveBatch = function (status) {
    if (currentItems.length === 0) {
      alert('Adicione pelo menos um item ao lote fiscal.');
      return;
    }
    const batchCode = document.getElementById('hdrBatchCode').value || 'LOTE-AUT';
    const invNo = document.getElementById('hdrInvoiceNumber').value || '';
    const totalIi = parseFloat(document.getElementById('hdrIiTotal').value || 0);
    const totalPis = parseFloat(document.getElementById('hdrPisTotal').value || 0);
    const totalCofins = parseFloat(document.getElementById('hdrCofinsTotal').value || 0);
    const totalExp = parseFloat(document.getElementById('hdrExpensesTotal').value || 0);

    let totProd = 0;
    let totCostColvix = 0;
    currentItems.forEach(it => {
      totProd += it.total_product_val || 0;
      totCostColvix += it.total_cost_item || 0;
    });

    const payload = {
      batch_code: batchCode,
      invoice_number: invNo,
      source_type: 'excel',
      supplier_name: 'COLVIX (Planilha)',
      status: status,
      totals: {
        total_products_val: totProd,
        total_ii_val: totalIi,
        total_pis_val: totalPis,
        total_cofins_val: totalCofins,
        total_other_expenses_val: totalExp,
        total_cost_colvix: totCostColvix,
        pis_credit_initial: totProd * 0.0165,
        cofins_credit_initial: totProd * 0.0760,
        icms_credit_initial: totProd * 0.12,
        ipi_credit_initial: totProd * 0.35,
      },
      items: currentItems,
    };

    fetch('/fiscal-pricing/api/save-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(res => res.json())
      .then(res => {
        if (!res.success) {
          alert('Erro ao salvar lote: ' + res.message);
          return;
        }
        alert(`✓ ${res.message}`);
        window.location.href = '/fiscal-pricing/';
      })
      .catch(err => {
        console.error(err);
        alert('Erro ao conectar com o servidor.');
      });
  };
})();
