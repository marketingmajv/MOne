/*
 * M-One WhatsApp Automation Studio & Interactive Graph Builder (static/js/automation_studio.js)
 * Versão 5.0 - Editor Funcional Completo: Inspector com Múltiplas Opções, Formatação CRM,
 * Portas Dinâmicas (valid/invalid/timeout/options), Conexões Removíveis, Prevenção XSS e Grafo Fiel.
 */

let flowGraph = {
  id: 1,
  name: "Menu Principal & Qualificação MAJ",
  status: "draft",
  nodes: [
    {
      id: "node_trigger",
      type: "trigger",
      label: "Gatilho: Palavras-chave",
      config: { keywords: ["ola", "olá", "menu", "ajuda", "inicio"] },
      position: { x: 60, y: 100 }
    },
    {
      id: "node_welcome",
      type: "send_message",
      label: "Boas-Vindas MAJ",
      config: { text: "👋 Olá! Seja bem-vindo à *MAJ Mobilidade Elétrica*!\nComo podemos te ajudar hoje?" },
      position: { x: 380, y: 100 }
    },
    {
      id: "node_menu",
      type: "send_menu",
      label: "Menu de Opções",
      config: {
        title: "Escolha uma opção:",
        options: [
          { id: "opt_catalog", text: "1. Ver Veículos Elétricos" },
          { id: "opt_freight", text: "2. Cotar Frete" },
          { id: "opt_human", text: "3. Falar com Vendedor" }
        ],
        save_variable: "menu_choice"
      },
      position: { x: 700, y: 100 }
    },
    {
      id: "node_ask_email",
      type: "ask_question",
      label: "Coletar E-mail",
      config: { text: "Por favor, informe seu e-mail corporativo:", validation: "email", save_variable: "lead_email", timeout_seconds: 300 },
      position: { x: 1020, y: 100 }
    },
    {
      id: "node_crm_task",
      type: "action",
      label: "Criar Tarefa no CRM",
      config: { action_type: "create_task", task_title: "Follow-up Lead WhatsApp", assigned_to: "fauzer", due_days: 1 },
      position: { x: 1340, y: 100 }
    }
  ],
  edges: [
    { id: "e1", source: "node_trigger", target: "node_welcome" },
    { id: "e2", source: "node_welcome", target: "node_menu" },
    { id: "e3", source: "node_menu", target: "node_ask_email", source_handle: "opt_catalog" },
    { id: "e4", source: "node_ask_email", target: "node_crm_task", source_handle: "valid" }
  ]
};

let selectedNodeId = null;
let scale = 1.0;
let panOffset = { x: 0, y: 0 };
let isPanning = false;
let startPanPos = { x: 0, y: 0 };

let undoStack = [];
let redoStack = [];
let activeSimulatorNodeId = null;
let simulatorVariables = {};

// Auxiliary XSS Escaping Helper
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
  renderGraph();
  setupCanvasPanning();
});

// ==========================================
// GRAPH RENDERER & SVG CONNECTIONS
// ==========================================

function renderGraph() {
  const nodesLayer = document.getElementById("nodesLayer");
  const svgLayer = document.getElementById("svgConnectionsLayer");

  if (!nodesLayer || !svgLayer) return;

  nodesLayer.style.transform = `translate(${panOffset.x}px, ${panOffset.y}px) scale(${scale})`;
  nodesLayer.innerHTML = "";
  
  svgLayer.innerHTML = `
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#0070F3" />
      </marker>
      <marker id="arrow-green" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
      </marker>
      <marker id="arrow-red" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#f43f5e" />
      </marker>
    </defs>
  `;

  // Render node cards
  flowGraph.nodes.forEach(n => {
    const card = createNodeCardElement(n);
    nodesLayer.appendChild(card);
  });

  // Render SVG connections
  flowGraph.edges.forEach(e => {
    drawEdgeLine(e);
  });
}

