from __future__ import annotations

from typing import Iterable

from .models import (
    CommsDraft,
    IncidentTicket,
    ItsmRecord,
    ItsmTwinState,
    ItsmWorkNote,
    RcaSummary,
    RemediationPlan,
    utc_now,
)


STAKEHOLDERS = {
    "incident_commander": "Incident Commander",
    "service_owner": "Service Owner",
    "resolver_lead": "Resolver Lead",
    "business_stakeholder": "Business Stakeholder",
    "service_desk": "Service Desk Lead",
}

_RECORD_EVENT_MAP = {
    "itsm.problem.created": "problem-repeat-driver",
    "itsm.serviceops.drafted": "change-remediation-plan",
    "plan.generated": "change-remediation-plan",
    "approval.summary": "ritm-approval-evidence",
    "approval.requested": "ritm-approval-evidence",
    "approval.granted": "ritm-approval-evidence",
    "approval.rejected": "ritm-approval-evidence",
    "execution.mocked": "change-remediation-plan",
    "validation.passed": "change-remediation-plan",
    "validation.failed": "change-remediation-plan",
    "rca.generated": "problem-repeat-driver",
    "incident.closed": "incident-primary",
}


def create_itsm_twin(run_id: str, ticket: IncidentTicket) -> ItsmTwinState:
    twin = ItsmTwinState(run_id=run_id)
    incident = ItsmRecord(
        id="incident-primary",
        record_type="incident",
        number=ticket.incident_id,
        title=ticket.title,
        state="New",
        priority=ticket.priority,
        owner_group=ticket.team,
        business_service=ticket.business_service,
        affected_ci=ticket.affected_ci,
        description=ticket.current_state,
        evidence={
            "scenario_id": ticket.scenario_id,
            "environment": ticket.environment,
            "requested_outcome": ticket.requested_outcome,
        },
        work_notes=[
            ItsmWorkNote(
                note=(
                    "Local ITSM Twin opened from synthetic alert. "
                    "No real ServiceNow, Teams, email, or IVR side effects are enabled."
                )
            )
        ],
    )
    twin.records.append(incident)
    twin.audit_notes.append(
        "incident-primary opened with outbound communication approval policy active."
    )
    _add_initial_comms(twin, ticket)
    return twin


def create_problem_from_history(
    twin: ItsmTwinState, ticket: IncidentTicket, similar_count: int, unsafe_count: int
) -> ItsmRecord:
    return _upsert_record(
        twin,
        ItsmRecord(
            id="problem-repeat-driver",
            record_type="problem",
            number=f"PRB-{ticket.incident_id.removeprefix('INC-')}",
            title=f"Recurring driver for {ticket.alert_type if hasattr(ticket, 'alert_type') else ticket.title}",
            state="Root cause analysis",
            priority=ticket.priority,
            owner_group=ticket.team,
            business_service=ticket.business_service,
            affected_ci=ticket.affected_ci,
            description=(
                f"NEXUS found {similar_count} related historical tickets and "
                f"{unsafe_count} unsafe precedent while investigating {ticket.incident_id}."
            ),
            linked_records=[ticket.incident_id],
            evidence={
                "similar_tickets": similar_count,
                "unsafe_precedents": unsafe_count,
                "created_by": "NEXUS-RESOLVE local ITSM simulator",
            },
            work_notes=[
                ItsmWorkNote(
                    note="Problem record drafted from repeated evidence and unsafe-history signal."
                )
            ],
        ),
    )


