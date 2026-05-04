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

```bash
cd backend
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
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
│   └── ROADMAP.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   │       └── 001_create_roi_records.py
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
