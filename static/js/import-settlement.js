/**
 * M-One Import Settlement & Reconciliation Controller (static/js/import-settlement.js)
 * Gerencia o wizard de 3 passos para fechamento de importação, leitura com IA e cruzamento financeiro.
 */

(function () {
  const settleState = {
    currentStep: 1,
    files: [],
    selectedImportId: null,
    baseline: null,
    detectedDocs: [],
    reconciliation: null,
  };

  const DOC_TYPE_OPTIONS = [
    { value: "FECHAMENTO_DESPACHANTE", label: "Fechamento Despachante (Prestação de Contas)" },
    { value: "ICMS_GUIDE", label: "Guias de ICMS / Comprovante de ICMS" },
    { value: "NF_FRETE_CARRETA", label: "Nota Fiscal FRETE, CARRETA" },
    { value: "AGENTE_CARGA_BR", label: "AGENTE DE CARGA BRASIL" },
    { value: "AJUDANTES_PAGTO", label: "AJUDANTES (comprovante de pagamento)" },
    { value: "EXCHANGE_CONTRACT", label: "Contrato de Câmbio" },
    { value: "SUPPLIER_PAYMENT", label: "Comprovante de Pagamento ao Fornecedor" },
    { value: "OTHER", label: "Outros Comprovantes" },
  ];

  function formatMoney(val, curr) {
    const num = Number(val) || 0;
    if (curr === "USD") {
      return "US$ " + num.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return "R$ " + num.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  window.openSettlementModal = async function (preselectedId) {
    settleState.currentStep = 1;
    settleState.files = [];
    settleState.selectedImportId = preselectedId || null;
    settleState.baseline = null;
    settleState.detectedDocs = [];
    settleState.reconciliation = null;

    const modal = document.getElementById("settlementReconciliationModal");
    if (!modal) return;
    modal.style.removeProperty("display");
    modal.style.display = "grid";
    modal.classList.add("show");

    // Reset UI
    document.getElementById("settleUserNotes").value = "";
    document.getElementById("settleCloseProcessCheckbox").checked = false;
    clearSettlementFiles();
    goToSettlementStep(1);

    // Carregar candidatos
    const sel = document.getElementById("settleImportSelect");
    sel.innerHTML = '<option value="">-- Carregando importações... --</option>';

    try {
      const res = await fetch("/api/imports/settlement-candidates");
      const data = await res.json();
      if (data.success && data.imports) {
        let opts = '<option value="">-- Selecione a Importação --</option>';
        data.imports.forEach((imp) => {
          const isClosed = imp.step === "fechado" ? " [Fechado]" : "";
          const selAttr = preselectedId && Number(preselectedId) === Number(imp.id) ? "selected" : "";
          opts += `<option value="${imp.id}" ${selAttr}>${imp.reference} - ${imp.supplier_name || "Sem Fornecedor"} (${imp.step || "compra"})${isClosed}</option>`;
        });
        sel.innerHTML = opts;

        if (preselectedId) {
          onSettlementImportChange();
        }
      } else {
        sel.innerHTML = '<option value="">Erro ao carregar lista</option>';
      }
    } catch (e) {
      console.error("Erro ao carregar candidatos:", e);
      sel.innerHTML = '<option value="">Erro na requisição</option>';
    }
  };

  window.closeSettlementModal = function () {
    const modal = document.getElementById("settlementReconciliationModal");
    if (modal) {
      modal.classList.remove("show");
      modal.style.display = "none";
    }
  };

  window.onSettlementImportChange = async function () {
    const sel = document.getElementById("settleImportSelect");
    const banner = document.getElementById("settleImportInfoBanner");
    const iid = sel.value;
    settleState.selectedImportId = iid;

    if (!iid) {
      banner.style.display = "none";
      settleState.baseline = null;
      return;
    }

    try {
      const res = await fetch(`/api/imports/${iid}/settlement-baseline`);
      const data = await res.json();
      if (data.success && data.baseline) {
        settleState.baseline = data.baseline;
        document.getElementById("settleBannerRef").textContent = data.baseline.reference || `ID #${iid}`;
        document.getElementById("settleBannerSupplier").textContent = data.baseline.supplier_name ? `• ${data.baseline.supplier_name}` : "";
        document.getElementById("settleBannerFob").textContent = formatMoney(data.baseline.pi_amount_usd || data.baseline.ci_amount_usd, "USD");
        document.getElementById("settleBannerNum").textContent = formatMoney(data.baseline.broker_advances_brl, "BRL");
        banner.style.display = "block";
      }
    } catch (e) {
      console.error("Erro ao carregar baseline:", e);
    }
  };

  window.handleSettlementFiles = function (fileList) {
    if (!fileList || fileList.length === 0) return;
    for (let i = 0; i < fileList.length; i++) {
      settleState.files.push(fileList[i]);
    }
    renderSettlementFilesList();
  };

  window.clearSettlementFiles = function () {
    settleState.files = [];
    document.getElementById("settleFileInput").value = "";
    renderSettlementFilesList();
  };

  function renderSettlementFilesList() {
    const cont = document.getElementById("settleFilesContainer");
    const list = document.getElementById("settleFilesList");
    if (!settleState.files.length) {
      cont.style.display = "none";
      list.innerHTML = "";
      return;
    }
    cont.style.display = "block";
    list.innerHTML = settleState.files
      .map(
        (f, idx) => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--panel);border:1px solid var(--line);border-radius:8px;font-size:12px;">
        <div style="display:flex;align-items:center;gap:8px;overflow:hidden;">
          <span>📄</span>
          <strong style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:320px;color:var(--text);">${f.name}</strong>
          <span style="color:var(--muted);font-size:11px;">(${(f.size / 1024).toFixed(1)} KB)</span>
        </div>
        <button type="button" onclick="removeSettlementFile(${idx})" style="background:none;border:none;color:#DC2626;cursor:pointer;font-size:16px;line-height:1;">&times;</button>
      </div>`
      )
      .join("");
  }

  window.removeSettlementFile = function (index) {
    settleState.files.splice(index, 1);
    renderSettlementFilesList();
  };

  // Drag and Drop
  document.addEventListener("DOMContentLoaded", () => {
    const dz = document.getElementById("settleDropzone");
    if (!dz) return;
    ["dragenter", "dragover"].forEach((eventName) => {
      dz.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dz.style.borderColor = "#0284C7";
        dz.style.background = "rgba(2, 132, 199, 0.05)";
      });
    });
    ["dragleave", "drop"].forEach((eventName) => {
      dz.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dz.style.borderColor = "var(--line)";
        dz.style.background = "var(--panel2)";
      });
    });
    dz.addEventListener("drop", (e) => {
      if (e.dataTransfer && e.dataTransfer.files) {
        handleSettlementFiles(e.dataTransfer.files);
      }
    });
  });

  window.goToSettlementStep = function (step) {
    settleState.currentStep = step;
    document.getElementById("settleStep1").style.display = step === 1 ? "block" : "none";
    document.getElementById("settleStep2").style.display = step === 2 ? "block" : "none";
    document.getElementById("settleStep3").style.display = step === 3 ? "block" : "none";
    document.getElementById("settleLoadingOverlay").style.display = "none";

    // Stepper Tabs
    for (let i = 1; i <= 3; i++) {
      const tab = document.getElementById(`settleTab${i}`);
      if (!tab) continue;
      if (i === step) {
        tab.classList.add("active");
        tab.style.opacity = "1";
      } else if (i < step) {
        tab.classList.remove("active");
        tab.style.opacity = "0.9";
      } else {
        tab.classList.remove("active");
        tab.style.opacity = "0.5";
      }
    }

    // Buttons
    const btnBack = document.getElementById("settleBtnBack");
    const btnNext = document.getElementById("settleBtnNext");
    btnBack.style.display = step > 1 ? "inline-block" : "none";

    if (step === 1) {
      btnNext.textContent = "Analisar com IA & Cruzar Dados ➔";
    } else if (step === 2) {
      btnNext.textContent = "Ver Cruzamento de Dados ➔";
    } else if (step === 3) {
      btnNext.textContent = "✅ Salvar Comprovantes & Concluir";
    }
  };

  window.onSettlementBack = function () {
    if (settleState.currentStep > 1) {
      goToSettlementStep(settleState.currentStep - 1);
    }
  };

  window.onSettlementNext = async function () {
    if (settleState.currentStep === 1) {
      // Validar
      if (!settleState.selectedImportId) {
        alert("Por favor, selecione a importação para o fechamento.");
        return;
      }
      if (!settleState.files.length) {
        alert("Por favor, anexe ao menos um comprovante ou prestação de contas.");
        return;
      }

      // Iniciar análise IA
      document.getElementById("settleStep1").style.display = "none";
      const overlay = document.getElementById("settleLoadingOverlay");
      overlay.style.display = "block";
      document.getElementById("settleLoadingTitle").textContent = "Processando com IA...";
      document.getElementById("settleLoadingMsg").textContent = `Lendo ${settleState.files.length} comprovante(s) e extraindo metadados...`;

      const fd = new FormData();
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
      if (csrfToken) fd.append("csrf_token", csrfToken);
      fd.append("import_id", settleState.selectedImportId);
      fd.append("document_notes", document.getElementById("settleUserNotes").value.trim());
      settleState.files.forEach((f) => fd.append("documents", f));

      try {
        const res = await fetch("/api/imports/analyze-settlement", {
          method: "POST",
          body: fd,
        });
        const data = await res.json();
        overlay.style.display = "none";

        if (!data.success) {
          alert("Erro na análise: " + (data.error || "Tente novamente."));
          goToSettlementStep(1);
          return;
        }

        settleState.detectedDocs = data.detected_docs || [];
        settleState.reconciliation = data.reconciliation || {};
        settleState.baseline = data.baseline || settleState.baseline;

        renderStep2Docs();
        goToSettlementStep(2);
      } catch (err) {
        console.error(err);
        overlay.style.display = "none";
        alert("Erro na comunicação com o servidor.");
        goToSettlementStep(1);
      }
    } else if (settleState.currentStep === 2) {
      // Aplicar eventuais reclassificações manuais feitas pelo usuário
      settleState.detectedDocs.forEach((doc, idx) => {
        const sel = document.getElementById(`settleDocTypeSelect_${idx}`);
        if (sel) doc.doc_type = sel.value;
        const amtInput = document.getElementById(`settleDocAmtInput_${idx}`);
        if (amtInput) doc.total_amount = parseFloat(amtInput.value) || 0;
      });

      renderStep3Reconciliation();
      goToSettlementStep(3);
    } else if (settleState.currentStep === 3) {
      // Commit
      const closeProcess = document.getElementById("settleCloseProcessCheckbox").checked;
      const btnNext = document.getElementById("settleBtnNext");
      btnNext.disabled = true;
      btnNext.textContent = "Gravando conciliação...";

      try {
        const res = await fetch(`/api/imports/${settleState.selectedImportId}/commit-settlement`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            detected_docs: settleState.detectedDocs,
            close_process: closeProcess,
          }),
        });
        const data = await res.json();
        if (data.success) {
          alert(data.message || "Fechamento e conciliação concluídos com sucesso!");
          window.location.reload();
        } else {
          alert("Erro ao gravar: " + (data.error || "Tente novamente."));
          btnNext.disabled = false;
          btnNext.textContent = "✅ Salvar Comprovantes & Concluir";
        }
      } catch (err) {
        console.error(err);
        alert("Erro na comunicação ao salvar conciliação.");
        btnNext.disabled = false;
        btnNext.textContent = "✅ Salvar Comprovantes & Concluir";
      }
    }
  };

  function renderStep2Docs() {
    const list = document.getElementById("settleDetectedDocsList");
    const badge = document.getElementById("settleDocsCountBadge");
    badge.textContent = `${settleState.detectedDocs.length} comprovante(s)`;

    if (!settleState.detectedDocs.length) {
      list.innerHTML = '<div style="text-align:center;padding:20px;color:var(--muted);">Nenhum documento processado.</div>';
      return;
    }

    list.innerHTML = settleState.detectedDocs
      .map((doc, idx) => {
        const opts = DOC_TYPE_OPTIONS.map(
          (opt) => `<option value="${opt.value}" ${opt.value === doc.doc_type ? "selected" : ""}>${opt.label}</option>`
        ).join("");

        return `
        <div style="padding:14px 16px;border-radius:12px;background:var(--panel2);border:1px solid var(--line);display:flex;flex-direction:column;gap:10px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;">
            <div style="flex:1;min-width:240px;">
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:16px;">📄</span>
                <strong style="font-size:13.5px;color:var(--text);">${doc.title || doc.filename}</strong>
              </div>
              <p style="margin:4px 0 0 24px;font-size:11.5px;color:var(--muted);">${doc.summary || "Sem resumo adicional da IA."}</p>
            </div>
            <div style="display:flex;align-items:center;gap:12px;">
              <div>
                <label style="font-size:10.5px;font-weight:700;color:var(--muted);display:block;margin-bottom:2px;">VALOR DETECTADO</label>
                <div style="display:flex;align-items:center;gap:4px;">
                  <span style="font-size:12px;font-weight:700;color:var(--muted);">${doc.currency || "BRL"}</span>
                  <input type="number" step="0.01" id="settleDocAmtInput_${idx}" value="${Number(doc.total_amount || 0).toFixed(2)}" style="width:110px;height:32px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--text);padding:0 8px;font-size:13px;font-weight:700;text-align:right;">
                </div>
              </div>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:10px;padding-top:6px;border-top:1px dashed var(--line);">
            <label style="font-size:11px;font-weight:700;color:var(--muted);white-space:nowrap;">Classificação:</label>
            <select id="settleDocTypeSelect_${idx}" style="flex:1;height:32px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--text);padding:0 10px;font-size:12px;font-weight:600;">
              ${opts}
            </select>
          </div>
        </div>
      `;
      })
      .join("");
  }

  function renderStep3Reconciliation() {
    const base = settleState.baseline || {};
    const rec = settleState.reconciliation || {};
    const items = rec.items || [];

    // Preencher KPIs
    const adv = Number(base.broker_advances_brl) || 0;
    const provBroker = Number(rec.totals_proven?.fechamento_despachante) || Number(base.broker_proven_brl) || 0;
    const balBroker = adv - provBroker;

    document.getElementById("settleKpiAdv").textContent = formatMoney(adv, "BRL");
    document.getElementById("settleKpiProven").textContent = formatMoney(provBroker, "BRL");

    const kpiBal = document.getElementById("settleKpiBalance");
    if (balBroker > 0) {
      kpiBal.textContent = `${formatMoney(balBroker, "BRL")} (A Devolver)`;
      kpiBal.style.color = "#059669";
    } else if (balBroker < 0) {
      kpiBal.textContent = `${formatMoney(Math.abs(balBroker), "BRL")} (A Complementar)`;
      kpiBal.style.color = "#DC2626";
    } else {
      kpiBal.textContent = "R$ 0,00 (Zerado)";
      kpiBal.style.color = "#0284C7";
    }

    // Tabela
    const tbody = document.getElementById("settleReconciliationTableBody");
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--muted);">Nenhum item de conciliação disponível.</td></tr>';
      return;
    }

    tbody.innerHTML = items
      .map((item) => {
        let badgeBg = "rgba(107, 114, 128, 0.12)";
        let badgeColor = "#6B7280";
        let badgeBorder = "rgba(107, 114, 128, 0.25)";
        let badgeText = "Pendente";

        if (item.status === "reconciled" || item.status === "ok") {
          badgeBg = "rgba(16, 185, 129, 0.12)";
          badgeColor = "#059669";
          badgeBorder = "rgba(16, 185, 129, 0.25)";
          badgeText = "✓ Conciliado";
        } else if (item.status === "refund_due") {
          badgeBg = "rgba(2, 132, 199, 0.12)";
          badgeColor = "#0284C7";
          badgeBorder = "rgba(2, 132, 199, 0.25)";
          badgeText = "Restituição a Receber";
        } else if (item.status === "complement_due") {
          badgeBg = "rgba(239, 68, 68, 0.12)";
          badgeColor = "#DC2626";
          badgeBorder = "rgba(239, 68, 68, 0.25)";
          badgeText = "Complemento a Pagar";
        } else if (item.status === "divergent") {
          badgeBg = "rgba(245, 158, 11, 0.12)";
          badgeColor = "#D97706";
          badgeBorder = "rgba(245, 158, 11, 0.25)";
          badgeText = "⚠ Divergência";
        }

        return `
        <tr style="border-bottom:1px solid var(--line);">
          <td style="padding:12px 16px;">
            <strong style="color:var(--text);font-size:13px;display:block;">${item.title}</strong>
            <small style="color:var(--muted);font-size:11px;">${item.detail || ""}</small>
          </td>
          <td style="padding:12px 16px;text-align:right;font-weight:600;color:var(--text);">
            ${item.expected_label}
          </td>
          <td style="padding:12px 16px;text-align:right;font-weight:700;color:#059669;">
            ${item.proven_label}
          </td>
          <td style="padding:12px 16px;text-align:center;">
            <span class="badge" style="background:${badgeBg};color:${badgeColor};border:1px solid ${badgeBorder};font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px;">
              ${badgeText}
            </span>
          </td>
        </tr>
      `;
      })
      .join("");
  }
})();