function createNodeCardElement(node) {
  const div = document.createElement("div");
  div.id = node.id;
  div.className = `node-card ${selectedNodeId === node.id ? 'selected' : ''}`;
  div.style.left = `${node.position.x}px`;
  div.style.top = `${node.position.y}px`;

  let typeBadge = "💬 MENSAGEM";
  let badgeStyle = "background: rgba(52, 211, 153, 0.2); color: #34d399;";
  
  if (node.type === "trigger") {
    typeBadge = "⚡ GATILHO";
    badgeStyle = "background: rgba(56, 189, 248, 0.2); color: #38bdf8;";
  } else if (node.type === "send_menu" || node.type === "interactive") {
    typeBadge = "📋 MENU";
    badgeStyle = "background: rgba(52, 211, 153, 0.2); color: #34d399;";
  } else if (node.type === "ask_question") {
    typeBadge = "❓ PERGUNTA";
    badgeStyle = "background: rgba(251, 191, 36, 0.2); color: #fbbf24;";
  } else if (node.type === "condition") {
    typeBadge = "🔀 CONDIÇÃO";
    badgeStyle = "background: rgba(192, 132, 252, 0.2); color: #c084fc;";
  } else if (node.type === "delay") {
    typeBadge = "⏳ DELAY";
    badgeStyle = "background: rgba(192, 132, 252, 0.2); color: #c084fc;";
  } else if (node.type === "webhook") {
    typeBadge = "🌐 WEBHOOK";
    badgeStyle = "background: rgba(192, 132, 252, 0.2); color: #c084fc;";
  } else if (node.type === "action") {
    typeBadge = "🛠️ AÇÃO CRM";
    badgeStyle = "background: rgba(244, 63, 94, 0.2); color: #f43f5e;";
  } else if (node.type === "transfer_agent" || node.type === "transfer") {
    typeBadge = "👨‍💼 HUMANO";
    badgeStyle = "background: rgba(244, 63, 94, 0.2); color: #f43f5e;";
  } else if (node.type === "ai_reply") {
    typeBadge = "🤖 IA COPILOT";
    badgeStyle = "background: rgba(56, 189, 248, 0.2); color: #38bdf8;";
  } else if (node.type === "end") {
    typeBadge = "🏁 FIM";
    badgeStyle = "background: rgba(148, 163, 184, 0.2); color: #94a3b8;";
  }

  let previewText = node.config.text || node.config.title || (node.config.keywords ? node.config.keywords.join(", ") : "");
  if (!previewText && node.config.action_type) previewText = `Ação: ${node.config.action_type}`;
  if (!previewText && node.config.url) previewText = `URL: ${node.config.url}`;
  if (previewText.length > 45) previewText = previewText.substring(0, 45) + "...";

  let bodyHtml = `
    <strong class="node-title">${escapeHtml(node.label)}</strong>
    <p class="node-preview">${escapeHtml(previewText || 'Clique para configurar...')}</p>
  `;

  // Dynamic Output Ports for Menus, Perguntas and Conditions
  let extraPortsHtml = "";
  if ((node.type === "send_menu" || node.type === "interactive") && node.config.options && node.config.options.length > 0) {
    extraPortsHtml += `<div style="margin-top: 8px; font-size: 0.72rem;">`;
    node.config.options.forEach((opt, idx) => {
      const handleId = opt.id || `opt_${idx}`;
      extraPortsHtml += `
        <div class="multi-port-row">
          <span>🔹 ${escapeHtml(opt.text || handleId)}</span>
          <div class="multi-port-handle" id="port_${node.id}_${handleId}" title="Porta: ${escapeHtml(handleId)}"></div>
        </div>
      `;
    });
    extraPortsHtml += `</div>`;
  } else if (node.type === "ask_question") {
    extraPortsHtml += `
      <div style="margin-top: 8px; font-size: 0.7rem; color: #94a3b8;">
        <div class="multi-port-row"><span style="color: #34d399;">✓ Resposta Válida</span><div class="multi-port-handle" style="background:#34d399; box-shadow:0 0 6px #34d399;"></div></div>
        <div class="multi-port-row"><span style="color: #fbbf24;">⚠️ Inválida</span><div class="multi-port-handle" style="background:#fbbf24; box-shadow:0 0 6px #fbbf24;"></div></div>
        <div class="multi-port-row"><span style="color: #f43f5e;">⏳ Timeout (${node.config.timeout_seconds || 300}s)</span><div class="multi-port-handle" style="background:#f43f5e; box-shadow:0 0 6px #f43f5e;"></div></div>
      </div>
    `;
  } else if (node.type === "condition") {
    extraPortsHtml += `
      <div style="margin-top: 8px; font-size: 0.7rem;">
        <div class="multi-port-row"><span style="color: #34d399;">Verdadeiro (True)</span><div class="multi-port-handle" style="background:#34d399;"></div></div>
        <div class="multi-port-row"><span style="color: #f43f5e;">Falso (False)</span><div class="multi-port-handle" style="background:#f43f5e;"></div></div>
      </div>
    `;
  }

  div.innerHTML = `
    <div class="node-header" onclick="selectNode('${node.id}')">
      <span class="node-type-badge" style="${badgeStyle}">${typeBadge}</span>
      <div class="node-actions">
        <button type="button" onclick="duplicateNode('${node.id}', event)" class="node-action-btn" title="Duplicar">📋</button>
        <button type="button" onclick="deleteNode('${node.id}', event)" class="node-action-btn" style="color: #f87171 !important;" title="Excluir">🗑️</button>
      </div>
    </div>
    <div class="node-body" onclick="selectNode('${node.id}')">
      ${bodyHtml}
      ${extraPortsHtml}
    </div>
    ${node.type !== 'trigger' ? '<div class="port-input" title="Entrada"></div>' : ''}
    ${node.type !== 'end' && node.type !== 'send_menu' ? '<div class="port-output" title="Saída Padrão"></div>' : ''}
  `;

  makeNodeDraggable(div, node);
  return div;
}

function makeNodeDraggable(elem, node) {
  let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
  elem.onmousedown = (e) => {
    if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.classList.contains('node-action-btn')) return;
    e.stopPropagation();
    
    selectNode(node.id);
    pos3 = e.clientX;
    pos4 = e.clientY;

    document.onmousemove = (e2) => {
      e2.preventDefault();
      pos1 = (pos3 - e2.clientX) / scale;
      pos2 = (pos4 - e2.clientY) / scale;
      pos3 = e2.clientX;
      pos4 = e2.clientY;

      node.position.x = Math.max(10, Math.round(node.position.x - pos1));
      node.position.y = Math.max(10, Math.round(node.position.y - pos2));
      elem.style.left = `${node.position.x}px`;
      elem.style.top = `${node.position.y}px`;

      renderGraph();
    };

    document.onmouseup = () => {
      document.onmousemove = null;
      document.onmouseup = null;
    };
  };
}

