# Sprint 1 — Backend, Docker, and PostgreSQL

This folder documents how to run and operate the **FastAPI backend** with **Docker Compose** and **PostgreSQL**, how to verify **Python / FastAPI** locally, and how to confirm **Sprint 1** is fully operational.

## Who this is for

- Developers bringing up the stack for the first time
- Reviewers checking that the backend, database, and migrations work end-to-end
- Anyone debugging Docker or database connectivity issues

**If Docker or Python are not installed yet on Windows**, start with the installation guides before the other docs:

- [INSTALL_DOCKER_WINDOWS.md](INSTALL_DOCKER_WINDOWS.md) — install WSL2 + Docker Desktop, then run the project
- [INSTALL_PYTHON_WINDOWS.md](INSTALL_PYTHON_WINDOWS.md) — fix `python` / Store alias, install Python 3.11 (or use 3.12), venv, run the backend locally

## Documents

| Document | Description |
|----------|-------------|
| [INSTALL_DOCKER_WINDOWS.md](INSTALL_DOCKER_WINDOWS.md) | **Start here (Windows):** what Docker is, WSL2, Docker Desktop install, first `docker compose up`, how services connect |
| [INSTALL_PYTHON_WINDOWS.md](INSTALL_PYTHON_WINDOWS.md) | **Start here (Windows):** install/fix Python, venv, `pip install`, run Uvicorn and pytest on the host |
| [DOCKER.md](DOCKER.md) | Docker Desktop / Engine prerequisites, `docker compose` commands, services, ports, networks, volumes, troubleshooting |
| [POSTGRESQL.md](POSTGRESQL.md) | Connection URLs, schema (`sessions`, `roi_records`), Alembic migrations, optional host port for GUI tools, backups |
| [LOCAL_PYTHON_AND_FASTAPI.md](LOCAL_PYTHON_AND_FASTAPI.md) | Running Uvicorn on the host (venv, dependencies, version checks) |
| [LOCAL_POSTGRES_NATIVE.md](LOCAL_POSTGRES_NATIVE.md) | **Native Postgres on Windows:** `DATABASE_URL` with `localhost`, `.env` cwd, Alembic, CORS for Vite (:5173), troubleshooting vs Docker |
| [SPRINT_1_UP_AND_RUNNING.md](SPRINT_1_UP_AND_RUNNING.md) | Sprint 1 checklist with copy-paste verification commands |

## Happy path (full stack)

From the **repository root** (where `docker-compose.yml` lives):

```bash
cp .env.example .env
docker compose up --build
```

When containers are healthy:

- API docs: **http://localhost:8000/docs**
- OpenAPI JSON: **http://localhost:8000/openapi.json**
- Frontend (if built): **http://localhost:3000**

The backend container runs **`alembic upgrade head`** before starting Uvicorn, so PostgreSQL tables are created or upgraded automatically.

## Related project docs

- [../ARCHITECTURE.md](../ARCHITECTURE.md) — system design
- [../API.md](../API.md) — REST and WebSocket contracts
- [../ROADMAP.md](../ROADMAP.md) — sprint goals and checkpoints
