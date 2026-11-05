/**
 * M-One Outlet Admin Script (static/js/outlet-admin.js)
 * Gerencia modal de produtos, variações de preço por cor, galeria de fotos e ações rápidas.
 */

let CURRENT_GALLERY = [];
let CURRENT_IMAGE_MAIN = '';
let CURRENT_COLOR_PRICES = [];

function parseCurrencyNum(val) {
  if (val === null || val === undefined || val === '') return 0;
  if (typeof val === 'number') return val;
  let clean = String(val).replace(/[^\d,\.]/g, '').trim();
  if (!clean) return 0;
  if (clean.includes(',') && clean.includes('.')) clean = clean.replace(/\./g, '').replace(',', '.');
  else if (clean.includes(',')) clean = clean.replace(',', '.');
  const num = parseFloat(clean);
  return isNaN(num) ? 0 : num;
}

function formatBrlString(numVal) {
  const n = Number(numVal) || 0;
  return 'R$ ' + n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function computeInstallment12(priceNum) {
  return (!priceNum || priceNum <= 0) ? 0 : Math.round(((priceNum * 1.1013216) / 12) * 100) / 100;
}

function computeInstallment18(priceNum) {
  return (!priceNum || priceNum <= 0) ? 0 : Math.round(((priceNum * 1.1437722) / 18) * 100) / 100;
}

function syncColorPricesHiddenInput() {
  const hidden = document.getElementById('outlet_form_color_prices_json');
  if (hidden) hidden.value = JSON.stringify(CURRENT_COLOR_PRICES);
}

function ensureMainColorVariation(syncTopInputs = false) {
  const activeIndices = [];
  CURRENT_COLOR_PRICES.forEach((cp, idx) => {
    if (cp.active !== false) activeIndices.push(idx);
    else cp.is_main = false;
  });

  if (activeIndices.length === 0) {
    CURRENT_COLOR_PRICES.forEach(cp => { cp.is_main = false; });
    syncColorPricesHiddenInput();
    return;
  }

  let currentMainIdx = CURRENT_COLOR_PRICES.findIndex(cp => cp.active !== false && cp.is_main === true);
  if (currentMainIdx === -1) {
    let minPrice = Infinity;
    let bestIdx = activeIndices[0];
    activeIndices.forEach(idx => {
      const p = parseCurrencyNum(CURRENT_COLOR_PRICES[idx].price);
      if (p > 0 && p < minPrice) {
        minPrice = p;
        bestIdx = idx;
      }
    });
    currentMainIdx = bestIdx;
  }

  CURRENT_COLOR_PRICES.forEach((cp, idx) => { cp.is_main = (idx === currentMainIdx); });

  if (syncTopInputs && currentMainIdx >= 0) {
    const mainCp = CURRENT_COLOR_PRICES[currentMainIdx];
    const pNum = parseCurrencyNum(mainCp.price);
    if (pNum > 0) {
      const p12Num = parseCurrencyNum(mainCp.p12) || computeInstallment12(pNum);
      const p18Num = parseCurrencyNum(mainCp.p18) || computeInstallment18(pNum);
      const outInput = document.getElementById('outlet_form_price_outlet');
      const i12Input = document.getElementById('outlet_form_installment_12');
      const i18Input = document.getElementById('outlet_form_installment_18');
      if (outInput) outInput.value = pNum.toFixed(2);
      if (i12Input) i12Input.value = p12Num.toFixed(2);
      if (i18Input) i18Input.value = p18Num.toFixed(2);
    }
  }
  syncColorPricesHiddenInput();
}

function renderColorPricesEditor() {
  const container = document.getElementById('outlet_color_prices_container');
  syncColorPricesHiddenInput();
  if (!container) return;
  container.innerHTML = '';

  if (!CURRENT_COLOR_PRICES || CURRENT_COLOR_PRICES.length === 0) {
    container.innerHTML = `<div style="padding:10px 12px;border-radius:8px;background:rgba(148,163,184,0.08);color:var(--muted);font-size:0.78rem;text-align:center;">Nenhuma variação de preço por cor cadastrada. Clique em <strong>+ Adicionar Variação</strong> caso tenha preços diferentes por cor.</div>`;
    return;
  }

  CURRENT_COLOR_PRICES.forEach((cp, idx) => {
    const isActive = cp.active !== false;
    const isMain = !!cp.is_main && isActive;
    const row = document.createElement('div');
    row.style.cssText = `display:grid;grid-template-columns:auto auto 1.4fr 1fr auto;gap:8px;align-items:center;padding:8px 10px;border-radius:8px;border:1px solid ${isMain ? 'rgba(0,204,136,0.5)' : 'var(--line,#cbd5e1)'};background:${!isActive ? 'rgba(148,163,184,0.06)' : (isMain ? 'rgba(0,204,136,0.06)' : 'var(--panel2,rgba(255,255,255,0.03))')};opacity:${isActive ? '1' : '0.6'};transition:all 0.15s ease;`;
    const p12Label = cp.p12 || formatBrlString(computeInstallment12(parseCurrencyNum(cp.price)));

    row.innerHTML = `
      <div style="display:flex;align-items:center;" title="${isActive ? 'Desmarque para ocultar esta cor do modal público' : 'Marque para exibir esta cor no modal público'}">
        <input type="checkbox" ${isActive ? 'checked' : ''} onchange="toggleColorVariationActive(${idx}, this.checked)" style="width:18px;height:18px;cursor:pointer;accent-color:#00cc88;">
      </div>
      <div>
        <button type="button" onclick="setMainColorVariation(${idx})" ${!isActive ? 'disabled' : ''} title="${isMain ? 'Preço Principal exibido na vitrine e destaque do modal' : 'Definir como Preço Principal'}" style="padding:4px 8px;border-radius:6px;font-size:0.7rem;font-weight:700;cursor:${isActive ? 'pointer' : 'not-allowed'};white-space:nowrap;border:1px solid ${isMain ? '#00cc88' : 'var(--line,#cbd5e1)'};background:${isMain ? '#00cc88' : 'transparent'};color:${isMain ? '#000' : 'var(--muted)'};">
          ${isMain ? '⭐ Principal' : '☆ Principal'}
        </button>
      </div>
      <div>
        <input type="text" class="form-input" value="${(cp.colors || '').replace(/"/g, '&quot;')}" placeholder="Nome da Cor (ex: Verde Claro)" oninput="updateColorVariationField(${idx}, 'colors', this.value)" style="width:100%;padding:6px 8px;font-size:0.8rem;">
      </div>
      <div>
        <input type="text" class="form-input" value="${(cp.price || '').replace(/"/g, '&quot;')}" placeholder="R$ 7.490,00" onchange="updateColorVariationPrice(${idx}, this.value)" onblur="updateColorVariationPrice(${idx}, this.value)" style="width:100%;padding:6px 8px;font-size:0.8rem;font-weight:700;">
        <small class="muted" style="display:block;font-size:0.68rem;margin-top:2px;">12x ${p12Label}</small>
      </div>
      <div>
        <button type="button" class="btn sm" onclick="removeColorVariationRow(${idx})" title="Remover variação" style="padding:4px 8px;color:#ef4444;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);">✕</button>
      </div>
    `;
    container.appendChild(row);
  });
}

function toggleColorVariationActive(index, isChecked) {
  if (!CURRENT_COLOR_PRICES[index]) return;
  CURRENT_COLOR_PRICES[index].active = !!isChecked;
  ensureMainColorVariation(true);
  renderColorPricesEditor();
}

function setMainColorVariation(index) {
  if (!CURRENT_COLOR_PRICES[index] || CURRENT_COLOR_PRICES[index].active === false) return;
  CURRENT_COLOR_PRICES.forEach((cp, idx) => { cp.is_main = (idx === index); });
  ensureMainColorVariation(true);
  renderColorPricesEditor();
}

function updateColorVariationField(index, field, val) {
  if (!CURRENT_COLOR_PRICES[index]) return;
  CURRENT_COLOR_PRICES[index][field] = val;
  syncColorPricesHiddenInput();
}

function updateColorVariationPrice(index, rawVal) {
  if (!CURRENT_COLOR_PRICES[index]) return;
  const num = parseCurrencyNum(rawVal);
  if (num > 0) {
    CURRENT_COLOR_PRICES[index].price = formatBrlString(num);
    CURRENT_COLOR_PRICES[index].p12 = formatBrlString(computeInstallment12(num));
    CURRENT_COLOR_PRICES[index].p18 = formatBrlString(computeInstallment18(num));
  } else {
    CURRENT_COLOR_PRICES[index].price = rawVal;
  }
  ensureMainColorVariation(true);
  renderColorPricesEditor();
}

function addOutletColorPriceRow() {
  const defaultPriceNum = parseCurrencyNum(document.getElementById('outlet_form_price_outlet')?.value) || 0;
  CURRENT_COLOR_PRICES.push({
    colors: '',
    price: defaultPriceNum > 0 ? formatBrlString(defaultPriceNum) : 'R$ 0,00',
    p12: defaultPriceNum > 0 ? formatBrlString(computeInstallment12(defaultPriceNum)) : 'R$ 0,00',
    p18: defaultPriceNum > 0 ? formatBrlString(computeInstallment18(defaultPriceNum)) : 'R$ 0,00',
    stock: 1,
    active: true,
    is_main: CURRENT_COLOR_PRICES.filter(c => c.active !== false).length === 0
  });
  ensureMainColorVariation(false);
  renderColorPricesEditor();
}

function removeColorVariationRow(index) {
  CURRENT_COLOR_PRICES.splice(index, 1);
  ensureMainColorVariation(true);
  renderColorPricesEditor();
}

function openOutletNewModal() {
  document.getElementById('outlet_form_id').value = '';
  document.getElementById('outlet_form_name').value = '';
  document.getElementById('outlet_form_category').value = 'Scooter Elétrica';
  document.getElementById('outlet_form_price_original').value = '';
  document.getElementById('outlet_form_price_outlet').value = '';
  document.getElementById('outlet_form_installment_12').value = '';
  document.getElementById('outlet_form_installment_18').value = '';
  document.getElementById('outlet_form_stock_qty').value = '1';
  document.getElementById('outlet_form_show_on_demand').checked = false;
  document.getElementById('outlet_form_show_color_prices').checked = true;
  document.getElementById('outlet_form_color').value = '';
  document.getElementById('outlet_form_description').value = '';
  CURRENT_GALLERY = [];
  CURRENT_IMAGE_MAIN = '';
  CURRENT_COLOR_PRICES = [];
  renderGalleryPreview();
  renderColorPricesEditor();
  const title = document.getElementById('outlet_modal_title');
  if (title) title.textContent = 'Novo Produto do Outlet';
  openModal('outletModal');
}

function openOutletEditModal(id) {
  const item = (window.OUTLET_ITEMS_LIST || []).find(i => String(i.id) === String(id));
  if (!item) return;
  document.getElementById('outlet_form_id').value = item.id || '';
  document.getElementById('outlet_form_name').value = item.name || '';
  document.getElementById('outlet_form_category').value = item.category || 'Scooter Elétrica';
  document.getElementById('outlet_form_price_original').value = (item.price_original !== null && item.price_original !== undefined) ? item.price_original : '';
  document.getElementById('outlet_form_price_outlet').value = (item.price_outlet !== null && item.price_outlet !== undefined) ? item.price_outlet : '';
  document.getElementById('outlet_form_installment_12').value = (item.installment_12 !== null && item.installment_12 !== undefined) ? item.installment_12 : '';
  document.getElementById('outlet_form_installment_18').value = (item.installment_18 !== null && item.installment_18 !== undefined) ? item.installment_18 : '';
  document.getElementById('outlet_form_stock_qty').value = (item.stock_qty !== null && item.stock_qty !== undefined) ? item.stock_qty : 1;
  document.getElementById('outlet_form_show_on_demand').checked = !!item.show_on_demand;
  document.getElementById('outlet_form_show_color_prices').checked = (item.show_color_prices !== false);
  document.getElementById('outlet_form_color').value = item.color || '';
  document.getElementById('outlet_form_description').value = item.description || '';

  let specs = item.specs_json || {};
  if (typeof specs === 'string') {
    try { specs = JSON.parse(specs); } catch (e) { specs = {}; }
  }
  const rawCp = Array.isArray(specs.color_prices) ? specs.color_prices : [];
  CURRENT_COLOR_PRICES = rawCp.map(cp => ({ ...cp, active: cp.active !== false, is_main: !!cp.is_main }));
  if (CURRENT_COLOR_PRICES.length > 0 && !CURRENT_COLOR_PRICES.some(cp => cp.is_main && cp.active !== false)) {
    const itemPrice = Number(item.price_outlet) || 0;
    const matchIdx = CURRENT_COLOR_PRICES.findIndex(cp => cp.active !== false && Math.abs(parseCurrencyNum(cp.price) - itemPrice) < 1);
    if (matchIdx >= 0) CURRENT_COLOR_PRICES[matchIdx].is_main = true;
  }
  ensureMainColorVariation(false);
  renderColorPricesEditor();

  CURRENT_IMAGE_MAIN = item.image_main || '';
  let gal = item.images_gallery || [];
  if (typeof gal === 'string') {
    try { gal = JSON.parse(gal); } catch (e) { gal = []; }
  }
  CURRENT_GALLERY = Array.isArray(gal) ? [...gal] : [];
  if (CURRENT_IMAGE_MAIN && !CURRENT_GALLERY.includes(CURRENT_IMAGE_MAIN)) CURRENT_GALLERY.unshift(CURRENT_IMAGE_MAIN);
  renderGalleryPreview();

  const title = document.getElementById('outlet_modal_title');
  if (title) title.textContent = 'Editar Produto: ' + (item.name || '');
  openModal('outletModal');
}

function renderGalleryPreview() {
  const container = document.getElementById('outlet_gallery_preview_container');
  const mainInput = document.getElementById('outlet_form_image_main');
  const galleryInput = document.getElementById('outlet_form_images_gallery');
  if (mainInput) mainInput.value = CURRENT_IMAGE_MAIN;
  if (galleryInput) galleryInput.value = JSON.stringify(CURRENT_GALLERY);
  if (!container) return;
  container.innerHTML = '';

  if (CURRENT_GALLERY.length === 0) {
    container.innerHTML = '<small class="muted" style="grid-column:1 / -1;font-style:italic;">Nenhuma foto adicionada ainda.</small>';
    return;
  }

  CURRENT_GALLERY.forEach((imgUrl, index) => {
    const isMain = (imgUrl === CURRENT_IMAGE_MAIN) || (index === 0 && !CURRENT_IMAGE_MAIN);
    if (isMain && !CURRENT_IMAGE_MAIN) {
      CURRENT_IMAGE_MAIN = imgUrl;
      if (mainInput) mainInput.value = CURRENT_IMAGE_MAIN;
    }
    const card = document.createElement('div');
    card.style.cssText = `position:relative;border-radius:8px;overflow:hidden;border:2px solid ${isMain ? '#00cc88' : 'var(--line,#334155)'};background:rgba(0,0,0,0.3);display:flex;flex-direction:column;align-items:center;padding:4px;`;
    card.innerHTML = `
      <img src="${imgUrl}" style="width:100%;aspect-ratio:4/5;object-fit:cover;object-position:center;border-radius:6px;" onerror="this.src='/static/logo.png'">
      ${isMain ? '<span style="position:absolute;top:6px;left:6px;background:#00cc88;color:#000;font-weight:800;font-size:0.65rem;padding:2px 6px;border-radius:4px;">⭐ CAPA</span>' : ''}
      <div style="display:flex;gap:4px;width:100%;margin-top:4px;">
        ${!isMain ? `<button type="button" class="btn sm" onclick="setAsCoverPhoto(${index})" style="flex:1;padding:2px;font-size:0.65rem;background:rgba(0,204,136,0.15);color:#00cc88;border:1px solid rgba(0,204,136,0.3);">Capa</button>` : ''}
        <button type="button" class="btn sm" onclick="removePhotoFromGallery(${index})" style="padding:2px 6px;font-size:0.65rem;color:#ef4444;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);">✕</button>
      </div>
    `;
    container.appendChild(card);
  });
}

function setAsCoverPhoto(index) {
  if (CURRENT_GALLERY[index]) {
    CURRENT_IMAGE_MAIN = CURRENT_GALLERY[index];
    renderGalleryPreview();
  }
}

function removePhotoFromGallery(index) {
  const removed = CURRENT_GALLERY.splice(index, 1)[0];
  if (CURRENT_IMAGE_MAIN === removed) CURRENT_IMAGE_MAIN = CURRENT_GALLERY.length > 0 ? CURRENT_GALLERY[0] : '';
  renderGalleryPreview();
}

function validateOutletFormPayload() {
  const statusDiv = document.getElementById('upload_status_badge');
  const mainInput = document.getElementById('outlet_form_image_main');
  const galleryInput = document.getElementById('outlet_form_images_gallery');
  if (mainInput) mainInput.value = CURRENT_IMAGE_MAIN || '';
  if (galleryInput) galleryInput.value = JSON.stringify(CURRENT_GALLERY || []);
  syncColorPricesHiddenInput();

  const totalChars = (mainInput?.value || '').length + (galleryInput?.value || '').length;
  const sizeMb = (totalChars * 3 / 4) / (1024 * 1024);
  if (sizeMb > 3.8) {
    alert(`⚠️ O tamanho total da galeria (${sizeMb.toFixed(1)} MB) ultrapassaria o limite máximo de envio da Vercel (4.5 MB). Por favor, remova 1 ou 2 fotos antes de salvar.`);
    if (statusDiv) {
      statusDiv.style.display = 'block';
      statusDiv.style.color = '#ef4444';
      statusDiv.textContent = `⚠️ Tamanho do lote grande (${sizeMb.toFixed(1)} MB / máx 3.8 MB). Remova 1 ou 2 fotos.`;
    }
    return false;
  }
  return true;
}

function handleOutletGalleryUpload(input) {
  const files = input.files;
  const statusDiv = document.getElementById('upload_status_badge');
  const saveBtn = document.getElementById('outlet_save_btn');
  if (!files || files.length === 0) return;

  if (CURRENT_GALLERY.length >= 12) {
    if (statusDiv) {
      statusDiv.style.display = 'block';
      statusDiv.style.color = '#ef4444';
      statusDiv.textContent = '⚠️ Limite máximo de 12 fotos por produto atingido.';
    }
    input.value = '';
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.style.opacity = '0.5';
    saveBtn.style.cursor = 'wait';
    saveBtn.textContent = '⏳ Processando fotos...';
  }
  if (statusDiv) {
    statusDiv.style.display = 'block';
    statusDiv.style.color = '#e5a93b';
    statusDiv.textContent = `Otimizando e comprimindo ${files.length} foto(s)... Aguarde finalizar antes de salvar.`;
  }

  let processedCount = 0;
  const totalFiles = Math.min(files.length, 12 - CURRENT_GALLERY.length);

  Array.from(files).slice(0, totalFiles).forEach(file => {
    const reader = new FileReader();
    reader.onload = function(e) {
      const img = new Image();
      img.onload = function() {
        const canvas = document.createElement('canvas');
        let width = img.width, height = img.height;
        const maxDim = 640;
        if (width > maxDim || height > maxDim) {
          if (width > height) { height = Math.round((height * maxDim) / width); width = maxDim; }
          else { width = Math.round((width * maxDim) / height); height = maxDim; }
        }
        canvas.width = width;
        canvas.height = height;
        canvas.getContext('2d').drawImage(img, 0, 0, width, height);
        const compressedDataUrl = canvas.toDataURL('image/jpeg', 0.50);
        CURRENT_GALLERY.push(compressedDataUrl);
        if (!CURRENT_IMAGE_MAIN) CURRENT_IMAGE_MAIN = compressedDataUrl;

        processedCount++;
        if (processedCount === totalFiles) {
          renderGalleryPreview();
          const totalKb = Math.round(JSON.stringify(CURRENT_GALLERY).length / 1024);
          if (statusDiv) {
            statusDiv.style.color = '#00cc88';
            statusDiv.textContent = `✓ ${CURRENT_GALLERY.length} foto(s) na galeria (Tamanho total: ~${totalKb} KB - Otimizado para Vercel)`;
          }
          if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.style.opacity = '1';
            saveBtn.style.cursor = 'pointer';
            saveBtn.textContent = 'Salvar Produto';
          }
          input.value = '';
        }
      };
      img.onerror = function() {
        processedCount++;
        if (processedCount === totalFiles && saveBtn) {
          saveBtn.disabled = false;
          saveBtn.style.opacity = '1';
          saveBtn.style.cursor = 'pointer';
          saveBtn.textContent = 'Salvar Produto';
        }
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

async function toggleOutletOnDemand(itemId, btn) {
  try {
    const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
    const res = await fetch(`/admin/outlet/toggle-on-demand/${itemId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' }
    });
    const data = await res.json();
    if (data.success) {
      btn.textContent = data.show_on_demand ? '📦 Sob Encomenda' : '🚫 Ocultar';
      btn.style.background = data.show_on_demand ? 'rgba(229, 169, 59, 0.15)' : 'rgba(148, 163, 184, 0.1)';
      btn.style.color = data.show_on_demand ? '#e5a93b' : 'var(--muted)';
      btn.style.borderColor = data.show_on_demand ? 'rgba(229, 169, 59, 0.35)' : 'rgba(148, 163, 184, 0.2)';
    }
  } catch (err) {
    console.error('Erro ao alternar disponibilidade sob encomenda:', err);
  }
}

function maskPhoneInput(val) {
  if (!val) return '';
  let d = val.replace(/\D/g, '');
  if (!d) return '';
  if (d.length <= 2) return '+' + d;
  if (d.length <= 4) return '+' + d.slice(0, 2) + ' (' + d.slice(2);
  if (d.length <= 9) return '+' + d.slice(0, 2) + ' (' + d.slice(2, 4) + ') ' + d.slice(4);
  if (d.length <= 13) return '+' + d.slice(0, 2) + ' (' + d.slice(2, 4) + ') ' + d.slice(4, d.length - 4) + '-' + d.slice(d.length - 4);
  return '+' + d.slice(0, 2) + ' (' + d.slice(2, 4) + ') ' + d.slice(4, 9) + '-' + d.slice(9, 13);
}

function outletAdmin() {
  return {
    searchTable: '',
    matchesSearch(name, category) {
      if (!this.searchTable) return true;
      const q = this.searchTable.toLowerCase();
      return (name || '').toLowerCase().includes(q) || (category || '').toLowerCase().includes(q);
    }
  };
}

Object.assign(window, {
  openOutletNewModal, openNewOutletModal: openOutletNewModal,
  openOutletEditModal, editOutletItem: openOutletEditModal,
  setAsCoverPhoto, removePhotoFromGallery, handleOutletGalleryUpload,
  validateOutletFormPayload, toggleOutletOnDemand, maskPhoneInput, outletAdmin,
  toggleColorVariationActive, setMainColorVariation,
  updateColorVariationField, updateColorVariationPrice,
  addOutletColorPriceRow, removeColorVariationRow
});
