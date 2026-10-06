/**
 * M-One Carrier Details & Rules Modal (static/js/carrier-details-modal.js)
 * Gerencia a navegação por abas, modo de edição, carregamento de dados e filtros de faixas.
 */

let currentModalReportNotes = "";
let currentModalRatesList = [];
let isCarrierEditMode = false;

function switchCarrierModalTab(tabKey) {
  document.querySelectorAll(".carrier-modal-tab").forEach(btn => btn.classList.remove("active"));
  document.querySelectorAll(".carrier-modal-pane").forEach(pane => pane.style.display = "none");

  const btn = document.getElementById(`cTabBtn-${tabKey}`);
  const pane = document.getElementById(`cTabPane-${tabKey}`);
  if (btn) btn.classList.add("active");
  if (pane) pane.style.display = "block";
}

function toggleCarrierEditMode(forceState) {
  isCarrierEditMode = (forceState !== undefined) ? forceState : !isCarrierEditMode;

  const viewFields = document.querySelectorAll(".view-field");
  const editFields = document.querySelectorAll(".edit-field");
  const editBar = document.getElementById("editActionBar");
  const btnText = document.getElementById("btnToggleEditText");
  const btnIcon = document.getElementById("btnToggleEditIcon");

  if (isCarrierEditMode) {
    viewFields.forEach(el => el.style.display = "none");
    editFields.forEach(el => el.style.display = "block");
    if (editBar) editBar.style.display = "flex";
    if (btnText) btnText.innerText = "Modo Visualização";
    if (btnIcon) btnIcon.innerText = "👁️";
  } else {
    viewFields.forEach(el => el.style.display = "");
    editFields.forEach(el => el.style.display = "none");
    if (editBar) editBar.style.display = "none";
    if (btnText) btnText.innerText = "Editar Dados";
    if (btnIcon) btnIcon.innerText = "✏️";
  }
}