function drawEdgeLine(edge) {
  const srcNode = flowGraph.nodes.find(n => n.id === edge.source);
  const tgtNode = flowGraph.nodes.find(n => n.id === edge.target);
  if (!srcNode || !tgtNode) return;

  const svgLayer = document.getElementById("svgConnectionsLayer");
  
  const x1 = (srcNode.position.x + 270 + panOffset.x) * scale;
  const y1 = (srcNode.position.y + 38 + panOffset.y) * scale;
  
  const x2 = (tgtNode.position.x + panOffset.x) * scale;
  const y2 = (tgtNode.position.y + 38 + panOffset.y) * scale;

  const dx = Math.max(40, (x2 - x1) / 2);
  const pathD = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;

  const g = document.createElementNS("http://www.w3.org/2000/svg", "g");

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathD);
  path.setAttribute("stroke", edge.source_handle === "invalid" || edge.source_handle === "timeout" ? "#f43f5e" : "#0070F3");
  path.setAttribute("stroke-width", "2.5");
  path.setAttribute("fill", "none");
  path.setAttribute("marker-end", edge.source_handle === "invalid" || edge.source_handle === "timeout" ? "url(#arrow-red)" : "url(#arrow)");

  // Midpoint delete button handle
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;

  const deleteCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  deleteCircle.setAttribute("cx", midX);
  deleteCircle.setAttribute("cy", midY);
  deleteCircle.setAttribute("r", "9");
  deleteCircle.setAttribute("fill", "#1e293b");
  deleteCircle.setAttribute("stroke", "#f87171");
  deleteCircle.setAttribute("stroke-width", "1.5");
  deleteCircle.setAttribute("style", "cursor: pointer; pointer-events: all;");

  const deleteText = document.createElementNS("http://www.w3.org/2000/svg", "text");
  deleteText.setAttribute("x", midX);
  deleteText.setAttribute("y", midY + 3.5);
  deleteText.setAttribute("fill", "#f87171");
  deleteText.setAttribute("font-size", "11");
  deleteText.setAttribute("font-weight", "bold");
  deleteText.setAttribute("text-anchor", "middle");
  deleteText.setAttribute("style", "cursor: pointer; pointer-events: all; user-select: none;");
  deleteText.textContent = "×";

  const deleteAction = (ev) => {
    ev.stopPropagation();
    deleteEdge(edge.id);
  };

  deleteCircle.onclick = deleteAction;
  deleteText.onclick = deleteAction;

  g.appendChild(path);
  g.appendChild(deleteCircle);
  g.appendChild(deleteText);

  svgLayer.appendChild(g);
}

function deleteEdge(edgeId) {
  saveHistoryState();
  flowGraph.edges = flowGraph.edges.filter(e => e.id !== edgeId);
  renderGraph();
  if (selectedNodeId) selectNode(selectedNodeId);
}

// ==========================================
// DRAG & DROP BIBLIOTECA PARA CANVAS
// ==========================================

function onBlockDragStart(e, type, label) {
  e.dataTransfer.setData("application/json", JSON.stringify({ type, label }));
}

function onCanvasDragOver(e) {
  e.preventDefault();
}

function onCanvasDrop(e) {
  e.preventDefault();
  const raw = e.dataTransfer.getData("application/json");
  if (!raw) return;

  const data = JSON.parse(raw);
  const rect = document.getElementById("canvasContainer").getBoundingClientRect();
  
  const x = Math.round((e.clientX - rect.left - panOffset.x) / scale);
  const y = Math.round((e.clientY - rect.top - panOffset.y) / scale);

  const newNodeId = `node_${Date.now()}`;
  const newNode = {
    id: newNodeId,
    type: data.type,
    label: data.label,
    config: getDefaultConfigForType(data.type),
    position: { x, y }
  };

  saveHistoryState();
  flowGraph.nodes.push(newNode);
  
  // IMPORTANTE: Não conectar automaticamente novo bloco ao último bloco sem intenção do usuário!
  // O nó é inserido isolado para o usuário realizar as conexões deliberadamente.

  selectNode(newNodeId);
  renderGraph();
}

function getDefaultConfigForType(type) {
  if (type === "trigger") return { keywords: ["ola", "menu"] };
  if (type === "send_media") return { media_type: "image", media_url: "https://m-one.majmobilidade.com.br/static/img/banner.jpg", caption: "Confira nossas fotos e documentos!" };
  if (type === "send_message") return { text: "👋 Olá! Como podemos te ajudar?" };
  if (type === "send_menu" || type === "interactive") {
    return {
      title: "Escolha uma opção:",
      save_variable: "menu_choice",
      options: [
        { id: "opt_1", text: "1. Opção Um" },
        { id: "opt_2", text: "2. Opção Dois" }
      ]
    };
  }
  if (type === "ask_question") return { text: "Por favor, digite seu e-mail:", validation: "email", save_variable: "lead_email", timeout_seconds: 300 };
  if (type === "condition") return { variable: "menu_choice", operator: "equals", value: "1" };
  if (type === "delay") return { seconds: 5 };
  if (type === "webhook") return { method: "POST", url: "https://api.exemplo.com/webhook", headers: "{}", payload: "{}" };
  if (type === "action") return { action_type: "update_stage", status: "em_atendimento", assigned_to: "fauzer", task_title: "Follow-up WhatsApp", due_days: 1 };
  if (type === "transfer_agent" || type === "transfer") return { assigned_to: "fauzer", message: "👨‍💼 Transferindo seu atendimento para Fauzer...", pause_bot: true };
  if (type === "ai_reply") return { provider: "openai", prompt: "Você é um assistente da MAJ..." };
  if (type === "end") return {};
  return { text: "" };
}

// ==========================================
// NODES SELECTION & INSPECTOR PANEL COMPLETO
// ==========================================

