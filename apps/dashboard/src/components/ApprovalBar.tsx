import { Check, X } from 'lucide-react';
import type { Mode } from '../types';

type Props = {
  mode: Mode;
  waitingForApproval: boolean;
  onApprove: () => void;
  onReject: () => void;
};

export function ApprovalBar({
  mode,
  waitingForApproval,
  onApprove,
  onReject,
}: Props) {
  const disabled = mode === 'replay' || !waitingForApproval;
  return (
    <section className="approval-bar" aria-label="Approval controls">
      <div>
        <strong>Human Approval Gate</strong>
        <span>
          {mode === 'replay'
            ? 'Replay Mode: side effects disabled'
            : waitingForApproval
              ? 'Review SOP, history, evidence summary, plan, and policy hold before remediation'
              : 'Waiting for approval stage'}
        </span>
      </div>
      <div className="approval-actions">
        <button type="button" onClick={onReject} disabled={disabled}>
          <X size={16} aria-hidden="true" />
          Reject
        </button>
        <button type="button" onClick={onApprove} disabled={disabled}>
          <Check size={16} aria-hidden="true" />
          Approve
        </button>
      </div>
    </section>
  );
}
