# AI Usage Attestation

This project was built with the assistance of AI coding tools. Per the assignment
instructions, this document records where and how AI was used, and what was manually
reviewed, verified, or modified.

---

## Tools Used

| Tool | Role |
|------|------|
| Cursor (Claude Sonnet 4.5) | Architecture design, code scaffolding, documentation drafting |

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

| Area | AI contribution | Human verification |
|------|-----------------|--------------------|
| `VideoCanvas.tsx` | Generated canvas capture + WebSocket send loop | Verified frame rate (requestAnimationFrame vs setInterval), confirmed JPEG encoding via `toBlob` |
| ROI overlay drawing | Generated `ctx.strokeRect` call from ROI state | Verified coordinate mapping matches actual frame dimensions rendered on canvas |
| WebSocket hook | Generated `useWebSocket.ts` with reconnect logic | Reviewed reconnect backoff; confirmed no reconnect storm on server restart |
| `useWebcam.ts` | Generated `getUserMedia` hook | Tested in Chrome and Firefox; confirmed MediaStream cleanup on unmount |
| UI layout | Generated basic Tailwind layout | Adjusted for visual clarity; manually tested responsive behaviour |

### Sprint 3 — Integration & Polish

| Area | AI contribution | Human verification |
|------|-----------------|--------------------|
| Integration tests | Generated pytest-asyncio test for ingest pipeline | Ran against live Docker stack; fixed DB connection string in test config |
| Error handling | Generated try/except blocks for all WS paths | Verified that malformed binary messages do not crash the server |
| nginx config | Generated proxy_pass rules for `/ws/` and `/api/` | Verified WebSocket upgrade headers are forwarded correctly |
| `.env.example` | Generated variable list | Cross-checked against `config.py` to ensure no variable is missing |

---

## What Was Not AI-Generated

- All architectural decisions (client-side drawing, WebSocket protocol, bounded queue) were
  made by the developer after reasoning through trade-offs. AI provided context and options.
- All tests were run locally before committing. Failing tests were debugged manually.
- Git history and commit messages were written by the developer.
- The final README "stranger test" (running the project end-to-end fresh) was done manually.

---

## Limitations Noted

- AI-generated detector code initially used `cv2.imdecode` — this was caught in review and
  replaced with `Pillow.Image.open(io.BytesIO(...))` to comply with the no-OpenCV rule.
- AI-generated Alembic `env.py` used a synchronous engine; updated to async engine pattern
  compatible with `asyncpg`.
