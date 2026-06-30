from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from .config import env_bool, load_project_env
from .models import IncidentTicket, ServiceNowIncidentRecord, utc_now


load_project_env()


@dataclass(frozen=True)
class ServiceNowConfig:
    instance_url: str | None
    username: str | None
    password: str | None
    table: str = "incident"
    app_mode: str = "mock"
    create_incidents: bool = False
    update_incidents: bool = False
    caller_id: str | None = None
    assignment_group: str | None = None
    category: str = "inquiry"
    impact: str = "3"
    urgency: str = "3"
    resolve_on_close: bool = False
    close_state: str = "6"
    close_code: str = "Solved (Permanently)"
    close_notes: str = "NEXUS-RESOLVE closed after approved mock remediation, validation, and RCA."

    @classmethod
    def from_env(cls) -> "ServiceNowConfig":
        return cls(
            instance_url=os.getenv("SERVICENOW_INSTANCE_URL"),
            username=os.getenv("SERVICENOW_USERNAME"),
            password=os.getenv("SERVICENOW_PASSWORD"),
            table=os.getenv("SERVICENOW_TABLE", "incident"),
            app_mode=os.getenv("APP_MODE", "mock"),
            create_incidents=env_bool("SERVICENOW_CREATE_INCIDENTS", False),
            update_incidents=env_bool("SERVICENOW_UPDATE_INCIDENTS", False),
            caller_id=os.getenv("SERVICENOW_CALLER_ID") or None,
            assignment_group=os.getenv("SERVICENOW_ASSIGNMENT_GROUP") or None,
            category=os.getenv("SERVICENOW_CATEGORY", "inquiry"),
            impact=os.getenv("SERVICENOW_IMPACT", "3"),
            urgency=os.getenv("SERVICENOW_URGENCY", "3"),
            resolve_on_close=env_bool("SERVICENOW_RESOLVE_ON_CLOSE", False),
            close_state=os.getenv("SERVICENOW_CLOSE_STATE", "6"),
            close_code=os.getenv("SERVICENOW_CLOSE_CODE", "Solved (Permanently)"),
            close_notes=os.getenv(
                "SERVICENOW_CLOSE_NOTES",
                "NEXUS-RESOLVE closed after approved mock remediation, validation, and RCA.",
            ),
        )

    @property
    def configured(self) -> bool:
        return bool(self.instance_url and self.username and self.password)

    @property
    def live_mode(self) -> bool:
        return self.app_mode.lower() == "live"

    @property
    def create_enabled(self) -> bool:
        return self.configured and self.live_mode and self.create_incidents

    @property
    def update_enabled(self) -> bool:
        return self.configured and self.live_mode and self.update_incidents

    @property
    def missing(self) -> list[str]:
        missing = []
        if not self.instance_url:
            missing.append("SERVICENOW_INSTANCE_URL")
        if not self.username:
            missing.append("SERVICENOW_USERNAME")
        if not self.password:
            missing.append("SERVICENOW_PASSWORD")
        return missing


