import type {
  ItsmTwinState,
  PolicyCheck,
  RunEvent,
  ScenarioSummary,
  ServiceNowIncidentHistoryEntry,
  ServiceNowIncidentLookup,
  StartIncidentResponse,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';
const STATIC_BASE = import.meta.env.BASE_URL;

export async function healthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export async function fetchScenarios(): Promise<ScenarioSummary[]> {
  const response = await fetch(`${STATIC_BASE}data/scenarios/catalog.json`);
  if (!response.ok) {
    throw new Error('Scenario catalog is unavailable.');
  }
  const catalog = (await response.json()) as Array<{
    scenario_id: string;
    team: string;
    alert_type: string;
    incident: {
      incident_id: string;
      priority: string;
      title: string;
      business_service: string;
      affected_ci: string;
      current_state: string;
      requested_outcome: string;
    };
    rca?: {
      metrics?: Record<string, string>;
    };
    replay_outcome?: 'success' | 'rejected';
  }>;
  return catalog.map((scenario) => ({
    scenario_id: scenario.scenario_id,
    team: scenario.team,
    alert_type: scenario.alert_type,
    incident_id: scenario.incident.incident_id,
    priority: scenario.incident.priority,
    title: scenario.incident.title,
    business_service: scenario.incident.business_service,
    affected_ci: scenario.incident.affected_ci,
    current_state: scenario.incident.current_state,
    requested_outcome: scenario.incident.requested_outcome,
    mttr_minutes: minutesFromMetric(scenario.rca?.metrics?.['MTTR Estimate']),
    manual_steps_avoided: Number(scenario.rca?.metrics?.['Manual Steps Avoided'] ?? 0),
    audit_completeness: scenario.rca?.metrics?.['Audit Completeness'],
    replay_outcome: scenario.replay_outcome ?? 'success',
  }));
}

export async function startIncident(
  scenarioId: string,
): Promise<StartIncidentResponse> {
  const response = await fetch(`${API_BASE}/api/incidents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
  if (!response.ok) {
    let detail = 'Unable to start local run.';
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function approveRun(runId: string): Promise<void> {
  await postRunAction(`${API_BASE}/api/runs/${runId}/approve`, 'Unable to approve this run.');
}

export async function rejectRun(runId: string): Promise<void> {
  await postRunAction(`${API_BASE}/api/runs/${runId}/reject`, 'Unable to reject this run.');
}

export async function closeRun(runId: string): Promise<void> {
  await postRunAction(`${API_BASE}/api/runs/${runId}/close`, 'Unable to close this run.');
}

export async function observeRun(runId: string): Promise<void> {
  await postRunAction(`${API_BASE}/api/runs/${runId}/observe`, 'Unable to observe this run.');
}

export async function fetchPolicyDemoBlock(): Promise<PolicyCheck[]> {
  const response = await fetch(`${API_BASE}/api/policy/demo-block`, {
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error('Unable to load protected-resource policy demo.');
  }
  const payload = (await response.json()) as { checks: PolicyCheck[] };
  return payload.checks;
}

export async function fetchServiceNowIncidents(): Promise<ServiceNowIncidentHistoryEntry[]> {
  const response = await fetch(`${API_BASE}/api/connectors/servicenow/incidents`, {
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error('Unable to load ServiceNow PDI history.');
  }
  const payload = (await response.json()) as { incidents: ServiceNowIncidentHistoryEntry[] };
  return payload.incidents;
}

export async function lookupServiceNowIncident(
  incidentNumber: string,
): Promise<ServiceNowIncidentLookup> {
  const response = await fetch(
    `${API_BASE}/api/connectors/servicenow/incidents/${encodeURIComponent(incidentNumber)}`,
    { cache: 'no-store' },
  );
  if (!response.ok) {
    let detail = 'Unable to verify ServiceNow PDI incident.';
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function fetchItsmTwin(runId: string): Promise<ItsmTwinState> {
  const response = await fetch(`${API_BASE}/api/runs/${runId}/itsm-twin`, {
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error('Unable to load Local ITSM Twin state.');
  }
  return response.json();
}

export async function approveCommsDraft(
  runId: string,
  draftId: string,
): Promise<ItsmTwinState> {
  return commsAction(
    `${API_BASE}/api/runs/${runId}/comms/${encodeURIComponent(draftId)}/approve`,
    'Unable to approve simulated communication.',
  );
}

export async function rejectCommsDraft(
  runId: string,
  draftId: string,
): Promise<ItsmTwinState> {
  return commsAction(
    `${API_BASE}/api/runs/${runId}/comms/${encodeURIComponent(draftId)}/reject`,
    'Unable to reject simulated communication.',
  );
}

export function auditPacketUrl(runId: string): string {
  return `${API_BASE}/api/runs/${runId}/audit-packet`;
}

export function auditReportPdfUrl(runId: string): string {
  return `${API_BASE}/api/runs/${runId}/audit-report.pdf`;
}

export type ServiceNowWorkNoteResult = {
  sent: boolean;
  mode:
    | 'dry_run'
    | 'not_configured'
    | 'live'
    | 'no_incident'
    | 'missing_sys_id'
    | 'missing_incident';
  missing?: string[];
  request: {
    connector: string;
    configured: boolean;
    table: string;
    incident_number?: string | null;
    sys_id?: string | null;
    synthetic_incident_id?: string | null;
    synthetic_only: boolean;
    real_execution_disabled: boolean;
    body: {
      work_notes: string;
      [key: string]: string;
    };
  };
};

export async function previewServiceNowWorkNote(runId: string): Promise<ServiceNowWorkNoteResult> {
  return serviceNowWorkNote(runId, true, 'Unable to preview ServiceNow work-note payload.');
}

export async function writeServiceNowWorkNote(runId: string): Promise<ServiceNowWorkNoteResult> {
  return serviceNowWorkNote(runId, false, 'Unable to write ServiceNow work note.');
}

async function serviceNowWorkNote(
  runId: string,
  dryRun: boolean,
  errorMessage: string,
): Promise<ServiceNowWorkNoteResult> {
  const response = await fetch(`${API_BASE}/api/runs/${runId}/servicenow/work-note`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dry_run: dryRun }),
  });
  if (!response.ok) {
    let detail = errorMessage;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }
  return response.json();
}

export function connectRunStream(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onClose: () => void,
): WebSocket {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = `/ws/runs/${runId}`;
  const socket = new WebSocket(url);
  socket.onmessage = (message) => onEvent(JSON.parse(message.data) as RunEvent);
  socket.onclose = onClose;
  return socket;
}

function minutesFromMetric(value?: string): number | undefined {
  if (!value) return undefined;
  const match = value.match(/[\d.]+/);
  if (!match) return undefined;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : undefined;
}

async function postRunAction(url: string, errorMessage: string): Promise<void> {
  const response = await fetch(url, { method: 'POST' });
  if (!response.ok) {
    throw new Error(errorMessage);
  }
}

async function commsAction(url: string, errorMessage: string): Promise<ItsmTwinState> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    let detail = errorMessage;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }
  return response.json();
}
