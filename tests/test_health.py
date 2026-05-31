"""Smoke test for the health check endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_healthz_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
