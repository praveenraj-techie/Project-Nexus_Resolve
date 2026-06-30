const DEFAULT_API_BASE = 'http://127.0.0.1:8000';
const DASHBOARD_BASE = 'http://localhost:5173/#/incident/';
const MAJOR_COMMS_CHANNELS = new Set(['teams_bridge', 'isinfo_email', 'ivr']);

const params = new URLSearchParams(window.location.search);
const API_BASE = params.get('api') || DEFAULT_API_BASE;

const state = {
  selectedRunId: params.get('run') || null,
  selectedRecordId: 'incident-primary',
  latest: null,
  runs: [],
  socket: null,
  refreshTimer: null,
  reconnectTimer: null,
  pendingRefresh: false,
};

const els = {
  pageTitle: document.getElementById('page-title'),
  wsState: document.getElementById('ws-state'),
  dashboardLink: document.getElementById('dashboard-link'),
  emptyState: document.getElementById('empty-state'),
  recordToolbar: document.getElementById('record-toolbar'),
  summaryStrip: document.getElementById('summary-strip'),
  runList: document.getElementById('run-list'),
  recordTabs: document.getElementById('record-tabs'),
  recordHeading: document.getElementById('record-heading'),
  recordState: document.getElementById('record-state'),
  fieldGrid: document.getElementById('field-grid'),
  recordDescription: document.getElementById('record-description'),
  cmdbGrid: document.getElementById('cmdb-grid'),
  metricBox: document.getElementById('metric-box'),
  workNoteTitle: document.getElementById('work-note-title'),
  workNoteCount: document.getElementById('work-note-count'),
  workNotes: document.getElementById('work-notes'),
  eventCount: document.getElementById('event-count'),
  eventStream: document.getElementById('event-stream'),
  relatedTable: document.getElementById('related-table'),
  commsList: document.getElementById('comms-list'),
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

function titleCase(value) {
  return String(value ?? '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDate(value) {
  if (!value) return 'Pending';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    month: 'short',
    day: '2-digit',
  });
}

function setWsState(label, tone = 'neutral') {
  els.wsState.textContent = label;
  els.wsState.className = `status-pill ${tone}`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    cache: 'no-store',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail = payload?.detail || response.statusText || 'Request failed';
    throw new Error(detail);
  }
  return payload;
}

async function refreshRuns() {
  try {
    const payload = await fetchJson(`${API_BASE}/api/local-snow/runs`);
    state.runs = payload.runs || [];
  } catch {
    state.runs = [];
  }
  renderRunList();
}

async function refreshCurrent() {
  try {
    const url = state.selectedRunId
      ? `${API_BASE}/api/local-snow/runs/${encodeURIComponent(state.selectedRunId)}`
      : `${API_BASE}/api/local-snow/latest`;
    const payload = await fetchJson(url);
    state.latest = payload;
    state.selectedRunId = payload.run_id;
    ensureSelectedRecord();
    connectSocket(payload.run_id);
    render();
  } catch (error) {
    if (!state.latest) {
      renderEmpty(error instanceof Error ? error.message : 'No active run yet.');
    }
  }
}

function scheduleRefresh() {
  if (state.pendingRefresh) return;
  state.pendingRefresh = true;
  window.setTimeout(async () => {
    state.pendingRefresh = false;
    await refreshCurrent();
    await refreshRuns();
  }, 200);
}

function connectSocket(runId) {
  if (state.socket?.runId === runId && state.socket.readyState <= 1) return;
  if (state.socket) state.socket.close();
  const wsUrl = new URL(API_BASE);
  wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  wsUrl.pathname = `/ws/runs/${runId}`;
  const socket = new WebSocket(wsUrl.toString());
  socket.runId = runId;
  state.socket = socket;
  setWsState('Connecting', 'neutral');
  socket.onopen = () => setWsState('Live mirror', 'live');
  socket.onmessage = () => scheduleRefresh();
  socket.onclose = () => {
    if (state.socket === socket) {
      setWsState('Reconnecting', 'neutral');
      window.clearTimeout(state.reconnectTimer);
      state.reconnectTimer = window.setTimeout(() => connectSocket(runId), 1500);
    }
  };
  socket.onerror = () => setWsState('Socket error', 'danger');
}

function ensureSelectedRecord() {
  const records = state.latest?.itsm_twin?.records || [];
  if (!records.some((record) => record.id === state.selectedRecordId)) {
    state.selectedRecordId = records[0]?.id || 'incident-primary';
  }
}

function activeRecord() {
  const records = state.latest?.itsm_twin?.records || [];
  return (
    records.find((record) => record.id === state.selectedRecordId) ||
    records.find((record) => record.id === 'incident-primary') ||
    records[0] ||
    null
  );
}