def create_ritm_for_approval(twin: ItsmTwinState, ticket: IncidentTicket) -> ItsmRecord:
    return _upsert_record(
        twin,
        ItsmRecord(
            id="ritm-approval-evidence",
            record_type="ritm",
            number=f"RITM-{ticket.incident_id.removeprefix('INC-')}",
            title=f"Approval and evidence package for {ticket.incident_id}",
            state="Awaiting approval",
            priority=ticket.priority,
            owner_group="Service Desk",
            business_service=ticket.business_service,
            affected_ci=ticket.affected_ci,
            description=(
                "Request item tracks human approval, stakeholder communication review, "
                "and audit export generation for the NEXUS remediation workflow."
            ),
            linked_records=[ticket.incident_id],
            evidence={"approval_required": True, "external_side_effects": "disabled"},
            work_notes=[
                ItsmWorkNote(note="RITM opened to track approval-gated operator tasks.")
            ],
        ),
    )


def draft_change_from_plan(
    twin: ItsmTwinState, ticket: IncidentTicket, plan: RemediationPlan
) -> ItsmRecord:
    return _upsert_record(
        twin,
        ItsmRecord(
            id="change-remediation-plan",
            record_type="change",
            number=f"CHG-{ticket.incident_id.removeprefix('INC-')}",
            title=f"Controlled remediation for {ticket.title}",
            state="Draft",
            priority=ticket.priority,
            risk="Low - mock-only demo execution",
            owner_group=ticket.team,
            business_service=ticket.business_service,
            affected_ci=ticket.affected_ci,
            description=(
                f"Plan: {plan.summary}\n"
                f"Expected effect: {plan.estimated_effect}\n"
                f"Rollback: stop before live execution; all actions are mock-only."
            ),
            linked_records=[
                ticket.incident_id,
                f"PRB-{ticket.incident_id.removeprefix('INC-')}",
                f"RITM-{ticket.incident_id.removeprefix('INC-')}",
            ],
            evidence={
                "target_resources": plan.target_resources,
                "uses_dry_run": plan.uses_dry_run,
                "mock_only": plan.mock_only,
                "validation_steps": plan.validation_steps,
            },
            work_notes=[
                ItsmWorkNote(
                    source_event="plan.generated",
                    note="Change draft generated from approved NEXUS plan.",
                )
            ],
        ),
    )


def draft_status_update(
    twin: ItsmTwinState, ticket: IncidentTicket, rca: RcaSummary
) -> CommsDraft:
    return _upsert_comms(
        twin,
        CommsDraft(
            id="stakeholder-update-rca",
            channel="stakeholder_update",
            title="15-minute stakeholder update draft",
            subject=f"Update: {ticket.business_service} - {ticket.title}",
            body=(
                f"Status update for {ticket.business_service}: remediation validated in mock mode. "
                f"Root cause: {rca.root_cause}. Validation: {rca.validation}. "
                "Next step: approve closure or keep under observation."
            ),
            recipients=_stakeholder_recipients(ticket),
            cadence="15-minute major incident update loop",
            source_event="rca.generated",
        ),
    )


def draft_closure_update(
    twin: ItsmTwinState, ticket: IncidentTicket, rca: RcaSummary | None
) -> CommsDraft:
    root_cause = rca.root_cause if rca else "RCA evidence is attached to the audit packet."
    return _upsert_comms(
        twin,
        CommsDraft(
            id="closure-update",
            channel="closure_update",
            title="Closure communication draft",
            subject=f"Resolved: {ticket.business_service} - {ticket.title}",
            body=(
                f"{ticket.incident_id} is ready for closure. Root cause: {root_cause}. "
                "Validation passed and the audit packet is available for review."
            ),
            recipients=_stakeholder_recipients(ticket),
            source_event="incident.closed",
        ),
    )


def close_incident_record(twin: ItsmTwinState, ticket: IncidentTicket) -> ItsmRecord:
    record = _find_record(twin, "incident-primary")
    if record is None:
        return create_itsm_twin(twin.run_id, ticket).records[0]
    record.state = "Resolved"
    record.updated_at = utc_now()
    record.work_notes.append(
        ItsmWorkNote(
            note="Incident marked resolved in Local ITSM Twin after closure approval."
        )
    )
    return record


