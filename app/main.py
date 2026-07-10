"""FastAPI application for the URL shortener service.

Endpoints
---------
POST /shorten           Accept a long URL; return a generated short slug + URL.
GET  /{slug}            Redirect (302) to the original URL; increment click count.
GET  /stats/{slug}      Return slug metadata and click count.
GET  /healthz           Liveness probe.
GET  /readyz            Readiness probe (verifies DB connectivity).
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, create_all, dispose, get_session
from app.repository import UrlRepository
from app.schemas import ShortenRequest, ShortenResponse, StatsResponse
from app.service import SlugCollisionError, SlugNotFoundError, UrlShortenerService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: create DB tables on startup, dispose engine on shutdown."""
    logger.info("Starting URL shortener service; creating DB schema if required.")
    await create_all()
    yield
    logger.info("Shutting down URL shortener service.")
    await dispose()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="URL Shortener Service",
    description=(
        "A production-grade URL shortener: create short slugs, redirect, and "
        "track per-slug click counts."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_service(session: SessionDep) -> UrlShortenerService:
    """Dependency: construct a UrlShortenerService bound to the current session."""
    repo = UrlRepository(session)
    return UrlShortenerService(repository=repo, base_url=BASE_URL)


ServiceDep = Annotated[UrlShortenerService, Depends(get_service)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_200_OK,
    summary="Shorten a URL",
    description="Accept a long URL and return a unique 6-character slug plus the short URL.",
)
async def shorten_url(
    body: ShortenRequest,
    service: ServiceDep,
    request: Request,
) -> ShortenResponse:
    """Create a new short URL mapping."""
    try:
        result = await service.shorten(body.url)
    except SlugCollisionError as exc:
        logger.error("Slug collision exhausted retries: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to generate a unique slug at this time. Please retry.",
        ) from exc

    logger.info(
        "Shortened URL",
        extra={"slug": result.slug, "request_id": request.headers.get("x-request-id")},
    )
    return ShortenResponse(
        slug=result.slug,
        short_url=result.short_url,
        original_url=result.original_url,
    )


@app.get(
    "/stats/{slug}",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get slug statistics",
    description="Return the original URL and total redirect hit count for a slug.",
)
async def get_stats(
    slug: str,
    service: ServiceDep,
    request: Request,
) -> StatsResponse:
    """Return statistics for a given slug."""
    try:
        result = await service.get_stats(slug)
    except SlugNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Slug {slug!r} not found.",
        ) from exc

    logger.info(
        "Stats fetched",
        extra={"slug": slug, "request_id": request.headers.get("x-request-id")},
    )
    return StatsResponse(
        slug=result.slug,
        original_url=result.original_url,
        click_count=result.click_count,
    )


# ---------------------------------------------------------------------------
# Health / readiness probes  — MUST be registered before /{slug} wildcard
# ---------------------------------------------------------------------------


@app.get("/healthz", include_in_schema=False)
@app.get("/health", include_in_schema=False)  # backward-compat alias
async def healthz() -> dict[str, str]:
    """Liveness probe: always returns 200 if the process is running."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readyz() -> dict[str, str]:
    """Readiness probe: verifies DB connectivity before accepting traffic."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready.",
        ) from exc
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Redirect — registered LAST so fixed paths take precedence
# ---------------------------------------------------------------------------


@app.get(
    "/{slug}",
    summary="Redirect to original URL",
    description="Redirect the caller to the original long URL and increment the click counter.",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
)
async def redirect_to_url(
    slug: str,
    service: ServiceDep,
    request: Request,
) -> RedirectResponse:
    """Resolve a slug to its original URL and issue a 302 redirect."""
    try:
        original_url = await service.redirect(slug)
    except SlugNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Slug {slug!r} not found.",
        ) from exc

    logger.info(
        "Redirecting",
        extra={"slug": slug, "request_id": request.headers.get("x-request-id")},
    )
    return RedirectResponse(url=original_url, status_code=status.HTTP_302_FOUND)
