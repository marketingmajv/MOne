/**
 * M-One Freight Ranking Renderer (static/js/freight-ranking-render.js)
 * Renderizador executivo de cards de classificação de transportadoras.
 * Organização limpa, sem duplicação de botões e com transparência de taxas.
 * Em conformidade estrita Anti-Monólito (< 500 linhas).
 */

function buildCarrierRankingHtml(options, scopePrefix = "modal") {
  if (!options || options.length === 0) {
    return `
      <div style="padding: 20px; border-radius: 12px; background: var(--surface-subtle, rgba(255,255,255,0.02)); border: 1px dashed var(--border-subtle, rgba(255,255,255,0.15)); font-size: 0.82rem; color: var(--muted, #94a3b8); text-align: center;">
        ⚠️ Nenhuma transportadora classificada para este CEP e peso. Use a inclusão manual abaixo para adicionar uma cotação direta.
      </div>
    `;
  }

  const recIdx = window.freightSelection ? window.freightSelection.recommended : 0;
  const inc = window.freightSelection ? window.freightSelection.included : new Set();
  const editingIdx = window.freightSelection ? window.freightSelection.editingIdx : null;

  return options.map((opt, idx) => {
    const isInc = inc.has(idx);
    const isRec = (recIdx === idx);
    const isEditing = (editingIdx === idx);
    const isCheapest = opt.badges && opt.badges.some(b => b.includes("Barato"));
    const isFastest = opt.badges && opt.badges.some(b => b.includes("Rápido"));

    const rankBg = isCheapest ? "var(--brand-emerald, #00e599)" : (isFastest ? "var(--brand-blue, #38bdf8)" : "var(--primary, #3b82f6)");
    const rankColor = (isCheapest || isFastest) ? "#042211" : "#ffffff";

    const badgeHtml = isCheapest
      ? `<span class="badge" style="background: rgba(0,229,153,0.15); color: var(--accent, #00e599); border: 1px solid rgba(0,229,153,0.3); font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 99px;">⚡ MAIS ECONÔMICA</span>`
      : (isFastest
        ? `<span class="badge" style="background: rgba(56,189,248,0.15); color: var(--brand-blue, #38bdf8); border: 1px solid rgba(56,189,248,0.3); font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 99px;">🚀 MAIS RÁPIDA</span>`
        : "");

    // Seletor de praças/faixas da transportadora
    let variantSelectHtml = "";
    if (Array.isArray(opt.rate_variants) && opt.rate_variants.length > 1) {
      const vOpts = opt.rate_variants.map((v, vIdx) => {
        const sel = (v.city_label === opt.city_label) ? "selected" : "";
        return `<option value="${vIdx}" ${sel}>📍 ${v.city_label} — R$ ${Number(v.total_price).toFixed(2).replace('.', ',')} (${v.delivery_days}d)</option>`;
      }).join("");
      variantSelectHtml = `
        <select class="form-input" style="font-size: 0.72rem; padding: 3px 8px; height: 26px; border-radius: 6px; max-width: 260px; background: var(--surface-card, #121722); color: var(--text, #f8fafc); border: 1px solid var(--border-subtle, rgba(255,255,255,0.15));" onchange="changeCarrierRateVariant(${idx}, this.value, event)" onclick="event.stopPropagation();" title="Alternar praça/faixa desta tabela">
          ${vOpts}
        </select>
      `;
    } else if (opt.city_label) {
      variantSelectHtml = `<span style="font-size: 0.72rem; color: var(--brand-blue, #38bdf8); font-weight: 600;">📍 ${opt.city_label}</span>`;
    }

    // Sub-barra de transparência de taxas
    const baseVal = Number(opt.base_freight || opt.fixed_price || 0);
    const insVal = Number(opt.insurance_cost || 0);
    const surVal = Number(opt.surcharges_cost || 0);
    const tecVal = Number(opt.tec_cost || 0);
    const tasVal = Number(opt.tas_cost || 0);
    const posVal = Number(opt.pos_cost || 0);
    const chWeight = Number(opt.charged_weight_kg || opt.gross_weight_kg || 0);

    const feeDetails = [];
    if (tecVal > 0) feeDetails.push(`TEC: R$ ${tecVal.toFixed(2).replace('.', ',')}`);
    if (tasVal > 0) feeDetails.push(`TAS: R$ ${tasVal.toFixed(2).replace('.', ',')}`);
    if (posVal > 0) feeDetails.push(`Pedágio/POS: R$ ${posVal.toFixed(2).replace('.', ',')}`);
    const feeTooltip = feeDetails.length ? ` title="${feeDetails.join(' • ')}"` : "";

    const breakdownHtml = `
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 0.70rem; color: var(--muted, #94a3b8); margin-top: 4px; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle, rgba(255,255,255,0.08)); width: fit-content;" ${feeTooltip}>
        <span>Base/Peso: <strong style="color: var(--text, #f8fafc);">R$ ${baseVal.toFixed(2).replace('.', ',')}</strong></span>
        <span>•</span>
        <span>Seguro: <strong style="color: var(--text, #f8fafc);">R$ ${insVal.toFixed(2).replace('.', ',')}</strong></span>
        <span>•</span>
        <span>Taxas (TEC/TAS/Ped): <strong style="color: ${surVal > 0 ? 'var(--brand-amber, #e5a93b)' : 'var(--text, #f8fafc)'};">R$ ${surVal.toFixed(2).replace('.', ',')}</strong></span>
        ${chWeight > 0 ? `<span>•</span><span style="opacity: 0.8;">(${chWeight.toFixed(1).replace('.', ',')} kg taxados)</span>` : ""}
      </div>
    `;

    // Ações de aferição da planilha e contato direto
    const dlUrl = opt.download_url || (opt.table_id ? `/freight/tables/${opt.table_id}/download` : "");
    const dlBtnHtml = dlUrl ? `
      <a href="${dlUrl}" target="_blank" class="btn sm" style="padding: 3px 8px; font-size: 0.68rem; gap: 4px; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; background: rgba(16,185,129,0.12); color: #10b981; border: 1px solid rgba(16,185,129,0.25);" onclick="event.stopPropagation();" title="Abrir e conferir a planilha oficial da transportadora no Google Planilhas">
        📊 Planilha Google
      </a>
    ` : "";

    const phoneRaw = opt.phone ? String(opt.phone).trim() : "";
    const phoneDigits = phoneRaw.replace(/\D/g, "");
    const repName = opt.sales_rep_name ? String(opt.sales_rep_name).trim() : "Comercial";

    let contactHtml = "";
    if (phoneDigits) {
      const callLink = `<a href="tel:${phoneDigits}" class="btn sm" style="padding: 3px 8px; font-size: 0.68rem; gap: 4px; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; background: var(--surface-subtle, rgba(255,255,255,0.06)); border: 1px solid var(--border-subtle, rgba(255,255,255,0.15)); color: var(--text, #f8fafc);" onclick="event.stopPropagation();" title="Ligar para ${repName} (${phoneRaw})">📞 ${phoneRaw}</a>`;
      const waText = encodeURIComponent(`Olá ${repName}, estou conferindo a cotação da ${opt.carrier_name} para ${opt.city_label || 'destino'} no valor de R$ ${Number(opt.total_price).toFixed(2)}.`);
      const waLink = `<a href="https://wa.me/55${phoneDigits}?text=${waText}" target="_blank" class="btn sm" style="padding: 3px 8px; font-size: 0.68rem; gap: 3px; border-radius: 6px; background: rgba(37,211,102,0.12); color: #25d366; border: 1px solid rgba(37,211,102,0.25); text-decoration: none; display: inline-flex; align-items: center;" onclick="event.stopPropagation();" title="Chamar no WhatsApp para confirmar preço">💬 WhatsApp</a>`;

      contactHtml = `
        <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 6px;" onclick="event.stopPropagation();">
          <span style="font-size: 0.68rem; color: var(--muted, #94a3b8); font-weight: 600;">👤 ${repName}:</span>
          ${callLink}
          ${waLink}
          ${dlBtnHtml}
        </div>
      `;
    } else if (dlBtnHtml) {
      contactHtml = `
        <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 6px;" onclick="event.stopPropagation();">
          ${dlBtnHtml}
        </div>
      `;
    }

    // Caixa de edição de valor/prazo
    const priceInputId = `${scopePrefix}_edit_price_${idx}`;
    const daysInputId = `${scopePrefix}_edit_days_${idx}`;
    const editBoxHtml = isEditing ? `
      <div style="margin-top: 8px; padding: 8px 10px; border-radius: 8px; background: var(--surface-subtle, rgba(255,255,255,0.04)); border: 1px solid var(--border-subtle, rgba(255,255,255,0.15)); display: flex; align-items: center; gap: 8px; flex-wrap: wrap;" onclick="event.stopPropagation();">
        <div style="display: flex; align-items: center; gap: 4px;">
          <span style="font-size: 0.72rem; color: var(--muted, #94a3b8); font-weight: 700;">R$</span>
          <input type="number" step="0.01" id="${priceInputId}" value="${Number(opt.total_price).toFixed(2)}" class="form-input" style="width: 90px; padding: 3px 6px; font-size: 0.75rem; font-weight: 700; border-radius: 6px;">
        </div>
        <div style="display: flex; align-items: center; gap: 4px;">
          <input type="number" min="1" id="${daysInputId}" value="${opt.delivery_days}" class="form-input" style="width: 55px; padding: 3px 6px; font-size: 0.75rem; text-align: center; border-radius: 6px;">
          <span style="font-size: 0.72rem; color: var(--muted, #94a3b8);">dias</span>
        </div>
        <button type="button" class="btn sm primary" style="padding: 3px 8px; font-size: 0.70rem;" onclick="applyEditedCarrierRate(${idx}, '${priceInputId}', '${daysInputId}', event)">Salvar</button>
        <button type="button" class="btn sm secondary" style="padding: 3px 6px; font-size: 0.70rem;" onclick="toggleEditCarrierRate(${idx}, event)">Cancelar</button>
      </div>
    ` : "";

    return `
      <div class="rank-row modal-carrier-card ${isRec ? 'recommended selected' : ''} ${!isInc ? 'excluded' : ''}" data-idx="${idx}" style="padding: 12px 14px; gap: 12px; cursor: pointer; align-items: flex-start; border-radius: 12px; margin-bottom: 8px; transition: all 0.2s ease;" onclick="toggleCarrierRecommendation(${idx}, event)">
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 3px;">
          <input type="checkbox" class="carrier-include-checkbox" title="${isInc ? 'Desmarcar para não enviar esta opção' : 'Marcar para incluir no envio'}" ${isInc ? 'checked' : ''} onclick="toggleCarrierInclusion(${idx}, event)">
          <div class="rank-num" style="background: ${rankBg}; color: ${rankColor}; width: 22px; height: 22px; border-radius: 6px; font-size: 11px; font-weight: 800; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
            ${idx + 1}
          </div>
        </div>

        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <strong style="color: var(--text, #f8fafc); font-size: 0.95rem; letter-spacing: -0.01em;">${opt.carrier_name}</strong>
            ${badgeHtml}
            ${isRec ? `<span class="carrier-chosen-tag" style="background: rgba(0,229,153,0.15); color: var(--accent, #00e599); border: 1px solid rgba(0,229,153,0.3); font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 99px;">✓ RECOMENDADA</span>` : ""}
          </div>

          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 0.74rem; color: var(--muted, #94a3b8); margin-top: 2px;">
            <span>Tabela: <strong style="color: var(--text-secondary, #cbd5e1);">${opt.table_name}</strong></span>
            <span>•</span>
            <span>Prazo: <strong style="color: var(--text, #f8fafc);">${opt.delivery_days} dia(s) útil(eis)</strong></span>
            <span>•</span>
            ${variantSelectHtml}
          </div>

          ${breakdownHtml}
          ${contactHtml}
          ${editBoxHtml}
        </div>

        <div style="text-align: right; flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 6px;">
          <div style="font-size: 1.20rem; font-weight: 800; color: ${isCheapest ? 'var(--accent, #00e599)' : 'var(--text, #f8fafc)'}; letter-spacing: -0.02em;">
            R$ ${Number(opt.total_price).toFixed(2).replace('.', ',')}
          </div>
          <div style="display: flex; align-items: center; gap: 4px;">
            <button type="button" class="btn sm carrier-edit-btn" style="padding: 2px 7px; font-size: 0.68rem; height: 24px;" onclick="toggleEditCarrierRate(${idx}, event)" title="Ajustar valor ou prazo manualmente">
              ✏️ Ajustar
            </button>
            <button type="button" class="carrier-star-btn ${isRec ? 'recommended' : ''}" style="height: 24px; font-size: 0.68rem; padding: 2px 8px;" onclick="toggleCarrierRecommendation(${idx}, event)" title="${isRec ? 'Remover recomendação' : 'Recomendar ao cliente'}">
              ${isRec ? '⭐ Recomendada' : '☆ Recomendar'}
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

window.buildCarrierRankingHtml = buildCarrierRankingHtml;
