/*
 * M-One Sales Operations & AI Document Verification (static/js/sales.js)
 */

let cameraStream = null;
let currentFile = null;
let currentBase64 = null;

let chassisDebounceTimer = null;
let danfeCameraStream = null;
let termCameraStream = null;
let chassisPhotoCameraStream = null;
let warrantyTermCameraStream = null;
let signedStubCameraStream = null;

let currentDanfeFile = null;
let currentDanfeBase64 = null;
let currentChassisPhotoFile = null;
let currentChassisPhotoBase64 = null;
let currentWarrantyTermFile = null;
let currentWarrantyTermBase64 = null;
let currentSignedStubFile = null;
let currentSignedStubBase64 = null;
let termCapturedPhotos = [];

document.addEventListener('DOMContentLoaded', () => {
  if (typeof addPaymentRow === 'function') {
    addPaymentRow('Pix', 'Sicoob');
    addPaymentRow('Link', 'Fonton Pay');
  }
});

function filterSalesTable() {
  const q = document.getElementById('salesSearch').value.toLowerCase();
  const rows = document.querySelectorAll('#salesTable tbody tr');
  rows.forEach(r => {
    const text = r.textContent.toLowerCase();
    r.style.display = text.includes(q) ? '' : 'none';
  });
}

async function fetchFromBling() {
  const input = document.getElementById('blingOrderInput');
  const num = input.value.trim();
  if (!num) {
    alert('Por favor, digite o número do Pedido Bling antes de buscar.');
    input.focus();
    return;
  }
  const btn = document.getElementById('blingSearchBtn');
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = 'Buscando...';

  try {
    const res = await fetch(`/api/bling/order/${encodeURIComponent(num)}`);
    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = originalText;

    if (!data.found) {
      alert(data.message || 'Pedido não localizado no Bling.');
      return;
    }

    if (data.customer) {
      document.getElementById('customerInput').value = data.customer;
    }
    if (data.invoice_number) {
      document.getElementById('invoiceNumberInput').value = data.invoice_number;
    }
    if (data.sold_at) {
      document.getElementById('soldAtInput').value = data.sold_at;
    }
    if (data.total_value) {
      document.getElementById('totalValueInput').value = data.total_value.toFixed(2);
    }
    if (data.vehicle_model) {
      document.getElementById('vehicleModelInput').value = data.vehicle_model;
    } else if (data.items && data.items.length) {
      document.getElementById('vehicleModelInput').value = data.items.map(i => i.descricao).join(', ');
    }
    if (data.notes) {
      const notesEl = document.querySelector('#saleForm textarea[name="notes"]');
      if (notesEl && !notesEl.value) {
        notesEl.value = data.notes;
      }
    }

    let itemsMsg = '';
    if (data.items && data.items.length) {
      itemsMsg = '\n\nItens do pedido:\n' + data.items.map(i => `• ${i.quantidade}x ${i.descricao}`).join('\n');
    }
    alert(`✓ Pedido #${data.order_number} encontrado no Bling!\n\nCliente: ${data.customer}\nNota Fiscal: ${data.invoice_number || 'Ainda não emitida'}\nModelo: ${data.vehicle_model || 'Identificado no item'}\nValor Total: R$ ${data.total_value.toFixed(2)}${itemsMsg}`);

  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = originalText;
    alert('Erro ao consultar API do Bling: ' + err.message + '\nVerifique se o M-One está conectado ao Bling na aba Integrações.');
  }
}

function onChannelChange() {
  const ch = document.getElementById('channelInput').value;
  const warrantySec = document.getElementById('warrantyTermSection');
  const stubSec = document.getElementById('signedStubSection');

  if (ch === 'varejo') {
    warrantySec.style.display = 'block';
    stubSec.style.display = 'none';
  } else {
    warrantySec.style.display = 'none';
    stubSec.style.display = 'block';
  }
  onChassisInputChange();
}

