"""E2E test fixtures — real HTTP stack with in-memory SQLite database."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import get_session, reset_engine
from app.main import app
from app.models.task import Base

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture(autouse=True)
async def _override_db():
    """Override the application database with an in-memory SQLite for E2E."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    async def _override_get_session() -> AsyncGenerator:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _override_get_session
    reset_engine()

    yield

    app.dependency_overrides.clear()
    reset_engine()
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` pointed at the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
