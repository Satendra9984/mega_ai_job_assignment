# MegaAI — Real-Time Face ROI Streaming

## What you are evaluating

This project is a **full-stack real-time face streaming demo**. The browser captures webcam frames, sends **binary JPEG** over **WebSocket** (`/ws/ingest`), the **FastAPI** backend runs a **MediaPipe BlazeFace** detector, persists **ROI** (bounding-box) metadata in **PostgreSQL**, and returns **JSON** per frame. A **React** app draws the ROI on a **canvas** in the browser and can **fetch persisted rows** via **`GET /api/roi`**. Judges can verify end-to-end behavior in under five minutes using **Docker Compose** (recommended path below).

## Stack

| Layer | Technology |
|-------|------------|
| API | **FastAPI**, **Uvicorn** |
| Database | **PostgreSQL 16** (Compose image), **SQLAlchemy 2.x** (async), **asyncpg**, **Alembic** migrations |
| Detection | **MediaPipe Tasks** — BlazeFace short-range **TFLite** (~230 KB), no OpenCV-Python in application code |
| Frontend | **React**, **Vite**, **TypeScript**, **Vitest** |
| Containers | **Docker Compose** — `db`, `backend`, `frontend` (nginx serves UI on **:3000**) |

Deeper design and message contracts: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/API.md](docs/API.md).

## Architecture

```
Browser (React)
  │  binary JPEG frames           ROI JSON {x,y,w,h}
  │──────────────────▶ WS /ws/ingest ──▶ Face Detector ──▶ PostgreSQL
  │◀──────────────────────────────────────────────────────▶ GET /api/roi
  │  binary frames
  │◀────────────────── WS /ws/stream ◀── Frame Bus ◀──────────────────
```

Diagram asset: [diagrams/architecture.png](diagrams/architecture.png).

---

## Prerequisites

**Path A (Docker — recommended for reviewers)**

- **Docker** ≥ 24 and **Docker Compose v2** (`docker compose`, not `docker-compose`)
- A **webcam** reachable from the browser

**Path B (native development)**

