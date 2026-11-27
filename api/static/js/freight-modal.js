/**
 * M-One Freight Results Modal & Carrier Ranking Module
 * Suporta:
 * - Seletor de Praça/Faixa (Capital, Reg. Metropolitana, Interior) por UF
 * - Edição livre de Valor (R$) e Prazo (dias) no card
 * - Inclusão manual de transportadora cadastrada na cotação
 * Extracted from freight.js for Anti-Monolith Compliance (< 500 lines)
 */

window.freightSelection = {
  included: new Set(),
  recommended: 0,
  editingIdx: null
};

function recomputeFreightBadges(options) {
  if (!options || !options.length) return;
  const cheapest = Math.min(...options.map(o => Number(o.total_price) || 0));
  const fastest = Math.min(...options.map(o => Number(o.delivery_days) || 1));
  options.forEach(o => {
    const badges = [];
    if (Number(o.total_price) === cheapest) badges.push("Mais Barato");
    if (Number(o.delivery_days) === fastest) badges.push("Mais Rápido");
    o.badges = badges;
  });
}

function toggleCarrierInclusion(idx, evt) {
  if (evt) evt.stopPropagation();
  const data = window.lastFreightCalculationResult;
  if (!data?.options?.[idx]) return;
  const inc = window.freightSelection.included;
  if (inc.has(idx)) {
    inc.delete(idx);
    if (window.freightSelection.recommended === idx) {
      window.freightSelection.recommended = null;
    }
  } else {
    inc.add(idx);
  }
  syncAllCarrierCardViews();
}
window.toggleCarrierInclusion = toggleCarrierInclusion;

function toggleCarrierRecommendation(idx, evt) {
  if (evt) evt.stopPropagation();
  const data = window.lastFreightCalculationResult;
  if (!data?.options?.[idx]) return;
  if (window.freightSelection.recommended === idx) {
    window.freightSelection.recommended = null;
  } else {
    window.freightSelection.recommended = idx;
    window.freightSelection.included.add(idx);
  }
  syncAllCarrierCardViews();
  persistSelectedCarrier();
}
window.toggleCarrierRecommendation = toggleCarrierRecommendation;

function persistSelectedCarrier() {
  const data = window.lastFreightCalculationResult;
  if (!data || (!data.quote_id && !data.quote_number)) return;
  const recIdx = window.freightSelection.recommended;
  const chosen = (recIdx !== null && data.options?.[recIdx]) ? data.options[recIdx] : (data.options?.[0] || null);
  fetch("/freight/quotes/select-carrier", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quote_id: data.quote_id,
      quote_number: data.quote_number,
      selected_carrier: chosen ? chosen.carrier_name : "Comparativo Neutro",
      carrier_name: chosen ? chosen.carrier_name : "Comparativo Neutro",
      selected_price: chosen ? chosen.total_price : 0,
      options: data.options || []
    })
  }).catch(e => console.warn("Erro ao persistir recomendação:", e));
}

function changeCarrierRateVariant(idx, vIdxStr, evt) {
  if (evt) evt.stopPropagation();
  const data = window.lastFreightCalculationResult;
  const opt = data?.options?.[idx];
  const vIdx = parseInt(vIdxStr, 10);
  if (!opt || !opt.rate_variants || !opt.rate_variants[vIdx]) return;
  const chosenVar = opt.rate_variants[vIdx];
  opt.city_label = chosenVar.city_label;
  opt.total_price = Number(chosenVar.total_price);
  opt.delivery_days = Number(chosenVar.delivery_days);
  opt.fixed_price = Number(chosenVar.fixed_price || opt.fixed_price || 0);
  opt.base_freight = Number(chosenVar.base_freight || opt.base_freight || opt.fixed_price || 0);
  opt.insurance_cost = Number(chosenVar.insurance_cost || opt.insurance_cost || 0);
  opt.surcharges_cost = Number(chosenVar.surcharges_cost || opt.surcharges_cost || 0);
  opt.tec_cost = Number(chosenVar.tec_cost || opt.tec_cost || 0);
  opt.tas_cost = Number(chosenVar.tas_cost || opt.tas_cost || 0);
  opt.pos_cost = Number(chosenVar.pos_cost || opt.pos_cost || 0);
  if (chosenVar.phone) opt.phone = chosenVar.phone;
  if (chosenVar.sales_rep_name) opt.sales_rep_name = chosenVar.sales_rep_name;
  if (chosenVar.download_url) opt.download_url = chosenVar.download_url;

  recomputeFreightBadges(data.options);
  renderFreightResultsEverywhere();
  persistSelectedCarrier();
}
window.changeCarrierRateVariant = changeCarrierRateVariant;

