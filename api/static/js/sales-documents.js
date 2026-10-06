/*
 * M-One Sales - Document & Camera Capture Module (static/js/sales-documents.js)
 * Gerencia upload, captura via webcam/mobile e renderização de prévias dos comprovantes.
 */

// Streams de câmera
var danfeCameraStream = null;
var termCameraStream = null;
var chassisPhotoCameraStream = null;
var warrantyTermCameraStream = null;
var signedStubCameraStream = null;

// Estados de arquivos e Base64 dos comprovantes
var currentDanfeFile = null;
var currentDanfeBase64 = null;
var currentChassisPhotoFile = null;
var currentChassisPhotoBase64 = null;
var currentWarrantyTermFile = null;
var currentWarrantyTermBase64 = null;
var currentSignedStubFile = null;
var currentSignedStubBase64 = null;
var termCapturedPhotos = [];

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

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
  if (badge) {
    badge.className = 'badge available';
    badge.innerText = '✓ Termo Anexado';
  }

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
  if (badge) {
    badge.className = 'badge available';
    badge.innerText = '✓ Termo Capturado';
  }

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
  if (badge) {
    badge.className = 'badge available';
    badge.innerText = '✓ Canhoto Anexado';
  }

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
  if (badge) {
    badge.className = 'badge available';
    badge.innerText = '✓ Canhoto Capturado';
  }

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
  if (badge) {
    badge.className = 'badge available';
    badge.innerText = 'Foto Anexada';
  }

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
  if (badge) {
    badge.className = 'badge available';
    badge.innerText = 'Foto Capturada';
  }

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
}

/* ================= TERMO DE ENTREGA LOGIC ================= */
function onTermFilesSelected(event) {
  renderTermGallery();
  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
}

function removeTermCapturedPhoto(index) {
  termCapturedPhotos.splice(index, 1);
  document.getElementById('deliveryTermCapturedImages').value = JSON.stringify(termCapturedPhotos);
  renderTermGallery();
  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
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
