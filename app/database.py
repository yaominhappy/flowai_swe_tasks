"""Async database engine and session factory for the task manager.

Configuration is read from the ``DATABASE_URL`` environment variable with a
fallback to a local SQLite file.  The module exposes a ``get_session``
async generator suitable for use as a FastAPI dependency.
"""

from __future__ import annotations

import os
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.models.task import Base

logger = logging.getLogger(__name__)

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./tasks.db",
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _get_engine(database_url: str = DATABASE_URL) -> AsyncEngine:
    """Return (or create) the singleton async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker:
    """Return (or create) the singleton async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = _get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator:
    """Yield an async SQLAlchemy session (FastAPI dependency).

    Commits on successful exit; rolls back on exception.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def reset_engine() -> None:
    """Reset cached engine/session factory (used in tests to swap databases)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def create_tables(engine: AsyncEngine | None = None) -> None:
    """Create all ORM tables (idempotent)."""
    eng = engine or _get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
