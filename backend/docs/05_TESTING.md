# Testing — layout, fixtures, and commands

## Commands

From the `backend/` directory (where [`pytest.ini`](../pytest.ini) sets `pythonpath = .`):

```bash
pytest -v
```

Run a single file:

```bash
pytest tests/test_roi_api.py -v
```

Inside Docker (stack up):

```bash
docker compose exec backend pytest -v
```

---

## Test inventory

| File | Scope |
|------|--------|
| [`tests/test_smoke.py`](../tests/test_smoke.py) | App imports; `/openapi.json`, `/docs` |
| [`tests/test_detector.py`](../tests/test_detector.py) | `FaceDetector` on synthetic JPEG / invalid bytes |
| [`tests/test_frame_bus.py`](../tests/test_frame_bus.py) | `FrameBus` publish / subscribe |
| [`tests/test_roi_api.py`](../tests/test_roi_api.py) | `GET /api/roi` with SQLite + `httpx.AsyncClient` + `ASGITransport` |
| [`tests/test_ws_ingest.py`](../tests/test_ws_ingest.py) | `/ws/ingest` handshake, frames, errors — `TestClient` + patched lifespan |
| [`tests/test_ws_stream.py`](../tests/test_ws_stream.py) | `/ws/stream` receives bytes after ingest publishes |
| [`tests/test_e2e_compose.py`](../tests/test_e2e_compose.py) | Optional live stack smoke (skipped if backend not healthy) |

---

## Shared fixtures — [`tests/conftest.py`](../tests/conftest.py)

### Problem solved

1. **In-memory SQLite per connection:** Without a shared pool, each `AsyncSession` could attach to a **different** empty `:memory:` database. **`StaticPool`** forces one shared connection for all sessions in a test.

2. **`BigInteger` autoincrement on SQLite:** The production model uses `BigInteger` for `roi_records.id`. SQLite autoincrement works reliably on **`INTEGER PRIMARY KEY`**. The conftest creates tables with **hand-written DDL** (`INTEGER PRIMARY KEY AUTOINCREMENT` for `roi_records.id`) instead of `Base.metadata.create_all` for integration tests.

### Fixture families

| Fixture | Used by | Behavior |
|---------|---------|----------|
| `sqlite_engine` / `sqlite_session_factory` / `http_client` | `test_roi_api.py` | Overrides `app.dependency_overrides[get_db]` so REST uses SQLite. |
| `ws_client` | `test_ws_ingest.py`, `test_ws_stream.py` | Monkeypatches `app.router.lifespan_context` with a test lifespan that installs SQLite `session_factory`, `FrameBus`, and `FaceDetector` on `app.state`. |

---

## E2E tests — [`tests/test_e2e_compose.py`](../tests/test_e2e_compose.py)

- Probe **`http://localhost:8000`** (override with `E2E_BACKEND_HOST` / `E2E_BACKEND_PORT`).
- **Skip** when `GET /openapi.json` is not HTTP 200 (stack down, wrong port, or app not ready). This avoids false failures when only TCP is open but the app returns 500 (e.g. DB not migrated).
- REST checks use **`httpx`** (already in `requirements.txt`).
- WebSocket checks use **`websocket-client`** (declared in `requirements.txt`); WS tests also require the health check to pass.
- **`test_e2e_ws_ingest_one_jpeg_returns_roi_json`** — after `/ws/ingest` handshake, sends one small JPEG and asserts a `type: "roi"` JSON response (full pipeline smoke when DB + detector are up).

Run only E2E:

```bash
pytest tests/test_e2e_compose.py -v
```

With Compose up and healthy, skipped tests should become **passed**; when nothing is listening, expect **skipped**, not failed.

---

## pytest-asyncio

[`pytest.ini`](../pytest.ini) sets `asyncio_mode = auto` so `async def` tests are scheduled without extra decorators in most cases.
