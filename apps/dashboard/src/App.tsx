import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, PlayCircle, ShieldCheck } from 'lucide-react';
import {
  approveRun,
  closeRun,
  connectRunStream,
  fetchPolicyDemoBlock,
  fetchScenarios,
  fetchServiceNowIncidents,
  healthCheck,
  lookupServiceNowIncident,
  observeRun,
  rejectRun,
  startIncident,
} from './api';
import { loadReplayEvents, playReplayEvents } from './replay';
import { ApprovalBar } from './components/ApprovalBar';
import { AlertDashboard } from './components/AlertDashboard';
import { AuditExportPanel } from './components/AuditExportPanel';
import { AuditTrail } from './components/AuditTrail';
import { ClosureBar } from './components/ClosureBar';
import { DecisionPanel } from './components/DecisionPanel';
import { EvidencePanel } from './components/EvidencePanel';
import { ItsmCommandCenterPanel } from './components/ItsmCommandCenterPanel';
import { ModeSwitch } from './components/ModeSwitch';
import { PolicyCheckPanel } from './components/PolicyCheckPanel';
import { RcaPanel } from './components/RcaPanel';
import { RunTimeline } from './components/RunTimeline';
import { ScenarioSelector } from './components/ScenarioSelector';
import { ScriptReviewPanel } from './components/ScriptReviewPanel';
import { ServiceNowHistoryPanel } from './components/ServiceNowHistoryPanel';
import { TicketPanel } from './components/TicketPanel';
import type {
  ItsmTwinState,
  Mode,
  PolicyCheck,
  RcaSummary,
  RemediationPlan,
  RunEvent,
  ScenarioSummary,
  ServiceNowIncidentHistoryEntry,
  ServiceNowIncidentRecord,
  TicketDetails,
} from './types';

type View = 'dashboard' | 'incident';

const defaultScenario: ScenarioSummary = {
  scenario_id: 'disk-space',
  team: 'Windows Infra',
  alert_type: 'Disk utilization high',
  incident_id: 'INC-2026-00421',
  priority: 'P4',
  title: 'C: drive utilization is above threshold',
  business_service: 'Internal Claims Portal',
  affected_ci: 'APP-WIN-042',
  current_state: 'C: drive is 96% used with 8 GB free.',
  requested_outcome: 'Reclaim space with SOP-approved cleanup.',
  mttr_minutes: 8,
  manual_steps_avoided: 6,
  audit_completeness: '100%',
  replay_outcome: 'success',
};

const localSnowUrl =
  import.meta.env.VITE_LOCAL_SNOW_URL ?? 'http://127.0.0.1:5177/apps/local-snow/';

function routeFromLocation(): { view: View; scenarioId: string } {
  if (typeof window === 'undefined') {
    return { view: 'dashboard', scenarioId: 'disk-space' };
  }
  const match = window.location.hash.match(/^#\/incident\/([^/?#]+)/);
  if (!match) {
    return { view: 'dashboard', scenarioId: 'disk-space' };
  }
  return { view: 'incident', scenarioId: decodeURIComponent(match[1]) };
}

function extractPlan(events: RunEvent[]): RemediationPlan | undefined {
  return events.find((event) => event.type === 'plan.generated')?.payload as
    | RemediationPlan
    | undefined;
}

function extractChecks(events: RunEvent[]): PolicyCheck[] {
  const policyEvent = [...events]
    .reverse()
    .find((event) => event.type === 'policy.checked' || event.type === 'approval.granted');
  const payload = policyEvent?.payload as { checks?: PolicyCheck[] } | undefined;
  return payload?.checks ?? [];
}

function extractRca(events: RunEvent[]): RcaSummary | undefined {
  return events.find((event) => event.type === 'rca.generated')?.payload as
    | RcaSummary
    | undefined;
}

function extractServiceNowIncident(events: RunEvent[]): ServiceNowIncidentRecord | undefined {
  for (const event of [...events].reverse()) {
    const payload = event.payload as { servicenow_incident?: ServiceNowIncidentRecord | null } | null;
    if (payload?.servicenow_incident) {
      return payload.servicenow_incident;
    }
  }
  return undefined;
}

function extractItsmTwin(events: RunEvent[]): ItsmTwinState | undefined {
  for (const event of [...events].reverse()) {
    const payload = event.payload as { itsm_twin?: ItsmTwinState | null } | null;
    if (payload?.itsm_twin) {
      return payload.itsm_twin;
    }
  }
  return undefined;
}

function latestEventIndex(events: RunEvent[], types: string[]): number {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (types.includes(events[index].type)) {
      return index;
    }
  }
  return -1;
}

