let serverStatusCache = null;
let currentSessionId = null;
let allTablesCache = [];
let currentExplorerTable = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  loadStoredSettings();
  fetchSystemStatus();
  setupDropzone();
  setupInputListeners();
});

/* ==========================================================================
   Navigation & Status & Settings
   ========================================================================== */

function switchTab(tabId) {
  document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  if (activeBtn) activeBtn.classList.add('active');

  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
  const activePane = document.getElementById(`tab-pane-${tabId}`);
  if (activePane) activePane.classList.add('active');

  if (tabId === 'explorer') {
    loadExplorerTables();
  }
}

async function fetchSystemStatus() {
  const statusBadgeText = document.getElementById('status-model-text');
  const userApiKey = localStorage.getItem('datavox_user_api_key');
  const userProvider = localStorage.getItem('datavox_user_provider') || 'gemini';
  const userModel = localStorage.getItem('datavox_user_model');

  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('Status request failed');
    serverStatusCache = await res.json();

    if (userApiKey) {
      const displayModel = userModel || (userProvider === 'gemini' ? 'Gemini 3.6 Flash' : 'GPT-4o Mini');
      statusBadgeText.textContent = `${displayModel} (Custom Key) • ${serverStatusCache.database}`;
    } else {
      statusBadgeText.textContent = `${serverStatusCache.model} • ${serverStatusCache.database}`;
    }
  } catch (err) {
    statusBadgeText.textContent = userApiKey ? 'Custom Key Active' : 'Server Online';
  }
}

function loadStoredSettings() {
  const provider = localStorage.getItem('datavox_user_provider') || 'gemini';
  const apiKey = localStorage.getItem('datavox_user_api_key') || '';
  const model = localStorage.getItem('datavox_user_model') || '';

  const providerEl = document.getElementById('setting-provider');
  const keyEl = document.getElementById('setting-api-key');
  const modelEl = document.getElementById('setting-model-name');
  const settingsBtn = document.getElementById('btn-open-settings');

  if (providerEl) providerEl.value = provider;
  if (keyEl) keyEl.value = apiKey;
  if (modelEl) modelEl.value = model;

  handleProviderChange();

  if (apiKey) {
    if (settingsBtn) {
      settingsBtn.classList.add('configured');
      const span = settingsBtn.querySelector('span');
      if (span) span.textContent = 'Key Active';
    }
  } else {
    if (settingsBtn) {
      settingsBtn.classList.remove('configured');
      const span = settingsBtn.querySelector('span');
      if (span) span.textContent = 'API Key';
    }
  }
}

function openSettingsModal() {
  loadStoredSettings();
  const alertEl = document.getElementById('settings-save-alert');
  if (alertEl) alertEl.innerHTML = '';
  document.getElementById('settings-modal').classList.add('active');
}

function closeSettingsModal(event) {
  if (event && event.target !== document.getElementById('settings-modal')) return;
  document.getElementById('settings-modal').classList.remove('active');
}

function toggleKeyVisibility() {
  const input = document.getElementById('setting-api-key');
  if (input.type === 'password') input.type = 'text';
  else input.type = 'password';
}

function handleProviderChange() {
  const providerEl = document.getElementById('setting-provider');
  if (!providerEl) return;
  const provider = providerEl.value;
  const helpLink = document.getElementById('setting-key-help-link');
  const modelInput = document.getElementById('setting-model-name');

  if (provider === 'gemini') {
    if (helpLink) {
      helpLink.href = 'https://aistudio.google.com/app/apikey';
      helpLink.textContent = 'Get a free Gemini API Key';
    }
    if (modelInput) modelInput.placeholder = 'Default: gemini-3.6-flash';
  } else {
    if (helpLink) {
      helpLink.href = 'https://platform.openai.com/api-keys';
      helpLink.textContent = 'Get an OpenAI API Key';
    }
    if (modelInput) modelInput.placeholder = 'Default: gpt-4o-mini';
  }
}