function renderEmpty(message) {
  els.pageTitle.textContent = 'Waiting for a NEXUS incident';
  els.emptyState.hidden = false;
  els.recordToolbar.hidden = true;
  els.summaryStrip.hidden = true;
  setWsState(message || 'No active run', 'neutral');
  renderRunList();
}

function render() {
  const payload = state.latest;
  const ticket = payload?.ticket;
  const twin = payload?.itsm_twin;
  const records = twin?.records || [];
  const events = payload?.events || [];
  const selected = activeRecord();

  if (!payload || !ticket || !twin || !selected) {
    renderEmpty('Waiting for state');
    return;
  }

  els.emptyState.hidden = true;
  els.recordToolbar.hidden = false;
  els.summaryStrip.hidden = false;
  els.pageTitle.textContent = `${ticket.incident_id} - ${ticket.title}`;
  els.dashboardLink.href = `${DASHBOARD_BASE}${encodeURIComponent(ticket.scenario_id || 'disk-space')}`;
  renderRunList();
  renderRecordTabs(records);
  renderSummary(payload, records, twin.comms || []);
  renderForm(selected, ticket, payload);
  renderCmdb(selected, ticket);
  renderWorkNotes(selected);
  renderEvents(events);
  renderRelatedRecords(records);
  renderComms(twin.comms || [], ticket);
}

function renderRunList() {
  if (!state.runs.length) {
    els.runList.innerHTML = '<p class="muted">No active backend runs yet.</p>';
    return;
  }
  els.runList.innerHTML = state.runs
    .map((run) => `
      <button class="run-card ${run.run_id === state.selectedRunId ? 'active' : ''}" type="button" data-run-id="${escapeHtml(run.run_id)}">
        <div>
          <strong>${escapeHtml(run.incident_id || run.run_id)}</strong>
          <span>${escapeHtml(run.title || 'NEXUS run')}</span>
          <small>${escapeHtml(run.status)} / ${escapeHtml(run.affected_ci || 'CI pending')}</small>
        </div>
      </button>
    `)
    .join('');
}

function renderRecordTabs(records) {
  els.recordTabs.innerHTML = records
    .map((record) => `
      <button class="record-tab ${record.id === state.selectedRecordId ? 'active' : ''}" type="button" data-record-id="${escapeHtml(record.id)}">
        <strong>${escapeHtml(record.number)}</strong>
        <span>${escapeHtml(titleCase(record.record_type))}</span>
      </button>
    `)
    .join('');
}

