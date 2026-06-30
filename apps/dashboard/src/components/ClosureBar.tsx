import { Eye, LockKeyhole, TimerReset } from 'lucide-react';
import type { Mode } from '../types';

type Props = {
  mode: Mode;
  waitingForClosure: boolean;
  observing: boolean;
  closed: boolean;
  onCloseIncident: () => void;
  onObserveIncident: () => void;
};

export function ClosureBar({
  mode,
  waitingForClosure,
  observing,
  closed,
  onCloseIncident,
  onObserveIncident,
}: Props) {
  const disabled = mode === 'replay' || !waitingForClosure;
  return (
    <section className="closure-bar" aria-label="Closure controls">
      <div>
        <strong>Incident Closure Decision</strong>
        <span>
          {mode === 'replay'
            ? 'Replay Mode: closure outcome is shown in the timeline; live closure controls are disabled'
            : closed
            ? 'Incident closed with RCA and audit evidence'
            : observing
              ? 'Observation window running, metrics will be rechecked'
              : waitingForClosure
                ? 'RCA ready: approve closure or observe first'
                : 'Closure controls unlock after RCA'}
        </span>
      </div>
      <div className="closure-actions">
        <button type="button" onClick={onObserveIncident} disabled={disabled}>
          <TimerReset size={16} aria-hidden="true" />
          Observe
        </button>
        <button type="button" onClick={onCloseIncident} disabled={disabled}>
          <LockKeyhole size={16} aria-hidden="true" />
          Close INC
        </button>
        <span className="closure-chip">
          <Eye size={14} aria-hidden="true" />
          Auto recheck
        </span>
      </div>
    </section>
  );
}
