"""In-process pub/sub for broadcasting raw JPEG frames to /ws/stream viewers."""

from __future__ import annotations

import asyncio
from collections import defaultdict


class FrameBus:
    def __init__(self, queue_maxsize: int = 2) -> None:
        self._queue_maxsize = queue_maxsize
        self._queues: dict[str | None, set[asyncio.Queue[bytes | None]]] = defaultdict(set)

    def subscribe(self, session_id: str | None = None) -> asyncio.Queue[bytes | None]:
        q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._queues[session_id].add(q)
        return q

    def unsubscribe(
        self,
        q: asyncio.Queue[bytes | None],
        session_id: str | None = None,
    ) -> None:
        bucket = self._queues.get(session_id)
        if bucket is None:
            return
        bucket.discard(q)
        if not bucket:
            self._queues.pop(session_id, None)

    async def publish(self, frame: bytes, session_id: str) -> None:
        targets = list(self._queues.get(None, set()) | self._queues.get(session_id, set()))
        for q in targets:
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(frame)
                except asyncio.QueueFull:
                    pass

    async def drain_queue(self, q: asyncio.Queue[bytes | None]) -> bytes | None:
        return await q.get()
