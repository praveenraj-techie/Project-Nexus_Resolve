import { BrainCircuit, FileCheck2, GitBranch, ShieldCheck } from 'lucide-react';
import type {
  AiGeneratedPayload,
  ApprovalSummary,
  RcaSummary,
  RemediationPlan,
  RunEvent,
} from '../types';

type Props = {
  events: RunEvent[];
  plan?: RemediationPlan;
};

type SopPayload = {
  id?: string;
  sop_id?: string;
  metadata?: { controls?: string[] };
};

type HistoryPayload = {
  safe_examples?: number;
  unsafe_examples?: number;
  escalations?: number;
  unsafe_ticket?: string;
};

type EvidenceSummaryPayload = {
  outcome?: string;
  governance_note?: string;
  unsafe_precedent_ids?: string[];
  escalation_precedent_ids?: string[];
  sop_controls?: string[];
} & AiGeneratedPayload;

type ApprovalSummaryPayload = ApprovalSummary & AiGeneratedPayload;

type RcaSummaryPayload = RcaSummary & AiGeneratedPayload;

type DecisionCardState = 'pending' | 'ready' | 'openai' | 'fallback' | 'replay';

function sourceLabel(payload?: AiGeneratedPayload): string {
  if (!payload) {
    return 'Pending live evidence';
  }
  if (!payload.ai_source) {
    return 'Replay / static evidence';
  }
  if (payload.ai_source === 'openai') {
    return `${payload.generated_by ?? 'OpenAI Responses API'}${
      payload.model ? ` (${payload.model})` : ''
    }`;
  }
  return `${payload.generated_by ?? 'Deterministic fallback'}${
    payload.model ? ` (${payload.model})` : ''
  }`;
}

function sourceState(payload?: AiGeneratedPayload): DecisionCardState {
  if (!payload) return 'pending';
  return payload.ai_source ?? 'replay';
}

export function DecisionPanel({ events, plan }: Props) {
  const sop = events.find((event) => event.type === 'evidence.sop');
  const history = events.find((event) => event.type === 'evidence.history');
  const warning = events.find((event) => event.type === 'policy.warning');
  const evidence = events.find((event) => event.type === 'evidence.summary');
  const approval = events.find((event) => event.type === 'approval.summary');
  const rca = events.find((event) => event.type === 'rca.generated');

  const sopPayload = sop?.payload as SopPayload | undefined;
  const sopId = sopPayload?.id ?? sopPayload?.sop_id ?? 'SOP pending';
  const historyPayload = history?.payload as HistoryPayload | undefined;
  const evidencePayload = evidence?.payload as EvidenceSummaryPayload | undefined;
  const approvalPayload = approval?.payload as ApprovalSummaryPayload | undefined;
  const rcaPayload = rca?.payload as RcaSummaryPayload | undefined;
  const sourceText = sourceLabel(evidencePayload ?? approvalPayload ?? rcaPayload);
  const reasonState = sourceState(evidencePayload);
  const sourceChipState = sourceState(evidencePayload ?? approvalPayload ?? rcaPayload);
  const governanceState: DecisionCardState = sop ? 'ready' : 'pending';
  const historyState: DecisionCardState = history ? 'ready' : 'pending';
  const approvalState = approvalPayload
    ? sourceState(approvalPayload)
    : evidencePayload || historyPayload
      ? 'ready'
      : 'pending';
  const actionState = plan ? sourceState(plan) : 'pending';
  const rcaState = sourceState(rcaPayload);
  const historySummary = history
    ? `${historyPayload?.safe_examples ?? 0} safe precedents, ${historyPayload?.unsafe_examples ?? 0} unsafe precedent, ${historyPayload?.escalations ?? 0} escalation.`
    : 'Historical ticket comparison will appear after simulation starts.';
  const blockedRisk = historyPayload?.unsafe_ticket
    ? `Blocked ${historyPayload.unsafe_ticket}; SOP controls override unsafe history.`
    : (warning?.message ?? 'Unsafe precedent filtering is pending.');

  return (
    <section className="panel decision-panel" aria-labelledby="decision-title">
      <div className="panel-heading">
        <BrainCircuit size={18} aria-hidden="true" />
        <h2 id="decision-title">Decision Evidence</h2>
      </div>
      <div className="decision-summary-strip">
        <article className="decision-summary-card" data-state={reasonState}>
          <BrainCircuit size={17} aria-hidden="true" />
          <div>
            <strong>Reason Summary</strong>
            <span className="ai-source-chip" data-state={sourceChipState}>
              {sourceText}
            </span>
            <p>
              {evidencePayload?.outcome ??
                'The run will summarize why this remediation path is safe.'}
            </p>
          </div>
        </article>
        <article data-state={governanceState}>
          <ShieldCheck size={17} aria-hidden="true" />
          <div>
            <strong>Governance Source</strong>
            <p>
              {sopId}: {sop?.message ?? 'Waiting for SOP retrieval.'}
            </p>
          </div>
        </article>
        <article data-state={historyState}>
          <GitBranch size={17} aria-hidden="true" />
          <div>
            <strong>History Signal</strong>
            <p>{historySummary}</p>
          </div>
        </article>
        <article data-state={approvalState}>
          <FileCheck2 size={17} aria-hidden="true" />
          <div>
            <strong>Approval Decision</strong>
            <p>
              {approvalPayload?.operator_message ??
                evidencePayload?.governance_note ??
                blockedRisk}
            </p>
          </div>
        </article>
        <article data-state={actionState}>
          <FileCheck2 size={17} aria-hidden="true" />
          <div>
            <strong>Selected Action And Expected Effect</strong>
            <p>
              {plan
                ? `${plan.summary} ${approvalPayload?.expected_safe_effect ?? plan.estimated_effect}`
                : 'Safe remediation plan pending.'}
            </p>
          </div>
        </article>
        <article data-state={rcaState}>
          <FileCheck2 size={17} aria-hidden="true" />
          <div>
            <strong>RCA Outcome</strong>
            <p>
              {rcaPayload
                ? `${rcaPayload.root_cause} ${rcaPayload.validation}`
                : 'RCA will be generated by the backend after validation.'}
            </p>
          </div>
        </article>
      </div>
    </section>
  );
}
