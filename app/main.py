"""FastAPI application entry-point for the Task Manager API."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.tasks import router as tasks_router
from app.database import create_tables

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", '
    '"logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup; clean up on shutdown (no-op for SQLite)."""
    logger.info("Creating database tables (if not exist)...")
    await create_tables()
    logger.info("Application started.")
    yield
    logger.info("Application shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Task Manager API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(tasks_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/healthz", status_code=200)
async def healthz(request: Request) -> dict[str, str]:
    """Liveness probe -- returns 200 when the process is alive."""
    return {"status": "ok"}


@app.get("/readyz", status_code=200)
async def readyz(request: Request) -> dict[str, str]:
    """Readiness probe -- returns 200 when the service can accept traffic."""
    return {"status": "ok", "database": "connected"}


# ---------------------------------------------------------------------------
# Request-id and structured logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Attach a unique ``X-Request-ID`` to every response and emit a
    structured access-log entry for every request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
        },
    )
    return response
