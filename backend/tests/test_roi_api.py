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
    assert body["has_more"] is False
    assert body["next_cursor"] is None
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

    by_frame = {r["frame_index"]: r for r in body["records"]}
    assert by_frame[0]["face_detected"] is False
    assert by_frame[0]["x"] is None
    assert by_frame[1]["face_detected"] is True
    assert by_frame[1]["x"] == 10
    assert by_frame[1]["y"] == 20
    assert by_frame[1]["w"] == 50
    assert by_frame[1]["h"] == 60
    assert abs(by_frame[1]["confidence"] - 0.92) < 0.01


async def test_roi_records_ordered_by_frame_index(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    # Insert in reverse order to confirm ORDER BY applies
    for i in range(4, -1, -1):
        await _seed_roi(sqlite_session_factory, sid, i)

    r = await http_client.get(f"/api/roi?session_id={sid}")
    rows = r.json()["records"]
    for i in range(len(rows) - 1):
        left = rows[i]
        right = rows[i + 1]
        left_key = (left["detected_at"], left["id"])
        right_key = (right["detected_at"], right["id"])
        assert left_key >= right_key


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
    assert body["has_more"] is True
    assert body["records"][0]["frame_index"] == 4
    assert body["records"][1]["frame_index"] == 3


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
    assert body["records"][0]["frame_index"] == 1


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


async def test_roi_cursor_first_page_returns_cursor_and_snapshot(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    for i in range(5):
        await _seed_roi(sqlite_session_factory, sid, i)

    r = await http_client.get(f"/api/roi?session_id={sid}&limit=2&use_cursor=true")
    assert r.status_code == 200
    body = r.json()

    assert len(body["records"]) == 2
    assert body["has_more"] is True
    assert isinstance(body["next_cursor"], str)
    assert isinstance(body["snapshot"], str)
    assert body["offset"] == 0
    assert body["records"][0]["frame_index"] == 4
    assert body["records"][1]["frame_index"] == 3


async def test_roi_cursor_second_page_continues_without_duplicates(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    for i in range(6):
        await _seed_roi(sqlite_session_factory, sid, i)

    first = await http_client.get(f"/api/roi?session_id={sid}&limit=2&use_cursor=true")
    b1 = first.json()
    second = await http_client.get(
        f"/api/roi?session_id={sid}&limit=2&use_cursor=true&cursor={b1['next_cursor']}&snapshot={b1['snapshot']}"
    )
    b2 = second.json()

    first_ids = {r["id"] for r in b1["records"]}
    second_ids = {r["id"] for r in b2["records"]}
    assert first_ids.isdisjoint(second_ids)
    assert [r["frame_index"] for r in b2["records"]] == [3, 2]


async def test_roi_cursor_snapshot_freezes_view_under_new_inserts(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    for i in range(3):
        await _seed_roi(sqlite_session_factory, sid, i)

    first = await http_client.get(f"/api/roi?session_id={sid}&limit=2&use_cursor=true")
    b1 = first.json()

    await _seed_roi(sqlite_session_factory, sid, 99)

    second = await http_client.get(
        f"/api/roi?session_id={sid}&limit=2&use_cursor=true&cursor={b1['next_cursor']}&snapshot={b1['snapshot']}"
    )
    b2 = second.json()
    assert all(r["frame_index"] != 99 for r in b2["records"])


async def test_roi_cursor_invalid_cursor_returns_422(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    await _seed_roi(sqlite_session_factory, sid, 0)

    r = await http_client.get(
        f"/api/roi?session_id={sid}&use_cursor=true&cursor=not-a-token"
    )
    assert r.status_code == 422


async def test_roi_cursor_invalid_snapshot_returns_422(
    http_client, sqlite_session_factory
) -> None:
    sid = await _seed_session(sqlite_session_factory)
    await _seed_roi(sqlite_session_factory, sid, 0)

    r = await http_client.get(
        f"/api/roi?session_id={sid}&use_cursor=true&snapshot=not-a-token"
    )
    assert r.status_code == 422
