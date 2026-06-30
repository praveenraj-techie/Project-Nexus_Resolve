import { ExternalLink, History } from 'lucide-react';
import type { ServiceNowIncidentHistoryEntry } from '../types';

type Props = {
  backendOnline: boolean;
  incidents: ServiceNowIncidentHistoryEntry[];
  lookupStatus?: Record<string, string>;
  onVerifyIncident: (incidentNumber: string) => void;
};

export function ServiceNowHistoryPanel({
  backendOnline,
  incidents,
  lookupStatus = {},
  onVerifyIncident,
}: Props) {
  const visibleIncidents = incidents.slice(0, 5);
  return (
    <section className="panel servicenow-history-panel" aria-label="ServiceNow PDI history">
      <div className="panel-heading">
        <History size={18} aria-hidden="true" />
        <h2>ServiceNow PDI History</h2>
      </div>
      {visibleIncidents.length > 0 ? (
        <ol className="servicenow-history-list">
          {visibleIncidents.map((incident) => (
            <li key={`${incident.run_id}-${incident.number}`}>
              <div>
                <strong>
                  {incident.url ? (
                    <a href={incident.url} target="_blank" rel="noreferrer">
                      {incident.number}
                      <ExternalLink size={12} aria-hidden="true" />
                    </a>
                  ) : (
                    incident.number
                  )}
                </strong>
                <span>{incident.alert_type ?? incident.synthetic_incident_id ?? incident.run_id}</span>
                {lookupStatus[incident.number] ? (
                  <em>{lookupStatus[incident.number]}</em>
                ) : null}
              </div>
              <div className="servicenow-history-actions">
                <small>{incident.last_update_status ?? incident.status}</small>
                <button
                  type="button"
                  onClick={() => onVerifyIncident(incident.number)}
                  disabled={!backendOnline}
                >
                  Verify
                </button>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="servicenow-history-empty">
          {backendOnline ? 'No live PDI incidents recorded.' : 'Backend offline'}
        </p>
      )}
    </section>
  );
}
