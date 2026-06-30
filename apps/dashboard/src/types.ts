export type Mode = 'replay' | 'live';

export type EventPayload = Record<string, unknown> | null;

export type AiSource = 'openai' | 'fallback';

export type AiUsageRecord = {
  operation: string;
  source: AiSource;
  model: string;
  latency_ms: number;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost_usd?: number | null;
  cost_basis: string;
  captured_at: string;
  tool_calls?: AiToolCallRecord[];
};

export type AiToolCallRecord = {
  operation: string;
  name: string;
  arguments: Record<string, unknown>;
  output_preview: string;
  status: 'completed' | 'failed';
  call_id?: string | null;
  latency_ms: number;
};

export type AiTelemetrySummary = {
  calls: number;
  openai_calls: number;
  fallback_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_tool_calls?: number;
  total_latency_ms: number;
  estimated_openai_cost_usd?: number | null;
  human_hourly_rate_usd: number;
  human_baseline_minutes: number;
  nexus_mttr_minutes: number;
  estimated_human_cost_usd: number;
  estimated_nexus_labor_cost_usd: number;
  estimated_labor_savings_usd: number;
  estimated_net_savings_usd?: number | null;
  records: AiUsageRecord[];
};

export type AiGeneratedPayload = {
  ai_source?: AiSource;
  generated_by?: string;
  model?: string;
  ai_usage?: AiUsageRecord | null;
  ai_tool_trace?: AiToolCallRecord[];
  ai_telemetry?: AiTelemetrySummary | null;
};

export type ScenarioSummary = {
  scenario_id: string;
  team: string;
  alert_type: string;
  incident_id: string;
  priority: string;
  title: string;
  business_service: string;
  affected_ci: string;
  current_state: string;
  requested_outcome: string;
  mttr_minutes?: number;
  manual_steps_avoided?: number;
  audit_completeness?: string;
  replay_outcome?: 'success' | 'rejected';
};

export type RunEvent = {
  run_id: string;
  sequence: number;
  timestamp: string;
  type: string;
  title: string;
  message: string;
  payload?: EventPayload;
};

export type ServiceNowIncidentRecord = {
  number?: string | null;
  sys_id?: string | null;
  url?: string | null;
  table: string;
  mode: 'live' | 'dry_run' | 'not_configured' | 'no_incident' | 'missing_sys_id' | 'failed';
  configured: boolean;
  synthetic_incident_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_update_status?: string | null;
  state?: string | null;
  error?: string | null;
  missing: string[];
};

export type StartIncidentResponse = {
  run_id: string;
  status: string;
  servicenow_incident?: ServiceNowIncidentRecord | null;
};

export type ServiceNowIncidentHistoryEntry = {
  run_id: string;
  recorded_at: string;
  status: string;
  number: string;
  sys_id?: string | null;
  url?: string | null;
  table: string;
  mode: string;
  created_at?: string | null;
  updated_at?: string | null;
  last_update_status?: string | null;
  state?: string | null;
  error?: string | null;
  scenario_id?: string | null;
  synthetic_incident_id?: string | null;
  team?: string | null;
  alert_type?: string | null;
  business_service?: string | null;
  affected_ci?: string | null;
};

export type ServiceNowIncidentLookup = {
  found: boolean;
  mode: 'live' | 'not_configured';
  missing?: string[];
  incident_number?: string;
  table?: string;
  incident?: {
    number: string;
    sys_id?: string | null;
    state?: string | null;
    short_description?: string | null;
    priority?: string | null;
    impact?: string | null;
    urgency?: string | null;
    assignment_group?: string | null;
    caller_id?: string | null;
    opened_at?: string | null;
    closed_at?: string | null;
    close_code?: string | null;
    close_notes?: string | null;
    correlation_id?: string | null;
    correlation_display?: string | null;
    sys_updated_on?: string | null;
    url?: string | null;
  };
};

export type ItsmWorkNote = {
  timestamp: string;
  author: string;
  source_event?: string | null;
  note: string;
};

export type ItsmRecord = {
  id: string;
  record_type: 'incident' | 'ritm' | 'change' | 'problem';
  number: string;
  title: string;
  state: string;
  priority?: string | null;
  risk?: string | null;
  owner_group: string;
  business_service: string;
  affected_ci: string;
  description: string;
  linked_records: string[];
  work_notes: ItsmWorkNote[];
  evidence: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CommsDraft = {
  id: string;
  channel: 'teams_bridge' | 'isinfo_email' | 'ivr' | 'stakeholder_update' | 'closure_update';
  title: string;
  status: 'pending_approval' | 'sent' | 'rejected';
  subject: string;
  body: string;
  recipients: string[];
  participants: string[];
  cadence?: string | null;
  source_event: string;
  approval_required: boolean;
  approved_by?: string | null;
  approved_at?: string | null;
  sent_at?: string | null;
  rejected_by?: string | null;
  rejected_at?: string | null;
  simulated_delivery: Record<string, unknown>;
};

export type ItsmTwinState = {
  mode: 'local_itsm_simulator';
  run_id: string;
  external_side_effects: 'disabled';
  approval_policy: string;
  records: ItsmRecord[];
  comms: CommsDraft[];
  audit_notes: string[];
};

export type PolicyCheck = {
  name: string;
  status: 'pass' | 'blocked' | 'requires_approval';
  message: string;
  evidence?: Record<string, unknown>;
};

export type RemediationPlan = {
  summary: string;
  target_resources: string[];
  action_preview: string;
  estimated_effect: string;
  safeguards: string[];
  approval_required: boolean;
  approval_granted: boolean;
  uses_dry_run: boolean;
  mock_only: boolean;
  validation_steps: string[];
  escalation_condition: string;
} & AiGeneratedPayload;

export type RcaSummary = {
  root_cause: string;
  actions_taken: string[];
  validation: string;
  business_impact: string;
  follow_up: string[];
  metrics: Record<string, number | string | boolean>;
} & AiGeneratedPayload;

export type ApprovalSummary = {
  decision_required: boolean;
  operator_message: string;
  expected_safe_effect: string;
  blocked_until_approved: boolean;
  replay_side_effects_disabled: boolean;
};

export type TicketDetails = {
  scenario_id: string;
  team: string;
  alert_type: string;
  incident_id: string;
  priority: string;
  ci: string;
  service: string;
  current_state: string;
  requested_outcome: string;
};