function resetAiValidation() {
  document.getElementById('aiChassisVerified').value = '0';
  document.getElementById('aiExtractedChassis').value = '';
  const saveBtn = document.getElementById('saveSaleBtn');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '🔒 Anexe os comprovantes para liberar';
    saveBtn.classList.remove('good-btn');
  }
  
  const badge = document.getElementById('aiBadge');
  if (badge) {
    badge.className = 'badge muted';
    badge.innerText = 'Aguardando Documento';
  }

  const statusBox = document.getElementById('aiStatusBox');
  if (statusBox) {
    statusBox.style.display = 'none';
    statusBox.innerHTML = '';
  }
}

function hasAnyDocumentAttached() {
  const termFiles = document.getElementById('termFileInput')?.files;
  return currentDanfeFile || currentDanfeBase64 || currentChassisPhotoFile || currentChassisPhotoBase64 || currentWarrantyTermFile || currentWarrantyTermBase64 || currentSignedStubFile || currentSignedStubBase64 || (termFiles && termFiles.length > 0) || (termCapturedPhotos && termCapturedPhotos.length > 0);
}

function onChassisInputChange() {
  resetAiValidation();

  const chassisVal = document.getElementById('chassisInput').value.trim();
  const hasDoc = hasAnyDocumentAttached();

  if (hasDoc && chassisVal) {
    if (chassisDebounceTimer) clearTimeout(chassisDebounceTimer);
    chassisDebounceTimer = setTimeout(() => {
      runChassisAiVerification();
    }, 600);
  } else if (hasDoc && !chassisVal) {
    const badge = document.getElementById('aiBadge');
    if (badge) {
      badge.className = 'badge warning';
      badge.innerText = 'Digite o Chassi Acima';
    }

    const statusBox = document.getElementById('aiStatusBox');
    if (statusBox) {
      statusBox.style.display = 'block';
      statusBox.style.background = '#1b232c';
      statusBox.style.borderColor = '#384756';
      statusBox.style.color = '#e2ecf7';
      statusBox.innerHTML = '📄 <strong>Comprovante anexado!</strong> Digite ou cole o número do chassi no campo de chassis acima para a IA realizar a triangulação dos documentos.';
    }
  }
}

/* ================= DANFE LOGIC ================= */
function onDanfeFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  currentDanfeFile = file;
  currentDanfeBase64 = null;
  document.getElementById('danfeCapturedImage').value = '';

  const previewBox = document.getElementById('danfePreviewBox');
  const previewImg = document.getElementById('danfePreviewImg');
  const previewLabel = document.getElementById('danfePreviewLabel');

  if (file.type.startsWith('image/')) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewImg.style.display = 'inline-block';
      previewLabel.innerText = file.name;
      previewBox.style.display = 'block';
    };
    reader.readAsDataURL(file);
  } else {
    previewImg.style.display = 'none';
    previewLabel.innerText = '📄 Documento PDF: ' + file.name;
    previewBox.style.display = 'block';
  }

  onChassisInputChange();
}

async function toggleDanfeCamera() {
  const box = document.getElementById('danfeCameraBox');
  if (box.style.display === 'none') {
    try {
      danfeCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      document.getElementById('danfeVideo').srcObject = danfeCameraStream;
      box.style.display = 'block';
    } catch (err) {
      alert('Não foi possível acessar a câmera para DANFE: ' + err.message);
    }
  } else {
    closeDanfeCamera();
  }
}

function closeDanfeCamera() {
  if (danfeCameraStream) {
    danfeCameraStream.getTracks().forEach(t => t.stop());
    danfeCameraStream = null;
  }
  document.getElementById('danfeCameraBox').style.display = 'none';
}