- **Python** 3.11+ (matches backend Docker image; 3.14 may work locally with warnings)
- **Node.js** LTS (for `npm run dev`)
- **PostgreSQL** 15+ if you run the database outside Compose (see [Native PostgreSQL checklist](#native-postgresql-checklist))

---

## Path A — Full Docker (recommended)

This is the **shortest path** for judges and users: one clone, one Compose command, UI on **http://localhost:3000**.

### Why tables exist without manual steps

The backend container entrypoint runs **`alembic upgrade head`** before **`uvicorn`** ([backend/Dockerfile](backend/Dockerfile)), so `sessions`, `roi_records`, and **`alembic_version`** are created automatically. You do **not** need to run Alembic manually when using the full stack in Docker.

### Run

**Linux/macOS (Bash):**

```bash
git clone <repo-url>
cd megaai

cp .env.example .env

docker compose up --build
# or: make up
```

**Windows (PowerShell):**

```powershell
git clone <repo-url>
Set-Location megaai

Copy-Item .env.example .env

docker compose up --build
```

First full build typically takes **2–3 minutes**; later starts are faster.

Open **http://localhost:3000**, allow camera access, and click **Start webcam**. With a face in frame, a **cyan** ROI rectangle appears on the video; status shows **Live**; **FPS** reflects ROI message cadence.

### Video proof (configured setup)

A full working demo recording for the documented configurations is available here: [OneDrive video proof](https://1drv.ms/v/c/105c6069263297c8/IQCnGFBDiblhRLvM29kc12OAAaXETxh0dgHbBD_uA1OyuS8?e=bLdP03).

### Stop

**All platforms (Docker CLI):**

```bash
docker compose down           # stop containers
docker compose down -v       # stop and remove Postgres volume (wipes DB data)
```

### Verification checklist (full stack)

1. Containers healthy: `backend`, `db`, `frontend`.
2. **http://localhost:3000** loads; **Start webcam** enables **Live**.
3. **Current ROI (live)** shows frame index, confidence, bbox, face yes/no.
4. **Fetch ROI history (sample)** shows persisted rows or an empty-message path.
5. **Stop** returns status to idle.
6. Optional one-command check: `make verify` (prints `backend OK` and `frontend OK`).

Optional: `GET http://localhost:8000/api/roi?session_id=<uuid>` (session UUID appears in the UI after streaming).

### Stranger test (fresh evaluation)

Use a **new empty directory** clone with **no leftover `.env` or Docker volumes**:

1. `git clone … && cd megaai`
2. copy env file:
   - Bash: `cp .env.example .env`
   - PowerShell: `Copy-Item .env.example .env`
3. `docker compose up --build`
4. Repeat the verification checklist above.

**Rebuild after code edits:** Compose images bake the code; run `docker compose up --build` (or rebuild the affected service) so containers pick up changes.

**Security:** Never commit **`backend/.env`** or secrets. Only [.env.example](.env.example) belongs in git.

---

## Path B — Native development

Use when you want **hot reload** for backend or frontend **without rebuilding Docker images**.

- **Backend** listens on **:8000** (Uvicorn).
- **Frontend** dev server runs on **:5173** and **proxies** `/ws` and `/api` to the API — **do not** use port **3000** for UI unless the **Docker frontend/nginx** stack is running (see [Troubleshooting](#troubleshooting)).

```mermaid
flowchart LR
  subgraph DockerPath [PathA_Docker]
    Clone[Clone_repo]
    Env[cp_env_example]
    Up[docker_compose_up]
    UI3000[Browser_port_3000]
    Clone --> Env --> Up --> UI3000
  end
  subgraph NativePath [PathB_Native]
    Venv[venv_and_dependencies]
    Alembic[alembic_upgrade_head]
    Uvicorn[uvicorn_port_8000]
    Vite[npm_run_dev_5173]
    Venv --> Alembic --> Uvicorn
    Vite -.->|"proxy"| Uvicorn
  end
```

### B1 — Backend

**Linux/macOS (Bash):**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python scripts/download_face_detector_model.py

cp ../.env.example .env
# Edit .env if your Postgres host, port, or credentials differ.
alembic upgrade head

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Windows (PowerShell):**

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python scripts/download_face_detector_model.py

Copy-Item ..\.env.example .env
# Edit .env if your Postgres host, port, or credentials differ.
alembic upgrade head

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive OpenAPI: **http://localhost:8000/docs**

Full Windows/native Postgres narrative: [docs/SPRINT_1/LOCAL_POSTGRES_NATIVE.md](docs/SPRINT_1/LOCAL_POSTGRES_NATIVE.md)

### B2 — Frontend

**Linux/macOS (Bash):**

```bash
cd frontend
npm install
npm run dev
```

**Windows (PowerShell):**

```powershell
Set-Location frontend
npm install
npm run dev
```

Open **http://localhost:5173** — not `:3000` — when only **host Uvicorn** is running.

---

## Database URLs: Docker versus host

Understanding this avoids the most common “works in Docker, fails on my PC” confusion.

| Where the API runs | Where Postgres is | Typical `DATABASE_URL` host |
|--------------------|-------------------|----------------------------|
| **Backend container** (Compose) | **`db` container** | Compose **overrides** `DATABASE_URL` to use host **`db`** ([docker-compose.yml](docker-compose.yml)). |
| **Uvicorn on your machine** | Postgres on same PC, WSL, or published container port | Use **`localhost`** or **`127.0.0.1`** plus the correct **port**. |

**Important:**

- **`db`** resolves **only inside** the Compose network. Running Uvicorn on Windows/macOS/Linux **host** with `@db` in `DATABASE_URL` causes **`getaddrinfo failed`**.
- [.env.example](.env.example) defaults to **`localhost`** for **native** workflows; Compose still injects **`@db`** for the backend service environment.

Detailed mode table: [docs/SPRINT_1/LOCAL_POSTGRES_NATIVE.md](docs/SPRINT_1/LOCAL_POSTGRES_NATIVE.md).

---

## Native PostgreSQL checklist

Minimum steps when **not** using the Compose `db` service:

1. **Create role and database** (example matches `.env.example`):

   ```sql
   CREATE USER megaai WITH PASSWORD 'megaai';
   CREATE DATABASE megaai OWNER megaai;
   GRANT ALL PRIVILEGES ON DATABASE megaai TO megaai;
   ```

   Then connect to database `megaai` and run:

   ```sql
   GRANT ALL ON SCHEMA public TO megaai;
   ```

   If using `psql`, you can switch DB with:

   ```text
   \c megaai
   ```

2. **Apply schema** from `backend/`:

   **Linux/macOS (Bash):**

   ```bash
   cd backend
   alembic upgrade head
   ```

   **Windows (PowerShell):**

   ```powershell
   Set-Location backend
   alembic upgrade head
   ```

3. **PostgreSQL 15+ (`permission denied for schema public`)**

   New databases may not grant `CREATE` on `public` to non-owners. As superuser (e.g. `postgres`) on database **`megaai`**:

   ```sql
   GRANT CREATE, USAGE ON SCHEMA public TO megaai;
   ```

   Alternative: `ALTER SCHEMA public OWNER TO megaai;` for a DB dedicated to this app.

4. **Align `DATABASE_URL`** in `backend/.env`:

   ```text
   DATABASE_URL=postgresql+asyncpg://megaai:megaai@localhost:5432/megaai
   ```

   Use **`127.0.0.1`**, non-default ports, or URL-encoded passwords if your setup requires it.

---

## Endpoints

| # | Type | Path | Purpose |
|---|------|------|---------|
| 1 | WebSocket | `ws://localhost:8000/ws/ingest` | Send webcam frames; receive ROI JSON per frame |
| 2 | WebSocket | `ws://localhost:8000/ws/stream` | Receive fan-out JPEG frames after ingest |
| 3 | REST GET | `http://localhost:8000/api/roi` | Query persisted ROI rows by `session_id` |

Note: Via Docker UI on **:3000**, the browser typically uses **`ws://localhost:3000/ws/...`** — nginx proxies to the backend ([frontend/nginx.conf](frontend/nginx.conf)).

Full schemas: [docs/API.md](docs/API.md).

---

## Environment variables

See [.env.example](.env.example). Highlights:

| Variable | Role |
|----------|------|
| `DATABASE_URL` | Async SQLAlchemy URL (**`postgresql+asyncpg://`**). Native default uses **`localhost`**; Compose **overrides** to **`db`** for the backend service. |
| `MAX_FRAME_BYTES` | Maximum accepted JPEG payload (default 1 MB). |
| `DETECTION_CONFIDENCE` | MediaPipe BlazeFace detection threshold. |
| `CORS_ORIGINS` | Allowed browser origins — include **`http://localhost:5173`** when using Vite-only dev alongside a local API. |
| `VITE_WS_BASE` / `VITE_API_BASE` | Frontend build/runtime bases (Compose typically uses `:3000` nginx). |

---

## Tests

**Backend** (expects venv activated, from `backend/`):

**Linux/macOS (Bash):**

```bash
pytest -v
```

**Windows (PowerShell):**

```powershell
pytest -v
# If pytest is not on PATH in your venv:
python -m pytest -v
```

**Frontend** (from `frontend/`):

**All platforms (npm):**

```bash
npm run test
```

**Inside running Compose** (optional):

**All platforms (Docker CLI):**

```bash
docker compose exec backend pytest -v
```

Latest local run: backend **31** tests, frontend **19** tests (Vitest).

---

## Troubleshooting

| Symptom | Likely cause | What to try |
|---------|---------------|-------------|
| WebSocket fails on **`localhost:3000`** but you only run **host Uvicorn** | Port **3000** is **nginx inside Docker**, proxying to the **backend container** — not your PC’s Uvicorn | Use **`http://localhost:5173`** with `npm run dev`, or bring up **full Docker** for **:3000**. |
| **`getaddrinfo failed`** when ingesting | `DATABASE_URL` uses **`db`** while API runs **on host** | Set host to **`localhost`** / reachable IP in `backend/.env`. |
| **`password authentication failed for user megaai`** | Wrong password or role misconfigured | `ALTER ROLE megaai WITH PASSWORD 'megaai';` or match `.env`; confirm with `psql`. |
| **`relation "sessions" does not exist`** | Schema not migrated | **`alembic upgrade head`** from `backend/` (Docker does this automatically in the container). |
| **`permission denied for schema public`** (Alembic) | PostgreSQL **15+** default privileges | `GRANT CREATE, USAGE ON SCHEMA public TO megaai;` (see [Native PostgreSQL checklist](#native-postgresql-checklist)). |
| ROI history pages show duplicates/skips while stream is active | Offset pagination drifts under concurrent inserts | Use cursor pagination (`use_cursor=true`) and pass returned `next_cursor` + `snapshot` across pages. |

---

## Screenshots and live UI

The committed mockups illustrate the dashboard layout:

| Live stream + ROI overlay | ROI history |
|---------------------------|-------------|
| ![Live ROI](docs/images/app-ui-live.png) | ![ROI history](docs/images/app-ui-history.png) |

The **running React app** (after the dashboard redesign) follows the same structure: navy theme, cyan ROI overlay, ROI stats grid, ROI history table, and coordinate info callout.

---

## Project structure

```
megaai/
├── README.md
├── .env.example
├── docker-compose.yml
├── diagrams/
│   └── architecture.png
├── docs/
│   ├── images/                 README / Sprint screenshots
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
│       ├── LOCAL_POSTGRES_NATIVE.md
│       ├── LOCAL_PYTHON_AND_FASTAPI.md
│       └── SPRINT_1_UP_AND_RUNNING.md
├── backend/
│   ├── README.md
│   ├── docs/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── models/                 BlazeFace TFLite (see scripts/)
│   ├── scripts/download_face_detector_model.py
│   ├── alembic/versions/
│   ├── app/                    FastAPI routers, detector, DB models
│   └── tests/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── index.html
    └── src/
        ├── App.tsx
        ├── index.css
        └── __tests__/          Vitest suites
```

---

## Documentation index

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Decisions](docs/DECISIONS.md)
- [AI usage disclosure](docs/AI_USAGE.md)
- [Roadmap](docs/ROADMAP.md)
- Sprint 1 index — install guides, Postgres, Compose: [docs/SPRINT_1/README.md](docs/SPRINT_1/README.md)
- Backend implementation notes: [backend/docs/README.md](backend/docs/README.md)
