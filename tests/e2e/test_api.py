"""End-to-end tests for the URL shortener HTTP API.

These tests exercise the full HTTP stack using httpx.AsyncClient pointed at
the real FastAPI application with a fresh in-memory SQLite database per test.
No mocks are used at the HTTP layer.

Coverage targets
----------------
AC-1  POST /shorten – success (200, returns slug + short_url + original_url)
AC-2  POST /shorten – missing url field → 422
AC-3  POST /shorten – empty url field → 422
AC-4  GET  /{slug}  – known slug → 302 redirect to original_url, click_count++
AC-5  GET  /{slug}  – unknown slug → 404
AC-6  GET  /stats/{slug} – known slug → 200 with correct payload
AC-7  GET  /stats/{slug} – unknown slug → 404
AC-8  Multiple redirects accumulate click_count correctly
AC-9  GET  /healthz → 200 {"status": "ok"}
AC-10 GET  /readyz  → 200 {"status": "ready"}
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def test_db_engine(tmp_path):  # type: ignore[no-untyped-def]
    """Create a fresh async SQLite engine for each E2E test."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/e2e_test.db"
    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(test_db_engine):  # type: ignore[no-untyped-def]
    """Return an AsyncClient wired to a fresh in-memory database.

    The FastAPI dependency ``get_session`` is overridden so that every
    request in this test shares the same isolated database engine.
    """
    session_factory = async_sessionmaker(
        bind=test_db_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async def override_get_session():  # type: ignore[no-untyped-def]
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    # Use ASGITransport so we never hit a real network socket.
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _shorten(client: AsyncClient, url: str = "https://example.com/long/path") -> dict:  # type: ignore[type-arg]
    """POST /shorten and return the parsed JSON body."""
    resp = await client.post("/shorten", json={"url": url})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# AC-1: POST /shorten success
# ---------------------------------------------------------------------------


async def test_shorten_success_returns_slug_and_short_url(client: AsyncClient) -> None:
    """AC-1: POST /shorten with valid URL returns 200 with slug/short_url/original_url."""
    original = "https://example.com/very/long/path?query=value"
    resp = await client.post("/shorten", json={"url": original})

    assert resp.status_code == 200
    body = resp.json()
    assert "slug" in body
    assert len(body["slug"]) == 6
    assert body["original_url"] == original
    assert body["slug"] in body["short_url"]


# ---------------------------------------------------------------------------
# AC-2 & AC-3: POST /shorten validation failures
# ---------------------------------------------------------------------------


async def test_shorten_missing_url_field_returns_422(client: AsyncClient) -> None:
    """AC-2: POST /shorten without url field returns 422."""
    resp = await client.post("/shorten", json={})
    assert resp.status_code == 422


async def test_shorten_empty_url_field_returns_422(client: AsyncClient) -> None:
    """AC-3: POST /shorten with empty url string returns 422."""
    resp = await client.post("/shorten", json={"url": ""})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC-4: GET /{slug} → 302 redirect
# ---------------------------------------------------------------------------


async def test_redirect_known_slug_returns_302(client: AsyncClient) -> None:
    """AC-4: GET /{slug} for a known slug returns 302 with Location header."""
    original = "https://example.com/redirect-target"
    data = await _shorten(client, original)
    slug = data["slug"]

    resp = await client.get(f"/{slug}", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == original


async def test_redirect_increments_click_count(client: AsyncClient) -> None:
    """AC-4 (click count): each redirect increments click_count by 1."""
    data = await _shorten(client, "https://example.com/click-test")
    slug = data["slug"]

    # Two redirects
    await client.get(f"/{slug}", follow_redirects=False)
    await client.get(f"/{slug}", follow_redirects=False)

    stats_resp = await client.get(f"/stats/{slug}")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["click_count"] == 2


# ---------------------------------------------------------------------------
# AC-5: GET /{slug} → 404 for unknown slug
# ---------------------------------------------------------------------------


async def test_redirect_unknown_slug_returns_404(client: AsyncClient) -> None:
    """AC-5: GET /{slug} for an unknown slug returns 404."""
    resp = await client.get("/xxxxxx", follow_redirects=False)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC-6: GET /stats/{slug} success
# ---------------------------------------------------------------------------


async def test_stats_known_slug_returns_correct_payload(client: AsyncClient) -> None:
    """AC-6: GET /stats/{slug} returns 200 with slug, original_url, click_count."""
    original = "https://example.com/stats-test"
    data = await _shorten(client, original)
    slug = data["slug"]

    resp = await client.get(f"/stats/{slug}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == slug
    assert body["original_url"] == original
    assert body["click_count"] == 0


# ---------------------------------------------------------------------------
# AC-7: GET /stats/{slug} → 404 for unknown slug
# ---------------------------------------------------------------------------


async def test_stats_unknown_slug_returns_404(client: AsyncClient) -> None:
    """AC-7: GET /stats/{slug} for an unknown slug returns 404."""
    resp = await client.get("/stats/xxxxxx")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC-8: Multiple redirects accumulate correctly
# ---------------------------------------------------------------------------


async def test_multiple_redirects_accumulate_click_count(client: AsyncClient) -> None:
    """AC-8: 5 redirects on the same slug yields click_count == 5."""
    data = await _shorten(client, "https://example.com/multi")
    slug = data["slug"]

    for _ in range(5):
        r = await client.get(f"/{slug}", follow_redirects=False)
        assert r.status_code == 302

    stats = await client.get(f"/stats/{slug}")
    assert stats.json()["click_count"] == 5


# ---------------------------------------------------------------------------
# AC-9 & AC-10: Health / readiness probes
# ---------------------------------------------------------------------------


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    """AC-9: GET /healthz returns 200 {"status": "ok"}."""
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_returns_ready(client: AsyncClient) -> None:
    """AC-10: GET /readyz returns 200 {"status": "ready"} when DB is accessible."""
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


async def test_shorten_two_different_urls_return_different_slugs(client: AsyncClient) -> None:
    """Two distinct URLs receive two distinct slugs."""
    d1 = await _shorten(client, "https://example.com/first")
    d2 = await _shorten(client, "https://example.com/second")
    assert d1["slug"] != d2["slug"]


async def test_stats_click_count_zero_before_any_redirect(client: AsyncClient) -> None:
    """A freshly shortened URL has click_count == 0 before any redirect."""
    data = await _shorten(client, "https://example.com/fresh")
    slug = data["slug"]
    resp = await client.get(f"/stats/{slug}")
    assert resp.json()["click_count"] == 0