function selectNode(id) {
  selectedNodeId = id;
  renderGraph();

  const panel = document.getElementById("nodeInspectorPanel");
  const form = document.getElementById("inspectorFormContent");
  const title = document.getElementById("inspectorNodeTitle");
  if (!panel || !form) return;

  const node = flowGraph.nodes.find(n => n.id === id);
  if (!node) return;

  title.innerText = `Configurar: ${node.label}`;
  
  let html = `
    <div class="inspector-field">
      <label>Nome do Bloco</label>
      <input type="text" value="${escapeHtml(node.label)}" onchange="updateNodeProp('${id}', 'label', this.value)" class="inspector-input">
    </div>
  `;

  if (node.type === "trigger") {
    const kws = (node.config.keywords || []).join(", ");
    html += `
      <div class="inspector-field">
        <label>Palavras-chave (separadas por vírgula)</label>
        <textarea onchange="updateNodeConfigKws('${id}', this.value)" class="inspector-textarea" rows="3">${escapeHtml(kws)}</textarea>
      </div>
    `;
  } else if (node.type === "send_media") {
    const mType = node.config.media_type || "image";
    const mUrl = node.config.media_url || "";
    const caption = node.config.caption || "";
    html += `
      <div class="inspector-field">
        <label>Tipo de Mídia Meta</label>
        <select onchange="updateNodeConfigProp('${id}', 'media_type', this.value)" class="inspector-select">
          <option value="image" ${mType === 'image' ? 'selected' : ''}>Imagem (JPG/PNG)</option>
          <option value="document" ${mType === 'document' ? 'selected' : ''}>Documento (PDF/Doc)</option>
          <option value="audio" ${mType === 'audio' ? 'selected' : ''}>Áudio (MP3/OGG)</option>
          <option value="video" ${mType === 'video' ? 'selected' : ''}>Vídeo (MP4)</option>
        </select>
      </div>
      <div class="inspector-field">
        <label>URL da Mídia (HTTP/HTTPS Público)</label>
        <input type="url" value="${escapeHtml(mUrl)}" onchange="updateNodeConfigProp('${id}', 'media_url', this.value)" class="inspector-input" placeholder="https://exemplo.com/arquivo.jpg">
      </div>
      <div class="inspector-field">
        <label>Legenda / Descrição</label>
        <textarea onchange="updateNodeConfigProp('${id}', 'caption', this.value)" class="inspector-textarea" rows="3" placeholder="Legenda opcional...">${escapeHtml(caption)}</textarea>
      </div>
    `;
  } else if (node.type === "send_message") {
    const txt = node.config.text || "";
    html += `
      <div class="inspector-field">
        <label>Conteúdo da Mensagem</label>
        <textarea onchange="updateNodeConfigText('${id}', this.value)" class="inspector-textarea" rows="4" placeholder="Digite a mensagem do robô...">${escapeHtml(txt)}</textarea>
      </div>
    `;
  } else if (node.type === "send_menu" || node.type === "interactive") {
    const titleText = node.config.title || "";
    const saveVar = node.config.save_variable || "menu_choice";
    const options = node.config.options || [];

    let optionsListHtml = "";
    options.forEach((opt, idx) => {
      optionsListHtml += `
        <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 8px; margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <strong style="font-size: 0.76rem; color: #38bdf8;">Opção #${idx + 1}</strong>
            <div style="display: flex; gap: 4px;">
              <button type="button" class="btn tiny" onclick="moveMenuOption('${id}', ${idx}, -1)" title="Subir">⬆️</button>
              <button type="button" class="btn tiny" onclick="moveMenuOption('${id}', ${idx}, 1)" title="Descer">⬇️</button>
              <button type="button" class="btn tiny" style="color:#f87171;" onclick="removeMenuOption('${id}', ${idx})" title="Excluir">🗑️</button>
            </div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <input type="text" placeholder="Texto da Opção (ex: 1. Ver Carros)" value="${escapeHtml(opt.text)}" onchange="updateMenuOptionProp('${id}', ${idx}, 'text', this.value)" class="inspector-input" style="font-size: 0.78rem !important;">
            <input type="text" placeholder="ID da Opção (ex: opt_catalog)" value="${escapeHtml(opt.id)}" onchange="updateMenuOptionProp('${id}', ${idx}, 'id', this.value)" class="inspector-input" style="font-size: 0.72rem !important; opacity: 0.8;">
          </div>
        </div>
      `;
    });

    html += `
      <div class="inspector-field">
        <label>Título do Menu</label>
        <input type="text" value="${escapeHtml(titleText)}" onchange="updateNodeConfigProp('${id}', 'title', this.value)" class="inspector-input">
      </div>
      <div class="inspector-field">
        <label>Salvar Escolha na Variável</label>
        <input type="text" value="${escapeHtml(saveVar)}" onchange="updateNodeConfigProp('${id}', 'save_variable', this.value)" class="inspector-input">
      </div>
      <div class="inspector-field">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <label style="margin:0;">Opções do Menu (${options.length})</label>
          <button type="button" class="btn tiny primary" onclick="addMenuOption('${id}')">+ Adicionar Opção</button>
        </div>
        ${optionsListHtml || '<div style="font-size: 0.75rem; color: #94a3b8;">Nenhuma opção cadastrada.</div>'}
      </div>
    `;
  } else if (node.type === "ask_question") {
    const txt = node.config.text || "";
    const valRule = node.config.validation || "email";
    const saveVar = node.config.save_variable || "user_response";
    const timeoutSec = node.config.timeout_seconds || 300;

    html += `
      <div class="inspector-field">
        <label>Texto da Pergunta</label>
        <textarea onchange="updateNodeConfigText('${id}', this.value)" class="inspector-textarea" rows="3">${escapeHtml(txt)}</textarea>
      </div>
      <div class="inspector-field">
        <label>Validação do Formato</label>
        <select onchange="updateNodeConfigProp('${id}', 'validation', this.value)" class="inspector-select">
          <option value="text" ${valRule === 'text' ? 'selected' : ''}>Texto Livre</option>
          <option value="email" ${valRule === 'email' ? 'selected' : ''}>Endereço de E-mail</option>
          <option value="number" ${valRule === 'number' ? 'selected' : ''}>Número Inteiro</option>
          <option value="phone" ${valRule === 'phone' ? 'selected' : ''}>Telefone / WhatsApp</option>
        </select>
      </div>
      <div class="inspector-field">
        <label>Salvar na Variável</label>
        <input type="text" value="${escapeHtml(saveVar)}" onchange="updateNodeConfigProp('${id}', 'save_variable', this.value)" class="inspector-input">
      </div>
      <div class="inspector-field">
        <label>Timeout (Tempo Limite em Segundos)</label>
        <input type="number" value="${timeoutSec}" onchange="updateNodeConfigProp('${id}', 'timeout_seconds', parseInt(this.value))" class="inspector-input" min="30" max="86400">
      </div>
    `;
  } else if (node.type === "condition") {
    const varName = node.config.variable || "menu_choice";
    const op = node.config.operator || "equals";
    const val = node.config.value || "1";
    html += `
      <div class="inspector-field">
        <label>Variável de Teste</label>
        <input type="text" value="${escapeHtml(varName)}" onchange="updateNodeConfigProp('${id}', 'variable', this.value)" class="inspector-input">
      </div>
      <div class="inspector-field">
        <label>Operador Lógico</label>
        <select onchange="updateNodeConfigProp('${id}', 'operator', this.value)" class="inspector-select">
          <option value="equals" ${op === 'equals' ? 'selected' : ''}>Igual a (==)</option>
          <option value="contains" ${op === 'contains' ? 'selected' : ''}>Contém texto</option>
          <option value="greater_than" ${op === 'greater_than' ? 'selected' : ''}>Maior que (&gt;)</option>
        </select>
      </div>
      <div class="inspector-field">
        <label>Valor de Comparação</label>
        <input type="text" value="${escapeHtml(val)}" onchange="updateNodeConfigProp('${id}', 'value', this.value)" class="inspector-input">
      </div>
    `;
  } else if (node.type === "action") {
    const actType = node.config.action_type || "update_stage";
    const status = node.config.status || "em_atendimento";
    const assigned = node.config.assigned_to || "fauzer";
    const taskTitle = node.config.task_title || node.config.title || "Follow-up Lead WhatsApp";
    const dueDays = node.config.due_days || 1;
    const notes = node.config.notes || "";

    html += `
      <div class="inspector-field">
        <label>Tipo de Ação no CRM</label>
        <select onchange="updateNodeConfigProp('${id}', 'action_type', this.value)" class="inspector-select">
          <option value="create_lead" ${actType === 'create_lead' ? 'selected' : ''}>Criar Novo Lead</option>
          <option value="update_stage" ${actType === 'update_stage' ? 'selected' : ''}>Mudar Etapa do Funil</option>
          <option value="assign_seller" ${actType === 'assign_seller' ? 'selected' : ''}>Atribuir Vendedor</option>
          <option value="create_task" ${actType === 'create_task' ? 'selected' : ''}>Criar Tarefa de CRM</option>
          <option value="follow_up" ${actType === 'follow_up' ? 'selected' : ''}>Agendar Follow-up</option>
          <option value="update_lead" ${actType === 'update_lead' ? 'selected' : ''}>Atualizar Lead</option>
        </select>
      </div>
    `;

    if (actType === "update_stage") {
      html += `
        <div class="inspector-field">
          <label>Nova Etapa do Lead</label>
          <select onchange="updateNodeConfigProp('${id}', 'status', this.value)" class="inspector-select">
            <option value="novo" ${status === 'novo' ? 'selected' : ''}>Novo Lead</option>
            <option value="em_atendimento" ${status === 'em_atendimento' ? 'selected' : ''}>Em Atendimento</option>
            <option value="proposta" ${status === 'proposta' ? 'selected' : ''}>Proposta Enviada</option>
            <option value="qualificado" ${status === 'qualificado' ? 'selected' : ''}>Qualificado</option>
            <option value="fechado" ${status === 'fechado' ? 'selected' : ''}>Venda Concluída</option>
            <option value="perdido" ${status === 'perdido' ? 'selected' : ''}>Perdido</option>
          </select>
        </div>
      `;
    } else if (actType === "assign_seller") {
      html += `
        <div class="inspector-field">
          <label>Vendedor Responsável</label>
          <select onchange="updateNodeConfigProp('${id}', 'assigned_to', this.value)" class="inspector-select">
            <option value="fauzer" ${assigned === 'fauzer' ? 'selected' : ''}>Fauzer (Diretoria / Vendas)</option>
            <option value="jam" ${assigned === 'jam' ? 'selected' : ''}>Jam (Diretoria / Vendas)</option>
            <option value="fila_geral" ${assigned === 'fila_geral' ? 'selected' : ''}>Fila Geral de Vendas</option>
          </select>
        </div>
      `;
    } else if (actType === "create_task" || actType === "follow_up") {
      html += `
        <div class="inspector-field">
          <label>Título da Tarefa / Follow-up</label>
          <input type="text" value="${escapeHtml(taskTitle)}" onchange="updateNodeConfigProp('${id}', 'task_title', this.value)" class="inspector-input">
        </div>
        <div class="inspector-field">
          <label>Responsável</label>
          <select onchange="updateNodeConfigProp('${id}', 'assigned_to', this.value)" class="inspector-select">
            <option value="fauzer" ${assigned === 'fauzer' ? 'selected' : ''}>Fauzer</option>
            <option value="jam" ${assigned === 'jam' ? 'selected' : ''}>Jam</option>
          </select>
        </div>
        <div class="inspector-field">
          <label>Prazo em Dias (+Dias)</label>
          <input type="number" value="${dueDays}" onchange="updateNodeConfigProp('${id}', 'due_days', parseInt(this.value))" class="inspector-input" min="1" max="30">
        </div>
      `;
    } else if (actType === "update_lead") {
      html += `
        <div class="inspector-field">
          <label>Etapa do Funil (Status)</label>
          <select onchange="updateNodeConfigProp('${id}', 'status', this.value)" class="inspector-select">
            <option value="novo" ${status === 'novo' ? 'selected' : ''}>Novo Lead</option>
            <option value="em_atendimento" ${status === 'em_atendimento' ? 'selected' : ''}>Em Atendimento</option>
            <option value="proposta" ${status === 'proposta' ? 'selected' : ''}>Proposta Enviada</option>
            <option value="qualificado" ${status === 'qualificado' ? 'selected' : ''}>Qualificado</option>
            <option value="fechado" ${status === 'fechado' ? 'selected' : ''}>Venda Concluída</option>
            <option value="perdido" ${status === 'perdido' ? 'selected' : ''}>Perdido</option>
          </select>
        </div>
        <div class="inspector-field">
          <label>Atribuir Vendedor</label>
          <select onchange="updateNodeConfigProp('${id}', 'assigned_to', this.value)" class="inspector-select">
            <option value="fauzer" ${assigned === 'fauzer' ? 'selected' : ''}>Fauzer</option>
            <option value="jam" ${assigned === 'jam' ? 'selected' : ''}>Jam</option>
          </select>
        </div>
        <div class="inspector-field">
          <label>Observações do Lead</label>
          <textarea onchange="updateNodeConfigProp('${id}', 'notes', this.value)" class="inspector-textarea" rows="3" placeholder="Digite notas ou observações...">${escapeHtml(notes)}</textarea>
        </div>
      `;
    }
  } else if (node.type === "transfer_agent" || node.type === "transfer") {
    const assigned = node.config.assigned_to || "fauzer";
    const msg = node.config.message || "👨‍💼 Transferindo seu atendimento para Fauzer...";
    html += `
      <div class="inspector-field">
        <label>Transferir para Atendente</label>
        <select onchange="updateNodeConfigProp('${id}', 'assigned_to', this.value)" class="inspector-select">
          <option value="fauzer" ${assigned === 'fauzer' ? 'selected' : ''}>Fauzer (Diretoria / Vendas)</option>
          <option value="jam" ${assigned === 'jam' ? 'selected' : ''}>Jam (Diretoria / Vendas)</option>
          <option value="fila_geral" ${assigned === 'fila_geral' ? 'selected' : ''}>Fila Geral / Suporte</option>
        </select>
      </div>
      <div class="inspector-field">
        <label>Mensagem de Transição</label>
        <textarea onchange="updateNodeConfigProp('${id}', 'message', this.value)" class="inspector-textarea" rows="3">${escapeHtml(msg)}</textarea>
      </div>
    `;
  } else if (node.type === "delay") {
    const seconds = node.config.seconds || 5;
    html += `
      <div class="inspector-field">
        <label>Duração do Delay (Segundos)</label>
        <input type="number" value="${seconds}" onchange="updateNodeConfigProp('${id}', 'seconds', parseInt(this.value))" class="inspector-input" min="1" max="3600">
      </div>
    `;
  } else if (node.type === "webhook") {
    const url = node.config.url || "https://api.exemplo.com/webhook";
    const method = node.config.method || "POST";
    const payload = node.config.payload || "{}";
    const saveVar = node.config.save_variable || "api_response";

    html += `
      <div class="inspector-field">
        <label>Método HTTP</label>
        <select onchange="updateNodeConfigProp('${id}', 'method', this.value)" class="inspector-select">
          <option value="POST" ${method === 'POST' ? 'selected' : ''}>POST</option>
          <option value="GET" ${method === 'GET' ? 'selected' : ''}>GET</option>
          <option value="PUT" ${method === 'PUT' ? 'selected' : ''}>PUT</option>
        </select>
      </div>
      <div class="inspector-field">
        <label>URL do Webhook</label>
        <input type="text" value="${escapeHtml(url)}" onchange="updateNodeConfigProp('${id}', 'url', this.value)" class="inspector-input">
      </div>
      <div class="inspector-field">
        <label>Payload JSON Template</label>
        <textarea onchange="updateNodeConfigProp('${id}', 'payload', this.value)" class="inspector-textarea" rows="3">${escapeHtml(payload)}</textarea>
      </div>
      <div class="inspector-field">
        <label>Salvar Resposta em Variável</label>
        <input type="text" value="${escapeHtml(saveVar)}" onchange="updateNodeConfigProp('${id}', 'save_variable', this.value)" class="inspector-input">
      </div>
    `;
  }

  // Seção de Gerenciador de Conexões e Links
  let connectionsHtml = "";
  const outgoingEdges = flowGraph.edges.filter(e => e.source === id);
  if (outgoingEdges.length > 0) {
    outgoingEdges.forEach(edge => {
      const tgtNode = flowGraph.nodes.find(n => n.id === edge.target);
      const tgtLabel = tgtNode ? tgtNode.label : edge.target;
      const handleLabel = edge.source_handle ? ` (${edge.source_handle})` : '';
      connectionsHtml += `
        <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 4px; font-size: 0.74rem; margin-top: 4px;">
          <span>➡️ Conectado a <b>${escapeHtml(tgtLabel)}</b>${escapeHtml(handleLabel)}</span>
          <button type="button" class="btn tiny" style="color: #f87171;" onclick="deleteEdge('${edge.id}')">Excluir</button>
        </div>
      `;
    });
  } else {
    connectionsHtml = `<div style="font-size: 0.74rem; color: #94a3b8;">Nenhuma conexão de saída.</div>`;
  }

  html += `
    <hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.08); margin: 16px 0 10px 0;">
    <div class="inspector-field">
      <label>Conexões de Saída deste Bloco</label>
      ${connectionsHtml}
      <div style="margin-top: 8px;">
        <label style="font-size: 0.7rem;">Conectar a Outro Bloco:</label>
        <div style="display: flex; gap: 4px;">
          <select id="connectTargetSelect_${id}" class="inspector-select" style="font-size: 0.74rem !important;">
            ${flowGraph.nodes.filter(n => n.id !== id).map(n => `<option value="${n.id}">${escapeHtml(n.label)}</option>`).join('')}
          </select>
          <button type="button" class="btn tiny primary" onclick="connectNodeToSelected('${id}')">Conectar</button>
        </div>
      </div>
    </div>
  `;

  form.innerHTML = html;
  panel.style.display = "flex";
}

