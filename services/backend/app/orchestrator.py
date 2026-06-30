from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .event_stream import EventStream
from .itsm import (
    add_work_note_for_event,
    approve_comms_draft,
    close_incident_record,
    create_itsm_twin,
    create_problem_from_history,
    create_ritm_for_approval,
    draft_change_from_plan,
    draft_closure_update,
    draft_status_update,
    reject_comms_draft,
)
from .mock_execute import mock_execute
from .models import (
    AiTelemetrySummary,
    AiUsageRecord,
    ApprovalSummary,
    EvidenceSummary,
    IncidentTicket,
    ItsmTwinState,
    PolicyCheck,
    RcaSummary,
    RemediationPlan,
    RunSnapshot,
    RunStatus,
    ServiceNowIncidentRecord,
    new_run_id,
    utc_now,
)
from .openai_client import NexusOpenAIClient
from .policy import has_blocking_check, policy_check
from .servicenow import ServiceNowWriteBackClient
from .servicenow_history import record_servicenow_incident
from .tools import (
    DATA_ROOT,
    get_incident_for_scenario,
    get_initial_state,
    retrieve_similar_tickets,
    retrieve_sop,
    validate_result,
)


_SERVICENOW_MILESTONE_EVENTS = {
    "ticket.received",
    "evidence.summary",
    "plan.generated",
    "approval.requested",
    "approval.granted",
    "approval.rejected",
    "execution.mocked",
    "validation.passed",
    "validation.failed",
    "rca.generated",
    "closure.requested",
    "observation.started",
    "observation.completed",
    "incident.closed",
    "policy.blocked",
}

_MAJOR_INCIDENT_COMMS_DRAFT_IDS = {"teams-bridge", "isinfo-initial", "ivr-standby"}


class ServiceNowIncidentCreateError(RuntimeError):
    """Raised when live mode cannot attach a real ServiceNow incident."""


@dataclass
class RunSession:
    run_id: str
    stream: EventStream
    status: RunStatus = "created"
    approval_future: asyncio.Future[bool] | None = None
    closure_future: asyncio.Future[str] | None = None
    done_future: asyncio.Future[None] | None = None
    evidence_summary: EvidenceSummary | None = None
    approval_summary: ApprovalSummary | None = None
    plan: RemediationPlan | None = None
    policy_checks: list[PolicyCheck] = field(default_factory=list)
    rca: RcaSummary | None = None
    approval_record: dict[str, Any] | None = None
    ai_usage_records: list[AiUsageRecord] = field(default_factory=list)
    servicenow_incident: ServiceNowIncidentRecord | None = None
    servicenow_updates: list[dict[str, Any]] = field(default_factory=list)
    itsm_twin: ItsmTwinState | None = None
    ticket: IncidentTicket | None = None
    human_hourly_rate_usd: float = 30.0
    human_baseline_minutes: float = 45.0
    nexus_mttr_minutes: float = 0.0

    def snapshot(self) -> RunSnapshot:
        return RunSnapshot(
            run_id=self.run_id,
            status=self.status,
            events=self.stream.events,
            approval_record=self.approval_record,
            plan=self.plan,
            evidence_summary=self.evidence_summary,
            approval_summary=self.approval_summary,
            policy_checks=self.policy_checks,
            rca=self.rca,
            ai_telemetry=self.ai_telemetry_summary(),
            servicenow_incident=self.servicenow_incident,
            itsm_twin=self.itsm_twin,
        )

    def ai_telemetry_summary(self) -> AiTelemetrySummary:
        openai_costs = [
            record.estimated_cost_usd
            for record in self.ai_usage_records
            if record.estimated_cost_usd is not None
        ]
        estimated_openai_cost = (
            round(sum(openai_costs), 6)
            if len(openai_costs) == len(self.ai_usage_records) and self.ai_usage_records
            else None
        )
        estimated_human_cost = round(
            self.human_baseline_minutes / 60 * self.human_hourly_rate_usd, 2
        )
        estimated_nexus_labor_cost = round(
            self.nexus_mttr_minutes / 60 * self.human_hourly_rate_usd, 2
        )
        estimated_labor_savings = round(
            max(estimated_human_cost - estimated_nexus_labor_cost, 0), 2
        )
        estimated_net_savings = (
            round(estimated_labor_savings - estimated_openai_cost, 4)
            if estimated_openai_cost is not None
            else None
        )
        return AiTelemetrySummary(
            calls=len(self.ai_usage_records),
            openai_calls=sum(1 for record in self.ai_usage_records if record.source == "openai"),
            fallback_calls=sum(1 for record in self.ai_usage_records if record.source == "fallback"),
            total_input_tokens=sum(record.input_tokens or 0 for record in self.ai_usage_records),
            total_output_tokens=sum(record.output_tokens or 0 for record in self.ai_usage_records),
            total_tokens=sum(record.total_tokens or 0 for record in self.ai_usage_records),
            total_tool_calls=sum(len(record.tool_calls) for record in self.ai_usage_records),
            total_latency_ms=sum(record.latency_ms for record in self.ai_usage_records),
            estimated_openai_cost_usd=estimated_openai_cost,
            human_hourly_rate_usd=self.human_hourly_rate_usd,
            human_baseline_minutes=self.human_baseline_minutes,
            nexus_mttr_minutes=self.nexus_mttr_minutes,
            estimated_human_cost_usd=estimated_human_cost,
            estimated_nexus_labor_cost_usd=estimated_nexus_labor_cost,
            estimated_labor_savings_usd=estimated_labor_savings,
            estimated_net_savings_usd=estimated_net_savings,
            records=self.ai_usage_records,
        )