function toggleEditCarrierRate(idx, evt) {
  if (evt) evt.stopPropagation();
  window.freightSelection.editingIdx = (window.freightSelection.editingIdx === idx) ? null : idx;
  renderFreightResultsEverywhere();
}
window.toggleEditCarrierRate = toggleEditCarrierRate;

function applyEditedCarrierRate(idx, priceId, daysId, evt) {
  if (evt) evt.stopPropagation();
  const data = window.lastFreightCalculationResult;
  const opt = data?.options?.[idx];
  if (!opt) return;
  const pEl = document.getElementById(priceId);
  const dEl = document.getElementById(daysId);
  const rawPrice = pEl ? parseFloat(String(pEl.value).replace(",", ".")) : NaN;
  const rawDays = dEl ? parseInt(dEl.value, 10) : NaN;

  if (isNaN(rawPrice) || rawPrice < 0) {
    alert("Informe um valor de frete válido (R$).");
    return;
  }
  opt.total_price = Math.round(rawPrice * 100) / 100;
  opt.delivery_days = (!isNaN(rawDays) && rawDays >= 1) ? rawDays : (opt.delivery_days || 1);
  window.freightSelection.editingIdx = null;

  recomputeFreightBadges(data.options);
  renderFreightResultsEverywhere();
  persistSelectedCarrier();
}
window.applyEditedCarrierRate = applyEditedCarrierRate;

function includeCarrierOptionManual(carrierId, carrierName, tableName, priceVal, daysVal) {
  const data = window.lastFreightCalculationResult;
  if (!data) return;
  const numPrice = parseFloat(String(priceVal).replace(",", "."));
  const numDays = parseInt(daysVal, 10);
  if (isNaN(numPrice) || numPrice <= 0) {
    alert("Informe o valor do frete (R$) para incluir a transportadora na cotação.");
    return;
  }
  data.options = data.options || [];
  const existingIdx = data.options.findIndex(o => Number(o.carrier_id) === Number(carrierId));
  const newOpt = {
    carrier_id: Number(carrierId),
    carrier_name: carrierName,
    table_name: tableName || "Tabela Comercial",
    city_label: data.city ? `${data.city}/${data.uf || ''}` : (data.uf || "Padrão"),
    total_price: Math.round(numPrice * 100) / 100,
    fixed_price: Math.round(numPrice * 100) / 100,
    insurance_cost: 0,
    delivery_days: (!isNaN(numDays) && numDays >= 1) ? numDays : 3,
    gross_weight_kg: Number(data.total_weight_kg || 0),
    cubic_weight_kg: Number(data.charged_weight_kg || 0),
    charged_weight_kg: Number(data.charged_weight_kg || 0),
    cubing_factor: 300,
    notes: "",
    rate_variants: []
  };

  if (existingIdx >= 0) {
    data.options[existingIdx] = newOpt;
    window.freightSelection.included.add(existingIdx);
    window.freightSelection.recommended = existingIdx;
  } else {
    data.options.push(newOpt);
    const newIdx = data.options.length - 1;
    window.freightSelection.included.add(newIdx);
    window.freightSelection.recommended = newIdx;
  }

  if (Array.isArray(data.unserved_carriers)) {
    data.unserved_carriers = data.unserved_carriers.filter(u => Number(u.carrier_id) !== Number(carrierId));
  }

  recomputeFreightBadges(data.options);
  renderFreightResultsEverywhere();
  persistSelectedCarrier();
}
window.includeCarrierOptionManual = includeCarrierOptionManual;

