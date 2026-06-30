from __future__ import annotations

import httpx
import pytest

from app.models import ServiceNowIncidentRecord
from app.servicenow import ServiceNowConfig, ServiceNowWriteBackClient
from app.tools import get_default_incident


def test_create_incident_posts_to_servicenow_table_api(monkeypatch):
    captured = {}

    def fake_post(url, auth, json, headers, timeout):
        captured.update(
            {
                "url": url,
                "auth": auth,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return httpx.Response(
            201,
            json={"result": {"number": "INC0010001", "sys_id": "sys-123", "state": "1"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.servicenow.httpx.post", fake_post)
    client = ServiceNowWriteBackClient(
        ServiceNowConfig(
            instance_url="https://dev123.service-now.com",
            username="admin",
            password="secret",
            app_mode="live",
            create_incidents=True,
            update_incidents=True,
        )
    )

    result = client.create_incident(get_default_incident(), "run-demo")

    assert result["sent"] is True
    assert result["incident"]["number"] == "INC0010001"
    assert result["incident"]["sys_id"] == "sys-123"
    assert captured["url"] == "https://dev123.service-now.com/api/now/table/incident"
    assert captured["auth"] == ("admin", "secret")
    assert captured["json"]["correlation_id"] == "run-demo"
    assert captured["json"]["short_description"].startswith("NEXUS-RESOLVE:")


def test_create_incident_requires_explicit_enable_flag(monkeypatch):
    def fail_post(*args, **kwargs):
        raise AssertionError("ServiceNow HTTP call should not be made")

    monkeypatch.setattr("app.servicenow.httpx.post", fail_post)
    client = ServiceNowWriteBackClient(
        ServiceNowConfig(
            instance_url="https://dev123.service-now.com",
            username="admin",
            password="secret",
            app_mode="live",
            create_incidents=False,
            update_incidents=True,
        )
    )

    result = client.create_incident(get_default_incident(), "run-demo")

    assert result["sent"] is False
    assert result["mode"] == "dry_run"
    assert "SERVICENOW_CREATE_INCIDENTS" in result["reason"]


def test_create_incident_requires_number_and_sys_id(monkeypatch):
    def fake_post(url, auth, json, headers, timeout):
        return httpx.Response(
            201,
            json={"result": {"number": "INC0010001"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.servicenow.httpx.post", fake_post)
    client = ServiceNowWriteBackClient(
        ServiceNowConfig(
            instance_url="https://dev123.service-now.com",
            username="admin",
            password="secret",
            app_mode="live",
            create_incidents=True,
            update_incidents=True,
        )
    )

    with pytest.raises(RuntimeError, match="number and sys_id"):
        client.create_incident(get_default_incident(), "run-demo")


def test_append_work_note_patches_existing_incident_sys_id(monkeypatch):
    captured = {}

    def fake_patch(url, auth, json, headers, timeout):
        captured.update(
            {
                "url": url,
                "auth": auth,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return httpx.Response(
            200,
            json={"result": {"number": "INC0010001"}},
            request=httpx.Request("PATCH", url),
        )

    monkeypatch.setattr("app.servicenow.httpx.patch", fake_patch)
    client = ServiceNowWriteBackClient(
        ServiceNowConfig(
            instance_url="https://dev123.service-now.com",
            username="admin",
            password="secret",
            app_mode="live",
            create_incidents=True,
            update_incidents=True,
        )
    )
    incident = ServiceNowIncidentRecord(
        number="INC0010001",
        sys_id="sys-123",
        table="incident",
        mode="live",
        configured=True,
    )

    result = client.append_work_note(incident, "RCA generated.")

    assert result["sent"] is True
    assert captured["url"] == "https://dev123.service-now.com/api/now/table/incident/sys-123"
    assert captured["json"] == {"work_notes": "RCA generated."}


def test_incident_closed_event_can_include_resolve_fields():
    client = ServiceNowWriteBackClient(
        ServiceNowConfig(
            instance_url="https://dev123.service-now.com",
            username="admin",
            password="secret",
            app_mode="live",
            create_incidents=True,
            update_incidents=True,
            resolve_on_close=True,
            close_state="6",
            close_code="Solved (Permanently)",
            close_notes="Closed by NEXUS-RESOLVE.",
        )
    )

    fields = client.fields_for_event(
        "incident.closed",
        "run-demo",
        {"closure_code": "Resolved by approved mock remediation"},
    )

    assert fields == {
        "state": "6",
        "close_code": "Solved (Permanently)",
        "close_notes": (
            "Closed by NEXUS-RESOLVE.\n"
            "Run: run-demo\n"
            "Closure: Resolved by approved mock remediation"
        ),
    }


def test_get_incident_queries_servicenow_by_number(monkeypatch):
    captured = {}

    def fake_get(url, auth, params, headers, timeout):
        captured.update(
            {
                "url": url,
                "auth": auth,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "number": "INC0010001",
                        "sys_id": "sys-123",
                        "state": "6",
                        "short_description": "NEXUS-RESOLVE: test",
                    }
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr("app.servicenow.httpx.get", fake_get)
    client = ServiceNowWriteBackClient(
        ServiceNowConfig(
            instance_url="https://dev123.service-now.com",
            username="admin",
            password="secret",
            app_mode="live",
            create_incidents=True,
            update_incidents=True,
        )
    )

    result = client.get_incident("INC0010001")

    assert result["found"] is True
    assert result["incident"]["number"] == "INC0010001"
    assert result["incident"]["state"] == "6"
    assert result["incident"]["url"].endswith("sys_id=sys-123")
    assert captured["url"] == "https://dev123.service-now.com/api/now/table/incident"
    assert captured["params"]["sysparm_query"] == "number=INC0010001"