function saveUserSettings() {
  const provider = document.getElementById('setting-provider').value;
  const apiKey = document.getElementById('setting-api-key').value.trim();
  const model = document.getElementById('setting-model-name').value.trim();
  const alertEl = document.getElementById('settings-save-alert');

  localStorage.setItem('datavox_user_provider', provider);
  localStorage.setItem('datavox_user_api_key', apiKey);
  localStorage.setItem('datavox_user_model', model);

  alertEl.innerHTML = `
    <div class="alert-banner success" style="margin-top: 8px;">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
      <span>Credentials saved locally in your browser!</span>
    </div>
  `;

  loadStoredSettings();
  fetchSystemStatus();

  setTimeout(() => {
    closeSettingsModal();
  }, 900);
}

function clearUserSettings() {
  localStorage.removeItem('datavox_user_provider');
  localStorage.removeItem('datavox_user_api_key');
  localStorage.removeItem('datavox_user_model');
  loadStoredSettings();
  fetchSystemStatus();
  const alertEl = document.getElementById('settings-save-alert');
  if (alertEl) {
    alertEl.innerHTML = `
      <div class="alert-banner success" style="margin-top: 8px;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span>Credentials cleared. Using server default model.</span>
      </div>
    `;
  }
  setTimeout(() => {
    closeSettingsModal();
  }, 800);
}

/* ==========================================================================
   Tab 1: Chat & Query Studio
   ========================================================================== */

function useQuickPrompt(text) {
  const input = document.getElementById('user-query-input');
  input.value = text;
  submitQuery();
}

function resetSession() {
  currentSessionId = null;
  const messagesContainer = document.getElementById('chat-messages');
  const divider = document.createElement('div');
  divider.style.cssText = 'text-align: center; color: var(--text-subtle); font-size: 0.78rem; margin: 12px 0; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 8px;';
  divider.textContent = '— New Conversation Session Started —';
  messagesContainer.appendChild(divider);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function setupInputListeners() {
  const input = document.getElementById('user-query-input');
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitQuery();
    }
  });
}