function captureDanfePhoto() {
  const video = document.getElementById('danfeVideo');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

  closeDanfeCamera();

  currentDanfeBase64 = dataUrl;
  currentDanfeFile = null;
  document.getElementById('danfeFileInput').value = '';
  document.getElementById('danfeCapturedImage').value = dataUrl;

  const previewBox = document.getElementById('danfePreviewBox');
  const previewImg = document.getElementById('danfePreviewImg');
  const previewLabel = document.getElementById('danfePreviewLabel');
  previewImg.src = dataUrl;
  previewImg.style.display = 'inline-block';
  previewLabel.innerText = '📷 Foto da DANFE capturada';
  previewBox.style.display = 'block';

  onChassisInputChange();
}

/* ================= TERMO DE GARANTIA LOGIC (VAREJO) ================= */
function onWarrantyTermFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  currentWarrantyTermFile = file;
  currentWarrantyTermBase64 = null;
  document.getElementById('warrantyTermCapturedImage').value = '';

  const previewBox = document.getElementById('warrantyTermPreviewBox');
  const previewImg = document.getElementById('warrantyTermPreviewImg');
  const previewLabel = document.getElementById('warrantyTermPreviewLabel');

  if (file.type.startsWith('image/')) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewImg.style.display = 'inline-block';
      previewLabel.innerText = file.name;
      previewBox.style.display = 'block';
    };
    reader.readAsDataURL(file);
  } else {
    previewImg.style.display = 'none';
    previewLabel.innerText = '📄 Documento: ' + file.name;
    previewBox.style.display = 'block';
  }

  const badge = document.getElementById('warrantyTermBadge');
  badge.className = 'badge available';
  badge.innerText = '✓ Termo Anexado';

  onChassisInputChange();
}

async function toggleWarrantyTermCamera() {
  const box = document.getElementById('warrantyTermCameraBox');
  if (box.style.display === 'none') {
    try {
      warrantyTermCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      document.getElementById('warrantyTermVideo').srcObject = warrantyTermCameraStream;
      box.style.display = 'block';
    } catch (err) {
      alert('Não foi possível acessar a câmera para Termo de Garantia: ' + err.message);
    }
  } else {
    closeWarrantyTermCamera();
  }
}

function closeWarrantyTermCamera() {
  if (warrantyTermCameraStream) {
    warrantyTermCameraStream.getTracks().forEach(t => t.stop());
    warrantyTermCameraStream = null;
  }
  document.getElementById('warrantyTermCameraBox').style.display = 'none';
}

function captureWarrantyTermPhoto() {
  const video = document.getElementById('warrantyTermVideo');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

  closeWarrantyTermCamera();

  currentWarrantyTermBase64 = dataUrl;
  currentWarrantyTermFile = null;
  document.getElementById('warrantyTermFileInput').value = '';
  document.getElementById('warrantyTermCapturedImage').value = dataUrl;

  const previewBox = document.getElementById('warrantyTermPreviewBox');
  const previewImg = document.getElementById('warrantyTermPreviewImg');
  const previewLabel = document.getElementById('warrantyTermPreviewLabel');
  previewImg.src = dataUrl;
  previewImg.style.display = 'inline-block';
  previewLabel.innerText = '📷 Foto do Termo de Garantia capturada';
  previewBox.style.display = 'block';

  const badge = document.getElementById('warrantyTermBadge');
  badge.className = 'badge available';
  badge.innerText = '✓ Termo Capturado';

  onChassisInputChange();
}

/* ================= CANHOTO NF LOGIC (ATACADO) ================= */
function onSignedStubFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  currentSignedStubFile = file;
  currentSignedStubBase64 = null;
  document.getElementById('signedStubCapturedImage').value = '';

  const previewBox = document.getElementById('signedStubPreviewBox');
  const previewImg = document.getElementById('signedStubPreviewImg');
  const previewLabel = document.getElementById('signedStubPreviewLabel');

  if (file.type.startsWith('image/')) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewImg.style.display = 'inline-block';
      previewLabel.innerText = file.name;
      previewBox.style.display = 'block';
    };
    reader.readAsDataURL(file);
  } else {
    previewImg.style.display = 'none';
    previewLabel.innerText = '📄 Documento: ' + file.name;
    previewBox.style.display = 'block';
  }

  const badge = document.getElementById('signedStubBadge');
  badge.className = 'badge available';
  badge.innerText = '✓ Canhoto Anexado';

  onChassisInputChange();
}

