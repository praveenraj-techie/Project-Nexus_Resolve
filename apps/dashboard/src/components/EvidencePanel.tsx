import { BookOpenText, History } from 'lucide-react';
import type { RunEvent } from '../types';

type Props = {
  events: RunEvent[];
};

export function EvidencePanel({ events }: Props) {
  const sop = events.find((event) => event.type === 'evidence.sop');
  const history = events.find((event) => event.type === 'evidence.history');
  const warning = events.find((event) => event.type === 'policy.warning');
  const evidenceReady = events.some((event) => event.type === 'evidence.summary');
  const sopPayload = sop?.payload as { id?: string; sop_id?: string; title?: string } | undefined;

  return (
    <section className="panel evidence-panel" aria-labelledby="evidence-title">
      <div className="panel-heading">
        <BookOpenText size={18} aria-hidden="true" />
        <h2 id="evidence-title">SOP And History</h2>
      </div>
      {evidenceReady ? (
        <div className="evidence-ready-stack">
          <div className="evidence-card sop-card">
            <BookOpenText size={16} aria-hidden="true" />
            <div>
              <strong>{sopPayload?.sop_id ?? sopPayload?.id ?? 'Scenario SOP'}</strong>
              <p>{sop?.message}</p>
            </div>
          </div>
          <div className="evidence-card">
            <History size={16} aria-hidden="true" />
            <div>
              <strong>Similar Tickets</strong>
              <p>{history?.message}</p>
            </div>
          </div>
          <div className="blocked-card">
            <strong>SOP beats history</strong>
            <p>{warning?.message}</p>
          </div>
        </div>
      ) : (
        <div className="evidence-blank" aria-hidden="true" />
      )}
    </section>
  );
}
