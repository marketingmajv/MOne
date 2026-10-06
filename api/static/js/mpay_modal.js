/**
 * M-Pay Confirmation Modal Controller (static/js/mpay_modal.js)
 * Gerencia os chips inteligentes de seleção rápida e o extrato editável de confirmação.
 */

function openConfirmationModal(data, currentIdx, total) {
  const modal = document.getElementById('mpayConfirmModal');
  if (!modal) return;

  const badge = document.getElementById('modalQueueBadge');
  if (badge) {
    if (total > 1) {
      badge.textContent = `${currentIdx} de ${total}`;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }

  const ext = data.extracted || {};

  // Sugestão Inteligente IA: Chips da Empresa Pagadora
  const suggestedCompany = ext.paying_company || 'M-one';
  const companyInput = document.getElementById('modalInputCompany');
  if (companyInput) companyInput.value = suggestedCompany;
  document.querySelectorAll('#companyChipsContainer .mpay-chip').forEach(chip => {
    chip.classList.toggle('active', chip.dataset.company === suggestedCompany);
  });

  // Sugestão Inteligente IA: Chips de Forma de Pagamento
  const suggestedSource = ext.payment_source || 'Conta da Empresa';
  const sourceInput = document.getElementById('modalInputSource');
  if (sourceInput) sourceInput.value = suggestedSource;
  document.querySelectorAll('#sourceChipsContainer .mpay-chip').forEach(chip => {
    chip.classList.toggle('active', chip.dataset.source === suggestedSource);
  });

  // Extrato Editável
  const amtInput = document.getElementById('modalInputAmount');
  if (amtInput) amtInput.value = ext.amount ? Number(ext.amount).toFixed(2) : '';

  const benInput = document.getElementById('modalInputBeneficiary');
  if (benInput) benInput.value = ext.beneficiary_name || '';

  const docInput = document.getElementById('modalInputDoc');
  if (docInput) docInput.value = ext.beneficiary_document || '';

  const dateInput = document.getElementById('modalInputDate');
  if (dateInput) dateInput.value = ext.paid_at || '';

  const bankInput = document.getElementById('modalInputBank');
  if (bankInput) bankInput.value = ext.bank_origin || '';

  const catSelect = document.getElementById('modalInputCategory');
  if (catSelect) catSelect.value = ext.category || 'Geral';

  const notesInput = document.getElementById('modalInputNotes');
  if (notesInput) notesInput.value = ext.notes || '';

  // Atualizar Tag de Confiança da IA / Status de Erro
  const confTag = document.getElementById('modalConfidenceTag');
  if (confTag) {
    if (ext.confidence_status === 'verified') {
      confTag.textContent = '✓ Alta Precisão IA';
      confTag.style.background = 'rgba(16, 185, 129, 0.15)';
      confTag.style.color = '#34d399';
      confTag.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    } else if (ext.confidence_status === 'partial') {
      confTag.textContent = '⚠️ Leitura Parcial IA';
      confTag.style.background = 'rgba(245, 158, 11, 0.15)';
      confTag.style.color = '#fbbf24';
      confTag.style.borderColor = 'rgba(245, 158, 11, 0.3)';
    } else {
      confTag.textContent = '⚠️ Cota IA Excedida (Manual)';
      confTag.style.background = 'rgba(239, 68, 68, 0.15)';
      confTag.style.color = '#f87171';
      confTag.style.borderColor = 'rgba(239, 68, 68, 0.3)';
    }
  }

  // Visualização / Preview do Arquivo
  const imgPreview = document.getElementById('modalPreviewImg');
  const pdfPreview = document.getElementById('modalPreviewPdf');
  const pdfName = document.getElementById('modalPdfName');
  const fileMeta = document.getElementById('modalFileMeta');

  if (fileMeta) fileMeta.textContent = data.filename || 'Comprovante';

  if (data.is_pdf) {
    if (imgPreview) imgPreview.style.display = 'none';
    if (pdfPreview) pdfPreview.style.display = 'flex';
    if (pdfName) pdfName.textContent = data.filename || 'documento.pdf';
  } else {
    if (pdfPreview) pdfPreview.style.display = 'none';
    if (imgPreview) {
      imgPreview.src = data.preview_url || '';
      imgPreview.style.display = 'block';
    }
  }

  // Reset do botão de salvar
  const btnConfirm = document.getElementById('btnModalConfirm');
  const saveStatus = document.getElementById('modalSaveStatus');
  if (btnConfirm) { btnConfirm.disabled = false; btnConfirm.style.opacity = '1'; }
  if (saveStatus) saveStatus.style.display = 'none';

  modal.style.display = 'flex';
}

function selectCompanyChip(btn) {
  document.querySelectorAll('#companyChipsContainer .mpay-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  const comp = btn.dataset.company || 'M-one';
  const input = document.getElementById('modalInputCompany');
  if (input) input.value = comp;
}

function selectSourceChip(btn) {
  document.querySelectorAll('#sourceChipsContainer .mpay-chip').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  const src = btn.dataset.source || 'Conta da Empresa';
  const input = document.getElementById('modalInputSource');
  if (input) input.value = src;
}

function confirmCurrentReceipt() {
  if (!currentAnalysis) return;

  const btnConfirm = document.getElementById('btnModalConfirm');
  const saveStatus = document.getElementById('modalSaveStatus');
  if (btnConfirm) { btnConfirm.disabled = true; btnConfirm.style.opacity = '0.6'; }
  if (saveStatus) {
    saveStatus.textContent = 'Gravando e sincronizando com planilha...';
    saveStatus.style.display = 'inline-block';
  }

  const payload = {
    orig_filename: currentAnalysis.filename,
    file_base64: currentAnalysis.file_base64,
    file_hash: currentAnalysis.file_hash,
    mime_type: currentAnalysis.mime_type,
    paying_company: document.getElementById('modalInputCompany')?.value || 'M-one',
    payment_source: document.getElementById('modalInputSource')?.value || 'Conta da Empresa',
    amount: document.getElementById('modalInputAmount')?.value || 0,
    beneficiary_name: document.getElementById('modalInputBeneficiary')?.value || '',
    beneficiary_document: document.getElementById('modalInputDoc')?.value || '',
    paid_at: document.getElementById('modalInputDate')?.value || '',
    bank_origin: document.getElementById('modalInputBank')?.value || '',
    category: document.getElementById('modalInputCategory')?.value || 'Geral',
    notes: document.getElementById('modalInputNotes')?.value || '',
    confidence_status: currentAnalysis.extracted?.confidence_status || 'verified',
  };

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/api/confirm-receipt', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    if (data && data.success) {
      closeConfirmModal();
      mpayQueue.shift();
      if (mpayQueue.length > 0) {
        processNextInQueue();
      } else {
        window.location.reload();
      }
    } else {
      alert(data.message || 'Erro ao gravar comprovante.');
      if (btnConfirm) { btnConfirm.disabled = false; btnConfirm.style.opacity = '1'; }
      if (saveStatus) saveStatus.style.display = 'none';
    }
  })
  .catch(err => {
    console.error(err);
    alert('Erro de conexão ao salvar comprovante.');
    if (btnConfirm) { btnConfirm.disabled = false; btnConfirm.style.opacity = '1'; }
    if (saveStatus) saveStatus.style.display = 'none';
  });
}

function discardCurrentReceipt() {
  if (!confirm('Deseja realmente descartar este comprovante sem salvar?')) {
    return;
  }
  closeConfirmModal();
  mpayQueue.shift();
  if (mpayQueue.length > 0) {
    processNextInQueue();
  } else {
    resetUploadState();
  }
}

function closeConfirmModal() {
  const modal = document.getElementById('mpayConfirmModal');
  if (modal) modal.style.display = 'none';
  currentAnalysis = null;
}