def add_work_note_for_event(
    twin: ItsmTwinState,
    event_type: str,
    title: str,
    message: str,
    payload: dict[str, object] | None = None,
) -> None:
    record = _find_record(twin, _RECORD_EVENT_MAP.get(event_type, "incident-primary"))
    if record is None:
        record = _find_record(twin, "incident-primary")
    if record is None:
        return

    note = _work_note_text(event_type, title, message, payload or {})
    if record.work_notes and record.work_notes[-1].source_event == event_type:
        if record.work_notes[-1].note == note:
            return
    record.work_notes.append(
        ItsmWorkNote(
            source_event=event_type,
            note=note,
        )
    )
    record.updated_at = utc_now()
    twin.audit_notes.append(f"work_note:{record.number}:{event_type}")


def approve_comms_draft(
    twin: ItsmTwinState,
    draft_id: str,
    *,
    operator: str,
    role: str,
) -> CommsDraft:
    draft = _find_draft(twin, draft_id)
    if draft is None:
        raise KeyError(f"Unknown communication draft: {draft_id}")
    if draft.status == "rejected":
        raise ValueError(f"Communication draft {draft_id} was already rejected.")
    if draft.status == "sent":
        return draft
    now = utc_now()
    draft.status = "sent"
    draft.approved_by = f"{operator} / {role}"
    draft.approved_at = now
    draft.sent_at = now
    draft.simulated_delivery = _simulated_delivery(draft)
    twin.audit_notes.append(f"{draft.id} approved and sent in simulator by {operator}.")
    return draft


def reject_comms_draft(
    twin: ItsmTwinState,
    draft_id: str,
    *,
    operator: str,
    reason: str,
) -> CommsDraft:
    draft = _find_draft(twin, draft_id)
    if draft is None:
        raise KeyError(f"Unknown communication draft: {draft_id}")
    if draft.status == "sent":
        raise ValueError(f"Communication draft {draft_id} was already sent.")
    if draft.status == "rejected":
        return draft
    draft.status = "rejected"
    draft.rejected_by = operator
    draft.rejected_at = utc_now()
    draft.simulated_delivery = {"rejected_reason": reason}
    twin.audit_notes.append(f"{draft.id} rejected in simulator by {operator}: {reason}")
    return draft


def _work_note_text(
    event_type: str,
    title: str,
    message: str,
    payload: dict[str, object],
) -> str:
    lines = [
        f"{title} [{event_type}]",
        message,
    ]
    if event_type == "ticket.received":
        incident_id = payload.get("incident_id")
        ci = payload.get("ci")
        service = payload.get("service")
        priority = payload.get("priority")
        lines.append(
            "Intake: "
            f"incident={incident_id or 'unknown'}, "
            f"priority={priority or 'unknown'}, "
            f"ci={ci or 'unknown'}, "
            f"service={service or 'unknown'}."
        )
    if event_type == "plan.generated" and payload.get("summary"):
        lines.append(f"Plan summary: {payload['summary']}")
    if event_type == "approval.granted" and isinstance(payload.get("approval_record"), dict):
        approval = payload["approval_record"]
        lines.append(
            "Approval: "
            f"{approval.get('operator', 'unknown')} / "
            f"{approval.get('role', 'unknown')}."
        )
    if event_type == "comms.sent" and isinstance(payload.get("draft"), dict):
        draft = payload["draft"]
        lines.append(
            "Communication: "
            f"{draft.get('channel', 'unknown')} sent in simulator after approval."
        )
    if event_type == "comms.rejected" and isinstance(payload.get("draft"), dict):
        draft = payload["draft"]
        lines.append(
            "Communication: "
            f"{draft.get('channel', 'unknown')} remained blocked after rejection."
        )
    if event_type == "rca.generated" and payload.get("root_cause"):
        lines.append(f"RCA: {payload['root_cause']}")
    if event_type == "incident.closed" and payload.get("closure_code"):
        lines.append(f"Closure: {payload['closure_code']}")
    return "\n".join(lines)


