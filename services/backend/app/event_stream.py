from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .models import RunEvent, utc_now


class EventStream:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[RunEvent] = []
        self.subscribers: set[asyncio.Queue[RunEvent]] = set()

    async def emit(
        self,
        event_type: str,
        title: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> RunEvent:
        event = RunEvent(
            run_id=self.run_id,
            sequence=len(self.events) + 1,
            timestamp=utc_now(),
            type=event_type,
            title=title,
            message=message,
            payload=payload,
        )
        self.events.append(event)
        for queue in list(self.subscribers):
            await queue.put(event)
        return event

    def subscribe(self) -> asyncio.Queue[RunEvent]:
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        for event in self.events:
            queue.put_nowait(event)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[RunEvent]) -> None:
        self.subscribers.discard(queue)

    def export_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(
                    json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n"
                )

