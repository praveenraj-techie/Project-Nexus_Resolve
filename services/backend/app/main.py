from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audit_export import (
    build_audit_packet,
    build_audit_pdf,
    load_persisted_audit_packet,
    load_persisted_run_snapshot,
)
from .models import IncidentTicket, utc_now
from .orchestrator import RunManager, ServiceNowIncidentCreateError
from .policy import policy_check
from .models import RemediationPlan
from .scenario_catalog import get_replay_path
from .servicenow import ServiceNowWriteBackClient
from .servicenow_history import load_servicenow_incident_history
from .tools import get_incident_for_scenario, get_scenario_summaries


class IncidentStartRequest(BaseModel):
    scenario_id: str = "disk-space"
    ticket: IncidentTicket | None = None


class ApprovalRequest(BaseModel):
    operator: str = "Demo Operator"
    role: str = "Incident Approver"
    reason: str = "Approved mock-only remediation after policy review."


class ServiceNowWriteBackRequest(BaseModel):
    dry_run: bool = True
    incident_number: str | None = None


class CommsApprovalRequest(BaseModel):
    operator: str = "Demo Operator"
    role: str = "Incident Commander"
    reason: str = "Approved after manual communications review."


class CommsRejectionRequest(BaseModel):
    operator: str = "Demo Operator"
    reason: str = "Rejected during manual communications review."


app = FastAPI(title="NEXUS-RESOLVE API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = RunManager(event_delay_seconds=1.4)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nexus-resolve"}


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": get_scenario_summaries()}