class RunManager:
    def __init__(
        self,
        openai_client: NexusOpenAIClient | None = None,
        servicenow_client: ServiceNowWriteBackClient | None = None,
        event_delay_seconds: float = 0.0,
    ) -> None:
        self.openai_client = openai_client or NexusOpenAIClient()
        self.servicenow_client = servicenow_client or ServiceNowWriteBackClient()
        self.event_delay_seconds = event_delay_seconds
        self.sessions: dict[str, RunSession] = {}

    async def start_run(
        self, ticket: IncidentTicket | None = None, scenario_id: str = "disk-space"
    ) -> RunSession:
        run_id = new_run_id()
        loop = asyncio.get_running_loop()
        session = RunSession(
            run_id=run_id,
            stream=EventStream(run_id),
            approval_future=loop.create_future(),
            closure_future=loop.create_future(),
            done_future=loop.create_future(),
        )
        self.sessions[run_id] = session
        selected_ticket = ticket or get_incident_for_scenario(scenario_id)
        session.ticket = selected_ticket
        session.itsm_twin = create_itsm_twin(session.run_id, selected_ticket)
        incident_created = await self._create_servicenow_incident(
            session, selected_ticket
        )
        if self._requires_live_servicenow_incident() and not incident_created:
            self.sessions.pop(run_id, None)
            if session.done_future and not session.done_future.done():
                session.done_future.set_result(None)
            detail = (
                session.servicenow_incident.error
                if session.servicenow_incident and session.servicenow_incident.error
                else "ServiceNow Table API did not return a live incident."
            )
            raise ServiceNowIncidentCreateError(
                "Real ServiceNow PDI incident was not created; live run was not started. "
                f"{detail}"
            )
        asyncio.create_task(self._execute(session, selected_ticket))
        return session

    def get_session(self, run_id: str) -> RunSession | None:
        return self.sessions.get(run_id)

    def approve(
        self, run_id: str, approval_record: dict[str, Any] | None = None
    ) -> RunSnapshot:
        session = self._require_session(run_id)
        if session.approval_future and not session.approval_future.done():
            session.approval_record = approval_record or {
                "operator": "Demo Operator",
                "role": "Incident Approver",
                "reason": "Approved mock-only remediation after policy review.",
                "recorded_at": utc_now().isoformat(),
            }
            session.approval_future.set_result(True)
        return session.snapshot()

    def reject(self, run_id: str) -> RunSnapshot:
        session = self._require_session(run_id)
        if session.approval_future and not session.approval_future.done():
            session.approval_future.set_result(False)
        return session.snapshot()

    def close_incident(self, run_id: str) -> RunSnapshot:
        session = self._require_session(run_id)
        if session.closure_future and not session.closure_future.done():
            session.closure_future.set_result("close")
        return session.snapshot()

    def observe_incident(self, run_id: str) -> RunSnapshot:
        session = self._require_session(run_id)
        if session.closure_future and not session.closure_future.done():
            session.closure_future.set_result("observe")
        return session.snapshot()

    async def approve_comms(
        self, run_id: str, draft_id: str, approval_record: dict[str, Any] | None = None
    ) -> RunSnapshot:
        session = self._require_session(run_id)
        if not session.itsm_twin:
            raise KeyError(f"ITSM Twin is not available for {run_id}")
        self._require_major_comms_allowed(session, draft_id)
        approval = approval_record or {}
        draft = approve_comms_draft(
            session.itsm_twin,
            draft_id,
            operator=str(approval.get("operator", "Demo Operator")),
            role=str(approval.get("role", "Incident Commander")),
        )
        await self._emit(
            session,
            "comms.sent",
            f"{draft.title} sent in simulator",
            (
                f"{draft.channel} was approved and delivered in the Local ITSM Twin. "
                "No external Teams, email, or IVR side effect occurred."
            ),
            {
                "draft": draft.model_dump(mode="json"),
                "itsm_twin": session.itsm_twin.model_dump(mode="json"),
            },
            sync_servicenow=False,
        )
        return session.snapshot()

    async def reject_comms(
        self, run_id: str, draft_id: str, rejection_record: dict[str, Any] | None = None
    ) -> RunSnapshot:
        session = self._require_session(run_id)
        if not session.itsm_twin:
            raise KeyError(f"ITSM Twin is not available for {run_id}")
        self._require_major_comms_allowed(session, draft_id)
        rejection = rejection_record or {}
        draft = reject_comms_draft(
            session.itsm_twin,
            draft_id,
            operator=str(rejection.get("operator", "Demo Operator")),
            reason=str(rejection.get("reason", "Rejected during manual review.")),
        )
        await self._emit(
            session,
            "comms.rejected",
            f"{draft.title} rejected",
            f"{draft.channel} remained blocked by the manual approval gate.",
            {
                "draft": draft.model_dump(mode="json"),
                "itsm_twin": session.itsm_twin.model_dump(mode="json"),
            },
            sync_servicenow=False,
        )
        return session.snapshot()

    def _require_major_comms_allowed(self, session: RunSession, draft_id: str) -> None:
        if draft_id not in _MAJOR_INCIDENT_COMMS_DRAFT_IDS:
            return
        priority = session.ticket.priority if session.ticket else ""
        if priority in {"P1", "P2"}:
            return
        raise ValueError(
            "Teams bridge, ISINFO, and IVR communications are enabled only for P1/P2 incidents."
        )

    def _require_session(self, run_id: str) -> RunSession:
        session = self.sessions.get(run_id)
        if not session:
            raise KeyError(f"Unknown run_id: {run_id}")
        return session

    async def _emit(
        self,
        session: RunSession,
        event_type: str,
        title: str,
        message: str,
        payload: dict[str, Any],
        *,
        sync_servicenow: bool = True,
    ) -> None:
        if session.itsm_twin:
            add_work_note_for_event(
                session.itsm_twin,
                event_type,
                title,
                message,
                payload,
            )
        await session.stream.emit(event_type, title, message, payload)
        if sync_servicenow and not event_type.startswith("servicenow."):
            await self._sync_servicenow_for_event(
                session, event_type, title, message, payload
            )
        if self.event_delay_seconds > 0:
            await asyncio.sleep(self.event_delay_seconds)

    async def _create_servicenow_incident(
        self, session: RunSession, ticket: IncidentTicket
    ) -> bool:
        try:
            result = self.servicenow_client.create_incident(ticket, session.run_id)
            incident = result.get("incident")
            if incident:
                session.servicenow_incident = ServiceNowIncidentRecord.model_validate(
                    incident
                )
            mode = result.get("mode", "dry_run")
            if result.get("sent") and session.servicenow_incident:
                record_servicenow_incident(
                    run_id=session.run_id,
                    ticket=ticket,
                    incident=session.servicenow_incident,
                    status="created",
                )
                await self._emit(
                    session,
                    "servicenow.incident.created",
                    "ServiceNow incident created",
                    (
                        f"{session.servicenow_incident.number} was created in the PDI "
                        f"for synthetic alert {ticket.incident_id}."
                    ),
                    {
                        "servicenow_incident": session.servicenow_incident.model_dump(
                            mode="json"
                        ),
                        "synthetic_incident_id": ticket.incident_id,
                    },
                    sync_servicenow=False,
                )
                return True

            title = (
                "ServiceNow incident not configured"
                if mode == "not_configured"
                else "ServiceNow incident creation previewed"
            )
            message = (
                "No PDI incident was created because ServiceNow credentials are missing."
                if mode == "not_configured"
                else str(result.get("reason", "Live ServiceNow incident creation is disabled."))
            )
            await self._emit(
                session,
                "servicenow.incident.preview",
                title,
                message,
                {
                    "mode": mode,
                    "missing": result.get("missing", []),
                    "servicenow_incident": (
                        session.servicenow_incident.model_dump(mode="json")
                        if session.servicenow_incident
                        else None
                    ),
                },
                sync_servicenow=False,
            )
            return False
        except Exception as exc:
            session.servicenow_incident = ServiceNowIncidentRecord(
                mode="failed",
                configured=True,
                table=self.servicenow_client.config.table,
                synthetic_incident_id=ticket.incident_id,
                error=str(exc),
                last_update_status="create_failed",
            )
            await self._emit(
                session,
                "servicenow.incident.failed",
                "ServiceNow incident create failed",
                "The workflow continued safely without a PDI incident record.",
                {
                    "error": str(exc),
                    "servicenow_incident": session.servicenow_incident.model_dump(
                        mode="json"
                    ),
                },
                sync_servicenow=False,
            )
            return False

    def _requires_live_servicenow_incident(self) -> bool:
        config = getattr(self.servicenow_client, "config", None)
        return bool(
            getattr(config, "live_mode", False)
            and getattr(config, "create_enabled", False)
            and getattr(config, "update_enabled", False)
        )

    async def _sync_servicenow_for_event(
        self,
        session: RunSession,
        event_type: str,
        title: str,
        message: str,
        payload: dict[str, Any],
    ) -> None:
        if event_type not in _SERVICENOW_MILESTONE_EVENTS:
            return
        if not session.servicenow_incident or session.servicenow_incident.mode != "live":
            return

        note = self._servicenow_note_for_event(
            session, event_type, title, message, payload
        )
        try:
            fields = self.servicenow_client.fields_for_event(
                event_type, session.run_id, payload
            )
            result = self.servicenow_client.append_work_note(
                session.servicenow_incident,
                note,
                fields=fields,
            )
            session.servicenow_updates.append(
                {
                    "event_type": event_type,
                    "sent": result.get("sent", False),
                    "mode": result.get("mode"),
                    "recorded_at": utc_now().isoformat(),
                }
            )
            session.servicenow_incident.updated_at = utc_now()
            session.servicenow_incident.last_update_status = (
                f"work_note:{event_type}"
                if result.get("sent")
                else f"work_note_skipped:{result.get('mode', 'unknown')}"
            )
            if result.get("sent") and fields and fields.get("state"):
                session.servicenow_incident.state = str(fields["state"])
            record_servicenow_incident(
                run_id=session.run_id,
                ticket=session.ticket,
                incident=session.servicenow_incident,
                status="updated" if result.get("sent") else "update_skipped",
            )
            await self._emit(
                session,
                "servicenow.work_note.updated"
                if result.get("sent")
                else "servicenow.work_note.skipped",
                "ServiceNow work note updated"
                if result.get("sent")
                else "ServiceNow work note skipped",
                (
                    f"{session.servicenow_incident.number} received a work note for {event_type}."
                    if result.get("sent")
                    else str(result.get("reason", "The PDI work note was not sent."))
                ),
                {
                    "event_type": event_type,
                    "mode": result.get("mode"),
                    "sent": result.get("sent", False),
                    "servicenow_incident": session.servicenow_incident.model_dump(
                        mode="json"
                    ),
                },
                sync_servicenow=False,
            )
        except Exception as exc:
            session.servicenow_updates.append(
                {
                    "event_type": event_type,
                    "sent": False,
                    "mode": "failed",
                    "error": str(exc),
                    "recorded_at": utc_now().isoformat(),
                }
            )
            session.servicenow_incident.updated_at = utc_now()
            session.servicenow_incident.last_update_status = (
                f"work_note_failed:{event_type}"
            )
            session.servicenow_incident.error = str(exc)
            record_servicenow_incident(
                run_id=session.run_id,
                ticket=session.ticket,
                incident=session.servicenow_incident,
                status="update_failed",
            )
            await self._emit(
                session,
                "servicenow.work_note.failed",
                "ServiceNow work note failed",
                f"The PDI work note for {event_type} was not sent.",
                {
                    "event_type": event_type,
                    "error": str(exc),
                    "servicenow_incident": session.servicenow_incident.model_dump(
                        mode="json"
                    ),
                },
                sync_servicenow=False,
            )

    @staticmethod
    def _servicenow_note_for_event(
        session: RunSession,
        event_type: str,
        title: str,
        message: str,
        payload: dict[str, Any],
    ) -> str:
        lines = [
            f"NEXUS-RESOLVE run {session.run_id} milestone: {title}",
            f"Event: {event_type}",
            f"Workflow status: {session.status}",
            f"Message: {message}",
        ]
        if event_type == "plan.generated" and payload.get("summary"):
            lines.append(f"Plan: {payload['summary']}")
        if event_type == "approval.granted" and payload.get("approval_record"):
            approval = payload["approval_record"]
            lines.append(
                f"Approval: {approval.get('operator', 'unknown')} / {approval.get('role', 'unknown')}"
            )
        if event_type == "rca.generated" and payload.get("root_cause"):
            lines.append(f"Root cause: {payload['root_cause']}")
        if event_type == "incident.closed" and payload.get("closure_code"):
            lines.append(f"Closure: {payload['closure_code']}")
        return "\n".join(lines)

    def _ai_payload(self, session: RunSession, payload: dict[str, Any]) -> dict[str, Any]:
        source = self.openai_client.last_response_source
        usage_record = self.openai_client.last_usage_record
        tool_calls = usage_record.tool_calls if usage_record else []
        return {
            **payload,
            "ai_source": source,
            "model": self.openai_client.model,
            "generated_by": (
                "OpenAI Responses API + local tool loop"
                if source == "openai" and tool_calls
                else "OpenAI Responses API"
                if source == "openai"
                else "Deterministic fallback"
            ),
            "ai_usage": (
                usage_record.model_dump(mode="json") if usage_record is not None else None
            ),
            "ai_tool_trace": [record.model_dump(mode="json") for record in tool_calls],
            "ai_telemetry": session.ai_telemetry_summary().model_dump(mode="json"),
        }

    def _capture_ai_usage(self, session: RunSession) -> None:
        record = self.openai_client.last_usage_record
        if record is not None:
            session.ai_usage_records.append(record)

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw in (None, ""):
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    @staticmethod
    def _minutes_from_metric(value: Any) -> float:
        text = str(value)
        digits = "".join(char if char.isdigit() or char == "." else " " for char in text)
        for part in digits.split():
            try:
                return float(part)
            except ValueError:
                continue
        return 0.0

    async def _execute(self, session: RunSession, ticket: IncidentTicket) -> None:
        try:
            await self._run_workflow(session, ticket)
        except Exception as exc:
            session.status = "failed"
            await self._emit(
                session,
                "run.failed",
                "Run failed safely",
                "The workflow stopped without executing remediation.",
                {"error": str(exc)},
            )
        finally:
            if session.done_future and not session.done_future.done():
                session.done_future.set_result(None)

    async def _run_workflow(
        self, session: RunSession, ticket: IncidentTicket
    ) -> None:
        session.status = "running"
        await self._emit(
            session,
            "ticket.received",
            f"{ticket.team} alert received",
            f"{ticket.incident_id} reports {ticket.title} on {ticket.affected_ci}.",
            {
                "scenario_id": ticket.scenario_id,
                "team": ticket.team,
                "alert_type": ticket.metric_snapshot.get("alert_type", ticket.title),
                "incident_id": ticket.incident_id,
                "priority": ticket.priority,
                "ci": ticket.affected_ci,
                "service": ticket.business_service,
                "current_state": ticket.current_state,
                "requested_outcome": ticket.requested_outcome,
                "servicenow_incident": (
                    session.servicenow_incident.model_dump(mode="json")
                    if session.servicenow_incident
                    else None
                ),
            },
        )

        if session.itsm_twin:
            incident = session.itsm_twin.records[0]
            await self._emit(
                session,
                "itsm.incident.created",
                "Local ITSM incident opened",
                (
                    f"{incident.number} is now tracked in the Local ITSM Twin with "
                    "manual approval required for bridge, ISINFO, and IVR actions."
                ),
                {
                    "record": incident.model_dump(mode="json"),
                    "itsm_twin": session.itsm_twin.model_dump(mode="json"),
                },
            )
            await self._emit(
                session,
                "comms.command_center.drafted",
                "Command center drafts prepared",
                (
                    "Teams bridge, initial ISINFO email, and IVR standby drafts are "
                    "ready but blocked until a human approves each outbound action."
                ),
                {
                    "drafts": [
                        draft.model_dump(mode="json") for draft in session.itsm_twin.comms
                    ],
                    "itsm_twin": session.itsm_twin.model_dump(mode="json"),
                },
            )

        sop = retrieve_sop(ticket)
        await self._emit(
            session,
            "evidence.sop",
            "SOP retrieved",
            sop.summary,
            sop.model_dump(mode="json"),
        )

        history = retrieve_similar_tickets(ticket)
        unsafe = [item for item in history if not item.metadata.get("safe")]
        escalations = [
            item for item in history if item.metadata.get("outcome") == "escalated"
        ]
        await self._emit(
            session,
            "evidence.history",
            "Historical tickets compared",
            f"{len(history)} similar tickets found; {len(unsafe)} unsafe precedent flagged.",
            {
                "safe_examples": len(history) - len(unsafe) - len(escalations),
                "unsafe_examples": len(unsafe),
                "escalations": len(escalations),
                "unsafe_ticket": unsafe[0].id if unsafe else None,
                "items": [item.model_dump(mode="json") for item in history],
            },
        )

        if session.itsm_twin:
            problem = create_problem_from_history(
                session.itsm_twin,
                ticket,
                similar_count=len(history),
                unsafe_count=len(unsafe),
            )
            await self._emit(
                session,
                "itsm.problem.created",
                "Problem record drafted",
                (
                    f"{problem.number} links the incident to repeated history and "
                    "unsafe-precedent evidence for permanent-fix tracking."
                ),
                {
                    "record": problem.model_dump(mode="json"),
                    "itsm_twin": session.itsm_twin.model_dump(mode="json"),
                },
            )

        before_state = get_initial_state(ticket)
        scenario_rca = before_state.get("scenario", {}).get("rca", {})
        rca_metrics = scenario_rca.get("metrics", {})
        session.human_hourly_rate_usd = self._env_float("HUMAN_HOURLY_RATE_USD", 30.0)
        session.human_baseline_minutes = self._env_float(
            "HUMAN_BASELINE_MINUTES_PER_INCIDENT", 45.0
        )
        session.nexus_mttr_minutes = self._minutes_from_metric(
            rca_metrics.get("MTTR Estimate", 0)
        )

        if unsafe:
            await self._emit(
                session,
                "policy.warning",
                "SOP beats history",
                before_state["scenario"].get(
                    "unsafe_message", "Unsafe history is blocked by SOP controls."
                ),
                {"blocked_precedent": unsafe[0].model_dump(mode="json")},
            )

        session.evidence_summary = await self.openai_client.create_evidence_summary(
            ticket, sop, history, before_state
        )
        self._capture_ai_usage(session)
        await self._emit_openai_notice_if_needed(session)
        await self._emit(
            session,
            "evidence.summary",
            "OpenAI evidence summary structured"
            if self.openai_client.last_response_source == "openai"
            else "Evidence summary structured",
            session.evidence_summary.outcome,
            self._ai_payload(session, session.evidence_summary.model_dump(mode="json")),
        )

        session.plan = await self.openai_client.create_plan(
            ticket, sop, history, before_state
        )
        self._capture_ai_usage(session)
        await self._emit_openai_notice_if_needed(session)

        await self._emit(
            session,
            "plan.generated",
            "OpenAI remediation plan generated"
            if self.openai_client.last_response_source == "openai"
            else "Safe remediation plan generated",
            session.plan.summary,
            self._ai_payload(session, session.plan.model_dump(mode="json")),
        )

        if session.itsm_twin:
            ritm = create_ritm_for_approval(session.itsm_twin, ticket)
            change = draft_change_from_plan(session.itsm_twin, ticket, session.plan)
            await self._emit(
                session,
                "itsm.serviceops.drafted",
                "RITM and Change drafted",
                (
                    f"{ritm.number} tracks approval tasks and {change.number} captures "
                    "risk, rollback, and validation for the controlled remediation."
                ),
                {
                    "records": [
                        ritm.model_dump(mode="json"),
                        change.model_dump(mode="json"),
                    ],
                    "itsm_twin": session.itsm_twin.model_dump(mode="json"),
                },
            )

        session.policy_checks = policy_check(session.plan, enforce_approval=False)
        await self._emit(
            session,
            "policy.checked",
            "Policy gate passed with approval hold",
            "Policy allows planning but requires human approval before mock execution.",
            {"checks": [check.model_dump(mode="json") for check in session.policy_checks]},
        )

        non_approval_blockers = [
            check
            for check in session.policy_checks
            if check.status == "blocked" and check.name != "Human approval"
        ]
        if non_approval_blockers:
            session.status = "blocked"
            await self._emit(
                session,
                "policy.blocked",
                "Policy blocked remediation",
                "The remediation plan failed safety checks.",
                {"checks": [check.model_dump(mode="json") for check in session.policy_checks]},
            )
            return

        session.approval_summary = await self.openai_client.create_approval_summary(
            session.plan, session.policy_checks
        )
        self._capture_ai_usage(session)
        await self._emit_openai_notice_if_needed(session)
        await self._emit(
            session,
            "approval.summary",
            "OpenAI approval package structured"
            if self.openai_client.last_response_source == "openai"
            else "Approval package structured",
            session.approval_summary.operator_message,
            self._ai_payload(session, session.approval_summary.model_dump(mode="json")),
        )

        session.status = "waiting_approval"
        await self._emit(
            session,
            "approval.requested",
            "Human approval required",
            "Operator review is required before mock remediation can continue.",
            {
                "plan": session.plan.model_dump(mode="json"),
                "approval_summary": session.approval_summary.model_dump(mode="json"),
            },
        )

        approved = await session.approval_future
        if not approved:
            session.status = "rejected"
            await self._emit(
                session,
                "approval.rejected",
                "Operator rejected remediation",
                "The run ended safely with no mock state change.",
                {"mock_execution_started": False},
            )
            return

        session.plan.approval_granted = True
        session.policy_checks = policy_check(session.plan, enforce_approval=True)
        await self._emit(
            session,
            "approval.granted",
            "Operator approved remediation",
            "Human approval was recorded and policy was rechecked.",
            {
                "approval_record": session.approval_record,
                "checks": [check.model_dump(mode="json") for check in session.policy_checks],
            },
        )

        if has_blocking_check(session.policy_checks):
            session.status = "blocked"
            await self._emit(
                session,
                "policy.blocked",
                "Policy blocked remediation",
                "The final pre-execution policy check failed.",
                {"checks": [check.model_dump(mode="json") for check in session.policy_checks]},
            )
            return

        after_state = mock_execute(session.plan, before_state)
        validation = validate_result(before_state, after_state)
        execution = after_state.get("execution", {})
        await self._emit(
            session,
            "execution.mocked",
            execution.get("title", "Mock remediation executed"),
            execution.get("message", "Validated mock remediation completed safely."),
            execution.get("payload", {"mock_only": True}),
        )

        await self._emit(
            session,
            "validation.passed" if validation.status == "pass" else "validation.failed",
            (
                "Scenario validation passed"
                if validation.status == "pass"
                else "Scenario validation failed"
            ),
            validation.message,
            validation.model_dump(mode="json"),
        )

        if validation.status != "pass":
            session.status = "escalated"
            return

        session.rca = await self.openai_client.create_rca(before_state, after_state)
        self._capture_ai_usage(session)
        await self._emit_openai_notice_if_needed(session)
        await self._emit(
            session,
            "rca.generated",
            "OpenAI RCA and audit evidence generated"
            if self.openai_client.last_response_source == "openai"
            else "RCA and audit evidence generated",
            session.rca.root_cause,
            self._ai_payload(session, session.rca.model_dump(mode="json")),
        )

        if session.itsm_twin:
            update_draft = draft_status_update(session.itsm_twin, ticket, session.rca)
            await self._emit(
                session,
                "comms.update.drafted",
                "Stakeholder update drafted",
                (
                    "A 15-minute update was generated from RCA and validation evidence "
                    "and is waiting for manual approval before simulated delivery."
                ),
                {
                    "draft": update_draft.model_dump(mode="json"),
                    "itsm_twin": session.itsm_twin.model_dump(mode="json"),
                },
            )

        session.status = "waiting_closure"
        await self._emit(
            session,
            "closure.requested",
            "Closure decision required",
            (
                "Remediation is validated. Operator can close the incident now "
                "or keep it under observation before closure."
            ),
            {
                "incident_id": ticket.incident_id,
                "options": [
                    {
                        "id": "close",
                        "label": "Approve closure",
                        "message": "Close the incident with RCA and audit evidence attached.",
                    },
                    {
                        "id": "observe",
                        "label": "Observe first",
                        "message": "Keep the incident under observation, recheck metrics, then close.",
                    },
                ],
            },
        )

        decision = await session.closure_future
        if decision == "observe":
            session.status = "observing"
            await self._emit(
                session,
                "observation.started",
                "Observation window started",
                "Synthetic observation is running before final incident closure.",
                {"duration_seconds": 60, "mock_duration_ms": 1200},
            )
            await asyncio.sleep(1.2)
            await self._emit(
                session,
                "observation.completed",
                "Observation check passed",
                "Recovery metrics remained healthy through the observation window.",
                {"validation": validation.model_dump(mode="json")},
            )

        if session.itsm_twin:
            close_incident_record(session.itsm_twin, ticket)
            closure_draft = draft_closure_update(session.itsm_twin, ticket, session.rca)
            await self._emit(
                session,
                "comms.closure.drafted",
                "Closure communication drafted",
                (
                    "A final stakeholder closure message is ready and still requires "
                    "human approval before simulated delivery."
                ),
                {
                    "draft": closure_draft.model_dump(mode="json"),
                    "itsm_twin": session.itsm_twin.model_dump(mode="json"),
                },
            )

        session.status = "closed"
        await self._emit(
            session,
            "incident.closed",
            "Incident closed",
            f"{ticket.incident_id} was closed with RCA, evidence, and validation attached.",
            {
                "incident_id": ticket.incident_id,
                "closure_code": "Resolved by approved mock remediation",
                "final_status": "closed",
                "itsm_twin": (
                    session.itsm_twin.model_dump(mode="json")
                    if session.itsm_twin
                    else None
                ),
            },
        )
        session.stream.export_jsonl(
            Path(DATA_ROOT) / "generated" / "runs" / f"{session.run_id}.events.jsonl"
        )

    async def _emit_openai_notice_if_needed(self, session: RunSession) -> None:
        if not self.openai_client.last_notice:
            return
        await self._emit(
            session,
            "openai.fallback",
            "Validated fallback response used",
            self.openai_client.last_notice,
            {"model": self.openai_client.model},
        )
        self.openai_client.last_notice = None
