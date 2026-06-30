import { CheckCircle2, Mail, PhoneCall, Radio, Send, Users, XCircle } from 'lucide-react';
import { useState } from 'react';
import { approveCommsDraft, rejectCommsDraft } from '../api';
import type { CommsDraft, ItsmRecord, ItsmTwinState } from '../types';

type Props = {
  backendOnline: boolean;
  runId: string | null;
  itsmTwin?: ItsmTwinState | null;
  ticketPriority: string;
  onTwinChange: (nextTwin: ItsmTwinState) => void;
};

const recordLabels: Record<ItsmRecord['record_type'], string> = {
  incident: 'Incident',
  ritm: 'RITM',
  change: 'Change',
  problem: 'Problem',
};

const channelLabels: Record<CommsDraft['channel'], string> = {
  teams_bridge: 'Teams Bridge',
  isinfo_email: 'ISINFO Email',
  ivr: 'IVR',
  stakeholder_update: 'Stakeholder Update',
  closure_update: 'Closure Update',
};

function ChannelIcon({ channel }: { channel: CommsDraft['channel'] }) {
  if (channel === 'teams_bridge') return <Users size={16} aria-hidden="true" />;
  if (channel === 'ivr') return <PhoneCall size={16} aria-hidden="true" />;
  if (channel === 'isinfo_email') return <Mail size={16} aria-hidden="true" />;
  return <Radio size={16} aria-hidden="true" />;
}

function isMajorIncidentChannel(channel: CommsDraft['channel']): boolean {
  return channel === 'teams_bridge' || channel === 'isinfo_email' || channel === 'ivr';
}

function majorCommsAllowed(priority: string): boolean {
  return priority === 'P1' || priority === 'P2';
}