function connectNodeToSelected(sourceId) {
  const select = document.getElementById(`connectTargetSelect_${sourceId}`);
  if (!select) return;
  const targetId = select.value;
  if (!targetId) return;

  saveHistoryState();
  flowGraph.edges.push({ id: `e_${Date.now()}`, source: sourceId, target: targetId });
  renderGraph();
  selectNode(sourceId);
}

function addMenuOption(nodeId) {
  const node = flowGraph.nodes.find(n => n.id === nodeId);
  if (!node) return;
  saveHistoryState();
  if (!node.config.options) node.config.options = [];
  const idx = node.config.options.length + 1;
  node.config.options.push({
    id: `opt_${Date.now()}_${idx}`,
    text: `${idx}. Nova Opção`
  });
  renderGraph();
  selectNode(nodeId);
}

function removeMenuOption(nodeId, index) {
  const node = flowGraph.nodes.find(n => n.id === nodeId);
  if (!node || !node.config.options) return;
  saveHistoryState();
  node.config.options.splice(index, 1);
  renderGraph();
  selectNode(nodeId);
}

function moveMenuOption(nodeId, index, direction) {
  const node = flowGraph.nodes.find(n => n.id === nodeId);
  if (!node || !node.config.options) return;
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= node.config.options.length) return;
  saveHistoryState();
  const temp = node.config.options[index];
  node.config.options[index] = node.config.options[targetIndex];
  node.config.options[targetIndex] = temp;
  renderGraph();
  selectNode(nodeId);
}

