"""Shared pytest fixtures for backend tests.

Tests that need a database use an in-memory SQLite engine so no running Postgres
is required.  Two SQLite-specific quirks are handled here:

1. **StaticPool** — all sessions share the same underlying connection so they all
   see the same in-memory database (default pool creates a fresh DB per connection).

2. **INTEGER PRIMARY KEY** — SQLite only auto-increments `INTEGER PRIMARY KEY`;
   the ORM model uses `BigInteger` which maps to `BIGINT` and breaks SQLite's
   rowid auto-increment.  We create test tables with hand-written DDL that uses
   `INTEGER PRIMARY KEY AUTOINCREMENT` instead.
"""
from __future__ import annotations

import io
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.services.detector import FaceDetector
from app.services.frame_bus import FrameBus

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_solid_jpeg(
    width: int = 64,
    height: int = 64,
    color: tuple[int, int, int] = (200, 200, 200),
) -> bytes:
    """Return a minimal solid-colour JPEG — no face, always valid."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def _create_test_tables(conn) -> None:
    """Create tables using SQLite-compatible DDL (INTEGER PK, not BIGINT)."""
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sessions (
            id CHAR(32) PRIMARY KEY,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS roi_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id CHAR(32) NOT NULL REFERENCES sessions(id),
            frame_index INTEGER NOT NULL,
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            face_detected BOOLEAN NOT NULL DEFAULT 0,
            x INTEGER,
            y INTEGER,
            w INTEGER,
            h INTEGER,
            confidence REAL
        )
    """))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_roi_records_session_id "
        "ON roi_records(session_id)"
    ))


def _make_sqlite_engine():
    """Create a StaticPool SQLite engine so all sessions share one in-memory DB."""
    return create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


# ---------------------------------------------------------------------------
# Async (HTTP) fixtures — used by test_roi_api.py
# ---------------------------------------------------------------------------

@pytest.fixture
async def sqlite_engine():
    """In-memory SQLite engine with test tables created for one test function."""
    engine = _make_sqlite_engine()
    async with engine.begin() as conn:
        await _create_test_tables(conn)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sqlite_session_factory(sqlite_engine):
    """async_sessionmaker bound to the test SQLite engine."""
    return async_sessionmaker(
        bind=sqlite_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest.fixture
async def http_client(sqlite_session_factory) -> AsyncGenerator:
    """httpx.AsyncClient with the DB dependency overridden to use SQLite."""
    from httpx import ASGITransport, AsyncClient

    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        async with sqlite_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sync (WebSocket) fixture — used by test_ws_ingest.py and test_ws_stream.py
# ---------------------------------------------------------------------------

@pytest.fixture
def ws_client(monkeypatch) -> Generator:
    """Starlette TestClient with a test lifespan that substitutes SQLite for Postgres.

    The custom lifespan runs inside TestClient's own event loop, so the SQLite
    engine, session factory, FaceDetector, and FrameBus all share that loop.
    StaticPool ensures the ingest router's multiple sessions all write to the
    same in-memory DB.
    """
    from starlette.testclient import TestClient

    @asynccontextmanager
    async def _test_lifespan(the_app):  # type: ignore[override]
        engine = _make_sqlite_engine()
        async with engine.begin() as conn:
            await _create_test_tables(conn)
        sf = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        the_app.state.session_factory = sf
        the_app.state.frame_bus = FrameBus()
        the_app.state.detector = FaceDetector()
        yield
        the_app.state.detector.close()
        await engine.dispose()

    monkeypatch.setattr(app.router, "lifespan_context", _test_lifespan)
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
