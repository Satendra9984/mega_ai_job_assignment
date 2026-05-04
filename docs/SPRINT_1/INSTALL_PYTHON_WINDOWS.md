# Installing Python on Windows and running the backend locally

This guide helps when **`python` does not work in PowerShell**, when **`py -3.11` fails** (Python 3.11 not installed), or when you want to run **FastAPI / Uvicorn** on your PC instead of inside Docker.

After Python works, see [LOCAL_PYTHON_AND_FASTAPI.md](LOCAL_PYTHON_AND_FASTAPI.md) for daily workflow (venv, `DATABASE_URL`, tests).

---

## What Python is used for in this project

- Run the **FastAPI** backend with **Uvicorn** (hot reload during development).
- Run **pytest** for unit tests.
- Run **Alembic** migrations against a Postgres you can reach from Windows.

Docker already bundles Python 3.11 inside the **backend** image. Local Python is optional but useful for faster edit/run cycles **without** rebuilding the Docker image every time.

---

## Problem A — `python` opens the Microsoft Store or says “not found”

Windows can map the `python` command to a **Store stub** instead of a real installation.

**Fix: turn off App Execution Aliases**

1. Open **Settings** → **Apps** → **Advanced app settings** → **App execution aliases**.
2. Find **python.exe** and **python3.exe**.
3. Set both to **Off**.

Alternatively, install Python from **python.org** (next section) and ensure **“Add python.exe to PATH”** is checked during setup.

After this, open a **new** PowerShell window and try:

```powershell
python --version
```

---

## Step 1 — Install Python 3.11 (recommended for parity with Docker)

The project **Dockerfile** uses **Python 3.11**. Matching that version locally avoids subtle differences.

1. Open: **https://www.python.org/downloads/release/python-3119/**  
   (or the latest **3.11.x** “Windows installer (64-bit)”.)

2. Run the installer. Enable:

   - **Add python.exe to PATH**
   - **Install for all users** (optional; requires admin)

3. Finish the wizard and **close and reopen** PowerShell.

---

## Step 2 — Verify installation

The **Python Launcher** (`py`) can manage multiple versions:

```powershell
py --list
py -3.11 --version
python --version
```

- If **3.11** appears in `py --list`, use **`py -3.11`** for this project.
- If you only have **3.12** (or another version), you can still develop locally: **`py -3.12`** usually works with this project’s dependencies; the Docker image remains 3.11 for production parity.

**If `py -3.11` says it cannot find 3.11:** Install 3.11 from the link above, or use whatever version `py --list` shows (e.g. `py -3.12`).

---

## Note — Python 3.12 already on your machine

Many PCs already have 3.12 at a path like:

`C:\Users\<You>\AppData\Local\Programs\Python\Python312\python.exe`

That is fine for local development. Use:

```powershell
py -3.12 -m venv .venv
```

inside `backend/` if you do not install 3.11.

---

## Step 3 — Virtual environment in `backend/`

Always use a **venv** so project packages do not clash with other Python projects.

**PowerShell** (from repository root, then `backend`):

```powershell
cd C:\path\to\megaai\backend
py -3.11 -m venv .venv
```

If 3.11 is not installed:

```powershell
py -3.12 -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of the prompt.

**If activation is blocked** (“running scripts is disabled”):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try `Activate.ps1` again.

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 4 — Environment file (`.env`)

From the **repository root** (parent of `backend`):

```powershell
cd C:\path\to\megaai
Copy-Item .env.example .env
```

**Running only the backend on Windows** while Postgres runs **inside Docker:**

1. Publish Postgres to the host — add under the `db` service in `docker-compose.yml` (dev only):

   ```yaml
   ports:
     - "5432:5432"
   ```

2. Start only the database:

   ```powershell
   docker compose up db -d
   ```

3. In `.env`, set:

   ```text
   DATABASE_URL=postgresql+asyncpg://megaai:megaai@localhost:5432/megaai
   ```

   Use the same user/password/database as `POSTGRES_*` in `.env`.

If you run **full** `docker compose up`, you do not need local Python for the backend — use Docker instead.

---

## Step 5 — Run the FastAPI server locally

With venv **activated** and current directory **`backend`**:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- **http://localhost:8000/docs** — Swagger UI  
- **http://localhost:8000/openapi.json** — OpenAPI schema  

Stop the server with **Ctrl+C**.

---

## Step 6 — Apply migrations (if you use a real Postgres)

When `DATABASE_URL` points to a running Postgres:

```powershell
cd C:\path\to\megaai\backend
alembic upgrade head
```

---

## Step 7 — Run tests

With venv activated:

```powershell
cd C:\path\to\megaai\backend
pytest -v
```

Some tests need no database; others expect DB connectivity if configured.

---

## Quick verification commands

After `pip install -r requirements.txt`:

```powershell
python -c "import fastapi; print('fastapi', fastapi.__version__)"
python -c "from app.main import app; print(app.title)"
```

---

## Why Docker is still recommended for face detection

**MediaPipe** and its native dependencies are tested heavily in **Linux** (as in our `Dockerfile`). On Windows, you may need **Visual C++ Redistributables** or hit DLL issues. If `import mediapipe` fails locally, use:

```powershell
cd C:\path\to\megaai
docker compose up --build
```

and run tests inside the container:

```powershell
docker compose exec backend pytest -v
```

---

## Next steps

- Day-to-day local backend usage: [LOCAL_PYTHON_AND_FASTAPI.md](LOCAL_PYTHON_AND_FASTAPI.md)
- Full stack with Docker: [INSTALL_DOCKER_WINDOWS.md](INSTALL_DOCKER_WINDOWS.md)

---

## Official reference

- [Python on Windows](https://docs.python.org/3/using/windows.html)
