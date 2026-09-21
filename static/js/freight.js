/*
 * M-One Freight Operations Module (static/js/freight.js)
 */

let lastFreightCalculationResult = null;
let itemRowCounter = 0;

document.addEventListener("DOMContentLoaded", () => {
  addProductRow();
});

function resetFreightForm() {
  document.getElementById("freightCalcForm")?.reset();
  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  setVal("customer_name", ""); setVal("cep_dest", "");
  if (window.DEFAULT_FREIGHT_CEP) setVal("cep_orig", window.DEFAULT_FREIGHT_CEP);
  const txtElem = document.getElementById("cepLocationText"); if (txtElem) txtElem.innerText = "";
  const container = document.getElementById("productRowsContainer");
  if (container) container.innerHTML = "";
  itemRowCounter = 0; addProductRow();
  document.getElementById("freightEmptyState")?.classList.remove("hidden");
  const optionsList = document.getElementById("freightOptionsList");
  if (optionsList) { optionsList.classList.add("hidden"); optionsList.innerHTML = ""; }
  lastFreightCalculationResult = null;
}

function addProductRow() {
  itemRowCounter++;
  const container = document.getElementById("productRowsContainer");
  if (!container) return;
  
  const productsCatalog = window.productsCatalog || [];
  let optionsHtml = `<option value="">-- Selecione o Veículo / Modelo --</option>`;
  productsCatalog.forEach(p => {
    const oneThird = p.one_third_wholesale || 0;
    optionsHtml += `<option value="${p.id}" data-name="${p.name}" data-wholesale="${p.wholesale_price}" data-onethird="${oneThird}" data-weight="${p.weight_kg}" data-l="${p.length_cm}" data-w="${p.width_cm}" data-h="${p.height_cm}">${p.name} (1/3 Atacado: R$ ${oneThird.toFixed(2).replace('.', ',')})</option>`;
  });

  const rowId = `productRow_${itemRowCounter}`;
  const card = document.createElement("div");
  card.id = rowId;
  card.className = "bg-[var(--surface-subtle)] border border-[var(--border-subtle)] rounded-2xl p-4 space-y-3 product-item-card shadow-xs transition-all";

  card.innerHTML = `
    <div class="flex items-end justify-between gap-3">
      <div class="flex-1 min-w-0">
        <label class="block text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-1.5">Modelo do Veículo / Produto</label>
        <select class="product-select form-input w-full px-3 py-2 text-xs text-[var(--text-primary)] min-w-0 font-medium rounded-xl" onchange="onProductSelectChange('${rowId}')">
          ${optionsHtml}
        </select>
      </div>
      <div class="flex-shrink-0">
        <button type="button" class="btn-remove-item" onclick="removeProductRow('${rowId}')" title="Remover este item da carga" aria-label="Remover item">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
          <span>Remover</span>
        </button>
      </div>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-6 gap-2.5 items-end text-xs">
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Qtd</label>
        <input type="number" min="1" value="1" class="product-qty form-input w-full text-center text-xs py-1.5 min-w-0 rounded-xl" onchange="updateTotalsSummary()" onkeyup="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Peso (kg)</label>
        <input type="number" step="0.1" value="" placeholder="kg" class="product-weight form-input w-full text-center text-xs py-1.5 min-w-0 rounded-xl" onchange="updateTotalsSummary()" onkeyup="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Compr. (cm)</label>
        <input type="number" value="" placeholder="C" class="product-length form-input w-full text-center text-xs py-1.5 min-w-0 rounded-xl" onchange="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Largura (cm)</label>
        <input type="number" value="" placeholder="L" class="product-width form-input w-full text-center text-xs py-1.5 min-w-0 rounded-xl" onchange="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">Altura (cm)</label>
        <input type="number" value="" placeholder="A" class="product-height form-input w-full text-center text-xs py-1.5 min-w-0 rounded-xl" onchange="updateTotalsSummary()">
      </div>
      <div class="min-w-0 col-span-2 sm:col-span-1 text-right">
        <label class="block text-[10px] font-semibold text-[var(--text-muted)] mb-1">1/3 Atacado</label>
        <span class="product-onethird-display text-xs font-bold text-[var(--brand-blue)] block py-1">R$ 0,00</span>
      </div>
    </div>
  `;

  container.appendChild(card);
  updateTotalsSummary();
}

function removeProductRow(rowId) {
  const container = document.getElementById("productRowsContainer");
  if (container.children.length <= 1) {
    alert("A cotação deve conter ao menos 1 item.");
    return;
  }
  const elem = document.getElementById(rowId);
  if (elem) elem.remove();
  updateTotalsSummary();
}