export function ItsmCommandCenterPanel({
  backendOnline,
  runId,
  itsmTwin,
  ticketPriority,
  onTwinChange,
}: Props) {
  const [actionStatus, setActionStatus] = useState('Manual approval queue idle');
  const [busyDraftId, setBusyDraftId] = useState<string | null>(null);
  const records = itsmTwin?.records ?? [];
  const comms = itsmTwin?.comms ?? [];
  const majorCommsEnabled = majorCommsAllowed(ticketPriority);
  const isActionableDraft = (draft: CommsDraft) =>
    draft.status === 'pending_approval' &&
    (!isMajorIncidentChannel(draft.channel) || majorCommsEnabled);
  const pendingCount = comms.filter(isActionableDraft).length;
  const lockedMajorCount = comms.filter(
    (draft) =>
      draft.status === 'pending_approval' &&
      isMajorIncidentChannel(draft.channel) &&
      !majorCommsEnabled,
  ).length;
  const sentCount = comms.filter((draft) => draft.status === 'sent').length;
  const canAct = Boolean(backendOnline && runId && !runId.startsWith('replay-'));

  async function approveDraft(draft: CommsDraft) {
    if (!runId) return;
    setBusyDraftId(draft.id);
    setActionStatus(`Approving ${channelLabels[draft.channel]} in simulator`);
    try {
      const nextTwin = await approveCommsDraft(runId, draft.id);
      onTwinChange(nextTwin);
      setActionStatus(`${channelLabels[draft.channel]} sent in simulator`);
    } catch (error) {
      setActionStatus(error instanceof Error ? error.message : 'Communication approval failed.');
    } finally {
      setBusyDraftId(null);
    }
  }

  async function rejectDraft(draft: CommsDraft) {
    if (!runId) return;
    setBusyDraftId(draft.id);
    setActionStatus(`Rejecting ${channelLabels[draft.channel]} draft`);
    try {
      const nextTwin = await rejectCommsDraft(runId, draft.id);
      onTwinChange(nextTwin);
      setActionStatus(`${channelLabels[draft.channel]} rejected by manual review`);
    } catch (error) {
      setActionStatus(error instanceof Error ? error.message : 'Communication rejection failed.');
    } finally {
      setBusyDraftId(null);
    }
  }

  return (
    <section className="panel itsm-command-panel" aria-label="ITSM command center">
      <div className="panel-heading">
        <Radio size={18} aria-hidden="true" />
        <h2>ITSM Twin Command Center</h2>
      </div>

      <div className="itsm-command-summary">
        <article>
          <strong>{records.length}</strong>
          <span>Incident/RITM/Change/Problem records</span>
        </article>
        <article>
          <strong>{pendingCount}</strong>
          <span>Actionable comms approvals</span>
        </article>
        <article>
          <strong>{majorCommsEnabled ? sentCount : lockedMajorCount}</strong>
          <span>{majorCommsEnabled ? 'Simulator sends approved' : 'P1/P2 comms locked'}</span>
        </article>
      </div>

      {itsmTwin ? (
        <>
          <div className="itsm-record-strip" aria-label="Local ITSM records">
            {records.map((record) => (
              <article key={record.id} data-type={record.record_type}>
                <span>{recordLabels[record.record_type]}</span>
                <strong>{record.number}</strong>
                <small>{record.state}</small>
              </article>
            ))}
          </div>

          <ol className="comms-draft-list" aria-label="Approval-gated communications">
            {comms.map((draft) => (
              <li
                key={draft.id}
                data-locked={
                  isMajorIncidentChannel(draft.channel) && !majorCommsEnabled
                    ? 'true'
                    : 'false'
                }
                data-status={draft.status}
              >
                <div className="comms-draft-copy">
                  <ChannelIcon channel={draft.channel} />
                  <div>
                    <strong>{draft.title}</strong>
                    <span>
                      {channelLabels[draft.channel]} - {draft.status.replace('_', ' ')}
                    </span>
                    <p>{draft.subject}</p>
                    <small>
                      {draft.participants.length || draft.recipients.length} targets -{' '}
                      {draft.cadence ?? 'approval gated'}
                    </small>
                  </div>
                </div>
                <div className="comms-draft-actions">
                  {draft.status === 'pending_approval' &&
                  isMajorIncidentChannel(draft.channel) &&
                  !majorCommsEnabled ? (
                    <span className="comms-state restricted">
                      <XCircle size={14} aria-hidden="true" />
                      P1/P2 only
                    </span>
                  ) : draft.status === 'sent' ? (
                    <span className="comms-state sent">
                      <CheckCircle2 size={14} aria-hidden="true" />
                      Sent
                    </span>
                  ) : draft.status === 'rejected' ? (
                    <span className="comms-state rejected">
                      <XCircle size={14} aria-hidden="true" />
                      Rejected
                    </span>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => rejectDraft(draft)}
                        disabled={!canAct || busyDraftId === draft.id}
                        aria-label={`Reject ${draft.title}`}
                      >
                        <XCircle size={14} aria-hidden="true" />
                        Reject
                      </button>
                      <button
                        type="button"
                        onClick={() => approveDraft(draft)}
                        disabled={!canAct || busyDraftId === draft.id}
                        aria-label={`Approve send ${draft.title}`}
                      >
                        <Send size={14} aria-hidden="true" />
                        Send
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ol>
          <small className="itsm-command-note">
            {itsmTwin.approval_policy} External side effects are {itsmTwin.external_side_effects}.
            {majorCommsEnabled
              ? ' Major-incident bridge, ISINFO, and IVR controls are enabled for this priority.'
              : ' Teams bridge, ISINFO, and IVR controls unlock only for P1/P2 incidents.'}
          </small>
        </>
      ) : (
        <p className="itsm-command-empty">
          Start a local live run to create the Incident, Problem, RITM, Change, bridge,
          ISINFO, IVR, and update drafts.
        </p>
      )}
      <small className="itsm-command-note">{actionStatus}</small>
    </section>
  );
}