async function submitQuery() {
  const input = document.getElementById('user-query-input');
  const sendBtn = document.getElementById('send-query-btn');
  const query = input.value.trim();

  if (!query) return;

  const userApiKey = localStorage.getItem('datavox_user_api_key') || null;
  const userProvider = localStorage.getItem('datavox_user_provider') || null;
  const userModel = localStorage.getItem('datavox_user_model') || null;

  // If no user key and server has no key, prompt settings modal
  if (!userApiKey && serverStatusCache && !serverStatusCache.has_server_key) {
    openSettingsModal();
    const alertEl = document.getElementById('settings-save-alert');
    if (alertEl) {
      alertEl.innerHTML = `
        <div class="alert-banner error" style="margin-top: 8px;">
          <span>Please enter your Gemini or OpenAI API Key to start querying Datavox.</span>
        </div>
      `;
    }
    return;
  }

  // Clear input
  input.value = '';
  sendBtn.disabled = true;

  // Append user message
  appendUserMessage(query);

  // Append loading indicator
  const loadingId = appendLoadingMessage();

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (userApiKey) headers['X-Datavox-Api-Key'] = userApiKey;
    if (userProvider) headers['X-Datavox-Provider'] = userProvider;
    if (userModel) headers['X-Datavox-Model'] = userModel;

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        query: query,
        session_id: currentSessionId
      })
    });

    removeLoadingMessage(loadingId);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(errData.detail || 'Query execution failed');
    }

    const data = await res.json();
    if (data.session_id) {
      currentSessionId = data.session_id;
    }

    appendAssistantMessage(data);

  } catch (err) {
    removeLoadingMessage(loadingId);
    appendErrorMessage(err.message);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function appendUserMessage(text) {
  const messagesContainer = document.getElementById('chat-messages');

  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `
    <div class="msg-avatar" title="You">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
        <circle cx="12" cy="7" r="4"></circle>
      </svg>
    </div>
    <div class="msg-body">
      <div class="user-bubble">${escapeHtml(text)}</div>
    </div>
  `;

  messagesContainer.appendChild(row);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function appendLoadingMessage() {
  const messagesContainer = document.getElementById('chat-messages');
  const loadingId = 'loading-' + Date.now();

  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.id = loadingId;
  row.innerHTML = `
    <div class="msg-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
      </svg>
    </div>
    <div class="msg-body">
      <div class="assistant-card" style="padding: 16px;">
        <div style="display: flex; align-items: center; gap: 10px; color: var(--text-muted); font-size: 0.88rem;">
          <span class="status-dot"></span>
          <span>Datavox agentic pipeline is routing and generating query...</span>
        </div>
      </div>
    </div>
  `;

  messagesContainer.appendChild(row);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  return loadingId;
}

function removeLoadingMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendAssistantMessage(data) {
  const messagesContainer = document.getElementById('chat-messages');

  const row = document.createElement('div');
  row.className = 'message-row assistant';

  // Build Trace Strip
  let traceHtml = '';
  if (data.node_trace && data.node_trace.length > 0) {
    const pills = data.node_trace.map(node => {
      const friendlyName = node.replace(/_/g, ' ').toUpperCase();
      return `<span class="node-pill active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        ${friendlyName}
      </span>`;
    }).join(' ');

    traceHtml = `
      <div class="trace-strip">
        <span class="trace-title">Trace:</span>
        ${pills}
      </div>
    `;
  }

  // Build SQL Accordion
  let sqlAccordionHtml = '';
  if (data.generated_sql) {
    const copyId = 'sql-' + Date.now();
    sqlAccordionHtml = `
      <div class="details-accordion open">
        <div class="accordion-header" onclick="toggleAccordion(this)">
          <span style="display: flex; align-items: center; gap: 6px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="16 18 22 12 16 6"></polyline>
              <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
            Generated SQL Query
          </span>
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div class="accordion-content">
          <div class="sql-code-box">
            <button class="copy-btn" onclick="copyToClipboard('${copyId}', this)">Copy</button>
            <code id="${copyId}">${escapeHtml(data.generated_sql)}</code>
          </div>
        </div>
      </div>
    `;
  }

  // Build Results Table Accordion
  let tableAccordionHtml = '';
  if (data.executed_sql_output && Array.isArray(data.executed_sql_output) && data.executed_sql_output.length > 0) {
    const rows = data.executed_sql_output;
    const columns = Object.keys(rows[0]);

    const headerHtml = columns.map(c => `<th>${escapeHtml(c)}</th>`).join('');
    const rowsHtml = rows.slice(0, 50).map(r => {
      const cells = columns.map(c => `<td>${escapeHtml(String(r[c] !== null && r[c] !== undefined ? r[c] : ''))}</td>`).join('');
      return `<tr>${cells}</tr>`;
    }).join('');

    tableAccordionHtml = `
      <div class="details-accordion">
        <div class="accordion-header" onclick="toggleAccordion(this)">
          <span style="display: flex; align-items: center; gap: 6px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="3" y1="9" x2="21" y2="9"></line>
              <line x1="9" y1="21" x2="9" y2="9"></line>
            </svg>
            Raw Execution Output (${rows.length} row${rows.length === 1 ? '' : 's'})
          </span>
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div class="accordion-content">
          <div class="table-responsive">
            <table class="data-table">
              <thead><tr>${headerHtml}</tr></thead>
              <tbody>${rowsHtml}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  }

  // Format Text Response
  const formattedResponse = formatMarkdown(data.final_response || 'No response generated.');

  row.innerHTML = `
    <div class="msg-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
      </svg>
    </div>
    <div class="msg-body">
      <div class="assistant-card">
        ${traceHtml}
        <div class="prose-output">${formattedResponse}</div>
        ${sqlAccordionHtml}
        ${tableAccordionHtml}
      </div>
    </div>
  `;

  messagesContainer.appendChild(row);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function appendErrorMessage(errText) {
  const messagesContainer = document.getElementById('chat-messages');
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.innerHTML = `
    <div class="msg-avatar" style="background: var(--accent-rose);">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
    </div>
    <div class="msg-body">
      <div class="assistant-card" style="border-color: rgba(244, 63, 94, 0.4);">
        <div style="color: var(--accent-rose); font-weight: 600;">Error Encountered</div>
        <div style="color: #fda4af; font-size: 0.9rem; line-height: 1.5;">${escapeHtml(errText)}</div>
      </div>
    </div>
  `;
  messagesContainer.appendChild(row);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function toggleAccordion(header) {
  const accordion = header.closest('.details-accordion');
  if (accordion) accordion.classList.toggle('open');
}

function copyToClipboard(elementId, btn) {
  const el = document.getElementById(elementId);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => {
    const orig = btn.innerText;
    btn.innerText = 'Copied!';
    setTimeout(() => { btn.innerText = orig; }, 2000);
  });
}

/* ==========================================================================
   Tab 2: Add Data / Ingestion Studio
   ========================================================================== */

let queuedFiles = [];
let databaseRelationships = [];

/* ==========================================================================
   Tab 2: Add Data / Ingestion Studio (Multi-Table & Relationships)
   ========================================================================== */

function setupDropzone() {
  const dropzone = document.getElementById('file-dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer && e.dataTransfer.files.length > 0) {
      handleFilesBatch(Array.from(e.dataTransfer.files));
    }
  });
}

function handleFileSelected(event) {
  if (event.target.files && event.target.files.length > 0) {
    handleFilesBatch(Array.from(event.target.files));
  }
}

async function handleFilesBatch(files) {
  for (const file of files) {
    // Avoid duplicate additions
    if (!queuedFiles.some(item => item.file.name === file.name)) {
      await processAndQueueFile(file);
    }
  }
  renderQueuedFiles();
  updateDetectedRelationships();
}

function processAndQueueFile(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target.result;
      const baseName = file.name.split('.')[0].toLowerCase().replace(/[^a-z0-9_]/g, '_');
      const parsed = parseFileRows(content, file.name);

      queuedFiles.push({
        file: file,
        tableName: baseName,
        columns: parsed.columns,
        rows: parsed.rows,
        size: file.size
      });
      resolve();
    };
    reader.readAsText(file);
  });
}

function parseFileRows(content, filename) {
  let rows = [];
  let columns = [];
  try {
    if (filename.endsWith('.json')) {
      const parsed = JSON.parse(content);
      rows = Array.isArray(parsed) ? parsed : [parsed];
      if (rows.length > 0) columns = Object.keys(rows[0]);
    } else {
      const lines = content.trim().split(/\r\n|\n/).filter(l => l.trim().length > 0);
      if (lines.length > 0) {
        columns = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
        rows = lines.slice(1).map(line => {
          const vals = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''));
          const rowObj = {};
          columns.forEach((h, i) => { rowObj[h] = vals[i] || ''; });
          return rowObj;
        });
      }
    }
  } catch (e) {
    console.warn("Parse error:", e);
  }
  return { columns, rows };
}

function removeQueuedFile(index) {
  queuedFiles.splice(index, 1);
  renderQueuedFiles();
  updateDetectedRelationships();
}

function renderQueuedFiles() {
  const section = document.getElementById('queued-files-section');
  const list = document.getElementById('files-queue-list');
  const countEl = document.getElementById('queued-files-count');
  const submitBtn = document.getElementById('btn-submit-upload');
  const dropText = document.getElementById('drop-text');

  if (queuedFiles.length === 0) {
    section.style.display = 'none';
    submitBtn.disabled = true;
    dropText.textContent = 'Drag & drop multiple CSV or JSON files here, or browse';
    renderPreviewTable(null);
    return;
  }

  section.style.display = 'block';
  submitBtn.disabled = false;
  countEl.textContent = queuedFiles.length;
  dropText.textContent = `${queuedFiles.length} table${queuedFiles.length > 1 ? 's' : ''} queued for upload`;

  list.innerHTML = queuedFiles.map((item, idx) => `
    <div class="queued-file-card" onclick="renderPreviewTable(${idx})" style="cursor: pointer;">
      <div class="queued-file-info">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
        </svg>
        <div>
          <div class="queued-file-name">${escapeHtml(item.tableName)}</div>
          <div class="queued-file-meta">${item.rows.length} rows • ${item.columns.length} columns • ${formatBytes(item.size)}</div>
        </div>
      </div>
      <button class="remove-file-btn" onclick="event.stopPropagation(); removeQueuedFile(${idx})" title="Remove table">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>
  `).join('');

  // Render preview of first queued table
  renderPreviewTable(0);
}

function renderPreviewTable(index) {
  const container = document.getElementById('preview-table-container');
  const subtitle = document.getElementById('preview-subtitle');

  if (index === null || !queuedFiles[index]) {
    container.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-subtle);">No files queued for preview yet.</div>';
    subtitle.textContent = 'Select files on the left to preview their schema columns and records.';
    return;
  }

  const item = queuedFiles[index];
  subtitle.textContent = `Previewing table '${item.tableName}' (${item.rows.length} total rows, showing first 10):`;

  const headersHtml = item.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('');
  const rowsHtml = item.rows.slice(0, 10).map(r => {
    const cells = item.columns.map(c => `<td>${escapeHtml(String(r[c] !== null && r[c] !== undefined ? r[c] : ''))}</td>`).join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  container.innerHTML = `
    <table class="data-table">
      <thead><tr>${headersHtml}</tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  `;
}

function updateDetectedRelationships() {
  const relBox = document.getElementById('detected-relationships-box');
  const relList = document.getElementById('detected-relationships-list');

  // Gather all table columns from queued files + existing database tables
  const allTables = [];
  (allTablesCache || []).forEach(t => {
    allTables.push({
      name: t.name,
      columns: t.columns ? t.columns.map(c => c.name) : []
    });
  });

  queuedFiles.forEach(item => {
    allTables.push({
      name: item.tableName,
      columns: item.columns
    });
  });

  const rels = detectRelationshipsClient(allTables);

  // Filter to relationships involving at least one queued table
  const relevantRels = rels.filter(r => 
    queuedFiles.some(q => q.tableName === r.from_table || q.tableName === r.to_table)
  );

  if (relevantRels.length === 0) {
    relBox.style.display = 'none';
    return;
  }

  relBox.style.display = 'block';
  relList.innerHTML = relevantRels.map(r => `
    <div class="rel-link-pill">
      <span class="from-col">${escapeHtml(r.from_table)}.${escapeHtml(r.from_column)}</span>
      <span class="arrow">➔</span>
      <span class="to-col">${escapeHtml(r.to_table)}.${escapeHtml(r.to_column)}</span>
    </div>
  `).join('');
}

function detectRelationshipsClient(tables) {
  const rels = [];
  const map = {};

  tables.forEach(t => {
    map[t.name.toLowerCase()] = {
      name: t.name,
      cols: (t.columns || []).map(c => typeof c === 'string' ? c.toLowerCase() : c.name.toLowerCase())
    };
  });

  for (const [fromName, fromData] of Object.entries(map)) {
    for (const col of fromData.cols) {
      if (col.endsWith('_id') || col.endsWith('id')) {
        const prefix = col.endsWith('_id') ? col.slice(0, -3) : col.slice(0, -2);
        if (!prefix || prefix === fromName) continue;

        const candidates = [prefix, prefix + 's', prefix + 'es'];
        for (const targetCand of candidates) {
          if (map[targetCand] && targetCand !== fromName) {
            const targetCols = map[targetCand].cols;
            let targetColMatched = null;
            if (targetCols.includes(col)) targetColMatched = col;
            else if (targetCols.includes('id')) targetColMatched = 'id';
            else if (targetCols.includes(prefix + '_id')) targetColMatched = prefix + '_id';

            if (targetColMatched) {
              const link = {
                from_table: fromData.name,
                from_column: col,
                to_table: map[targetCand].name,
                to_column: targetColMatched
              };
              if (!rels.some(r => r.from_table === link.from_table && r.from_column === link.from_column && r.to_table === link.to_table)) {
                rels.push(link);
              }
              break;
            }
          }
        }
      }
    }
  }

  return rels;
}

async function uploadQueuedDatasets() {
  if (queuedFiles.length === 0) return;

  const submitBtn = document.getElementById('btn-submit-upload');
  const alertContainer = document.getElementById('upload-alert');

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="status-dot"></span> Ingesting Batch & Indexing Relations...';
  alertContainer.innerHTML = '';

  const formData = new FormData();
  queuedFiles.forEach(item => {
    formData.append('files', item.file);
  });

  const clearSampleCheckbox = document.getElementById('clear-sample-on-upload');
  if (clearSampleCheckbox && clearSampleCheckbox.checked) {
    formData.append('clear_sample_data', 'true');
  }

  try {
    const res = await fetch('/api/upload-multiple-data', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Batch upload failed');
    }

    const relCount = (data.details.detected_relationships || []).length;
    const tableCount = (data.details.tables_ingested || []).length;

    alertContainer.innerHTML = `
      <div class="alert-banner success">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span>Successfully ingested <strong>${tableCount} related tables</strong> with <strong>${relCount} detected foreign key links</strong>! You can now ask cross-table JOIN queries.</span>
      </div>
    `;

    // Clear queue
    queuedFiles = [];
    renderQueuedFiles();
    updateDetectedRelationships();

    // Reload Explorer
    loadExplorerTables();

  } catch (err) {
    alertContainer.innerHTML = `
      <div class="alert-banner error">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>${escapeHtml(err.message)}</span>
      </div>
    `;
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M5 12h14"></path><path d="M12 5l7 7-7 7"></path>
      </svg>
      Upload & Ingest All Tables with Relationships
    `;
  }
}

async function clearSampleDataManually() {
  if (!confirm("Are you sure you want to remove all pre-existing sample/testing tables? Any uploaded custom tables will be preserved.")) return;
  try {
    const res = await fetch('/api/clear-sample-data', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to clear sample tables');

    currentExplorerTable = null;
    const uploadAlert = document.getElementById('upload-alert');
    if (uploadAlert) {
      uploadAlert.innerHTML = `
        <div class="alert-banner success">
          <span>${escapeHtml(data.message)}</span>
        </div>
      `;
    }
    await loadExplorerTables();
  } catch (err) {
    alert(`Error clearing sample data: ${err.message}`);
  }
}

async function resetSampleDataManually() {
  if (!confirm("Restore the default sample demo tables (customers, products, orders, order_items, regional_sales)?")) return;
  try {
    const res = await fetch('/api/reset-sample-data', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to reset sample tables');
    currentExplorerTable = null;
    await loadExplorerTables();
  } catch (err) {
    alert(`Error restoring sample data: ${err.message}`);
  }
}

/* ==========================================================================
   Tab 3: Database & Schema Explorer
   ========================================================================== */

async function loadExplorerTables() {
  const listContainer = document.getElementById('explorer-table-list');
  try {
    const res = await fetch('/api/tables');
    if (!res.ok) throw new Error('Could not list tables');
    const data = await res.json();
    allTablesCache = data.tables || [];

    // Also fetch relationships
    const relRes = await fetch('/api/relationships');
    if (relRes.ok) {
      const relData = await relRes.json();
      databaseRelationships = relData.relationships || [];
    }

    if (allTablesCache.length === 0) {
      listContainer.innerHTML = '<div style="color: var(--text-subtle); font-size: 0.82rem;">No tables found in database.</div>';
      return;
    }

    listContainer.innerHTML = allTablesCache.map(t => `
      <div class="table-nav-item ${currentExplorerTable === t.name ? 'active' : ''}" onclick="selectExplorerTable('${t.name}')">
        <span style="font-weight: 600;">${escapeHtml(t.name)}</span>
        <span class="table-nav-badge">${t.row_count}</span>
      </div>
    `).join('');

    const tableStillExists = allTablesCache.some(t => t.name === currentExplorerTable);
    if (!tableStillExists && allTablesCache.length > 0) {
      selectExplorerTable(allTablesCache[0].name);
    } else if (tableStillExists) {
      selectExplorerTable(currentExplorerTable);
    } else {
      currentExplorerTable = null;
      resetExplorerViewer();
    }

  } catch (err) {
    listContainer.innerHTML = `<div style="color: var(--accent-rose); font-size: 0.8rem;">${escapeHtml(err.message)}</div>`;
  }
}

async function selectExplorerTable(tableName) {
  currentExplorerTable = tableName;

  document.querySelectorAll('.table-nav-item').forEach(el => {
    el.classList.toggle('active', el.innerText.includes(tableName));
  });

  const tableMeta = allTablesCache.find(t => t.name === tableName);
  const titleEl = document.getElementById('explorer-active-table-name');
  const infoEl = document.getElementById('explorer-active-table-info');
  const badgeEl = document.getElementById('explorer-row-count-badge');
  const schemaContainer = document.getElementById('explorer-schema-tags');
  const dataTableContainer = document.getElementById('explorer-data-table-container');
  const relsBox = document.getElementById('explorer-table-relationships-box');
  const relsGrid = document.getElementById('explorer-active-table-rels');

  titleEl.textContent = tableName;
  badgeEl.style.display = 'inline-block';
  badgeEl.textContent = `${tableMeta ? tableMeta.row_count : 0} Rows`;
  infoEl.textContent = `Live data records in table '${tableName}'`;

  // Filter relationships for active table
  const activeRels = (databaseRelationships || []).filter(r => r.from_table === tableName || r.to_table === tableName);
  if (activeRels.length > 0) {
    relsBox.style.display = 'block';
    relsGrid.innerHTML = activeRels.map(r => `
      <div class="rel-link-pill">
        <span class="from-col">${escapeHtml(r.from_table)}.${escapeHtml(r.from_column)}</span>
        <span class="arrow">➔</span>
        <span class="to-col">${escapeHtml(r.to_table)}.${escapeHtml(r.to_column)}</span>
      </div>
    `).join('');
  } else {
    relsBox.style.display = 'none';
  }

  // Render Schema Tags with FK notations
  if (tableMeta && tableMeta.columns) {
    schemaContainer.innerHTML = tableMeta.columns.map(c => {
      const isPk = c.primary_key;
      const isFk = activeRels.some(r => r.from_table === tableName && r.from_column === c.name);
      return `
        <span class="schema-tag ${isPk ? 'pk' : ''}">
          ${escapeHtml(c.name)}: <em>${escapeHtml(c.type)}</em> ${isPk ? '<span class="pill-badge pk-badge">PK</span>' : ''} ${isFk ? '<span class="pill-badge fk-badge">FK</span>' : ''}
        </span>
      `;
    }).join('');
  }

  // Fetch Table Rows
  dataTableContainer.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-subtle);"><span class="status-dot"></span> Loading table rows...</div>';

  try {
    const res = await fetch(`/api/tables/${tableName}?limit=50`);
    if (!res.ok) throw new Error('Failed to load table rows');
    const tableData = await res.json();

    if (!tableData.rows || tableData.rows.length === 0) {
      dataTableContainer.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--text-subtle);">This table is currently empty.</div>';
      return;
    }

    const cols = tableData.columns;
    const headerHtml = cols.map(c => `<th>${escapeHtml(c)}</th>`).join('');
    const rowsHtml = tableData.rows.map(r => {
      const cells = cols.map(c => `<td>${escapeHtml(String(r[c] !== null && r[c] !== undefined ? r[c] : ''))}</td>`).join('');
      return `<tr>${cells}</tr>`;
    }).join('');

    dataTableContainer.innerHTML = `
      <table class="data-table">
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    `;

  } catch (err) {
    dataTableContainer.innerHTML = `<div style="padding: 30px; color: var(--accent-rose);">Error: ${escapeHtml(err.message)}</div>`;
  }
}

function resetExplorerViewer() {
  const titleEl = document.getElementById('explorer-active-table-name');
  const infoEl = document.getElementById('explorer-active-table-info');
  const badgeEl = document.getElementById('explorer-row-count-badge');
  const schemaContainer = document.getElementById('explorer-schema-tags');
  const dataTableContainer = document.getElementById('explorer-data-table-container');
  const relsBox = document.getElementById('explorer-table-relationships-box');

  if (titleEl) titleEl.textContent = 'No Tables Present';
  if (badgeEl) badgeEl.style.display = 'none';
  if (infoEl) infoEl.textContent = 'Database is currently empty. Upload CSV or JSON files from the Add Data tab to begin.';
  if (relsBox) relsBox.style.display = 'none';
  if (schemaContainer) schemaContainer.innerHTML = '<span style="color: var(--text-subtle); font-size: 0.82rem;">No schema available</span>';
  if (dataTableContainer) {
    dataTableContainer.innerHTML = '<div style="padding: 48px; text-align: center; color: var(--text-subtle);">No tables in database. Upload a dataset or restore sample data to explore.</div>';
  }
}

/* ==========================================================================
   Utilities
   ========================================================================== */

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // Headings ###
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bullet points * or -
  html = html.replace(/^\s*[\*\-]\s+(.*$)/gim, '<li>$1</li>');

  // Wrap list items
  html = html.replace(/(<li>.*<\/li>)/gms, '<ul>$1</ul>');

  // Newlines to paragraph breaks
  html = html.split('\n\n').map(p => {
    if (p.startsWith('<h3>') || p.startsWith('<ul>') || p.startsWith('<h2>') || p.startsWith('<h1>')) {
      return p;
    }
    return `<p>${p}</p>`;
  }).join('');

  return html;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
