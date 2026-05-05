"""Root pytest configuration and shared async fixtures.

Fixtures defined here are available to all test modules in the project.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


# ---------------------------------------------------------------------------
# pytest-asyncio configuration
# ---------------------------------------------------------------------------

# Use "auto" mode so every async test function is automatically treated as
# asyncio-based without requiring @pytest.mark.asyncio on each one.
pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Force asyncio mode globally."""
    config.addinivalue_line(
        "markers", "asyncio: mark a test as an asyncio coroutine"
    )


# ---------------------------------------------------------------------------
# In-memory SQLite engine + session (shared across all test layers)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_engine(tmp_path):  # type: ignore[no-untyped-def]
    """Create a fresh async SQLite engine backed by a tmp file per test.

    Using a file (rather than pure in-memory `:memory:`) avoids the SQLite
    limitation that each connection to `sqlite:///:memory:` sees a separate
    empty database — important when the app uses connection pooling.
    """
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):  # type: ignore[no-untyped-def]
    """Yield a managed AsyncSession connected to the per-test SQLite database."""
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with factory() as session:
        yield session
