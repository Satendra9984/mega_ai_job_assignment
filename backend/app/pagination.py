from __future__ import annotations

import base64
import json

from fastapi import HTTPException


def _b64_decode(token: str) -> dict:
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8") + b"===")
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid pagination token") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=422, detail="Invalid pagination token")
    return parsed


def _b64_encode(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def encode_cursor(*, record_id: int) -> str:
    return _b64_encode({"id": record_id})


def decode_cursor(token: str) -> int:
    payload = _b64_decode(token)
    try:
        return int(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor token") from exc


def encode_snapshot(*, max_id: int) -> str:
    return _b64_encode({"max_id": max_id})


def decode_snapshot(token: str) -> int:
    payload = _b64_decode(token)
    try:
        return int(payload["max_id"])
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid snapshot token") from exc
