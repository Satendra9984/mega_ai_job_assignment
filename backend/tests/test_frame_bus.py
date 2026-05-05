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

    await bus.publish(payload, session_id="s1")
    out = await asyncio.wait_for(q.get(), timeout=1.0)
    assert out == payload
    bus.unsubscribe(q)


@pytest.mark.asyncio
async def test_multiple_subscribers_receive() -> None:
    bus = FrameBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    payload = b"frame-bytes"

    await bus.publish(payload, session_id="s1")
    assert await q1.get() == payload
    assert await q2.get() == payload
    bus.unsubscribe(q1)
    bus.unsubscribe(q2)


@pytest.mark.asyncio
async def test_session_filtered_subscriber_receives_matching_session_only() -> None:
    bus = FrameBus()
    all_sessions_q = bus.subscribe()
    s1_q = bus.subscribe(session_id="s1")
    s2_q = bus.subscribe(session_id="s2")

    s1_payload = b"s1-frame"
    await bus.publish(s1_payload, session_id="s1")

    assert await asyncio.wait_for(all_sessions_q.get(), timeout=1.0) == s1_payload
    assert await asyncio.wait_for(s1_q.get(), timeout=1.0) == s1_payload
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(s2_q.get(), timeout=0.1)

    bus.unsubscribe(all_sessions_q)
    bus.unsubscribe(s1_q, session_id="s1")
    bus.unsubscribe(s2_q, session_id="s2")


@pytest.mark.asyncio
async def test_concurrent_publish_no_loss_for_fast_consumers() -> None:
    bus = FrameBus(queue_maxsize=20)
    subscribers = [bus.subscribe() for _ in range(3)]
    payloads = [f"frame-{i}".encode("utf-8") for i in range(10)]

    await asyncio.gather(*(bus.publish(payload, session_id="s-load") for payload in payloads))

    for q in subscribers:
        received = [await asyncio.wait_for(q.get(), timeout=1.0) for _ in range(len(payloads))]
        assert received == payloads
        bus.unsubscribe(q)