async function toggleSignedStubCamera() {
  const box = document.getElementById('signedStubCameraBox');
  if (box.style.display === 'none') {
    try {
      signedStubCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      document.getElementById('signedStubVideo').srcObject = signedStubCameraStream;
      box.style.display = 'block';
    } catch (err) {
      alert('Não foi possível acessar a câmera para Canhoto NF: ' + err.message);
    }
  } else {
    closeSignedStubCamera();
  }
}

function closeSignedStubCamera() {
  if (signedStubCameraStream) {
    signedStubCameraStream.getTracks().forEach(t => t.stop());
    signedStubCameraStream = null;
  }
  document.getElementById('signedStubCameraBox').style.display = 'none';
}

function captureSignedStubPhoto() {
  const video = document.getElementById('signedStubVideo');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

  closeSignedStubCamera();

  currentSignedStubBase64 = dataUrl;
  currentSignedStubFile = null;
  document.getElementById('signedStubFileInput').value = '';
  document.getElementById('signedStubCapturedImage').value = dataUrl;

  const previewBox = document.getElementById('signedStubPreviewBox');
  const previewImg = document.getElementById('signedStubPreviewImg');
  const previewLabel = document.getElementById('signedStubPreviewLabel');
  previewImg.src = dataUrl;
  previewImg.style.display = 'inline-block';
  previewLabel.innerText = '📷 Foto do Canhoto NF capturada';
  previewBox.style.display = 'block';

  const badge = document.getElementById('signedStubBadge');
  badge.className = 'badge available';
  badge.innerText = '✓ Canhoto Capturado';

  onChassisInputChange();
}

/* ================= CHASSIS PHOTO LOGIC ================= */
function onChassisPhotoFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  currentChassisPhotoFile = file;
  currentChassisPhotoBase64 = null;
  document.getElementById('chassisPhotoCapturedImage').value = '';

  const previewBox = document.getElementById('chassisPhotoPreviewBox');
  const previewImg = document.getElementById('chassisPhotoPreviewImg');
  const previewLabel = document.getElementById('chassisPhotoPreviewLabel');

  if (file.type.startsWith('image/')) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewImg.style.display = 'inline-block';
      previewLabel.innerText = file.name;
      previewBox.style.display = 'block';
    };
    reader.readAsDataURL(file);
  } else {
    previewImg.style.display = 'none';
    previewLabel.innerText = '📄 Documento: ' + file.name;
    previewBox.style.display = 'block';
  }

  const badge = document.getElementById('chassisPhotoBadge');
  badge.className = 'badge available';
  badge.innerText = 'Foto Anexada';

  onChassisInputChange();
}

async function toggleChassisPhotoCamera() {
  const box = document.getElementById('chassisPhotoCameraBox');
  if (box.style.display === 'none') {
    try {
      chassisPhotoCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      document.getElementById('chassisPhotoVideo').srcObject = chassisPhotoCameraStream;
      box.style.display = 'block';
    } catch (err) {
      alert('Não foi possível acessar a câmera para foto do chassi: ' + err.message);
    }
  } else {
    closeChassisPhotoCamera();
  }
}

function closeChassisPhotoCamera() {
  if (chassisPhotoCameraStream) {
    chassisPhotoCameraStream.getTracks().forEach(t => t.stop());
    chassisPhotoCameraStream = null;
  }
  document.getElementById('chassisPhotoCameraBox').style.display = 'none';
}

