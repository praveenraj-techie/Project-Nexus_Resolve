const DEFAULT_SCENARIO_ID = 'disk-space';
const DASHBOARD_BASE = 'http://localhost:5173/#/incident/';
const API_BASE = 'http://127.0.0.1:8000';

let scenarios = [];
let selectedScenario = null;
let selectedTeam = 'All';
let runToken = 0;
let liveApiEvidence = null;
let liveApiRunId = null;
const timers = new Set();
const approvalResolvers = new Map();

const fallbackScenario = {
  scenario_id: 'command-centre-alert-storm',
  team: 'Command Centre',
  alert_type: 'Major incident alert storm / duplicate alerts',
  incident: {
    incident_id: 'INC-2026-00430',
    priority: 'P2',
    affected_ci: 'MON-CORR-01',
    business_service: 'Enterprise Monitoring',
    current_state: '147 duplicate alerts opened in 12 minutes for the same checkout symptom.',
    requested_outcome: 'Correlate duplicates, suppress child alerts, and create a parent incident.',
  },
  sop: {
    id: 'SOP-CMD-ALERT-010',
    controls: [
      'Group alerts only when symptom, CI, and time window match.',
      'Do not bulk-close alerts without parent incident linkage.',
      'Require approval before suppression.',
      'Validate duplicate count and parent linkage.',
    ],
  },
  history: [
    { ticket_id: 'HIST-CMD-2026-001', outcome: 'resolved', safe: true },
    { ticket_id: 'HIST-CMD-2026-002', outcome: 'resolved', safe: true },
    { ticket_id: 'HIST-CMD-2026-003', outcome: 'resolved', safe: true },
    { ticket_id: 'HIST-CMD-2026-009', outcome: 'caused follow-up incident', safe: false },
    { ticket_id: 'HIST-CMD-2026-010', outcome: 'escalated', safe: true },
  ],
  initial_state: {
    summary: '147 duplicate alerts opened in 12 minutes for the same checkout symptom.',
    metrics: [
      { label: 'Duplicate Alerts', value: '147' },
      { label: 'Parent MI', value: 'Missing' },
      { label: 'Window', value: '12 min' },
    ],
    evidence_summary: {
      outcome: 'Proceed with SOP-governed mock remediation for Major incident alert storm / duplicate alerts.',
    },
  },
  after_state: {
    summary: 'Duplicate active alerts reduced from 147 to 0 with one parent incident and 147 child links.',
    metrics: [
      { label: 'Duplicate Alerts', value: '0 active' },
      { label: 'Parent MI', value: 'Created' },
      { label: 'Child Links', value: '147' },
    ],
  },
  plan: {
    summary: 'Correlate duplicate checkout alerts and create a parent incident in mock mode.',
    target_resources: ['MON-CORR-01', 'checkout-alert-group-2026-00430'],
    action_preview: 'Mock action: group 147 duplicate alerts, create parent MI, suppress matching child alerts for 30 minutes.',
    estimated_effect: 'Open duplicate alerts reduce from 147 to 1 parent incident with child links preserved.',
    safeguards: [
      'Mock-only execution in this demo.',
      'Human approval is required before remediation.',
      'SOP controls override unsafe historical precedent.',
      'Post-remediation validation is mandatory.',
    ],
    approval_required: true,
    uses_dry_run: true,
    mock_only: true,
    validation_steps: [
      'Confirm duplicate symptom and CI match.',
      'Validate parent incident is created.',
      'Validate child alerts are linked, not deleted.',
    ],
    escalation_condition: 'Escalate to incident commander if non-duplicate critical alerts remain.',
  },
  validation: {
    status: 'pass',
    message: 'Duplicate active alerts reduced from 147 to 0 with one parent incident and 147 child links.',
  },
  execution: {
    message: 'Mock correlation grouped duplicate alerts and preserved child alert evidence.',
  },
  rca: {
    root_cause: 'Monitoring correlation did not group repeated checkout symptoms quickly enough.',
    metrics: {
      'MTTR Estimate': '5 min',
      'Manual Steps Avoided': '6',
      'Audit Completeness': '100%',
    },
  },
};

const els = {
  landing: document.getElementById('landing-panel'),
  frontendPanel: document.getElementById('frontend-panel'),
  backendPanel: document.getElementById('backend-panel'),
  bothPanel: document.getElementById('both-panel'),
  teamTabs: document.getElementById('team-tabs'),
  alertList: document.getElementById('alert-list'),
  frontendTimeline: document.getElementById('frontend-timeline'),
  backendTerminal: document.getElementById('backend-terminal'),
  bothTimeline: document.getElementById('both-frontend-timeline'),
  bothTerminal: document.getElementById('both-terminal'),
  bothDecisionStack: document.getElementById('both-decision-stack'),
  frontendDashboardFrame: document.getElementById('frontend-dashboard-frame'),
  bothDashboardFrame: document.getElementById('both-dashboard-frame'),
  frontendDashboardRoute: document.getElementById('frontend-dashboard-route'),
  frontendOpenRoute: document.getElementById('frontend-open-route'),
  frontendFrameTitle: document.getElementById('frontend-frame-title'),
  topbarDashboardLink: document.getElementById('topbar-dashboard-link'),
  apiResponseBoard: document.getElementById('api-response-board'),
  apiBoardStatus: document.getElementById('api-board-status'),
  apiHealthTitle: document.getElementById('api-health-title'),
  apiHealthPacket: document.getElementById('api-health-packet'),
  bothApiStack: document.getElementById('both-api-stack'),
};