function isWaitingForApproval(events: RunEvent[]): boolean {
  return (
    latestEventIndex(events, ['approval.requested']) >
    latestEventIndex(events, ['approval.granted', 'approval.rejected', 'policy.blocked'])
  );
}

function isWaitingForClosure(events: RunEvent[]): boolean {
  return (
    latestEventIndex(events, ['closure.requested']) >
    latestEventIndex(events, ['observation.started', 'incident.closed'])
  );
}

function isObserving(events: RunEvent[]): boolean {
  return latestEventIndex(events, ['observation.started']) > latestEventIndex(events, ['incident.closed']);
}

function runStatus(events: RunEvent[], mode: Mode): string {
  const last = events.at(-1);
  if (!last) {
    return mode === 'replay' ? 'Simulation idle' : 'Live idle';
  }
  if (latestEventIndex(events, ['incident.closed']) >= 0) return 'Closed';
  if (isObserving(events)) return 'Observing';
  if (isWaitingForClosure(events)) return 'Waiting closure';
  if (isWaitingForApproval(events)) return 'Waiting approval';
  if (last.type === 'rca.generated') return 'RCA ready';
  if (last.type === 'comms.sent') return 'Comms sent';
  if (last.type === 'comms.rejected') return 'Comms rejected';
  if (last.type.includes('blocked')) return 'Blocked';
  if (last.type.includes('rejected')) return 'Rejected';
  return 'Running';
}

