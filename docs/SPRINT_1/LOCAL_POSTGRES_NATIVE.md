# Native PostgreSQL — local dev without Docker (Windows-oriented)

This guide is for running **Uvicorn on your PC** with **PostgreSQL installed on the same machine** (not the `db` container). It avoids mixing Docker-only hostnames (`db`) and host-only URLs (`localhost`).

**Related:** [LOCAL_PYTHON_AND_FASTAPI.md](LOCAL_PYTHON_AND_FASTAPI.md) (venv, uvicorn), [POSTGRESQL.md](POSTGRESQL.md) (schema, Alembic URL conversion), [README.md](../../README.md) (ports 3000 vs 5173).

---

## 1. Mode table (read this first)

| Mode | What runs | Open in browser | `DATABASE_URL` host | `CORS_ORIGINS` must include |
|------|-----------|-------------------|---------------------|----------------------------|
| **A — Full Docker** | `db`, `backend`, `frontend` containers | http://localhost:3000 | N/A (set inside Compose; uses `db`) | `http://localhost:3000` (default) |
| **B — Host API + Postgres in Docker** | `db` only (or db + others), `uvicorn` on host | http://localhost:5173 (`npm run dev`) | **`localhost`** (publish Postgres `5432` to host) | `http://localhost:5173` |
| **C — Host API + native Postgres** (this doc) | Windows PostgreSQL service, `uvicorn`, Vite | http://localhost:5173 | **`localhost`** or **`127.0.0.1`** | `http://localhost:5173` (and `3000` only if you also use Docker UI) |

**Do not** use `DATABASE_URL=...@db:5432/...` when Uvicorn runs on the host — hostname **`db`** only resolves **inside** the Docker network. You will get **`getaddrinfo failed` (Windows: 11001)** on the first DB write (e.g. WebSocket ingest creating `VideoSession`).

**Do not** open **http://localhost:3000** (nginx in Docker) while only your **host** API is running — nginx proxies to the **`backend` container**, not your local Uvicorn. Use **5173** + Vite for local API dev ([README troubleshooting](../../README.md)).

---

## 2. Prerequisites

1. **PostgreSQL is installed** and the **server service is running** (default listen port **5432**).
2. You can connect with **`psql`** or **pgAdmin** as a superuser (often `postgres` on Windows).

**Quick check (PowerShell)** — if `psql` is on your PATH:

```powershell
psql -U postgres -h localhost -p 5432 -c "SELECT version();"
```

If that fails, fix PostgreSQL service / PATH before continuing.

---

## 3. Create role, database, and privileges (project defaults)

These names match [`.env.example`](../../.env.example): user **`megaai`**, password **`megaai`**, database **`megaai`**.

**Option A — `psql` as superuser (e.g. `postgres`)**

```sql
-- Run inside: psql -U postgres -h localhost

CREATE USER megaai WITH PASSWORD 'megaai';
CREATE DATABASE megaai OWNER megaai;
GRANT ALL PRIVILEGES ON DATABASE megaai TO megaai;
```

Connect to the new DB and grant schema usage (PostgreSQL 15+ may need this for migrations):

```sql
\c megaai
GRANT ALL ON SCHEMA public TO megaai;
```

**Option B — use your own user/database**

If you already have a user and empty database, set `DATABASE_URL` in `.env` to match (see section 4). Run Alembic as a user that can create tables in that database.

---

## 4. `DATABASE_URL` for asyncpg (host)

Use **`localhost`** (or `127.0.0.1`) and port **`5432`** (unless you configured another port):

```text
DATABASE_URL=postgresql+asyncpg://megaai:megaai@localhost:5432/megaai
```

- Driver must be **`postgresql+asyncpg://`** for the running FastAPI app ([`app/config.py`](../../backend/app/config.py)).
- **Never** use host `db` for host-side Uvicorn.

Keep `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in `.env` aligned with the credentials in `DATABASE_URL` (useful if you later use Compose scripts or docs that reference them).

---

## 5. Where to put `.env` (current working directory)

[`backend/app/config.py`](../../backend/app/config.py) loads:

```python
model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

`env_file=".env"` is resolved relative to the **process current working directory**, not relative to the `app/` package.

| You start Uvicorn from… | Put `.env` here |
|-------------------------|-----------------|
| `cd backend` then `uvicorn app.main:app …` | **`backend/.env`** (recommended; matches [README](../../README.md) `cp ../.env.example .env` from `backend/`) |
| Repo root with a custom wrapper | **repo root `.env`** only if that is your actual cwd when the process starts |

If variables are ignored, you are almost certainly in the wrong directory or the wrong `.env` path.

---

## 6. CORS for Vite (`localhost:5173`)

The browser origin for **`npm run dev`** is **http://localhost:5173**. If `CORS_ORIGINS` only lists `http://localhost:3000`, some browser requests may be blocked.

Set (comma-separated if you need both):

```text
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

WebSocket connections from the Vite dev server also originate from **5173**; the backend must allow that origin.

---

## 7. Apply schema (Alembic)

From **`backend/`** with the same `DATABASE_URL` exported or present in `backend/.env`:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1   # if you use a venv
alembic upgrade head
```

Alembic converts `asyncpg` → sync `postgresql://` internally ([POSTGRESQL.md](POSTGRESQL.md)). If this step fails, fix DB credentials or connectivity before starting Uvicorn.

---

## 8. Run order and smoke test

1. **PostgreSQL service** running.
2. **`alembic upgrade head`** (once per machine / after new migrations).
3. **`uvicorn`** from `backend/`:

   ```powershell
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Frontend** (separate terminal):

   ```powershell
   cd frontend
   npm run dev
   ```

5. Open **http://localhost:5173** → **Start webcam**. You should receive the `session` JSON and then `roi` messages. If the first DB write fails, check Uvicorn logs for `getaddrinfo` or connection refused.

**Quick API check:** http://localhost:8000/openapi.json should return `200`.

---

## 9. Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `getaddrinfo failed` / 11001 on first WS use | `DATABASE_URL` still uses **`@db:`** | Change to **`@localhost:5432`** (this doc, section 4). |
| `connection refused` to Postgres | Service stopped or wrong port | Start PostgreSQL service; confirm `5432` in `DATABASE_URL`. |
| Port **5432** already in use | Docker `db` also published `5432:5432` | Stop conflicting container or use a different host port and update `DATABASE_URL`. |
| `password authentication failed` | Wrong user/password | Match `DATABASE_URL` to the role you created (section 3). |
| Tables missing / relation does not exist | Migrations not applied | Run `alembic upgrade head` from `backend/`. |
| WebSocket fails on **3000** only | Using Docker nginx without Docker **backend** | Use **5173** + Vite for host API, or run full `docker compose up`. |
| CORS errors in browser console | Origin `5173` not allowed | Add `http://localhost:5173` to `CORS_ORIGINS` (section 6). |

---

## 10. Optional: two `.env` files (advanced)

Some teams keep **`.env.docker`** (Compose) and **`.env.local`** (host) and copy/symlink — the repo does not enforce this. Whatever you use, ensure the file that **`pydantic-settings` actually loads** matches the environment where Uvicorn runs (section 5).