function includeFromUnservedCard(uIdx, scopePrefix) {
  const data = window.lastFreightCalculationResult;
  const u = data?.unserved_carriers?.[uIdx];
  if (!u) return;
  const pEl = document.getElementById(`${scopePrefix}_unserved_price_${uIdx}`);
  const dEl = document.getElementById(`${scopePrefix}_unserved_days_${uIdx}`);
  includeCarrierOptionManual(u.carrier_id, u.carrier_name, u.table_name, pEl?.value, dEl?.value);
}
window.includeFromUnservedCard = includeFromUnservedCard;

function includeFromManualDropdown(scopePrefix) {
  const data = window.lastFreightCalculationResult;
  const sel = document.getElementById(`${scopePrefix}_manual_carrier_select`);
  const pEl = document.getElementById(`${scopePrefix}_manual_carrier_price`);
  const dEl = document.getElementById(`${scopePrefix}_manual_carrier_days`);
  if (!sel || !sel.value) {
    alert("Selecione uma transportadora cadastrada.");
    return;
  }
  const optEl = sel.options[sel.selectedIndex];
  const cName = optEl.getAttribute("data-name") || optEl.text;
  const tName = optEl.getAttribute("data-table") || "Tabela Comercial";
  includeCarrierOptionManual(sel.value, cName, tName, pEl?.value, dEl?.value);
}
window.includeFromManualDropdown = includeFromManualDropdown;

function syncAllCarrierCardViews() {
  const data = window.lastFreightCalculationResult;
  if (!data?.options) return;
  const recIdx = window.freightSelection.recommended;
  const inc = window.freightSelection.included;

  document.querySelectorAll(".modal-carrier-card").forEach(card => {
    const idx = parseInt(card.getAttribute("data-idx"), 10);
    if (isNaN(idx)) return;
    const isInc = inc.has(idx);
    const isRec = (recIdx === idx);

    card.classList.toggle("excluded", !isInc);
    card.classList.toggle("recommended", isRec);
    card.classList.toggle("selected", isRec);

    const chk = card.querySelector(".carrier-include-checkbox");
    if (chk) chk.checked = isInc;

    const starBtn = card.querySelector(".carrier-star-btn");
    if (starBtn) {
      starBtn.classList.toggle("recommended", isRec);
      starBtn.innerHTML = isRec ? "⭐ Recomendada" : "☆ Recomendar";
      starBtn.title = isRec ? "Clique para remover recomendação (envio neutro)" : "Definir como opção recomendada pela MAJ";
    }
  });

  const notice = document.getElementById("modalSelectedCarrierNotice");
  if (notice) {
    if (recIdx !== null && data.options[recIdx]) {
      const rec = data.options[recIdx];
      notice.innerHTML = `⭐ Recomendada: <strong style="color: var(--accent);">${rec.carrier_name}</strong> (R$ ${rec.total_price.toFixed(2).replace('.', ',')}) • ${inc.size} no envio`;
    } else {
      notice.innerHTML = `Envio comparativo neutro (${inc.size} transportadora(s) no envio)`;
    }
  }
}
window.syncAllCarrierCardViews = syncAllCarrierCardViews;

// buildCarrierRankingHtml is loaded from static/js/freight-ranking-render.js
if (typeof window.buildCarrierRankingHtml !== "function") {
  window.buildCarrierRankingHtml = function(options, scopePrefix = "modal") {
    if (!options || !options.length) return `<div class="p-3 text-muted text-center">Nenhuma opção de frete disponível.</div>`;
    return options.map((opt, idx) => `
      <div class="rank-row modal-carrier-card" data-idx="${idx}" style="padding: 12px 14px; gap: 12px;">
        <strong>${opt.carrier_name}</strong> - R$ ${Number(opt.total_price).toFixed(2)} (${opt.delivery_days}d)
      </div>
    `).join("");
  };
}

