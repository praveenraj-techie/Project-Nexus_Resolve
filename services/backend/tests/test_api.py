import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import servicenow_history
from app.audit_export import _openai_cost_label
from app.main import app, manager
from app.models import ServiceNowIncidentRecord, utc_now
from app.scenario_catalog import DATA_ROOT
from app.servicenow import ServiceNowConfig, ServiceNowWriteBackClient
from app.tools import get_default_incident


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_replay_endpoint_returns_events():
    client = TestClient(app)
    response = client.get("/api/replay/disk-space")

    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) >= 10
    assert events[0]["type"] == "ticket.received"


def test_scenarios_endpoint_returns_all_catalog_items():
    client = TestClient(app)
    response = client.get("/api/scenarios")

    assert response.status_code == 200
    scenarios = response.json()["scenarios"]
    assert len(scenarios) == 12
    assert {scenario["scenario_id"] for scenario in scenarios} >= {
        "disk-space",
        "db-connection-pool",
        "cloud-vm-unhealthy",
        "endpoint-third-party-app-exception",
    }


def test_unknown_replay_scenario_returns_404():
    client = TestClient(app)
    response = client.get("/api/replay/not-a-scenario")

    assert response.status_code == 404


def test_servicenow_mock_connector_returns_synthetic_ticket_shape():
    client = TestClient(app)
    response = client.get("/api/connectors/servicenow/mock-ticket/disk-space")

    assert response.status_code == 200
    payload = response.json()
    assert payload["connector"] == "servicenow-mock"
    assert payload["synthetic_only"] is True
    assert payload["record"]["number"] == "INC-2026-00421"
    assert payload["record"]["cmdb_ci"] == "APP-WIN-042"