function updateMenuOptionProp(nodeId, index, prop, value) {
  const node = flowGraph.nodes.find(n => n.id === nodeId);
  if (!node || !node.config.options || !node.config.options[index]) return;
  node.config.options[index][prop] = value;
  renderGraph();
}

function closeInspector() {
  const panel = document.getElementById("nodeInspectorPanel");
  if (panel) panel.style.display = "none";
}

function updateNodeProp(id, prop, val) {
  const node = flowGraph.nodes.find(n => n.id === id);
  if (node) {
    node[prop] = val;
    renderGraph();
  }
}

function updateNodeConfigText(id, val) {
  const node = flowGraph.nodes.find(n => n.id === id);
  if (node) {
    node.config.text = val;
    renderGraph();
  }
}

function updateNodeConfigProp(id, prop, val) {
  const node = flowGraph.nodes.find(n => n.id === id);
  if (node) {
    node.config[prop] = val;
    renderGraph();
    selectNode(id);
  }
}

function updateNodeConfigKws(id, val) {
  const node = flowGraph.nodes.find(n => n.id === id);
  if (node) {
    node.config.keywords = val.split(",").map(s => s.trim()).filter(Boolean);
    renderGraph();
  }
}

function duplicateNode(id, e) {
  if (e) e.stopPropagation();
  const src = flowGraph.nodes.find(n => n.id === id);
  if (!src) return;

  saveHistoryState();
  const dupId = `node_${Date.now()}`;
  const dup = {
    ...JSON.parse(JSON.stringify(src)),
    id: dupId,
    label: `${src.label} (Cópia)`,
    position: { x: src.position.x + 40, y: src.position.y + 40 }
  };
  flowGraph.nodes.push(dup);
  selectNode(dupId);
}

