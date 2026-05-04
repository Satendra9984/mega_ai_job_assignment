"""E2E Compose smoke tests.

These tests run against a *live* Docker Compose stack.  They are skipped
automatically when the backend is not reachable, so they never fail in
local unit-test runs where Postgres/Docker is not available.

To run against the full stack:

    docker compose up -d
    # Then either:
    docker compose exec backend pytest tests/test_e2e_compose.py -v
    # Or from the host (requires stack up on localhost:8000):
    pytest tests/test_e2e_compose.py -v

Probes:
  - REST /api/roi          → 404 for unknown session, 422 for missing param
  - REST /openapi.json     → 200 with schema
  - WS  /ws/ingest         → handshake JSON contains session_id UUID
  - WS  /ws/ingest         → one JPEG frame → ROI JSON (integration smoke)
  - WS  /ws/stream         → connect + disconnect without crash
"""
from __future__ import annotations

import io
import json
import os
import uuid

import pytest
from PIL import Image

BACKEND_HOST = os.getenv("E2E_BACKEND_HOST", "localhost")
BACKEND_PORT = int(os.getenv("E2E_BACKEND_PORT", "8000"))
BACKEND_HTTP = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
BACKEND_WS = f"ws://{BACKEND_HOST}:{BACKEND_PORT}"


def _backend_reachable() -> bool:
    """Return True when the backend is reachable AND returns a healthy response.

    We probe /openapi.json (no DB required) instead of just checking TCP so
    that tests are skipped cleanly when Docker is running but the backend
    container has not finished starting.
    """
    try:
        import httpx  # httpx is a test dep so always available in the venv
        r = httpx.get(
            f"http://{BACKEND_HOST}:{BACKEND_PORT}/openapi.json", timeout=3
        )
        return r.status_code == 200
    except Exception:
        return False


def _ws_available() -> bool:
    """Return True when both the backend is reachable and websocket-client is installed."""
    if not _backend_reachable():
        return False
    try:
        import websocket  # noqa: F401  # websocket-client package
        return True
    except ImportError:
        return False


skip_no_stack = pytest.mark.skipif(
    not _backend_reachable(),
    reason=(
        f"Backend not reachable at {BACKEND_HOST}:{BACKEND_PORT}. "
        "Start the Compose stack (`docker compose up -d`) to run E2E tests."
    ),
)

skip_no_ws_client = pytest.mark.skipif(
    not _ws_available(),
    reason=(
        "websocket-client not installed or backend not reachable. "
        "Install with `pip install websocket-client` and ensure the stack is up."
    ),
)


def _tiny_gray_jpeg() -> bytes:
    """Minimal valid JPEG (solid gray) for ingest smoke — no face expected."""
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (200, 200, 200)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# REST smoke tests (use httpx — already a test dependency)
# ---------------------------------------------------------------------------

@skip_no_stack
def test_e2e_openapi_schema_available() -> None:
    """Backend exposes the OpenAPI schema at /openapi.json with no 5xx."""
    import httpx

    r = httpx.get(f"{BACKEND_HTTP}/openapi.json", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert "openapi" in body
    assert "paths" in body


@skip_no_stack
def test_e2e_roi_missing_session_id_returns_422() -> None:
    """GET /api/roi without session_id must return 422 Unprocessable Entity."""
    import httpx

    r = httpx.get(f"{BACKEND_HTTP}/api/roi", timeout=5)
    assert r.status_code == 422


@skip_no_stack
def test_e2e_roi_unknown_session_returns_404() -> None:
    """GET /api/roi with an unknown session UUID must return 404."""
    import httpx

    r = httpx.get(
        f"{BACKEND_HTTP}/api/roi",
        params={"session_id": str(uuid.uuid4())},
        timeout=5,
    )
    assert r.status_code == 404
    assert "Session not found" in r.json().get("detail", "")


# ---------------------------------------------------------------------------
# WebSocket smoke tests (require websocket-client)
# ---------------------------------------------------------------------------

@skip_no_ws_client
def test_e2e_ws_ingest_handshake() -> None:
    """Connecting to /ws/ingest must immediately receive a session JSON."""
    import websocket as ws_lib

    ws = ws_lib.create_connection(f"{BACKEND_WS}/ws/ingest", timeout=5)
    try:
        raw = ws.recv()
        msg = json.loads(raw)
        assert msg["type"] == "session"
        uuid.UUID(msg["session_id"])  # raises ValueError if not a valid UUID
    finally:
        ws.close()


@skip_no_ws_client
def test_e2e_ws_ingest_one_jpeg_returns_roi_json() -> None:
    """After handshake, sending one binary JPEG yields a type:roi JSON message."""
    import websocket as ws_lib
    from websocket import ABNF

    ws = ws_lib.create_connection(f"{BACKEND_WS}/ws/ingest", timeout=15)
    try:
        raw = ws.recv()
        msg = json.loads(raw)
        assert msg["type"] == "session"

        ws.send(_tiny_gray_jpeg(), opcode=ABNF.OPCODE_BINARY)
        raw2 = ws.recv()
        roi = json.loads(raw2)
        assert roi["type"] == "roi"
        assert "face_detected" in roi
        assert isinstance(roi["face_detected"], bool)
        assert roi.get("frame_index") == 0
    finally:
        ws.close()


@skip_no_ws_client
def test_e2e_ws_stream_connect_disconnect_clean() -> None:
    """Connecting and immediately disconnecting /ws/stream must not crash."""
    import websocket as ws_lib

    ws = ws_lib.create_connection(f"{BACKEND_WS}/ws/stream", timeout=5)
    ws.close()
    # Reaching here means the server handled the disconnect gracefully
