# Database — schema, migrations, and session patterns

## Tables

### `sessions`

- **ORM:** [`app/models/video_session.py`](../app/models/video_session.py) — class `VideoSession`, `__tablename__ = "sessions"`.
- **Purpose:** One row per **ingest WebSocket** connection. The UUID is sent to the client in the handshake and ties all `roi_records` rows together.

### `roi_records`

- **ORM:** [`app/models/roi_record.py`](../app/models/roi_record.py) — class `ROIRecord`.
- **Purpose:** One row per **successfully processed** JPEG on ingest (after detection). Includes `frame_index` (0-based sequence for that session), `face_detected`, optional box `x,y,w,h`, optional `confidence`, server timestamp `detected_at`.
- **Constraints:** `session_id` FK → `sessions.id` with `ON DELETE CASCADE`. Index `ix_roi_records_session_id` for listing by session.

Production DDL is created by Alembic revision [`alembic/versions/001_initial_sessions_roi.py`](../alembic/versions/001_initial_sessions_roi.py).

---

## Two ways the code opens a database session

Understanding this removes a lot of confusion when reading [`routers/ingest.py`](../app/routers/ingest.py) vs [`routers/roi.py`](../app/routers/roi.py).

### 1. `Depends(get_db)` — REST only

[`app/database.py`](../app/database.py) defines:

```python
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

[`routers/roi.py`](../app/routers/roi.py) declares `session: AsyncSession = Depends(get_db)`. FastAPI opens one session per request and closes it after the handler returns.

**Engine:** Always the global `engine` / `AsyncSessionLocal` built from `settings.database_url` at import time.

### 2. `app.state.session_factory` — WebSocket ingest

[`main.py`](../app/main.py) sets:

```python
app.state.session_factory = AsyncSessionLocal
```

[`routers/ingest.py`](../app/routers/ingest.py) does:

```python
session_factory = websocket.app.state.session_factory
async with session_factory() as db:
    ...
```

So ingest **does not** use `get_db`; it uses the **same factory type** (`async_sessionmaker`) but retrieved from `app.state` so tests can **replace** the factory with an in-memory SQLite session maker without patching `database.py` imports (see [05_TESTING.md](05_TESTING.md)).

**Why not `Depends(get_db)` on WebSocket?** Possible with WebSocket dependencies, but the current design keeps a long-lived connection and explicit `async with` blocks per logical unit (session row creation vs each frame insert).

---

## Alembic

| File | Role |
|------|------|
| [`alembic.ini`](../alembic.ini) | Script location, logging, DB URL override pattern. |
| [`alembic/env.py`](../alembic/env.py) | Imports `Base.metadata` and `settings.database_url`, runs `run_migrations_online()` with async engine. |
| [`alembic/script.py.mako`](../alembic/script.py.mako) | Template for new revisions. |

**Docker:** The backend image typically runs `alembic upgrade head` before Uvicorn starts (see root [`Dockerfile`](../Dockerfile) if present).

**Local:** From `backend/` with `.env` pointing at Postgres: `alembic upgrade head`.

---

## SQLite in tests vs Postgres in production

ORM models target **Postgres** types (`Uuid`, `BigInteger` autoincrement). SQLite in tests uses hand-written DDL in [`tests/conftest.py`](../tests/conftest.py) so `roi_records.id` autoincrements correctly (SQLite quirk with `BIGINT`). Do not assume test DDL matches Alembic line-for-line; behavior under test is aligned at the **application** level (insert + select + pagination).
