import { ExternalLink, Server } from 'lucide-react';
import type { ServiceNowIncidentRecord, TicketDetails } from '../types';

type Props = {
  ticket: TicketDetails;
  serviceNowIncident?: ServiceNowIncidentRecord | null;
};

export function TicketPanel({ ticket, serviceNowIncident }: Props) {
  const serviceNowValue = serviceNowIncident?.number ?? serviceNowIncidentLabel(serviceNowIncident);

  return (
    <section className="panel ticket-panel" aria-labelledby="ticket-title">
      <div className="panel-heading">
        <Server size={18} aria-hidden="true" />
        <h2 id="ticket-title">Ticket Details</h2>
      </div>
      <dl className="ticket-grid">
        <div>
          <dt>Team</dt>
          <dd>{ticket.team}</dd>
        </div>
        <div>
          <dt>Alert</dt>
          <dd>{ticket.alert_type}</dd>
        </div>
        <div>
          <dt>Incident</dt>
          <dd>{ticket.incident_id}</dd>
        </div>
        <div>
          <dt>ServiceNow PDI</dt>
          <dd>
            {serviceNowIncident?.url && serviceNowIncident.number ? (
              <a className="ticket-link" href={serviceNowIncident.url} target="_blank" rel="noreferrer">
                {serviceNowIncident.number}
                <ExternalLink size={12} aria-hidden="true" />
              </a>
            ) : (
              serviceNowValue
            )}
          </dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd className="priority">{ticket.priority}</dd>
        </div>
        <div>
          <dt>Affected CI</dt>
          <dd>{ticket.ci}</dd>
        </div>
        <div>
          <dt>Business Service</dt>
          <dd>{ticket.service}</dd>
        </div>
        <div>
          <dt>Current State</dt>
          <dd>{ticket.current_state}</dd>
        </div>
        <div>
          <dt>Outcome</dt>
          <dd>{ticket.requested_outcome}</dd>
        </div>
      </dl>
    </section>
  );
}

function serviceNowIncidentLabel(incident?: ServiceNowIncidentRecord | null): string {
  if (!incident) return 'Not attached';
  if (incident.mode === 'not_configured') return 'Not configured';
  if (incident.mode === 'failed') return 'Create failed';
  if (incident.mode === 'dry_run') return 'Preview only';
  return incident.last_update_status ?? 'Pending';
}
