/**
 * M-One Atacado Admin - Gallery & Image Compression Helpers
 */

function renderAtacadoGalleryPreview() {
  const container = document.getElementById('atacado_gallery_preview_container');
  const mainInput = document.getElementById('atacado_form_image_main');
  const galleryInput = document.getElementById('atacado_form_images_gallery');
  if (!container) return;

  if (mainInput) mainInput.value = ATACADO_CURRENT_IMAGE_MAIN || '';
  if (galleryInput) galleryInput.value = JSON.stringify(ATACADO_CURRENT_GALLERY || []);

  container.innerHTML = '';
  if (!ATACADO_CURRENT_GALLERY || ATACADO_CURRENT_GALLERY.length === 0) {
    container.innerHTML = '<span style="color: var(--muted); font-size: 0.75rem; grid-column: 1/-1;">Nenhuma foto enviada para o modelo. Use o campo acima para adicionar fotos.</span>';
    return;
  }

  ATACADO_CURRENT_GALLERY.forEach((imgUrl, index) => {
    const isMain = imgUrl === ATACADO_CURRENT_IMAGE_MAIN;
    const card = document.createElement('div');
    card.style.position = 'relative';
    card.style.border = isMain ? '2px solid #00cc88' : '1px solid var(--line, #334155)';
    card.style.borderRadius = '8px';
    card.style.padding = '4px';
    card.style.background = 'rgba(0,0,0,0.3)';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.alignItems = 'center';

    card.innerHTML = `
      <img src="${imgUrl}" style="width: 100%; aspect-ratio: 4 / 5; object-fit: cover; object-position: center; border-radius: 6px;" onerror="this.src='/static/logo.png'">
      ${isMain ? '<span style="position: absolute; top: 6px; left: 6px; background: #00cc88; color: #000; font-weight: 800; font-size: 0.65rem; padding: 2px 6px; border-radius: 4px;">⭐ CAPA</span>' : ''}
      <div style="display: flex; gap: 4px; width: 100%; margin-top: 4px;">
        ${!isMain ? `<button type="button" class="btn sm" onclick="setAtacadoCoverPhoto(${index})" style="flex: 1; padding: 2px; font-size: 0.65rem; background: rgba(0, 204, 136, 0.15); color: #00cc88; border: 1px solid rgba(0,204,136,0.3);">Capa</button>` : ''}
        <button type="button" class="btn sm" onclick="removeAtacadoPhotoFromGallery(${index})" style="padding: 2px 6px; font-size: 0.65rem; color: #ef4444; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3);">✕</button>
      </div>
    `;
    container.appendChild(card);
  });
}

function setAtacadoCoverPhoto(index) {
  if (ATACADO_CURRENT_GALLERY[index]) {
    ATACADO_CURRENT_IMAGE_MAIN = ATACADO_CURRENT_GALLERY[index];
    renderAtacadoGalleryPreview();
  }
}

function removeAtacadoPhotoFromGallery(index) {
  const removed = ATACADO_CURRENT_GALLERY.splice(index, 1)[0];
  if (ATACADO_CURRENT_IMAGE_MAIN === removed) {
    ATACADO_CURRENT_IMAGE_MAIN = ATACADO_CURRENT_GALLERY.length > 0 ? ATACADO_CURRENT_GALLERY[0] : '';
  }
  renderAtacadoGalleryPreview();
}

function validateAtacadoFormPayload(form) {
  const statusDiv = document.getElementById('atacado_upload_status_badge');
  const mainInput = document.getElementById('atacado_form_image_main');
  const galleryInput = document.getElementById('atacado_form_images_gallery');

  if (mainInput) mainInput.value = ATACADO_CURRENT_IMAGE_MAIN || '';
  if (galleryInput) galleryInput.value = JSON.stringify(ATACADO_CURRENT_GALLERY || []);

  const mainImg = mainInput?.value || '';
  const galleryJson = galleryInput?.value || '';
  const totalChars = mainImg.length + galleryJson.length;
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

function handleAtacadoGalleryUpload(input) {
  const files = input.files;
  const statusDiv = document.getElementById('atacado_upload_status_badge');
  const saveBtn = document.getElementById('atacado_save_btn');
  if (!files || files.length === 0) return;

  if (ATACADO_CURRENT_GALLERY.length >= 12) {
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
  const availableSlots = 12 - ATACADO_CURRENT_GALLERY.length;
  const totalFiles = Math.min(files.length, availableSlots);

  Array.from(files).slice(0, totalFiles).forEach(file => {
    compressAtacadoImage(file, 640, 0.50, (base64Data) => {
      if (base64Data && !ATACADO_CURRENT_GALLERY.includes(base64Data)) {
        ATACADO_CURRENT_GALLERY.push(base64Data);
        if (!ATACADO_CURRENT_IMAGE_MAIN) {
          ATACADO_CURRENT_IMAGE_MAIN = base64Data;
        }
      }
      processedCount++;
      if (processedCount === totalFiles) {
        renderAtacadoGalleryPreview();
        const mainImg = document.getElementById('atacado_form_image_main')?.value || '';
        const galleryJson = document.getElementById('atacado_form_images_gallery')?.value || '';
        const totalMb = ((mainImg.length + galleryJson.length) * 3 / 4) / (1024 * 1024);
        if (statusDiv) {
          statusDiv.style.display = 'block';
          statusDiv.style.color = '#00cc88';
          statusDiv.textContent = `✅ ${ATACADO_CURRENT_GALLERY.length} foto(s) otimizada(s) (~${totalMb.toFixed(2)} MB - Pronto para salvar).`;
          setTimeout(() => { statusDiv.style.display = 'none'; }, 5000);
        }
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.style.opacity = '1';
          saveBtn.style.cursor = 'pointer';
          saveBtn.textContent = 'Salvar no Atacado';
        }
        input.value = '';
      }
    });
  });
}

function compressAtacadoImage(file, maxWidth, quality, callback) {
  const reader = new FileReader();
  reader.onload = function(e) {
    const img = new Image();
    img.onload = function() {
      let width = img.width;
      let height = img.height;
      if (width > maxWidth) {
        height = Math.round((height * maxWidth) / width);
        width = maxWidth;
      }

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, width, height);

      const dataUrl = canvas.toDataURL('image/jpeg', quality);
      callback(dataUrl);
    };
    img.onerror = function() {
      console.warn("Erro ao processar imagem:", file ? file.name : "desconhecido");
      callback(null);
    };
    img.src = e.target.result;
  };
  reader.onerror = function() {
    console.warn("Erro ao ler arquivo:", file ? file.name : "desconhecido");
    callback(null);
  };
  reader.readAsDataURL(file);
}
