"""Async SQLAlchemy engine, session factory, and schema bootstrap.

Provides:
  - async_engine     : SQLAlchemy async engine (configured via DATABASE_URL env var).
  - AsyncSessionLocal: async_sessionmaker factory for request-scoped sessions.
  - create_all()     : coroutine that creates all tables declared in Base.metadata.
  - get_session()    : FastAPI dependency that yields a managed AsyncSession.
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

# Default to a local SQLite file; override via DATABASE_URL in production.
_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./urlshort.db"
DATABASE_URL: str = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)

async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # pool_pre_ping only meaningful for server-side DB engines; harmless for SQLite.
    pool_pre_ping=True,
    # SQLite-specific: allow the same connection to be used across threads
    # (needed when running sync helpers from async context in tests).
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------


async def create_all() -> None:
    """Create all tables defined in Base.metadata if they do not already exist.

    Called once during application startup via the FastAPI lifespan handler.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created (or already exist).")


async def dispose() -> None:
    """Dispose the async engine connection pool.

    Called during application shutdown to release database resources cleanly.
    """
    await async_engine.dispose()
    logger.info("Database engine disposed.")


# ---------------------------------------------------------------------------
# FastAPI session dependency
# ---------------------------------------------------------------------------


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield a database session, then close it.

    Usage::

        @router.get("/example")
        async def example(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