const steps = [
  {
    key: 'generate',
    title: 'Synthetic data packet loaded',
    front: 'The real dashboard route loads the selected incident workspace with team, CI, priority, service, state, and requested outcome.',
    cli: (s) => [
      '$ uvicorn services.backend.app.main:app --host 127.0.0.1 --port 8000',
      'GET /api/health -> 200 {"status":"ok","service":"nexus-resolve"}',
      `GET /api/scenarios -> selected ${s.scenario_id} for ${s.incident.incident_id}`,
      `$ python scripts/generate_scenarios.py --scenario ${s.scenario_id}`,
      `catalog: data/scenarios/catalog.json -> ${s.incident.incident_id}, ${s.team}, ${s.incident.affected_ci}`,
      `packet: ${s.incident.current_state}`,
    ],
    inspector: 'Scenario packet is synthetic HCL-style data: incident, SOP, history, metrics, plan template, validation, and RCA.',
    status: 'Intake',
  },
  {
    key: 'sop',
    title: 'SOP retrieved first',
    front: 'The action review is grounded in the SOP before any history ticket can influence the plan.',
    cli: (s) => [
      `POST /api/incidents {"scenario_id":"${s.scenario_id}"} -> {"run_id":"run-judge-${s.scenario_id}","status":"running"}`,
      `WS /ws/runs/run-judge-${s.scenario_id} -> ticket.received`,
      `retrieve_sop(ticket) -> ${s.sop.id}`,
      `WS event evidence.sop -> ${s.sop.id}`,
      `controls: ${s.sop.controls.length} guardrails loaded`,
      `rule: SOP outranks historical precedent`,
    ],
    inspector: 'The backend loads the governing SOP before comparing prior incidents.',
    status: 'SOP',
  },
  {
    key: 'history',
    title: 'History compared',
    front: 'Five similar tickets are summarized into safe examples, unsafe precedent, and escalation precedent.',
    cli: (s) => {
      const unsafe = s.history.filter((item) => !item.safe).map((item) => item.ticket_id);
      const escalated = s.history.filter((item) => item.outcome === 'escalated').map((item) => item.ticket_id);
      return [
        `retrieve_similar_tickets(ticket) -> ${s.history.length} records`,
        'WS event evidence.history -> safe/unsafe/escalation counts',
        `safe precedents: ${s.history.filter((item) => item.safe && item.outcome !== 'escalated').length}`,
        `unsafe precedent: ${unsafe.join(', ') || 'none'}`,
        `escalation precedent: ${escalated.join(', ') || 'none'}`,
      ];
    },
    inspector: 'The unsafe history is visible as evidence, but it is not allowed to become the plan.',
    status: 'History',
  },
  {
    key: 'openai',
    title: 'OpenAI structured decision',
    front: 'The agent summarizes why the action is allowed, what it will change, and which safeguards apply.',
    cli: (s) => [
      'NexusOpenAIClient.create_evidence_summary(ticket, sop, history, state)',
      'OpenAI Responses API parse -> EvidenceSummaryOutput typed JSON',
      'WS event evidence.summary -> Decision Evidence / Reason Summary',
      'NexusOpenAIClient.create_plan(ticket, sop, history, state)',
      'WS event plan.generated -> Action Review + selected action card',
      'reasoning: SOP beats unsafe history; approval required; mock-only execution',
      `outcome: ${s.initial_state.evidence_summary.outcome}`,
    ],
    inspector: 'OpenAI is used for typed decision support. Policy code and human approval still control execution.',
    status: 'OpenAI',
  },
  {
    key: 'policy',
    title: 'Policy gate evaluated',
    front: 'The run shows scope, dry-run, mock-only, validation, and approval checks before execution.',
    cli: (s) => {
      const p = planFor(s);
      return [
        'policy_check(plan, enforce_approval=false)',
        `target_resources: ${p.target_resources.join(', ')}`,
        `dry_run=${String(p.uses_dry_run)} mock_only=${String(p.mock_only)} approval_required=${String(p.approval_required)}`,
        'WS event policy.checked -> Policy Checks panel',
        'status: requires human approval before remediation',
      ];
    },
    inspector: 'The policy module blocks protected resources, destructive execution markers, missing validation, and missing approval.',
    status: 'Policy hold',
  },
  {
    key: 'approval',
    title: 'Human approval required',
    front: 'The run pauses. A human must approve the mock remediation package before execution can continue.',
    cli: () => [
      'WS event approval.summary -> Approval Decision card',
      'WS event approval.requested -> Human Approval Gate enabled',
      'approval_future created',
      'workflow paused: waiting for operator approval',
      'no remediation command has executed',
    ],
    inspector: 'This is the human-in-the-loop control point judges should see clearly.',
    status: 'Awaiting approval',
    waitsForApproval: true,
  },
  {
    key: 'execute',
    title: 'Mock remediation executed',
    front: 'After approval, synthetic state changes from red alert to green resolved metrics.',
    cli: (s) => [
      `POST /api/runs/run-judge-${s.scenario_id}/approve -> {"status":"approved"}`,
      'mock_execute(plan, before_state)',
      'WS event execution.mocked -> mock-only result',
      s.execution.message,
      `after metrics: ${s.after_state.metrics.map((m) => `${m.label}=${m.value}`).join(', ')}`,
    ],
    inspector: 'Execution is mock-only; no real infrastructure, cloud, AD, firewall, backup, IAM, or database call is made.',
    status: 'Executing',
    resolved: true,
  },
  {
    key: 'validate',
    title: 'Validation passed',
    front: 'The validation panel proves recovery with before-and-after metrics instead of only saying the issue is solved.',
    cli: (s) => [
      'validate_result(before_state, after_state)',
      `validation.status=${s.validation.status}`,
      `validation.message="${s.validation.message}"`,
      'WS event validation.passed -> Metrics ribbon turns green',
    ],
    inspector: 'Impact is measured with scenario-specific metrics, not a generic success message.',
    status: 'Validated',
    resolved: true,
  },
  {
    key: 'rca',
    title: 'RCA and audit evidence generated',
    front: 'The run closes with root cause, actions taken, business impact, follow-up, and audit-ready metrics.',
    cli: (s) => [
      'NexusOpenAIClient.create_rca(before_state, after_state)',
      'OpenAI Responses API parse -> RcaSummaryOutput typed JSON',
      'WS event rca.generated -> RCA Summary + RCA Outcome card',
      `root_cause: ${s.rca.root_cause}`,
      `metrics: ${Object.entries(s.rca.metrics).map(([key, value]) => `${key}=${value}`).join(', ')}`,
      'run status: ready for closure',
    ],
    inspector: 'The final artifact is an auditable incident record for judge review.',
    status: 'RCA ready',
    resolved: true,
  },
];

