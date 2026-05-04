# Real-Time Face Detection Video Streaming System

A containerized backend API that accepts a live webcam feed over WebSocket, detects faces
using MediaPipe (no OpenCV-Python in application code), persists ROI bounding-box data in
PostgreSQL, and streams the feed back to a React frontend that overlays a rectangle on the
detected face entirely in the browser.

## Architecture

```
Browser (React)
  │  binary JPEG frames           ROI JSON {x,y,w,h}
  │──────────────────▶ WS /ws/ingest ──▶ Face Detector ──▶ PostgreSQL
  │◀──────────────────────────────────────────────────────▶ GET /api/roi
  │  binary frames
  │◀────────────────── WS /ws/stream ◀── Frame Bus ◀──────────────────
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full diagram and component
descriptions, and [diagrams/architecture.png](diagrams/architecture.png) for the visual.

## Quickstart (< 5 minutes)

### Prerequisites

- Docker ≥ 24 and Docker Compose v2 (`docker compose` not `docker-compose`)
- A webcam accessible by your browser

### Run

```bash
git clone <repo-url>
cd megaai

cp .env.example .env          # defaults work for local dev; no edits required

docker compose up --build     # first build ~2-3 min; subsequent runs ~10 s
```

Open **http://localhost:3000** in your browser, allow webcam access, and click **Start**.
A rectangle will appear around your face in real time.

### Stop

```bash
docker compose down           # stop containers
docker compose down -v        # also remove the Postgres volume
```

## Endpoints

| # | Type | Path | Purpose |
|---|------|------|---------|
| 1 | WebSocket | `ws://localhost:8000/ws/ingest` | Send webcam frames; receive ROI JSON per frame |
| 2 | WebSocket | `ws://localhost:8000/ws/stream` | Receive raw video frames (viewer endpoint) |
| 3 | REST GET  | `http://localhost:8000/api/roi` | Query persisted ROI records by session |

Full contracts and message schemas: [docs/API.md](docs/API.md)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://megaai:megaai@db:5432/megaai` | Async SQLAlchemy DB URL |
| `MAX_FRAME_BYTES` | `1048576` | Max accepted frame size (1 MB) |
| `DETECTION_CONFIDENCE` | `0.5` | MediaPipe min detection confidence |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |

See [.env.example](.env.example) for the full list.

## Development (without Docker)

### Backend

**PostgreSQL on Windows without Docker** (role, `DATABASE_URL` with `localhost`, `.env` cwd, CORS for Vite on 5173): [docs/SPRINT_1/LOCAL_POSTGRES_NATIVE.md](docs/SPRINT_1/LOCAL_POSTGRES_NATIVE.md)

**Backend implementation guide (code walkthrough, DB, tests, learning sprints):** [backend/docs/README.md](backend/docs/README.md)

```bash
cd backend
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
python scripts/download_face_detector_model.py   # BlazeFace TFLite (~230 KB) for MediaPipe Tasks
cp ../.env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (Vite; proxies /ws and /api to :8000)
```

### Troubleshooting — WebSocket fails on `localhost:3000`

If Chrome shows `WebSocket connection to 'ws://localhost:3000/ws/ingest' failed`:

- **Cause:** The UI on port **3000** is the **nginx** container from `docker compose`. Nginx forwards `/ws/` to the Docker hostname **`backend:8000`** (see [`frontend/nginx.conf`](frontend/nginx.conf)), i.e. the **backend container** on the Compose network — **not** a separate `uvicorn` process you started only on your PC.
- **Fix (pick one):**
  1. **Full stack in Docker:** `docker compose up --build` and use http://localhost:3000 (backend + db + frontend all running).
  2. **Local backend only:** run `uvicorn` on :8000 as above, then use the **Vite** dev app at http://localhost:5173 (`npm run dev`), which proxies `/ws` and `/api` to `127.0.0.1:8000` — do **not** rely on port 3000 unless the backend container is up.

### Tests

With Python 3.11+ and dependencies installed locally:

```bash
cd backend
pytest -v
```

Or inside the backend container (after `docker compose up --build`):

```bash
docker compose exec backend pytest -v
```

## Project Structure

```
megaai/
├── README.md
├── .env.example
├── docker-compose.yml
├── diagrams/
│   └── architecture.png        ← required by assignment
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DECISIONS.md
│   ├── AI_USAGE.md
│   ├── ROADMAP.md
│   └── SPRINT_1/
│       ├── README.md
│       ├── INSTALL_DOCKER_WINDOWS.md
│       ├── INSTALL_PYTHON_WINDOWS.md
│       ├── DOCKER.md
│       ├── POSTGRESQL.md
│       ├── LOCAL_PYTHON_AND_FASTAPI.md
│       └── SPRINT_1_UP_AND_RUNNING.md
├── backend/
│   ├── README.md               ← backend quickstart; see docs/ for code walkthrough
│   ├── docs/                   ← backend-only implementation guides
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── models/                 ← BlazeFace TFLite (committed; see scripts/ to re-download)
│   ├── scripts/
│   │   └── download_face_detector_model.py
│   ├── alembic/
│   │   └── versions/
│   │       └── 001_initial_sessions_roi.py
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   └── services/
│   └── tests/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/
        ├── App.tsx
        ├── components/
        └── hooks/
```

## Documentation Index

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Decisions](docs/DECISIONS.md)
- [AI Usage](docs/AI_USAGE.md)
- [Roadmap](docs/ROADMAP.md)

### Sprint 1 — Backend, Docker, and PostgreSQL

Step-by-step guides for Compose, Postgres, local Python/FastAPI, and the Sprint 1 “up and running” checklist:

- **Windows — install from scratch:** [docs/SPRINT_1/INSTALL_DOCKER_WINDOWS.md](docs/SPRINT_1/INSTALL_DOCKER_WINDOWS.md), [docs/SPRINT_1/INSTALL_PYTHON_WINDOWS.md](docs/SPRINT_1/INSTALL_PYTHON_WINDOWS.md)
- [docs/SPRINT_1/README.md](docs/SPRINT_1/README.md) (index)
- [docs/SPRINT_1/DOCKER.md](docs/SPRINT_1/DOCKER.md)
- [docs/SPRINT_1/POSTGRESQL.md](docs/SPRINT_1/POSTGRESQL.md)
- [docs/SPRINT_1/LOCAL_PYTHON_AND_FASTAPI.md](docs/SPRINT_1/LOCAL_PYTHON_AND_FASTAPI.md)
- [docs/SPRINT_1/SPRINT_1_UP_AND_RUNNING.md](docs/SPRINT_1/SPRINT_1_UP_AND_RUNNING.md)
