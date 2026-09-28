/**
 * M-Pay Interactive Sheet & Camera Capture Scripts (static/js/mpay.js)
 */

function handleDrop(e) {
  e.preventDefault();
  const dropzone = document.getElementById('mpayDropzone');
  if (dropzone) dropzone.classList.remove('dragover');
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    uploadFiles(e.dataTransfer.files);
  }
}

let isUploading = false;
let mpayQueue = [];
let mpayQueueTotal = 0;
let currentAnalysis = null;

function handleFileInput(input) {
  if (input.files && input.files.length > 0) {
    uploadFiles(input.files);
    input.value = '';
  }
}

function uploadFiles(fileList) {
  if (!fileList || fileList.length === 0) return;
  if (isUploading) {
    console.warn("[M-Pay] Processamento já em andamento.");
    return;
  }
  mpayQueue = Array.from(fileList);
  mpayQueueTotal = mpayQueue.length;
  isUploading = true;

  const btnCamera = document.getElementById('btnCamera');
  const btnFiles = document.getElementById('btnFiles');
  if (btnCamera) { btnCamera.disabled = true; btnCamera.style.opacity = '0.6'; btnCamera.style.pointerEvents = 'none'; }
  if (btnFiles) { btnFiles.disabled = true; btnFiles.style.opacity = '0.6'; btnFiles.style.pointerEvents = 'none'; }

  processNextInQueue();
}

function processNextInQueue() {
  if (mpayQueue.length === 0) {
    resetUploadState();
    window.location.reload();
    return;
  }

  const currentFile = mpayQueue[0];
  const currentIndex = mpayQueueTotal - mpayQueue.length + 1;

  const loader = document.getElementById('uploadLoader');
  const loaderText = document.getElementById('uploadLoaderText');
  if (loader) loader.style.display = 'block';
  if (loaderText) {
    loaderText.textContent = `Analisando comprovante (${currentIndex} de ${mpayQueueTotal}) com IA Gemini...`;
  }

  const formData = new FormData();
  formData.append('receipt', currentFile);

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = { 'X-Requested-With': 'XMLHttpRequest' };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/api/analyze-receipt', {
    method: 'POST',
    body: formData,
    headers: headers
  })
  .then(res => {
    if (res.status === 401 || res.redirected) {
      alert('Sua sessão expirou. Redirecionando para login...');
      window.location.href = '/login';
      return null;
    }
    return res.json();
  })
  .then(data => {
    if (!data) return;
    if (loader) loader.style.display = 'none';
    if (!data.success) {
      alert(data.message || 'Erro ao analisar comprovante.');
      mpayQueue.shift();
      processNextInQueue();
      return;
    }
    currentAnalysis = data;
    openConfirmationModal(data, currentIndex, mpayQueueTotal);
  })
  .catch(err => {
    console.error(err);
    alert('Falha ao conectar com o serviço de análise por IA.');
    if (loader) loader.style.display = 'none';
    mpayQueue.shift();
    if (mpayQueue.length > 0) processNextInQueue();
    else resetUploadState();
  });
}



function resetUploadState() {
  isUploading = false;
  const loader = document.getElementById('uploadLoader');
  if (loader) loader.style.display = 'none';
  const btnCamera = document.getElementById('btnCamera');
  const btnFiles = document.getElementById('btnFiles');
  if (btnCamera) { btnCamera.disabled = false; btnCamera.style.opacity = '1'; btnCamera.style.pointerEvents = ''; }
  if (btnFiles) { btnFiles.disabled = false; btnFiles.style.opacity = '1'; btnFiles.style.pointerEvents = ''; }
}

function updateCell(id, field, value) {
  const ind = document.getElementById(`save-ind-${id}`);
  const payload = {};
  payload[field] = value;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch(`/m-pay/api/transactions/${id}`, {
    method: 'PUT',
    headers: headers,
    body: JSON.stringify(payload)
  })
  .then(res => {
    if (res.status === 401 || res.redirected) {
      alert('Sua sessão expirou. Faça login novamente.');
      window.location.href = '/login';
      return null;
    }
    return res.json();
  })
  .then(data => {
    if (data && data.success && ind) {
      ind.classList.add('active');
      setTimeout(() => ind.classList.remove('active'), 1500);
    }
  })
  .catch(err => console.error('Erro ao salvar célula:', err));
}

