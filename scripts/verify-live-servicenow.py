from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "services" / "backend"
sys.path.insert(0, str(BACKEND))

from app.models import ServiceNowIncidentRecord, new_run_id  # noqa: E402
from app.servicenow import ServiceNowConfig, ServiceNowWriteBackClient  # noqa: E402
from app.tools import get_default_incident  # noqa: E402


def main() -> int:
    config = ServiceNowConfig.from_env()
    status = ServiceNowWriteBackClient(config).status()
    if not config.configured:
        print("ServiceNow PDI is not configured.")
        print("Missing: " + ", ".join(config.missing))
        print("Run scripts\\configure-live-servicenow.cmd first.")
        return 2
    if not config.live_mode:
        print("APP_MODE must be live.")
        return 2
    if not config.create_incidents or not config.update_incidents:
        print("SERVICENOW_CREATE_INCIDENTS and SERVICENOW_UPDATE_INCIDENTS must both be true.")
        return 2
    if status["mode"] != "live":
        print(f"ServiceNow connector is not live. Mode: {status['mode']}")
        return 2

    client = ServiceNowWriteBackClient(config)
    run_id = new_run_id()
    ticket = get_default_incident().model_copy(
        update={
            "incident_id": f"PREFLIGHT-{run_id}",
            "title": "NEXUS-RESOLVE ServiceNow PDI preflight",
            "requested_outcome": "Verify real PDI incident create and work-note update.",
        }
    )

    print("Creating a real ServiceNow PDI incident for preflight verification...")
    create_result = client.create_incident(ticket, run_id)
    if not create_result.get("sent"):
        print(f"Create did not run. Mode: {create_result.get('mode')}")
        print(create_result.get("reason") or create_result.get("missing") or "No reason returned.")
        return 1

    incident = ServiceNowIncidentRecord.model_validate(create_result["incident"])
    if not incident.number:
        print("Create response did not include a real ServiceNow incident number.")
        return 1
    print(f"Created: {incident.number}")
    if incident.url:
        print(f"URL: {incident.url}")

    print("Appending a ServiceNow work note to the same incident...")
    note = "\n".join(
        [
            "NEXUS-RESOLVE ServiceNow PDI preflight update succeeded.",
            f"Run: {run_id}",
            "This verifies create and update permissions before the live demo.",
        ]
    )
    update_result = client.append_work_note(incident, note)
    if not update_result.get("sent"):
        print(f"Update did not run. Mode: {update_result.get('mode')}")
        print(update_result.get("reason") or update_result.get("missing") or "No reason returned.")
        return 1

    print("Looking up the same ServiceNow incident by real incident number...")
    lookup_result = client.get_incident(incident.number)
    if not lookup_result.get("found"):
        print(f"Lookup did not find the created incident. Mode: {lookup_result.get('mode')}")
        return 1

    print("ServiceNow PDI verification passed.")
    print(f"Incident: {incident.number}")
    if incident.url:
        print(f"Open later: {incident.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