function captureChassisPhoto() {
  const video = document.getElementById('chassisPhotoVideo');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

  closeChassisPhotoCamera();

  currentChassisPhotoBase64 = dataUrl;
  currentChassisPhotoFile = null;
  document.getElementById('chassisPhotoFileInput').value = '';
  document.getElementById('chassisPhotoCapturedImage').value = dataUrl;

  const previewBox = document.getElementById('chassisPhotoPreviewBox');
  const previewImg = document.getElementById('chassisPhotoPreviewImg');
  const previewLabel = document.getElementById('chassisPhotoPreviewLabel');
  previewImg.src = dataUrl;
  previewImg.style.display = 'inline-block';
  previewLabel.innerText = '📷 Foto da plaqueta/caixa capturada';
  previewBox.style.display = 'block';

  const badge = document.getElementById('chassisPhotoBadge');
  badge.className = 'badge available';
  badge.innerText = 'Foto Capturada';

  onChassisInputChange();
}

/* ================= TERMO DE ENTREGA LOGIC ================= */
function onTermFilesSelected(event) {
  renderTermGallery();
  onChassisInputChange();
}

async function toggleTermCamera() {
  const box = document.getElementById('termCameraBox');
  if (box.style.display === 'none') {
    try {
      termCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      document.getElementById('termVideo').srcObject = termCameraStream;
      box.style.display = 'block';
    } catch (err) {
      alert('Não foi possível acessar a câmera para Termo de Entrega: ' + err.message);
    }
  } else {
    closeTermCamera();
  }
}

function closeTermCamera() {
  if (termCameraStream) {
    termCameraStream.getTracks().forEach(t => t.stop());
    termCameraStream = null;
  }
  document.getElementById('termCameraBox').style.display = 'none';
}

function captureTermPhoto() {
  const video = document.getElementById('termVideo');
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

  termCapturedPhotos.push(dataUrl);
  document.getElementById('deliveryTermCapturedImages').value = JSON.stringify(termCapturedPhotos);
  renderTermGallery();
  onChassisInputChange();
}

function removeTermCapturedPhoto(index) {
  termCapturedPhotos.splice(index, 1);
  document.getElementById('deliveryTermCapturedImages').value = JSON.stringify(termCapturedPhotos);
  renderTermGallery();
  onChassisInputChange();
}

function renderTermGallery() {
  const gallery = document.getElementById('termPreviewGallery');
  if (!gallery) return;
  gallery.innerHTML = '';

  const filesInput = document.getElementById('termFileInput');
  const selectedFilesCount = filesInput && filesInput.files ? filesInput.files.length : 0;
  const totalCount = selectedFilesCount + termCapturedPhotos.length;

  const badge = document.getElementById('termCountBadge');
  if (badge) {
    badge.className = totalCount > 0 ? 'badge available' : 'badge muted';
    badge.innerText = `${totalCount} foto(s)/doc(s) do termo`;
  }

  if (filesInput && filesInput.files) {
    Array.from(filesInput.files).forEach((file) => {
      const item = document.createElement('div');
      item.style.cssText = 'background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:11px;color:var(--text);display:flex;align-items:center;gap:6px;';
      item.innerHTML = `<span>📄 ${file.name}</span>`;
      gallery.appendChild(item);
    });
  }

  termCapturedPhotos.forEach((b64, idx) => {
    const item = document.createElement('div');
    item.style.cssText = 'position:relative;display:inline-block;';
    item.innerHTML = `
      <img src="${b64}" style="width:70px;height:70px;object-fit:cover;border-radius:8px;border:1px solid var(--line);">
      <button type="button" onclick="removeTermCapturedPhoto(${idx})" style="position:absolute;top:-6px;right:-6px;background:#ff4d4d;color:#fff;border:none;border-radius:50%;width:20px;height:20px;font-size:12px;cursor:pointer;line-height:1;display:flex;align-items:center;justify-content:center;" title="Remover esta foto">×</button>
    `;
    gallery.appendChild(item);
  });
}

