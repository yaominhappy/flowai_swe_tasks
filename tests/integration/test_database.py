"""Integration tests for the database module singletons and helper functions."""

from __future__ import annotations

import pytest_asyncio

from app.database import (
    _get_engine,
    _get_session_factory,
    create_tables,
    get_session,
    reset_engine,
)
from app.models.task import Base, Task


@pytest_asyncio.fixture(autouse=True)
async def _clean_engine():
    """Run tests against an in-memory engine, then clean up."""
    reset_engine()
    yield
    # Dispose the engine created during tests
    engine = _get_engine("sqlite+aiosqlite://")
    await engine.dispose()
    reset_engine()


class TestGetEngine:
    def test_creates_engine_with_custom_url(self) -> None:
        """_get_engine creates a new AsyncEngine for a given URL."""
        engine = _get_engine("sqlite+aiosqlite://")
        assert engine is not None
        # Calling again returns the same instance (singleton behaviour)
        engine2 = _get_engine("sqlite+aiosqlite://")
        assert engine is engine2

    def test_different_url_requires_reset(self) -> None:
        """When the singleton is reset, a new engine is built."""
        e1 = _get_engine("sqlite+aiosqlite://")
        reset_engine()
        e2 = _get_engine("sqlite+aiosqlite:///./other.db")
        assert e1 is not e2


class TestSessionFactory:
    def test_creates_factory(self) -> None:
        factory = _get_session_factory()
        assert factory is not None
        # Second call returns same singleton
        assert _get_session_factory() is factory


class TestGetSession:
    async def test_yields_session_and_commits(self) -> None:
        # Pre-create tables so we can insert something
        engine = _get_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async for session in get_session():
            task = Task(
                title="db-test",
                description=None,
            )
            session.add(task)
            await session.flush()
            await session.refresh(task)
            assert task.id is not None

        # After successful commit, task should be persisted
        async for session in get_session():
            fetched = await session.get(Task, task.id)
            assert fetched is not None
            assert fetched.title == "db-test"
            break  # only need one iteration

    async def test_rollback_on_exception(self) -> None:
        """If an exception is raised inside the context, the transaction
        is rolled back."""
        engine = _get_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create a task in a separate session first
        async for session in get_session():
            task = Task(title="will-rollback", description=None)
            session.add(task)
            await session.flush()
            break

        # Now try to insert and then raise — the rollback should undo
        try:
            async for session in get_session():
                task2 = Task(title="should-not-persist", description=None)
                session.add(task2)
                await session.flush()
                raise ValueError("injected failure")
        except ValueError:
            pass

        # The rolled-back task should NOT exist
        async for session in get_session():
            from sqlalchemy import select

            result = await session.execute(
                select(Task).where(Task.title == "should-not-persist")
            )
            assert result.scalar_one_or_none() is None
            break


class TestCreateTables:
    async def test_create_tables_idempotent(self) -> None:
        """create_tables can be called multiple times without error."""
        engine = _get_engine("sqlite+aiosqlite://")
        await create_tables(engine)  # first call
        await create_tables(engine)  # idempotent — no error

    async def test_create_tables_with_default_engine(self) -> None:
        """create_tables works with the default engine (when no arg is given)."""
        _get_engine("sqlite+aiosqlite://")
        await create_tables()  # uses the singleton