function text(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function setHtml(id, value) {
  const node = document.getElementById(id);
  if (node) node.innerHTML = value;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);
}

function planFor(scenario) {
  return scenario?.plan ?? scenario?.initial_state?.plan_template ?? fallbackScenario.plan;
}

function dashboardUrl(scenario = selectedScenario) {
  const scenarioId = scenario?.scenario_id ?? DEFAULT_SCENARIO_ID;
  return `${DASHBOARD_BASE}${encodeURIComponent(scenarioId)}`;
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

async function fetchJson(url, options = {}) {
  try {
    const response = await fetch(url, {
      cache: 'no-store',
      ...options,
      headers: {
        ...(options.headers ?? {}),
      },
    });
    const contentType = response.headers.get('content-type') ?? '';
    const payload = contentType.includes('application/json')
      ? await response.json()
      : await response.text();
    return { ok: response.ok, status: response.status, payload };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      payload: error instanceof Error ? error.message : 'request failed',
    };
  }
}

async function fetchBlobMeta(url) {
  try {
    const response = await fetch(url, { cache: 'no-store' });
    const blob = await response.blob();
    return {
      ok: response.ok,
      status: response.status,
      payload: {
        content_type: response.headers.get('content-type'),
        content_disposition: response.headers.get('content-disposition'),
        bytes: blob.size,
      },
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      payload: error instanceof Error ? error.message : 'request failed',
    };
  }
}

