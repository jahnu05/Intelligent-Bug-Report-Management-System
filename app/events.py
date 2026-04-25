"""Lightweight in-process SSE event bus.

emit() is safe to call from synchronous service code.
stream_events() is an async generator consumed by the SSE endpoint.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator

_events: list[dict] = []
_MAX_EVENTS = 200


def emit(event_type: str, data: dict) -> None:
    _events.append(
        {
            "id": int(time.time() * 1000),
            "type": event_type,
            "data": data,
            "ts": time.time(),
        }
    )
    if len(_events) > _MAX_EVENTS:
        del _events[0]


async def stream_events(last_id: int = 0) -> AsyncIterator[str]:
    yield f"event: connected\ndata: {json.dumps({'status': 'ok'})}\n\n"
    last_sent = last_id
    while True:
        pending = [e for e in _events if e["id"] > last_sent]
        for event in pending:
            last_sent = event["id"]
            payload = json.dumps(event["data"])
            yield f"id: {event['id']}\nevent: {event['type']}\ndata: {payload}\n\n"
        yield ": heartbeat\n\n"
        await asyncio.sleep(5)