function buildUnservedCarriersHtml(unserved, scopePrefix = "modal") {
  const data = window.lastFreightCalculationResult || {};
  const allCarriers = data.all_active_carriers || [];
  const servedIds = new Set((data.options || []).map(o => Number(o.carrier_id)));
  const availableToAdd = allCarriers.filter(c => !servedIds.has(Number(c.id)));

  let manualBarHtml = "";
  if (availableToAdd.length > 0) {
    const selOpts = availableToAdd.map(c => `<option value="${c.id}" data-name="${c.name}" data-table="${c.table_name || 'Tabela Comercial'}">${c.name}</option>`).join("");
    manualBarHtml = `
      <div style="margin-top: 14px; padding: 12px; border-radius: 12px; background: var(--surface-subtle); border: 1px solid var(--border-subtle);">
        <div style="font-size: 0.72rem; font-weight: 800; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
          ➕ Incluir Transportadora Cadastrada Manualmente
        </div>
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <select id="${scopePrefix}_manual_carrier_select" class="form-input" style="flex: 1; min-width: 160px; font-size: 0.76rem; padding: 6px 10px; border-radius: 8px;">
            ${selOpts}
          </select>
          <input type="number" step="0.01" id="${scopePrefix}_manual_carrier_price" placeholder="Valor R$" class="form-input" style="width: 105px; font-size: 0.76rem; padding: 6px 8px; border-radius: 8px;">
          <input type="number" min="1" id="${scopePrefix}_manual_carrier_days" value="4" placeholder="Dias" title="Prazo em dias úteis" class="form-input" style="width: 68px; font-size: 0.76rem; padding: 6px 8px; text-align: center; border-radius: 8px;">
          <button type="button" class="btn sm primary" style="padding: 6px 12px; font-size: 0.75rem;" onclick="includeFromManualDropdown('${scopePrefix}')">
            Incluir na Cotação
          </button>
        </div>
      </div>
    `;
  }

  if (!unserved || !unserved.length) return manualBarHtml;

  const items = unserved.map((u, uIdx) => `
    <div class="unserved-carrier-card" style="display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap;">
      <div style="flex: 1; min-width: 180px;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span class="unserved-title">${u.carrier_name}</span>
          <span class="unserved-badge">INDISPONÍVEL</span>
          <span class="unserved-table">${u.table_name || ''}</span>
        </div>
        <p class="unserved-reason">⚠️ ${u.reason}</p>
      </div>
      <div style="display: flex; align-items: center; gap: 6px;">
        <input type="number" step="0.01" id="${scopePrefix}_unserved_price_${uIdx}" placeholder="R$ Frete" class="form-input" style="width: 92px; padding: 4px 8px; font-size: 0.74rem; border-radius: 7px;">
        <input type="number" min="1" id="${scopePrefix}_unserved_days_${uIdx}" value="4" title="Prazo (dias úteis)" class="form-input" style="width: 54px; padding: 4px 6px; font-size: 0.74rem; text-align: center; border-radius: 7px;">
        <button type="button" class="btn sm secondary" style="padding: 4px 10px; font-size: 0.72rem;" onclick="includeFromUnservedCard(${uIdx}, '${scopePrefix}')">
          + Incluir
        </button>
      </div>
    </div>
  `).join("");

  return `
    ${manualBarHtml}
    <div style="margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--line);">
      <div style="font-size: 0.75rem; font-weight: 800; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
        Transportadoras Não Classificadas na Tabela (${unserved.length})
      </div>
      <div style="display: flex; flex-direction: column; gap: 8px;">${items}</div>
    </div>
  `;
}
window.buildUnservedCarriersHtml = buildUnservedCarriersHtml;