async function openTableDetailsModal(tableId) {
  const m = document.getElementById("tableDetailsModal");
  if (!m) return;

  if (m.parentElement !== document.body) {
    document.body.appendChild(m);
  }

  // Reset de Abas e Modo
  switchCarrierModalTab("cadastral");
  toggleCarrierEditMode(false);

  // Loading state
  document.getElementById("tdModalCarrierName").innerText = "Carregando...";
  document.getElementById("tdModalTradeName").innerText = "";
  document.getElementById("tdModalRatesBadge").innerText = "...";
  document.getElementById("tdModalReportText").innerText = "Buscando dados da transportadora...";
  document.getElementById("tdModalRatesTbody").innerHTML = `<tr><td colspan="7" style="padding: 20px; text-align: center; color: var(--text-muted);">Buscando faixas tarifárias...</td></tr>`;

  m.style.removeProperty("display");
  m.style.display = "grid";
  m.style.zIndex = "99999";
  m.classList.add("show");

  try {
    const resp = await fetch(`/freight/tables/${tableId}/details`);
    const data = await resp.json();
    if (!data.success) {
      alert(data.message || "Erro ao carregar detalhes da transportadora.");
      closeTableDetailsModal();
      return;
    }

    const t = data.table;
    document.getElementById("editCarrierId").value = t.carrier_id;
    document.getElementById("editTableId").value = t.table_id;

    // Cabeçalho
    document.getElementById("tdModalCarrierName").innerText = t.carrier_name;
    document.getElementById("tdModalTradeName").innerText = t.trade_name ? `(${t.trade_name})` : "";
    document.getElementById("tdModalTableName").innerText = `Tabela: ${t.table_name}`;
    document.getElementById("tdModalRatesBadge").innerText = `${data.total_rates} faixas cadastradas`;
    document.getElementById("tdModalCreatedAt").innerText = `Importado em: ${t.created_at_fmt || 'Recente'}`;
    document.getElementById("tdModalOriginCity").innerText = `Origem ${t.origin_city || 'Cariacica'}/ES`;
    
    const cubingVal = parseFloat(t.cubing_factor) || 300.0;
    document.getElementById("tdModalCubingFactorBadge").innerText = `📦 Cubagem: ${cubingVal.toFixed(0)} kg/m³`;

    // Aba 1: Ficha Cadastral
    document.getElementById("vTradeName").innerText = t.trade_name || t.carrier_name;
    document.getElementById("editTradeName").value = t.trade_name || t.carrier_name;

    document.getElementById("vCnpj").innerText = t.cnpj || "Não informado";
    document.getElementById("editCnpj").value = t.cnpj || "";

    document.getElementById("vPaymentTerms").innerText = t.payment_terms || "Semanal com mais 14 dias";
    document.getElementById("editPaymentTerms").value = t.payment_terms || "";

    document.getElementById("vAddress").innerText = t.address || "Não cadastrado";
    document.getElementById("editAddress").value = t.address || "";

    document.getElementById("vCity").innerText = t.carrier_city || "Cariacica";
    document.getElementById("editCity").value = t.carrier_city || "";

    document.getElementById("vUf").innerText = t.carrier_uf || "ES";
    document.getElementById("editUf").value = t.carrier_uf || "ES";

    document.getElementById("vPhone").innerText = t.phone || "Não informado";
    document.getElementById("editPhone").value = t.phone || "";
    if (t.phone) {
      document.getElementById("linkPhoneCall").href = `tel:${t.phone.replace(/\D/g, '')}`;
      document.getElementById("linkPhoneCall").style.display = "inline-flex";
    } else {
      document.getElementById("linkPhoneCall").style.display = "none";
    }

    document.getElementById("vWebsite").innerText = t.website || "Não informado";
    document.getElementById("editWebsite").value = t.website || "";
    if (t.website) {
      document.getElementById("linkWebsiteOpen").href = t.website.startsWith('http') ? t.website : `https://${t.website}`;
      document.getElementById("linkWebsiteOpen").style.display = "inline-flex";
    } else {
      document.getElementById("linkWebsiteOpen").style.display = "none";
    }

    document.getElementById("vSalesRepName").innerText = t.sales_rep_name || "Comercial Matriz";
    document.getElementById("editSalesRepName").value = t.sales_rep_name || "";

    // Aba 2: Regras & Taxas
    document.getElementById("vCubingFactor").innerText = cubingVal.toFixed(1);
    document.getElementById("editCubingFactor").value = cubingVal;

    document.getElementById("vOriginCity").innerText = `${t.origin_city || 'Cariacica'} / ES`;
    document.getElementById("editOriginCity").value = t.origin_city || "Cariacica";

    const tasVal = parseFloat(t.tas_fixed) || 0.0;
    document.getElementById("vTasFixed").innerText = tasVal > 0 ? `R$ ${tasVal.toFixed(2).replace('.', ',')}` : 'Isento';
    document.getElementById("editTasFixed").value = tasVal;

    const posVal = parseFloat(t.pos_fixed) || 0.0;
    document.getElementById("vPosFixed").innerText = posVal > 0 ? `R$ ${posVal.toFixed(2).replace('.', ',')}` : 'Isento';
    document.getElementById("editPosFixed").value = posVal;

    const minGrisVal = parseFloat(t.min_gris_value) || 0.0;
    document.getElementById("vMinGris").innerText = minGrisVal > 0 ? `R$ ${minGrisVal.toFixed(2).replace('.', ',')}` : 'R$ 0,00';
    document.getElementById("editMinGris").value = minGrisVal;

    const tecVal = parseFloat(t.tec_percent) || 0.0;
    document.getElementById("vTecPercent").innerText = tecVal > 0 ? `${tecVal.toFixed(2).replace('.', ',')}%` : '0,00%';
    document.getElementById("editTecPercent").value = tecVal;

    const expDays = parseInt(t.expiration_days) || 90;
    document.getElementById("vExpirationDays").innerText = `${expDays} dias sem envios`;
    document.getElementById("editExpirationDays").value = expDays;

    // Aba 4: Parecer IA
    currentModalReportNotes = t.notes || "Tabela importada e auditada com 100% de conformidade operacional.";
    document.getElementById("tdModalReportText").innerText = currentModalReportNotes;

    // Aba 3: Faixas Tarifárias
    currentModalRatesList = data.rates || [];
    renderModalRatesTable(currentModalRatesList);

  } catch (err) {
    document.getElementById("tdModalReportText").innerText = `Erro ao carregar dados: ${err.message}`;
  }
}

