# MegaAI — FastAPI backend

Real-time face ROI detection over WebSocket ingest, ROI persistence in PostgreSQL, and a passive JPEG fan-out stream for viewers.

## Documentation (start here)

All **backend-specific** guides live under **`docs/`** in this folder:

| Doc | What you get |
|-----|----------------|
| [docs/README.md](docs/README.md) | Table of contents and recommended reading order |
| [docs/01_OVERVIEW.md](docs/01_OVERVIEW.md) | Folder layout, lifespan, `app.state` |
| [docs/02_FLOWS.md](docs/02_FLOWS.md) | Ingest, stream, and REST ROI execution paths |
| [docs/03_MODULE_REFERENCE.md](docs/03_MODULE_REFERENCE.md) | File-by-file map + links to tests |
| [docs/04_DATABASE.md](docs/04_DATABASE.md) | Models, Alembic, two session patterns |
| [docs/05_TESTING.md](docs/05_TESTING.md) | Pytest, fixtures, E2E skips |
| [docs/06_BACKEND_SPRINTS.md](docs/06_BACKEND_SPRINTS.md) | Backend-only learning sprints |

Repo-wide contracts and diagrams: [../docs/API.md](../docs/API.md), [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md), [../docs/SPRINT_1/BACKEND_CORE.md](../docs/SPRINT_1/BACKEND_CORE.md).

## Quick commands

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
python scripts/download_face_detector_model.py
cp ../.env.example .env   # adjust DATABASE_URL if not using Docker Postgres

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- OpenAPI UI: http://localhost:8000/docs  
- Run tests: `pytest -v` (from this directory, with `pythonpath` set by `pytest.ini`)

## Layout

```
backend/
├── README.md           ← you are here
├── docs/               ← implementation guides
├── app/                ← FastAPI application package
├── alembic/            ← migrations
├── tests/              ← pytest
├── models/             ← BlazeFace TFLite asset
├── scripts/            ← model download helper
├── requirements.txt
├── Dockerfile
└── pytest.ini
```