async function refreshLiveApiEvidence({ startRun = false } = {}) {
  const scenario = selectedScenario ?? fallbackScenario;
  const health = await fetchJson(`${API_BASE}/api/health`);
  const scenariosResponse = await fetchJson(`${API_BASE}/api/scenarios`);
  const serviceNowTicket = await fetchJson(
    `${API_BASE}/api/connectors/servicenow/mock-ticket/${scenario.scenario_id}`,
  );
  const policyBlock = await fetchJson(`${API_BASE}/api/policy/demo-block`);
  let startedRun = null;
  let snapshot = null;
  let auditPacket = null;
  let auditPdf = null;

  if (health.ok && startRun) {
    startedRun = await fetchJson(`${API_BASE}/api/incidents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenario.scenario_id }),
    });
    liveApiRunId = startedRun.payload?.run_id ?? liveApiRunId;
  }

  if (health.ok && liveApiRunId) {
    await wait(350);
    snapshot = await fetchJson(`${API_BASE}/api/runs/${liveApiRunId}`);
    auditPacket = await fetchJson(`${API_BASE}/api/runs/${liveApiRunId}/audit-packet`);
    auditPdf = await fetchBlobMeta(`${API_BASE}/api/runs/${liveApiRunId}/audit-report.pdf`);
  }

  liveApiEvidence = {
    fetched_at: new Date().toISOString(),
    health,
    scenarios: scenariosResponse,
    servicenow_ticket: serviceNowTicket,
    policy_block: policyBlock,
    started_run: startedRun,
    run_snapshot: snapshot,
    audit_packet: auditPacket,
    audit_pdf: auditPdf,
  };
  renderApiBoard();
  renderBothApiStack();
  syncBackendHealth();
  return liveApiEvidence;
}

async function approveLiveApiRun() {
  if (!liveApiRunId || !liveApiEvidence) return;
  await fetchJson(`${API_BASE}/api/runs/${liveApiRunId}/approve`, { method: 'POST' });
  await wait(500);
  liveApiEvidence.run_snapshot = await fetchJson(`${API_BASE}/api/runs/${liveApiRunId}`);
  liveApiEvidence.audit_packet = await fetchJson(`${API_BASE}/api/runs/${liveApiRunId}/audit-packet`);
  liveApiEvidence.audit_pdf = await fetchBlobMeta(`${API_BASE}/api/runs/${liveApiRunId}/audit-report.pdf`);
  renderApiBoard();
  renderBothApiStack();
}

function renderJsonCard(title, eyebrow, value, tone = 'neutral') {
  return `
    <article class="api-card ${tone}">
      <span>${escapeHtml(eyebrow)}</span>
      <strong>${escapeHtml(title)}</strong>
      <pre>${escapeHtml(prettyJson(value))}</pre>
    </article>
  `;
}

function apiEvidence(scenario = selectedScenario) {
  const s = scenario ?? fallbackScenario;
  const plan = planFor(s);
  const runId = `run-judge-${s.scenario_id}`;
  const safeCount = s.history.filter((item) => item.safe && item.outcome !== 'escalated').length;
  const unsafe = s.history.filter((item) => !item.safe).map((item) => item.ticket_id);
  const escalated = s.history.filter((item) => item.outcome === 'escalated').map((item) => item.ticket_id);

  const traceReplayCards = [
    {
      title: 'GET /api/health',
      eyebrow: 'Trace replay',
      tone: 'success',
      value: { status: 'ok', service: 'nexus-resolve', api_base: API_BASE },
    },
    {
      title: 'GET /api/scenarios',
      eyebrow: 'Dashboard catalog',
      value: {
        selected: s.scenario_id,
        team: s.team,
        incident_id: s.incident.incident_id,
        route: dashboardUrl(s),
      },
    },
    {
      title: 'POST /api/incidents',
      eyebrow: 'Start live run',
      tone: 'active',
      value: {
        request: { scenario_id: s.scenario_id },
        response: { run_id: runId, status: 'running' },
      },
    },
    {
      title: `WS /ws/runs/${runId}`,
      eyebrow: 'Trace replay stream',
      tone: 'stream',
      value: {
        emitted_events: [
          'ticket.received',
          'evidence.sop',
          'evidence.history',
          'evidence.summary',
          'plan.generated',
          'policy.checked',
          'approval.summary',
          'approval.requested',
          'execution.mocked',
          'validation.passed',
          'rca.generated',
        ],
        frontend_surfaces: [
          'Agent Timeline',
          'SOP And History',
          'Decision Evidence',
          'Action Review',
          'Policy Checks',
          'RCA Summary',
        ],
      },
    },
    {
      title: 'SOP + history payload',
      eyebrow: 'Governance evidence',
      value: {
        sop_id: s.sop.id,
        controls: s.sop.controls,
        history: {
          safe_precedents: safeCount,
          unsafe_precedents: unsafe,
          escalation_precedents: escalated,
        },
      },
    },
    {
      title: 'RemediationPlanOutput',
      eyebrow: 'Typed OpenAI output replay',
      tone: 'openai',
      value: {
        summary: plan.summary,
        target_resources: plan.target_resources,
        mock_only: plan.mock_only,
        uses_dry_run: plan.uses_dry_run,
        approval_required: plan.approval_required,
        estimated_effect: plan.estimated_effect,
      },
    },
  ];

  if (!liveApiEvidence) {
    return traceReplayCards;
  }

  const liveCards = [
    {
      title: 'LIVE GET /api/health',
      eyebrow: liveApiEvidence.health.ok ? 'FastAPI live' : 'FastAPI offline',
      tone: liveApiEvidence.health.ok ? 'success' : 'danger',
      value: {
        status: liveApiEvidence.health.status,
        response: liveApiEvidence.health.payload,
        fetched_at: liveApiEvidence.fetched_at,
      },
    },
    {
      title: 'LIVE GET /api/scenarios',
      eyebrow: 'Catalog live',
      tone: liveApiEvidence.scenarios.ok ? 'active' : 'danger',
      value: {
        status: liveApiEvidence.scenarios.status,
        selected: s.scenario_id,
        scenario_count: liveApiEvidence.scenarios.payload?.scenarios?.length ?? 'unavailable',
      },
    },
    {
      title: 'LIVE ServiceNow mock connector',
      eyebrow: 'Connector contract',
      tone: liveApiEvidence.servicenow_ticket.ok ? 'active' : 'danger',
      value: {
        status: liveApiEvidence.servicenow_ticket.status,
        response: liveApiEvidence.servicenow_ticket.payload,
      },
    },
    {
      title: 'LIVE GET /api/policy/demo-block',
      eyebrow: 'Policy live',
      tone: liveApiEvidence.policy_block.ok ? 'danger' : 'danger',
      value: {
        status: liveApiEvidence.policy_block.status,
        blocked_checks:
          liveApiEvidence.policy_block.payload?.checks?.filter((check) => check.status === 'blocked') ??
          liveApiEvidence.policy_block.payload,
      },
    },
    {
      title: liveApiRunId ? `LIVE GET /api/runs/${liveApiRunId}` : 'LIVE POST /api/incidents',
      eyebrow: liveApiEvidence.run_snapshot?.ok ? 'Run snapshot live' : 'Run pending',
      tone: liveApiEvidence.run_snapshot?.ok ? 'stream' : 'active',
      value: {
        started_run: liveApiEvidence.started_run?.payload ?? 'not started from this panel yet',
        snapshot_status: liveApiEvidence.run_snapshot?.status ?? 'not fetched',
        snapshot: liveApiEvidence.run_snapshot?.payload ?? null,
      },
    },
    {
      title: liveApiRunId ? 'LIVE audit packet hash' : 'LIVE audit packet pending',
      eyebrow: liveApiEvidence.audit_packet?.ok ? 'Audit live' : 'Audit pending',
      tone: liveApiEvidence.audit_packet?.ok ? 'openai' : 'active',
      value: {
        status: liveApiEvidence.audit_packet?.status ?? 'not fetched',
        audit_hash: liveApiEvidence.audit_packet?.payload?.audit_hash ?? null,
        safety: liveApiEvidence.audit_packet?.payload?.safety ?? null,
      },
    },
    {
      title: liveApiRunId ? 'LIVE audit PDF report' : 'LIVE audit PDF pending',
      eyebrow: liveApiEvidence.audit_pdf?.ok ? 'PDF export live' : 'PDF pending',
      tone: liveApiEvidence.audit_pdf?.ok ? 'openai' : 'active',
      value: {
        status: liveApiEvidence.audit_pdf?.status ?? 'not fetched',
        response: liveApiEvidence.audit_pdf?.payload ?? null,
      },
    },
  ];

  return [...liveCards, traceReplayCards[4]];
}

function renderApiBoard() {
  if (!els.apiResponseBoard) return;
  els.apiResponseBoard.innerHTML = apiEvidence()
    .map((card) => renderJsonCard(card.title, card.eyebrow, card.value, card.tone))
    .join('');
  text(
    'api-board-status',
    liveApiEvidence
      ? `${selectedScenario?.incident?.incident_id ?? 'Incident'} live API checked`
      : `${selectedScenario?.incident?.incident_id ?? 'Incident'} trace replay ready`,
  );
}

function renderBothApiStack() {
  if (!els.bothApiStack || !selectedScenario) return;
  const cards = liveApiEvidence
    ? apiEvidence(selectedScenario)
        .filter((card) =>
          /ServiceNow|policy|runs|audit|scenarios/.test(card.title),
        )
        .slice(0, 6)
    : apiEvidence(selectedScenario).slice(1, 5);
  els.bothApiStack.innerHTML = cards
    .map(
      (card) => {
        const detail =
          card.value?.audit_hash ??
          card.value?.snapshot_status ??
          card.value?.status ??
          card.value?.scenario_count ??
          '';
        return `
        <article class="api-mini-card ${card.tone ?? ''}">
          <span>${escapeHtml(card.eyebrow)}</span>
          <strong>${escapeHtml(card.title)}</strong>
          ${detail ? `<small>${escapeHtml(detail)}</small>` : ''}
        </article>
      `;
      },
    )
    .join('');
}

function updateDashboardFrames(forceReload = false) {
  if (!selectedScenario) return;
  const url = dashboardUrl(selectedScenario);
  const title = `${selectedScenario.incident.incident_id} / ${selectedScenario.alert_type}`;
  text('frontend-dashboard-route', url);
  text('frontend-frame-title', title);
  text('frontend-run-status', 'Real dashboard route');
  if (els.frontendOpenRoute) els.frontendOpenRoute.href = url;
  if (els.topbarDashboardLink) els.topbarDashboardLink.href = url;
  for (const frame of [els.frontendDashboardFrame, els.bothDashboardFrame]) {
    if (!frame) continue;
    if (forceReload || frame.getAttribute('src') !== url) {
      frame.setAttribute('src', url);
    }
  }
}

async function syncBackendHealth() {
  if (liveApiEvidence?.health) {
    const result = liveApiEvidence.health;
    if (result.ok) {
      text('api-health-title', 'FastAPI online');
      text('api-health-packet', `${API_BASE}/api/health -> ${result.status} ${prettyJson(result.payload)}`);
      return;
    }
  }
  try {
    const response = await fetch(`${API_BASE}/api/health`, { cache: 'no-store' });
    const payload = await response.json();
    text('api-health-title', 'FastAPI online');
    text('api-health-packet', `${API_BASE}/api/health -> ${response.status} ${prettyJson(payload)}`);
  } catch {
    text('api-health-title', 'FastAPI not reachable');
    text('api-health-packet', `${API_BASE}/api/health did not respond. Start scripts/dev-backend.cmd for live API evidence.`);
  }
}

function clearTimers() {
  for (const timer of timers) clearTimeout(timer);
  timers.clear();
}

function wait(ms) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      timers.delete(timer);
      resolve();
    }, ms);
    timers.add(timer);
  });
}

function modeFromHash() {
  const hash = location.hash.replace('#', '');
  return ['frontend', 'backend', 'both'].includes(hash) ? hash : null;
}

function showMode(mode) {
  const current = mode || null;
  document.querySelectorAll('.mode-card').forEach((button) => {
    const active = button.dataset.mode === current;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-selected', String(active));
  });
  els.landing.classList.toggle('is-active', !current);
  els.frontendPanel.classList.toggle('is-active', current === 'frontend');
  els.backendPanel.classList.toggle('is-active', current === 'backend');
  els.bothPanel.classList.toggle('is-active', current === 'both');
  if (current && location.hash !== `#${current}`) history.replaceState(null, '', `#${current}`);
}

function priorityTone(priority) {
  if (priority === 'P2') return 'danger';
  if (priority === 'P3') return 'warning';
  return 'neutral';
}

function metricSummary(metrics, fallback) {
  const first = metrics?.[0];
  if (!first) return fallback;
  return `${first.value} ${first.label.toLowerCase()}`.trim();
}

function renderTeamTabs() {
  const teams = ['All', ...new Set(scenarios.map((scenario) => scenario.team))];
  els.teamTabs.innerHTML = teams
    .map(
      (team) => `
        <button class="team-tab ${team === selectedTeam ? 'is-active' : ''}" type="button" data-team="${escapeHtml(team)}">
          ${escapeHtml(team)}
        </button>
      `,
    )
    .join('');
}

function renderAlertList() {
  const visible = scenarios.filter((scenario) => selectedTeam === 'All' || scenario.team === selectedTeam);
  text('frontend-alert-count', `${scenarios.length} open`);
  els.alertList.innerHTML = visible
    .map(
      (scenario) => `
        <button class="alert-item ${scenario.scenario_id === selectedScenario.scenario_id ? 'is-active' : ''}" type="button" data-scenario="${escapeHtml(scenario.scenario_id)}">
          <span class="priority-dot ${priorityTone(scenario.incident.priority)}">${escapeHtml(scenario.incident.priority)}</span>
          <span>
            <strong>${escapeHtml(scenario.team)}</strong>
            <em>${escapeHtml(scenario.alert_type)}</em>
            <small>${escapeHtml(scenario.incident.incident_id)} / ${escapeHtml(scenario.incident.affected_ci)}</small>
          </span>
        </button>
      `,
    )
    .join('');
}

function renderIncident() {
  const s = selectedScenario;
  if (!s) return;
  text('incident-alert', s.alert_type);
  text('incident-state', s.incident.current_state);
  text('incident-id', s.incident.incident_id);
  text('incident-priority', s.incident.priority);
  text('incident-team', s.team);
  text('incident-ci', s.incident.affected_ci);
  text('incident-service', s.incident.business_service);
  text('incident-outcome', s.incident.requested_outcome);
  text('before-main', metricSummary(s.initial_state.metrics, s.incident.current_state));
  text('before-detail', s.initial_state.summary);
  text('after-main', 'Waiting for run');
  text('after-detail', 'Mock remediation has not executed yet.');
  text('both-alert-title', s.alert_type);
  text('both-before', metricSummary(s.initial_state.metrics, 'Active'));
  text('both-after', 'Pending');
  updateDashboardFrames();
  renderActionReview();
  renderApiBoard();
  renderBothApiStack();
  resetRunVisuals('frontend');
  resetRunVisuals('backend');
  resetRunVisuals('both');
}

function renderActionReview() {
  const p = planFor(selectedScenario);
  setHtml(
    'action-review',
    `
      <dl class="review-list">
        <div><dt>Target</dt><dd>${escapeHtml(p.target_resources.join(', '))}</dd></div>
        <div><dt>Preview</dt><dd>${escapeHtml(p.action_preview)}</dd></div>
        <div><dt>Expected effect</dt><dd>${escapeHtml(p.estimated_effect)}</dd></div>
        <div><dt>Escalate if</dt><dd>${escapeHtml(p.escalation_condition)}</dd></div>
      </dl>
      <div class="safeguard-list">
        ${p.safeguards.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}
      </div>
    `,
  );
}

function renderBackendPackets() {
  const s = selectedScenario;
  const p = planFor(s);
  text('data-packet', `${s.incident.incident_id} / ${s.team} / ${s.incident.affected_ci}. ${s.incident.current_state}`);
  text(
    'compare-packet',
    `${s.sop.id}; ${s.history.length} tickets compared; ${
      s.history.filter((item) => !item.safe).length
    } unsafe precedent flagged.`,
  );
  text('openai-packet', `${s.initial_state.evidence_summary.outcome} Output is typed and validated before policy checks.`);
  text('policy-packet', `Approval required=${p.approval_required}; dry-run=${p.uses_dry_run}; mock-only=${p.mock_only}.`);
  syncBackendHealth();
}

function resetRunVisuals(scope) {
  clearApproval(scope);
  if (scope === 'frontend') {
    updateDashboardFrames(true);
    text('frontend-run-status', 'Frame refreshed');
  }
  if (scope === 'backend') {
    els.backendTerminal.innerHTML = '';
    renderBackendPackets();
    renderApiBoard();
    text('api-board-status', 'Ready');
  }
  if (scope === 'both') {
    els.bothTimeline.innerHTML = '';
    els.bothTerminal.innerHTML = '';
    els.bothDecisionStack.innerHTML = '';
    renderBothApiStack();
    updateDashboardFrames();
    text('both-front-status', 'Ready');
    text('both-back-status', 'Ready');
    text('both-after', 'Pending');
  }
}

function setApproval(scope, enabled) {
  document.querySelectorAll(`[data-approve="${scope}"], [data-reject="${scope}"]`).forEach((button) => {
    button.disabled = !enabled;
  });
}

function clearApproval(scope) {
  approvalResolvers.delete(scope);
  setApproval(scope, false);
}

function approve(scope) {
  const resolver = approvalResolvers.get(scope);
  if (resolver) resolver(true);
}

function reject(scope) {
  const resolver = approvalResolvers.get(scope);
  if (resolver) resolver(false);
}

function appendTimeline(container, step, tone = 'neutral') {
  if (!container) return;
  const node = document.createElement('article');
  node.className = `timeline-item ${tone}`;
  node.innerHTML = `
    <span></span>
    <div>
      <strong>${escapeHtml(step.title)}</strong>
      <p>${escapeHtml(step.front)}</p>
    </div>
  `;
  container.appendChild(node);
  container.scrollTop = container.scrollHeight;
}

async function typeLine(container, line, tone = 'normal') {
  if (!container) return;
  const row = document.createElement('div');
  row.className = `terminal-line ${tone}`;
  container.appendChild(row);
  const words = line.split(' ');
  for (const word of words) {
    row.textContent += `${word} `;
    container.scrollTop = container.scrollHeight;
    await wait(42);
  }
}

async function emitBackendLines(container, step, scenario) {
  for (const line of step.cli(scenario)) {
    await typeLine(container, line, step.key === 'approval' ? 'hold' : step.resolved ? 'success' : 'normal');
  }
}

function addDecisionCard(step) {
  const node = document.createElement('article');
  node.className = `decision-card ${step.resolved ? 'success' : step.waitsForApproval ? 'hold' : ''}`;
  node.innerHTML = `
    <span>${escapeHtml(step.status)}</span>
    <strong>${escapeHtml(step.title)}</strong>
    <p>${escapeHtml(step.inspector)}</p>
  `;
  els.bothDecisionStack.appendChild(node);
  els.bothDecisionStack.scrollTop = els.bothDecisionStack.scrollHeight;
}

function applyResolvedState(scope) {
  const after = selectedScenario.after_state.metrics;
  if (scope === 'frontend') {
    text('after-main', metricSummary(after, 'Resolved'));
    text('after-detail', selectedScenario.after_state.summary);
    text('frontend-run-status', 'Resolved');
    text('approval-state', 'Approved');
  }
  if (scope === 'both') {
    text('both-after', metricSummary(after, 'Resolved'));
    text('both-front-status', 'Resolved');
    text('both-back-status', 'Validated');
  }
}

async function waitForApproval(scope, token) {
  setApproval(scope, true);
  if (scope === 'frontend') {
    text('frontend-run-status', 'Waiting for approval');
    text('approval-state', 'Approval required');
  }
  if (scope === 'both') {
    text('both-front-status', 'Waiting for approval');
    text('both-back-status', 'Paused');
  }
  const approved = await new Promise((resolve) => {
    approvalResolvers.set(scope, resolve);
  });
  if (token !== runToken) return false;
  clearApproval(scope);
  if (!approved) {
    await handleRejected(scope);
    return false;
  }
  await approveLiveApiRun();
  return true;
}

async function handleRejected(scope) {
  const rejectedStep = {
    title: 'Human rejected remediation',
    front: 'The workflow stopped safely. No mock execution was performed.',
  };
  if (scope === 'frontend') {
    appendTimeline(els.frontendTimeline, rejectedStep, 'danger');
    text('frontend-run-status', 'Rejected');
    text('approval-state', 'Rejected');
  }
  if (scope === 'backend') {
    await typeLine(els.backendTerminal, 'operator decision: rejected -> workflow stopped safely', 'danger');
  }
  if (scope === 'both') {
    appendTimeline(els.bothTimeline, rejectedStep, 'danger');
    await typeLine(els.bothTerminal, 'operator decision: rejected -> workflow stopped safely', 'danger');
    text('both-front-status', 'Rejected');
    text('both-back-status', 'Stopped');
  }
}

async function startRun(scope) {
  runToken += 1;
  const token = runToken;
  clearTimers();
  resetRunVisuals(scope);
  const scenario = selectedScenario;

  if (scope === 'frontend') {
    updateDashboardFrames(true);
    text('frontend-run-status', 'Real dashboard refreshed');
    return;
  }

  await refreshLiveApiEvidence({ startRun: true });

  if (scope === 'frontend') text('frontend-run-status', 'Running');
  if (scope === 'both') {
    text('both-front-status', 'Running');
    text('both-back-status', 'Running');
  }

  for (const step of steps) {
    if (token !== runToken) return;
    if (scope === 'frontend') {
      appendTimeline(els.frontendTimeline, step, step.waitsForApproval ? 'hold' : step.resolved ? 'success' : 'neutral');
      text('frontend-run-status', step.status);
    }
    if (scope === 'backend') {
      await emitBackendLines(els.backendTerminal, step, scenario);
    }
    if (scope === 'both') {
      appendTimeline(els.bothTimeline, step, step.waitsForApproval ? 'hold' : step.resolved ? 'success' : 'neutral');
      text('both-front-status', step.status);
      text('both-back-status', step.status);
      addDecisionCard(step);
      await emitBackendLines(els.bothTerminal, step, scenario);
    }

    if (step.waitsForApproval) {
      const approved = await waitForApproval(scope, token);
      if (!approved) return;
    }

    if (step.resolved) applyResolvedState(scope);
    await wait(scope === 'backend' ? 420 : 850);
  }

  if (scope === 'frontend') text('frontend-run-status', 'Ready to close');
  if (scope === 'backend') await typeLine(els.backendTerminal, 'audit: RCA, validation, approval, policy checks, and event stream complete', 'success');
  if (scope === 'both') {
    text('both-front-status', 'Ready to close');
    text('both-back-status', 'Audit complete');
  }
}

function useScenarios(nextScenarios) {
  scenarios = nextScenarios;
  selectedScenario = scenarios.find((scenario) => scenario.scenario_id === DEFAULT_SCENARIO_ID) ?? scenarios[0];
  renderTeamTabs();
  renderAlertList();
  renderIncident();
  renderBackendPackets();
}

async function loadScenarios() {
  const catalogUrls = ['/data/scenarios/catalog.json', '../../data/scenarios/catalog.json'];
  for (const url of catalogUrls) {
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) continue;
      const loaded = await response.json();
      if (Array.isArray(loaded) && loaded.length > 0) {
        useScenarios(loaded);
        return;
      }
    } catch {
      // Try the next URL, then keep the built-in fallback.
    }
  }
}

