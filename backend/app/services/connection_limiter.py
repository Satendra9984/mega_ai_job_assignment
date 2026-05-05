"""Simple in-memory connection limiter for websocket clients."""

from __future__ import annotations


class ConnectionLimiter:
    def __init__(self, max_per_ip: int = 5) -> None:
        self._max_per_ip = max_per_ip
        self._counts: dict[str, int] = {}

    def check(self, ip: str) -> bool:
        current = self._counts.get(ip, 0)
        if current >= self._max_per_ip:
            return False
        self._counts[ip] = current + 1
        return True

    def release(self, ip: str) -> None:
        current = self._counts.get(ip)
        if current is None:
            return
        if current <= 1:
            self._counts.pop(ip, None)
            return
        self._counts[ip] = current - 1