function deleteNode(id, e) {
  if (e) e.stopPropagation();
  saveHistoryState();
  flowGraph.nodes = flowGraph.nodes.filter(n => n.id !== id);
  flowGraph.edges = flowGraph.edges.filter(edge => edge.source !== id && edge.target !== id);
  closeInspector();
  renderGraph();
}

// ==========================================
// CONTROLES DE ZOOM, PAN E HISTÓRICO
// ==========================================

function setupCanvasPanning() {
  const container = document.getElementById("canvasContainer");
  if (!container) return;

  container.addEventListener("mousedown", (e) => {
    if (e.target === container || e.target.id === "svgConnectionsLayer") {
      isPanning = true;
      startPanPos = { x: e.clientX - panOffset.x, y: e.clientY - panOffset.y };
    }
  });

  window.addEventListener("mousemove", (e) => {
    if (!isPanning) return;
    panOffset.x = e.clientX - startPanPos.x;
    panOffset.y = e.clientY - startPanPos.y;
    renderGraph();
  });

  window.addEventListener("mouseup", () => {
    isPanning = false;
  });
}

function zoomCanvas(factor) {
  scale = Math.min(2.0, Math.max(0.5, scale * factor));
  renderGraph();
}

function resetCanvasView() {
  scale = 1.0;
  panOffset = { x: 0, y: 0 };
  renderGraph();
}

function saveHistoryState() {
  undoStack.push(JSON.stringify(flowGraph));
  redoStack = [];
}

function undoCanvas() {
  if (undoStack.length === 0) return;
  redoStack.push(JSON.stringify(flowGraph));
  flowGraph = JSON.parse(undoStack.pop());
  renderGraph();
}

function redoCanvas() {
  if (redoStack.length === 0) return;
  undoStack.push(JSON.stringify(flowGraph));
  flowGraph = JSON.parse(redoStack.pop());
  renderGraph();
}

// ==========================================
// PERSISTÊNCIA & ATIVAÇÃO
// ==========================================

async function saveFlowDraft() {
  const name = document.getElementById("flowNameInput").value.trim() || "Novo Fluxo de Automação";
  try {
    const res = await fetch("/api/automation/flows/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: flowGraph.id, name, graph_data: flowGraph })
    });
    const data = await res.json();
    if (data.success) {
      if (data.id) flowGraph.id = data.id;
      alert("✅ Rascunho do fluxo salvo com sucesso!");
    } else {
      alert("⚠️ " + (data.error || "Erro ao salvar rascunho."));
    }
  } catch (err) {
    alert("Erro de conexão ao salvar rascunho: " + err.message);
  }
}

