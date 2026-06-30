from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "services" / "backend"
sys.path.insert(0, str(BACKEND))

from app.openai_client import NexusOpenAIClient  # noqa: E402
from app.orchestrator import RunManager  # noqa: E402
from app.tools import get_default_incident  # noqa: E402


async def wait_for_status(session, status: str, timeout: float = 120.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if session.status == status:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {status}; saw {session.status}")


async def main() -> int:
    if not os.getenv("OPENAI_API_KEY") and not (ROOT / ".env").exists():
        print("OPENAI_API_KEY is not configured. Copy .env.example to .env and set a real key.")
        return 2

    client = NexusOpenAIClient(mode="live")
    if not client.api_key:
        print("OPENAI_API_KEY is not loaded by the backend runtime.")
        return 2

    manager = RunManager(openai_client=client)
    session = await manager.start_run(get_default_incident())
    await wait_for_status(session, "waiting_approval")
    manager.approve(session.run_id)
    await wait_for_status(session, "waiting_closure")
    manager.close_incident(session.run_id)
    await wait_for_status(session, "closed")

    fallback_events = [
        event for event in session.stream.events if event.type == "openai.fallback"
    ]
    if fallback_events:
        print("Live OpenAI verification failed: workflow used fallback response.")
        for event in fallback_events:
            print(event.message)
        return 1

    print("Live OpenAI verification passed.")
    print(f"Run: {session.run_id}")
    print(f"Events: {len(session.stream.events)}")
    print(f"Model: {client.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