/* ================= IA AUDIT VERIFICATION ================= */
async function runChassisAiVerification() {
  const chassisVal = document.getElementById('chassisInput').value.trim();
  const badge = document.getElementById('aiBadge');
  const statusBox = document.getElementById('aiStatusBox');
  const saveBtn = document.getElementById('saveSaleBtn');

  if (!chassisVal || !hasAnyDocumentAttached()) {
    resetAiValidation();
    return;
  }

  if (badge) {
    badge.className = 'badge warning';
    badge.innerHTML = '✦ IA Rastreando e Conferindo...';
  }
  if (statusBox) {
    statusBox.style.display = 'block';
    statusBox.style.background = '#1b232c';
    statusBox.style.borderColor = '#384756';
    statusBox.style.color = '#e2ecf7';
    statusBox.innerHTML = '<div style="display:flex;align-items:center;gap:10px;"><div class="typing-dot" style="animation-delay:0s"></div><span>O Gemini está examinando os comprovantes (DANFE, Foto do Chassi, Termo de Entrega e Garantia/Canhoto) e realizando a triangulação do chassi...</span></div>';
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '⏳ Conferindo chassi com documento...';
  }

  const vehicleModelVal = document.getElementById('vehicleModelInput').value.trim();
  const fd = new FormData();
  fd.append('chassis', chassisVal);
  if (vehicleModelVal) {
    fd.append('vehicle_model', vehicleModelVal);
  }

  if (currentDanfeFile) {
    fd.append('file', currentDanfeFile);
  } else if (currentDanfeBase64) {
    fd.append('captured_image', currentDanfeBase64);
  }

  if (currentChassisPhotoFile) {
    fd.append('chassis_photo_file', currentChassisPhotoFile);
  } else if (currentChassisPhotoBase64) {
    fd.append('chassis_photo_captured_image', currentChassisPhotoBase64);
  }

  if (currentWarrantyTermFile) {
    fd.append('warranty_term_file', currentWarrantyTermFile);
  } else if (currentWarrantyTermBase64) {
    fd.append('warranty_term_captured_image', currentWarrantyTermBase64);
  }

  if (currentSignedStubFile) {
    fd.append('signed_stub_file', currentSignedStubFile);
  } else if (currentSignedStubBase64) {
    fd.append('signed_stub_captured_image', currentSignedStubBase64);
  }

  const termFilesInput = document.getElementById('termFileInput');
  if (termFilesInput && termFilesInput.files && termFilesInput.files.length) {
    Array.from(termFilesInput.files).forEach(f => fd.append('file', f));
  }
  if (termCapturedPhotos && termCapturedPhotos.length) {
    fd.append('captured_images', JSON.stringify(termCapturedPhotos));
  }

  try {
    const res = await fetch('/api/sales/verify-chassis', {
      method: 'POST',
      body: fd
    });
    const data = await res.json();

    if (data.success && data.is_valid) {
      document.getElementById('aiChassisVerified').value = '1';
      document.getElementById('aiExtractedChassis').value = (data.extracted_chassis || []).join(', ');

      if (badge) {
        badge.className = 'badge available';
        badge.innerHTML = '✓ Chassi e Modelo Confirmados';
      }

      let modelInfo = '';
      if (data.extracted_model) {
        modelInfo = `<br><strong>Modelo no Documento:</strong> <span style="color:var(--text);">${data.extracted_model}</span>`;
      }

      if (statusBox) {
        statusBox.style.background = 'rgba(97, 243, 156, 0.12)';
        statusBox.style.borderColor = 'rgba(97, 243, 156, 0.4)';
        statusBox.style.color = '#a5f3c5';
        statusBox.innerHTML = `
          <div style="display:flex;align-items:flex-start;gap:8px;">
            <span style="font-size:16px;">✓</span>
            <div>
              <strong>Confirmação Positiva por IA:</strong> O chassi localizado no comprovante (<em>${data.document_type || 'Documento de Venda'}</em>) corresponde exatamente ao chassi digitado!${modelInfo}<br>
              <div style="margin-top:6px;padding:6px 10px;background:rgba(0,0,0,0.25);border-radius:6px;display:inline-block;">
                <strong>Chassi no Documento:</strong> <span class="mono" style="color:var(--accent);font-weight:bold;">${data.matched_chassis.join(', ')}</span>
              </div>
            </div>
          </div>
        `;
      }

      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '✓ Chassis conferidos e liberados - Registrar Venda';
        saveBtn.classList.add('good-btn');
      }

    } else {
      document.getElementById('aiChassisVerified').value = '0';
      if (badge) {
        badge.className = 'badge warn-btn';
        badge.innerHTML = '✕ Divergência de Chassi';
      }

      if (statusBox) {
        statusBox.style.background = 'rgba(255, 107, 107, 0.12)';
        statusBox.style.borderColor = 'rgba(255, 107, 107, 0.4)';
        statusBox.style.color = '#ffc5cb';

        let missingMsg = '';
        if (data.missing_chassis && data.missing_chassis.length > 0) {
          missingMsg = `<br>Chassi(s) digitado(s) que não constam no documento: <b class="mono" style="color:#ff8e98;">${data.missing_chassis.join(', ')}</b>`;
        }
        let foundMsg = '';
        if (data.extracted_chassis && data.extracted_chassis.length > 0) {
          foundMsg = `<br>Chassi(s) lido(s) no documento: <b class="mono" style="color:var(--accent);">${data.extracted_chassis.join(', ')}</b>`;
        }

        statusBox.innerHTML = `
          <div style="display:flex;align-items:flex-start;gap:8px;">
            <span style="font-size:16px;">✕</span>
            <div>
              <strong>Divergência Detectada:</strong> O chassi informado no campo não coincide com o chassi do comprovante.
              ${missingMsg}
              ${foundMsg}
              <div style="margin-top:6px;font-size:12px;color:#f0b4ba;">
                Confira a digitação ou certifique-se de anexar a foto nítida do DANFE/Termo correto.
              </div>
            </div>
          </div>
        `;
      }

      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '🔒 Bloqueado: Chassi digitado não confere com documento';
        saveBtn.classList.remove('good-btn');
      }
    }

  } catch (err) {
    document.getElementById('aiChassisVerified').value = '0';
    if (badge) {
      badge.className = 'badge warn-btn';
      badge.innerHTML = '✕ Erro na Validação';
    }

    if (statusBox) {
      statusBox.style.background = 'rgba(255, 107, 107, 0.12)';
      statusBox.style.borderColor = 'rgba(255, 107, 107, 0.4)';
      statusBox.style.color = '#ffc5cb';
      statusBox.innerHTML = `<strong>Erro ao processar validação:</strong> ${err.message}`;
    }

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '🔒 Falha de Conexão na Validação';
      saveBtn.classList.remove('good-btn');
    }
  }
}

function validateSaleBeforeSubmit(event) {
  const channel = document.getElementById('channelInput').value;
  if (channel === 'varejo') {
    const hasWarranty = currentWarrantyTermFile || currentWarrantyTermBase64 || (document.getElementById('warrantyTermFileInput')?.files.length > 0);
    if (!hasWarranty) {
      event.preventDefault();
      alert('Atenção: Para vendas no Varejo, é OBRIGATÓRIO anexar o Termo de Ciência da Garantia.');
      return false;
    }
  } else if (channel === 'atacado') {
    const hasStub = currentSignedStubFile || currentSignedStubBase64 || (document.getElementById('signedStubFileInput')?.files.length > 0);
    if (!hasStub) {
      event.preventDefault();
      alert('Atenção: Para vendas no Atacado, é OBRIGATÓRIO anexar o Canhoto da NF Assinado.');
      return false;
    }
  }

  const verified = document.getElementById('aiChassisVerified').value === '1';
  if (!verified) {
    event.preventDefault();
    alert('Atenção: A venda não pode ser registrada sem que a IA confirme que o chassi do comprovante confere com o chassi digitado.');
    return false;
  }
  return true;
}
