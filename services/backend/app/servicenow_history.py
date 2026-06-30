from __future__ import annotations

import json
from typing import Any

from .models import IncidentTicket, ServiceNowIncidentRecord, utc_now
from .scenario_catalog import DATA_ROOT


HISTORY_PATH = DATA_ROOT / "generated" / "servicenow_incidents.jsonl"


def record_servicenow_incident(
    *,
    run_id: str,
    ticket: IncidentTicket | None,
    incident: ServiceNowIncidentRecord,
    status: str,
) -> None:
    if incident.mode != "live" or not incident.number:
        return

    entry = {
        "run_id": run_id,
        "recorded_at": utc_now().isoformat(),
        "status": status,
        "number": incident.number,
        "sys_id": incident.sys_id,
        "url": incident.url,
        "table": incident.table,
        "mode": incident.mode,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
        "last_update_status": incident.last_update_status,
        "state": incident.state,
        "error": incident.error,
        "scenario_id": ticket.scenario_id if ticket else None,
        "synthetic_incident_id": incident.synthetic_incident_id
        or (ticket.incident_id if ticket else None),
        "team": ticket.team if ticket else None,
        "alert_type": ticket.title if ticket else None,
        "business_service": ticket.business_service if ticket else None,
        "affected_ci": ticket.affected_ci if ticket else None,
    }
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def load_servicenow_incident_history(limit: int = 20) -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []

    bounded_limit = max(1, min(limit, 100))
    latest_by_run: dict[str, dict[str, Any]] = {}
    lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        run_id = str(entry.get("run_id") or "")
        if not run_id or run_id in latest_by_run:
            continue
        latest_by_run[run_id] = entry
        if len(latest_by_run) >= bounded_limit:
            break

    return list(latest_by_run.values())
