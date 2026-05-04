# Sprint 0 — Foundation [DONE]

**Completed:** 2026-05-04  
**Commit:** `chore: foundation setup — Docker, docs, MediaPipe Tasks, Python 3.14 deps`

This sprint established the reproducible baseline that all subsequent sprints build on. No
feature code ships in Sprint 0; everything here is scaffolding, contracts, and decisions.

---

## What was established

### Architecture & contracts

| Document | Purpose |
|----------|---------|
| [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) | System diagram (Mermaid + PNG), component descriptions, data-flow notes |
| [docs/API.md](../docs/API.md) | Full endpoint contracts: WS message shapes, REST request/response schemas, error codes |
| [docs/DECISIONS.md](../docs/DECISIONS.md) | Six numbered ADRs (client-side ROI, no OpenCV, WS ingest, Postgres, bounded queues, React+Nginx) |
| [docs/AI_USAGE.md](../docs/AI_USAGE.md) | Mandatory AI attestation log; updated each sprint |
| [diagrams/architecture.png](../diagrams/architecture.png) | Exported PNG required by assignment rubric |

### Repository skeleton

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Three services: `db` (Postgres), `backend` (FastAPI), `frontend` (React + Nginx) |
| `.env.example` | All environment variables with sane defaults for local dev |
| `.gitignore` | Python, Node, Docker artefacts excluded; `.env` never committed |
| `backend/requirements.txt` | Pinned Python dependencies with Python 3.14 compatibility notes |
| `backend/Dockerfile` | `python:3.11-slim` with `libgl1` + `libgles2` (MediaPipe native lib needs `libGLESv2.so.2`) |
| `backend/alembic/` | Initial migration `001_initial_sessions_roi.py` creating `sessions` + `roi_records` |
| `backend/models/blaze_face_short_range.tflite` | BlazeFace model bundled (~230 KB) |

### Key decisions locked in Sprint 0

1. **Client-side ROI drawing** — backend sends raw JPEG + ROI JSON; canvas drawn in browser.
2. **MediaPipe Tasks API** — migrated from deprecated `mp.solutions` to `mediapipe.tasks.python.vision.FaceDetector` (Python 3.14 compatible).
3. **WebSocket for ingest** — `/ws/ingest` for real-time frame streaming, not batch HTTP.
4. **PostgreSQL + Alembic** — async SQLAlchemy sessions, schema versioned from day one.
5. **Bounded `asyncio.Queue` (maxsize=2)** — drop-behind policy prevents memory growth on slow stream viewers.

### Sprint 1 operational guides (also committed in Sprint 0)

- [docs/SPRINT_1/INSTALL_DOCKER_WINDOWS.md](SPRINT_1/INSTALL_DOCKER_WINDOWS.md)
- [docs/SPRINT_1/INSTALL_PYTHON_WINDOWS.md](SPRINT_1/INSTALL_PYTHON_WINDOWS.md)
- [docs/SPRINT_1/DOCKER.md](SPRINT_1/DOCKER.md)
- [docs/SPRINT_1/POSTGRESQL.md](SPRINT_1/POSTGRESQL.md)
- [docs/SPRINT_1/LOCAL_PYTHON_AND_FASTAPI.md](SPRINT_1/LOCAL_PYTHON_AND_FASTAPI.md)
- [docs/SPRINT_1/SPRINT_1_UP_AND_RUNNING.md](SPRINT_1/SPRINT_1_UP_AND_RUNNING.md)

---

## Definition of Done — Sprint 0

- [x] Architecture diagram reviewed and exported to PNG
- [x] All three endpoint shapes agreed (path, WS vs REST, payload in/out)
- [x] Face detection library chosen — MediaPipe Tasks (BlazeFace short-range, no `cv2` in app code)
- [x] DB schema drafted — `sessions` + `roi_records` tables with FK + index
- [x] Docker Compose boots all three services (backend, frontend, db)
- [x] Foundation commit pushed to GitHub main branch
