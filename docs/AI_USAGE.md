# AI Usage Attestation

This project was built with the assistance of AI coding tools. Per the assignment
instructions, this document records where and how AI was used, and what was manually
reviewed, verified, or modified.

---

## Tools Used

| Tool | Role |
|------|------|
| Cursor (AI-assisted IDE) | Architecture design, code scaffolding, documentation drafting, refactors |

---

## Usage Log

### Sprint 0 — Architecture & Documentation

| Area | AI contribution | Human verification |
|------|-----------------|--------------------|
| System architecture | Generated initial diagram layout and component descriptions | Reviewed data flow, confirmed it matches the 3-endpoint requirement; adjusted WS protocol details |
| API.md contracts | Drafted WebSocket message schemas and REST response shapes | Verified field names match actual model schemas; added error codes |
| DECISIONS.md | Generated rationale for each technical choice | Confirmed each decision was actually implemented as described |
| ROADMAP.md | Generated sprint breakdown with checkpoints | Adjusted timelines and checkpoint granularity |
| README.md quickstart | Drafted commands and env-var table | Ran `docker compose up` manually to verify commands are correct |

### Sprint 1 — Backend

| Area | AI contribution | Human verification |
|------|-----------------|--------------------|
| Project scaffold | Generated directory structure and boilerplate files | Verified import paths, removed unused stubs |
| `detector.py` | Generated MediaPipe integration using Pillow for decode | Ran detector against test images; confirmed bounding box pixel coordinates are correct |
| `frame_bus.py` | Generated asyncio pub/sub pattern | Reviewed queue maxsize and drop logic; confirmed no deadlock path |
| SQLAlchemy models | Generated `Session` and `ROIRecord` models with async session factory | Verified column types, FK constraints, and index |
| Alembic migration | Generated initial migration script | Ran `alembic upgrade head` against a local DB to confirm it applies cleanly |
| `routers/ingest.py` | Generated WebSocket handler with thread-pool offload | Reviewed concurrency: confirmed `run_in_executor` is awaited before DB write |
| `routers/stream.py` | Generated subscriber loop | Verified disconnect cleanup unsubscribes from bus |
| `routers/roi.py` | Generated REST handler with pagination | Verified 404 for unknown session and 422 for missing session_id |
| Unit tests | Generated test stubs | Filled in assertions, added edge cases (no face, oversized frame, WS disconnect) |

### Sprint 2 — Frontend

The production UI lives in a single [`../frontend/src/App.tsx`](../frontend/src/App.tsx) (Vite + React + TypeScript), not split across separate canvas/hook files.

| Area | AI contribution | Human verification |
|------|-----------------|--------------------|
| `App.tsx` — webcam + canvas | Generated `getUserMedia`, hidden capture canvas + visible display canvas, `toBlob` JPEG send loop, `requestAnimationFrame` draw loop | Confirmed ~120 ms send interval; ROI `strokeRect` aligns with video dimensions in browser |
| `App.tsx` — WebSocket | Generated `/ws/ingest` client: handshake, binary send, JSON `session` / `roi` / `error` handling | Tested with Docker nginx on :3000 and Vite dev proxy on :5173 |
| `App.tsx` — ROI readout | Generated live ROI panel + `GET /api/roi` history table | Spot-checked table vs API response; Vitest tests for message handling and fetch |
| Vitest tests | Generated [`../frontend/src/__tests__/App.test.tsx`](../frontend/src/__tests__/App.test.tsx) and [`canvasOverlay.test.tsx`](../frontend/src/__tests__/canvasOverlay.test.tsx) | Run `npm run test`; updated selectors when UI structure changed |

### Sprint 3 — Integration & Polish

| Area | AI contribution | Human verification |
|------|-----------------|--------------------|
| Frontend error UX | User-facing messages for `getUserMedia` failures, REST `/api/roi` errors (404/422/5xx), network failures; loading state on history fetch; dismissible error alert; connection status chip; `aria-busy` / `role="alert"` | Manual: deny camera permission, bad session fetch, disconnect mid-stream |
| WebSocket lifecycle | On unexpected `onclose`, clear send interval and sync `running` / connection status vs UI | Manual + unit behaviour for `intentionalStopRef` vs disconnect |
| Compose E2E | Added `test_e2e_ws_ingest_one_jpeg_returns_roi_json` in [`../backend/tests/test_e2e_compose.py`](../backend/tests/test_e2e_compose.py) (skipped when stack down) | `docker compose up -d` then `pytest tests/test_e2e_compose.py -v` from host or `docker compose exec backend …` |
| README / screenshots | Stranger-test checklist, 5-minute verification, Docker rebuild note, illustrative PNGs under `docs/images/` | Replace screenshots with real captures if reviewers require production-only assets |
| `docs/AI_USAGE.md` | Rewrote Sprint 2–3 rows to match actual files | This review |

---

## What Was Not AI-Generated

- All architectural decisions (client-side drawing, WebSocket protocol, bounded queue) were
  made by the developer after reasoning through trade-offs. AI provided context and options.
- All tests were run locally before committing. Failing tests were debugged manually.
- Git history and commit messages were written by the developer.
- The README now includes a **stranger-test checklist** and a **5-minute verification** flow; a real fresh-clone run before submission is still recommended.

---

## Limitations Noted

- AI-generated detector code initially used `cv2.imdecode` — this was caught in review and
  replaced with `Pillow.Image.open(io.BytesIO(...))` to comply with the no-OpenCV rule.
- AI-generated Alembic `env.py` used a synchronous engine; updated to async engine pattern
  compatible with `asyncpg`.
