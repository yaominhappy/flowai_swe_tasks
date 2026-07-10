"""Unit and integration tests for app/main.py error paths and lifespan.

These tests complement the E2E tests by exercising routes via mocked services
(to trigger error branches) and the lifespan/readyz probe via real DB.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app, get_service
from app.models import Base
from app.service import SlugCollisionError, SlugNotFoundError, UrlShortenerService


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def api_client(tmp_path):  # type: ignore[no-untyped-def]
    """Async HTTP client wired to a fresh in-memory SQLite DB."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/main_test.db"
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


# ---------------------------------------------------------------------------
# Helper: mock service that raises a specific error
# ---------------------------------------------------------------------------


def _make_mock_service(side_effect: Exception) -> UrlShortenerService:
    """Return a mock UrlShortenerService that raises *side_effect* on shorten/redirect/get_stats."""
    svc = MagicMock(spec=UrlShortenerService)
    svc.shorten = AsyncMock(side_effect=side_effect)
    svc.redirect = AsyncMock(side_effect=side_effect)
    svc.get_stats = AsyncMock(side_effect=side_effect)
    return svc  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# POST /shorten — SlugCollisionError → 503
# ---------------------------------------------------------------------------


async def test_shorten_slug_collision_returns_503(api_client: AsyncClient) -> None:
    """When SlugCollisionError is raised, POST /shorten returns 503."""
    collision_svc = _make_mock_service(SlugCollisionError(5))
    app.dependency_overrides[get_service] = lambda: collision_svc  # type: ignore[assignment]
    try:
        resp = await api_client.post("/shorten", json={"url": "https://example.com"})
        assert resp.status_code == 503
        assert "unique slug" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# GET /stats/{slug} — SlugNotFoundError → 404
# ---------------------------------------------------------------------------


async def test_get_stats_not_found_via_mock(api_client: AsyncClient) -> None:
    """When SlugNotFoundError is raised in get_stats, the endpoint returns 404."""
    not_found_svc = _make_mock_service(SlugNotFoundError("abc123"))
    app.dependency_overrides[get_service] = lambda: not_found_svc  # type: ignore[assignment]
    try:
        resp = await api_client.get("/stats/abc123")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# GET /{slug} — SlugNotFoundError → 404
# ---------------------------------------------------------------------------


async def test_redirect_not_found_via_mock(api_client: AsyncClient) -> None:
    """When SlugNotFoundError is raised in redirect, the endpoint returns 404."""
    not_found_svc = _make_mock_service(SlugNotFoundError("abc123"))
    app.dependency_overrides[get_service] = lambda: not_found_svc  # type: ignore[assignment]
    try:
        resp = await api_client.get("/abc123", follow_redirects=False)
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


# ---------------------------------------------------------------------------
# GET /readyz — DB failure → 503
# ---------------------------------------------------------------------------


async def test_readyz_db_failure_returns_503(api_client: AsyncClient) -> None:
    """When the DB is unreachable, GET /readyz returns 503."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    # Patch AsyncSessionLocal so its execute raises OperationalError.
    with patch("app.main.AsyncSessionLocal") as mock_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            side_effect=OperationalError("DB down", None, None)
        )
        mock_factory.return_value = mock_session

        resp = await api_client.get("/readyz")
        assert resp.status_code == 503
        assert "not ready" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Lifespan: create_all + dispose called during startup/shutdown
# ---------------------------------------------------------------------------


async def test_lifespan_calls_create_all_and_dispose() -> None:
    """Lifespan context manager calls create_all on enter and dispose on exit."""
    from app.main import lifespan

    mock_app = MagicMock()
    with (
        patch("app.main.create_all", new_callable=AsyncMock) as mock_create,
        patch("app.main.dispose", new_callable=AsyncMock) as mock_dispose,
    ):
        async with lifespan(mock_app):
            # Startup: create_all should have been called.
            mock_create.assert_awaited_once()
            mock_dispose.assert_not_called()
        # Shutdown: dispose should have been called.
        mock_dispose.assert_awaited_once()
