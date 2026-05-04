# Docker and Docker Compose

**Docker not installed yet (Windows)?** See [INSTALL_DOCKER_WINDOWS.md](INSTALL_DOCKER_WINDOWS.md) first.

This project runs the **backend**, **PostgreSQL**, and **frontend** as services defined in `docker-compose.yml` at the repository root.

## Prerequisites

- **Docker Engine** ≥ 24 (or **Docker Desktop** on Windows/macOS) with **Compose V2**
- Verify the CLI:
  ```bash
  docker --version
  docker compose version
  ```
  You should see `docker compose` (space), not only the legacy `docker-compose` binary.

- **Resources**: First image build pulls Python, Node, and Postgres layers (~several hundred MB). Ensure enough disk space (WSL2 users: check virtual disk usage if builds fail with “no space left”).

## One-time setup

From the repo root:

```bash
cd megaai    # or your clone directory
cp .env.example .env
```

The default `.env.example` values work with Compose. The `backend` service **overrides** `DATABASE_URL` in `docker-compose.yml` so the hostname is `db` inside the Docker network (see [POSTGRESQL.md](POSTGRESQL.md)).

## Core commands

| Goal | Command |
|------|---------|
| Build images and start all services (foreground logs) | `docker compose up --build` |
| Start in background | `docker compose up -d --build` |
| Stop containers | `docker compose down` |
| Stop and **delete Postgres data** | `docker compose down -v` |
| Follow logs | `docker compose logs -f` |
| Logs for one service | `docker compose logs -f backend` |
| Run a shell in the backend container | `docker compose exec backend sh` |
| Run tests inside backend | `docker compose exec backend pytest -v` |

After code changes to `backend/` or `frontend/`, rebuild:

```bash
docker compose up --build
```

## Services (matrix)

| Service | Image / build | Host ports | Role |
|---------|----------------|------------|------|
| `db` | `postgres:16-alpine` | *(none by default — internal only)* | PostgreSQL 16, persistent data in volume `postgres_data` |
| `backend` | Built from `./backend` (`Dockerfile`, Python 3.11) | **8000** → 8000 | FastAPI + Alembic migrations + Uvicorn |
| `frontend` | Built from `./frontend` | **3000** → 80 (nginx) | Static React app; proxies `/ws/*` and `/api/*` to backend |

## Networking

- All services attach to **`megaai_net`** (bridge). Service DNS names match Compose service names: `backend`, `db`, `frontend`.
- The backend connects to Postgres at host **`db`**, port **5432** (internal).

## Startup order and health

- `backend` has `depends_on: db` with **`condition: service_healthy`**.
- The `db` service defines a **`healthcheck`** (`pg_isready`) so the backend does not start until Postgres accepts connections.

## Backend container lifecycle

From [backend/Dockerfile](../../backend/Dockerfile):

1. `alembic upgrade head` — applies SQL migrations.
2. `uvicorn app.main:app --host 0.0.0.0 --port 8000` — serves the API.

If migrations fail, the container exits; check `docker compose logs backend`.

## Troubleshooting

### Port already in use

- **8000** or **3000** taken by another process: stop that process or change the left side of `ports:` in `docker-compose.yml` (e.g. `"8001:8000"`).

### Build fails or very slow

- Run `docker compose build --no-cache backend` once to rule out a bad cache layer.
- On Windows, ensure Docker Desktop is running and WSL2 backend has enough memory/disk.

### Backend restarts in a loop

- Read logs: `docker compose logs backend`.
- Typical causes: cannot reach `db`, wrong `DATABASE_URL`, or Alembic error (e.g. DB not ready — rare because of `depends_on` + healthcheck).

### Cannot connect to Postgres from the host

- By default **5432 is not published** to the host. Use `docker compose exec db psql …` (see [POSTGRESQL.md](POSTGRESQL.md)) or add an optional `ports` mapping for local GUI tools (documented there — dev-only).

### Clean slate

```bash
docker compose down -v
docker compose up --build
```

This removes the named volume and **wipes all ROI data**.
