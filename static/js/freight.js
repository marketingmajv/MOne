/*
 * M-One Freight Operations Module (static/js/freight.js)
 */

let lastFreightCalculationResult = null;
let itemRowCounter = 0;

document.addEventListener("DOMContentLoaded", () => {
  addProductRow();
});

function resetFreightForm() {
  const form = document.getElementById("freightCalcForm");
  if (form) form.reset();
  
  const customerName = document.getElementById("customer_name");
  if (customerName) customerName.value = "";
  
  const cepDest = document.getElementById("cep_dest");
  if (cepDest) cepDest.value = "";
  
  const cepOrig = document.getElementById("cep_orig");
  if (cepOrig && window.DEFAULT_FREIGHT_CEP) cepOrig.value = window.DEFAULT_FREIGHT_CEP;
  
  const txtElem = document.getElementById("cepLocationText");
  if (txtElem) txtElem.innerText = "";
  
  const container = document.getElementById("productRowsContainer");
  if (container) container.innerHTML = "";
  itemRowCounter = 0;
  addProductRow();

  const emptyState = document.getElementById("freightEmptyState");
  const optionsList = document.getElementById("freightOptionsList");
  if (emptyState) emptyState.classList.remove("hidden");
  if (optionsList) {
    optionsList.classList.add("hidden");
    optionsList.innerHTML = "";
  }
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
        <button type="button" class="h-10 w-10 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/20 flex items-center justify-center transition-all icon-svg cursor-pointer shadow-xs" onclick="removeProductRow('${rowId}')" title="Remover item">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
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
  const selectedOpt = select.options[select.selectedIndex];

  if (selectedOpt && selectedOpt.value) {
    const oneThirdVal = parseFloat(selectedOpt.getAttribute("data-onethird") || 0);
    const weightVal = selectedOpt.getAttribute("data-weight");
    const lengthVal = selectedOpt.getAttribute("data-l");
    const widthVal = selectedOpt.getAttribute("data-w");
    const heightVal = selectedOpt.getAttribute("data-h");

    row.querySelector(".product-onethird-display").innerText = `R$ ${oneThirdVal.toFixed(2).replace('.', ',')}`;
    row.querySelector(".product-weight").value = weightVal !== null ? weightVal : "";
    row.querySelector(".product-length").value = lengthVal !== null ? lengthVal : "";
    row.querySelector(".product-width").value = widthVal !== null ? widthVal : "";
    row.querySelector(".product-height").value = heightVal !== null ? heightVal : "";
  } else {
    row.querySelector(".product-onethird-display").innerText = "R$ 0,00";
    row.querySelector(".product-weight").value = "";
    row.querySelector(".product-length").value = "";
    row.querySelector(".product-width").value = "";
    row.querySelector(".product-height").value = "";
  }

  updateTotalsSummary();
}

function updateTotalsSummary() {
  const rows = document.querySelectorAll("#productRowsContainer > .product-item-card");
  let totalQty = 0;
  let totalPhysicalWeight = 0;
  let totalCubicWeight = 0;
  let totalInsurance = 0;

  rows.forEach(row => {
    const select = row.querySelector(".product-select");
    const qtyInput = row.querySelector(".product-qty");
    const weightInput = row.querySelector(".product-weight");
    const lInput = row.querySelector(".product-length");
    const wInput = row.querySelector(".product-width");
    const hInput = row.querySelector(".product-height");
    const selectedOpt = select.options[select.selectedIndex];

    const qty = intVal(qtyInput.value, 1);
    const weight = floatVal(weightInput.value, 0);
    const l = floatVal(lInput.value, 0);
    const w = floatVal(wInput.value, 0);
    const h = floatVal(hInput.value, 0);
    const oneThirdVal = parseFloat(selectedOpt ? selectedOpt.getAttribute("data-onethird") || 0 : 0);

    const cubicWeightPerUnit = (l * w * h) / 6000.0;

    totalQty += qty;
    totalPhysicalWeight += (weight * qty);
    totalCubicWeight += (cubicWeightPerUnit * qty);
    totalInsurance += (oneThirdVal * qty);
  });

  const elQty = document.getElementById("summaryTotalQty");
  if (elQty) elQty.innerText = totalQty;
  
  const elW = document.getElementById("summaryTotalWeight");
  if (elW) elW.innerText = `${totalPhysicalWeight.toFixed(1).replace('.', ',')} kg`;
  
  const elCw = document.getElementById("summaryCubicWeight");
  if (elCw) elCw.innerText = `${totalCubicWeight.toFixed(1).replace('.', ',')} kg`;
  
  const elIns = document.getElementById("summaryTotalInsurance");
  if (elIns) elIns.innerText = `R$ ${totalInsurance.toFixed(2).replace('.', ',')}`;
}

