from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "services" / "backend"
sys.path.insert(0, str(BACKEND))

from app.openai_client import NexusOpenAIClient  # noqa: E402
from app.orchestrator import RunManager  # noqa: E402
from app.servicenow import ServiceNowWriteBackClient  # noqa: E402
from app.tools import get_default_incident  # noqa: E402
from app.models import utc_now  # noqa: E402


async def wait_for_status(session, status: str, timeout: float = 180.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if session.status == status:
            return
        if session.done_future and session.done_future.done():
            break
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {status}; saw {session.status}")


async def main() -> int:
    servicenow = ServiceNowWriteBackClient()
    try:
        servicenow.require_live_ready()
    except RuntimeError as exc:
        print(str(exc))
        print("Run scripts\\configure-live-servicenow.cmd first.")
        return 2

    openai = NexusOpenAIClient(mode="live")
    if not openai.api_key:
        print("OPENAI_API_KEY is not loaded by the backend runtime.")
        print("Run scripts\\configure-live-servicenow.cmd first.")
        return 2

    manager = RunManager(openai_client=openai, servicenow_client=servicenow)
    ticket = get_default_incident()

    print("Starting a headless live NEXUS workflow.")
    print("This creates and updates one real ServiceNow PDI incident.")
    session = await manager.start_run(ticket)

    incident = session.servicenow_incident
    if not incident or incident.mode != "live" or not incident.number:
        print("Live workflow did not attach a real ServiceNow incident.")
        return 1
    print(f"Created ServiceNow incident: {incident.number}")
    if incident.url:
        print(f"URL: {incident.url}")

    await wait_for_status(session, "waiting_approval")
    manager.approve(
        session.run_id,
        {
            "operator": "NEXUS live verifier",
            "role": "Automated demo verifier",
            "reason": "Approve mock-only remediation for ServiceNow live integration proof.",
            "recorded_at": utc_now().isoformat(),
        },
    )
    await wait_for_status(session, "waiting_closure")
    manager.close_incident(session.run_id)
    await wait_for_status(session, "closed")

    fallback_events = [
        event for event in session.stream.events if event.type == "openai.fallback"
    ]
    if fallback_events:
        print("OpenAI live verification failed: workflow used fallback response.")
        for event in fallback_events:
            print(event.message)
        return 1

    sent_updates = [
        update for update in session.servicenow_updates if update.get("sent")
    ]
    if not sent_updates:
        print("ServiceNow live verification failed: no work-note updates were sent.")
        return 1

    lookup_result = servicenow.get_incident(incident.number)
    if not lookup_result.get("found"):
        print("ServiceNow live verification failed: created incident was not found by number.")
        return 1

    print("Live NEXUS ServiceNow workflow verification passed.")
    print(f"Run: {session.run_id}")
    print(f"Incident: {incident.number}")
    print(f"Events: {len(session.stream.events)}")
    print(f"ServiceNow updates: {len(sent_updates)}")
    print(f"Last update: {incident.last_update_status}")
    print(f"OpenAI model: {openai.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
