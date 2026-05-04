# Sprint Roadmap

Assignment deadline: **2026-05-10 18:00 UTC+5:30**
Start date: **2026-05-04**

---

## Sprint 0 — Documentation & Architecture (Day 1: May 4)

**Goal:** All docs written, architecture locked, PNG diagram exported, project scaffolded.

### Deliverables

- `README.md` with quickstart skeleton (ports, `docker compose up`, env vars)
- `docs/ARCHITECTURE.md` with diagram and component descriptions
- `docs/API.md` with 3 endpoint contracts + WebSocket message schemas
- `docs/DECISIONS.md` with decisions: client-side draw, WS ingest, face lib, DB, schema
- `docs/AI_USAGE.md` — attestation template filled as work progresses
- `docs/ROADMAP.md` — this file committed to repo
- `diagrams/architecture.png` — exported architecture PNG
- Git commit: `docs: add architecture, API contract, and sprint roadmap`

### Checkpoints

- [x] Architecture diagram reviewed and exported to PNG
- [x] All 3 endpoint shapes agreed (path, WS vs REST, payload in/out)
- [x] Face detection library chosen — MediaPipe (no OpenCV-Python in app code)
- [x] DB schema drafted — `sessions` + `roi_records` tables

---

## Sprint 1 — Backend Core (Days 2–3: May 5–6)

**Goal:** FastAPI app running in Docker with face detection pipeline and DB persistence.

### Deliverables

- `backend/` FastAPI project (`main.py`, `routers/`, `services/`, `models/`, `schemas/`, `db/`)
- `docker-compose.yml` with `backend`, `db` (Postgres) services
- `.env.example` with all env vars
- `WS /ws/ingest` — accept binary frames, run detection, write ROI to DB, return ROI JSON
- `WS /ws/stream` — serve raw frames to passive viewers
- `REST GET /api/roi` — return stored ROI records queryable by session
- Alembic migration for `sessions` + `roi_records` tables
- Unit tests: detector service, ROI CRUD, frame routing

### Checkpoints

- [x] `docker compose up` starts backend + Postgres cleanly (compose + migrations wired; verify on machine with Docker)
- [x] `/ws/ingest` accepts frames and returns ROI JSON `{"type":"roi","frame_index":N,…}`
- [x] ROI records appear in DB after sending test frames
- [x] `/api/roi` returns correct paginated records
- [x] `pytest -v` passes for detector, frame bus, and smoke tests (`docker compose exec backend pytest -v`)
- [ ] Git commits are small and meaningful (one per feature — perform before submit)

---

## Sprint 2 — Frontend (Day 4: May 7)

**Goal:** React app displays webcam stream with ROI rectangle overlay.

### Deliverables

- `frontend/` React + TypeScript app (Vite)
- `<canvas>` captures webcam frames, encodes JPEG, sends to `/ws/ingest`
- Receives ROI JSON → stores in state → draws rectangle on canvas overlay
- Simple UI: Start/Stop button, session ID display, detection confidence badge
- Optional: ROI history panel fetching from `/api/roi`
- `frontend/Dockerfile` (nginx serving Vite build)
- nginx proxying `/ws/*` and `/api/*` to backend

### Checkpoints

- [x] Webcam stream visible on canvas in browser
- [x] Rectangle drawn on canvas aligned to face in real time
- [x] Frontend container in `docker-compose.yml`, accessible at `localhost:3000`
- [x] No ROI drawing done by backend (confirmed: pure client-side canvas)
- [x] `docker compose up` brings up all three services cleanly (verify locally with Docker)

---

## Sprint 3 — Integration, Testing & Polish (Day 5: May 8–9)

**Goal:** End-to-end flow verified, tests added, docs finalized, ready for review.

### Deliverables

- Integration test: optional — run end-to-end manually (`docker compose up`, open `localhost:3000`, use webcam)
- Error handling: no face → graceful empty ROI; oversized frame → error JSON; WS disconnect → cleanup
- Security: no secrets in repo; env vars only; frame-size guard; CORS restricted to `CORS_ORIGINS`
- `README.md` finalized with correct commands, expected output, and screenshots
- `docs/AI_USAGE.md` filled in with every AI interaction logged

### Checkpoints

- [ ] `docker compose up` → `localhost:3000` → webcam with face box in under 5 min (manual verification)
- [ ] `/api/roi` returns records after a live session (manual verification)
- [x] All automated tests pass (`pytest -v` in backend container)
- [x] No `.env` file committed; `.env.example` is complete and accurate
- [ ] README "stranger test" — a fresh clone, `docker compose up`, works first try

---

## Sprint 4 — Final Review & Submit (Day 6: May 10)

**Goal:** Repo is clean, submission-ready, every rubric point addressed.

### Rubric Checklist

- [x] **Setup & docs** — README + `.env.example`; full manual run depends on Docker install
- [ ] **Version control** — git history tells a story; no "fix fix final v2" commits (your commits before submit)
- [x] **Pragmatism** — three endpoints; thin routers; single ROI table + sessions
- [x] **API design** — REST `GET /api/roi`; WS for ingest + stream; documented in `docs/API.md`
- [x] **Architecture** — router → detector / frame bus → DB (see `docs/ARCHITECTURE.md`)
- [x] **DB schema** — index on `session_id`, FK to `sessions`, Alembic migration `001`
- [x] **Error handling** — no-face ROI; `FRAME_TOO_LARGE` / `INVALID_FRAME`; WS disconnect handling
- [x] **Security** — `.gitignore` for `.env`; `MAX_FRAME_BYTES`; `CORS_ORIGINS`
- [x] **Testing** — unit tests for detector + frame bus + OpenAPI smoke
- [x] **AI usage** — `docs/AI_USAGE.md`
- [x] **PNG diagram** — `diagrams/architecture.png` referenced in README
- [ ] Submit GitHub URL on DevMesh before **2026-05-10 18:00**