function addNewManualRow() {
  const companyEl = document.getElementById('activeCompanySelect');
  const sourceEl = document.getElementById('activePaymentSourceSelect');
  const payingCompany = companyEl ? companyEl.value : 'M-one';
  const paymentSource = sourceEl ? sourceEl.value : 'Conta da Empresa';

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/api/transactions/new', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({ paying_company: payingCompany, payment_source: paymentSource })
  })
  .then(res => {
    if (res.status === 401 || res.redirected) {
      alert('Sua sessão expirou. Faça login novamente.');
      window.location.href = '/login';
      return null;
    }
    return res.json();
  })
  .then(data => {
    if (data && data.success) {
      window.location.reload();
    }
  })
  .catch(err => console.error('Erro ao criar linha:', err));
}

function deleteRow(id) {
  if (!confirm('Deseja realmente remover este registro de comprovante?')) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch(`/m-pay/api/transactions/${id}`, {
    method: 'DELETE',
    headers: headers
  })
  .then(res => {
    if (res.status === 401 || res.redirected) {
      alert('Sua sessão expirou. Faça login novamente.');
      window.location.href = '/login';
      return null;
    }
    return res.json();
  })
  .then(data => {
    if (data && data.success) {
      const row = document.getElementById(`row-${id}`);
      if (row) row.remove();
    }
  })
  .catch(err => console.error('Erro ao excluir:', err));
}

// Google Sheets Modals & Sync
function openSheetsNotConnectedModal() {
  const m = document.getElementById('sheetsNotConnectedModal');
  if (m) m.style.display = 'flex';
}

function closeSheetsNotConnectedModal() {
  const m = document.getElementById('sheetsNotConnectedModal');
  if (m) m.style.display = 'none';
}

function goToSheetsConfig() {
  closeSheetsNotConnectedModal();
  openSheetsModal(true);
}

function openSheetsModal(focusSpreadsheet = false) {
  const m = document.getElementById('sheetsModal');
  if (m) {
    m.style.display = 'flex';
    if (focusSpreadsheet) {
      setTimeout(() => {
        const input = document.getElementById('sheetsSpreadsheetInput');
        if (input) {
          input.focus();
          input.select();
        }
      }, 100);
    }
  }
}

function closeSheetsModal() {
  const m = document.getElementById('sheetsModal');
  if (m) m.style.display = 'none';
}

function saveSheetsWebhook() {
  const webhookInput = document.getElementById('sheetsWebhookInput');
  const spreadsheetInput = document.getElementById('sheetsSpreadsheetInput');
  const webhookUrl = webhookInput ? webhookInput.value.trim() : '';
  const sheetsUrl = spreadsheetInput ? spreadsheetInput.value.trim() : '';

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/api/sheets/config', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({ webhook_url: webhookUrl, sheets_url: sheetsUrl })
  })
  .then(res => res.json())
  .then(data => {
    alert(data.message || 'Configurações salvas!');
    closeSheetsModal();
    window.location.reload();
  })
  .catch(err => alert('Erro ao salvar configuração: ' + err));
}

function syncAllToSheets() {
  if (!confirm('Deseja enviar todos os comprovantes lançados para a planilha do Google Sheets?')) return;

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/api/sheets/sync-all', {
    method: 'POST',
    headers: headers
  })
  .then(res => res.json())
  .then(data => {
    alert(data.message || 'Sincronização concluída!');
  })
  .catch(err => alert('Erro na sincronização: ' + err));
}