class ServiceNowWriteBackClient:
    def __init__(self, config: ServiceNowConfig | None = None) -> None:
        self.config = config or ServiceNowConfig.from_env()

    def status(self) -> dict[str, Any]:
        if self.config.create_enabled and self.config.update_enabled:
            mode = "live"
        elif self.config.configured and self.config.live_mode:
            mode = "configured_disabled"
        elif self.config.configured:
            mode = "configured_dry_run_only"
        else:
            mode = "dry_run_only"
        return {
            "connector": "servicenow-pdi-incident",
            "configured": self.config.configured,
            "mode": mode,
            "table": self.config.table,
            "missing": self.config.missing,
            "create_enabled": self.config.create_enabled,
            "update_enabled": self.config.update_enabled,
            "resolve_on_close": self.config.resolve_on_close,
            "synthetic_only": False,
            "real_execution_disabled": True,
        }

    def require_live_ready(self) -> None:
        if not self.config.live_mode:
            return
        if self.config.create_enabled and self.config.update_enabled:
            return

        status = self.status()
        missing = status.get("missing") or []
        reasons: list[str] = []
        if missing:
            reasons.append("missing " + ", ".join(missing))
        if self.config.configured and not self.config.create_incidents:
            reasons.append("SERVICENOW_CREATE_INCIDENTS must be true")
        if self.config.configured and not self.config.update_incidents:
            reasons.append("SERVICENOW_UPDATE_INCIDENTS must be true")
        detail = "; ".join(reasons) or f"connector mode is {status['mode']}"
        raise RuntimeError(
            "Real ServiceNow PDI live mode is required before starting a live run: "
            f"{detail}."
        )

    def create_incident(self, ticket: IncidentTicket, run_id: str) -> dict[str, Any]:
        request = self.preview_create_payload(ticket, run_id)
        if not self.config.configured:
            return {
                "sent": False,
                "mode": "not_configured",
                "missing": self.config.missing,
                "request": request,
                "incident": ServiceNowIncidentRecord(
                    mode="not_configured",
                    configured=False,
                    table=self.config.table,
                    synthetic_incident_id=ticket.incident_id,
                    missing=self.config.missing,
                ).model_dump(mode="json"),
            }
        if not self.config.live_mode or not self.config.create_incidents:
            reason = (
                "APP_MODE must be live"
                if not self.config.live_mode
                else "SERVICENOW_CREATE_INCIDENTS must be true"
            )
            return {
                "sent": False,
                "mode": "dry_run",
                "reason": reason,
                "request": request,
                "incident": ServiceNowIncidentRecord(
                    mode="dry_run",
                    configured=True,
                    table=self.config.table,
                    synthetic_incident_id=ticket.incident_id,
                ).model_dump(mode="json"),
            }

        response = httpx.post(
            self._table_url(self.config.table),
            auth=(self.config.username or "", self.config.password or ""),
            json=request["body"],
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        result = response.json().get("result", {})
        number = _optional_str(result.get("number"))
        sys_id = _optional_str(result.get("sys_id"))
        if not number or not sys_id:
            raise RuntimeError(
                "ServiceNow incident create response did not include both number and sys_id."
            )
        record = ServiceNowIncidentRecord(
            number=number,
            sys_id=sys_id,
            url=self._record_url(sys_id),
            table=self.config.table,
            mode="live",
            configured=True,
            synthetic_incident_id=ticket.incident_id,
            created_at=utc_now(),
            updated_at=utc_now(),
            last_update_status="created",
            state=_optional_str(result.get("state")),
        )
        return {
            "sent": True,
            "mode": "live",
            "request": request,
            "incident": record.model_dump(mode="json"),
            "servicenow": response.json(),
        }

    def preview_create_payload(self, ticket: IncidentTicket, run_id: str) -> dict[str, Any]:
        body = {
            "short_description": f"NEXUS-RESOLVE: {ticket.title}",
            "description": "\n".join(
                [
                    "NEXUS-RESOLVE live demo incident created from a synthetic alert.",
                    f"Run ID: {run_id}",
                    f"Synthetic source incident: {ticket.incident_id}",
                    f"Team: {ticket.team}",
                    f"Business service: {ticket.business_service}",
                    f"Affected CI: {ticket.affected_ci}",
                    f"Current state: {ticket.current_state}",
                    f"Requested outcome: {ticket.requested_outcome}",
                    "Safety: remediation execution remains mock-only; this record receives evidence work notes.",
                ]
            ),
            "category": self.config.category,
            "impact": self.config.impact,
            "urgency": self.config.urgency,
            "correlation_id": run_id,
            "correlation_display": "NEXUS-RESOLVE",
            "work_notes": (
                "NEXUS-RESOLVE started a live, policy-gated investigation. "
                f"Run {run_id} maps synthetic alert {ticket.incident_id} to this PDI incident."
            ),
        }
        if self.config.caller_id:
            body["caller_id"] = self.config.caller_id
        if self.config.assignment_group:
            body["assignment_group"] = self.config.assignment_group
        return {
            "connector": "servicenow-pdi-incident",
            "configured": self.config.configured,
            "table": self.config.table,
            "synthetic_incident_id": ticket.incident_id,
            "body": body,
        }

    def append_work_note(
        self,
        incident: ServiceNowIncidentRecord | dict[str, Any] | None,
        note: str,
        *,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = _record_from_any(incident)
        payload = self.preview_update_payload(record, note, fields=fields)
        if record is None:
            return {"sent": False, "mode": "no_incident", "request": payload}
        if not self.config.configured:
            return {
                "sent": False,
                "mode": "not_configured",
                "missing": self.config.missing,
                "request": payload,
            }
        if not self.config.live_mode or not self.config.update_incidents:
            reason = (
                "APP_MODE must be live"
                if not self.config.live_mode
                else "SERVICENOW_UPDATE_INCIDENTS must be true"
            )
            return {
                "sent": False,
                "mode": "dry_run",
                "reason": reason,
                "request": payload,
            }
        if not record.sys_id:
            return {"sent": False, "mode": "missing_sys_id", "request": payload}

        response = httpx.patch(
            self._table_url(f"{record.table or self.config.table}/{record.sys_id}"),
            auth=(self.config.username or "", self.config.password or ""),
            json=payload["body"],
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        return {
            "sent": True,
            "mode": "live",
            "request": payload,
            "servicenow": response.json(),
        }

    def fields_for_event(
        self, event_type: str, run_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if event_type != "incident.closed" or not self.config.resolve_on_close:
            return None
        close_notes = "\n".join(
            [
                self.config.close_notes,
                f"Run: {run_id}",
                f"Closure: {payload.get('closure_code', 'closed by NEXUS-RESOLVE')}",
            ]
        )
        return {
            "state": self.config.close_state,
            "close_code": self.config.close_code,
            "close_notes": close_notes,
        }

    def get_incident(self, incident_number: str) -> dict[str, Any]:
        if not self.config.configured:
            return {
                "found": False,
                "mode": "not_configured",
                "missing": self.config.missing,
                "incident_number": incident_number,
            }

        response = httpx.get(
            self._table_url(self.config.table),
            auth=(self.config.username or "", self.config.password or ""),
            params={
                "sysparm_query": f"number={incident_number}",
                "sysparm_limit": "1",
                "sysparm_fields": (
                    "sys_id,number,state,short_description,priority,impact,urgency,"
                    "assignment_group,caller_id,opened_at,closed_at,close_code,"
                    "close_notes,correlation_id,correlation_display,sys_updated_on"
                ),
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json().get("result", [])
        if not rows:
            return {
                "found": False,
                "mode": "live",
                "incident_number": incident_number,
                "table": self.config.table,
            }
        row = rows[0]
        sys_id = _optional_str(row.get("sys_id"))
        return {
            "found": True,
            "mode": "live",
            "table": self.config.table,
            "incident": {
                **row,
                "url": self._record_url(sys_id),
            },
        }

    def preview_update_payload(
        self,
        incident: ServiceNowIncidentRecord | None,
        note: str,
        *,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = {"work_notes": note}
        if fields:
            body.update({key: value for key, value in fields.items() if value not in (None, "")})
        return {
            "connector": "servicenow-pdi-work-note",
            "configured": self.config.configured,
            "table": incident.table if incident else self.config.table,
            "incident_number": incident.number if incident else None,
            "sys_id": incident.sys_id if incident else None,
            "synthetic_incident_id": incident.synthetic_incident_id if incident else None,
            "synthetic_only": False,
            "real_execution_disabled": True,
            "body": body,
        }

    def build_work_note(self, audit_packet: dict[str, Any]) -> str:
        packet = audit_packet["packet"]
        events = packet.get("events", [])
        rca = packet.get("rca") or {}
        plan = packet.get("plan") or {}
        approval = packet.get("approval_record") or {}
        telemetry = packet.get("ai_telemetry") or {}
        servicenow_incident = packet.get("servicenow_incident") or {}
        return "\n".join(
            [
                "NEXUS-RESOLVE remediation evidence",
                f"Run: {audit_packet['run_id']}",
                f"Status: {packet.get('status', 'unknown')}",
                f"ServiceNow: {servicenow_incident.get('number') or 'not attached'}",
                f"Audit hash: {audit_packet.get('audit_hash', 'pending')}",
                "Safety: mock_only=true, real_execution_disabled=true",
                f"Plan: {plan.get('summary', 'not generated')}",
                f"RCA: {rca.get('root_cause', 'not generated')}",
                f"Approval: {approval.get('operator', 'not approved')} / {approval.get('role', 'not approved')}",
                f"AI: {telemetry.get('openai_calls', 0)} OpenAI calls, {telemetry.get('fallback_calls', 0)} fallback calls, {telemetry.get('total_tool_calls', 0)} tool calls",
                f"Events: {len(events)} ordered audit events",
            ]
        )

    def preview_payload(
        self, audit_packet: dict[str, Any], incident_number: str | None = None
    ) -> dict[str, Any]:
        packet = audit_packet["packet"]
        record = _record_from_any(packet.get("servicenow_incident"))
        resolved_incident = incident_number or (record.number if record else None)
        if record is None and resolved_incident:
            record = ServiceNowIncidentRecord(
                number=resolved_incident,
                table=self.config.table,
                mode="live" if self.config.configured else "dry_run",
                configured=self.config.configured,
            )
        if record is None:
            synthetic_number = self._incident_number(packet)
            record = ServiceNowIncidentRecord(
                number=resolved_incident,
                table=self.config.table,
                mode="dry_run",
                configured=self.config.configured,
                synthetic_incident_id=synthetic_number,
            )
        return self.preview_update_payload(record, self.build_work_note(audit_packet))

    def write_work_note(
        self,
        audit_packet: dict[str, Any],
        *,
        incident_number: str | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        packet = audit_packet["packet"]
        record = _record_from_any(packet.get("servicenow_incident"))
        if incident_number:
            record = ServiceNowIncidentRecord(
                number=incident_number,
                table=self.config.table,
                mode="live" if self.config.configured else "dry_run",
                configured=self.config.configured,
            )
        payload = self.preview_payload(audit_packet, incident_number)
        if dry_run:
            return {"sent": False, "mode": "dry_run", "request": payload}
        if not self.config.configured:
            return {
                "sent": False,
                "mode": "not_configured",
                "missing": self.config.missing,
                "request": payload,
            }
        if not self.config.live_mode or not self.config.update_incidents:
            return {
                "sent": False,
                "mode": "dry_run",
                "reason": "APP_MODE=live and SERVICENOW_UPDATE_INCIDENTS=true are required.",
                "request": payload,
            }
        if record is None or not record.sys_id:
            if not payload.get("incident_number"):
                return {"sent": False, "mode": "missing_incident", "request": payload}
            sys_id = self._lookup_incident_sys_id(str(payload["incident_number"]))
            record = ServiceNowIncidentRecord(
                number=str(payload["incident_number"]),
                sys_id=sys_id,
                table=self.config.table,
                mode="live",
                configured=True,
            )
        return self.append_work_note(record, payload["body"]["work_notes"])

    def _lookup_incident_sys_id(self, incident_number: str) -> str:
        response = httpx.get(
            self._table_url(self.config.table),
            auth=(self.config.username or "", self.config.password or ""),
            params={
                "sysparm_query": f"number={incident_number}",
                "sysparm_limit": "1",
                "sysparm_fields": "sys_id,number",
            },
            headers={"Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json().get("result", [])
        if not rows:
            raise LookupError(f"ServiceNow incident not found: {incident_number}")
        return str(rows[0]["sys_id"])

    def _table_url(self, suffix: str) -> str:
        base = (self.config.instance_url or "").rstrip("/") + "/"
        return urljoin(base, f"api/now/table/{suffix.lstrip('/')}")

    def _record_url(self, sys_id: str | None) -> str | None:
        if not sys_id or not self.config.instance_url:
            return None
        base = (self.config.instance_url or "").rstrip("/")
        return f"{base}/nav_to.do?uri={self.config.table}.do?sys_id={sys_id}"

    @staticmethod
    def _incident_number(snapshot: dict[str, Any]) -> str | None:
        for event in snapshot.get("events", []):
            payload = event.get("payload") or {}
            if payload.get("incident_id"):
                return str(payload["incident_id"])
        return None


def _record_from_any(
    value: ServiceNowIncidentRecord | dict[str, Any] | None,
) -> ServiceNowIncidentRecord | None:
    if value is None:
        return None
    if isinstance(value, ServiceNowIncidentRecord):
        return value
    return ServiceNowIncidentRecord.model_validate(value)


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