function onProductSelectChange(rowId) {
  const row = document.getElementById(rowId);
  if (!row) return;
  const select = row.querySelector(".product-select");
  const opt = select.options[select.selectedIndex];
  const hasVal = opt && opt.value;
  const oneThird = hasVal ? parseFloat(opt.getAttribute("data-onethird") || 0) : 0;
  row.querySelector(".product-onethird-display").innerText = `R$ ${oneThird.toFixed(2).replace('.', ',')}`;
  row.querySelector(".product-weight").value = (hasVal && opt.getAttribute("data-weight") !== null) ? opt.getAttribute("data-weight") : "";
  row.querySelector(".product-length").value = (hasVal && opt.getAttribute("data-l") !== null) ? opt.getAttribute("data-l") : "";
  row.querySelector(".product-width").value = (hasVal && opt.getAttribute("data-w") !== null) ? opt.getAttribute("data-w") : "";
  row.querySelector(".product-height").value = (hasVal && opt.getAttribute("data-h") !== null) ? opt.getAttribute("data-h") : "";
  updateTotalsSummary();
}

function updateTotalsSummary() {
  const rows = document.querySelectorAll("#productRowsContainer > .product-item-card");
  let totalQty = 0, totalPhysicalWeight = 0, totalCubicWeight = 0, totalInsurance = 0;
  rows.forEach(row => {
    const sel = row.querySelector(".product-select");
    const opt = sel ? sel.options[sel.selectedIndex] : null;
    const qty = intVal(row.querySelector(".product-qty")?.value, 1);
    const w = floatVal(row.querySelector(".product-weight")?.value, 0);
    const l = floatVal(row.querySelector(".product-length")?.value, 0);
    const wid = floatVal(row.querySelector(".product-width")?.value, 0);
    const h = floatVal(row.querySelector(".product-height")?.value, 0);
    const oneThird = parseFloat(opt ? opt.getAttribute("data-onethird") || 0 : 0);
    totalQty += qty;
    totalPhysicalWeight += (w * qty);
    totalCubicWeight += (((l * wid * h) / 6000.0) * qty);
    totalInsurance += (oneThird * qty);
  });
  const setEl = (id, txt) => { const el = document.getElementById(id); if (el) el.innerText = txt; };
  setEl("summaryTotalQty", totalQty);
  setEl("summaryTotalWeight", `${totalPhysicalWeight.toFixed(1).replace('.', ',')} kg`);
  setEl("summaryCubicWeight", `${totalCubicWeight.toFixed(1).replace('.', ',')} kg`);
  setEl("summaryTotalInsurance", `R$ ${totalInsurance.toFixed(2).replace('.', ',')}`);
}

const intVal = (v, def=0) => { const p = parseInt(v); return isNaN(p) ? def : p; };
const floatVal = (v, def=0.0) => { const p = parseFloat(v); return isNaN(p) ? def : p; };

async function lookupViaCEP(cepVal) {
  if (!cepVal) return;
  const clean = cepVal.replace(/\D/g, "");
  if (clean.length !== 8) return;
  
  const txtElem = document.getElementById("cepLocationText");
  if (txtElem) txtElem.innerText = "Buscando localização...";
  
  try {
    const res = await fetch(`https://viacep.com.br/ws/${clean}/json/`);
    const data = await res.json();
    if (txtElem) {
      if (data.erro) {
        txtElem.innerText = "❌ CEP não encontrado.";
      } else {
        txtElem.innerText = `📍 ${data.logradouro ? data.logradouro + ', ' : ''}${data.bairro ? data.bairro + ' - ' : ''}${data.localidade}/${data.uf}`;
      }
    }
  } catch (err) {
    if (txtElem) txtElem.innerText = "";
  }
}

