/**
 * M-One Import Document Repository Controller (static/js/import-repository.js)
 * Gerencia a navegação em pastas temáticas do Comex, busca instantânea,
 * visualizador integrado com metadados da IA e download de pacotes ZIP.
 */

(function () {
  const repoState = {
    selectedImportId: null,
    currentTree: null,
    openFolders: {},
    allExpanded: false,
  };

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 KB";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + " " + sizes[i];
  }

  function getFileIcon(filename) {
    const ext = (filename || "").split(".").pop().toLowerCase();
    if (ext === "pdf") return "📕";
    if (["jpg", "jpeg", "png", "webp"].includes(ext)) return "🖼️";
    if (["xlsx", "xls", "csv"].includes(ext)) return "📊";
    return "📄";
  }

  function cleanDocTitle(title, filename) {
    if (!title) return filename || "Documento";
    const match = title.match(/^Documento\s*\((.*?)\)$/i);
    if (match && match[1]) return match[1];
    return title;
  }

  window.openRepositoryModal = async function (preselectedId) {
    const modal = document.getElementById("docRepositoryModal");
    if (!modal) return;

    modal.style.removeProperty("display");
    modal.style.display = "grid";
    modal.classList.add("show");

    document.getElementById("repoSearchInput").value = "";
    const sel = document.getElementById("repoImportSelect");
    sel.innerHTML = '<option value="">-- Carregando lotes... --</option>';

    try {
      const res = await fetch("/api/imports/settlement-candidates");
      const data = await res.json();
      if (data.success && data.imports) {
        let opts = '<option value="">-- Selecione o Lote de Importação --</option>';
        data.imports.forEach((imp) => {
          const selAttr = preselectedId && Number(preselectedId) === Number(imp.id) ? "selected" : "";
          opts += `<option value="${imp.id}" ${selAttr}>${imp.reference} - ${imp.supplier_name || "Sem Fornecedor"} (${imp.step || "compra"})</option>`;
        });
        sel.innerHTML = opts;

        const targetId = preselectedId || (data.imports.length > 0 ? data.imports[0].id : null);
        if (targetId) {
          sel.value = targetId;
          onRepositoryImportChange();
        }
      }
    } catch (e) {
      console.error("Erro ao listar importações:", e);
    }
  };

  window.closeRepositoryModal = function () {
    const modal = document.getElementById("docRepositoryModal");
    if (modal) {
      modal.classList.remove("show");
      modal.style.display = "none";
    }
  };

  window.onRepositoryImportChange = function () {
    const sel = document.getElementById("repoImportSelect");
    const iid = sel.value;
    repoState.selectedImportId = iid;
    repoState.openFolders = {};
    if (!iid) {
      document.getElementById("repoBodyContent").innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted);">Selecione uma importação acima para carregar os documentos.</div>';
      document.getElementById("repoTotalFilesCount").textContent = "0 arquivos";
      document.getElementById("repoTotalSize").textContent = "0 KB";
      document.getElementById("repoFolderPills").innerHTML = "";
      return;
    }
    loadRepositoryTree(iid);
  };

  window.loadRepositoryTree = async function (importId) {
    const cont = document.getElementById("repoBodyContent");
    cont.innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted);">Carregando pastas e documentos...</div>';

    try {
      const res = await fetch(`/api/imports/${importId}/repository`);
      const data = await res.json();
      if (data.success && data.repository) {
        repoState.currentTree = data.repository;
        renderRepositoryTree(data.repository);
      } else {
        cont.innerHTML = '<div style="text-align:center;padding:40px;color:#DC2626;">Erro ao carregar repositório.</div>';
      }
    } catch (e) {
      console.error("Erro no repositório:", e);
      cont.innerHTML = '<div style="text-align:center;padding:40px;color:#DC2626;">Falha na comunicação com o servidor.</div>';
    }
  };

  function renderRepositoryTree(repo) {
    document.getElementById("repoTotalFilesCount").textContent = `${repo.total_files} arquivo(s)`;
    document.getElementById("repoTotalSize").textContent = formatBytes(repo.total_bytes);

    // Pills interativas de pastas no cabeçalho
    const pillsCont = document.getElementById("repoFolderPills");
    pillsCont.innerHTML = (repo.folders || [])
      .filter((f) => f.count > 0)
      .map(
        (f) => `
        <button type="button" class="badge repo-pill-btn" onclick="focusRepositoryFolder('${f.id}')" title="Ir para ${f.title}" style="font-size:11px;background:${f.bg};color:${f.color};border:1px solid ${f.border};font-weight:700;padding:3px 8px;border-radius:6px;">
          ${f.icon} ${f.count}
        </button>
      `
      )
      .join("");

    const cont = document.getElementById("repoBodyContent");
    if (!repo.folders || !repo.folders.length || repo.total_files === 0) {
      cont.innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted);">Nenhum documento anexado a este processo até o momento.</div>';
      return;
    }

    cont.innerHTML = repo.folders
      .map((f) => {
        const hasDocs = f.count > 0;
        const isOpen = repoState.openFolders[f.id] !== undefined ? repoState.openFolders[f.id] : hasDocs;
        
        const docsHtml = (f.documents || [])
          .map(
            (d) => `
          <div class="repo-doc-row">
            <div style="display:flex;align-items:center;gap:12px;overflow:hidden;flex:1;min-width:240px;">
              <span style="font-size:22px;line-height:1;flex-shrink:0;">${getFileIcon(d.filename)}</span>
              <div style="overflow:hidden;min-width:0;">
                <strong style="display:block;color:var(--text);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3;" title="${d.title || d.filename}">
                  ${cleanDocTitle(d.title, d.filename)}
                </strong>
                <div style="display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);margin-top:3px;flex-wrap:wrap;">
                  <span class="badge" style="font-size:9.5px;padding:1px 6px;background:${f.bg};color:${f.color};border:1px solid ${f.border};font-weight:700;">
                    ${d.doc_type_label}
                  </span>
                  <span>${formatBytes(d.file_size)}</span>
                  <span>•</span>
                  <span>Enviado em ${d.created_at_label || "—"}</span>
                </div>
              </div>
            </div>

            <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
              <button type="button" class="btn sm secondary" onclick="openDocumentViewer(${d.id})" style="font-size:11.5px;font-weight:700;padding:5px 10px;display:inline-flex;align-items:center;gap:4px;">
                <span>👁️</span> Visualizar
              </button>
              <a href="/uploads/${d.file_url}" download="${d.filename}" class="btn sm secondary" style="font-size:11.5px;font-weight:700;padding:5px 10px;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
                <span>⬇️</span> Baixar
              </a>
            </div>
          </div>
        `
          )
          .join("");

        const emptyNotice = `
          <div style="padding:14px 18px;font-size:12px;color:var(--muted);background:var(--panel);border-top:1px solid var(--line);display:flex;align-items:center;gap:8px;">
            <span>ℹ️</span> Nenhum documento anexado nesta pasta até o momento.
          </div>
        `;

        return `
        <div class="repo-folder-card" id="folder_card_${f.id}" style="${hasDocs ? `border-color: ${f.border};` : 'opacity: 0.85;'}">
          <div class="repo-folder-header" onclick="toggleRepositoryFolder('${f.id}')">
            <div style="display:flex;align-items:flex-start;gap:12px;min-width:0;flex:1;">
              <span style="font-size:22px;line-height:1;margin-top:2px;flex-shrink:0;">${f.icon}</span>
              <div style="min-width:0;flex:1;">
                <strong style="font-size:14px;color:var(--text);display:block;line-height:1.3;">${f.title}</strong>
                <p style="margin:3px 0 0 0;font-size:11.5px;color:var(--muted);line-height:1.4;word-break:break-word;">${f.description}</p>
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;flex-shrink:0;margin-left:12px;">
              <span class="badge" style="background:${hasDocs ? f.bg : 'var(--panel)'};color:${hasDocs ? f.color : 'var(--muted)'};border:1px solid ${hasDocs ? f.border : 'var(--line)'};font-size:11px;font-weight:800;padding:3px 10px;border-radius:99px;">
                ${f.count} doc${f.count === 1 ? '' : 's'}
              </span>
              <span id="arrow_${f.id}" style="font-size:13px;color:var(--muted);transition:transform 0.2s;display:inline-block;transform:${isOpen ? "rotate(180deg)" : "rotate(0deg)"};">▾</span>
            </div>
          </div>
          <div id="folder_body_${f.id}" style="display:${isOpen ? "block" : "none"};">
            ${hasDocs ? docsHtml : emptyNotice}
          </div>
        </div>
      `;
      })
      .join("");
  }

  window.toggleRepositoryFolder = function (folderId) {
    const body = document.getElementById(`folder_body_${folderId}`);
    const arrow = document.getElementById(`arrow_${folderId}`);
    if (!body) return;
    const isHidden = body.style.display === "none";
    body.style.display = isHidden ? "block" : "none";
    if (arrow) arrow.style.transform = isHidden ? "rotate(180deg)" : "rotate(0deg)";
    repoState.openFolders[folderId] = isHidden;
  };

  window.toggleAllRepositoryFolders = function () {
    if (!repoState.currentTree || !repoState.currentTree.folders) return;
    repoState.allExpanded = !repoState.allExpanded;
    const btn = document.getElementById("btnToggleAllFolders");
    if (btn) {
      btn.textContent = repoState.allExpanded ? "▴ Recolher Pastas" : "▾ Expandir Pastas";
    }

    repoState.currentTree.folders.forEach((f) => {
      repoState.openFolders[f.id] = repoState.allExpanded;
      const body = document.getElementById(`folder_body_${f.id}`);
      const arrow = document.getElementById(`arrow_${f.id}`);
      if (body) body.style.display = repoState.allExpanded ? "block" : "none";
      if (arrow) arrow.style.transform = repoState.allExpanded ? "rotate(180deg)" : "rotate(0deg)";
    });
  };

  window.focusRepositoryFolder = function (folderId) {
    repoState.openFolders[folderId] = true;
    const body = document.getElementById(`folder_body_${folderId}`);
    const arrow = document.getElementById(`arrow_${folderId}`);
    if (body) body.style.display = "block";
    if (arrow) arrow.style.transform = "rotate(180deg)";

    const card = document.getElementById(`folder_card_${folderId}`);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
      card.style.outline = "2px solid #2563EB";
      setTimeout(() => {
        card.style.outline = "none";
      }, 1500);
    }
  };

  window.onRepositorySearchInput = async function (val) {
    const query = (val || "").trim();
    if (!query) {
      if (repoState.currentTree) renderRepositoryTree(repoState.currentTree);
      return;
    }

    const cont = document.getElementById("repoBodyContent");
    if (!repoState.selectedImportId) return;

    try {
      const res = await fetch(`/api/imports/${repoState.selectedImportId}/repository/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      if (data.success) {
        const list = data.results || [];
        if (!list.length) {
          cont.innerHTML = `<div style="text-align:center;padding:40px;color:var(--muted);">Nenhum documento encontrado para a busca "<strong>${query}</strong>".</div>`;
          return;
        }

        cont.innerHTML = `
          <div style="margin-bottom:8px;font-size:12px;font-weight:700;color:var(--muted);display:flex;justify-content:space-between;align-items:center;">
            <span>RESULTADOS DA BUSCA (${list.length} encontrados):</span>
            <button type="button" class="btn sm" onclick="document.getElementById('repoSearchInput').value='';onRepositorySearchInput('');" style="font-size:11px;padding:2px 8px;">✕ Limpar Busca</button>
          </div>
          <div class="repo-folder-card" style="border-color:#2563EB;">
            ${list
              .map(
                (d) => `
              <div class="repo-doc-row">
                <div style="display:flex;align-items:center;gap:12px;overflow:hidden;flex:1;">
                  <span style="font-size:22px;line-height:1;flex-shrink:0;">${getFileIcon(d.filename)}</span>
                  <div style="overflow:hidden;min-width:0;">
                    <strong style="display:block;color:var(--text);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${d.title || d.filename}">
                      ${cleanDocTitle(d.title, d.filename)}
                    </strong>
                    <div style="display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);margin-top:3px;flex-wrap:wrap;">
                      <span class="badge" style="font-size:9.5px;padding:1px 6px;background:rgba(37,99,235,0.1);color:#2563EB;border:1px solid rgba(37,99,235,0.25);font-weight:700;">
                        ${d.doc_type_label}
                      </span>
                      <span>Pasta: <strong>${d.folder_title}</strong></span>
                      <span>•</span>
                      <span>${formatBytes(d.file_size)}</span>
                    </div>
                  </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
                  <button type="button" class="btn sm secondary" onclick="openDocumentViewer(${d.id})" style="font-size:11.5px;font-weight:700;padding:5px 10px;">
                    👁️ Visualizar
                  </button>
                  <a href="/uploads/${d.file_url}" download="${d.filename}" class="btn sm secondary" style="font-size:11.5px;font-weight:700;padding:5px 10px;text-decoration:none;">
                    ⬇️ Baixar
                  </a>
                </div>
              </div>`
              )
              .join("")}
          </div>
        `;
      }
    } catch (e) {
      console.error("Erro na busca:", e);
    }
  };

  window.openDocumentViewer = async function (docId) {
    if (!repoState.selectedImportId) return;
    const modal = document.getElementById("repoDocViewerModal");
    if (!modal) return;

    modal.style.removeProperty("display");
    modal.style.display = "grid";
    modal.classList.add("show");

    // Limpar prévias
    const iframe = document.getElementById("viewerFrame");
    const img = document.getElementById("viewerImage");
    const unsup = document.getElementById("viewerUnsupportedMsg");
    iframe.style.display = "none";
    img.style.display = "none";
    unsup.style.display = "none";

    try {
      const res = await fetch(`/api/imports/${repoState.selectedImportId}/documents/${docId}/details`);
      const data = await res.json();
      if (data.success && data.document) {
        const d = data.document;
        document.getElementById("viewerDocTitle").textContent = cleanDocTitle(d.title, d.filename);
        document.getElementById("viewerDocBadge").textContent = d.doc_type;
        document.getElementById("viewerDownloadBtn").href = `/uploads/${d.file_url}`;
        document.getElementById("viewerDownloadBtn").download = d.filename;
        document.getElementById("viewerOpenTabBtn").href = `/uploads/${d.file_url}`;

        const fileUrl = `/uploads/${d.file_url}`;
        const ext = (d.filename || "").split(".").pop().toLowerCase();

        if (ext === "pdf") {
          iframe.src = fileUrl;
          iframe.style.display = "block";
        } else if (["jpg", "jpeg", "png", "webp", "gif"].includes(ext)) {
          img.src = fileUrl;
          img.style.display = "block";
        } else {
          document.getElementById("viewerFallbackDownloadBtn").href = fileUrl;
          document.getElementById("viewerFallbackDownloadBtn").download = d.filename;
          unsup.style.display = "block";
        }

        // Metadados IA
        let extData = d.extracted_data || {};
        if (typeof extData === "string") {
          try {
            extData = JSON.parse(extData);
          } catch (e) {
            extData = {};
          }
        }

        const amt = extData.total_amount ? `${extData.currency || "BRL"} ${Number(extData.total_amount).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "Não detectado";
        document.getElementById("metaDocAmount").textContent = amt;
        document.getElementById("metaDocNumber").textContent = extData.document_number || "—";
        document.getElementById("metaDocDate").textContent = extData.issue_date || "—";
        document.getElementById("metaDocSummary").textContent = extData.summary || d.title || "Sem observações adicionais.";
        document.getElementById("metaDocHash").textContent = d.file_hash ? d.file_hash.substring(0, 16) + "..." : "—";
        document.getElementById("metaDocUploader").textContent = d.uploader_name || "Sistema";
      }
    } catch (e) {
      console.error("Erro ao carregar detalhes do documento:", e);
    }
  };

  window.closeDocumentViewer = function () {
    const modal = document.getElementById("repoDocViewerModal");
    if (modal) {
      modal.classList.remove("show");
      modal.style.display = "none";
    }
    const iframe = document.getElementById("viewerFrame");
    if (iframe) iframe.src = "";
  };

  window.downloadRepositoryZip = function () {
    if (!repoState.selectedImportId) {
      alert("Selecione um lote de importação primeiro.");
      return;
    }
    window.location.href = `/api/imports/${repoState.selectedImportId}/documents/download-zip`;
  };
})();
