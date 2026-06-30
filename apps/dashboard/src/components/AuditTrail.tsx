import { ListChecks } from 'lucide-react';
import type { RunEvent } from '../types';

type Props = {
  events: RunEvent[];
};

function tokenTone(token: string): string {
  if (['blocked', 'rejected', 'warning', 'error'].some((word) => token.includes(word))) {
    return 'danger';
  }
  if (['approval', 'requested', 'hold', 'policy', 'checked'].some((word) => token.includes(word))) {
    return 'hold';
  }
  if (
    ['closed', 'completed', 'passed', 'executed', 'generated', 'granted', 'rca', 'validation'].some(
      (word) => token.includes(word),
    )
  ) {
    return 'success';
  }
  if (['evidence', 'sop', 'history', 'summary', 'plan'].some((word) => token.includes(word))) {
    return 'evidence';
  }
  if (['ticket', 'incident', 'received'].some((word) => token.includes(word))) {
    return 'intake';
  }
  return 'neutral';
}

export function AuditTrail({ events }: Props) {
  return (
    <section className="panel audit-panel" aria-labelledby="audit-title">
      <div className="panel-heading">
        <ListChecks size={18} aria-hidden="true" />
        <h2 id="audit-title">Audit Trail</h2>
      </div>
      <ol>
        {events.map((event) => (
          <li key={`${event.run_id}-${event.sequence}`}>
            <span className="audit-sequence">{event.sequence.toString().padStart(2, '0')}</span>
            <div className="audit-event-copy">
              <div className="audit-token-row" aria-label={event.type}>
                {event.type.split('.').map((token) => (
                  <strong className="audit-token" data-tone={tokenTone(token)} key={token}>
                    {token}
                  </strong>
                ))}
              </div>
              <p>
                <b>{event.title}</b>
                {event.message ? ` - ${event.message}` : ''}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