function intVal(v, def=0) {
  const p = parseInt(v);
  return isNaN(p) ? def : p;
}
function floatVal(v, def=0.0) {
  const p = parseFloat(v);
  return isNaN(p) ? def : p;
}

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
  const cep_dest = document.getElementById("cep_dest").value.trim();
  const cep_orig = document.getElementById("cep_orig").value.trim();
  const customer_name = (document.getElementById("customer_name")?.value || "").trim();
  const company_name = (document.getElementById("company_name")?.value || "").trim();
  const cpf_cnpj = (document.getElementById("cpf_cnpj")?.value || "").trim();
  const contact_phone = (document.getElementById("contact_phone")?.value || "").trim();
  const contact_person = (document.getElementById("contact_person")?.value || "").trim();
  const full_address = (document.getElementById("full_address")?.value || "").trim();

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
  const submitBtn = document.querySelector("#freightCalcForm button[type='submit']");
  const origBtnHtml = submitBtn ? submitBtn.innerHTML : "";
  
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.classList.add("opacity-80", "cursor-wait");
    submitBtn.innerHTML = `
      <svg class="icon-svg animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>
      <span>Consultando Transportadoras...</span>
    `;
  }

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
    lastFreightCalculationResult = { ...data, items: data.items || items, customer_name, cep_dest };

    if (!data.success || !data.options || data.options.length === 0) {
      optionsList.innerHTML = `
        <div class="bg-amber-950/60 border border-amber-800/60 text-amber-300 p-4 rounded-xl text-xs">
          ⚠️ ${data.message || 'Nenhuma transportadora cadastrada atende a este CEP ou faixa de peso.'}
        </div>
      `;
      return;
    }

    let html = `
      <div class="animate-fade-in space-y-3">
        <div class="radar-item" style="padding: 12px 14px; margin-bottom: 8px;">
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong style="color: var(--text); font-size: 0.84rem;">${data.product_name}</strong>
              <span class="badge" style="font-size: 0.7rem; font-weight: 700;">${data.total_volumes_count || (data.items ? data.items.reduce((acc, it) => acc + (it.qty || 1), 0) : 1)} volume(s)</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.76rem; color: var(--muted); margin-top: 4px;">
              <span>Peso Físico: <strong style="color: var(--text);">${data.total_weight_kg.toFixed(1).replace('.', ',')} kg</strong></span>
              <span>Base Seguro (1/3): <strong style="color: var(--accent);">R$ ${data.insurance_base_value.toFixed(2).replace('.', ',')}</strong></span>
            </div>
          </div>
        </div>

        <div class="rank-list">
    `;

    // Ordenação por menor preço
    data.options.sort((a, b) => a.total_price - b.total_price || a.delivery_days - b.delivery_days);

    data.options.forEach((opt, idx) => {
      let isCheapest = opt.badges && opt.badges.some(b => b.includes("Barato"));
      let isFastest = opt.badges && opt.badges.some(b => b.includes("Rápido"));

      let rankBg = "var(--primary)";
      let rankColor = "#042211";
      let rowBorder = "1px solid var(--line)";
      let badgeHtml = "";

      if (isCheapest) {
        rankBg = "var(--brand-emerald)";
        rankColor = "#042211";
        rowBorder = "1px solid rgba(0, 229, 153, 0.35)";
        badgeHtml = `<span class="badge" style="background: rgba(0,229,153,0.12); color: var(--accent); border-color: rgba(0,229,153,0.25); font-size: 9px; padding: 2px 6px; margin-left: 6px;">MAIS ECONÔMICA</span>`;
      } else if (isFastest) {
        rankBg = "var(--brand-blue)";
        rankColor = "#FFFFFF";
        rowBorder = "1px solid rgba(56, 189, 248, 0.35)";
        badgeHtml = `<span class="badge" style="background: rgba(56,189,248,0.12); color: var(--brand-blue); border-color: rgba(56,189,248,0.25); font-size: 9px; padding: 2px 6px; margin-left: 6px;">MAIS RÁPIDA</span>`;
      }

      html += `
        <div class="rank-row" style="border: ${rowBorder}; padding: 12px 14px; gap: 12px;">
          <span class="rank" style="background: ${rankBg}; color: ${rankColor}; flex-shrink: 0;">${idx + 1}</span>
          <div class="grow" style="min-width: 0;">
            <div style="display: flex; align-items: center; flex-wrap: wrap;">
              <b style="font-size: 0.88rem; color: var(--text);">${opt.carrier_name}</b>
              ${badgeHtml}
            </div>
            <small style="color: var(--muted); font-size: 0.74rem; display: block; margin-top: 2px;">
              Tabela: ${opt.table_name} • Prazo: <strong style="color: var(--text);">${opt.delivery_days} dia(s) útil(eis)</strong>
            </small>
            ${opt.insurance_cost > 0 ? `<small style="color: var(--muted); font-size: 0.7rem; display: block;">Seguro incluso: R$ ${opt.insurance_cost.toFixed(2).replace('.', ',')}</small>` : ''}
          </div>
          <div style="text-align: right; flex-shrink: 0;">
            <strong class="tabular-nums" style="display: block; font-size: 1.15rem; font-weight: 800; color: ${isCheapest ? 'var(--accent)' : 'var(--brand-blue)'};">
              R$ ${opt.total_price.toFixed(2).replace('.', ',')}
            </strong>
            <button type="button" onclick="exportFreightPDF(${idx})" class="link-btn" style="font-size: 0.72rem; margin-top: 3px; display: inline-flex; align-items: center; gap: 4px;" title="Exportar PDF desta transportadora">
              <span>Exportar PDF ↗</span>
            </button>
          </div>
        </div>
      `;
    });

    html += `
        </div>
      </div>
    `;
    optionsList.innerHTML = html;
  } catch (err) {
    if (optionsList) {
      optionsList.innerHTML = `<div class="bg-red-950/60 border border-red-800/60 text-red-300 p-4 rounded-xl text-xs">Erro ao realizar cálculo: ${err.message}</div>`;
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove("opacity-80", "cursor-wait");
      submitBtn.innerHTML = origBtnHtml;
    }
  }
}

