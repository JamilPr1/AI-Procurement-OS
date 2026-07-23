"""In-memory event bus for dashboard live updates."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._max_history = 500

    def publish(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        event = {
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        for q in self._queues.get("all", []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._history[-limit:]

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._queues["all"].append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._queues.get("all", []):
            self._queues["all"].remove(q)


# Global singleton for the dashboard process
bus = EventBus()
