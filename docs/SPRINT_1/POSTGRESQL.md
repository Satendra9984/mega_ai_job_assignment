# PostgreSQL with this backend

The FastAPI app persists face-detection results using **SQLAlchemy (async)** and **asyncpg**. Schema changes are applied with **Alembic** (using a **sync** driver for migrations).

## Connection URLs

### Application runtime (async)

The backend reads **`DATABASE_URL`** from the environment (see [app/config.py](../../backend/app/config.py)).

- **Inside Docker Compose** (as set in `docker-compose.yml`):

  ```text
  postgresql+asyncpg://megaai:megaai@db:5432/megaai
  ```

  Host **`db`** is the Compose service name on `megaai_net`.

- **`.env.example`** includes the same shape; when running with Compose, the compose file’s `environment` section typically overrides this so the hostname stays **`db`**.

### Alembic migrations (sync)

Alembic does not use `asyncpg`. In [backend/alembic/env.py](../../backend/alembic/env.py), the async URL is converted for the migration engine:

- `postgresql+asyncpg://…` → `postgresql://…` (uses **`psycopg2-binary`** from [requirements.txt](../../backend/requirements.txt))

So you only maintain one logical URL pattern; the env script normalizes it.

### Running the API on the host (Python outside Docker)

If Postgres still runs in Docker but your API runs on **localhost**, you must:

1. **Publish** Postgres to the host (see [Optional: expose port 5432](#optional-expose-port-5432-for-local-tools)), **or**
2. Keep DB internal-only and only inspect data via `docker compose exec db psql`.

Your **`DATABASE_URL`** must then use **`localhost`** (or `127.0.0.1`) instead of `db`:

```text
postgresql+asyncpg://megaai:megaai@localhost:5432/megaai
```

Password and database name must match `POSTGRES_*` in `.env`.

## Schema (Sprint 1)

Defined in migration [backend/alembic/versions/001_initial_sessions_roi.py](../../backend/alembic/versions/001_initial_sessions_roi.py).

### Table `sessions`

| Column | Type | Notes |
|--------|------|--------|
| `id` | UUID | Primary key (one row per capture session) |
| `created_at` | `TIMESTAMPTZ` | Default `now()` |

### Table `roi_records`

| Column | Type | Notes |
|--------|------|--------|
| `id` | `BIGSERIAL` | Primary key |
| `session_id` | UUID | FK → `sessions.id`, `ON DELETE CASCADE`, indexed |
| `frame_index` | INTEGER | Zero-based index within session |
| `detected_at` | `TIMESTAMPTZ` | Default `now()` |
| `face_detected` | BOOLEAN | |
| `x`, `y`, `w`, `h` | INTEGER NULL | Axis-aligned bounding box in pixels (nullable if no face) |
| `confidence` | FLOAT NULL | Detector score |

## Migrations

### Automatic (normal path)

The **backend Docker image** runs before Uvicorn:

```bash
alembic upgrade head
```

So tables appear on first deploy without a manual step.

### Manual (debugging or host Alembic)

From repo root, with DB reachable:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

Running Alembic on the host requires `DATABASE_URL` pointing at a reachable Postgres (often `localhost` with port published) and `backend/` as cwd with venv activated:

```bash
cd backend
alembic upgrade head
```

## Inspecting data with `psql` (no host port required)

Use the `db` container:

```bash
docker compose exec db psql -U megaai -d megaai -c "\dt"
docker compose exec db psql -U megaai -d megaai -c "SELECT COUNT(*) FROM roi_records;"
docker compose exec db psql -U megaai -d megaai -c "SELECT id, frame_index, face_detected FROM roi_records ORDER BY id DESC LIMIT 5;"
```

Default user/database match `.env.example` (`megaai` / `megaai`).

## Optional: expose port 5432 for local tools

The stock `docker-compose.yml` does **not** map Postgres to the host (good for security). For **local development only**, you can temporarily add under the `db` service:

```yaml
ports:
  - "5432:5432"
```

Then tools like DBeaver, `psql` on the host, or a host-run FastAPI can use `localhost:5432`.

**Caution:** If another Postgres already uses 5432 on your machine, pick another host port, e.g. `"5433:5432"`.

Remove or comment out this block before sharing a minimal production-like compose file.

## GUI connection string (host access)

If you publish `5432:5432` and keep defaults:

```text
postgresql://megaai:megaai@localhost:5432/megaai
```

## Backups and data loss

- Data lives in the Docker volume **`postgres_data`** (see `docker-compose.yml`).
- **`docker compose down -v`** deletes that volume and **all sessions / ROI rows**.
- For a serious backup, use `pg_dump` from `docker compose exec db` or snapshot the volume using your platform’s backup strategy.
