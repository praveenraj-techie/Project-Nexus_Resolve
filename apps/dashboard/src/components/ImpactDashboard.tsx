import { BadgeDollarSign, Clock3, Gauge, LineChart, TimerReset, WalletCards } from 'lucide-react';
import { formatMinutes, formatMoney } from '../telemetry';
import type { AiTelemetrySummary, Mode, ScenarioSummary } from '../types';

type Props = {
  mode?: Mode;
  scenarios: ScenarioSummary[];
  telemetry?: AiTelemetrySummary;
  telemetryActive?: boolean;
};

const HUMAN_RATE_USD = 30;
const HUMAN_BASELINE_MINUTES = 45;

export function ImpactDashboard({
  mode = 'replay',
  scenarios,
  telemetry,
  telemetryActive = false,
}: Props) {
  const baselineMinutes = scenarios.length * HUMAN_BASELINE_MINUTES;
  const nexusMinutes = scenarios.reduce(
    (total, scenario) => total + (scenario.mttr_minutes ?? 0),
    0,
  );
  const savedMinutes = Math.max(baselineMinutes - nexusMinutes, 0);
  const humanCost = (baselineMinutes / 60) * HUMAN_RATE_USD;
  const nexusLaborCost = (nexusMinutes / 60) * HUMAN_RATE_USD;
  const laborSavings = Math.max(humanCost - nexusLaborCost, 0);
  const manualSteps = scenarios.reduce(
    (total, scenario) => total + (scenario.manual_steps_avoided ?? 0),
    0,
  );
  const rejectedPaths = scenarios.filter((scenario) => scenario.replay_outcome === 'rejected').length;
  const replayTelemetry = telemetryActive && mode === 'replay' && !telemetry;

  const baselineCards = [
    {
      icon: Clock3,
      label: 'Portfolio Time Saved',
      value: formatMinutes(savedMinutes),
      detail: `${formatMinutes(baselineMinutes)} human baseline vs ${formatMinutes(nexusMinutes)} NEXUS MTTR`,
    },
    {
      icon: BadgeDollarSign,
      label: 'Human Cost Avoided',
      value: formatMoney(laborSavings, 2),
      detail: `${formatMoney(humanCost, 2)} human cost at $${HUMAN_RATE_USD}/hr`,
    },
    {
      icon: TimerReset,
      label: 'Manual Steps Avoided',
      value: String(manualSteps),
      detail: `${scenarios.length} incidents, ${rejectedPaths} rejection proof path`,
    },
    {
      icon: Gauge,
      label: 'Scenario Coverage',
      value: String(scenarios.length),
      detail: 'Windows, Linux, database, IAM, network, firewall, backup, service desk, AD, command centre, endpoint, and cloud',
    },
    {
      icon: LineChart,
      label: 'Failure Paths',
      value: String(rejectedPaths),
      detail: 'Dedicated rejection proof for endpoint security exception handling',
    },
    {
      icon: WalletCards,
      label: 'Audit Readiness',
      value: 'Ready',
      detail: 'Start simulation to attach run-specific JSON/PDF evidence and AI telemetry',
    },
  ];

  const telemetryCards = [
    ...baselineCards.slice(0, 3),
    {
      icon: Gauge,
      label: 'OpenAI Tokens',
      value: telemetry ? String(telemetry.total_tokens) : replayTelemetry ? 'Replay' : 'Pending',
      detail: telemetry
        ? `${telemetry.openai_calls} OpenAI calls, ${telemetry.fallback_calls} fallback calls`
        : replayTelemetry
          ? 'No OpenAI calls are made in replay mode'
        : 'Waiting for generated AI payload',
    },
    {
      icon: LineChart,
      label: 'OpenAI Latency',
      value: telemetry ? `${telemetry.total_latency_ms} ms` : replayTelemetry ? 'Replay' : 'Pending',
      detail: telemetry
        ? `${telemetry.calls} structured AI stages measured`
        : replayTelemetry
          ? 'Replay uses recorded synthetic events'
          : 'Start a live run to populate telemetry',
    },
    {
      icon: WalletCards,
      label: 'API Cost Vs Labor',
      value: telemetry ? formatMoney(telemetry.estimated_openai_cost_usd) : replayTelemetry ? '$0.0000' : 'Pending',
      detail:
        telemetry?.estimated_net_savings_usd !== null &&
        telemetry?.estimated_net_savings_usd !== undefined
          ? `${formatMoney(telemetry.estimated_net_savings_usd, 4)} estimated net savings`
          : replayTelemetry
            ? 'Replay mode has no API cost'
          : 'Set OpenAI cost env values for exact API estimate',
    },
  ];
  const cards = telemetryActive ? telemetryCards : baselineCards;

  return (
    <section className="impact-dashboard" data-state={telemetryActive ? 'active' : 'baseline'} aria-label="Dedicated impact dashboard">
      <div className="impact-heading">
        <div>
          <span className="eyebrow">{telemetryActive ? 'Executive Impact Dashboard' : 'Executive Impact Baseline'}</span>
          <h2>{telemetryActive ? 'Cost, MTTR, Audit, And AI Telemetry' : 'Portfolio Baseline Before Simulation'}</h2>
        </div>
        <strong>{telemetryActive ? `${scenarios.length} governed incidents` : 'Pre-run baseline'}</strong>
      </div>
      <div className="impact-grid">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article key={card.label}>
              <Icon size={18} aria-hidden="true" />
              <div>
                <strong>{card.value}</strong>
                <span>{card.label}</span>
                <p>{card.detail}</p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
