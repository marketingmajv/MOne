/*
 * M-One Sales - AI Verification & Chassis Triangulation (static/js/sales-ai.js)
 * Realiza a leitura e triangulação de chassi via Gemini Vision OCR contra os comprovantes.
 */

var chassisDebounceTimer = null;

function resetAiValidation() {
  const verifiedEl = document.getElementById('aiChassisVerified');
  if (verifiedEl) verifiedEl.value = '0';
  const extractedEl = document.getElementById('aiExtractedChassis');
  if (extractedEl) extractedEl.value = '';

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
  return Boolean(
    (typeof currentDanfeFile !== 'undefined' && currentDanfeFile) ||
    (typeof currentDanfeBase64 !== 'undefined' && currentDanfeBase64) ||
    (typeof currentChassisPhotoFile !== 'undefined' && currentChassisPhotoFile) ||
    (typeof currentChassisPhotoBase64 !== 'undefined' && currentChassisPhotoBase64) ||
    (typeof currentWarrantyTermFile !== 'undefined' && currentWarrantyTermFile) ||
    (typeof currentWarrantyTermBase64 !== 'undefined' && currentWarrantyTermBase64) ||
    (typeof currentSignedStubFile !== 'undefined' && currentSignedStubFile) ||
    (typeof currentSignedStubBase64 !== 'undefined' && currentSignedStubBase64) ||
    (termFiles && termFiles.length > 0) ||
    (typeof termCapturedPhotos !== 'undefined' && termCapturedPhotos && termCapturedPhotos.length > 0)
  );
}

function onChassisInputChange() {
  resetAiValidation();

  const chassisVal = document.getElementById('chassisInput')?.value.trim() || '';
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

/* ================= IA AUDIT VERIFICATION ================= */
async function runChassisAiVerification() {
  const chassisInput = document.getElementById('chassisInput');
  const chassisVal = chassisInput ? chassisInput.value.trim() : '';
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

  const vehicleModelVal = document.getElementById('vehicleModelInput')?.value.trim() || '';
  const fd = new FormData();
  fd.append('chassis', chassisVal);
  if (vehicleModelVal) {
    fd.append('vehicle_model', vehicleModelVal);
  }

  if (typeof currentDanfeFile !== 'undefined' && currentDanfeFile) {
    fd.append('file', currentDanfeFile);
  } else if (typeof currentDanfeBase64 !== 'undefined' && currentDanfeBase64) {
    fd.append('captured_image', currentDanfeBase64);
  }

  if (typeof currentChassisPhotoFile !== 'undefined' && currentChassisPhotoFile) {
    fd.append('chassis_photo_file', currentChassisPhotoFile);
  } else if (typeof currentChassisPhotoBase64 !== 'undefined' && currentChassisPhotoBase64) {
    fd.append('chassis_photo_captured_image', currentChassisPhotoBase64);
  }

  if (typeof currentWarrantyTermFile !== 'undefined' && currentWarrantyTermFile) {
    fd.append('warranty_term_file', currentWarrantyTermFile);
  } else if (typeof currentWarrantyTermBase64 !== 'undefined' && currentWarrantyTermBase64) {
    fd.append('warranty_term_captured_image', currentWarrantyTermBase64);
  }

  if (typeof currentSignedStubFile !== 'undefined' && currentSignedStubFile) {
    fd.append('signed_stub_file', currentSignedStubFile);
  } else if (typeof currentSignedStubBase64 !== 'undefined' && currentSignedStubBase64) {
    fd.append('signed_stub_captured_image', currentSignedStubBase64);
  }

  const termFilesInput = document.getElementById('termFileInput');
  if (termFilesInput && termFilesInput.files && termFilesInput.files.length) {
    Array.from(termFilesInput.files).forEach(f => fd.append('file', f));
  }
  if (typeof termCapturedPhotos !== 'undefined' && termCapturedPhotos && termCapturedPhotos.length) {
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
