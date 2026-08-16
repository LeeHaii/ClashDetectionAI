from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunEvent:
    id: int | None
    name: str
    data: dict[str, Any]


class RunEventBroker:
    def __init__(self) -> None:
        self._events: dict[str, list[RunEvent]] = defaultdict(list)
        self._conditions: dict[str, asyncio.Condition] = defaultdict(asyncio.Condition)
        self._terminal: set[str] = set()

    async def publish(self, run_id: str, name: str, data: dict[str, Any]) -> RunEvent:
        condition = self._conditions[run_id]
        async with condition:
            event = RunEvent(id=len(self._events[run_id]) + 1, name=name, data=data)
            self._events[run_id].append(event)
            condition.notify_all()
            return event

    async def finish(self, run_id: str) -> None:
        await self.publish(run_id, "done", {})
        condition = self._conditions[run_id]
        async with condition:
            self._terminal.add(run_id)
            condition.notify_all()

    async def stream(self, run_id: str, last_event_id: int = 0) -> AsyncIterator[RunEvent]:
        cursor = max(last_event_id, 0)
        condition = self._conditions[run_id]
        while True:
            event: RunEvent | None = None
            timed_out = False
            async with condition:
                if cursor < len(self._events[run_id]):
                    event = self._events[run_id][cursor]
                    cursor += 1
                elif run_id in self._terminal:
                    return
                else:
                    try:
                        await asyncio.wait_for(condition.wait(), timeout=15)
                    except TimeoutError:
                        timed_out = True
            if event is not None:
                yield event
            elif timed_out:
                yield RunEvent(id=None, name="ping", data={})
