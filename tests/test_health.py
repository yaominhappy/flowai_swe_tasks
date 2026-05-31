"""Smoke test for health check and readiness endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_healthz_endpoint() -> None:
    """Liveness probe returns 200 and status ok."""
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_endpoint() -> None:
    """Readiness probe returns 200 and includes database status."""
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
