"""Smoke tests — no database required."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_schema_available() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "openapi" in response.json()


def test_docs_redirect_or_available() -> None:
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
