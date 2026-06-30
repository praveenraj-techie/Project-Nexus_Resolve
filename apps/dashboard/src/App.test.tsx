import { fireEvent, render, screen } from '@testing-library/react';
import App from './App';
import { MetricsRibbon } from './components/MetricsRibbon';

vi.mock('./replay', () => ({
  loadReplayEvents: vi.fn(async () => []),
  playReplayEvents: vi.fn(() => () => undefined),
}));

vi.mock('./api', () => ({
  healthCheck: vi.fn(async () => false),
  fetchScenarios: vi.fn(async () => [
    {
      scenario_id: 'disk-space',
      team: 'Windows Infra',
      alert_type: 'Disk utilization high',
      incident_id: 'INC-2026-00421',
      priority: 'P4',
      title: 'C: drive utilization is above threshold',
      business_service: 'Internal Claims Portal',
      affected_ci: 'APP-WIN-042',
      current_state: 'C: drive is 96% used with 8 GB free.',
      requested_outcome: 'Reclaim space with SOP-approved cleanup.',
    },
    {
      scenario_id: 'linux-high-load',
      team: 'Linux',
      alert_type: 'Linux server high CPU / load average',
      incident_id: 'INC-2026-00425',
      priority: 'P3',
      title: 'Linux report worker load average above threshold',
      business_service: 'Reporting Platform',
      affected_ci: 'RPT-LNX-017',
      current_state: 'Load average is 18.6 on an 8-vCPU host.',
      requested_outcome: 'Stabilize load by restarting the approved service only.',
    },
  ]),
  startIncident: vi.fn(),
  approveRun: vi.fn(),
  rejectRun: vi.fn(),
  closeRun: vi.fn(),
  observeRun: vi.fn(),
  fetchItsmTwin: vi.fn(),
  approveCommsDraft: vi.fn(),
  rejectCommsDraft: vi.fn(),
  fetchPolicyDemoBlock: vi.fn(async () => []),
  fetchServiceNowIncidents: vi.fn(async () => []),
  lookupServiceNowIncident: vi.fn(async () => ({ found: false, mode: 'not_configured' })),
  previewServiceNowWorkNote: vi.fn(),
  writeServiceNowWorkNote: vi.fn(),
  connectRunStream: vi.fn(),
}));

describe('App', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/');
  });

  it('renders the alert dashboard as the first screen', async () => {
    render(<App />);

    expect(screen.getByText('NEXUS-RESOLVE')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /active operations alerts/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /priority and team sorted incidents/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /sort alerts/i })).toHaveValue('priority');
    expect(await screen.findByText('Linux server high CPU / load average')).toBeInTheDocument();
  });

  it('opens an alert into the incident workspace', async () => {
    render(<App />);

    fireEvent.click(await screen.findByText('Linux server high CPU / load average'));

    expect(window.location.hash).toBe('#/incident/linux-high-load');
    expect(await screen.findByRole('heading', { name: /ticket details/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /action review/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start simulation/i })).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /scenario/i })).toHaveValue('linux-high-load');
    expect(screen.queryByText('Live AI Proof')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Live AI proof')).not.toBeInTheDocument();
    expect(screen.getByText('Policy checks pending')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /show real block/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /start simulation/i }));

    expect(screen.getByRole('button', { name: /show real block/i })).toBeInTheDocument();
  });

  it('uses the selected mode in fallback metrics', () => {
    render(<MetricsRibbon events={[]} mode="live" />);

    expect(screen.getByText('Live')).toBeInTheDocument();
    expect(screen.getByText('Mode')).toBeInTheDocument();
  });
});
