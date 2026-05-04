"""In-process pub/sub for broadcasting raw JPEG frames to /ws/stream viewers."""

from __future__ import annotations

import asyncio


class FrameBus:
    def __init__(self, queue_maxsize: int = 2) -> None:
        self._queue_maxsize = queue_maxsize
        self._queues: set[asyncio.Queue[bytes | None]] = set()

    def subscribe(self) -> asyncio.Queue[bytes | None]:
        q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[bytes | None]) -> None:
        self._queues.discard(q)

    async def publish(self, frame: bytes) -> None:
        for q in list(self._queues):
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