async function activateFlowVersion() {
  await saveFlowDraft();
  if (!flowGraph.id) return;

  try {
    const res = await fetch(`/api/automation/flows/${flowGraph.id}/activate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    const data = await res.json();
    if (data.success) {
      document.getElementById("flowStatusBadge").className = "status-badge status-active";
      document.getElementById("flowStatusBadge").innerText = "Ativo";
      alert("⚡ Versão do fluxo validada e publicada com sucesso!");
    } else {
      alert("⚠️ " + (data.error || "Erro de validação ao publicar fluxo.") + "\n" + (data.validation_errors ? data.validation_errors.join("\n") : ""));
    }
  } catch (err) {
    alert("Erro de conexão ao publicar fluxo: " + err.message);
  }
}

// ==========================================
// GERENCIADOR DE FLUXOS MODAL
// ==========================================

function openFlowManagerModal() {
  document.getElementById("flowManagerModal").style.display = "flex";
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.style.display = "none";
}

async function loadFlowToStudio(fid) {
  try {
    const res = await fetch("/api/automation/flows");
    const flows = await res.json();
    const target = flows.find(f => f.id === fid);
    if (target) {
      const graphData = JSON.parse(target.draft_version_data || "{}");
      if (graphData.nodes) {
        flowGraph = graphData;
        flowGraph.id = target.id;
      }
      document.getElementById("flowNameInput").value = target.name;
      document.getElementById("flowStatusBadge").className = `status-badge ${target.status === 'active' ? 'status-active' : 'status-draft'}`;
      document.getElementById("flowStatusBadge").innerText = target.status === 'active' ? 'Ativo' : 'Rascunho';
      closeModal("flowManagerModal");
      renderGraph();
    }
  } catch (err) {
    console.error("Erro ao carregar fluxo:", err);
  }
}

function createNewFlow() {
  flowGraph = {
    id: null,
    name: "Novo Fluxo de Automação",
    status: "draft",
    nodes: [
      {
        id: "node_trigger",
        type: "trigger",
        label: "Gatilho: Palavras-chave",
        config: { keywords: ["menu", "inicio"] },
        position: { x: 80, y: 120 }
      }
    ],
    edges: []
  };
  document.getElementById("flowNameInput").value = "Novo Fluxo de Automação";
  document.getElementById("flowStatusBadge").className = "status-badge status-draft";
  document.getElementById("flowStatusBadge").innerText = "Rascunho";
  closeModal("flowManagerModal");
  renderGraph();
}

// ==========================================
// SIMULADOR EM TEMPO REAL
// ==========================================

function openSimulatorModal() {
  document.getElementById("simulatorModal").style.display = "flex";
  const body = document.getElementById("simFeed");
  body.innerHTML = `
    <div style="padding: 8px 12px; background: #0f172a; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); font-size: 0.78rem; color: #cbd5e1;">
      ⚡ <strong>Simulador Iniciado:</strong> Teste a conversação digitando palavras-chave como 'olá' ou 'menu'.
    </div>
  `;
  activeSimulatorNodeId = null;
  simulatorVariables = {};
  runSimulationStep("");
}

function closeSimulatorModal() {
  document.getElementById("simulatorModal").style.display = "none";
}

async function sendSimulatorMessage() {
  const input = document.getElementById("simInputMsg");
  const text = input.value.trim();
  if (!text) return;

  const body = document.getElementById("simFeed");
  body.innerHTML += `
    <div style="text-align: right; margin-top: 6px;">
      <div style="display: inline-block; background: #0070F3; color: #fff; padding: 8px 12px; border-radius: 14px; border-top-right-radius: 2px; font-size: 0.8rem; max-width: 80%; text-align: left;">
        ${escapeHtml(text)}
      </div>
    </div>
  `;
  input.value = "";
  body.scrollTop = body.scrollHeight;

  await runSimulationStep(text);
}

async function runSimulationStep(userInput) {
  try {
    const res = await fetch("/api/automation/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        graph_data: flowGraph,
        input: userInput,
        current_node_id: activeSimulatorNodeId,
        variables: simulatorVariables
      })
    });
    const data = await res.json();
    if (!data.success) return;

    activeSimulatorNodeId = data.current_node_id;
    simulatorVariables = data.variables || {};
    const body = document.getElementById("simFeed");

    (data.responses || []).forEach(r => {
      if (r.type === "bot_text") {
        body.innerHTML += `
          <div style="text-align: left; margin-top: 6px;">
            <div style="display: inline-block; background: #0f172a; border: 1px solid rgba(255,255,255,0.12); color: #e2e8f0; padding: 8px 12px; border-radius: 14px; border-top-left-radius: 2px; font-size: 0.8rem; max-width: 85%;">
              ${escapeHtml(r.text).replace(/\n/g, "<br>")}
            </div>
          </div>
        `;
      } else if (r.type === "menu_options") {
        const optsHtml = (r.options || []).map(opt => `
          <button type="button" class="btn tiny secondary" style="display: block; width: 100%; text-align: left; margin-top: 4px;" onclick="sendSimulatorOption('${escapeHtml(opt.text || opt.id).replace(/'/g, "\\'")}')">
            🔹 ${escapeHtml(opt.text || opt.id)}
          </button>
        `).join('');
        body.innerHTML += `
          <div style="margin-top: 6px; padding-left: 10px; border-left: 2px solid #0070F3;">
            <div style="font-size: 0.72rem; color: #94a3b8; margin-bottom: 2px;">Clique em uma opção para responder:</div>
            ${optsHtml}
          </div>
        `;
      } else if (r.type === "system_event") {
        body.innerHTML += `
          <div style="text-align: center; margin-top: 6px;">
            <span style="font-size: 0.72rem; color: #34d399; background: rgba(16, 185, 129, 0.15); padding: 3px 8px; border-radius: 10px; font-weight: 600;">
              ${escapeHtml(r.text)}
            </span>
          </div>
        `;
      }
    });

    if (data.completed) {
      const varsEntries = Object.entries(data.variables || {});
      const varsHtml = varsEntries.length > 0 
        ? varsEntries.map(([k, v]) => `<div><code>${escapeHtml(k)}</code>: <b>${escapeHtml(v)}</b></div>`).join('') 
        : '<div style="color: #94a3b8;">Nenhuma variável registrada.</div>';

      body.innerHTML += `
        <div style="margin-top: 10px; padding: 12px; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px; font-size: 0.78rem; color: #e2e8f0;">
          <strong style="color: #34d399; display: block; margin-bottom: 4px;">🏁 Resumo da Execução & Variáveis Coletadas</strong>
          <div style="display: flex; flex-direction: column; gap: 4px; font-size: 0.76rem;">
            ${varsHtml}
          </div>
        </div>
      `;
    }

    body.scrollTop = body.scrollHeight;
  } catch (err) {
    console.error("[Simulator Error]:", err);
  }
}

function sendSimulatorOption(optText) {
  const input = document.getElementById("simInputMsg");
  if (input) input.value = optText;
  sendSimulatorMessage();
}