function copyWhatsAppMessage() {
  if (!lastFreightCalculationResult || !lastFreightCalculationResult.options || lastFreightCalculationResult.options.length === 0) {
    alert("Realize um cálculo de frete primeiro para copiar o resumo do WhatsApp.");
    return;
  }
  const data = lastFreightCalculationResult;
  let text = `🚚 *COTAÇÃO DE FRETE — MAJ MOBILIDADE*\n`;
  if (data.customer_name) text += `👤 Cliente: ${data.customer_name}\n`;
  text += `📍 Destino: CEP ${data.cep_dest}\n`;
  text += `📦 Carga: ${data.product_name || 'Produtos MAJ'}\n`;
  text += `⚖️ Peso Total: ${data.total_weight_kg.toFixed(1).replace('.', ',')} kg\n\n`;
  text += `*OPÇÕES DE TRANSPORTE:*\n`;
  data.options.forEach((opt, idx) => {
    text += `${idx + 1}. *${opt.carrier_name}*\n`;
    text += `   • Valor: R$ ${opt.total_price.toFixed(2).replace('.', ',')}\n`;
    text += `   • Prazo: ${opt.delivery_days} dia(s) útil(eis)\n`;
  });
  text += `\n_Origem Vitória/ES. Seguro de 1/3 do valor de atacado já incluso na cotação._`;

  navigator.clipboard.writeText(text).then(() => {
    alert("Cotação formatada copiada com sucesso! Você já pode colar na conversa do WhatsApp.");
  }).catch(err => {
    alert("Erro ao copiar para a área de transferência: " + err.message);
  });
}

// Note: PDF generation and archived quote exports are modularized in static/js/freight-quotes.js