// Histórico & Auditoria Modal
function openAuditModal(tid) {
  const m = document.getElementById('auditModal');
  const content = document.getElementById('auditModalContent');
  if (m) m.style.display = 'flex';
  if (content) content.innerHTML = '<div style="text-align:center;padding:24px;color:var(--muted);">Carregando histórico...</div>';

  fetch(`/m-pay/api/audit-logs/${tid}`)
    .then(res => res.json())
    .then(data => {
      if (!data.success || !data.logs || data.logs.length === 0) {
        content.innerHTML = '<div style="text-align:center;padding:24px;color:var(--muted);">Nenhum histórico registrado para este comprovante.</div>';
        return;
      }

      let html = '<div style="display:flex;flex-direction:column;gap:12px;">';
      data.logs.forEach(l => {
        let badgeColor = '#2563EB';
        let actionLabel = l.action.toUpperCase();
        if (l.action === 'created') badgeColor = '#059669';
        if (l.action === 'deleted') badgeColor = '#EF4444';

        let originLabel = l.source === 'google_sheets' ? 'Google Sheets' : (l.source === 'mpay_ai' ? 'IA M-Pay' : 'M-One Web');

        html += `
          <div style="background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:12.5px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
              <span style="background:${badgeColor}1A;color:${badgeColor};font-weight:800;font-size:10.5px;padding:2px 8px;border-radius:4px;">
                ${actionLabel} • ${originLabel}
              </span>
              <span style="font-size:11px;color:var(--muted);">${l.created_at}</span>
            </div>
            <div style="color:var(--text);font-weight:600;">
              ${l.actor_name || 'Sistema'}
            </div>
            ${l.field_name ? `
              <div style="font-size:12px;color:var(--muted);margin-top:4px;">
                Campo: <b>${l.field_name}</b> | Anterior: <del>${l.old_value || 'vazio'}</del> ➔ Novo: <span style="color:#047857;font-weight:700;">${l.new_value || 'vazio'}</span>
              </div>
            ` : ''}
          </div>
        `;
      });
      html += '</div>';
      content.innerHTML = html;
    })
    .catch(err => {
      content.innerHTML = `<div style="color:#EF4444;text-align:center;padding:16px;">Erro ao carregar histórico: ${err}</div>`;
    });
}

function closeAuditModal() {
  const m = document.getElementById('auditModal');
  if (m) m.style.display = 'none';
}

