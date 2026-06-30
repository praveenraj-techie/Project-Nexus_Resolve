import { FileCode2 } from 'lucide-react';
import type { RemediationPlan, TicketDetails } from '../types';

type Props = {
  plan?: RemediationPlan;
  ticket: TicketDetails;
  waitingForApproval: boolean;
};

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function sourceState(plan?: RemediationPlan): 'pending' | 'openai' | 'fallback' | 'replay' {
  if (!plan) return 'pending';
  return plan.ai_source ?? 'replay';
}

function approvalScript(plan: RemediationPlan | undefined, ticket: TicketDetails, jobName: string): string {
  if (!plan) {
    return `# Human approval review\njob_name="${jobName}"\nincident="${ticket.incident_id}"\ntarget="${ticket.ci}"\nstatus="waiting_for_backend_plan"\ncommand_preview="pending"`;
  }

  const validations = plan.validation_steps
    .map((step, index) => `validation_${index + 1}="${step}"`)
    .join('\n');

  return [
    '# Human approval review - mock execution only',
    `job_name="${jobName}"`,
    `incident="${ticket.incident_id}"`,
    `target="${plan.target_resources.join(', ')}"`,
    `mock_only=${String(plan.mock_only)}`,
    `dry_run=${String(plan.uses_dry_run)}`,
    `approval_required=${String(plan.approval_required)}`,
    `command_preview="${plan.action_preview}"`,
    `expected_effect="${plan.estimated_effect}"`,
    validations,
  ]
    .filter(Boolean)
    .join('\n');
}

export function ScriptReviewPanel({ plan, ticket, waitingForApproval }: Props) {
  const source =
    plan?.ai_source === 'openai'
      ? `${plan.generated_by ?? 'OpenAI Responses API'}${
          plan.model ? ` (${plan.model})` : ''
        }`
      : plan?.ai_source === 'fallback'
        ? `${plan.generated_by ?? 'Deterministic fallback'}${
            plan.model ? ` (${plan.model})` : ''
          }`
        : 'Replay / static plan';
  const state = sourceState(plan);
  const jobName = `NXR-${ticket.incident_id}-${slug(ticket.scenario_id)}`;
  const commandPreview = approvalScript(plan, ticket, jobName);
  const reviewState = waitingForApproval
    ? 'Human approval required'
    : plan
      ? 'Generated plan ready'
      : 'Waiting for generated plan';
  const approvalChecks = plan
    ? [...(plan.safeguards ?? []), ...(plan.validation_steps ?? [])]
    : [
        'Confirm the generated action is mock-only.',
        'Confirm target resource matches the incident CI.',
        'Confirm validation evidence will be produced after execution.',
      ];

  return (
    <section className="panel script-panel" aria-labelledby="script-title">
      <div className="panel-heading">
        <FileCode2 size={18} aria-hidden="true" />
        <h2 id="script-title">Action Review</h2>
      </div>
      <div className="script-review-status">
        <span className="ai-source-chip" data-state={state}>
          {source}
        </span>
        <span className="approval-state-chip">{reviewState}</span>
      </div>
      <div className="job-review-card">
        <span>Job Name</span>
        <strong>{jobName}</strong>
        <p>{plan?.summary ?? `Backend will generate a governed action for ${ticket.alert_type}.`}</p>
      </div>
      <div className="code-review-block">
        <span>Command / Dry-Run Code For Human Review</span>
        <pre>
          <code>{commandPreview}</code>
        </pre>
      </div>
      <div className="script-meta">
        <span>{plan?.target_resources?.join(', ') ?? ticket.ci}</span>
        <span>{plan?.estimated_effect ?? 'Effect pending'}</span>
        <span>{plan?.mock_only ? 'Mock only' : 'Pending mock guard'}</span>
        <span>{plan?.uses_dry_run ? 'Dry-run enforced' : 'Dry-run pending'}</span>
      </div>
      <div className="approval-checklist" aria-label="Human approval checklist">
        {approvalChecks.slice(0, 6).map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
    </section>
  );
}
