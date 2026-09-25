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

function handleFileInput(input) {
  if (input.files && input.files.length > 0) {
    uploadFiles(input.files);
    input.value = '';
  }
}

function uploadFiles(fileList) {
  const loader = document.getElementById('uploadLoader');
  const loaderText = document.getElementById('uploadLoaderText');
  if (loader) loader.style.display = 'block';
  if (loaderText) {
    loaderText.textContent = `Processando ${fileList.length} arquivo(s) com IA Gemini...`;
  }

  const formData = new FormData();
  for (let i = 0; i < fileList.length; i++) {
    formData.append('receipts', fileList[i]);
  }

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = { 'X-Requested-With': 'XMLHttpRequest' };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/upload', {
    method: 'POST',
    body: formData,
    headers: headers
  })
  .then(res => res.json())
  .then(data => {
    if (loader) loader.style.display = 'none';
    if (data.success) {
      window.location.reload();
    } else {
      alert(data.message || 'Erro ao processar comprovantes.');
    }
  })
  .catch(err => {
    if (loader) loader.style.display = 'none';
    console.error(err);
    alert('Ocorreu uma falha na requisição de upload.');
  });
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
  .then(res => res.json())
  .then(data => {
    if (data.success && ind) {
      ind.classList.add('active');
      setTimeout(() => ind.classList.remove('active'), 1500);
    }
  })
  .catch(err => console.error('Erro ao salvar célula:', err));
}

function addNewManualRow() {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/api/transactions/new', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({})
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
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
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      const row = document.getElementById(`row-${id}`);
      if (row) row.remove();
    }
  })
  .catch(err => console.error('Erro ao excluir:', err));
}

// Google Sheets Modals & Sync
function openSheetsModal() {
  const m = document.getElementById('sheetsModal');
  if (m) m.style.display = 'flex';
}

function closeSheetsModal() {
  const m = document.getElementById('sheetsModal');
  if (m) m.style.display = 'none';
}

function saveSheetsWebhook() {
  const input = document.getElementById('sheetsWebhookInput');
  const url = input ? input.value.trim() : '';

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
  };
  if (csrfToken) headers['X-CSRFToken'] = csrfToken;

  fetch('/m-pay/api/sheets/config', {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({ webhook_url: url })
  })
  .then(res => res.json())
  .then(data => {
    alert(data.message || 'Configuração salva!');
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
 * M-Pay • Sincronizador Bidirecional Google Sheets
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
    
    if (action === "create") {
      sheetData.appendRow([
        tx.id,
        tx.paid_at,
        tx.beneficiary_name,
        tx.beneficiary_document,
        tx.amount,
        tx.bank_origin,
        tx.payment_method,
        tx.category,
        tx.notes,
        tx.confidence_status,
        new Date()
      ]);
      logHistory(sheetHistory, tx.id, "CRIAÇÃO", "Todos", "", "Valor: R$ " + tx.amount, actor, "M-Pay");
    } else if (action === "update") {
      const rowIdx = findRowById(sheetData, tx.id);
      if (rowIdx > 0) {
        sheetData.getRange(rowIdx, 2, 1, 9).setValues([[
          tx.paid_at,
          tx.beneficiary_name,
          tx.beneficiary_document,
          tx.amount,
          tx.bank_origin,
          tx.payment_method,
          tx.category,
          tx.notes,
          tx.confidence_status
        ]]);
        sheetData.getRange(rowIdx, 11).setValue(new Date());
        logHistory(sheetHistory, tx.id, "EDIÇÃO", "Células", "", "Atualizado por " + actor, actor, "M-Pay");
      }
    } else if (action === "delete") {
      const rowIdx = findRowById(sheetData, tx.id);
      if (rowIdx > 0) {
        sheetData.deleteRow(rowIdx);
        logHistory(sheetHistory, tx.id, "EXCLUSÃO", "Registro", "ID " + tx.id, "Removido", actor, "M-Pay");
      }
    }
    
    return ContentService.createTextOutput(JSON.stringify({ success: true })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ success: false, error: err.message })).setMimeType(ContentService.MimeType.JSON);
  }
}

function onEdit(e) {
  try {
    const range = e.range;
    const sheet = range.getSheet();
    if (sheet.getName() !== "Comprovantes") return;
    
    const row = range.getRow();
    if (row <= 1) return;
    
    const col = range.getColumn();
    const id = sheet.getRange(row, 1).getValue();
    if (!id) return;
    
    const colMap = {
      2: "paid_at",
      3: "beneficiary_name",
      4: "beneficiary_document",
      5: "amount",
      6: "bank_origin",
      7: "payment_method",
      8: "category",
      9: "notes"
    };
    
    const field = colMap[col];
    if (!field) return;
    
    const oldVal = e.oldValue || "";
    const newVal = range.getValue();
    const userEmail = Session.getActiveUser().getEmail() || "Usuário Google Sheets";
    
    const payload = {
      source: "google_sheets",
      transaction_id: id,
      actor: userEmail
    };
    payload[field] = newVal;
    
    const options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    UrlFetchApp.fetch(MONE_WEBHOOK_URL, options);
    
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheetHistory = ss.getSheetByName("Histórico de Alterações");
    if (sheetHistory) {
      logHistory(sheetHistory, id, "EDIÇÃO", field, oldVal, newVal, userEmail, "Google Sheets");
    }
  } catch (err) {
    Logger.log("Erro no onEdit: " + err);
  }
}

function findRowById(sheet, id) {
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] == id) return i + 1;
  }
  return -1;
}

function logHistory(sheet, txId, action, field, oldVal, newVal, actor, origin) {
  sheet.appendRow([new Date(), txId, action, field, oldVal, newVal, actor, origin]);
}

function setupSheetsIfMissing(ss) {
  let sheetData = ss.getSheetByName("Comprovantes");
  if (!sheetData) {
    sheetData = ss.getSheets()[0];
    sheetData.setName("Comprovantes");
  }
  if (sheetData.getLastRow() === 0) {
    sheetData.appendRow([
      "ID M-Pay", "Data", "Favorecido", "CPF/CNPJ/Pix", "Valor (R$)",
      "Banco Origem", "Método", "Categoria", "Observações", "Status IA", "Sincronizado Em"
    ]);
    sheetData.getRange("A1:K1").setBackground("#2563EB").setFontColor("#FFFFFF").setFontWeight("bold");
    sheetData.setFrozenRows(1);
  }
  
  let sheetHistory = ss.getSheetByName("Histórico de Alterações");
  if (!sheetHistory) {
    sheetHistory = ss.insertSheet("Histórico de Alterações");
    sheetHistory.appendRow([
      "Data/Hora", "ID Transação", "Ação", "Campo Alterado",
      "Valor Anterior", "Novo Valor", "Autor", "Origem"
    ]);
    sheetHistory.getRange("A1:H1").setBackground("#1E3A8A").setFontColor("#FFFFFF").setFontWeight("bold");
    sheetHistory.setFrozenRows(1);
  }
}`;

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
