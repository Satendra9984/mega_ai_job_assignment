"""Integration tests for GET /api/roi.

These tests use an in-memory SQLite database via the http_client fixture
(defined in conftest.py).  No running Postgres or Docker is required.
"""
from __future__ import annotations

import uuid

import pytest

from app.models import ROIRecord, VideoSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_session(sf) -> uuid.UUID:
    """Insert a VideoSession and return its UUID."""
    async with sf() as db:
        vs = VideoSession()
        db.add(vs)
        await db.commit()
        await db.refresh(vs)
        return vs.id


async def _seed_roi(sf, session_id: uuid.UUID, frame_index: int, **kwargs) -> None:
    """Insert one ROIRecord for the given session."""
    async with sf() as db:
        rec = ROIRecord(
            session_id=session_id,
            frame_index=frame_index,
            face_detected=kwargs.get("face_detected", False),
            x=kwargs.get("x"),
            y=kwargs.get("y"),
            w=kwargs.get("w"),
            h=kwargs.get("h"),
            confidence=kwargs.get("confidence"),
        )
        db.add(rec)
        await db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_roi_unknown_session_returns_404(http_client) -> None:
    r = await http_client.get(f"/api/roi?session_id={uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Session not found"


async def test_roi_missing_session_id_returns_422(http_client) -> None:
    r = await http_client.get("/api/roi")
    assert r.status_code == 422


async def test_roi_empty_session_returns_empty_list(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    r = await http_client.get(f"/api/roi?session_id={sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == str(sid)
    assert body["total"] == 0
    assert body["records"] == []


async def test_roi_returns_correct_shape(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    await _seed_roi(sqlite_session_factory, sid, 0, face_detected=False)
    await _seed_roi(
        sqlite_session_factory, sid, 1,
        face_detected=True, x=10, y=20, w=50, h=60, confidence=0.92,
    )

    r = await http_client.get(f"/api/roi?session_id={sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == str(sid)
    assert body["total"] == 2
    assert len(body["records"]) == 2

    first, second = body["records"]
    assert first["frame_index"] == 0
    assert first["face_detected"] is False
    assert first["x"] is None

    assert second["frame_index"] == 1
    assert second["face_detected"] is True
    assert second["x"] == 10
    assert second["y"] == 20
    assert second["w"] == 50
    assert second["h"] == 60
    assert abs(second["confidence"] - 0.92) < 0.01


async def test_roi_records_ordered_by_frame_index(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    # Insert in reverse order to confirm ORDER BY applies
    for i in range(4, -1, -1):
        await _seed_roi(sqlite_session_factory, sid, i)

    r = await http_client.get(f"/api/roi?session_id={sid}")
    frames = [rec["frame_index"] for rec in r.json()["records"]]
    assert frames == sorted(frames)


async def test_roi_pagination_limit(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    for i in range(5):
        await _seed_roi(sqlite_session_factory, sid, i)

    r = await http_client.get(f"/api/roi?session_id={sid}&limit=2&offset=0")
    body = r.json()
    assert body["total"] == 5
    assert len(body["records"]) == 2
    assert body["records"][0]["frame_index"] == 0
    assert body["records"][1]["frame_index"] == 1


async def test_roi_pagination_offset(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    for i in range(5):
        await _seed_roi(sqlite_session_factory, sid, i)

    r = await http_client.get(f"/api/roi?session_id={sid}&limit=2&offset=3")
    body = r.json()
    assert body["total"] == 5
    assert len(body["records"]) == 2
    assert body["records"][0]["frame_index"] == 3


async def test_roi_offset_beyond_total_returns_empty_list(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    for i in range(3):
        await _seed_roi(sqlite_session_factory, sid, i)

    r = await http_client.get(f"/api/roi?session_id={sid}&offset=100")
    body = r.json()
    assert body["total"] == 3
    assert body["records"] == []
