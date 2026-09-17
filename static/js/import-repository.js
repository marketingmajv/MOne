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

    // Pills de pastas
    const pillsCont = document.getElementById("repoFolderPills");
    pillsCont.innerHTML = (repo.folders || [])
      .filter((f) => f.count > 0)
      .map(
        (f) => `
        <span class="badge" style="font-size:10.5px;background:${f.bg};color:${f.color};border:1px solid ${f.border};font-weight:700;">
          ${f.icon} ${f.count}
        </span>
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
        const isOpen = repoState.openFolders[f.id] !== false && f.count > 0;
        const docsHtml = (f.documents || [])
          .map(
            (d) => `
          <div class="repo-doc-row">
            <div style="display:flex;align-items:center;gap:10px;overflow:hidden;flex:1;min-width:240px;">
              <span style="font-size:18px;">${getFileIcon(d.filename)}</span>
              <div style="overflow:hidden;">
                <strong style="display:block;color:var(--text);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:440px;" title="${d.title || d.filename}">
                  ${d.title || d.filename}
                </strong>
                <div style="display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);margin-top:2px;">
                  <span class="badge" style="font-size:9.5px;padding:1px 6px;background:${f.bg};color:${f.color};border:1px solid ${f.border};font-weight:700;">
                    ${d.doc_type_label}
                  </span>
                  <span>${formatBytes(d.file_size)}</span>
                  <span>•</span>
                  <span>Enviado em ${d.created_at_label || "—"}</span>
                </div>
              </div>
            </div>

            <div style="display:flex;align-items:center;gap:8px;">
              <button type="button" class="btn sm secondary" onclick="openDocumentViewer(${d.id})" style="font-size:11.5px;font-weight:700;padding:5px 10px;">
                👁️ Visualizar
              </button>
              <a href="/uploads/${d.file_url}" download="${d.filename}" class="btn sm secondary" style="font-size:11.5px;font-weight:700;padding:5px 10px;text-decoration:none;">
                ⬇️ Baixar
              </a>
            </div>
          </div>
        `
          )
          .join("");

        return `
        <div class="repo-folder-card">
          <div class="repo-folder-header" onclick="toggleRepositoryFolder('${f.id}')">
            <div style="display:flex;align-items:center;gap:10px;">
              <span style="font-size:20px;">${f.icon}</span>
              <div>
                <strong style="font-size:13.5px;color:var(--text);">${f.title}</strong>
                <p style="margin:2px 0 0 0;font-size:11.5px;color:var(--muted);">${f.description}</p>
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:12px;">
              <span class="badge" style="background:${f.bg};color:${f.color};border:1px solid ${f.border};font-size:11px;font-weight:800;padding:2px 8px;border-radius:99px;">
                ${f.count} doc(s)
              </span>
              <span id="arrow_${f.id}" style="font-size:14px;color:var(--muted);transition:transform 0.2s;transform:${isOpen ? "rotate(180deg)" : "rotate(0deg)"};">▾</span>
            </div>
          </div>
          <div id="folder_body_${f.id}" style="display:${isOpen ? "block" : "none"};">
            ${f.count > 0 ? docsHtml : '<div style="padding:14px 18px;font-size:12px;color:var(--muted);background:var(--panel);">Nenhum documento anexado nesta etapa.</div>'}
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
          <div style="margin-bottom:8px;font-size:12px;font-weight:700;color:var(--muted);">
            RESULTADOS DA BUSCA (${list.length} encontrados):
          </div>
          <div class="repo-folder-card">
            ${list
              .map(
                (d) => `
              <div class="repo-doc-row">
                <div style="display:flex;align-items:center;gap:10px;overflow:hidden;flex:1;">
                  <span style="font-size:18px;">${getFileIcon(d.filename)}</span>
                  <div style="overflow:hidden;">
                    <strong style="display:block;color:var(--text);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                      ${d.title || d.filename}
                    </strong>
                    <div style="display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted);margin-top:2px;">
                      <span class="badge" style="font-size:9.5px;padding:1px 6px;background:rgba(2,132,199,0.1);color:#0284C7;border:1px solid rgba(2,132,199,0.25);font-weight:700;">
                        ${d.doc_type_label}
                      </span>
                      <span>Pasta: ${d.folder_title}</span>
                      <span>•</span>
                      <span>${formatBytes(d.file_size)}</span>
                    </div>
                  </div>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
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
        document.getElementById("viewerDocTitle").textContent = d.title || d.filename;
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
            extData = json.parse(extData);
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
