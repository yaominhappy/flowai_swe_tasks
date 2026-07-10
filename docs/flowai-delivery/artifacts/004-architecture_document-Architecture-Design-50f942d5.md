# Architecture Design: FastAPI URL Shortener Service

## Architecture Summary

The FastAPI URL Shortener Service is a single‑container, multi‑tenant HTTP API that creates compact slugs for long URLs, serves HTTP 302 redirects, tracks per‑slug click counts, and exposes a statistics endpoint per tenant. The architecture follows a layered service design with strict tenant isolation enforced at the repository layer.

### System Layers

```
┌──────────────────────────────────────────┐
│              API Layer                    │
│  - FastAPI route handlers                │
│  - Pydantic request/response schemas     │
│  - Tenant context resolution via header  │
│  - Structured error responses            │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│        Application Layer                 │
│  - URLShortenerService                   │
│  - StatsService                          │
│  - Orchestrates creation, redirection,   │
│    and click counting                    │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│       Infrastructure Layer               │
│  - SQLAlchemy async repositories         │
│  - Tenant‑scoped queries                 │
│  - Database session management           │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│          Domain Models                   │
│  - ShortURL (SQLAlchemy ORM)             │
│  - ClickEvent (SQLAlchemy ORM)           │
│  - Pydantic DTOs for internal mapping    │
└──────────────────────────────────────────┘
```

**Key architectural decisions:**

- **Tenant isolation:** Every persisted record includes a `tenant_id` column. The `tenant_id` is extracted from a required `X-Tenant-ID` header on every request. All repository queries filter by this tenant identifier. Cross‑tenant access raises HTTP 404 to prevent information leakage.
- **Resumability:** The service is stateless; database durability provides resumability across restarts. No in‑memory state is used for critical operations.
- **Validation gates:** The architecture supports the SDLC validation chain by exposing clear interfaces, DTOs, and testable layers. Quality gates (≥80% line coverage, E2E tests per endpoint, static analysis) are designed into the project structure.
- **Tech stack compliance:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), SQLite, Uvicorn, Docker, pip for dependency management. All dependencies are pulled from `files.pythonhosted.org` and `pypi.org` in the container build.
- **Sandbox controls:** The Dockerfile is designed for a containerized build with restricted network allowed hosts. The container runs as a non‑root user with a read‑only root filesystem where appropriate.

---

## Primary Interfaces

All endpoints are prefixed with `/api/v1`. Responses are JSON with a consistent envelope `{"status": ..., "data": ...}` or `{"status": "error", "error": {"code": ..., "message": ...}}`.

### 1. Create Short URL

**Endpoint:** `POST /api/v1/shorten`  
**Purpose:** Accept a long URL and create a unique short slug scoped to the tenant.

**Headers:**
- `X-Tenant-ID`: string, required
- `Content-Type: application/json`

**Request body (Pydantic):**
```python
from pydantic import BaseModel, Field, HttpUrl

class ShortenRequest(BaseModel):
    url: HttpUrl = Field(..., description="The long URL to shorten")
    custom_slug: str | None = Field(
        default=None,
        min_length=4,
        max_length=32,
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Optional custom slug. Auto-generated if omitted."
    )
```

**Success response (HTTP 201):**
```python
class ShortenResponse(BaseModel):
    slug: str = Field(..., description="The generated or custom slug")
    short_url: str = Field(..., description="Full shortened URL (e.g., https://short.en/<slug>)")
    original_url: str
    created_at: datetime
```

**Error responses:**
- `422` – Validation error (invalid URL, invalid custom slug, slug already in use within tenant)
- `409` – Custom slug conflict within tenant (returned with error code `SLUG_CONFLICT`)
- `400` – Missing tenant header → `TENANT_REQUIRED`

### 2. Redirect

**Endpoint:** `GET /api/v1/{slug}`  
**Purpose:** Resolve a slug and return a 302 redirect to the original URL. Increment the click counter.

**Headers:**
- `X-Tenant-ID`: string, required

**Success response:**
- HTTP `302 Found` with `Location` header set to the original URL.

**Error responses:**
- `404` – Slug not found within tenant → error code `SLUG_NOT_FOUND`

### 3. Stats for a Slug

**Endpoint:** `GET /api/v1/stats/{slug}`  
**Purpose:** Return accumulated click metrics for a given slug.

**Headers:**
- `X-Tenant-ID`: string, required

**Success response (HTTP 200):**
```python
class SlugStatsResponse(BaseModel):
    slug: str
    original_url: str
    clicks: int = Field(..., description="Total click count")
    last_clicked_at: datetime | None
    created_at: datetime
```

**Error responses:**
- `404` – Slug not found within tenant

### 4. Health Check

**Endpoint:** `GET /healthz`  
**Purpose:** Liveness probe. Returns HTTP 200 with `{"status": "ok"}` when the service is running (no database check).

**Endpoint:** `GET /readyz`  
**Purpose:** Readiness probe. Verifies database connectivity. Returns 200 on success, 503 on failure.

---

## Data Model

All models use SQLAlchemy 2.0 `Mapped[T]` syntax. The database is SQLite, but the models are designed to be compatible with PostgreSQL if needed (UUID PKs, proper indexing).

### `short_urls` Table

```python
from datetime import datetime
from uuid import uuid4, UUID
from sqlalchemy import String, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

class ShortURL(Base):
    __tablename__ = "short_urls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(32), nullable=False)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    click_events: Mapped[list["ClickEvent"]] = relationship(
        back_populates="short_url", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_tenant_slug"),
        Index("ix_short_urls_tenant_slug", "tenant_id", "slug"),
    )
```