def test_servicenow_status_defaults_to_dry_run_only(monkeypatch):
    monkeypatch.delenv("SERVICENOW_INSTANCE_URL", raising=False)
    monkeypatch.delenv("SERVICENOW_USERNAME", raising=False)
    monkeypatch.delenv("SERVICENOW_PASSWORD", raising=False)
    client = TestClient(app)
    response = client.get("/api/connectors/servicenow/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["connector"] == "servicenow-pdi-incident"
    assert payload["configured"] is False
    assert payload["mode"] == "dry_run_only"
    assert payload["create_enabled"] is False
    assert payload["update_enabled"] is False
    assert payload["real_execution_disabled"] is True


def test_servicenow_incident_history_endpoint_returns_recent_real_records(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        servicenow_history,
        "HISTORY_PATH",
        tmp_path / "servicenow_incidents.jsonl",
    )
    ticket = get_default_incident()
    incident = ServiceNowIncidentRecord(
        number="INC0010001",
        sys_id="sys-123",
        url="https://dev123.service-now.com/nav_to.do?uri=incident.do?sys_id=sys-123",
        table="incident",
        mode="live",
        configured=True,
        synthetic_incident_id=ticket.incident_id,
        created_at=utc_now(),
        updated_at=utc_now(),
        last_update_status="work_note:incident.closed",
    )
    servicenow_history.record_servicenow_incident(
        run_id="run-history",
        ticket=ticket,
        incident=incident,
        status="updated",
    )

    client = TestClient(app)
    response = client.get("/api/connectors/servicenow/incidents")

    assert response.status_code == 200
    incidents = response.json()["incidents"]
    assert len(incidents) == 1
    assert incidents[0]["run_id"] == "run-history"
    assert incidents[0]["number"] == "INC0010001"
    assert incidents[0]["synthetic_incident_id"] == "INC-2026-00421"
    assert incidents[0]["last_update_status"] == "work_note:incident.closed"


def test_servicenow_incident_lookup_returns_not_configured(monkeypatch):
    monkeypatch.delenv("SERVICENOW_INSTANCE_URL", raising=False)
    monkeypatch.delenv("SERVICENOW_USERNAME", raising=False)
    monkeypatch.delenv("SERVICENOW_PASSWORD", raising=False)
    client = TestClient(app)
    response = client.get("/api/connectors/servicenow/incidents/INC0010001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is False
    assert payload["mode"] == "not_configured"
    assert "SERVICENOW_INSTANCE_URL" in payload["missing"]


def test_local_snow_run_endpoint_returns_current_itsm_mirror():
    client = TestClient(app)
    started = client.post("/api/incidents", json={"scenario_id": "disk-space"})
    assert started.status_code == 200
    run_id = started.json()["run_id"]

    response = client.get(f"/api/local-snow/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["connector"] == "local-snow-desk"
    assert payload["synthetic_only"] is True
    assert payload["external_side_effects"] == "disabled"
    assert payload["ticket"]["incident_id"] == "INC-2026-00421"
    assert payload["itsm_twin"]["run_id"] == run_id
    assert any(
        note.get("source_event")
        for record in payload["itsm_twin"]["records"]
        for note in record["work_notes"]
    )


def test_policy_demo_block_endpoint_shows_protected_path_block():
    client = TestClient(app)
    response = client.get("/api/policy/demo-block")

    assert response.status_code == 200
    checks = response.json()["checks"]
    assert any(
        check["name"] == "Target scope" and check["status"] == "blocked"
        for check in checks
    )


def test_audit_packet_endpoint_returns_hash_and_safety_metadata():
    client = TestClient(app)
    started = client.post("/api/incidents", json={"scenario_id": "disk-space"})
    assert started.status_code == 200

    run_id = started.json()["run_id"]
    response = client.get(f"/api/runs/{run_id}/audit-packet")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_hash"].startswith("sha256:")
    assert payload["safety"]["synthetic_only"] is True
    assert payload["packet"]["run_id"] == run_id
    assert payload["packet"]["ai_telemetry"]["human_hourly_rate_usd"] == 30.0
    assert payload["packet"]["servicenow_incident"]["mode"] == "not_configured"


def test_live_incident_start_requires_real_servicenow_configuration():
    original_client = manager.servicenow_client
    manager.servicenow_client = ServiceNowWriteBackClient(
        ServiceNowConfig(
            instance_url=None,
            username=None,
            password=None,
            app_mode="live",
            create_incidents=False,
            update_incidents=False,
        )
    )
    try:
        client = TestClient(app)
        response = client.post("/api/incidents", json={"scenario_id": "disk-space"})
    finally:
        manager.servicenow_client = original_client

    assert response.status_code == 409
    assert "Real ServiceNow PDI live mode is required" in response.json()["detail"]
    assert "SERVICENOW_INSTANCE_URL" in response.json()["detail"]


def test_live_incident_start_fails_if_servicenow_create_fails():
    class FailingServiceNowClient:
        config = SimpleNamespace(
            table="incident",
            live_mode=True,
            create_enabled=True,
            update_enabled=True,
        )

        def require_live_ready(self):
            return None

        def create_incident(self, ticket, run_id):
            raise RuntimeError("PDI rejected the credentials.")

    original_client = manager.servicenow_client
    manager.servicenow_client = FailingServiceNowClient()
    try:
        client = TestClient(app)
        response = client.post("/api/incidents", json={"scenario_id": "disk-space"})
    finally:
        manager.servicenow_client = original_client

    assert response.status_code == 502
    assert "Real ServiceNow PDI incident was not created" in response.json()["detail"]


def test_audit_report_pdf_endpoint_returns_downloadable_pdf():
    client = TestClient(app)
    started = client.post("/api/incidents", json={"scenario_id": "disk-space"})
    assert started.status_code == 200

    run_id = started.json()["run_id"]
    response = client.get(f"/api/runs/{run_id}/audit-report.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert f"nexus-resolve-{run_id}-audit.pdf" in response.headers["content-disposition"]


def test_audit_report_openai_cost_label_explains_fallback_mode():
    label = _openai_cost_label(
        {
            "estimated_openai_cost_usd": 0.0,
            "openai_calls": 0,
            "fallback_calls": 4,
        }
    )

    assert label == "$0.0000 (fallback mode; no OpenAI API charge)"


def test_servicenow_work_note_preview_has_no_external_side_effect(monkeypatch):
    monkeypatch.delenv("SERVICENOW_INSTANCE_URL", raising=False)
    monkeypatch.delenv("SERVICENOW_USERNAME", raising=False)
    monkeypatch.delenv("SERVICENOW_PASSWORD", raising=False)
    client = TestClient(app)
    started = client.post("/api/incidents", json={"scenario_id": "disk-space"})
    assert started.status_code == 200

    run_id = started.json()["run_id"]
    response = client.post(
        f"/api/runs/{run_id}/servicenow/work-note",
        json={"dry_run": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] is False
    assert payload["mode"] == "dry_run"
    assert payload["request"]["connector"] == "servicenow-pdi-work-note"
    assert payload["request"]["real_execution_disabled"] is True
    assert payload["request"]["body"]["work_notes"].startswith("NEXUS-RESOLVE")


def test_audit_exports_work_from_persisted_event_log_without_memory_session():
    client = TestClient(app)
    run_id = "run-persistedpdf"
    path = DATA_ROOT / "generated" / "runs" / f"{run_id}.events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    manager.sessions.pop(run_id, None)
    events = [
        {
            "run_id": run_id,
            "sequence": 1,
            "timestamp": "2026-06-27T00:00:00Z",
            "type": "ticket.received",
            "title": "Synthetic ticket received",
            "message": "INC-TEST received.",
            "payload": {"incident_id": "INC-TEST", "scenario_id": "disk-space"},
        },
        {
            "run_id": run_id,
            "sequence": 2,
            "timestamp": "2026-06-27T00:00:01Z",
            "type": "plan.generated",
            "title": "Plan generated",
            "message": "Use mock-only cleanup.",
            "payload": {
                "summary": "Use mock-only cleanup.",
                "target_resources": ["APP-WIN-042"],
                "action_preview": "Dry-run cleanup.",
                "estimated_effect": "Disk pressure reduced.",
                "safeguards": ["Mock only"],
                "approval_required": True,
                "approval_granted": True,
                "uses_dry_run": True,
                "mock_only": True,
                "validation_steps": ["Validate free space"],
                "escalation_condition": "Escalate if validation fails.",
            },
        },
        {
            "run_id": run_id,
            "sequence": 3,
            "timestamp": "2026-06-27T00:00:02Z",
            "type": "approval.granted",
            "title": "Approval granted",
            "message": "Approved.",
            "payload": {
                "approval_record": {
                    "operator": "QA",
                    "role": "Approver",
                    "reason": "Persistence test",
                    "recorded_at": "2026-06-27T00:00:02Z",
                },
                "checks": [],
            },
        },
        {
            "run_id": run_id,
            "sequence": 4,
            "timestamp": "2026-06-27T00:00:03Z",
            "type": "rca.generated",
            "title": "RCA generated",
            "message": "Log growth caused disk pressure.",
            "payload": {
                "root_cause": "Log growth caused disk pressure.",
                "actions_taken": ["Mock cleanup"],
                "validation": "Validation passed.",
                "business_impact": "Service stabilized.",
                "follow_up": ["Tune log rotation"],
                "metrics": {"Audit Completeness": "100%"},
            },
        },
        {
            "run_id": run_id,
            "sequence": 5,
            "timestamp": "2026-06-27T00:00:04Z",
            "type": "incident.closed",
            "title": "Incident closed",
            "message": "Closed with audit.",
            "payload": {"incident_id": "INC-TEST", "final_status": "closed"},
        },
    ]
    try:
        path.write_text(
            "\n".join(json.dumps(event) for event in events),
            encoding="utf-8",
        )

        run_response = client.get(f"/api/runs/{run_id}")
        packet_response = client.get(f"/api/runs/{run_id}/audit-packet")
        pdf_response = client.get(f"/api/runs/{run_id}/audit-report.pdf")

        assert run_response.status_code == 200
        assert run_response.json()["status"] == "closed"
        assert packet_response.status_code == 200
        assert packet_response.json()["packet"]["run_id"] == run_id
        assert pdf_response.status_code == 200
        assert pdf_response.content.startswith(b"%PDF")
    finally:
        path.unlink(missing_ok=True)


def test_security_exception_replay_proves_safe_rejection():
    client = TestClient(app)
    response = client.get("/api/replay/endpoint-third-party-app-exception")

    assert response.status_code == 200
    events = response.json()["events"]
    assert events[-1]["type"] == "approval.rejected"
    assert events[-1]["payload"]["exception_case"] is True
    assert not any(event["type"] == "execution.mocked" for event in events)