function renderSummary(payload, records, comms) {
  const notes = records.reduce((total, record) => total + (record.work_notes?.length || 0), 0);
  const sent = comms.filter((draft) => draft.status === 'sent').length;
  const pending = comms.filter((draft) => draft.status === 'pending_approval').length;
  const openProblems = records.filter((record) => record.record_type === 'problem').length;
  els.summaryStrip.innerHTML = [
    ['Run Status', payload.status],
    ['Records', records.length],
    ['Work Notes', notes],
    ['Comms Sent', sent],
    ['Pending Approvals', pending || openProblems],
  ]
    .map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`)
    .join('');
}

function renderForm(record, ticket, payload) {
  els.recordHeading.textContent = `${record.number} / ${record.title}`;
  els.recordState.textContent = record.state;
  els.recordDescription.textContent = record.description || ticket.current_state || 'No description.';
  const site = inferSite(record.affected_ci, record.business_service);
  const fields = [
    ['Number', record.number],
    ['Type', titleCase(record.record_type)],
    ['State', record.state],
    ['Priority', record.priority || ticket.priority],
    ['Assignment group', record.owner_group],
    ['Business service', record.business_service],
    ['Affected CI', record.affected_ci],
    ['CI site', site],
    ['Risk', record.risk || riskFromPriority(record.priority || ticket.priority)],
    ['Impact', impactFromPriority(record.priority || ticket.priority)],
    ['Urgency', urgencyFromPriority(record.priority || ticket.priority)],
    ['Run ID', payload.run_id],
  ];
  els.fieldGrid.innerHTML = fields
    .map(([label, value]) => `
      <div>
        <dt>${escapeHtml(label)}</dt>
        <dd>${escapeHtml(value || 'Pending')}</dd>
      </div>
    `)
    .join('');
}

function renderCmdb(record, ticket) {
  const site = inferSite(record.affected_ci, record.business_service);
  const fields = [
    ['CI Name', record.affected_ci],
    ['Class', inferCiClass(record.affected_ci)],
    ['Site', site],
    ['Operational status', record.state === 'Resolved' ? 'Operational' : 'Degraded'],
    ['Environment', ticket.environment || 'synthetic-hcl-managed-infra'],
    ['Owner group', record.owner_group],
  ];
  els.cmdbGrid.innerHTML = fields
    .map(([label, value]) => `
      <div>
        <dt>${escapeHtml(label)}</dt>
        <dd>${escapeHtml(value)}</dd>
      </div>
    `)
    .join('');

  const metrics = Object.entries(ticket.metric_snapshot || {}).filter(([key]) => key !== 'team');
  els.metricBox.innerHTML = `
    <span class="eyebrow">Issue metrics</span>
    <ul>
      ${
        metrics.length
          ? metrics.map(([key, value]) => `<li>${escapeHtml(titleCase(key))}: ${escapeHtml(value)}</li>`).join('')
          : `<li>${escapeHtml(ticket.current_state || 'No metric snapshot available.')}</li>`
      }
    </ul>
  `;
}

function renderWorkNotes(record) {
  const notes = [...(record.work_notes || [])].reverse();
  els.workNoteTitle.textContent = `${record.number} work notes`;
  els.workNoteCount.textContent = `${notes.length} notes`;
  if (!notes.length) {
    els.workNotes.innerHTML = '<p class="muted">No work notes yet.</p>';
    return;
  }
  els.workNotes.innerHTML = notes
    .map((note, index) => `
      <article class="work-note ${index === 0 ? 'latest' : ''}">
        <div class="work-note-head">
          <strong>${escapeHtml(note.author || 'NEXUS-RESOLVE')}</strong>
          <span>${escapeHtml(formatDate(note.timestamp))}</span>
        </div>
        ${note.source_event ? `<span class="source-chip">${escapeHtml(note.source_event)}</span>` : ''}
        <pre>${escapeHtml(note.note)}</pre>
      </article>
    `)
    .join('');
}

function renderEvents(events) {
  const visible = [...events].reverse();
  els.eventCount.textContent = `${events.length} events`;
  if (!visible.length) {
    els.eventStream.innerHTML = '<p class="muted">Waiting for backend events.</p>';
    return;
  }
  els.eventStream.innerHTML = visible
    .map((event, index) => `
      <article class="event-card ${index === 0 ? 'latest' : ''}">
        <div class="event-row">
          <strong>${escapeHtml(event.title)}</strong>
          <span>#${escapeHtml(event.sequence)} / ${escapeHtml(formatDate(event.timestamp))}</span>
        </div>
        <code>${escapeHtml(event.type)}</code>
        <p>${escapeHtml(event.message)}</p>
      </article>
    `)
    .join('');
}

function renderRelatedRecords(records) {
  els.relatedTable.innerHTML = records
    .map((record) => `
      <tr>
        <td><button class="record-link" type="button" data-record-id="${escapeHtml(record.id)}">${escapeHtml(record.number)}</button></td>
        <td>${escapeHtml(titleCase(record.record_type))}</td>
        <td>${escapeHtml(record.state)}</td>
        <td>${escapeHtml(record.owner_group)}</td>
        <td>${escapeHtml((record.linked_records || []).join(', ') || 'Primary')}</td>
      </tr>
    `)
    .join('');
}

function renderComms(comms, ticket) {
  if (!comms.length) {
    els.commsList.innerHTML = '<p class="muted">No communication drafts yet.</p>';
    return;
  }
  els.commsList.innerHTML = comms
    .map((draft) => {
      const locked = isCommsLocked(draft, ticket);
      const pending = draft.status === 'pending_approval';
      return `
        <article class="comms-card" data-status="${escapeHtml(draft.status)}" data-locked="${String(locked)}">
          <span>${escapeHtml(titleCase(draft.channel))} / ${escapeHtml(draft.status)}</span>
          <strong>${escapeHtml(draft.title)}</strong>
          <p>${escapeHtml(draft.subject)}</p>
          <p>${escapeHtml(draft.body)}</p>
          <p class="muted">${escapeHtml((draft.participants?.length ? draft.participants : draft.recipients || []).join(', '))}</p>
          <div class="comms-actions">
            ${
              locked
                ? '<span class="muted">P1/P2 only</span>'
                : pending
                  ? `
                    <button type="button" class="reject" data-reject-draft="${escapeHtml(draft.id)}">Reject</button>
                    <button type="button" class="send" data-approve-draft="${escapeHtml(draft.id)}">Approve Send</button>
                  `
                  : `<span class="muted">${escapeHtml(draft.status === 'sent' ? `Sent ${formatDate(draft.sent_at)}` : `Rejected ${formatDate(draft.rejected_at)}`)}</span>`
            }
          </div>
        </article>
      `;
    })
    .join('');
}

function isCommsLocked(draft, ticket) {
  return (
    draft.status === 'pending_approval' &&
    MAJOR_COMMS_CHANNELS.has(draft.channel) &&
    !['P1', 'P2'].includes(ticket.priority)
  );
}

function inferSite(ci, service) {
  const value = `${ci || ''} ${service || ''}`.toLowerCase();
  if (value.includes('pay')) return 'US-EAST-PAYMENTS / App Cluster';
  if (value.includes('cloud')) return 'AWS us-east-1 / Customer Portal';
  if (value.includes('vpn')) return 'Global Edge / Remote Access';
  if (value.includes('iam') || value.includes('ad-')) return 'HYD-IDM-01 / Identity Core';
  if (value.includes('backup')) return 'BOS-DR-02 / Backup Fabric';
  if (value.includes('win') || value.includes('claims')) return 'HYD-DC-01 / Windows Server Farm';
  if (value.includes('mon')) return 'Global NOC / Monitoring Core';
  return 'Synthetic Site / HCL Managed Infra';
}

function inferCiClass(ci) {
  const value = String(ci || '').toLowerCase();
  if (value.includes('db')) return 'Application DB Pool';
  if (value.includes('cloud') || value.includes('vm')) return 'Cloud VM';
  if (value.includes('vpn')) return 'Network Edge';
  if (value.includes('iam') || value.includes('ad')) return 'Identity Service';
  if (value.includes('backup')) return 'Backup Job';
  if (value.includes('mon')) return 'Monitoring Correlator';
  if (value.includes('win')) return 'Windows Server';
  return 'Application CI';
}

function riskFromPriority(priority) {
  if (priority === 'P1' || priority === 'P2') return 'High operational visibility';
  if (priority === 'P3') return 'Medium';
  return 'Low';
}

function impactFromPriority(priority) {
  if (priority === 'P1') return '1 - Enterprise';
  if (priority === 'P2') return '2 - Major service';
  if (priority === 'P3') return '3 - Service degraded';
  return '4 - Single CI / low impact';
}

function urgencyFromPriority(priority) {
  if (priority === 'P1' || priority === 'P2') return '1 - Immediate';
  if (priority === 'P3') return '2 - Soon';
  return '3 - Normal';
}

async function startScenario(scenarioId) {
  setWsState('Starting run', 'neutral');
  const payload = await fetchJson(`${API_BASE}/api/incidents`, {
    method: 'POST',
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
  state.selectedRunId = payload.run_id;
  await refreshCurrent();
  await refreshRuns();
}

async function runAction(action) {
  if (!state.selectedRunId) return;
  await fetchJson(`${API_BASE}/api/runs/${encodeURIComponent(state.selectedRunId)}/${action}`, {
    method: 'POST',
    body: '{}',
  });
  await refreshCurrent();
}

async function commsAction(draftId, action) {
  if (!state.selectedRunId) return;
  await fetchJson(
    `${API_BASE}/api/runs/${encodeURIComponent(state.selectedRunId)}/comms/${encodeURIComponent(draftId)}/${action}`,
    {
      method: 'POST',
      body: JSON.stringify({
        operator: 'Local SNOW Approver',
        role: 'Incident Commander',
        reason: `${titleCase(action)} from Local SNOW Desk demo.`,
      }),
    },
  );
  await refreshCurrent();
}

document.addEventListener('click', async (event) => {
  const runButton = event.target.closest('[data-run-id]');
  const recordButton = event.target.closest('[data-record-id]');
  const startButton = event.target.closest('[data-start-scenario]');
  const approveDraft = event.target.closest('[data-approve-draft]');
  const rejectDraft = event.target.closest('[data-reject-draft]');
  const actionButton = event.target.closest('[data-action]');

  try {
    if (runButton) {
      state.selectedRunId = runButton.dataset.runId;
      await refreshCurrent();
      return;
    }
    if (recordButton) {
      state.selectedRecordId = recordButton.dataset.recordId;
      render();
      return;
    }
    if (startButton) {
      await startScenario(startButton.dataset.startScenario);
      return;
    }
    if (approveDraft) {
      await commsAction(approveDraft.dataset.approveDraft, 'approve');
      return;
    }
    if (rejectDraft) {
      await commsAction(rejectDraft.dataset.rejectDraft, 'reject');
      return;
    }
    if (actionButton) {
      const action = actionButton.dataset.action;
      if (action === 'refresh') {
        await refreshRuns();
        await refreshCurrent();
      }
      if (action === 'approve-run') await runAction('approve');
      if (action === 'observe-run') await runAction('observe');
      if (action === 'close-run') await runAction('close');
    }
  } catch (error) {
    setWsState(error instanceof Error ? error.message : 'Action failed', 'danger');
  }
});

window.addEventListener('beforeunload', () => {
  if (state.socket) state.socket.close();
});

async function init() {
  await refreshRuns();
  await refreshCurrent();
  state.refreshTimer = window.setInterval(async () => {
    await refreshRuns();
    await refreshCurrent();
  }, 5000);
}

init();
