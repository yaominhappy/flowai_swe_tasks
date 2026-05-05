"""Integration tests for app/database.py.

Tests verify:
  - create_all() creates all tables.
  - dispose() completes without error.
  - get_session() dependency yields a functional AsyncSession (commit path).
  - get_session() rolls back and re-raises on exception (rollback path).
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import create_all, dispose, get_session
from app.models import Base


@pytest.mark.asyncio
async def test_create_all_creates_expected_tables(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """create_all() must create short_urls and click_events tables."""
    import app.database as db_module

    db_url = f"sqlite+aiosqlite:///{tmp_path}/ca_test.db"
    # Monkey-patch the module-level engine for the duration of this test.
    orig_engine = db_module.async_engine
    test_engine = create_async_engine(
        db_url, connect_args={"check_same_thread": False}
    )
    db_module.async_engine = test_engine
    try:
        await create_all()

        def _tables(conn):  # type: ignore[no-untyped-def]
            return inspect(conn).get_table_names()

        async with test_engine.connect() as conn:
            tables = await conn.run_sync(_tables)

        assert "short_urls" in tables
        assert "click_events" in tables
    finally:
        db_module.async_engine = orig_engine
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_dispose_does_not_raise(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """dispose() must complete without raising any exception."""
    import app.database as db_module

    db_url = f"sqlite+aiosqlite:///{tmp_path}/dispose_test.db"
    orig_engine = db_module.async_engine
    test_engine = create_async_engine(
        db_url, connect_args={"check_same_thread": False}
    )
    db_module.async_engine = test_engine
    try:
        # Ensure tables exist before disposing.
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # dispose() should complete cleanly.
        await dispose()
    finally:
        db_module.async_engine = orig_engine
        # Engine already disposed inside dispose(); calling again is safe.
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_get_session_commit_path(db_engine) -> None:  # type: ignore[no-untyped-def]
    """get_session() commits successfully when no exception is raised."""
    import app.database as db_module

    orig_engine = db_module.async_engine
    orig_factory = db_module.AsyncSessionLocal
    db_module.async_engine = db_engine
    db_module.AsyncSessionLocal = async_sessionmaker(
        bind=db_engine, expire_on_commit=False, autoflush=False
    )
    try:
        gen = get_session()
        session = await gen.__anext__()
        # Execute a trivial query to confirm the session works.
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
        # Exhaust the generator (triggers commit).
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
    finally:
        db_module.async_engine = orig_engine
        db_module.AsyncSessionLocal = orig_factory


@pytest.mark.asyncio
async def test_get_session_rollback_path(db_engine) -> None:  # type: ignore[no-untyped-def]
    """get_session() rolls back and re-raises when an exception occurs."""
    import app.database as db_module

    orig_engine = db_module.async_engine
    orig_factory = db_module.AsyncSessionLocal
    db_module.async_engine = db_engine
    db_module.AsyncSessionLocal = async_sessionmaker(
        bind=db_engine, expire_on_commit=False, autoflush=False
    )
    try:
        gen = get_session()
        await gen.__anext__()
        with pytest.raises(RuntimeError, match="simulated error"):
            await gen.athrow(RuntimeError("simulated error"))
    finally:
        db_module.async_engine = orig_engine
        db_module.AsyncSessionLocal = orig_factory
