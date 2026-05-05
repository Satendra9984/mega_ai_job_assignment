"""Integration tests for WS /ws/ingest.

Uses the ws_client fixture (conftest.py) which runs the app in Starlette's
TestClient with a SQLite-backed session factory so no Postgres is required.
The real FaceDetector (BlazeFace TFLite) is used; JPEG frames are solid-colour
images that will always return face_detected=False.
"""
from __future__ import annotations

import uuid

from tests.conftest import make_solid_jpeg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _white_jpeg() -> bytes:
    return make_solid_jpeg(color=(255, 255, 255))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ingest_handshake_returns_session_id(ws_client) -> None:
    """On connect, the ingest endpoint must immediately send a session JSON."""
    with ws_client.websocket_connect("/ws/ingest") as ws:
        msg = ws.receive_json()

    assert msg["type"] == "session"
    assert "session_id" in msg
    # Confirm it's a valid UUID
    uuid.UUID(msg["session_id"])


def test_ingest_valid_frame_returns_roi_json(ws_client) -> None:
    """A valid JPEG frame must produce a type:roi response with frame_index=0."""
    jpeg = _white_jpeg()
    with ws_client.websocket_connect("/ws/ingest") as ws:
        ws.receive_json()  # handshake
        ws.send_bytes(jpeg)
        roi = ws.receive_json()

    assert roi["type"] == "roi"
    assert roi["frame_index"] == 0
    assert roi["face_detected"] is False  # solid white frame — no face
    assert roi["x"] is None
    assert roi["confidence"] is None


def test_ingest_no_face_frame_persisted_to_db(ws_client) -> None:
    """A no-face frame should still persist as a row with face_detected=False."""
    jpeg = _white_jpeg()
    with ws_client.websocket_connect("/ws/ingest") as ws:
        handshake = ws.receive_json()
        sid = handshake["session_id"]
        ws.send_bytes(jpeg)
        ws.receive_json()

    r = ws_client.get(f"/api/roi?session_id={sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["records"]) == 1
    assert body["records"][0]["face_detected"] is False


def test_ingest_frame_index_increments(ws_client) -> None:
    """frame_index must increment for each successfully processed frame."""
    jpeg = _white_jpeg()
    with ws_client.websocket_connect("/ws/ingest") as ws:
        ws.receive_json()  # handshake
        for expected_index in range(3):
            ws.send_bytes(jpeg)
            roi = ws.receive_json()
            assert roi["type"] == "roi"
            assert roi["frame_index"] == expected_index


def test_ingest_oversized_frame_returns_error(ws_client) -> None:
    """Frames larger than MAX_FRAME_BYTES must be rejected with FRAME_TOO_LARGE."""
    oversized = b"x" * (1_048_576 + 1)  # 1 byte over the 1 MB limit
    with ws_client.websocket_connect("/ws/ingest") as ws:
        ws.receive_json()  # handshake
        ws.send_bytes(oversized)
        err = ws.receive_json()

    assert err["type"] == "error"
    assert err["code"] == "FRAME_TOO_LARGE"


def test_ingest_invalid_bytes_returns_invalid_frame_error(ws_client) -> None:
    """Non-JPEG binary data must return an INVALID_FRAME error."""
    with ws_client.websocket_connect("/ws/ingest") as ws:
        ws.receive_json()  # handshake
        ws.send_bytes(b"this is not a valid jpeg at all!")
        err = ws.receive_json()

    assert err["type"] == "error"
    assert err["code"] == "INVALID_FRAME"


def test_ingest_error_does_not_advance_frame_index(ws_client) -> None:
    """An invalid frame must NOT advance the frame_index counter."""
    jpeg = _white_jpeg()
    with ws_client.websocket_connect("/ws/ingest") as ws:
        ws.receive_json()  # handshake
        # First: valid frame → frame_index 0
        ws.send_bytes(jpeg)
        roi_0 = ws.receive_json()
        assert roi_0["frame_index"] == 0

        # Second: invalid frame → error, index must not advance
        ws.send_bytes(b"bad data")
        ws.receive_json()  # INVALID_FRAME error

        # Third: valid frame → frame_index must still be 1
        ws.send_bytes(jpeg)
        roi_1 = ws.receive_json()
        assert roi_1["frame_index"] == 1


def test_ingest_disconnect_is_clean(ws_client) -> None:
    """Disconnecting without sending frames must not raise an error."""
    with ws_client.websocket_connect("/ws/ingest") as ws:
        ws.receive_json()  # handshake — disconnect right after
    # Reaching here without exception means finally-block cleanup ran correctly


def test_ingest_session_id_is_unique_per_connection(ws_client) -> None:
    """Each new WS connection must create a distinct session UUID."""
    session_ids = []
    for _ in range(3):
        with ws_client.websocket_connect("/ws/ingest") as ws:
            msg = ws.receive_json()
            session_ids.append(msg["session_id"])

    assert len(set(session_ids)) == 3, "All session IDs should be unique"


def test_ingest_db_error_sends_error_and_continues(ws_client, monkeypatch) -> None:
    """A DB save failure should emit DB_ERROR and keep the websocket session alive."""
    state = {"failed_once": False}

    async def _save_roi_record_fail_once(*args, **kwargs):
        if not state["failed_once"]:
            state["failed_once"] = True
            raise RuntimeError("simulated DB outage")
        from app.services.session_service import save_roi_record

        return await save_roi_record(*args, **kwargs)

    monkeypatch.setattr("app.routers.ingest.save_roi_record", _save_roi_record_fail_once)

    jpeg = _white_jpeg()
    with ws_client.websocket_connect("/ws/ingest") as ws:
        ws.receive_json()  # handshake
        ws.send_bytes(jpeg)
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "DB_ERROR"

        ws.send_bytes(jpeg)
        roi = ws.receive_json()
        assert roi["type"] == "roi"
        assert roi["frame_index"] == 0
