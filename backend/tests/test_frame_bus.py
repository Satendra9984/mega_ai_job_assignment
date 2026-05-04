"""Unit tests for FrameBus."""

from __future__ import annotations

import asyncio

import pytest

from app.services.frame_bus import FrameBus


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber() -> None:
    bus = FrameBus(queue_maxsize=2)
    q = bus.subscribe()
    payload = b"\xff\xd8\xff\xe0fakejpeg"

    await bus.publish(payload)
    out = await asyncio.wait_for(q.get(), timeout=1.0)
    assert out == payload
    bus.unsubscribe(q)


@pytest.mark.asyncio
async def test_multiple_subscribers_receive() -> None:
    bus = FrameBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    payload = b"frame-bytes"

    await bus.publish(payload)
    assert await q1.get() == payload
    assert await q2.get() == payload
    bus.unsubscribe(q1)
    bus.unsubscribe(q2)
