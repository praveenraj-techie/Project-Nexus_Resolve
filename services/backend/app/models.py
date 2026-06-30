from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


PolicyStatus = Literal["pass", "blocked", "requires_approval"]
RunStatus = Literal[
    "created",
    "running",
    "waiting_approval",
    "waiting_closure",
    "observing",
    "closed",
    "rejected",
    "blocked",
    "escalated",
    "failed",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_run_id() -> str:
    return f"run-{uuid4().hex[:12]}"


class IncidentTicket(BaseModel):
    scenario_id: str = "disk-space"
    team: str = "Windows Infra"
    incident_id: str
    priority: str
    title: str
    business_service: str
    affected_ci: str
    environment: str = "synthetic"
    symptoms: list[str] = Field(default_factory=list)
    metric_snapshot: dict[str, Any] = Field(default_factory=dict)
    current_state: str = ""
    requested_outcome: str


class EvidenceItem(BaseModel):
    id: str
    type: Literal["sop", "history", "state", "warning"]
    title: str
    summary: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceSummary(BaseModel):
    outcome: str
    sop_controls: list[str]
    safe_precedent_count: int
    unsafe_precedent_ids: list[str]
    escalation_precedent_ids: list[str]
    governance_note: str


class PolicyCheck(BaseModel):
    name: str
    status: PolicyStatus
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class RemediationPlan(BaseModel):
    summary: str
    target_resources: list[str]
    action_preview: str
    estimated_effect: str
    safeguards: list[str] = Field(default_factory=list)
    approval_required: bool = True
    approval_granted: bool = False
    uses_dry_run: bool = True
    mock_only: bool = True
    validation_steps: list[str] = Field(default_factory=list)
    escalation_condition: str = "Escalate if validation remains below threshold."


class ApprovalSummary(BaseModel):
    decision_required: bool
    operator_message: str
    expected_safe_effect: str
    blocked_until_approved: bool
    replay_side_effects_disabled: bool = True


class RunEvent(BaseModel):
    run_id: str
    sequence: int
    timestamp: datetime
    type: str
    title: str
    message: str
    payload: dict[str, Any] | None = None


class RcaSummary(BaseModel):
    root_cause: str
    actions_taken: list[str]
    validation: str
    business_impact: str
    follow_up: list[str]
    metrics: dict[str, Any] = Field(default_factory=dict)


class AiToolCallRecord(BaseModel):
    operation: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    output_preview: str
    status: Literal["completed", "failed"]
    call_id: str | None = None
    latency_ms: int = 0


class AiUsageRecord(BaseModel):
    operation: str
    source: Literal["openai", "fallback"]
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    cost_basis: str = "pricing_not_configured"
    captured_at: datetime = Field(default_factory=utc_now)
    tool_calls: list[AiToolCallRecord] = Field(default_factory=list)


class AiTelemetrySummary(BaseModel):
    calls: int = 0
    openai_calls: int = 0
    fallback_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_tool_calls: int = 0
    total_latency_ms: int = 0
    estimated_openai_cost_usd: float | None = None
    human_hourly_rate_usd: float = 30.0
    human_baseline_minutes: float = 45.0
    nexus_mttr_minutes: float = 0.0
    estimated_human_cost_usd: float = 0.0
    estimated_nexus_labor_cost_usd: float = 0.0
    estimated_labor_savings_usd: float = 0.0
    estimated_net_savings_usd: float | None = None
    records: list[AiUsageRecord] = Field(default_factory=list)


class ServiceNowIncidentRecord(BaseModel):
    number: str | None = None
    sys_id: str | None = None
    url: str | None = None
    table: str = "incident"
    mode: Literal["live", "dry_run", "not_configured", "no_incident", "missing_sys_id", "failed"] = "dry_run"
    configured: bool = False
    synthetic_incident_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_update_status: str | None = None
    state: str | None = None
    error: str | None = None
    missing: list[str] = Field(default_factory=list)


class ItsmWorkNote(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    author: str = "NEXUS-RESOLVE"
    source_event: str | None = None
    note: str


class ItsmRecord(BaseModel):
    id: str
    record_type: Literal["incident", "ritm", "change", "problem"]
    number: str
    title: str
    state: str
    priority: str | None = None
    risk: str | None = None
    owner_group: str
    business_service: str
    affected_ci: str
    description: str
    linked_records: list[str] = Field(default_factory=list)
    work_notes: list[ItsmWorkNote] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CommsDraft(BaseModel):
    id: str
    channel: Literal[
        "teams_bridge",
        "isinfo_email",
        "ivr",
        "stakeholder_update",
        "closure_update",
    ]
    title: str
    status: Literal["pending_approval", "sent", "rejected"] = "pending_approval"
    subject: str
    body: str
    recipients: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    cadence: str | None = None
    source_event: str
    approval_required: bool = True
    approved_by: str | None = None
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None
    simulated_delivery: dict[str, Any] = Field(default_factory=dict)


class ItsmTwinState(BaseModel):
    mode: Literal["local_itsm_simulator"] = "local_itsm_simulator"
    run_id: str
    external_side_effects: Literal["disabled"] = "disabled"
    approval_policy: str = "Every outbound communication requires human approval."
    records: list[ItsmRecord] = Field(default_factory=list)
    comms: list[CommsDraft] = Field(default_factory=list)
    audit_notes: list[str] = Field(default_factory=list)


class RunSnapshot(BaseModel):
    run_id: str
    status: RunStatus
    events: list[RunEvent]
    approval_record: dict[str, Any] | None = None
    plan: RemediationPlan | None = None
    evidence_summary: EvidenceSummary | None = None
    approval_summary: ApprovalSummary | None = None
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    rca: RcaSummary | None = None
    ai_telemetry: AiTelemetrySummary | None = None
    servicenow_incident: ServiceNowIncidentRecord | None = None
    itsm_twin: ItsmTwinState | None = None
