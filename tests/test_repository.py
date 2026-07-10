"""Integration tests for app/repository.py.

Uses a real async SQLite database (via the conftest db_session fixture).
Every test gets a fresh, isolated database.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import UrlRepository

TENANT = "tenant-test"
OTHER_TENANT = "tenant-other"


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_short_url(db_session: AsyncSession) -> None:
    """create() returns a ShortURL with correct fields."""
    repo = UrlRepository(db_session)
    mapping = await repo.create("abc123", "https://example.com/long", TENANT)

    assert mapping.slug == "abc123"
    assert mapping.original_url == "https://example.com/long"
    assert mapping.tenant_id == TENANT
    assert mapping.click_count == 0
    assert mapping.id is not None
    assert mapping.created_at is not None


@pytest.mark.asyncio
async def test_create_default_tenant(db_session: AsyncSession) -> None:
    """create() uses 'default' tenant when none is specified."""
    repo = UrlRepository(db_session)
    mapping = await repo.create("defslug", "https://example.com")

    assert mapping.tenant_id == "default"


@pytest.mark.asyncio
async def test_create_duplicate_slug_same_tenant_raises(db_session: AsyncSession) -> None:
    """Inserting a duplicate (tenant_id, slug) pair raises IntegrityError."""
    repo = UrlRepository(db_session)
    await repo.create("dup001", "https://first.com", TENANT)

    with pytest.raises(IntegrityError):
        await repo.create("dup001", "https://second.com", TENANT)


@pytest.mark.asyncio
async def test_create_same_slug_different_tenants_ok(db_session: AsyncSession) -> None:
    """Two tenants may share the same slug without error."""
    repo = UrlRepository(db_session)
    m1 = await repo.create("shared", "https://tenant-a.com", TENANT)
    m2 = await repo.create("shared", "https://tenant-b.com", OTHER_TENANT)

    assert m1.id != m2.id
    assert m1.slug == m2.slug


# ---------------------------------------------------------------------------
# get_by_slug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_slug_returns_mapping(db_session: AsyncSession) -> None:
    """get_by_slug() returns the correct ShortURL for a known slug."""
    repo = UrlRepository(db_session)
    await repo.create("findme", "https://found.com", TENANT)

    result = await repo.get_by_slug("findme", TENANT)
    assert result is not None
    assert result.slug == "findme"
    assert result.original_url == "https://found.com"


@pytest.mark.asyncio
async def test_get_by_slug_unknown_returns_none(db_session: AsyncSession) -> None:
    """get_by_slug() returns None for a slug that has never been created."""
    repo = UrlRepository(db_session)
    result = await repo.get_by_slug("nope99", TENANT)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_slug_cross_tenant_returns_none(db_session: AsyncSession) -> None:
    """A slug created under one tenant is invisible to another tenant."""
    repo = UrlRepository(db_session)
    await repo.create("private", "https://secret.com", TENANT)

    result = await repo.get_by_slug("private", OTHER_TENANT)
    assert result is None


# ---------------------------------------------------------------------------
# increment_clicks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_increment_clicks_increases_count(db_session: AsyncSession) -> None:
    """increment_clicks() atomically bumps click_count by one."""
    repo = UrlRepository(db_session)
    await repo.create("click1", "https://click.com", TENANT)

    updated = await repo.increment_clicks("click1", TENANT)
    assert updated is not None
    assert updated.click_count == 1


@pytest.mark.asyncio
async def test_increment_clicks_multiple_times(db_session: AsyncSession) -> None:
    """Repeated calls accumulate click_count correctly."""
    repo = UrlRepository(db_session)
    await repo.create("multi", "https://multi.com", TENANT)

    for expected in range(1, 4):
        result = await repo.increment_clicks("multi", TENANT)
        assert result is not None
        assert result.click_count == expected


@pytest.mark.asyncio
async def test_increment_clicks_unknown_slug_returns_none(db_session: AsyncSession) -> None:
    """increment_clicks() returns None when the slug does not exist."""
    repo = UrlRepository(db_session)
    result = await repo.increment_clicks("ghost", TENANT)
    assert result is None


@pytest.mark.asyncio
async def test_increment_clicks_appends_click_event(db_session: AsyncSession) -> None:
    """increment_clicks() creates a ClickEvent row in the database."""
    from sqlalchemy import select
    from app.models import ClickEvent

    repo = UrlRepository(db_session)
    mapping = await repo.create("evtslug", "https://events.com", TENANT)
    await repo.increment_clicks("evtslug", TENANT)

    stmt = select(ClickEvent).where(ClickEvent.short_url_id == mapping.id)
    result = await db_session.execute(stmt)
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].tenant_id == TENANT