@app.get("/api/connectors/servicenow/mock-ticket/{scenario_id}")
def servicenow_mock_ticket(scenario_id: str):
    try:
        ticket = get_incident_for_scenario(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scenario not found") from None
    return {
        "connector": "servicenow-mock",
        "synthetic_only": True,
        "record": {
            "number": ticket.incident_id,
            "short_description": ticket.title,
            "priority": ticket.priority,
            "assignment_group": ticket.team,
            "cmdb_ci": ticket.affected_ci,
            "business_service": ticket.business_service,
            "state": "New",
            "requested_outcome": ticket.requested_outcome,
        },
    }


@app.get("/api/connectors/servicenow/status")
def servicenow_status():
    return ServiceNowWriteBackClient().status()


@app.get("/api/connectors/servicenow/incidents")
def servicenow_incidents(limit: int = 20):
    return {"incidents": load_servicenow_incident_history(limit)}


@app.get("/api/connectors/servicenow/incidents/{incident_number}")
def servicenow_incident_lookup(incident_number: str):
    try:
        return ServiceNowWriteBackClient().get_incident(incident_number)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/incidents")
async def create_incident(request: IncidentStartRequest | None = None) -> dict[str, object]:
    request = request or IncidentStartRequest()
    try:
        ticket = request.ticket or get_incident_for_scenario(request.scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scenario not found") from None
    try:
        manager.servicenow_client.require_live_ready()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        session = await manager.start_run(ticket, scenario_id=ticket.scenario_id)
    except ServiceNowIncidentCreateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "run_id": session.run_id,
        "status": session.status,
        "servicenow_incident": (
            session.servicenow_incident.model_dump(mode="json")
            if session.servicenow_incident
            else None
        ),
    }


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    session = manager.get_session(run_id)
    if not session:
        persisted = load_persisted_run_snapshot(run_id)
        if persisted is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return persisted
    return session.snapshot()


@app.get("/api/runs/{run_id}/itsm-twin")
def get_itsm_twin(run_id: str):
    session = manager.get_session(run_id)
    if not session:
        persisted = load_persisted_run_snapshot(run_id)
        if persisted is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return persisted.get("itsm_twin") or {
            "mode": "local_itsm_simulator",
            "run_id": run_id,
            "records": [],
            "comms": [],
            "audit_notes": ["Persisted run has no ITSM Twin state."],
        }
    if not session.itsm_twin:
        raise HTTPException(status_code=404, detail="ITSM Twin not found")
    return session.itsm_twin


@app.get("/api/local-snow/runs")
def local_snow_runs():
    sessions = list(manager.sessions.values())
    return {
        "connector": "local-snow-desk",
        "synthetic_only": True,
        "external_side_effects": "disabled",
        "runs": [_local_snow_summary(session) for session in reversed(sessions)],
    }


@app.get("/api/local-snow/latest")
def local_snow_latest():
    sessions = list(manager.sessions.values())
    if not sessions:
        raise HTTPException(status_code=404, detail="No active NEXUS run yet.")
    return _local_snow_payload(sessions[-1])


@app.get("/api/local-snow/runs/{run_id}")
def local_snow_run(run_id: str):
    session = manager.get_session(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Run not found")
    return _local_snow_payload(session)


@app.post("/api/runs/{run_id}/approve")
def approve_run(run_id: str, request: ApprovalRequest | None = None):
    try:
        approval = request or ApprovalRequest()
        return manager.approve(
            run_id,
            {
                **approval.model_dump(),
                "recorded_at": utc_now().isoformat(),
            },
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/api/runs/{run_id}/reject")
def reject_run(run_id: str):
    try:
        return manager.reject(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/api/runs/{run_id}/comms/{draft_id}/approve")
async def approve_comms_draft(
    run_id: str,
    draft_id: str,
    request: CommsApprovalRequest | None = None,
):
    try:
        approval = request or CommsApprovalRequest()
        snapshot = await manager.approve_comms(
            run_id,
            draft_id,
            {
                **approval.model_dump(),
                "recorded_at": utc_now().isoformat(),
            },
        )
        return snapshot.itsm_twin
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/comms/{draft_id}/reject")
async def reject_comms_draft(
    run_id: str,
    draft_id: str,
    request: CommsRejectionRequest | None = None,
):
    try:
        rejection = request or CommsRejectionRequest()
        snapshot = await manager.reject_comms(
            run_id,
            draft_id,
            {
                **rejection.model_dump(),
                "recorded_at": utc_now().isoformat(),
            },
        )
        return snapshot.itsm_twin
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/close")
def close_run(run_id: str):
    try:
        return manager.close_incident(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.post("/api/runs/{run_id}/observe")
def observe_run(run_id: str):
    try:
        return manager.observe_incident(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None


@app.get("/api/replay/{scenario_id}")
def replay_scenario(scenario_id: str):
    try:
        path = get_replay_path(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Scenario not found") from None
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {"events": events}


@app.get("/api/runs/{run_id}/audit-packet")
def audit_packet(run_id: str):
    packet = _audit_packet_for_run(run_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return packet


@app.get("/api/runs/{run_id}/audit-report.pdf")
def audit_report_pdf(run_id: str):
    packet = _audit_packet_for_run(run_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Run not found")

    pdf_bytes = build_audit_pdf(packet)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="nexus-resolve-{run_id}-audit.pdf"'
        },
    )


@app.post("/api/runs/{run_id}/servicenow/work-note")
def servicenow_work_note(
    run_id: str, request: ServiceNowWriteBackRequest | None = None
):
    packet = _audit_packet_for_run(run_id)
    if packet is None:
        raise HTTPException(status_code=404, detail="Run not found")

    write_request = request or ServiceNowWriteBackRequest()
    try:
        return ServiceNowWriteBackClient().write_work_note(
            packet,
            incident_number=write_request.incident_number,
            dry_run=write_request.dry_run,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _audit_packet_for_run(run_id: str):
    session = manager.get_session(run_id)
    if session:
        return build_audit_packet(session)
    return load_persisted_audit_packet(run_id)


def _local_snow_summary(session):
    ticket = session.ticket
    last_event = session.stream.events[-1] if session.stream.events else None
    return {
        "run_id": session.run_id,
        "status": session.status,
        "incident_id": ticket.incident_id if ticket else None,
        "priority": ticket.priority if ticket else None,
        "title": ticket.title if ticket else None,
        "team": ticket.team if ticket else None,
        "business_service": ticket.business_service if ticket else None,
        "affected_ci": ticket.affected_ci if ticket else None,
        "record_count": len(session.itsm_twin.records) if session.itsm_twin else 0,
        "work_note_count": (
            sum(len(record.work_notes) for record in session.itsm_twin.records)
            if session.itsm_twin
            else 0
        ),
        "comms_count": len(session.itsm_twin.comms) if session.itsm_twin else 0,
        "last_event": last_event.type if last_event else None,
        "updated_at": last_event.timestamp if last_event else None,
    }


def _local_snow_payload(session):
    return {
        "connector": "local-snow-desk",
        "synthetic_only": True,
        "external_side_effects": "disabled",
        "run_id": session.run_id,
        "status": session.status,
        "ticket": session.ticket.model_dump(mode="json") if session.ticket else None,
        "servicenow_incident": (
            session.servicenow_incident.model_dump(mode="json")
            if session.servicenow_incident
            else None
        ),
        "itsm_twin": (
            session.itsm_twin.model_dump(mode="json") if session.itsm_twin else None
        ),
        "events": [event.model_dump(mode="json") for event in session.stream.events],
        "ai_telemetry": session.ai_telemetry_summary().model_dump(mode="json"),
    }


@app.get("/api/policy/demo-block")
def policy_demo_block():
    unsafe_plan = RemediationPlan(
        summary="Unsafe protected-resource cleanup demo.",
        target_resources=["C:\\Windows\\System32"],
        action_preview="Remove-Item 'C:\\Windows\\System32\\*.log' -Recurse -Force",
        estimated_effect="Unknown effect.",
        safeguards=[],
        approval_required=False,
        uses_dry_run=False,
        mock_only=False,
        validation_steps=[],
    )
    return {"checks": policy_check(unsafe_plan, enforce_approval=True)}


@app.websocket("/ws/runs/{run_id}")
async def run_websocket(websocket: WebSocket, run_id: str):
    await websocket.accept()
    session = manager.get_session(run_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Run not found"})
        await websocket.close(code=1008)
        return

    queue = session.stream.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        session.stream.unsubscribe(queue)
