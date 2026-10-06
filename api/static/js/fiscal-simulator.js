/**
 * M-One Fiscal Simulator - Dual Comparative & NF-e Mirror Modal Controller
 */
(function () {
  'use strict';

  let currentMirrorData = null;

  window.runSimulation = function () {
    const unitCost = parseFloat(document.getElementById('simUnitCost')?.value || 8500);
    const marginPct = parseFloat(document.getElementById('simMarginPct')?.value || 30);
    const destUf = document.getElementById('simDestUf')?.value || 'SP';
    const ipiPct = parseFloat(document.getElementById('simIpiPct')?.value || 35);
    const mvaPct = parseFloat(document.getElementById('simMvaPct')?.value || 34);
    const opExpPct = parseFloat(document.getElementById('simOpExpPct')?.value || 5);

    // 1. Simular Cenário 1 (COLVIX -> M-ONE)
    const payload1 = {
      unit_cost_colvix: unitCost,
      margin_pct: marginPct,
      dest_uf: destUf,
      dest_type: 'M-ONE',
      ipi_sale_pct: ipiPct,
      mva_pct: mvaPct,
      op_expenses_pct: opExpPct,
    };

    // 2. Simular Cenário 2 (COLVIX -> PJ Direto)
    const payload2 = {
      unit_cost_colvix: unitCost,
      margin_pct: marginPct,
      dest_uf: destUf,
      dest_type: 'PJ_DIRECT',
      ipi_sale_pct: ipiPct,
      mva_pct: mvaPct,
      op_expenses_pct: opExpPct,
    };

    Promise.all([
      fetch('/fiscal-pricing/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload1),
      }).then(r => r.json()),
      fetch('/fiscal-pricing/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload2),
      }).then(r => r.json()),
    ]).then(([res1, res2]) => {
      if (res1.success && res1.sim) {
        updateScenario1(res1.sim);
      }
      if (res2.success && res2.sim) {
        updateScenario2(res2.sim);
        currentMirrorData = res2.mirror;
      }
    }).catch(err => {
      console.error('[Simulation Error]:', err);
    });
  };

  function updateScenario1(sim) {
    const pSale = document.getElementById('c1SalePrice');
    const pIcms = document.getElementById('c1IcmsOwn');
    const pIpi = document.getElementById('c1IpiSale');
    const pPisCofins = document.getElementById('c1PisCofins');
    const pSt = document.getElementById('c1IcmsSt');
    const pNet = document.getElementById('c1NetProfit');

    if (pSale) pSale.innerText = `R$ ${(sim.total_sale_price || 0).toFixed(2)}`;
    if (pIcms) pIcms.innerText = `R$ ${(sim.icms_own_val || 0).toFixed(2)}`;
    if (pIpi) pIpi.innerText = `R$ ${(sim.ipi_sale_val || 0).toFixed(2)}`;
    if (pPisCofins) pPisCofins.innerText = `R$ ${((sim.pis_sale_val || 0) + (sim.cofins_sale_val || 0)).toFixed(2)}`;
    if (pSt) pSt.innerText = `R$ ${(sim.icms_st_val || 0).toFixed(2)}`;
    if (pNet) pNet.innerText = `R$ ${(sim.net_profit || 0).toFixed(2)}`;
  }

  function updateScenario2(sim) {
    const pSale = document.getElementById('c2SalePrice');
    const pIcms = document.getElementById('c2IcmsOwn');
    const pIpi = document.getElementById('c2IpiSale');
    const pSt = document.getElementById('c2IcmsSt');
    const pSaving = document.getElementById('c2CashSaving');
    const pNet = document.getElementById('c2NetProfit');

    if (pSale) pSale.innerText = `R$ ${(sim.total_sale_price || 0).toFixed(2)}`;
    if (pIcms) pIcms.innerText = `R$ ${(sim.icms_own_val || 0).toFixed(2)}`;
    if (pIpi) pIpi.innerText = `R$ ${(sim.ipi_sale_val || 0).toFixed(2)}`;
    if (pSt) pSt.innerText = `R$ ${(sim.icms_st_val || 0).toFixed(2)} (PJ)`;
    if (pSaving) pSaving.innerText = `R$ ${(sim.st_cashflow_saving || 0).toFixed(2)}`;
    if (pNet) pNet.innerText = `R$ ${(sim.net_profit || 0).toFixed(2)}`;
  }

  window.onSimBatchChange = function (select) {
    if (!select.value) return;
    const batchId = select.value;
    fetch(`/fiscal-pricing/api/batch-items/${batchId}`)
      .then(r => r.json())
      .then(res => {
        if (res.success && res.items && res.items.length > 0) {
          const item = res.items[0];
          const unitCostInput = document.getElementById('simUnitCost');
          if (unitCostInput) unitCostInput.value = item.unit_cost_colvix || 8500;
          runSimulation();
        }
      });
  };

  window.openNfeMirrorModal = function () {
    const modal = document.getElementById('nfeMirrorModal');
    if (!modal) return;

    if (currentMirrorData) {
      populateMirrorModal(currentMirrorData);
    }
    modal.style.display = 'flex';
  };

  window.closeNfeMirrorModal = function () {
    const modal = document.getElementById('nfeMirrorModal');
    if (modal) modal.style.display = 'none';
  };

  function populateMirrorModal(mirror) {
    const h = mirror.header || {};
    const t = mirror.totals || {};

    const mUf = document.getElementById('mNfeUf');
    const mDest = document.getElementById('mNfeDestType');
    const mNcm = document.getElementById('mNfeNcm');
    const mMva = document.getElementById('mNfeMva');

    if (mUf) mUf.innerText = `${h.uf_emissor || 'ES'} ➔ ${h.uf_destino || 'SP'}`;
    if (mDest) mDest.innerText = h.destinatario_tipo || 'Venda PJ Direto';
    if (mNcm) mNcm.innerText = h.ncm || '87116000';
    if (mMva) mMva.innerText = `${mirror.rates?.pMVA || 34.00} %`;

    document.getElementById('mNfeVProd').innerText = `R$ ${(t.vProd || 0).toFixed(2)}`;
    document.getElementById('mNfeVBc').innerText = `R$ ${(t.vBC_ICMS || 0).toFixed(2)}`;
    document.getElementById('mNfeVIcms').innerText = `R$ ${(t.vICMS || 0).toFixed(2)}`;
    document.getElementById('mNfeVBcSt').innerText = `R$ ${(t.vBC_ST || 0).toFixed(2)}`;
    document.getElementById('mNfeVSt').innerText = `R$ ${(t.vST || 0).toFixed(2)}`;
    document.getElementById('mNfeVIpi').innerText = `R$ ${(t.vIPI || 0).toFixed(2)}`;
    document.getElementById('mNfeVPisCofins').innerText = `R$ ${((t.vPIS || 0) + (t.vCOFINS || 0)).toFixed(2)}`;
    document.getElementById('mNfeVNf').innerText = `R$ ${(t.vNF || 0).toFixed(2)}`;

    const savingVal = document.getElementById('mNfeSavingVal');
    if (savingVal) savingVal.innerText = `R$ ${(mirror.cashflow_highlight?.saving || 0).toFixed(2)}`;
  }

  document.addEventListener('DOMContentLoaded', function () {
    runSimulation();
  });
})();