function renderModalRatesTable(rates) {
  const tbody = document.getElementById("tdModalRatesTbody");
  document.getElementById("tdModalRatesTableCount").innerText = `${rates.length} regras listadas`;

  if (!rates || rates.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding: 20px; text-align: center; color: var(--text-muted);">Nenhuma faixa tarifária cadastrada nesta tabela.</td></tr>`;
    return;
  }

  let rowsHtml = "";
  rates.forEach(r => {
    const ufText = r.uf ? `<strong style="color: var(--brand-blue);">${r.uf}</strong>` : 'Brasil';
    const cityText = r.city ? ` <span style="color: var(--text-muted); font-size: 0.78rem;">(${r.city})</span>` : '';
    const minW = parseFloat(r.min_weight) || 0;
    const maxW = parseFloat(r.max_weight) || 0;
    const weightRange = `${minW.toFixed(0)} a ${maxW >= 99999 ? '∞' : maxW.toFixed(0)} kg`;
    
    const fixP = parseFloat(r.fixed_price) || 0;
    const fixedPrice = fixP > 0 ? `R$ ${fixP.toFixed(2).replace('.', ',')}` : '-';
    
    const perKg = parseFloat(r.weight_price_per_kg) || 0;
    const perKgText = perKg > 0 ? `R$ ${perKg.toFixed(2).replace('.', ',')}` : '-';

    const toll = parseFloat(r.toll_per_100kg) || 0;
    const tollText = toll > 0 ? `R$ ${toll.toFixed(2).replace('.', ',')}` : '-';

    const adVal = ((parseFloat(r.ad_valorem_percent) || 0) + (parseFloat(r.gris_percent) || 0)).toFixed(2).replace('.', ',');
    const days = r.delivery_days ? `${r.delivery_days} d` : '-';

    rowsHtml += `
      <tr class="modal-rate-row" data-dest="${(r.uf || '').toLowerCase()} ${(r.city || '').toLowerCase()}" style="border-bottom: 1px solid var(--border-subtle); font-size: 0.82rem;">
        <td style="padding: 10px 12px;">${ufText}${cityText}</td>
        <td style="padding: 10px 12px; font-family: monospace; font-size: 0.78rem; color: var(--text-secondary);">${weightRange}</td>
        <td style="padding: 10px 12px; text-align: right; font-weight: 700; color: var(--brand-emerald);">${fixedPrice}</td>
        <td style="padding: 10px 12px; text-align: right; color: var(--text-primary); font-weight: 600;">${perKgText}</td>
        <td style="padding: 10px 12px; text-align: right; color: var(--text-muted);">${tollText}</td>
        <td style="padding: 10px 12px; text-align: center; color: var(--text-muted);">${adVal}%</td>
        <td style="padding: 10px 12px; text-align: center; font-weight: 800; color: var(--text-primary);">${days}</td>
      </tr>
    `;
  });
  tbody.innerHTML = rowsHtml;
}

function filterModalRatesRows(query) {
  const q = (query || "").toLowerCase().trim();
  const rows = document.querySelectorAll(".modal-rate-row");
  let visibleCount = 0;
  rows.forEach(r => {
    const dest = r.getAttribute("data-dest") || "";
    if (!q || dest.includes(q)) {
      r.style.display = "";
      visibleCount++;
    } else {
      r.style.display = "none";
    }
  });
  document.getElementById("tdModalRatesTableCount").innerText = `${visibleCount} de ${rows.length} regras`;
}

async function handleCarrierUpdateSubmit(e) {
  e.preventDefault();
  const carrierId = document.getElementById("editCarrierId").value;
  if (!carrierId) return;

  const btn = document.getElementById("btnSaveCarrierData");
  btn.disabled = true;
  btn.innerText = "Salvando...";

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const formData = new FormData(document.getElementById("carrierEditForm"));
  const payload = Object.fromEntries(formData.entries());
  payload.csrf_token = csrfToken;

  try {
    const resp = await fetch(`/freight/carriers/${carrierId}/update`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken
      },
      body: JSON.stringify(payload)
    });
    const res = await resp.json();
    if (res.success) {
      alert("✅ " + res.message);
      toggleCarrierEditMode(false);
      const tableId = document.getElementById("editTableId").value;
      if (tableId) openTableDetailsModal(tableId);
    } else {
      alert("⚠️ Erro ao salvar: " + res.message);
    }
  } catch (err) {
    alert("Falha de comunicação: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerText = "💾 Salvar Alterações";
  }
}

function copyCarrierField(elId, label) {
  const val = document.getElementById(elId)?.innerText?.trim();
  if (!val) return;
  navigator.clipboard.writeText(val).then(() => {
    alert(`✅ ${label} copiado: ${val}`);
  });
}

function copyTableReportNotes() {
  if (!currentModalReportNotes) return;
  navigator.clipboard.writeText(currentModalReportNotes).then(() => {
    alert("📋 Parecer de auditoria copiado para a área de transferência!");
  }).catch(err => {
    alert("Erro ao copiar: " + err.message);
  });
}

function closeTableDetailsModal() {
  const m = document.getElementById("tableDetailsModal");
  if (m) {
    m.classList.remove("show");
    m.style.display = "none";
  }
}

window.openTableDetailsModal = openTableDetailsModal;
window.closeTableDetailsModal = closeTableDetailsModal;
window.switchCarrierModalTab = switchCarrierModalTab;
window.toggleCarrierEditMode = toggleCarrierEditMode;
window.handleCarrierUpdateSubmit = handleCarrierUpdateSubmit;
window.copyCarrierField = copyCarrierField;
window.copyTableReportNotes = copyTableReportNotes;

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeTableDetailsModal();
});
