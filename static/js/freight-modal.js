/**
 * M-One Freight Results Modal & Carrier Ranking Module
 * Extracted from freight.js for Anti-Monolith Compliance (< 500 lines)
 */

window.freightSelection = {
  included: new Set(),
  recommended: 0
};

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
  const chosen = (recIdx !== null && data.options[recIdx]) ? data.options[recIdx] : null;
  fetch("/freight/quotes/select-carrier", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quote_id: data.quote_id,
      quote_number: data.quote_number,
      selected_carrier: chosen ? chosen.carrier_name : "Comparativo Neutro",
      carrier_name: chosen ? chosen.carrier_name : "Comparativo Neutro",
      selected_price: chosen ? chosen.total_price : 0
    })
  }).catch(e => console.warn("Erro ao persistir recomendação:", e));
}

function syncAllCarrierCardViews() {
  const data = window.lastFreightCalculationResult;
  if (!data?.options) return;
  const recIdx = window.freightSelection.recommended;
  const inc = window.freightSelection.included;

  document.querySelectorAll(".modal-carrier-card").forEach(card => {
    const idx = parseInt(card.getAttribute("data-idx"));
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

function buildCarrierRankingHtml(options) {
  if (!options || options.length === 0) return "";
  const recIdx = window.freightSelection.recommended;
  const inc = window.freightSelection.included;

  return options.map((opt, idx) => {
    const isInc = inc.has(idx);
    const isRec = (recIdx === idx);
    const isCheapest = opt.badges && opt.badges.some(b => b.includes("Barato"));
    const isFastest = opt.badges && opt.badges.some(b => b.includes("Rápido"));
    const rankBg = isCheapest ? "var(--brand-emerald)" : (isFastest ? "var(--brand-blue)" : "var(--primary)");
    const rankColor = (isCheapest || isFastest) ? "#042211" : "var(--text)";
    const badgeHtml = isCheapest ? `<span class="badge" style="background: rgba(0,229,153,0.12); color: var(--accent); border-color: rgba(0,229,153,0.25); font-size: 9px; padding: 2px 6px;">MAIS ECONÔMICA</span>`
      : (isFastest ? `<span class="badge" style="background: rgba(56,189,248,0.12); color: var(--brand-blue); border-color: rgba(56,189,248,0.25); font-size: 9px; padding: 2px 6px;">MAIS RÁPIDA</span>` : "");

    return `
      <div class="rank-row modal-carrier-card ${isRec ? 'recommended selected' : ''} ${!isInc ? 'excluded' : ''}" data-idx="${idx}" style="padding: 12px 14px; gap: 12px; cursor: pointer; align-items: center;" onclick="toggleCarrierRecommendation(${idx}, event)">
        <input type="checkbox" class="carrier-include-checkbox" title="${isInc ? 'Desmarcar para não enviar esta opção' : 'Marcar para incluir no envio'}" ${isInc ? 'checked' : ''} onclick="toggleCarrierInclusion(${idx}, event)">

        <div class="rank-num" style="background: ${rankBg}; color: ${rankColor}; width: 24px; height: 24px; border-radius: 6px; font-size: 11px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
          ${idx + 1}
        </div>

        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <strong style="color: var(--text); font-size: 0.95rem; letter-spacing: -0.01em;">${opt.carrier_name}</strong>
            ${badgeHtml}
            <span class="carrier-chosen-tag" style="background: rgba(0,229,153,0.15); color: var(--accent); border: 1px solid rgba(0,229,153,0.3); font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px;">
              ✓ RECOMENDADA
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px; font-size: 0.76rem; color: var(--muted); margin-top: 3px;">
            <span>Tabela: <strong style="color: var(--text-secondary);">${opt.table_name}</strong></span>
            <span>•</span>
            <span>Prazo: <strong style="color: var(--text);">${opt.delivery_days} dia(s) útil(eis)</strong></span>
          </div>
        </div>

        <div style="text-align: right; flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
          <div style="font-size: 1.15rem; font-weight: 800; color: ${isCheapest ? 'var(--accent)' : 'var(--text)'}; letter-spacing: -0.02em;">
            R$ ${opt.total_price.toFixed(2).replace('.', ',')}
          </div>
          <button type="button" class="carrier-star-btn ${isRec ? 'recommended' : ''}" onclick="toggleCarrierRecommendation(${idx}, event)" title="${isRec ? 'Remover recomendação' : 'Recomendar ao cliente'}">
            ${isRec ? '⭐ Recomendada' : '☆ Recomendar'}
          </button>
        </div>
      </div>
    `;
  }).join("");
}
window.buildCarrierRankingHtml = buildCarrierRankingHtml;

function buildUnservedCarriersHtml(unserved) {
  if (!unserved || !unserved.length) return "";
  const items = unserved.map(u => `
    <div class="unserved-carrier-card">
      <div style="flex: 1; min-width: 0;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span class="unserved-title">${u.carrier_name}</span>
          <span class="unserved-badge">INDISPONÍVEL</span>
          <span class="unserved-table">${u.table_name || ''}</span>
        </div>
        <p class="unserved-reason">⚠️ ${u.reason}</p>
      </div>
    </div>
  `).join("");
  return `
    <div style="margin-top: 16px; padding-top: 14px; border-top: 1px dashed var(--line);">
      <div style="font-size: 0.75rem; font-weight: 800; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
        Transportadoras Não Classificadas (${unserved.length})
      </div>
      <div style="display: flex; flex-direction: column; gap: 8px;">${items}</div>
    </div>
  `;
}
window.buildUnservedCarriersHtml = buildUnservedCarriersHtml;

function openFreightModal(data, rankingHtml) {
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

  const iSum = document.getElementById("modalInsuranceSummary");
  if (iSum) {
    const iVal = parseFloat(data.insurance_base_value) || 0;
    iSum.innerText = `R$ ${iVal.toFixed(2).replace('.', ',')}`;
  }

  const mList = document.getElementById("modalCarrierRankingList");
  if (mList) {
    const unservedHtml = buildUnservedCarriersHtml(data.unserved_carriers);
    mList.innerHTML = `<div class="rank-list">${buildCarrierRankingHtml(data.options)}</div>${unservedHtml}`;
  }

  syncAllCarrierCardViews();

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
