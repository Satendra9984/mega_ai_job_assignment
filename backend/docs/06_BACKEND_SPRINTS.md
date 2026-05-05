# Backend-only learning sprints

These sprints are **small, backend-scoped** steps so you can understand and change the server **without** re-reading the entire repo. Dates and submission deadlines live in the product roadmap: [../docs/ROADMAP.md](../docs/ROADMAP.md).

Each sprint below has: **Goal**, **Read list**, **Hands-on exercises**, **Definition of done**.

---

## Sprint B0 — Onboard (half day)

**Goal:** Run tests locally, trace one request mentally from code to DB.

**Read list (in order):**

1. [docs/README.md](README.md) (this folder’s index)
2. [01_OVERVIEW.md](01_OVERVIEW.md)
3. [02_FLOWS.md](02_FLOWS.md) — ingest flow only, first pass

**Hands-on:**

- `cd backend && pytest -v` — note which tests are **skipped** (E2E) vs passed.
- Open [`app/routers/ingest.py`](../app/routers/ingest.py) and follow the variable `frame_index` through one success path and one error path (oversized frame).

**Definition of done:**

- [ ] You can explain aloud: handshake → first JPEG → DB row → ROI JSON → `frame_bus.publish`.
- [ ] `pytest -v` is green on your machine (skips allowed for E2E).

---

## Sprint B1 — REST and DB read path (half day)

**Goal:** Own `GET /api/roi` end-to-end.

**Read list:**

1. [03_MODULE_REFERENCE.md](03_MODULE_REFERENCE.md) — `roi.py`, `database.py`, models
2. [04_DATABASE.md](04_DATABASE.md) — `Depends(get_db)` pattern
3. [`tests/test_roi_api.py`](../tests/test_roi_api.py)

**Hands-on:**

- Add a temporary log line in [`roi.py`](../app/routers/roi.py) after `total` is computed; hit the endpoint with curl or browser; remove the log.
- Write a one-sentence comment in your notes: why `404` vs `422` happens for `/api/roi`.

**Definition of done:**

- [ ] You can describe pagination fields (`total`, `limit`, `offset`, `records`) without opening `API.md`.
- [ ] You know which test asserts “offset beyond total → empty list”.

---

## Sprint B2 — WebSocket ingest and detector (1 day)

**Goal:** Connect MediaPipe thread offload to non-blocking asyncio.

**Read list:**

1. [02_FLOWS.md](02_FLOWS.md) — full ingest section
2. [`services/detector.py`](../app/services/detector.py)
3. [`tests/test_ws_ingest.py`](../tests/test_ws_ingest.py)

**Hands-on:**

- Trace `run_in_executor` in [`ingest.py`](../app/routers/ingest.py): what runs on the worker thread vs what stays on the event loop?
- Change nothing; diagram on paper: one frame’s async timeline.

**Definition of done:**

- [ ] You can explain why `INVALID_FRAME` does not increment `frame_index`.
- [ ] You know where the BlazeFace model file path is resolved (`_DEFAULT_MODEL` in detector).

---

## Sprint B3 — Frame bus and stream (half day)

**Goal:** Understand fan-out and slow-consumer behavior.

**Read list:**

1. [`services/frame_bus.py`](../app/services/frame_bus.py)
2. [`routers/stream.py`](../app/routers/stream.py)
3. [`tests/test_ws_stream.py`](../tests/test_ws_stream.py), [`tests/test_frame_bus.py`](../tests/test_frame_bus.py)

**Hands-on:**

- Read `publish` drop-behind logic: what happens if a subscriber’s queue is full?

**Definition of done:**

- [ ] You can explain why stream viewers may miss intermediate frames but should see the latest when they catch up.

---

## Sprint B4 — E2E against Compose (optional)

**Goal:** Run optional smoke tests against a real stack.

**Read list:**

1. [05_TESTING.md](05_TESTING.md) — E2E section
2. [`tests/test_e2e_compose.py`](../tests/test_e2e_compose.py)

**Hands-on:**

- `docker compose up -d` then `pytest tests/test_e2e_compose.py -v` from host with `websocket-client` installed in your venv.

**Definition of done:**

- [ ] E2E tests pass when stack is healthy, skip cleanly when not.

---

## After these sprints

Pick a **single** improvement (metrics, rate limit, structured logging, auth, etc.) as a new Sprint B5 and repeat the same pattern: read list → small change → tests → doc note in this file or a new `backend/docs/deepdives/<topic>.md`.

---

## Sprint B5 — ROI pagination hardening (1 day)

**Goal:** Make `/api/roi` stable and efficient while ingestion continuously writes new rows.

**Read list:**

1. [`app/routers/roi.py`](../app/routers/roi.py)
2. [`tests/test_roi_api.py`](../tests/test_roi_api.py)
3. [../../docs/API.md](../../docs/API.md) — ROI endpoint contract

**Hands-on:**

- Implement cursor-first pagination with deterministic sort (`detected_at DESC, id DESC`).
- Keep `limit` + `offset` compatibility mode for existing clients.
- Add frozen snapshot semantics (`snapshot` token) so multi-page reads do not drift under live inserts.
- Add migration index aligned to query pattern (`session_id`, `detected_at`, `id`).
- Add tests for malformed tokens and snapshot behavior during concurrent inserts.

**Definition of done:**

- [ ] Cursor pagination returns `next_cursor`, `snapshot`, and `has_more`.
- [ ] No duplicate/skip rows across cursor pages while new records are inserted.
- [ ] Existing offset calls still succeed without contract break.
- [ ] `pytest -v` passes with new cursor/snapshot tests.
