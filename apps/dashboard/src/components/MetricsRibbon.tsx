import { Gauge } from 'lucide-react';
import type { Mode, RcaSummary, RunEvent } from '../types';

type Props = {
  events: RunEvent[];
  mode: Mode;
  rca?: RcaSummary;
};

export function MetricsRibbon({ events, mode, rca }: Props) {
  const execution = events.find((event) => event.type === 'execution.mocked');
  const payload = execution?.payload as
    | { metrics?: Array<{ label: string; value: string }> }
    | undefined;
  const executionMetrics = payload?.metrics ?? [];
  const rcaMetrics = rca?.metrics
    ? Object.entries(rca.metrics).map(([label, value]) => ({
        label,
        value: String(value),
      }))
    : [];

  const items = [...executionMetrics, ...rcaMetrics].slice(0, 5);
  const visibleItems =
    items.length > 0
      ? items
      : [
          { label: 'Events', value: String(events.length) },
          { label: 'Mode', value: mode === 'live' ? 'Live' : 'Replay' },
          { label: 'Approval', value: 'Pending' },
          { label: 'Guard', value: 'Mock' },
          { label: 'Audit', value: 'Ready' },
        ];

  return (
    <section className="metrics-ribbon" aria-label="Scenario metrics">
      <div className="metric-label">
        <Gauge size={17} aria-hidden="true" />
        Metrics
      </div>
      {visibleItems.map((item) => (
        <article key={item.label}>
          <strong>{item.value}</strong>
          <span>{item.label}</span>
        </article>
      ))}
    </section>
  );
}