function copyAppsScriptCode() {
  const code = `/**
 * M-Pay • Sincronizador Bidirecional & Arquivador Automático no Google Drive
 * Cole este código em Extensões > Apps Script na sua planilha Google.
 * Depois clique em "Implantar" > "Nova Implantação" > "App da Web" (Acesso: Qualquer pessoa).
 */
const MONE_WEBHOOK_URL = "https://m-one.majmobilidade.com.br/m-pay/api/sheets/webhook-sync";

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    setupSheetsIfMissing(ss);
    const sheetData = ss.getSheetByName("Comprovantes");
    const sheetHistory = ss.getSheetByName("Histórico de Alterações");
    const action = data.action || "create";
    const tx = data.transaction || {};
    const actor = data.actor || "M-Pay IA";
    let driveLink = "";
    if (tx.file_base64 && tx.orig_filename) {
      try {
        var rootFolder = DriveApp.getFoldersByName("Comprovantes M-Pay").hasNext() ? DriveApp.getFoldersByName("Comprovantes M-Pay").next() : DriveApp.createFolder("Comprovantes M-Pay");
        var companyName = tx.paying_company || "M-one";
        var targetFolder = rootFolder.getFoldersByName(companyName).hasNext() ? rootFolder.getFoldersByName(companyName).next() : rootFolder.createFolder(companyName);
        var decoded = Utilities.base64Decode(tx.file_base64);
        var blob = Utilities.newBlob(decoded, tx.mime_type || "application/pdf", tx.orig_filename);
        var driveFile = targetFolder.createFile(blob);
        driveFile.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
        driveLink = driveFile.getUrl();
      } catch (fErr) { Logger.log("Erro no Drive: " + fErr); }
    }
    if (action === "create") {
      sheetData.appendRow([tx.id, tx.paid_at, tx.paying_company || "M-one", tx.payment_source || "Conta da Empresa", tx.beneficiary_name, tx.beneficiary_document, tx.amount, tx.bank_origin, tx.payment_method, tx.category, tx.notes, tx.confidence_status, driveLink || tx.file_url || "", new Date()]);
      logHistory(sheetHistory, tx.id, "CRIAÇÃO", "Todos", "", "Valor: R$ " + tx.amount, actor, "M-Pay");
    } else if (action === "update") {
      const rowIdx = findRowById(sheetData, tx.id);
      if (rowIdx > 0) {
        sheetData.getRange(rowIdx, 2, 1, 10).setValues([[tx.paid_at, tx.paying_company || "M-one", tx.payment_source || "Conta da Empresa", tx.beneficiary_name, tx.beneficiary_document, tx.amount, tx.bank_origin, tx.payment_method, tx.category, tx.notes]]);
        sheetData.getRange(rowIdx, 14).setValue(new Date());
        logHistory(sheetHistory, tx.id, "EDIÇÃO", "Células", "", "Atualizado por " + actor, actor, "M-Pay");
      }
    } else if (action === "delete") {
      const rowIdx = findRowById(sheetData, tx.id);
      if (rowIdx > 0) {
        sheetData.deleteRow(rowIdx);
        logHistory(sheetHistory, tx.id, "EXCLUSÃO", "Registro", "ID " + tx.id, "Removido", actor, "M-Pay");
      }
    }
    return ContentService.createTextOutput(JSON.stringify({ success: true, drive_url: driveLink })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ success: false, error: err.message })).setMimeType(ContentService.MimeType.JSON);
  }
}

function onEdit(e) {
  try {
    const range = e.range;
    const sheet = range.getSheet();
    if (sheet.getName() !== "Comprovantes" || range.getRow() <= 1) return;
    const id = sheet.getRange(range.getRow(), 1).getValue();
    if (!id) return;
    const colMap = { 2: "paid_at", 3: "paying_company", 4: "payment_source", 5: "beneficiary_name", 6: "beneficiary_document", 7: "amount", 8: "bank_origin", 9: "payment_method", 10: "category", 11: "notes" };
    const field = colMap[range.getColumn()];
    if (!field) return;
    const userEmail = Session.getActiveUser().getEmail() || "Usuário Google Sheets";
    const payload = { source: "google_sheets", transaction_id: id, actor: userEmail };
    payload[field] = range.getValue();
    UrlFetchApp.fetch(MONE_WEBHOOK_URL, { method: "post", contentType: "application/json", payload: JSON.stringify(payload), muteHttpExceptions: true });
    const sheetHistory = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Histórico de Alterações");
    if (sheetHistory) logHistory(sheetHistory, id, "EDIÇÃO", field, e.oldValue || "", range.getValue(), userEmail, "Google Sheets");
  } catch (err) { Logger.log("Erro no onEdit: " + err); }
}

function findRowById(sheet, id) {
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) { if (data[i][0] == id) return i + 1; }
  return -1;
}

function logHistory(sheet, txId, action, field, oldVal, newVal, actor, origin) {
  sheet.appendRow([new Date(), txId, action, field, oldVal, newVal, actor, origin]);
}

function setupSheetsIfMissing(ss) {
  let sheetData = ss.getSheetByName("Comprovantes");
  if (!sheetData) { sheetData = ss.getSheets()[0]; sheetData.setName("Comprovantes"); }
  if (sheetData.getLastRow() === 0) {
    sheetData.appendRow(["ID M-Pay", "Data", "Empresa Pagadora", "Forma / Origem", "Favorecido", "CPF/CNPJ/Pix", "Valor (R$)", "Banco Origem", "Método", "Categoria", "Observações", "Status IA", "Link Comprovante (Drive)", "Sincronizado Em"]);
    sheetData.getRange("A1:N1").setBackground("#2563EB").setFontColor("#FFFFFF").setFontWeight("bold");
    sheetData.setFrozenRows(1);
  }
  let sheetHistory = ss.getSheetByName("Histórico de Alterações");
  if (!sheetHistory) {
    sheetHistory = ss.insertSheet("Histórico de Alterações");
    sheetHistory.appendRow(["Data/Hora", "ID Transação", "Ação", "Campo Alterado", "Valor Anterior", "Novo Valor", "Autor", "Origem"]);
    sheetHistory.getRange("A1:H1").setBackground("#1E3A8A").setFontColor("#FFFFFF").setFontWeight("bold");
    sheetHistory.setFrozenRows(1);
  }
}
`;

  navigator.clipboard.writeText(code).then(() => {
    const fb = document.getElementById('copyFeedback');
    if (fb) {
      fb.style.display = 'inline';
      setTimeout(() => fb.style.display = 'none', 3000);
    }
  }).catch(() => {
    alert('Por favor copie o código manualmente.');
  });
}
