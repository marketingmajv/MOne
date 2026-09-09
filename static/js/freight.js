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
  card.className = "bg-[#080E19] border border-[#1E2F52] rounded-lg p-3 space-y-2.5 transition-all product-item-card";

  card.innerHTML = `
    <div class="flex items-center justify-between gap-2">
      <div class="flex-1 min-w-0">
        <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Modelo do Veículo / Produto</label>
        <select class="product-select w-full bg-[#0D1628] border border-[#1E2F52] rounded-md px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-[#0070F3] transition-all min-w-0" onchange="onProductSelectChange('${rowId}')">
          ${optionsHtml}
        </select>
      </div>
      <div class="pt-4 flex-shrink-0">
        <button type="button" class="w-7 h-7 rounded-md bg-red-950/20 hover:bg-red-900/40 text-red-400 border border-red-800/30 flex items-center justify-center transition-all icon-svg" onclick="removeProductRow('${rowId}')" title="Remover item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-6 gap-2 items-end text-xs">
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-slate-400 mb-1">Qtd</label>
        <input type="number" min="1" value="1" class="product-qty w-full bg-[#0D1628] border border-[#1E2F52] text-slate-200 rounded-md text-center text-xs py-1.5 focus:outline-none focus:border-[#0070F3] min-w-0" onchange="updateTotalsSummary()" onkeyup="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-slate-400 mb-1">Peso (kg)</label>
        <input type="number" step="0.1" value="" placeholder="kg" class="product-weight w-full bg-[#0D1628] border border-[#1E2F52] text-slate-200 rounded-md text-center text-xs py-1.5 focus:outline-none focus:border-[#0070F3] min-w-0" onchange="updateTotalsSummary()" onkeyup="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-slate-400 mb-1">Compr. (cm)</label>
        <input type="number" value="" placeholder="C" class="product-length w-full bg-[#0D1628] border border-[#1E2F52] text-slate-200 rounded-md text-center text-xs py-1.5 focus:outline-none focus:border-[#0070F3] min-w-0" onchange="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-slate-400 mb-1">Largura (cm)</label>
        <input type="number" value="" placeholder="L" class="product-width w-full bg-[#0D1628] border border-[#1E2F52] text-slate-200 rounded-md text-center text-xs py-1.5 focus:outline-none focus:border-[#0070F3] min-w-0" onchange="updateTotalsSummary()">
      </div>
      <div class="min-w-0">
        <label class="block text-[10px] font-semibold text-slate-400 mb-1">Altura (cm)</label>
        <input type="number" value="" placeholder="A" class="product-height w-full bg-[#0D1628] border border-[#1E2F52] text-slate-200 rounded-md text-center text-xs py-1.5 focus:outline-none focus:border-[#0070F3] min-w-0" onchange="updateTotalsSummary()">
      </div>
      <div class="min-w-0 col-span-2 sm:col-span-1 text-right">
        <label class="block text-[10px] font-semibold text-slate-400 mb-1">1/3 Atacado</label>
        <span class="product-onethird-display text-xs font-bold text-[#38BDF8] block py-1">R$ 0,00</span>
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
  
  if (emptyState) emptyState.classList.add("hidden");
  if (optionsList) {
    optionsList.classList.remove("hidden");
    optionsList.innerHTML = `
      <div class="p-6 text-center text-slate-400 bg-[#111111] rounded-xl border border-[#222222]">
        <div class="inline-block animate-spin text-2xl mb-2 text-[#0070F3]">⚡</div>
        <p class="text-xs font-semibold text-white">Calculando e arquivando cotação com seguro de 1/3 do atacado...</p>
        <small class="text-[10px] text-slate-500 block mt-0.5">Comparando regras entre todas as transportadoras ativas</small>
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
      <div class="bg-[#111111] p-3.5 rounded-xl border border-[#222222] text-xs space-y-1.5 mb-4 shadow-md">
        <div class="flex justify-between text-slate-400"><span>Carga:</span> <strong class="text-white font-semibold">${data.product_name}</strong></div>
        <div class="flex justify-between text-slate-400"><span>Total de Volumes:</span> <strong class="text-[#38BDF8] font-semibold">${data.total_volumes_count || (data.items ? data.items.reduce((acc, it) => acc + (it.qty || 1), 0) : 1)} vol(s)</strong></div>
        <div class="flex justify-between text-slate-400"><span>Peso Total Físico:</span> <strong class="text-white font-semibold">${data.total_weight_kg.toFixed(1).replace('.', ',')} kg</strong></div>
        <div class="flex justify-between text-slate-400"><span>Base Seguro (1/3 Atacado):</span> <strong class="text-[#00E599] font-bold">R$ ${data.insurance_base_value.toFixed(2).replace('.', ',')}</strong></div>
      </div>
    `;

    // Ordenação por menor preço
    data.options.sort((a, b) => a.total_price - b.total_price || a.delivery_days - b.delivery_days);

    data.options.forEach((opt, idx) => {
      let isCheapest = opt.badges && opt.badges.some(b => b.includes("Barato"));
      let isFastest = opt.badges && opt.badges.some(b => b.includes("Rápido"));

      let cardBorderClass = "border-[#222222] bg-[#111111] hover:border-slate-700";
      let badgeHtml = "";

      if (isCheapest) {
        cardBorderClass = "border-2 border-[#00E599] bg-[#00E599]/5 shadow-md shadow-emerald-500/10";
        badgeHtml += `<span class="bg-[#00E599] text-[#000000] text-[10px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">🏆 MAIS ECONÔMICA</span>`;
      } else if (isFastest) {
        cardBorderClass = "border-2 border-[#0070F3] bg-[#0070F3]/5 shadow-md shadow-blue-500/10";
        badgeHtml += `<span class="bg-[#0070F3] text-white text-[10px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">⚡ MAIS RÁPIDA</span>`;
      }

      html += `
        <div class="border ${cardBorderClass} transition-all p-4 rounded-xl flex flex-wrap justify-between items-center gap-3">
          <div class="flex items-start gap-3">
            <span class="bg-[#1E293B] text-[#38BDF8] border border-[#334155] text-xs font-mono font-bold w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">${idx + 1}º</span>
            <div>
              <div class="flex items-center flex-wrap gap-2">
                <strong class="text-sm font-extrabold text-white">${opt.carrier_name}</strong>
                ${badgeHtml}
              </div>
              <p class="text-[11px] text-slate-400 mt-1">
                Tabela: <span class="text-slate-300 font-medium">${opt.table_name}</span> | Prazo de Entrega: <strong class="text-white font-bold">${opt.delivery_days} dia(s) útil(eis)</strong>
              </p>
              ${opt.insurance_cost > 0 ? `<small class="text-[10px] text-slate-500 block mt-0.5">Seguro incluso (1/3 Atacado): R$ ${opt.insurance_cost.toFixed(2).replace('.', ',')}</small>` : ''}
            </div>
          </div>
          <div class="flex items-center gap-3.5">
            <div class="text-right">
              <span class="text-xl font-black ${isCheapest ? 'text-[#00E599]' : 'text-[#0070F3]'} block">R$ ${opt.total_price.toFixed(2).replace('.', ',')}</span>
              <small class="text-[10px] text-slate-500 block uppercase font-bold tracking-wider">VALOR TOTAL DE FRETE</small>
            </div>
            <button type="button" onclick="exportFreightPDF(${idx})" class="bg-[#0070F3] hover:bg-[#0068D6] text-white px-3 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 shadow-sm hover:scale-105" title="Exportar PDF desta cotação com a transportadora ${opt.carrier_name}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
              <span>PDF</span>
            </button>
          </div>
        </div>
      `;
    });

    optionsList.innerHTML = html;
  } catch (err) {
    if (optionsList) {
      optionsList.innerHTML = `<div class="bg-red-950/60 border border-red-800/60 text-red-300 p-4 rounded-xl text-xs">Erro ao realizar cálculo: ${err.message}</div>`;
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

function exportFreightPDF(selectedIdx = null) {
  if (!lastFreightCalculationResult || !lastFreightCalculationResult.options || lastFreightCalculationResult.options.length === 0) {
    alert("Realize um cálculo de frete primeiro para exportar o PDF da cotação.");
    return;
  }

  const data = lastFreightCalculationResult;
  const today = new Date();
  const dateStr = today.toLocaleDateString("pt-BR", { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  const refNum = data.quote_number || `COT-${today.getFullYear()}${(today.getMonth()+1).toString().padStart(2,'0')}${today.getDate().toString().padStart(2,'0')}-${Math.floor(1000 + Math.random() * 9000)}`;

  let selectedBannerHtml = "";
  if (selectedIdx !== null && data.options[selectedIdx]) {
    const s = data.options[selectedIdx];
    selectedBannerHtml = `
      <div style="background: #EFF6FF; border: 2px solid #0070F3; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;">
        <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; letter-spacing: 0.5px;">✓ TRANSPORTADORA SELECIONADA PELO VENDEDOR</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
          <div>
            <strong style="font-size: 16px; color: #0F172A;">${s.carrier_name}</strong>
            <span style="font-size: 12px; color: #475569; margin-left: 8px;">(Tabela: ${s.table_name})</span>
            <div style="font-size: 11px; color: #64748B;">Prazo Estimado: <strong>${s.delivery_days} dia(s) útil(eis)</strong></div>
          </div>
          <div style="text-align: right;">
            <strong style="font-size: 20px; color: #0070F3;">R$ ${s.total_price.toFixed(2).replace('.', ',')}</strong>
            <div style="font-size: 10px; color: #64748B; font-weight: 700;">VALOR TOTAL DE FRETE COM SEGURO</div>
          </div>
        </div>
      </div>
    `;
  }

  let itemsHtml = "";
  let totalVolCount = 0;
  let grandTotalWeight = 0;
  let grandTotalCubicM3 = 0;

  const rawItems = data.items && data.items.length > 0 ? data.items : [];

  if (rawItems.length > 0) {
    let volIndex = 0;
    rawItems.forEach((item) => {
      const qty = parseInt(item.qty || 1);
      const weight = parseFloat(item.weight_kg || 0);
      const l = parseFloat(item.length_cm || 0);
      const w = parseFloat(item.width_cm || 0);
      const h = parseFloat(item.height_cm || 0);
      const volM3 = (l > 0 && w > 0 && h > 0) ? ((l * w * h) / 1000000.0) : 0;
      
      const dimStr = (l > 0 || w > 0 || h > 0) ? `${l} x ${w} x ${h} cm` : '-';
      const volStr = volM3 > 0 ? `${volM3.toFixed(3).replace('.', ',')} m³` : '-';

      for (let i = 1; i <= qty; i++) {
        volIndex++;
        itemsHtml += `
          <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. ${volIndex}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">${item.name || 'Produto MAJ'} ${qty > 1 ? `<span style="font-size: 10px; color: #64748B;">(Unidade ${i} de ${qty})</span>` : ''}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${weight > 0 ? weight.toFixed(1).replace('.', ',') + ' kg' : '-'}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${dimStr}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center; font-weight: 600;">${volStr}</td>
          </tr>
        `;
        grandTotalWeight += weight;
        grandTotalCubicM3 += volM3;
      }
      totalVolCount += qty;
    });

    itemsHtml += `
      <tr style="background-color: #F8FAFC; font-weight: bold;">
        <td colspan="2" style="padding: 10px 12px; border-top: 2px solid #CBD5E1; color: #0F172A;">
          TOTAL DA CARGA: ${totalVolCount} VOLUME(S)
        </td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${totalVolCount} ud</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${grandTotalWeight.toFixed(1).replace('.', ',')} kg</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #64748B;">-</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0070F3;">${grandTotalCubicM3 > 0 ? grandTotalCubicM3.toFixed(3).replace('.', ',') + ' m³' : '-'}</td>
      </tr>
    `;
  } else {
    itemsHtml = `
      <tr>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. 1</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">${data.product_name || 'Produtos MAJ'}</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${(data.total_weight_kg || 0).toFixed(1).replace('.', ',')} kg</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
      </tr>
    `;
  }

  let optionsHtml = "";
  data.options.forEach((opt, idx) => {
    const isSelected = (selectedIdx === idx);
    const isCheap = opt.badges && opt.badges.some(b => b.includes("Barato"));
    const isFast = opt.badges && opt.badges.some(b => b.includes("Rápido"));
    let badgeText = "";
    if (isSelected) badgeText += `<span style="background: #0070F3; color: #FFFFFF; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px; margin-left: 6px;">SELECIONADA</span>`;
    if (isCheap) badgeText += `<span style="background: #DCFCE7; color: #166534; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px; margin-left: 6px;">MAIS ECONÔMICA</span>`;
    if (isFast) badgeText += `<span style="background: #DBEAFE; color: #1E40AF; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px; margin-left: 6px;">MAIS RÁPIDA</span>`;

    optionsHtml += `
      <tr style="${isSelected ? 'background-color: #EFF6FF; font-weight: bold;' : (isCheap ? 'background-color: #F0FDF4;' : '')}">
        <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0;">
          <strong style="color: #0F172A; font-size: 13px;">${opt.carrier_name}</strong> ${badgeText}
          <div style="font-size: 11px; color: #64748B; margin-top: 2px;">Tabela: ${opt.table_name}</div>
        </td>
        <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; text-align: center; font-weight: 600; color: #1E293B;">
          ${opt.delivery_days} dia(s) útil(eis)
        </td>
        <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; text-align: right;">
          <strong style="font-size: 15px; color: ${isSelected ? '#0070F3' : '#0F172A'};">R$ ${opt.total_price.toFixed(2).replace('.', ',')}</strong>
        </td>
      </tr>
    `;
  });

  const pdfWin = window.open("", "_blank");
  if (!pdfWin) {
    alert("Permita pop-ups no navegador para visualizar e imprimir o PDF da cotação.");
    return;
  }

  pdfWin.document.write(`
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Cotação de Frete — MAJ Mobilidade (${refNum})</title>
      <style>
        @page { size: A4; margin: 15mm; }
        body { font-family: 'Segoe UI', Arial, sans-serif; color: #1E293B; background: #FFF; margin: 0; padding: 20px; font-size: 12px; line-height: 1.5; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0070F3; padding-bottom: 15px; margin-bottom: 20px; }
        .brand-title { font-size: 22px; font-weight: 900; color: #0070F3; letter-spacing: -0.5px; }
        .brand-sub { font-size: 11px; color: #64748B; font-weight: 600; text-transform: uppercase; }
        .doc-info { text-align: right; font-size: 11px; color: #64748B; }
        .doc-info strong { color: #0F172A; font-size: 12px; }
        .section-box { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; margin-bottom: 18px; }
        .section-title { font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; margin-bottom: 8px; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; letter-spacing: 0.5px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 6px; }
        th { background: #F1F5F9; color: #475569; font-size: 10px; font-weight: 800; text-transform: uppercase; padding: 8px 12px; text-align: left; border-bottom: 2px solid #CBD5E1; }
        .footer { margin-top: 30px; border-top: 1px solid #E2E8F0; padding-top: 12px; font-size: 10px; color: #94A3B8; text-align: center; }
        @media print {
          body { padding: 0; }
          .no-print { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="no-print" style="margin-bottom: 20px; text-align: right;">
        <button onclick="window.print()" style="background: #0070F3; color: white; border: none; padding: 9px 18px; border-radius: 6px; font-weight: bold; cursor: pointer;">🖨️ Imprimir / Salvar como PDF</button>
      </div>

      <div class="header">
        <div>
          <div class="brand-title">MAJ MOBILIDADE</div>
          <div class="brand-sub">M-One Operating System — Cotação Oficial de Frete</div>
        </div>
        <div class="doc-info">
          <strong>Cotação Nº: ${refNum}</strong><br>
          Data: ${dateStr}<br>
          Origem: Vitória / ES (29045-660)
        </div>
      </div>

      ${selectedBannerHtml}

      <div class="section-box grid-2">
        <div>
          <div class="section-title">Dados do Cliente & Destino</div>
          <strong>Cliente:</strong> ${data.customer_name || 'Não informado'}<br>
          <strong>CEP Destino:</strong> ${data.cep_dest || '-'}<br>
          <strong>Rota:</strong> Vitória/ES ➔ Destino
        </div>
        <div>
          <div class="section-title">Resumo da Carga & Seguro</div>
          <strong>Total de Volumes:</strong> ${totalVolCount || 1} volume(s)<br>
          <strong>Peso Total Físico:</strong> ${data.total_weight_kg.toFixed(1).replace('.', ',')} kg<br>
          <strong>Base de Seguro (1/3 Atacado):</strong> R$ ${data.insurance_base_value.toFixed(2).replace('.', ',')}<br>
          <strong>Regra:</strong> 1/3 do valor de atacado dos produtos
        </div>
      </div>

      <div style="margin-bottom: 20px;">
        <div class="section-title">Discriminação Individual dos Volumes & Produtos</div>
        <table>
          <thead>
            <tr>
              <th style="text-align: center; width: 70px;">Volume</th>
              <th>Produto / Veículo</th>
              <th style="text-align: center;">Qtd</th>
              <th style="text-align: center;">Peso Unit.</th>
              <th style="text-align: center;">Dimensões (C x L x A)</th>
              <th style="text-align: center;">Cubagem Unit.</th>
            </tr>
          </thead>
          <tbody>
            ${itemsHtml}
          </tbody>
        </table>
      </div>

      <div style="margin-bottom: 20px;">
        <div class="section-title">Opções Disponíveis de Transporte</div>
        <table>
          <thead>
            <tr>
              <th>Transportadora / Tabela</th>
              <th style="text-align: center;">Prazo Estimado</th>
              <th style="text-align: right;">Valor Total (Frete + Seguro)</th>
            </tr>
          </thead>
          <tbody>
            ${optionsHtml}
          </tbody>
        </table>
      </div>

      <div class="footer">
        MAJ Mobilidade — Sistema Operacional M-One. Esta cotação é válida por 7 dias a contar da data de emissão.<br>
        Origem Vitória/ES. Todos os valores incluem taxas operacionais e seguro de transporte regulamentar.
      </div>

      <script>
        window.onload = function() { setTimeout(function() { window.print(); }, 400); };
      <\/script>
    </body>
    </html>
  `);
  pdfWin.document.close();
}

function exportArchivedQuotePDF(refNum, customerName, cepDest, address, carrier, price, createdAt, itemsRaw = "") {
  let items = [];
  if (itemsRaw) {
    try {
      items = typeof itemsRaw === "string" ? JSON.parse(itemsRaw) : itemsRaw;
    } catch (e) {
      items = [];
    }
  }

  let itemsHtml = "";
  let totalVolCount = 0;
  let grandTotalWeight = 0;
  let grandTotalCubicM3 = 0;

  if (Array.isArray(items) && items.length > 0) {
    let volIndex = 0;
    items.forEach((item) => {
      const qty = parseInt(item.qty || 1);
      const weight = parseFloat(item.weight_kg || 0);
      const l = parseFloat(item.length_cm || 0);
      const w = parseFloat(item.width_cm || 0);
      const h = parseFloat(item.height_cm || 0);
      const volM3 = (l > 0 && w > 0 && h > 0) ? ((l * w * h) / 1000000.0) : 0;
      
      const dimStr = (l > 0 || w > 0 || h > 0) ? `${l} x ${w} x ${h} cm` : '-';
      const volStr = volM3 > 0 ? `${volM3.toFixed(3).replace('.', ',')} m³` : '-';

      for (let i = 1; i <= qty; i++) {
        volIndex++;
        itemsHtml += `
          <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. ${volIndex}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">${item.name || 'Produto MAJ'} ${qty > 1 ? `<span style="font-size: 10px; color: #64748B;">(Unidade ${i} de ${qty})</span>` : ''}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${weight > 0 ? weight.toFixed(1).replace('.', ',') + ' kg' : '-'}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${dimStr}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center; font-weight: 600;">${volStr}</td>
          </tr>
        `;
        grandTotalWeight += weight;
        grandTotalCubicM3 += volM3;
      }
      totalVolCount += qty;
    });

    itemsHtml += `
      <tr style="background-color: #F8FAFC; font-weight: bold;">
        <td colspan="2" style="padding: 10px 12px; border-top: 2px solid #CBD5E1; color: #0F172A;">
          TOTAL DA CARGA: ${totalVolCount} VOLUME(S)
        </td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${totalVolCount} ud</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${grandTotalWeight.toFixed(1).replace('.', ',')} kg</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #64748B;">-</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0070F3;">${grandTotalCubicM3 > 0 ? grandTotalCubicM3.toFixed(3).replace('.', ',') + ' m³' : '-'}</td>
      </tr>
    `;
  } else {
    itemsHtml = `
      <tr>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. 1</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">Carga Arquivada MAJ</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
      </tr>
    `;
  }

  const pdfHtml = `
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Cotação Arquivada — MAJ Mobilidade (${refNum})</title>
      <style>
        @page { size: A4; margin: 15mm; }
        body { font-family: 'Segoe UI', Arial, sans-serif; color: #1E293B; background: #FFF; margin: 0; padding: 20px; font-size: 12px; line-height: 1.5; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0070F3; padding-bottom: 15px; margin-bottom: 20px; }
        .brand-title { font-size: 22px; font-weight: 900; color: #0070F3; letter-spacing: -0.5px; }
        .brand-sub { font-size: 11px; color: #64748B; font-weight: 600; text-transform: uppercase; }
        .doc-info { text-align: right; font-size: 11px; color: #64748B; }
        .doc-info strong { color: #0F172A; font-size: 12px; }
        .section-box { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; margin-bottom: 18px; }
        .section-title { font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; margin-bottom: 8px; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; letter-spacing: 0.5px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 6px; }
        th { background: #F1F5F9; color: #475569; font-size: 10px; font-weight: 800; text-transform: uppercase; padding: 8px 12px; text-align: left; border-bottom: 2px solid #CBD5E1; }
        .footer { margin-top: 30px; border-top: 1px solid #E2E8F0; padding-top: 12px; font-size: 10px; color: #94A3B8; text-align: center; }
        @media print {
          body { padding: 0; }
          .no-print { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="no-print" style="margin-bottom: 20px; text-align: right;">
        <button onclick="window.print()" style="background: #0070F3; color: white; border: none; padding: 9px 18px; border-radius: 6px; font-weight: bold; cursor: pointer;">🖨️ Imprimir / Salvar como PDF</button>
      </div>

      <div class="header">
        <div>
          <div class="brand-title">MAJ MOBILIDADE</div>
          <div class="brand-sub">M-One Operating System — Cotação Arquivada de Frete</div>
        </div>
        <div class="doc-info">
          <strong>Cotação Nº: ${refNum}</strong><br>
          Data: ${createdAt}<br>
          Origem: Vitória / ES (29045-660)
        </div>
      </div>

      <div style="background: #EFF6FF; border: 2px solid #0070F3; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;">
        <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; letter-spacing: 0.5px;">✓ TRANSPORTADORA SELECIONADA</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
          <div>
            <strong style="font-size: 16px; color: #0F172A;">${carrier || 'Transportadora Selecionada'}</strong>
          </div>
          <div style="text-align: right;">
            <strong style="font-size: 20px; color: #0070F3;">R$ ${parseFloat(price || 0).toFixed(2).replace('.', ',')}</strong>
            <div style="font-size: 10px; color: #64748B; font-weight: 700;">VALOR TOTAL DE FRETE ARQUIVADO</div>
          </div>
        </div>
      </div>

      <div class="section-box grid-2">
        <div>
          <div class="section-title">Dados do Cliente & Destino</div>
          <strong>Cliente:</strong> ${customerName || 'Não informado'}<br>
          <strong>CEP / Endereço:</strong> ${address || cepDest || '-'}<br>
          <strong>Rota:</strong> Vitória/ES ➔ Destino
        </div>
        <div>
          <div class="section-title">Resumo da Carga & Seguro</div>
          <strong>Total de Volumes:</strong> ${totalVolCount || 1} volume(s)<br>
          <strong>Regra de Seguro:</strong> 1/3 do valor de atacado dos produtos
        </div>
      </div>

      <div style="margin-bottom: 20px;">
        <div class="section-title">Discriminação Individual dos Volumes & Produtos</div>
        <table>
          <thead>
            <tr>
              <th style="text-align: center; width: 70px;">Volume</th>
              <th>Produto / Veículo</th>
              <th style="text-align: center;">Qtd</th>
              <th style="text-align: center;">Peso Unit.</th>
              <th style="text-align: center;">Dimensões (C x L x A)</th>
              <th style="text-align: center;">Cubagem Unit.</th>
            </tr>
          </thead>
          <tbody>
            ${itemsHtml}
          </tbody>
        </table>
      </div>

      <div class="footer">
        MAJ Mobilidade — Sistema Operacional M-One. Cotação arquivada no histórico de fretes.<br>
        Origem Vitória/ES. Todos os valores incluem taxas operacionais e seguro de transporte regulamentar.
      </div>

      <script>window.onload = function() { setTimeout(function() { window.print(); }, 400); };<\/script>
    </body>
    </html>
  `;
  const printWindow = window.open("", "_blank", "width=850,height=950");
  if (printWindow) {
    printWindow.document.write(pdfHtml);
    printWindow.document.close();
  }
}

