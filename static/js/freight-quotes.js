/**
 * M-One Freight Quotes & PDF Generation Module
 * Extracted from freight.js for Anti-Monolith Compliance (< 500 lines)
 */

function exportFreightPDF(selectedIdx = null) {
  if (!lastFreightCalculationResult || !lastFreightCalculationResult.options || lastFreightCalculationResult.options.length === 0) {
    alert("Realize um cálculo de frete primeiro para exportar o PDF da cotação.");
    return;
  }

  const data = lastFreightCalculationResult;
  const today = new Date();
  const dateStr = today.toLocaleDateString("pt-BR", { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  const refNum = data.quote_number || `COT-${today.getFullYear()}${(today.getMonth()+1).toString().padStart(2,'0')}${today.getDate().toString().padStart(2,'0')}-${Math.floor(1000 + Math.random() * 9000)}`;

  let selectedBannerHtml = "";
  if (selectedIdx !== null && data.options[selectedIdx]) {
    const s = data.options[selectedIdx];
    selectedBannerHtml = `
      <div style="background: #EFF6FF; border: 2px solid #0070F3; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;">
        <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; letter-spacing: 0.5px;">✓ TRANSPORTADORA SELECIONADA PELO VENDEDOR</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
          <div>
            <strong style="font-size: 16px; color: #0F172A;">${s.carrier_name}</strong>
            <span style="font-size: 12px; color: #475569; margin-left: 8px;">(Tabela: ${s.table_name})</span>
            <div style="font-size: 11px; color: #64748B;">Prazo Estimado: <strong>${s.delivery_days} dia(s) útil(eis)</strong></div>
          </div>
          <div style="text-align: right;">
            <strong style="font-size: 20px; color: #0070F3;">R$ ${s.total_price.toFixed(2).replace('.', ',')}</strong>
            <div style="font-size: 10px; color: #64748B; font-weight: 700;">VALOR TOTAL DE FRETE COM SEGURO</div>
          </div>
        </div>
      </div>
    `;
  }

  let itemsHtml = "";
  let totalVolCount = 0;
  let grandTotalWeight = 0;
  let grandTotalCubicM3 = 0;

  const rawItems = data.items && data.items.length > 0 ? data.items : [];

  if (rawItems.length > 0) {
    let volIndex = 0;
    rawItems.forEach((item) => {
      const qty = parseInt(item.qty || 1);
      const weight = parseFloat(item.weight_kg || 0);
      const l = parseFloat(item.length_cm || 0);
      const w = parseFloat(item.width_cm || 0);
      const h = parseFloat(item.height_cm || 0);
      const volM3 = (l > 0 && w > 0 && h > 0) ? ((l * w * h) / 1000000.0) : 0;
      
      const dimStr = (l > 0 || w > 0 || h > 0) ? `${l} x ${w} x ${h} cm` : '-';
      const volStr = volM3 > 0 ? `${volM3.toFixed(3).replace('.', ',')} m³` : '-';

      for (let i = 1; i <= qty; i++) {
        volIndex++;
        itemsHtml += `
          <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. ${volIndex}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">${item.name || 'Produto MAJ'} ${qty > 1 ? `<span style="font-size: 10px; color: #64748B;">(Unidade ${i} de ${qty})</span>` : ''}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${weight > 0 ? weight.toFixed(1).replace('.', ',') + ' kg' : '-'}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${dimStr}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center; font-weight: 600;">${volStr}</td>
          </tr>
        `;
        grandTotalWeight += weight;
        grandTotalCubicM3 += volM3;
      }
      totalVolCount += qty;
    });

    itemsHtml += `
      <tr style="background-color: #F8FAFC; font-weight: bold;">
        <td colspan="2" style="padding: 10px 12px; border-top: 2px solid #CBD5E1; color: #0F172A;">
          TOTAL DA CARGA: ${totalVolCount} VOLUME(S)
        </td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${totalVolCount} ud</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${grandTotalWeight.toFixed(1).replace('.', ',')} kg</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #64748B;">-</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0070F3;">${grandTotalCubicM3 > 0 ? grandTotalCubicM3.toFixed(3).replace('.', ',') + ' m³' : '-'}</td>
      </tr>
    `;
  } else {
    itemsHtml = `
      <tr>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. 1</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">${data.product_name || 'Produtos MAJ'}</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${(data.total_weight_kg || 0).toFixed(1).replace('.', ',')} kg</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
      </tr>
    `;
  }

  let optionsHtml = "";
  data.options.forEach((opt, idx) => {
    const isSelected = (selectedIdx === idx);
    const isCheap = opt.badges && opt.badges.some(b => b.includes("Barato"));
    const isFast = opt.badges && opt.badges.some(b => b.includes("Rápido"));
    let badgeText = "";
    if (isSelected) badgeText += `<span style="background: #0070F3; color: #FFFFFF; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px; margin-left: 6px;">SELECIONADA</span>`;
    if (isCheap) badgeText += `<span style="background: #DCFCE7; color: #166534; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px; margin-left: 6px;">MAIS ECONÔMICA</span>`;
    if (isFast) badgeText += `<span style="background: #DBEAFE; color: #1E40AF; font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px; margin-left: 6px;">MAIS RÁPIDA</span>`;

    optionsHtml += `
      <tr style="${isSelected ? 'background-color: #EFF6FF; font-weight: bold;' : (isCheap ? 'background-color: #F0FDF4;' : '')}">
        <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0;">
          <strong style="color: #0F172A; font-size: 13px;">${opt.carrier_name}</strong> ${badgeText}
          <div style="font-size: 11px; color: #64748B; margin-top: 2px;">Tabela: ${opt.table_name}</div>
        </td>
        <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; text-align: center; font-weight: 600; color: #1E293B;">
          ${opt.delivery_days} dia(s) útil(eis)
        </td>
        <td style="padding: 10px 12px; border-bottom: 1px solid #E2E8F0; text-align: right;">
          <strong style="font-size: 15px; color: ${isSelected ? '#0070F3' : '#0F172A'};">R$ ${opt.total_price.toFixed(2).replace('.', ',')}</strong>
        </td>
      </tr>
    `;
  });

  const pdfWin = window.open("", "_blank");
  if (!pdfWin) {
    alert("Permita pop-ups no navegador para visualizar e imprimir o PDF da cotação.");
    return;
  }

  pdfWin.document.write(`
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Cotação de Frete — MAJ Mobilidade (${refNum})</title>
      <style>
        @page { size: A4; margin: 15mm; }
        body { font-family: 'Segoe UI', Arial, sans-serif; color: #1E293B; background: #FFF; margin: 0; padding: 20px; font-size: 12px; line-height: 1.5; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0070F3; padding-bottom: 15px; margin-bottom: 20px; }
        .brand-title { font-size: 22px; font-weight: 900; color: #0070F3; letter-spacing: -0.5px; }
        .brand-sub { font-size: 11px; color: #64748B; font-weight: 600; text-transform: uppercase; }
        .doc-info { text-align: right; font-size: 11px; color: #64748B; }
        .doc-info strong { color: #0F172A; font-size: 12px; }
        .section-box { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; margin-bottom: 18px; }
        .section-title { font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; margin-bottom: 8px; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; letter-spacing: 0.5px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 6px; }
        th { background: #F1F5F9; color: #475569; font-size: 10px; font-weight: 800; text-transform: uppercase; padding: 8px 12px; text-align: left; border-bottom: 2px solid #CBD5E1; }
        .footer { margin-top: 30px; border-top: 1px solid #E2E8F0; padding-top: 12px; font-size: 10px; color: #94A3B8; text-align: center; }
        @media print {
          body { padding: 0; }
          .no-print { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="no-print" style="margin-bottom: 20px; text-align: right;">
        <button onclick="window.print()" style="background: #0070F3; color: white; border: none; padding: 9px 18px; border-radius: 6px; font-weight: bold; cursor: pointer;">🖨️ Imprimir / Salvar como PDF</button>
      </div>

      <div class="header">
        <div>
          <div class="brand-title">MAJ MOBILIDADE</div>
          <div class="brand-sub">M-One Operating System — Cotação Oficial de Frete</div>
        </div>
        <div class="doc-info">
          <strong>Cotação Nº: ${refNum}</strong><br>
          Data: ${dateStr}<br>
          Origem: Vitória / ES (29045-660)
        </div>
      </div>

      ${selectedBannerHtml}

      <div class="section-box grid-2">
        <div>
          <div class="section-title">Dados do Cliente & Destino</div>
          <strong>Cliente:</strong> ${data.customer_name || 'Não informado'}<br>
          <strong>CEP Destino:</strong> ${data.cep_dest || '-'}<br>
          <strong>Rota:</strong> Vitória/ES ➔ Destino
        </div>
        <div>
          <div class="section-title">Resumo da Carga & Seguro</div>
          <strong>Total de Volumes:</strong> ${totalVolCount || 1} volume(s)<br>
          <strong>Peso Total Físico:</strong> ${data.total_weight_kg.toFixed(1).replace('.', ',')} kg<br>
          <strong>Base de Seguro (1/3 Atacado):</strong> R$ ${data.insurance_base_value.toFixed(2).replace('.', ',')}<br>
          <strong>Regra:</strong> 1/3 do valor de atacado dos produtos
        </div>
      </div>

      <div style="margin-bottom: 20px;">
        <div class="section-title">Discriminação Individual dos Volumes & Produtos</div>
        <table>
          <thead>
            <tr>
              <th style="text-align: center; width: 70px;">Volume</th>
              <th>Produto / Veículo</th>
              <th style="text-align: center;">Qtd</th>
              <th style="text-align: center;">Peso Unit.</th>
              <th style="text-align: center;">Dimensões (C x L x A)</th>
              <th style="text-align: center;">Cubagem Unit.</th>
            </tr>
          </thead>
          <tbody>
            ${itemsHtml}
          </tbody>
        </table>
      </div>

      <div style="margin-bottom: 20px;">
        <div class="section-title">Opções Disponíveis de Transporte</div>
        <table>
          <thead>
            <tr>
              <th>Transportadora / Tabela</th>
              <th style="text-align: center;">Prazo Estimado</th>
              <th style="text-align: right;">Valor Total (Frete + Seguro)</th>
            </tr>
          </thead>
          <tbody>
            ${optionsHtml}
          </tbody>
        </table>
      </div>

      <div class="footer">
        MAJ Mobilidade — Sistema Operacional M-One. Esta cotação é válida por 7 dias a contar da data de emissão.<br>
        Origem Vitória/ES. Todos os valores incluem taxas operacionais e seguro de transporte regulamentar.
      </div>

      <script>
        window.onload = function() { setTimeout(function() { window.print(); }, 400); };
      <\/script>
    </body>
    </html>
  `);
  pdfWin.document.close();
}

function exportArchivedQuotePDF(refNum, customerName, cepDest, address, carrier, price, createdAt, itemsRaw = "") {
  let items = [];
  if (itemsRaw) {
    try {
      items = typeof itemsRaw === "string" ? JSON.parse(itemsRaw) : itemsRaw;
    } catch (e) {
      items = [];
    }
  }

  let itemsHtml = "";
  let totalVolCount = 0;
  let grandTotalWeight = 0;
  let grandTotalCubicM3 = 0;

  if (Array.isArray(items) && items.length > 0) {
    let volIndex = 0;
    items.forEach((item) => {
      const qty = parseInt(item.qty || 1);
      const weight = parseFloat(item.weight_kg || 0);
      const l = parseFloat(item.length_cm || 0);
      const w = parseFloat(item.width_cm || 0);
      const h = parseFloat(item.height_cm || 0);
      const volM3 = (l > 0 && w > 0 && h > 0) ? ((l * w * h) / 1000000.0) : 0;
      
      const dimStr = (l > 0 || w > 0 || h > 0) ? `${l} x ${w} x ${h} cm` : '-';
      const volStr = volM3 > 0 ? `${volM3.toFixed(3).replace('.', ',')} m³` : '-';

      for (let i = 1; i <= qty; i++) {
        volIndex++;
        itemsHtml += `
          <tr>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. ${volIndex}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">${item.name || 'Produto MAJ'} ${qty > 1 ? `<span style="font-size: 10px; color: #64748B;">(Unidade ${i} de ${qty})</span>` : ''}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${weight > 0 ? weight.toFixed(1).replace('.', ',') + ' kg' : '-'}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">${dimStr}</td>
            <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center; font-weight: 600;">${volStr}</td>
          </tr>
        `;
        grandTotalWeight += weight;
        grandTotalCubicM3 += volM3;
      }
      totalVolCount += qty;
    });

    itemsHtml += `
      <tr style="background-color: #F8FAFC; font-weight: bold;">
        <td colspan="2" style="padding: 10px 12px; border-top: 2px solid #CBD5E1; color: #0F172A;">
          TOTAL DA CARGA: ${totalVolCount} VOLUME(S)
        </td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${totalVolCount} ud</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0F172A;">${grandTotalWeight.toFixed(1).replace('.', ',')} kg</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #64748B;">-</td>
        <td style="padding: 10px 12px; border-top: 2px solid #CBD5E1; text-align: center; color: #0070F3;">${grandTotalCubicM3 > 0 ? grandTotalCubicM3.toFixed(3).replace('.', ',') + ' m³' : '-'}</td>
      </tr>
    `;
  } else {
    itemsHtml = `
      <tr>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; font-weight: bold; color: #0070F3; text-align: center;">Vol. 1</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">Carga Arquivada MAJ</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">1 ud</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
        <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: center;">-</td>
      </tr>
    `;
  }

  const pdfHtml = `
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Cotação Arquivada — MAJ Mobilidade (${refNum})</title>
      <style>
        @page { size: A4; margin: 15mm; }
        body { font-family: 'Segoe UI', Arial, sans-serif; color: #1E293B; background: #FFF; margin: 0; padding: 20px; font-size: 12px; line-height: 1.5; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0070F3; padding-bottom: 15px; margin-bottom: 20px; }
        .brand-title { font-size: 22px; font-weight: 900; color: #0070F3; letter-spacing: -0.5px; }
        .brand-sub { font-size: 11px; color: #64748B; font-weight: 600; text-transform: uppercase; }
        .doc-info { text-align: right; font-size: 11px; color: #64748B; }
        .doc-info strong { color: #0F172A; font-size: 12px; }
        .section-box { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; margin-bottom: 18px; }
        .section-title { font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; margin-bottom: 8px; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; letter-spacing: 0.5px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 6px; }
        th { background: #F1F5F9; color: #475569; font-size: 10px; font-weight: 800; text-transform: uppercase; padding: 8px 12px; text-align: left; border-bottom: 2px solid #CBD5E1; }
        .footer { margin-top: 30px; border-top: 1px solid #E2E8F0; padding-top: 12px; font-size: 10px; color: #94A3B8; text-align: center; }
        @media print {
          body { padding: 0; }
          .no-print { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="no-print" style="margin-bottom: 20px; text-align: right;">
        <button onclick="window.print()" style="background: #0070F3; color: white; border: none; padding: 9px 18px; border-radius: 6px; font-weight: bold; cursor: pointer;">🖨️ Imprimir / Salvar como PDF</button>
      </div>

      <div class="header">
        <div>
          <div class="brand-title">MAJ MOBILIDADE</div>
          <div class="brand-sub">M-One Operating System — Cotação Arquivada de Frete</div>
        </div>
        <div class="doc-info">
          <strong>Cotação Nº: ${refNum}</strong><br>
          Data: ${createdAt}<br>
          Origem: Vitória / ES (29045-660)
        </div>
      </div>

      <div style="background: #EFF6FF; border: 2px solid #0070F3; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;">
        <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; color: #0070F3; letter-spacing: 0.5px;">✓ TRANSPORTADORA SELECIONADA</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
          <div>
            <strong style="font-size: 16px; color: #0F172A;">${carrier || 'Transportadora Selecionada'}</strong>
          </div>
          <div style="text-align: right;">
            <strong style="font-size: 20px; color: #0070F3;">R$ ${parseFloat(price || 0).toFixed(2).replace('.', ',')}</strong>
            <div style="font-size: 10px; color: #64748B; font-weight: 700;">VALOR TOTAL DE FRETE ARQUIVADO</div>
          </div>
        </div>
      </div>

      <div class="section-box grid-2">
        <div>
          <div class="section-title">Dados do Cliente & Destino</div>
          <strong>Cliente:</strong> ${customerName || 'Não informado'}<br>
          <strong>CEP / Endereço:</strong> ${address || cepDest || '-'}<br>
          <strong>Rota:</strong> Vitória/ES ➔ Destino
        </div>
        <div>
          <div class="section-title">Resumo da Carga & Seguro</div>
          <strong>Total de Volumes:</strong> ${totalVolCount || 1} volume(s)<br>
          <strong>Regra de Seguro:</strong> 1/3 do valor de atacado dos produtos
        </div>
      </div>

      <div style="margin-bottom: 20px;">
        <div class="section-title">Discriminação Individual dos Volumes & Produtos</div>
        <table>
          <thead>
            <tr>
              <th style="text-align: center; width: 70px;">Volume</th>
              <th>Produto / Veículo</th>
              <th style="text-align: center;">Qtd</th>
              <th style="text-align: center;">Peso Unit.</th>
              <th style="text-align: center;">Dimensões (C x L x A)</th>
              <th style="text-align: center;">Cubagem Unit.</th>
            </tr>
          </thead>
          <tbody>
            ${itemsHtml}
          </tbody>
        </table>
      </div>

      <div class="footer">
        MAJ Mobilidade — Sistema Operacional M-One. Cotação arquivada no histórico de fretes.<br>
        Origem Vitória/ES. Todos os valores incluem taxas operacionais e seguro de transporte regulamentar.
      </div>

      <script>window.onload = function() { setTimeout(function() { window.print(); }, 400); };<\/script>
    </body>
    </html>
  `;
  const printWindow = window.open("", "_blank", "width=850,height=950");
  if (printWindow) {
    printWindow.document.write(pdfHtml);
    printWindow.document.close();
  }
}
