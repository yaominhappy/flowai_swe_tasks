"""Shared pytest fixtures for unit, integration, and E2E tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import reset_engine
from app.models.task import Base


@pytest_asyncio.fixture
async def test_engine():
    """Create a fresh async engine pointing at an in-memory SQLite DB."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Yield a fresh session within a transaction (rolled back after test)."""
    factory = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture(autouse=True)
def _isolate_engine():
    """Ensure each test starts with a clean engine singleton."""
    reset_engine()
    yield
    reset_engine()
