/*
 * M-One Sales Operations (static/js/sales.js)
 * Controle geral da tela de vendas, filtros, integração Bling e validação de submissão.
 */

document.addEventListener('DOMContentLoaded', () => {
  if (typeof addPaymentRow === 'function') {
    addPaymentRow('Pix', 'Sicoob');
    addPaymentRow('Link', 'Fonton Pay');
  }
});

function filterSalesTable() {
  const q = document.getElementById('salesSearch')?.value.toLowerCase() || '';
  const rows = document.querySelectorAll('#salesTable tbody tr');
  rows.forEach(r => {
    const text = r.textContent.toLowerCase();
    r.style.display = text.includes(q) ? '' : 'none';
  });
}

async function fetchFromBling() {
  const input = document.getElementById('blingOrderInput');
  const num = input?.value.trim();
  if (!num) {
    alert('Por favor, digite o número do Pedido Bling antes de buscar.');
    input?.focus();
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
  const ch = document.getElementById('channelInput')?.value;
  const warrantySec = document.getElementById('warrantyTermSection');
  const stubSec = document.getElementById('signedStubSection');

  if (ch === 'varejo') {
    if (warrantySec) warrantySec.style.display = 'block';
    if (stubSec) stubSec.style.display = 'none';
  } else {
    if (warrantySec) warrantySec.style.display = 'none';
    if (stubSec) stubSec.style.display = 'block';
  }

  if (typeof onChassisInputChange === 'function') {
    onChassisInputChange();
  }
}

function validateSaleBeforeSubmit(event) {
  const channel = document.getElementById('channelInput')?.value;
  if (channel === 'varejo') {
    const hasWarranty = (typeof currentWarrantyTermFile !== 'undefined' && currentWarrantyTermFile) ||
                        (typeof currentWarrantyTermBase64 !== 'undefined' && currentWarrantyTermBase64) ||
                        (document.getElementById('warrantyTermFileInput')?.files.length > 0);
    if (!hasWarranty) {
      event.preventDefault();
      alert('Atenção: Para vendas no Varejo, é OBRIGATÓRIO anexar o Termo de Ciência da Garantia.');
      return false;
    }
  } else if (channel === 'atacado') {
    const hasStub = (typeof currentSignedStubFile !== 'undefined' && currentSignedStubFile) ||
                    (typeof currentSignedStubBase64 !== 'undefined' && currentSignedStubBase64) ||
                    (document.getElementById('signedStubFileInput')?.files.length > 0);
    if (!hasStub) {
      event.preventDefault();
      alert('Atenção: Para vendas no Atacado, é OBRIGATÓRIO anexar o Canhoto da NF Assinado.');
      return false;
    }
  }

  const verified = document.getElementById('aiChassisVerified')?.value === '1';
  if (!verified) {
    event.preventDefault();
    alert('Atenção: A venda não pode ser registrada sem que a IA confirme que o chassi do comprovante confere com o chassi digitado.');
    return false;
  }
  return true;
}