function runIntimation(
  status: string,
  mode: Mode,
  simulationStarted: boolean,
  notice: string,
): string {
  if (!simulationStarted) {
    if (
      mode === 'live' &&
      notice &&
      !['Local Live Mode Ready', 'Local Live Mode', 'Starting Local Live Mode'].includes(
        notice,
      )
    ) {
      return notice;
    }
    return mode === 'live'
      ? 'Live mode is ready. Start Simulation will stream backend work one step at a time.'
      : 'Replay mode is ready. Start Simulation will reveal the investigation slowly.';
  }
  if (status === 'Waiting approval') {
    return 'Human approval required: remediation is paused until the plan and evidence are reviewed.';
  }
  if (status === 'Waiting closure') {
    return 'RCA is ready: choose Close INC or Observe before final closure.';
  }
  if (status === 'Observing') {
    return 'Observation is running: recovery metrics are being rechecked before closure.';
  }
  if (status === 'Closed') {
    return 'Incident closed with RCA, validation, and audit evidence attached.';
  }
  return mode === 'live'
    ? 'Live run in progress: the backend is retrieving evidence and emitting each control step.'
    : 'Replay in progress: synthetic events are appearing step by step for review.';
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function App() {
  const initialRoute = routeFromLocation();
  const [view, setView] = useState<View>(initialRoute.view);
  const [mode, setMode] = useState<Mode>('replay');
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([defaultScenario]);
  const [selectedScenarioId, setSelectedScenarioId] = useState(initialRoute.scenarioId);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [simulationStarted, setSimulationStarted] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [policyDemoChecks, setPolicyDemoChecks] = useState<PolicyCheck[]>([]);
  const [policyDemoLoading, setPolicyDemoLoading] = useState(false);
  const [policyDemoError, setPolicyDemoError] = useState<string | undefined>();
  const [runId, setRunId] = useState<string | null>(null);
  const [startServiceNowIncident, setStartServiceNowIncident] = useState<
    ServiceNowIncidentRecord | undefined
  >();
  const [manualItsmTwin, setManualItsmTwin] = useState<ItsmTwinState | undefined>();
  const [serviceNowHistory, setServiceNowHistory] = useState<
    ServiceNowIncidentHistoryEntry[]
  >([]);
  const [serviceNowLookupStatus, setServiceNowLookupStatus] = useState<
    Record<string, string>
  >({});
  const [notice, setNotice] = useState('Alert Dashboard');
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let mounted = true;

    async function refreshBackendHealth() {
      const online = await healthCheck();
      if (mounted) {
        setBackendOnline(online);
      }
    }

    refreshBackendHealth();
    const healthTimer = window.setInterval(refreshBackendHealth, 5000);
    fetchScenarios()
      .then((loaded) => {
        if (!mounted) return;
        setScenarios(loaded);
        setSelectedScenarioId((current) =>
          loaded.some((scenario) => scenario.scenario_id === current)
            ? current
            : (loaded[0]?.scenario_id ?? 'disk-space'),
        );
      })
      .catch(() => {
        if (mounted) {
          setNotice('Scenario catalog unavailable');
        }
      });

    return () => {
      mounted = false;
      window.clearInterval(healthTimer);
    };
  }, []);

  useEffect(() => {
    function syncRoute() {
      const route = routeFromLocation();
      socketRef.current?.close();
      setView(route.view);
      setSelectedScenarioId(route.scenarioId);
      setEvents([]);
      setPolicyDemoChecks([]);
      setPolicyDemoError(undefined);
      setRunId(null);
      setStartServiceNowIncident(undefined);
      setManualItsmTwin(undefined);
      setSimulationStarted(false);
      setMode('replay');
      setNotice(route.view === 'incident' ? 'Incident Workspace' : 'Alert Dashboard');
    }

    window.addEventListener('popstate', syncRoute);
    return () => window.removeEventListener('popstate', syncRoute);
  }, []);

  useEffect(() => {
    if (view !== 'incident' || mode !== 'replay' || !simulationStarted) {
      return undefined;
    }
    let stop: () => void = () => undefined;
    let cancelled = false;
    loadReplayEvents(selectedScenarioId)
      .then((loaded) => {
        if (cancelled) return;
        stop = playReplayEvents(loaded, (event) => {
          setEvents((current) => [...current, event]);
        });
      })
      .catch(() => setNotice('Replay data unavailable'));

    return () => {
      cancelled = true;
      stop();
    };
  }, [mode, selectedScenarioId, simulationStarted, view]);

  useEffect(() => {
    return () => socketRef.current?.close();
  }, []);

  useEffect(() => {
    if (!backendOnline) {
      return undefined;
    }
    let cancelled = false;
    async function refreshServiceNowHistory() {
      try {
        const incidents = await fetchServiceNowIncidents();
        if (!cancelled) {
          setServiceNowHistory(incidents);
        }
      } catch {
        if (!cancelled) {
          setServiceNowHistory([]);
        }
      }
    }

    refreshServiceNowHistory();
    const historyTimer = window.setInterval(refreshServiceNowHistory, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(historyTimer);
    };
  }, [backendOnline]);

  const selectedScenario = useMemo(
    () =>
      scenarios.find((scenario) => scenario.scenario_id === selectedScenarioId) ??
      defaultScenario,
    [scenarios, selectedScenarioId],
  );
  const ticket: TicketDetails = useMemo(
    () => ({
      scenario_id: selectedScenario.scenario_id,
      team: selectedScenario.team,
      alert_type: selectedScenario.alert_type,
      incident_id: selectedScenario.incident_id,
      priority: selectedScenario.priority,
      ci: selectedScenario.affected_ci,
      service: selectedScenario.business_service,
      current_state: selectedScenario.current_state,
      requested_outcome: selectedScenario.requested_outcome,
    }),
    [selectedScenario],
  );
  const plan = useMemo(() => extractPlan(events), [events]);
  const checks = useMemo(() => extractChecks(events), [events]);
  const rca = useMemo(() => extractRca(events), [events]);
  const latestServiceNowIncident = useMemo(() => extractServiceNowIncident(events), [events]);
  const eventItsmTwin = useMemo(() => extractItsmTwin(events), [events]);
  const serviceNowIncident = latestServiceNowIncident ?? startServiceNowIncident;
  const itsmTwin = eventItsmTwin ?? manualItsmTwin;
  const status = runStatus(events, mode);
  const waitingForApproval = isWaitingForApproval(events);
  const waitingForClosure = isWaitingForClosure(events);
  const observing = isObserving(events);
  const closed = events.some((event) => event.type === 'incident.closed');

  async function startLive() {
    setMode('live');
    setEvents([]);
    setPolicyDemoChecks([]);
    setPolicyDemoError(undefined);
    setStartServiceNowIncident(undefined);
    setManualItsmTwin(undefined);
    setSimulationStarted(true);
    setNotice('Starting Local Live Mode');
    try {
      const run = await startIncident(selectedScenarioId);
      setRunId(run.run_id);
      setStartServiceNowIncident(run.servicenow_incident ?? undefined);
      if (run.servicenow_incident?.number) {
        setServiceNowHistory((current) => [
          {
            run_id: run.run_id,
            recorded_at: new Date().toISOString(),
            status: 'created',
            number: run.servicenow_incident?.number ?? '',
            sys_id: run.servicenow_incident?.sys_id,
            url: run.servicenow_incident?.url,
            table: run.servicenow_incident?.table ?? 'incident',
            mode: run.servicenow_incident?.mode ?? 'live',
            created_at: run.servicenow_incident?.created_at,
            updated_at: run.servicenow_incident?.updated_at,
            last_update_status: run.servicenow_incident?.last_update_status,
            state: run.servicenow_incident?.state,
            error: run.servicenow_incident?.error,
            scenario_id: selectedScenario.scenario_id,
            synthetic_incident_id:
              run.servicenow_incident?.synthetic_incident_id ?? selectedScenario.incident_id,
            team: selectedScenario.team,
            alert_type: selectedScenario.title,
            business_service: selectedScenario.business_service,
            affected_ci: selectedScenario.affected_ci,
          },
          ...current.filter((incident) => incident.run_id !== run.run_id),
        ]);
      }
      socketRef.current?.close();
      socketRef.current = connectRunStream(
        run.run_id,
        (event) => setEvents((current) => [...current, event]),
        () => setNotice('Live stream closed'),
      );
      setNotice('Local Live Mode');
    } catch (error) {
      socketRef.current?.close();
      setEvents([]);
      setRunId(null);
      setStartServiceNowIncident(undefined);
      setManualItsmTwin(undefined);
      setSimulationStarted(false);
      setNotice(errorMessage(error, 'Unable to start local live mode.'));
    }
  }

  function startReplay() {
    socketRef.current?.close();
    setMode('replay');
    setEvents([]);
    setPolicyDemoChecks([]);
    setPolicyDemoError(undefined);
    setStartServiceNowIncident(undefined);
    setManualItsmTwin(undefined);
    setRunId(`replay-${selectedScenarioId}`);
    setSimulationStarted(true);
    setNotice('Replay Simulation');
  }

  async function startSimulation() {
    if (mode === 'live' && backendOnline) {
      await startLive();
      return;
    }
    if (mode === 'live' && !backendOnline) {
      setNotice('Backend offline, running replay simulation');
    }
    startReplay();
  }

  function activateReplay() {
    socketRef.current?.close();
    setEvents([]);
    setPolicyDemoChecks([]);
    setPolicyDemoError(undefined);
    setStartServiceNowIncident(undefined);
    setManualItsmTwin(undefined);
    setRunId(`replay-${selectedScenarioId}`);
    setSimulationStarted(false);
    setNotice('Replay Mode Ready');
    setMode('replay');
  }

  function selectScenario(scenarioId: string) {
    socketRef.current?.close();
    setSelectedScenarioId(scenarioId);
    setEvents([]);
    setPolicyDemoChecks([]);
    setPolicyDemoError(undefined);
    setStartServiceNowIncident(undefined);
    setManualItsmTwin(undefined);
    setRunId(null);
    setSimulationStarted(false);
    setNotice('Incident Workspace');
    setMode('replay');
    if (view === 'incident') {
      window.history.replaceState(null, '', `#/incident/${encodeURIComponent(scenarioId)}`);
    }
  }

  function openScenario(scenarioId: string) {
    selectScenario(scenarioId);
    setView('incident');
    window.history.pushState(null, '', `#/incident/${encodeURIComponent(scenarioId)}`);
  }

  function backToDashboard() {
    socketRef.current?.close();
    setView('dashboard');
    setEvents([]);
    setPolicyDemoChecks([]);
    setPolicyDemoError(undefined);
    setRunId(null);
    setStartServiceNowIncident(undefined);
    setManualItsmTwin(undefined);
    setSimulationStarted(false);
    setNotice('Alert Dashboard');
    window.history.pushState(null, '', window.location.pathname + window.location.search);
  }

  async function approve() {
    if (!runId) return;
    try {
      await approveRun(runId);
    } catch (error) {
      setNotice(errorMessage(error, 'Approval request failed.'));
    }
  }

  async function reject() {
    if (!runId) return;
    try {
      await rejectRun(runId);
    } catch (error) {
      setNotice(errorMessage(error, 'Rejection request failed.'));
    }
  }

  async function closeIncident() {
    if (!runId) return;
    try {
      await closeRun(runId);
    } catch (error) {
      setNotice(errorMessage(error, 'Closure request failed.'));
    }
  }

  async function observeIncident() {
    if (!runId) return;
    try {
      await observeRun(runId);
    } catch (error) {
      setNotice(errorMessage(error, 'Observation request failed.'));
    }
  }

  async function loadPolicyDemo() {
    setPolicyDemoLoading(true);
    setPolicyDemoError(undefined);
    try {
      setPolicyDemoChecks(await fetchPolicyDemoBlock());
    } catch (error) {
      setPolicyDemoError(error instanceof Error ? error.message : 'Policy demo unavailable.');
    } finally {
      setPolicyDemoLoading(false);
    }
  }

  async function verifyServiceNowIncident(incidentNumber: string) {
    setServiceNowLookupStatus((current) => ({
      ...current,
      [incidentNumber]: 'Checking PDI...',
    }));
    try {
      const result = await lookupServiceNowIncident(incidentNumber);
      const message = result.found
        ? `Verified in PDI: state ${result.incident?.state ?? 'unknown'}`
        : result.mode === 'not_configured'
          ? `PDI lookup not configured: ${(result.missing ?? []).join(', ')}`
          : 'Not found in PDI';
      setServiceNowLookupStatus((current) => ({
        ...current,
        [incidentNumber]: message,
      }));
    } catch (error) {
      setServiceNowLookupStatus((current) => ({
        ...current,
        [incidentNumber]: errorMessage(error, 'PDI lookup failed.'),
      }));
    }
  }

  return (
    <main className={`console-shell ${view === 'dashboard' ? 'dashboard-shell' : ''}`}>
      <header className="topbar">
        <div className="brand">
          <ShieldCheck size={22} aria-hidden="true" />
          <div>
            <strong>NEXUS-RESOLVE</strong>
            <span>Policy-Grounded AI Remediation</span>
          </div>
        </div>
        <div className="status-strip">
          <span>{notice}</span>
          <strong>{status}</strong>
          <small>{backendOnline ? 'Backend online' : 'Backend offline'}</small>
        </div>
        <a className="local-snow-link" href={localSnowUrl} target="_blank" rel="noreferrer">
          Local SNOW
        </a>
        {view === 'incident' ? (
          <>
            <ScenarioSelector
              scenarios={scenarios}
              selectedScenarioId={selectedScenarioId}
              onChange={selectScenario}
            />
            <ModeSwitch
              mode={mode}
              backendOnline={backendOnline}
              onModeChange={(nextMode) => {
                if (nextMode === 'replay') {
                  activateReplay();
                } else {
                  setMode('live');
                  setSimulationStarted(false);
                  setEvents([]);
                  setPolicyDemoChecks([]);
                  setPolicyDemoError(undefined);
                  setStartServiceNowIncident(undefined);
                  setManualItsmTwin(undefined);
                  setRunId(null);
                  setNotice(backendOnline ? 'Local Live Mode Ready' : 'Backend offline');
                }
              }}
              onStartLive={startSimulation}
            />
          </>
        ) : null}
      </header>

      {view === 'dashboard' ? (
        <>
          <AlertDashboard
            scenarios={scenarios}
            selectedScenarioId={selectedScenarioId}
            onOpenScenario={openScenario}
          />
        </>
      ) : (
        <>
          <div className="workspace-toolbar">
            <button className="ghost-button" type="button" onClick={backToDashboard}>
              <ArrowLeft size={16} aria-hidden="true" />
              Dashboard
            </button>
            <span>{ticket.incident_id}</span>
            <strong>{ticket.alert_type}</strong>
          </div>

          <div className="incident-command">
            <TicketPanel ticket={ticket} serviceNowIncident={serviceNowIncident} />
            <section className="simulation-panel" aria-label="Simulation controls">
              <div className="simulation-copy">
                <span className="eyebrow">{ticket.team} Alert</span>
                <h1>{ticket.alert_type}</h1>
                <p>{ticket.current_state}</p>
                <div className="simulation-meta">
                  <span>{ticket.incident_id}</span>
                  <span>{ticket.priority}</span>
                  <span>{ticket.ci}</span>
                </div>
              </div>
              <div className="simulation-actions">
                <button
                  className="start-simulation"
                  type="button"
                  onClick={startSimulation}
                  disabled={simulationStarted && !closed}
                >
                  <PlayCircle size={18} aria-hidden="true" />
                  {closed
                    ? 'Restart Simulation'
                    : simulationStarted
                      ? 'Simulation Running'
                      : 'Start Simulation'}
                </button>
                <span className="run-intimation">
                  {runIntimation(status, mode, simulationStarted, notice)}
                </span>
              </div>
            </section>
          </div>

          <div className="workbench-grid">
            <RunTimeline events={events} mode={mode} status={status} />
            <DecisionPanel events={events} plan={plan} />
          </div>

          <div className="operations-grid">
            <ScriptReviewPanel
              plan={plan}
              ticket={ticket}
              waitingForApproval={waitingForApproval}
            />
            <div className="decision-stack">
              <ApprovalBar
                mode={mode}
                waitingForApproval={waitingForApproval}
                onApprove={approve}
                onReject={reject}
              />
              <ItsmCommandCenterPanel
                backendOnline={backendOnline}
                runId={runId}
                itsmTwin={itsmTwin}
                ticketPriority={ticket.priority}
                onTwinChange={setManualItsmTwin}
              />
              <ClosureBar
                mode={mode}
                waitingForClosure={waitingForClosure}
                observing={observing}
                closed={closed}
                onCloseIncident={closeIncident}
                onObserveIncident={observeIncident}
              />
              <RcaPanel rca={rca} />
              <AuditExportPanel
                backendOnline={backendOnline}
                events={events}
                runId={runId}
                serviceNowIncident={serviceNowIncident}
              />
              {serviceNowHistory.length > 0 || Boolean(serviceNowIncident?.number) ? (
                <ServiceNowHistoryPanel
                  backendOnline={backendOnline}
                  incidents={serviceNowHistory}
                  lookupStatus={serviceNowLookupStatus}
                  onVerifyIncident={verifyServiceNowIncident}
                />
              ) : null}
            </div>
          </div>

          <div className="assurance-bottom-grid">
            <EvidencePanel events={events} />
            <PolicyCheckPanel
              backendOnline={backendOnline}
              checks={checks}
              demoChecks={policyDemoChecks}
              demoError={policyDemoError}
              demoLoading={policyDemoLoading}
              simulationStarted={simulationStarted}
              onLoadDemo={loadPolicyDemo}
            />
            <AuditTrail events={events} />
          </div>
        </>
      )}
    </main>
  );
}

export default App;
