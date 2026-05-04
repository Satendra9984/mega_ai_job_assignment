# Backend documentation index

Read in this order the first time you touch the codebase.

## Recommended reading order

1. **[01_OVERVIEW.md](01_OVERVIEW.md)** — What lives where, how the app boots, what `app.state` holds.
2. **[02_FLOWS.md](02_FLOWS.md)** — Step-by-step behavior of `/ws/ingest`, `/ws/stream`, and `GET /api/roi`.
3. **[03_MODULE_REFERENCE.md](03_MODULE_REFERENCE.md)** — One section per Python module under `app/`; links to tests.
4. **[04_DATABASE.md](04_DATABASE.md)** — Tables, Alembic, and why ingest uses a different session path than the REST router.
5. **[05_TESTING.md](05_TESTING.md)** — How `conftest.py` replaces Postgres with SQLite for tests; E2E compose tests.
6. **[06_BACKEND_SPRINTS.md](06_BACKEND_SPRINTS.md)** — Small backend-only sprints (read, trace, extend) with checklists.

## Repo-wide references (outside `backend/`)

| Topic | Location |
|-------|----------|
| HTTP/WS message contracts | [../docs/API.md](../docs/API.md) |
| System architecture (browser, nginx, DB) | [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) |
| Sprint 1 backend diagrams (Mermaid) | [../docs/SPRINT_1/BACKEND_CORE.md](../docs/SPRINT_1/BACKEND_CORE.md) |
| ADRs and rationale | [../docs/DECISIONS.md](../docs/DECISIONS.md) |
| Assignment timeline / full roadmap | [../docs/ROADMAP.md](../docs/ROADMAP.md) |
| Docker and Postgres ops | [../docs/SPRINT_1/](../docs/SPRINT_1/) |

This folder focuses on **implementation** and **how to read the code**, not on duplicating every wire format from `docs/API.md`.