document.addEventListener('click', (event) => {
  const modeButton = event.target.closest('[data-mode]');
  if (modeButton) {
    showMode(modeButton.dataset.mode);
    return;
  }

  const startButton = event.target.closest('[data-start]');
  if (startButton) {
    startRun(startButton.dataset.start);
    return;
  }

  const resetButton = event.target.closest('[data-reset]');
  if (resetButton) {
    runToken += 1;
    clearTimers();
    resetRunVisuals(resetButton.dataset.reset);
    return;
  }

  const approveButton = event.target.closest('[data-approve]');
  if (approveButton) {
    approve(approveButton.dataset.approve);
    return;
  }

  const rejectButton = event.target.closest('[data-reject]');
  if (rejectButton) {
    reject(rejectButton.dataset.reject);
    return;
  }

  const teamButton = event.target.closest('[data-team]');
  if (teamButton) {
    selectedTeam = teamButton.dataset.team;
    renderTeamTabs();
    renderAlertList();
    return;
  }

  const scenarioButton = event.target.closest('[data-scenario]');
  if (scenarioButton) {
    const next = scenarios.find((scenario) => scenario.scenario_id === scenarioButton.dataset.scenario);
    if (!next) return;
    selectedScenario = next;
    renderAlertList();
    renderIncident();
  }
});

window.addEventListener('hashchange', () => showMode(modeFromHash()));

useScenarios([fallbackScenario]);
showMode(modeFromHash());
loadScenarios().then(() => showMode(modeFromHash()));
