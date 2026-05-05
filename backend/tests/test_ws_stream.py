"""Integration tests for WS /ws/stream.

The stream endpoint is a passive viewer: it subscribes to the FrameBus and
forwards raw JPEG bytes to connected clients.  These tests verify that frames
published via /ws/ingest appear on /ws/stream.

Because Starlette's TestClient is synchronous, concurrent connections are
managed with Python threads + threading.Event for synchronisation.
"""
from __future__ import annotations

import threading

from tests.conftest import make_solid_jpeg


def test_stream_client_receives_frame_after_ingest(ws_client) -> None:
    """A frame sent via /ws/ingest must be forwarded to a /ws/stream subscriber."""
    jpeg = make_solid_jpeg()
    received: list[bytes] = []
    stream_ready = threading.Event()
    frame_received = threading.Event()

    def _stream_worker() -> None:
        with ws_client.websocket_connect("/ws/stream") as stream_ws:
            stream_ready.set()
            try:
                data = stream_ws.receive_bytes()
                received.append(data)
                frame_received.set()
            except Exception:
                pass

    t = threading.Thread(target=_stream_worker, daemon=True)
    t.start()

    assert stream_ready.wait(timeout=5), "Stream client failed to connect in time"

    with ws_client.websocket_connect("/ws/ingest") as ingest_ws:
        ingest_ws.receive_json()  # handshake
        ingest_ws.send_bytes(jpeg)
        ingest_ws.receive_json()  # roi reply

    assert frame_received.wait(timeout=5), "Stream client did not receive the frame"
    t.join(timeout=2)

    assert len(received) == 1
    assert received[0] == jpeg


def test_stream_multiple_subscribers_all_receive_frame(ws_client) -> None:
    """Every active /ws/stream subscriber must receive each published frame."""
    jpeg = make_solid_jpeg(color=(128, 128, 128))
    n_subscribers = 2
    received: list[list[bytes]] = [[] for _ in range(n_subscribers)]
    ready_events = [threading.Event() for _ in range(n_subscribers)]
    done_events = [threading.Event() for _ in range(n_subscribers)]

    def _make_worker(idx: int):
        def _worker() -> None:
            with ws_client.websocket_connect("/ws/stream") as stream_ws:
                ready_events[idx].set()
                try:
                    data = stream_ws.receive_bytes()
                    received[idx].append(data)
                except Exception:
                    pass
                finally:
                    done_events[idx].set()

        return _worker

    threads = [
        threading.Thread(target=_make_worker(i), daemon=True)
        for i in range(n_subscribers)
    ]
    for t in threads:
        t.start()

    for ev in ready_events:
        assert ev.wait(timeout=5), "A stream subscriber failed to connect"

    with ws_client.websocket_connect("/ws/ingest") as ingest_ws:
        ingest_ws.receive_json()  # handshake
        ingest_ws.send_bytes(jpeg)
        ingest_ws.receive_json()  # roi reply

    for ev in done_events:
        assert ev.wait(timeout=5), "A stream subscriber timed out waiting for frame"

    for t in threads:
        t.join(timeout=2)

    for i in range(n_subscribers):
        assert len(received[i]) == 1, f"Subscriber {i} received {len(received[i])} frames"
        assert received[i][0] == jpeg


def test_stream_disconnect_does_not_affect_ingest(ws_client) -> None:
    """Disconnecting the stream client must not crash the ingest session."""
    jpeg = make_solid_jpeg()

    with ws_client.websocket_connect("/ws/stream"):
        pass  # connect and immediately disconnect

    # Ingest should still work after the stream subscriber left
    with ws_client.websocket_connect("/ws/ingest") as ingest_ws:
        ingest_ws.receive_json()  # handshake
        ingest_ws.send_bytes(jpeg)
        roi = ingest_ws.receive_json()

    assert roi["type"] == "roi"


def test_stream_session_filter_only_receives_matching_session(ws_client) -> None:
    """session_id query parameter should isolate stream frames by ingest session."""
    jpeg = make_solid_jpeg(color=(10, 20, 30))

    with ws_client.websocket_connect("/ws/ingest") as ingest_ws:
        handshake = ingest_ws.receive_json()
        sid = handshake["session_id"]

        with ws_client.websocket_connect(f"/ws/stream?session_id={sid}") as stream_ws:
            ingest_ws.send_bytes(jpeg)
            ingest_ws.receive_json()  # roi reply
            assert stream_ws.receive_bytes() == jpeg
