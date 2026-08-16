import pytest

from app.services.events import RunEventBroker


@pytest.mark.asyncio
async def test_replays_events_after_last_event_id() -> None:
    broker = RunEventBroker()
    await broker.publish("run-1", "run.started", {})
    await broker.publish("run-1", "content.delta", {"delta": "first"})
    await broker.publish("run-1", "content.delta", {"delta": "second"})
    await broker.finish("run-1")

    events = [event async for event in broker.stream("run-1", last_event_id=2)]

    assert [event.name for event in events] == ["content.delta", "done"]
    assert events[0].data == {"delta": "second"}