def _add_initial_comms(twin: ItsmTwinState, ticket: IncidentTicket) -> None:
    recipients = _stakeholder_recipients(ticket)
    participants = list(STAKEHOLDERS.values()) + [ticket.team]
    _upsert_comms(
        twin,
        CommsDraft(
            id="teams-bridge",
            channel="teams_bridge",
            title="Teams bridge draft",
            subject=f"{ticket.priority} bridge: {ticket.business_service} - {ticket.title}",
            body=(
                "Agenda: confirm impact, assign owner, review NEXUS evidence, "
                "approve mock remediation, and schedule next update."
            ),
            recipients=recipients,
            participants=participants,
            cadence="Open bridge until closure or observation decision.",
            source_event="ticket.received",
        ),
    )
    _upsert_comms(
        twin,
        CommsDraft(
            id="isinfo-initial",
            channel="isinfo_email",
            title="Initial ISINFO draft",
            subject=f"ISINFO: {ticket.business_service} investigation started",
            body=(
                f"We are investigating {ticket.title} affecting {ticket.business_service}. "
                f"Current state: {ticket.current_state} "
                "NEXUS is gathering SOP, historical precedent, and policy evidence. "
                "Next update will follow after approval review."
            ),
            recipients=recipients,
            cadence="Initial communication plus updates from work notes.",
            source_event="ticket.received",
        ),
    )
    _upsert_comms(
        twin,
        CommsDraft(
            id="ivr-standby",
            channel="ivr",
            title="IVR activation draft",
            subject=f"IVR standby: {ticket.business_service}",
            body=(
                f"IVR message prepared for targeted users of {ticket.business_service}. "
                "Activation remains blocked until an incident commander approves."
            ),
            recipients=[f"targeted-users:{ticket.business_service}"],
            cadence="Activate only if business impact expands.",
            source_event="ticket.received",
        ),
    )


def _stakeholder_recipients(ticket: IncidentTicket) -> list[str]:
    service = ticket.business_service.lower().replace(" ", ".")
    team = ticket.team.lower().replace(" ", ".").replace("/", "-")
    return [
        f"{team}.resolver@example.com",
        f"{service}.owner@example.com",
        "incident.commander@example.com",
        "service.desk.lead@example.com",
    ]


def _upsert_record(twin: ItsmTwinState, record: ItsmRecord) -> ItsmRecord:
    index = next((i for i, item in enumerate(twin.records) if item.id == record.id), None)
    if index is None:
        twin.records.append(record)
        twin.audit_notes.append(f"{record.record_type}:{record.number} created.")
        return record
    record.created_at = twin.records[index].created_at
    record.updated_at = utc_now()
    twin.records[index] = record
    twin.audit_notes.append(f"{record.record_type}:{record.number} refreshed.")
    return record


def _upsert_comms(twin: ItsmTwinState, draft: CommsDraft) -> CommsDraft:
    index = next((i for i, item in enumerate(twin.comms) if item.id == draft.id), None)
    if index is None:
        twin.comms.append(draft)
        twin.audit_notes.append(f"{draft.channel}:{draft.id} drafted for approval.")
        return draft
    existing = twin.comms[index]
    if existing.status == "pending_approval":
        twin.comms[index] = draft
        twin.audit_notes.append(f"{draft.channel}:{draft.id} refreshed.")
        return draft
    return existing


def _find_record(twin: ItsmTwinState, record_id: str) -> ItsmRecord | None:
    return next((record for record in twin.records if record.id == record_id), None)


def _find_draft(twin: ItsmTwinState, draft_id: str) -> CommsDraft | None:
    return next((draft for draft in twin.comms if draft.id == draft_id), None)


def _simulated_delivery(draft: CommsDraft) -> dict[str, object]:
    targets: Iterable[str] = draft.participants or draft.recipients
    return {
        "external_side_effects": "disabled",
        "simulated_at": utc_now().isoformat(),
        "channel": draft.channel,
        "target_count": len(list(targets)),
        "delivery_state": "simulated_success",
    }
