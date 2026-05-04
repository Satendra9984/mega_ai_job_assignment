# Local Python and FastAPI (backend without rebuilding the image)

**Python not installed or `python` does not work (Windows)?** See [INSTALL_PYTHON_WINDOWS.md](INSTALL_PYTHON_WINDOWS.md) first.

Use this when you want **hot reload** or faster iteration by running **Uvicorn** on your machine while optionally still using **Docker only for Postgres** (or Postgres installed locally).

## Supported versions

- **Python**: **3.11+** (matches [backend/Dockerfile](../../backend/Dockerfile) `FROM python:3.11-slim`).
- **FastAPI**: pinned in [backend/requirements.txt](../../backend/requirements.txt) (e.g. `fastapi==0.111.0`).

## Create a virtual environment

From the `backend/` directory:

**Linux / macOS**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Face detector model (MediaPipe Tasks)

The backend loads **BlazeFace short-range** from `backend/models/blaze_face_short_range.tflite` (committed in the repo). If that file is missing, run from `backend/`:

```bash
python scripts/download_face_detector_model.py
```

## Environment file

For **native PostgreSQL on your machine** (no Docker `db` service), hostname **`db` in `DATABASE_URL` will fail** on the host — use **`localhost`** and set **`CORS_ORIGINS`** for **http://localhost:5173** when using Vite. Step-by-step: [LOCAL_POSTGRES_NATIVE.md](LOCAL_POSTGRES_NATIVE.md).

Copy the root env template and adjust if needed:

```bash
# from repo root
cp .env.example .env
```

For API on the **host** connecting to Postgres **in Docker**:

1. Publish Postgres port **5432** on `db` (see [POSTGRESQL.md](POSTGRESQL.md) — optional `ports` mapping), **or** run Postgres another way.
2. Set in `.env` (or `backend/.env` if you load from there):

   ```text
   DATABASE_URL=postgresql+asyncpg://megaai:megaai@localhost:5432/megaai
   ```

   Use the same user/password/database as `POSTGRES_*` in `.env`.

The app loads settings via `pydantic-settings` from environment variables; keeping a single `.env` at the repo root is usually simplest.

**Note:** `.env.example` shows `@db:5432` — that hostname only resolves **inside** the Compose network. On the host, use **`localhost`** (and expose the port).

## Run the development server

Working directory must be `backend/` so `app` resolves:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive docs: **http://localhost:8000/docs**
- OpenAPI JSON: **http://localhost:8000/openapi.json**

## Verify Python and FastAPI are available

Run after activating the venv and installing requirements:

```bash
python --version
# Expect: Python 3.11.x (or newer if you intentionally use a newer interpreter)

pip show fastapi uvicorn sqlalchemy asyncpg
python -c "import fastapi; print('fastapi', fastapi.__version__)"
```

Quick import smoke test (starts no server):

```bash
python -c "from app.main import app; print(app.title)"
```

## Alembic from the host

If `DATABASE_URL` points to a reachable Postgres:

```bash
cd backend
alembic upgrade head
```

Uses sync URL conversion in `alembic/env.py` (see [POSTGRESQL.md](POSTGRESQL.md)).

## MediaPipe and native OS quirks

The Dockerfile installs several **system libraries** for MediaPipe ([backend/Dockerfile](../../backend/Dockerfile)). On **Linux**, you may need analogous packages. On **Windows**, native installs can be painful; **running the backend in Docker** is the most reproducible path for this assignment.

If `import mediapipe` or detection fails on the host, prefer:

```bash
docker compose up --build
docker compose exec backend pytest -v
```

## Tests

```bash
cd backend
pytest -v
```

Requires the same `DATABASE_URL` as migration/tests expect; unit tests for detector/frame bus do not need Postgres, but full-stack checks do.