function renderFreightResultsEverywhere() {
  const data = window.lastFreightCalculationResult;
  if (!data) return;

  const optionsList = document.getElementById("freightOptionsList");
  if (optionsList) {
    const feedRanking = buildCarrierRankingHtml(data.options, "feed");
    const feedUnserved = buildUnservedCarriersHtml(data.unserved_carriers, "feed");
    optionsList.innerHTML = `
      <div class="animate-fade-in space-y-3">
        <div class="radar-item" style="padding: 12px 14px; margin-bottom: 8px;">
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong style="color: var(--text); font-size: 0.84rem;">${data.product_name || 'Carga'}</strong>
              <span class="badge" style="font-size: 0.7rem; font-weight: 700;">${data.total_volumes_count || 1} volume(s)</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.76rem; color: var(--muted); margin-top: 4px;">
              <span>Peso Físico: <strong style="color: var(--text);">${Number(data.total_weight_kg || 0).toFixed(1).replace('.', ',')} kg</strong></span>
              <span>${data.pricing_mode === 'varejo' ? 'Base Seguro (Varejo):' : 'Base Seguro (1/3):'} <strong style="color: var(--accent);">R$ ${Number(data.insurance_base_value || 0).toFixed(2).replace('.', ',')}</strong></span>
            </div>
          </div>
        </div>
        <div class="rank-list">${feedRanking}</div>
        ${feedUnserved}
      </div>
    `;
  }

  const mList = document.getElementById("modalCarrierRankingList");
  if (mList) {
    const modalRanking = buildCarrierRankingHtml(data.options, "modal");
    const modalUnserved = buildUnservedCarriersHtml(data.unserved_carriers, "modal");
    mList.innerHTML = `<div class="rank-list">${modalRanking}</div>${modalUnserved}`;
  }

  syncAllCarrierCardViews();
}
window.renderFreightResultsEverywhere = renderFreightResultsEverywhere;

function openFreightModal(data) {
  const modal = document.getElementById("freightResultsModal");
  if (!modal) return;
  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }

  const loc = `${data.city ? data.city + '/' : ''}${data.uf || ''}`;
  const sub = document.getElementById("modalDestSubtitle");
  if (sub) {
    sub.innerHTML = `Destino: <strong style="color: var(--text-primary);">${loc}</strong> <span style="color: var(--text-secondary);">(CEP ${data.cep_dest})</span> • Cliente: <strong style="color: var(--text-primary);">${data.customer_name || 'Consumidor'}</strong>`;
  }

  const bQuote = document.getElementById("modalQuoteNumberBadge");
  if (bQuote && data.quote_number) bQuote.innerText = data.quote_number;

  const cSum = document.getElementById("modalCargoSummary");
  if (cSum) {
    const vol = data.total_volumes_count || (data.items ? data.items.reduce((acc, it) => acc + (it.qty || 1), 0) : 1);
    cSum.innerText = `${vol} vol • ${data.product_name || 'Carga'}`;
  }

  const wSum = document.getElementById("modalWeightSummary");
  if (wSum) {
    const wVal = parseFloat(data.total_weight_kg) || 0;
    wSum.innerText = `${wVal.toFixed(1).replace('.', ',')} kg físicos`;
  }

  const iLbl = document.getElementById("modalInsuranceLabel");
  if (iLbl) iLbl.innerText = data.pricing_mode === "varejo" ? "Base Seguro (Varejo Cheio)" : "Base Seguro (1/3 Atacado)";

  const iSum = document.getElementById("modalInsuranceSummary");
  if (iSum) {
    const iVal = parseFloat(data.insurance_base_value) || 0;
    iSum.innerText = `R$ ${iVal.toFixed(2).replace('.', ',')}`;
  }

  renderFreightResultsEverywhere();

  modal.style.removeProperty("display");
  modal.style.display = "grid";
  modal.classList.add("show");
}
window.openFreightModal = openFreightModal;

function closeFreightModal() {
  const modal = document.getElementById("freightResultsModal");
  if (!modal) return;
  modal.classList.remove("show");
  modal.style.display = "none";
}
window.closeFreightModal = closeFreightModal;

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeFreightModal();
});
