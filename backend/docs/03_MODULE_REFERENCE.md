# Module reference — `app/` package

Each subsection maps **one file** to its **role**, **key symbols**, **who imports it**, and **tests** that exercise it.

Paths are relative to `backend/app/` unless noted.

---

## `main.py`

| | |
|--|--|
| **Role** | Construct `FastAPI` app, register CORS, attach `lifespan`, include routers. |
| **Key symbols** | `app`, `lifespan` |
| **State** | `app.state.session_factory`, `app.state.detector`, `app.state.frame_bus` |
| **Imports** | `config.settings`, `database.AsyncSessionLocal`, routers `ingest`, `stream`, `roi`, `FaceDetector`, `FrameBus` |
| **Imported by** | Uvicorn (`app.main:app`), tests (`from app.main import app`) |
| **Tests** | Indirectly all integration tests; [`tests/test_smoke.py`](../tests/test_smoke.py) hits `/openapi.json`, `/docs` |

---

## `config.py`

| | |
|--|--|
| **Role** | Load settings from environment and optional `.env` (pydantic-settings). |
| **Key symbols** | `Settings`, `settings` (singleton) |
| **Fields** | `database_url`, `max_frame_bytes`, `detection_confidence`, `cors_origins` → `cors_origins_list` |
| **Imported by** | `database.py` (engine URL), `main.py` (CORS + detector confidence), `routers/ingest.py` (max frame size) |
| **Tests** | No dedicated unit tests; values exercised via ingest size guard and CORS in full app |

---

## `database.py`

| | |
|--|--|
| **Role** | Create async SQLAlchemy engine + session factory; expose `get_db` dependency and ORM `Base`. |
| **Key symbols** | `engine`, `AsyncSessionLocal`, `Base`, `get_db` |
| **Imported by** | `main.py` (binds `AsyncSessionLocal` to `app.state.session_factory` in prod), `routers/roi.py` (`Depends(get_db)`), Alembic `env.py` |
| **Tests** | [`tests/test_roi_api.py`](../tests/test_roi_api.py) overrides `get_db` with SQLite-backed session |

---

## `models/video_session.py`

| | |
|--|--|
| **Role** | ORM model for table `sessions` — one row per ingest WebSocket connection. |
| **Key symbols** | `VideoSession` — `id` (UUID PK), `created_at`, relationship to `ROIRecord` |
| **Imported by** | `models/__init__.py`, `routers/ingest.py`, `routers/roi.py` |
| **Tests** | Created implicitly in [`test_ws_ingest.py`](../tests/test_ws_ingest.py); seeded in [`test_roi_api.py`](../tests/test_roi_api.py) |

---

## `models/roi_record.py`

| | |
|--|--|
| **Role** | ORM model for table `roi_records` — one row per successfully processed frame on ingest. |
| **Key symbols** | `ROIRecord` — FK `session_id`, `frame_index`, `face_detected`, `x,y,w,h`, `confidence`, `detected_at` |
| **Imported by** | `models/__init__.py`, `routers/ingest.py`, `routers/roi.py` |
| **Tests** | [`test_ws_ingest.py`](../tests/test_ws_ingest.py), [`test_roi_api.py`](../tests/test_roi_api.py) |

---

## `schemas/roi.py`

| | |
|--|--|
| **Role** | Pydantic models for REST response serialization (not DB tables). |
| **Key symbols** | `ROIRecordRead`, `ROIListResponse` |
| **Imported by** | `routers/roi.py` |
| **Tests** | Validated via [`test_roi_api.py`](../tests/test_roi_api.py) response JSON shape |

---

## `services/detector.py`

| | |
|--|--|
| **Role** | Decode JPEG with Pillow, run MediaPipe Tasks `FaceDetector`, return `DetectionResult`. Thread-safe (`threading.Lock` around detect). |
| **Key symbols** | `DetectionResult` (dataclass), `FaceDetector` (`__init__`, `detect`, `close`) |
| **Side files** | Expects `backend/models/blaze_face_short_range.tflite` (see `_DEFAULT_MODEL`) |
| **Imported by** | `main.py`, `services/__init__.py`, `routers/ingest.py` (type-only `DetectionResult`) |
| **Tests** | [`tests/test_detector.py`](../tests/test_detector.py); ingest tests call real detector |

---

## `services/frame_bus.py`

| | |
|--|--|
| **Role** | In-process pub/sub: many subscriber queues, `publish` broadcasts raw bytes; bounded queues drop oldest on overflow. |
| **Key symbols** | `FrameBus` — `subscribe`, `unsubscribe`, `publish`, `drain_queue` |
| **Imported by** | `main.py`, `routers/ingest.py`, `routers/stream.py` |
| **Tests** | [`tests/test_frame_bus.py`](../tests/test_frame_bus.py), [`tests/test_ws_stream.py`](../tests/test_ws_stream.py) |

---

## `routers/ingest.py`

| | |
|--|--|
| **Role** | WebSocket `/ws/ingest` — session creation, frame loop, detection, DB insert, bus publish, ROI JSON. |
| **Key symbols** | `router`, `websocket_ingest` |
| **Imported by** | `main.py` |
| **Tests** | [`tests/test_ws_ingest.py`](../tests/test_ws_ingest.py) |

---

## `routers/stream.py`

| | |
|--|--|
| **Role** | WebSocket `/ws/stream` — subscribe to bus, `send_bytes` loop, unsubscribe on exit. |
| **Key symbols** | `router`, `websocket_stream` |
| **Imported by** | `main.py` |
| **Tests** | [`tests/test_ws_stream.py`](../tests/test_ws_stream.py) |

---

## `routers/roi.py`

| | |
|--|--|
| **Role** | REST `GET /api/roi` — session existence check, count, paginated list. |
| **Key symbols** | `router`, `list_roi` |
| **Imported by** | `main.py` (with prefix `/api`) |
| **Tests** | [`tests/test_roi_api.py`](../tests/test_roi_api.py) |

---

## `routers/__init__.py`, `services/__init__.py`, `schemas/__init__.py`, `app/__init__.py`

Package markers / re-exports. Read only if you care about import style; behavior lives in the modules above.

---

## Alembic (outside `app/` but part of backend)

| Path | Role |
|------|------|
| [`alembic/env.py`](../alembic/env.py) | Loads `DATABASE_URL` from settings, configures `target_metadata = Base.metadata`, runs migrations async. |
| [`alembic/versions/001_initial_sessions_roi.py`](../alembic/versions/001_initial_sessions_roi.py) | Creates `sessions` and `roi_records` + index. |

Tests **do not** run Alembic; they create SQLite DDL via [`tests/conftest.py`](../tests/conftest.py).
