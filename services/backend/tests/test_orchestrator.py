import asyncio
from types import SimpleNamespace

import pytest

from app import servicenow_history
from app.openai_client import NexusOpenAIClient
from app.orchestrator import RunManager, ServiceNowIncidentCreateError
from app.tools import get_default_incident, get_incident_for_scenario, get_scenario_summaries


async def wait_for_status(session, status: str, timeout: float = 2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if session.status == status:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Timed out waiting for status {status}; saw {session.status}")


def test_golden_disk_flow_completes_after_approval():
    async def scenario():
        manager = RunManager(openai_client=NexusOpenAIClient(mode="mock"))
        session = await manager.start_run(get_default_incident())
        await wait_for_status(session, "waiting_approval")

        manager.approve(session.run_id)
        await wait_for_status(session, "waiting_closure")
        manager.close_incident(session.run_id)
        await wait_for_status(session, "closed")

        events = session.stream.events
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert any(event.type == "policy.warning" for event in events)
        assert any(event.type == "evidence.summary" for event in events)
        assert any(event.type == "approval.summary" for event in events)
        assert any(event.type == "approval.requested" for event in events)
        assert any(event.type == "execution.mocked" for event in events)
        assert any(event.type == "rca.generated" for event in events)
        assert any(event.type == "closure.requested" for event in events)
        assert any(event.type == "incident.closed" for event in events)
        assert session.itsm_twin is not None
        assert {record.record_type for record in session.itsm_twin.records} == {
            "incident",
            "problem",
            "ritm",
            "change",
        }
        assert any(draft.channel == "teams_bridge" for draft in session.itsm_twin.comms)
        assert session.evidence_summary is not None
        assert session.approval_summary is not None
        assert session.approval_record is not None
        assert session.approval_record["operator"] == "Demo Operator"
        assert session.rca is not None
        assert session.rca.metrics["Audit Completeness"] == "100%"
        assert session.ai_usage_records
        assert session.ai_telemetry_summary().calls == 4
        assert session.ai_telemetry_summary().estimated_human_cost_usd == 22.5
        rca_event = next(event for event in events if event.type == "rca.generated")
        assert rca_event.payload["ai_telemetry"]["calls"] == 4

    asyncio.run(scenario())


def test_local_itsm_comms_require_manual_approval_before_simulated_send():
    async def scenario():
        manager = RunManager(openai_client=NexusOpenAIClient(mode="mock"))
        session = await manager.start_run(
            get_incident_for_scenario("command-centre-alert-storm")
        )
        await wait_for_status(session, "waiting_approval")

        assert session.itsm_twin is not None
        bridge = next(
            draft for draft in session.itsm_twin.comms if draft.id == "teams-bridge"
        )
        assert bridge.status == "pending_approval"
        assert bridge.sent_at is None

        snapshot = await manager.approve_comms(
            session.run_id,
            "teams-bridge",
            {"operator": "Comms Lead", "role": "Incident Commander"},
        )

        sent_bridge = next(
            draft for draft in snapshot.itsm_twin.comms if draft.id == "teams-bridge"
        )
        assert sent_bridge.status == "sent"
        assert sent_bridge.approved_by == "Comms Lead / Incident Commander"
        assert sent_bridge.simulated_delivery["external_side_effects"] == "disabled"
        assert any(event.type == "comms.sent" for event in session.stream.events)

    asyncio.run(scenario())


def test_local_itsm_records_receive_event_backed_work_notes():
    async def scenario():
        manager = RunManager(openai_client=NexusOpenAIClient(mode="mock"))
        session = await manager.start_run(get_default_incident())
        await wait_for_status(session, "waiting_approval")

        assert session.itsm_twin is not None
        incident = next(
            record for record in session.itsm_twin.records if record.id == "incident-primary"
        )
        problem = next(
            record
            for record in session.itsm_twin.records
            if record.id == "problem-repeat-driver"
        )
        ritm = next(
            record
            for record in session.itsm_twin.records
            if record.id == "ritm-approval-evidence"
        )
        change = next(
            record
            for record in session.itsm_twin.records
            if record.id == "change-remediation-plan"
        )

        incident_events = {note.source_event for note in incident.work_notes}
        problem_events = {note.source_event for note in problem.work_notes}
        ritm_events = {note.source_event for note in ritm.work_notes}
        change_events = {note.source_event for note in change.work_notes}

        assert "ticket.received" in incident_events
        assert "evidence.sop" in incident_events
        assert "itsm.problem.created" in problem_events
        assert "approval.requested" in ritm_events
        assert "plan.generated" in change_events

        manager.approve(session.run_id)
        await wait_for_status(session, "waiting_closure")
        manager.close_incident(session.run_id)
        await wait_for_status(session, "closed")

        incident_events = {note.source_event for note in incident.work_notes}
        change_events = {note.source_event for note in change.work_notes}
        assert "incident.closed" in incident_events
        assert "validation.passed" in change_events
        assert sum(len(record.work_notes) for record in session.itsm_twin.records) >= 18

    asyncio.run(scenario())


def test_major_incident_comms_are_locked_for_non_p1_p2_incidents():
    async def scenario():
        manager = RunManager(openai_client=NexusOpenAIClient(mode="mock"))
        session = await manager.start_run(get_default_incident())
        await wait_for_status(session, "waiting_approval")

        with pytest.raises(ValueError, match="enabled only for P1/P2"):
            await manager.approve_comms(
                session.run_id,
                "teams-bridge",
                {"operator": "Comms Lead", "role": "Incident Commander"},
            )

        bridge = next(
            draft for draft in session.itsm_twin.comms if draft.id == "teams-bridge"
        )
        assert bridge.status == "pending_approval"
        assert not any(event.type == "comms.sent" for event in session.stream.events)

    asyncio.run(scenario())


def test_all_catalog_scenarios_complete_after_approval():
    async def scenario():
        manager = RunManager(openai_client=NexusOpenAIClient(mode="mock"))
        for summary in get_scenario_summaries():
            session = await manager.start_run(
                get_incident_for_scenario(summary["scenario_id"])
            )
            await wait_for_status(session, "waiting_approval")

            manager.approve(session.run_id)
            await wait_for_status(session, "waiting_closure")
            manager.close_incident(session.run_id)
            await wait_for_status(session, "closed")

            event_types = {event.type for event in session.stream.events}
            assert {
                "ticket.received",
                "evidence.sop",
                "evidence.history",
                "policy.warning",
                "plan.generated",
                "approval.requested",
                "execution.mocked",
                "validation.passed",
                "rca.generated",
                "closure.requested",
                "incident.closed",
            } <= event_types

    asyncio.run(scenario())


def test_observation_path_rechecks_then_closes():
    async def scenario():
        manager = RunManager(openai_client=NexusOpenAIClient(mode="mock"))
        session = await manager.start_run(get_default_incident())
        await wait_for_status(session, "waiting_approval")

        manager.approve(session.run_id)
        await wait_for_status(session, "waiting_closure")
        manager.observe_incident(session.run_id)
        await wait_for_status(session, "closed", timeout=3.0)

        event_types = {event.type for event in session.stream.events}
        assert "observation.started" in event_types
        assert "observation.completed" in event_types
        assert "incident.closed" in event_types

    asyncio.run(scenario())


def test_rejection_ends_run_safely():
    async def scenario():
        manager = RunManager(openai_client=NexusOpenAIClient(mode="mock"))
        session = await manager.start_run(get_default_incident())
        await wait_for_status(session, "waiting_approval")

        manager.reject(session.run_id)
        await wait_for_status(session, "rejected")

        assert any(event.type == "approval.rejected" for event in session.stream.events)
        assert not any(event.type == "execution.mocked" for event in session.stream.events)

    asyncio.run(scenario())


def test_live_servicenow_incident_is_created_updated_and_persisted_for_run(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        servicenow_history,
        "HISTORY_PATH",
        tmp_path / "servicenow_incidents.jsonl",
    )

    class FakeServiceNowClient:
        def __init__(self):
            self.config = SimpleNamespace(
                table="incident",
                live_mode=True,
                create_enabled=True,
                update_enabled=True,
            )
            self.created = []
            self.notes = []

        def create_incident(self, ticket, run_id):
            self.created.append((ticket.incident_id, run_id))
            return {
                "sent": True,
                "mode": "live",
                "incident": {
                    "number": "INC0010001",
                    "sys_id": "sys-123",
                    "url": "https://dev123.service-now.com/nav_to.do?uri=incident.do?sys_id=sys-123",
                    "table": "incident",
                    "mode": "live",
                    "configured": True,
                    "synthetic_incident_id": ticket.incident_id,
                    "missing": [],
                },
            }

        def append_work_note(self, incident, note, *, fields=None):
            self.notes.append((incident.number, note, fields))
            return {"sent": True, "mode": "live"}

        def fields_for_event(self, event_type, run_id, payload):
            if event_type != "incident.closed":
                return None
            return {
                "state": "6",
                "close_code": "Solved (Permanently)",
                "close_notes": f"Closed by {run_id}",
            }

    async def scenario():
        servicenow = FakeServiceNowClient()
        manager = RunManager(
            openai_client=NexusOpenAIClient(mode="mock"),
            servicenow_client=servicenow,
        )
        session = await manager.start_run(get_default_incident())

        assert session.servicenow_incident.number == "INC0010001"
        assert servicenow.created == [("INC-2026-00421", session.run_id)]

        await wait_for_status(session, "waiting_approval")
        manager.approve(session.run_id)
        await wait_for_status(session, "waiting_closure")
        manager.close_incident(session.run_id)
        await wait_for_status(session, "closed")

        event_types = {event.type for event in session.stream.events}
        assert "servicenow.incident.created" in event_types
        assert "servicenow.work_note.updated" in event_types
        assert any("Event: plan.generated" in note for _, note, _ in servicenow.notes)
        assert any("Event: incident.closed" in note for _, note, _ in servicenow.notes)
        assert any(fields and fields["state"] == "6" for _, _, fields in servicenow.notes)
        assert session.snapshot().servicenow_incident.number == "INC0010001"
        history = servicenow_history.load_servicenow_incident_history()
        assert history[0]["run_id"] == session.run_id
        assert history[0]["number"] == "INC0010001"
        assert history[0]["status"] == "updated"
        assert history[0]["last_update_status"] == "work_note:incident.closed"
        assert history[0]["state"] == "6"

    asyncio.run(scenario())


def test_live_servicenow_create_failure_blocks_run():
    class FailingServiceNowClient:
        def __init__(self):
            self.config = SimpleNamespace(
                table="incident",
                live_mode=True,
                create_enabled=True,
                update_enabled=True,
            )

        def create_incident(self, ticket, run_id):
            raise RuntimeError("PDI rejected the credentials.")

    async def scenario():
        manager = RunManager(
            openai_client=NexusOpenAIClient(mode="mock"),
            servicenow_client=FailingServiceNowClient(),
        )

        with pytest.raises(ServiceNowIncidentCreateError, match="not created"):
            await manager.start_run(get_default_incident())

        assert manager.sessions == {}

    asyncio.run(scenario())
