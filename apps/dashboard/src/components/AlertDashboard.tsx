import {
  Activity,
  AlertTriangle,
  Cloud,
  Database,
  Flame,
  Gauge,
  HardDrive,
  Network,
  Server,
  Shield,
  Users,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import type { ScenarioSummary } from '../types';

type Props = {
  scenarios: ScenarioSummary[];
  selectedScenarioId: string;
  onOpenScenario: (scenarioId: string) => void;
};

const iconByTeam: Record<string, typeof Server> = {
  'Windows Infra': HardDrive,
  Database,
  'Security / IAM': Shield,
  Network,
  Linux: Server,
  Firewall: Flame,
  Backup: Activity,
  'Service Desk': Users,
  AD: Shield,
  'Command Centre': Gauge,
  Cloud,
  'Endpoint Security': Shield,
};

type SortMode = 'priority' | 'team';

const priorityRank: Record<string, number> = {
  P1: 1,
  P2: 2,
  P3: 3,
  P4: 4,
  P5: 5,
};

function urgency(priority: string): string {
  if (priority === 'P1') return 'Major';
  if (priority === 'P2') return 'Critical';
  if (priority === 'P3') return 'High';
  return 'Moderate';
}

export function AlertDashboard({
  scenarios,
  selectedScenarioId,
  onOpenScenario,
}: Props) {
  const [sortMode, setSortMode] = useState<SortMode>('priority');
  const critical = scenarios.filter((scenario) => scenario.priority === 'P2').length;
  const high = scenarios.filter((scenario) => scenario.priority === 'P3').length;
  const teams = new Set(scenarios.map((scenario) => scenario.team)).size;
  const sortedScenarios = useMemo(
    () =>
      [...scenarios].sort((a, b) => {
        const priorityDelta =
          (priorityRank[a.priority] ?? 99) - (priorityRank[b.priority] ?? 99);
        const teamDelta = a.team.localeCompare(b.team);
        if (sortMode === 'team') {
          return teamDelta || priorityDelta || a.alert_type.localeCompare(b.alert_type);
        }
        return priorityDelta || teamDelta || a.alert_type.localeCompare(b.alert_type);
      }),
    [scenarios, sortMode],
  );

  return (
    <section className="dashboard-view" aria-label="Alert dashboard">
      <div className="dashboard-hero">
        <div>
          <span className="eyebrow">HCL Managed Infrastructure Command View</span>
          <h1>Active Operations Alerts</h1>
          <p>
            Prioritized incident queue sorted for fast triage by severity and owning team.
            Open a row to review evidence, approval, remediation, and closure.
          </p>
        </div>
        <div className="hero-metrics" aria-label="Alert summary">
          <article>
            <strong>{scenarios.length}</strong>
            <span>Open alerts</span>
          </article>
          <article>
            <strong>{critical}</strong>
            <span>Critical</span>
          </article>
          <article>
            <strong>{high}</strong>
            <span>High</span>
          </article>
          <article>
            <strong>{teams}</strong>
            <span>Teams</span>
          </article>
        </div>
      </div>

      <section className="triage-queue" aria-label="Priority and team sorted alert list">
        <div className="triage-toolbar">
          <div>
            <span className="eyebrow">Triage Queue</span>
            <h2>Priority And Team Sorted Incidents</h2>
          </div>
          <label>
            <span>Sort</span>
            <select
              aria-label="Sort alerts"
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
            >
              <option value="priority">Priority first, then team</option>
              <option value="team">Team first, then priority</option>
            </select>
          </label>
        </div>

        <div className="alert-board">
          {sortedScenarios.map((scenario) => {
            const Icon = iconByTeam[scenario.team] ?? AlertTriangle;
            const active = scenario.scenario_id === selectedScenarioId;
            return (
              <button
                className="alert-card"
                data-active={active}
                key={scenario.scenario_id}
                type="button"
                onClick={() => onOpenScenario(scenario.scenario_id)}
              >
                <span className="team-icon">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <span className="alert-priority">
                  <span className={`severity severity-${scenario.priority.toLowerCase()}`}>
                    {scenario.priority}
                  </span>
                  <small>{urgency(scenario.priority)}</small>
                </span>
                <div className="alert-card-main">
                  <span>{scenario.team}</span>
                  <strong>{scenario.alert_type}</strong>
                  <p>{scenario.current_state}</p>
                </div>
                <div className="alert-card-bottom">
                  <span>{scenario.incident_id}</span>
                  <span>{scenario.business_service}</span>
                </div>
              </button>
            );
          })}
        </div>
      </section>
    </section>
  );
}
