"""Tests for the health and readiness probe endpoints."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base


@pytest_asyncio.fixture()
async def health_client(tmp_path):  # type: ignore[no-untyped-def]
    """Minimal async client for health endpoint tests."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/health_test.db"
    engine = create_async_engine(db_url, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    async def override_get_session():  # type: ignore[no-untyped-def]
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_health_endpoint(health_client: AsyncClient) -> None:
    """GET /health returns 200 {"status": "ok"}."""
    response = await health_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_endpoint(health_client: AsyncClient) -> None:
    """GET /healthz returns 200 {"status": "ok"}."""
    response = await health_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
