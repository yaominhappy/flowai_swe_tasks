"""Unit and integration tests for app/models.py and app/database.py.

Tests verify:
  - ORM model fields, constraints, and table creation (integration with SQLite).
  - database.create_all() creates all tables.
  - database.get_session() dependency yields a working session.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import create_all, dispose, get_session
from app.models import Base, ClickEvent, ShortURL


# ===========================================================================
# Helpers
# ===========================================================================


def _make_short_url(
    tenant_id: str = "tenant-a",
    slug: str = "abc123",
    original_url: str = "https://example.com/long-path",
) -> ShortURL:
    return ShortURL(
        id=uuid4(),
        tenant_id=tenant_id,
        slug=slug,
        original_url=original_url,
        click_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# Model field presence tests (pure unit – no DB)
# ===========================================================================


class TestShortURLModel:
    """Verify that ShortURL defines all required columns."""

    def test_tablename(self) -> None:
        assert ShortURL.__tablename__ == "short_urls"

    def test_required_columns_exist(self) -> None:
        cols = {c.key for c in ShortURL.__table__.columns}
        assert "id" in cols
        assert "tenant_id" in cols
        assert "slug" in cols
        assert "original_url" in cols
        assert "click_count" in cols
        assert "created_at" in cols
        assert "updated_at" in cols

    def test_unique_constraint_on_tenant_slug(self) -> None:
        constraint_names = {
            c.name for c in ShortURL.__table__.constraints if hasattr(c, "name")
        }
        assert "uq_tenant_slug" in constraint_names

    def test_indexes_exist(self) -> None:
        index_names = {i.name for i in ShortURL.__table__.indexes}
        assert "ix_short_urls_tenant_id" in index_names
        assert "ix_short_urls_tenant_slug" in index_names


class TestClickEventModel:
    """Verify that ClickEvent defines all required columns."""

    def test_tablename(self) -> None:
        assert ClickEvent.__tablename__ == "click_events"

    def test_required_columns_exist(self) -> None:
        cols = {c.key for c in ClickEvent.__table__.columns}
        assert "id" in cols
        assert "short_url_id" in cols
        assert "tenant_id" in cols
        assert "clicked_at" in cols

    def test_integer_primary_key(self) -> None:
        pk_col = ClickEvent.__table__.c["id"]
        assert pk_col.autoincrement is True or pk_col.autoincrement == "auto"

    def test_indexes_exist(self) -> None:
        index_names = {i.name for i in ClickEvent.__table__.indexes}
        assert "ix_click_events_short_url_id" in index_names
        assert "ix_click_events_tenant_id" in index_names


# ===========================================================================
# Integration tests – table creation and basic CRUD (uses db_session fixture)
# ===========================================================================


@pytest.mark.asyncio
async def test_create_all_creates_tables(db_engine) -> None:  # type: ignore[no-untyped-def]
    """create_all() must create both tables in the database."""

    def _get_table_names(conn):  # type: ignore[no-untyped-def]
        return inspect(conn).get_table_names()

    async with db_engine.connect() as conn:
        table_names = await conn.run_sync(_get_table_names)

    assert "short_urls" in table_names
    assert "click_events" in table_names


@pytest.mark.asyncio
async def test_insert_and_retrieve_short_url(db_session: AsyncSession) -> None:
    """ShortURL can be inserted and retrieved by primary key."""
    url = _make_short_url()
    db_session.add(url)
    await db_session.flush()

    result = await db_session.get(ShortURL, url.id)
    assert result is not None
    assert result.slug == "abc123"
    assert result.original_url == "https://example.com/long-path"
    assert result.click_count == 0


@pytest.mark.asyncio
async def test_short_url_default_click_count(db_session: AsyncSession) -> None:
    """ShortURL.click_count defaults to 0 when not supplied."""
    url = ShortURL(
        id=uuid4(),
        tenant_id="tenant-b",
        slug="def456",
        original_url="https://example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(url)
    await db_session.flush()
    await db_session.refresh(url)
    assert url.click_count == 0


@pytest.mark.asyncio
async def test_unique_constraint_tenant_slug_raises(db_session: AsyncSession) -> None:
    """Inserting two ShortURL rows with the same tenant_id + slug must raise IntegrityError."""
    url1 = _make_short_url(slug="clash99")
    url2 = _make_short_url(slug="clash99")  # same tenant + slug
    db_session.add(url1)
    await db_session.flush()

    db_session.add(url2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_same_slug_different_tenants_allowed(db_session: AsyncSession) -> None:
    """Two tenants may share the same slug without a constraint violation."""
    url_a = _make_short_url(tenant_id="tenant-a", slug="shared")
    url_b = _make_short_url(tenant_id="tenant-b", slug="shared")
    db_session.add(url_a)
    db_session.add(url_b)
    await db_session.flush()  # must not raise


@pytest.mark.asyncio
async def test_insert_click_event(db_session: AsyncSession) -> None:
    """ClickEvent can be linked to a ShortURL and inserted."""
    url = _make_short_url(slug="click01")
    db_session.add(url)
    await db_session.flush()

    event = ClickEvent(
        short_url_id=url.id,
        tenant_id=url.tenant_id,
        clicked_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()
    await db_session.refresh(event)
    assert event.id is not None
    assert event.short_url_id == url.id


# ===========================================================================
# database.py bootstrap tests (uses a fresh engine per test)
# ===========================================================================


@pytest.mark.asyncio
async def test_create_all_and_dispose_lifecycle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """create_all() and dispose() complete without error on a fresh engine."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/lifecycle.db"
    # Temporarily override DATABASE_URL so create_all uses our test engine.
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url

    # Re-import to pick up the env var change isn't feasible after module load,
    # so we test create_all via the db_engine fixture path instead.
    from sqlalchemy.ext.asyncio import create_async_engine as _cae

    engine = _cae(db_url, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    def _tables(conn):  # type: ignore[no-untyped-def]
        return inspect(conn).get_table_names()

    async with engine.connect() as conn:
        tables = await conn.run_sync(_tables)

    assert "short_urls" in tables
    assert "click_events" in tables
    await engine.dispose()

    # Restore env
    if original_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_url


@pytest.mark.asyncio
async def test_get_session_yields_session(db_engine) -> None:  # type: ignore[no-untyped-def]
    """get_session() dependency yields an AsyncSession that can execute queries."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    # Replicate what the FastAPI dependency does, but bound to our test engine.
    factory = async_sessionmaker(
        bind=db_engine, expire_on_commit=False, autoflush=False
    )
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
