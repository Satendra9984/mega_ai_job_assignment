# Sprint 1 — Up and running checklist

This checklist maps **[docs/ROADMAP.md](../ROADMAP.md) Sprint 1 (Backend Core)** to concrete verification steps. Tick items as you complete them on your machine.

Prerequisites: **Docker** + **Docker Compose v2**, repo cloned, `.env` from `.env.example` at repo root.

Reference docs: [DOCKER.md](DOCKER.md), [POSTGRESQL.md](POSTGRESQL.md), [LOCAL_PYTHON_AND_FASTAPI.md](LOCAL_PYTHON_AND_FASTAPI.md).

---

## 1. `docker compose up` starts backend + Postgres cleanly

**Pass criteria:** All services stay running; `db` is healthy; `backend` listens on port **8000** without crash loops.

```bash
docker compose up --build
```

In a second terminal:

```bash
docker compose ps
docker compose logs backend --tail 50
```

Expected: log lines showing Alembic then Uvicorn started; no repeated restart loop.

- [ ] Pass

---

## 2. `/ws/ingest` accepts frames and returns ROI JSON

**Pass criteria:** After connecting a WebSocket client to the ingest endpoint and sending at least one JPEG frame, the server responds with JSON containing `"type":"roi"` and `frame_index`.

**Option A — Use the UI (easiest)**

1. Open **http://localhost:3000** (with full stack) or point the frontend dev server at the API.
2. Click **Start webcam**; watch for session id and frame counter in the UI.

**Option B — `wscat` (if installed)**

```bash
npx wscat -c ws://localhost:8000/ws/ingest
```

Then send binary JPEG data (advanced); the UI path is recommended.

**Option C — curl HTTP checks only**

WebSockets are not exercised, but you can confirm the server is up:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs
```

- [ ] Pass (WS + ROI JSON observed)

---

## 3. ROI records appear in the database after sending frames

**Pass criteria:** Row count in `roi_records` increases after a short webcam session.

```bash
docker compose exec db psql -U megaai -d megaai -c "SELECT COUNT(*) FROM roi_records;"
```

Use the app to send frames, then run the query again.

- [ ] Pass

---

## 4. `GET /api/roi` returns stored records

**Pass criteria:** HTTP 200 and JSON body with `session_id`, `total`, and `records` for a valid session UUID.

1. Copy a `session_id` from the browser UI (after **Start webcam**) or from `sessions` table:

   ```bash
   docker compose exec db psql -U megaai -d megaai -c "SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1;"
   ```

2. Query the API (replace `UUID`):

   ```bash
   curl -s "http://localhost:8000/api/roi?session_id=UUID&limit=10" | head
   ```

Invalid session should return **404** (documented behavior).

- [ ] Pass

---

## 5. `pytest -v` passes (detector, frame bus, smoke)

**Pass criteria:** Exit code 0 from pytest inside the backend container.

```bash
docker compose exec backend pytest -v
```

- [ ] Pass

---

## 6. Git commits (process checkpoint)

**Pass criteria:** Meaningful commits (e.g. backend, docs, tests separately), not a single “final” dump.

This is a **process** item — no shell command.

- [ ] Pass

---

## Sprint 1 deliverables (quick mapping)

| Deliverable | Where / how |
|-------------|-------------|
| FastAPI project layout | `backend/app/` |
| `docker-compose.yml` + `db` + `backend` | repo root |
| `.env.example` | repo root |
| `WS /ws/ingest`, `WS /ws/stream`, `GET /api/roi` | see [docs/API.md](../API.md) |
| Alembic migration | `backend/alembic/versions/001_initial_sessions_roi.py` |
| Unit tests | `backend/tests/` |

---

## Optional: `/ws/stream` smoke

Connect a second client to `ws://localhost:8000/ws/stream` while ingest is active; you should receive binary JPEG frames. Useful to prove the frame bus fan-out.

- [ ] Optional pass