### `click_events` Table

```python
class ClickEvent(Base):
    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)  # integer PK for append performance
    short_url_id: Mapped[UUID] = mapped_column(ForeignKey("short_urls.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    short_url: Mapped["ShortURL"] = relationship(back_populates="click_events")

    __table_args__ = (
        Index("ix_click_events_tenant_short", "tenant_id", "short_url_id"),
        Index("ix_click_events_clicked_at", "clicked_at"),
    )
```

**Design rationale:**
- `short_urls` uses UUID PKs for global uniqueness and future sharding.
- `click_events` uses integer autoincrement PK for high‑write performance (append‑only log).
- Both tables carry `tenant_id` and every query filters by it.
- Compound unique constraint on `(tenant_id, slug)` ensures slugs are unique within a tenant only, allowing different tenants to have the same slug.
- FK from `click_events` to `short_urls` with ON DELETE CASCADE ensures cleanup if a URL is removed.

### Repository Pattern

All database access is encapsulated in repositories that accept a `tenant_id` parameter:

```python
class ShortURLRepository:
    async def get_by_slug(self, session: AsyncSession, tenant_id: str, slug: str) -> ShortURL | None: ...
    async def create(self, session: AsyncSession, tenant_id: str, data: ShortURLCreateDTO) -> ShortURL: ...
    async def get_stats(self, session: AsyncSession, tenant_id: str, slug: str) -> StatsDTO | None: ...

class ClickEventRepository:
    async def record_click(self, session: AsyncSession, tenant_id: str, short_url_id: UUID) -> None: ...
    async def count_clicks(self, session: AsyncSession, tenant_id: str, short_url_id: UUID) -> int: ...
```

**Tenant isolation invariant:** Repository methods never omit `tenant_id` from WHERE clauses. No repository returns data unless the `tenant_id` matches.

---

## Service Boundaries

### `URLShortenerService`
- **`create_short_url`:** Generates a unique slug (random 7‑character string) unless a custom slug is provided. Validates uniqueness within the tenant. Persists via repository.
- **`resolve_slug`:** Looks up slug within tenant, records a click event atomically using a database transaction, and returns the original URL.

### `StatsService`
- **`get_slug_stats`:** Retrieves click count and last‑clicked timestamp for a given slug within the tenant.

Service layer coordinates transactions: the redirect operation (resolve + record click) runs inside a single async database transaction to maintain consistency.

---

## Operational Constraints

### Deployment
- **Docker image:** Built with a multi‑stage Dockerfile (Python 3.12‑slim base). Dependencies are installed via `pip` from only `pypi.org` and `files.pythonhosted.org`. The final image runs as a non‑root user with a read‑only root filesystem (except for the SQLite database directory mounted as a volume).
- **Database:** SQLite file stored at `/data/shortener.db`. The directory `/data` is writable.
- **Networking:** No outbound calls are required except during build for pip. Runtime network is restricted (only internal container communication).
- **Entrypoint:** `uvicorn app.main:app --host 0.0.0.0 --port 8080`

### Database Migrations
- Migrations are managed by Alembic.
- Initial migration creates `short_urls` and `click_events` tables with all indexes and constraints.
- Future migrations follow the expand‑contract pattern to stay backward‑compatible.

### Tenant Isolation Enforcement
- **API layer:** A FastAPI dependency `get_tenant_id` reads `X-Tenant-ID` header and raises `HTTPException(400, "X-Tenant-ID header required")` if missing.
- **Service/Repository:** Tenant ID is passed explicitly to every service method. No global state holds a tenant context.
- **Cross‑tenant access:** A request for a slug that belongs to a different tenant returns 404, never 403, to avoid revealing the existence of the slug.

### Reliability & Observability
- **Structured logging:** Every request logs `request_id`, `tenant_id`, endpoint, and outcome. (We'll use Python's `logging` with JSON formatter for simplicity.)
- **Health checks:** `/healthz` (liveness) and `/readyz` (readiness, with DB ping).
- **Idempotency:** Slug creation is not naturally idempotent; custom slug requests are checked for conflicts (HTTP 409). Auto‑generated slugs will be unique and safe to retry.

### Quality Gates
The architecture is designed to support the SDLC quality gates:
- **≥80% line coverage:** All business logic layers are separated from I/O, making unit testing straightforward. Repositories are integration‑tested with SQLite.
- **E2E test per feature:** The project structure includes `tests/e2e/` for testing create, redirect, stats, and not‑found scenarios via `httpx.AsyncClient`.
- **Acceptance criteria mapping:** Each requirement (shorten, redirect, stats, not‑found) will have corresponding unit, integration, and E2E tests.
- **Static analysis:** The project will pass `python -m compileall` and use `mypy` (optional strict) and `ruff` for linting.

### Sandbox Controls
- The architecture fits a `containerized_build` sandbox with `restricted` network access.
- Dependency installation in the Dockerfile is allowed only from the hostnames `files.pythonhosted.org` and `pypi.org`.
- No system packages are installed; the Python base image provides all needed capabilities.
- Timeout is 1800 seconds; the build and test suite are designed to complete well within that limit.

---

## Implications for Implementation

The architecture fully constrains the implementation:
- API schemas and data models are specified with exact field types and constraints.
- Service layer interfaces are defined; engineers implement the repository methods and service logic.
- Tenant isolation and error handling patterns are unambiguous.
- The implementation plan can directly reference these interfaces for DTOs, dependencies, and test strategies.

The Solution Architect's output provides the unambiguous blueprint required for the Software Engineer to produce an implementation plan and begin coding.