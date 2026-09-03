function openModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('show');
    const dInput = el.querySelector('input[type="date"]');
    if (dInput && !dInput.value) {
      dInput.value = new Date().toISOString().slice(0, 10);
    }
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) {
    el.classList.remove('show');
    if (typeof stopLiveCamera === 'function') {
      stopLiveCamera(el);
    }
  }
}

document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal')) {
    e.target.classList.remove('show');
  }
});

function addPaymentRow(method, account) {
  method = method || 'Pix';
  account = account || '';
  const box = document.getElementById('paymentsBox');
  if (!box) return;
  const row = document.createElement('div');
  row.className = 'payment-row';
  row.innerHTML = '<select name="payment_method[]"><option ' + (method === 'Pix' ? 'selected' : '') + '>Pix</option><option ' + (method === 'Link' ? 'selected' : '') + '>Link</option><option ' + (method === 'Cartão' ? 'selected' : '') + '>Cartão</option><option ' + (method === 'Dinheiro' ? 'selected' : '') + '>Dinheiro</option><option ' + (method === 'Consignado' ? 'selected' : '') + '>Consignado</option><option>À vista</option></select><input name="payment_account[]" placeholder="Conta / plataforma" value="' + account + '"><input type="number" step="0.01" name="payment_amount[]" placeholder="Valor"><input type="file" name="payment_receipt[]" accept="image/*,.pdf" capture="environment"><button type="button" class="icon-btn" onclick="this.parentElement.remove()">×</button>';
  box.appendChild(row);
}

setTimeout(function() {
  document.querySelectorAll('.flash').forEach(function(x) {
    x.classList.add('fade');
  });
}, 5000);

let currentStream = null;

async function startLiveCamera(btn) {
  const container = btn.closest('.camera-widget-container') || btn.closest('.form-grid') || btn.closest('form');
  const streamBox = container.querySelector('#cameraStreamBox');
  const video = container.querySelector('#liveVideo');
  const controls = container.querySelector('#cameraControls');

  try {
    currentStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } }
    });
    video.srcObject = currentStream;
    if (streamBox) streamBox.style.display = 'block';
    if (controls) controls.style.display = 'none';
  } catch (err) {
    alert('Não foi possível abrir a câmera: ' + err.message);
  }
}

function stopLiveCamera(btn) {
  if (currentStream) {
    currentStream.getTracks().forEach(function(track) { track.stop(); });
    currentStream = null;
  }
  const container = btn ? (btn.closest('.camera-widget-container') || btn.closest('.form-grid') || btn.closest('form')) : document;
  const streamBox = container ? container.querySelector('#cameraStreamBox') : null;
  const controls = container ? container.querySelector('#cameraControls') : null;
  if (streamBox) streamBox.style.display = 'none';
  if (controls) controls.style.display = 'flex';
}

function takeSnapshot(btn) {
  const container = btn.closest('.camera-widget-container') || btn.closest('.form-grid') || btn.closest('form');
  const video = container.querySelector('#liveVideo');
  const previewBox = container.querySelector('#cameraPreviewBox');
  const previewImg = container.querySelector('#capturedImagePreview');
  const hiddenInput = container.querySelector('#capturedImageDataInput');

  if (!video || !video.videoWidth) {
    alert('Aguardando inicialização da câmera...');
    return;
  }

  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  const dataUrl = canvas.toDataURL('image/jpeg', 0.85);

  if (previewImg) previewImg.src = dataUrl;
  if (hiddenInput) hiddenInput.value = dataUrl;
  if (previewBox) previewBox.style.display = 'block';

  stopLiveCamera(btn);
}

function retakePhoto(btn) {
  const container = btn.closest('.camera-widget-container') || btn.closest('.form-grid') || btn.closest('form');
  const previewBox = container.querySelector('#cameraPreviewBox');
  const hiddenInput = container.querySelector('#capturedImageDataInput');

  if (previewBox) previewBox.style.display = 'none';
  if (hiddenInput) hiddenInput.value = '';

  startLiveCamera(btn);
}