async function runFreightCalculation() {
  const getVal = (id) => (document.getElementById(id)?.value || "").trim();
  const cep_dest = getVal("cep_dest"), cep_orig = getVal("cep_orig"), customer_name = getVal("customer_name");
  const company_name = getVal("company_name"), cpf_cnpj = getVal("cpf_cnpj"), contact_phone = getVal("contact_phone");
  const contact_person = getVal("contact_person"), full_address = getVal("full_address");

  if (!cep_dest) {
    alert("Informe o CEP de destino.");
    return;
  }

  const rows = document.querySelectorAll("#productRowsContainer > .product-item-card");
  const items = [];

  rows.forEach(row => {
    const select = row.querySelector(".product-select");
    const qtyInput = row.querySelector(".product-qty");
    const weightInput = row.querySelector(".product-weight");
    const lInput = row.querySelector(".product-length");
    const wInput = row.querySelector(".product-width");
    const hInput = row.querySelector(".product-height");
    const selectedOpt = select.options[select.selectedIndex];
    
    const productId = selectedOpt.value;
    const qty = intVal(qtyInput.value, 1);
    const weight = floatVal(weightInput.value, 0);
    const l = floatVal(lInput.value, 0);
    const w = floatVal(wInput.value, 0);
    const h = floatVal(hInput.value, 0);
    const productName = selectedOpt.getAttribute("data-name") || (selectedOpt.text ? selectedOpt.text.split("(")[0].trim() : "");

    if (productId || weight > 0) {
      items.push({
        product_id: productId,
        name: productName,
        qty: qty,
        weight_kg: weight,
        length_cm: l,
        width_cm: w,
        height_cm: h
      });
    }
  });

  if (items.length === 0) {
    alert("Selecione ao menos um produto válido na cotação.");
    return;
  }

  const emptyState = document.getElementById("freightEmptyState");
  const optionsList = document.getElementById("freightOptionsList");
  const submitBtns = document.querySelectorAll("#freightCalcForm button[type='submit'], #btnFreightSubmitHeader");
  submitBtns.forEach(btn => {
    if (!btn.dataset.origHtml) btn.dataset.origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.classList.add("opacity-80", "cursor-wait");
    btn.innerHTML = `
      <svg class="icon-svg animate-spin" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>
      <span>Consultando Transportadoras...</span>
    `;
  });

  if (emptyState) emptyState.classList.add("hidden");
  if (optionsList) {
    optionsList.classList.remove("hidden");
    optionsList.innerHTML = `
      <div class="freight-loading-card p-8 text-center rounded-2xl flex flex-col items-center justify-center min-h-[380px] shadow-sm">
        <div class="relative mb-4">
          <div class="w-16 h-16 rounded-2xl bg-[var(--surface-card)] border border-[var(--border-subtle)] text-[var(--brand-emerald)] flex items-center justify-center shadow-md icon-svg">
            <svg class="animate-spin" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
          </div>
          <span class="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-[var(--brand-emerald)] border-2 border-[var(--surface-card)] animate-pulse shadow-xs"></span>
        </div>
        <h3 class="text-sm font-extrabold text-[var(--text-primary)] tracking-tight">Simulando Melhores Rotas de Frete</h3>
        <p class="text-xs text-[var(--text-secondary)] mt-1.5 max-w-[300px]">
          Consultando tabelas ativas, peso cúbico e regra obrigatória de seguro de 1/3 do atacado...
        </p>
        <div class="w-48 progress-track mt-5">
          <div class="progress-fill progress-indeterminate" style="width: 100%;"></div>
        </div>
        <div class="mt-4 flex items-center gap-2 text-[11px] text-[var(--text-muted)] bg-[var(--surface-card)] px-3 py-1.5 rounded-full border border-[var(--border-subtle)] shadow-xs">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>Origem Vitória/ES • Cotação Dinâmica</span>
        </div>
      </div>
    `;
  }

  try {
    const calcUrl = window.FREIGHT_CALCULATE_URL || "/freight/calculate";
    const resp = await fetch(calcUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        cep_dest, cep_orig, items, 
        customer_name, company_name, cpf_cnpj, 
        contact_phone, contact_person, full_address 
      })
    });
    
    const data = await resp.json();
    window.lastFreightCalculationResult = lastFreightCalculationResult = { ...data, items: data.items || items, customer_name, cep_dest };

    if (!data.success || !data.options || data.options.length === 0) {
      optionsList.innerHTML = `
        <div class="bg-amber-950/60 border border-amber-800/60 text-amber-300 p-4 rounded-xl text-xs">
          ⚠️ ${data.message || 'Nenhuma transportadora cadastrada atende a este CEP ou faixa de peso.'}
        </div>
      `;
      return;
    }

    // Ordenação por menor preço e inicialização da seleção múltipla
    data.options.sort((a, b) => a.total_price - b.total_price || a.delivery_days - b.delivery_days);
    if (window.freightSelection) {
      window.freightSelection.included = new Set(data.options.map((_, i) => i));
      window.freightSelection.recommended = 0;
    }

    const rankingCardsHtml = (typeof buildCarrierRankingHtml === "function") ? buildCarrierRankingHtml(data.options) : "";
    const unservedHtml = (typeof buildUnservedCarriersHtml === "function") ? buildUnservedCarriersHtml(data.unserved_carriers) : "";

    optionsList.innerHTML = `
      <div class="animate-fade-in space-y-3">
        <div class="radar-item" style="padding: 12px 14px; margin-bottom: 8px;">
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong style="color: var(--text); font-size: 0.84rem;">${data.product_name}</strong>
              <span class="badge" style="font-size: 0.7rem; font-weight: 700;">${data.total_volumes_count || 1} volume(s)</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.76rem; color: var(--muted); margin-top: 4px;">
              <span>Peso Físico: <strong style="color: var(--text);">${data.total_weight_kg.toFixed(1).replace('.', ',')} kg</strong></span>
              <span>Base Seguro (1/3): <strong style="color: var(--accent);">R$ ${data.insurance_base_value.toFixed(2).replace('.', ',')}</strong></span>
            </div>
          </div>
        </div>
        <div class="rank-list">${rankingCardsHtml}</div>
        ${unservedHtml}
      </div>
    `;

    if (typeof openFreightModal === "function") {
      openFreightModal(data, rankingCardsHtml);
    }
  } catch (err) {
    if (optionsList) {
      optionsList.innerHTML = `<div class="bg-red-950/60 border border-red-800/60 text-red-300 p-4 rounded-xl text-xs">Erro ao realizar cálculo: ${err.message}</div>`;
    }
  } finally {
    document.querySelectorAll("#freightCalcForm button[type='submit'], #btnFreightSubmitHeader").forEach(btn => {
      btn.disabled = false;
      btn.classList.remove("opacity-80", "cursor-wait");
      if (btn.dataset.origHtml) {
        btn.innerHTML = btn.dataset.origHtml;
      }
    });
  }
}
