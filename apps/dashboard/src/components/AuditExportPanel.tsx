import { useState } from 'react';
import { Download, FileJson, FileText, Send } from 'lucide-react';
import {
  auditPacketUrl,
  auditReportPdfUrl,
  previewServiceNowWorkNote,
  writeServiceNowWorkNote,
} from '../api';
import type { RunEvent, ServiceNowIncidentRecord } from '../types';

type Props = {
  backendOnline: boolean;
  events: RunEvent[];
  runId: string | null;
  serviceNowIncident?: ServiceNowIncidentRecord | null;
};

const AUDIT_READY_EVENTS = new Set([
  'rca.generated',
  'closure.requested',
  'incident.closed',
  'approval.rejected',
  'policy.blocked',
  'observation.completed',
]);

export function AuditExportPanel({ backendOnline, events, runId, serviceNowIncident }: Props) {
  const liveRun = Boolean(runId && !runId.startsWith('replay-') && backendOnline);
  const auditReady = liveRun && events.some((event) => AUDIT_READY_EVENTS.has(event.type));
  const canWriteServiceNowNote = Boolean(
    auditReady && serviceNowIncident?.mode === 'live' && serviceNowIncident.number,
  );
  const [serviceNowStatus, setServiceNowStatus] = useState<string>('ServiceNow Preview Pending');

  async function previewServiceNow() {
    if (!runId) return;
    setServiceNowStatus('Preparing ServiceNow work-note');
    try {
      const result = await previewServiceNowWorkNote(runId);
      const incident =
        result.request.incident_number ??
        result.request.synthetic_incident_id ??
        serviceNowIncident?.number ??
        serviceNowIncident?.synthetic_incident_id ??
        'incident not attached';
      setServiceNowStatus(
        `${result.mode}: ${incident}, ${result.request.body.work_notes.length} chars`,
      );
    } catch (error) {
      setServiceNowStatus(
        error instanceof Error ? error.message : 'ServiceNow preview unavailable.',
      );
    }
  }

  async function writeServiceNow() {
    if (!runId) return;
    setServiceNowStatus('Writing ServiceNow work-note');
    try {
      const result = await writeServiceNowWorkNote(runId);
      const incident =
        result.request.incident_number ??
        serviceNowIncident?.number ??
        serviceNowIncident?.synthetic_incident_id ??
        'incident not attached';
      setServiceNowStatus(
        result.sent
          ? `live: ${incident}, final audit note written`
          : `${result.mode}: ${incident}, work-note not sent`,
      );
    } catch (error) {
      setServiceNowStatus(
        error instanceof Error ? error.message : 'ServiceNow write unavailable.',
      );
    }
  }

  return (
    <section className="panel audit-export-panel" aria-label="Audit export downloads">
      <div className="panel-heading">
        <Download size={18} aria-hidden="true" />
        <h2>Audit Export</h2>
      </div>
      <p>
        {auditReady
          ? 'Download the server-generated audit packet for this run.'
          : liveRun
            ? 'Audit export unlocks after RCA, rejection, or policy-block evidence is available.'
          : 'Start a local live run to enable server-generated PDF and JSON downloads.'}
      </p>
      <div className="audit-export-actions">
        {auditReady && runId ? (
          <>
            <a className="download-button" href={auditReportPdfUrl(runId)} download>
              <FileText size={16} aria-hidden="true" />
              PDF Report
            </a>
            <a className="download-button secondary" href={auditPacketUrl(runId)} target="_blank" rel="noreferrer">
              <FileJson size={16} aria-hidden="true" />
              JSON Packet
            </a>
            <button className="download-button secondary" type="button" onClick={previewServiceNow}>
              <Send size={16} aria-hidden="true" />
              Preview Note
            </button>
            {canWriteServiceNowNote ? (
              <button className="download-button secondary" type="button" onClick={writeServiceNow}>
                <Send size={16} aria-hidden="true" />
                Write Note
              </button>
            ) : null}
          </>
        ) : (
          <>
            <span>PDF Report Pending</span>
            <span>JSON Packet Pending</span>
            <span>ServiceNow Preview Pending</span>
          </>
        )}
      </div>
      <small className="audit-export-note">{serviceNowStatus}</small>
    </section>
  );
}
