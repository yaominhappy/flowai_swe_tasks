**Architecture Design: FastAPI Task Manager API**

---

## Architecture Summary

This document defines the concrete system architecture for a production-grade, tenant-isolated task management REST API built with FastAPI, SQLAlchemy, and SQLite. The architecture enforces strict tenant isolation at every persistence layer, provides CRUD endpoints with priority/status filtering, and uses Pydantic v2 for request/response validation. All I/O is asynchronous, and the service runs inside a Docker container with network access restricted to Python package mirrors. The design is organized into four layers (API, Application, Infrastructure, Domain) to ensure separation of concerns and testability. Validation gates are built into the API boundary, and every acceptance criterion maps to at least one automated pytest test.

---

## Primary Interfaces

### Base URL
`/api/v1`

### Common Headers
| Header | Required | Value |
|--------|----------|-------|
| `X-Tenant-ID` | yes | non‑empty string (tenant identifier) |
| `Content-Type` | yes (for POST/PUT) | `application/json` |

### Authentication & Tenant Resolution
- The `X-Tenant-ID` header is read in a FastAPI dependency and injected into every request context.
- Missing or blank `X-Tenant-ID` → `400 Bad Request` with error code `MISSING_TENANT_ID`.
- In production, this would be derived from a validated JWT’s tenant claim; for this sandbox deployment, a plain header suffices to exercise the isolation paths.

---

### 1. Create Task
```
POST /api/v1/tasks
```
**Request Body** (application/json)
```json
{
  "title": "Design system architecture",
  "description": "Produce the architecture document",
  "priority": "high",
  "status": "pending"
}
```
* `title`: `str`, `min_length=1`, required
* `description`: `str | None`, optional
* `priority`: `Priority` enum (`low`, `medium`, `high`), required
* `status`: `Status` enum (`pending`, `in_progress`, `completed`), default `pending`

**Success Response (201 Created)**
```json
{
  "id": "uuid-1234",
  "title": "Design system architecture",
  "description": "Produce the architecture document",
  "priority": "high",
  "status": "pending",
  "created_at": "2025-03-27T12:00:00Z",
  "updated_at": "2025-03-27T12:00:00Z"
}
```
* `id`: `UUID` (automatically generated)
* `created_at`, `updated_at`: `datetime` in ISO 8601

**Error Responses**
- `400` – missing body, validation error (Pydantic), or missing `X-Tenant-ID`
- `422` – automatically handled by FastAPI for invalid field types/value ranges

---

### 2. List Tasks
```
GET /api/v1/tasks
```
**Query Parameters**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `Status` | no | Filter by task status |
| `priority` | `Priority` | no | Filter by task priority |

**Success Response (200 OK)**
```json
{
  "items": [
    {
      "id": "uuid-1234",
      "title": "Design system architecture",
      "description": "Produce the architecture document",
      "priority": "high",
      "status": "pending",
      "created_at": "2025-03-27T12:00:00Z",
      "updated_at": "2025-03-27T12:00:00Z"
    }
  ]
}
```
* Returns all tasks belonging to the tenant identified by `X-Tenant-ID`, optionally filtered.
* If no tasks exist, `items` is an empty list (`[]`).

---

### 3. Get Single Task
```
GET /api/v1/tasks/{task_id}
```
* `task_id`: `UUID` path parameter

**Success Response (200 OK)**
Same shape as a single item from the list response.

**Error Responses**
- `404` – task not found **within the tenant scope** (cross‑tenant access returns `404` to avoid information leakage)
- `400` – missing `X-Tenant-ID`
- `422` – invalid UUID format

---

### 4. Update Task
```
PUT /api/v1/tasks/{task_id}
```
**Request Body** (application/json)
- All fields are optional; only supplied fields are updated.
```json
{
  "title": "Updated title",
  "description": null,
  "priority": "medium",
  "status": "in_progress"
}
```
- `title`: `str | None`
- `description`: `str | None`
- `priority`: `Priority | None`
- `status`: `Status | None`

**Success Response (200 OK)**
Full updated task object (same shape as create response).

**Error Responses**
- `404` – task not found for the tenant
- `422` – invalid field values

---

### 5. Delete Task
```
DELETE /api/v1/tasks/{task_id}
```
* `task_id`: UUID

**Success Response (204 No Content)**
Empty body.

**Error Responses**
- `404` – task not found for the tenant

---

### Pydantic Models Summary

* **Enums** – `Priority`, `Status` (shared between request and response)
* **Request** – `TaskCreate`, `TaskUpdate`, `TaskQuery` (dataclass for query params)
* **Response** – `TaskResponse`, `TaskListResponse`

All models use `from __future__ import annotations`, `str | None` syntax, and `Field(default_factory=…)` where appropriate.

---

## Data Model

### Database Table: `tasks`
| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `UUID` (PK) | `server_default=uuid4()` |
| `tenant_id` | `String` | `NOT NULL`, **indexed** |
| `title` | `String(200)` | `NOT NULL` |
| `description` | `Text` | nullable |
| `priority` | `String(10)` | `NOT NULL` (maps to `Priority` enum) |
| `status` | `String(20)` | `NOT NULL`, default `pending` |
| `created_at` | `DateTime(timezone=True)` | `server_default=func.now()` |
| `updated_at` | `DateTime(timezone=True)` | `server_default=func.now()`, `onupdate=func.now()` |

**Indexes** (defined in `__table_args__`)
- `Index("ix_tasks_tenant_id", "tenant_id")`
- `Index("ix_tasks_tenant_created", "tenant_id", "created_at")`

**ORM Mapping**
- SQLAlchemy 2.0 style: `Base` = declarative base, `Mapped[type]` with `mapped_column()`.
- The repository layer issues all queries with a `WHERE tenant_id = :tenant_id` filter.
- Business uniqueness rules (e.g., no duplicate titles within a tenant) are enforced with a `UniqueConstraint` on `(tenant_id, title)` (optional; can be added later without breaking isolation).

---

## Service Boundaries & Layered Architecture

```
┌──────────────────────────────────────────┐
│  API Layer (FastAPI routes)              │
│  - Input validation (Pydantic)           │
│  - Tenant resolution (dependency)        │
│  - HTTP error translation                │
└───────────────┬──────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│  Application Layer (services)            │
│  - TaskService: orchestrate CRUD         │
│  - Receives resolved TenantContext       │
│  - No raw SQL / ORM calls directly       │
└───────────────┬──────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│  Infrastructure Layer (repositories)     │
│  - TaskRepository: async SQLAlchemy      │
│  - All queries include tenant_id filter   │
│  - Returns domain DTOs / ORM models      │
└───────────────┬──────────────────────────┘
                │
┌───────────────▼──────────────────────────┐
│  Domain Layer (models, enums, DTOs)      │
│  - ORM model, Enums, DTOs                │
│  - Pure data, business rules             │
└──────────────────────────────────────────┘
```

### Key Implementation Decisions
1. **Async Throughout** – All route handlers, service methods, and repository functions are `async def`. The database engine uses `create_async_engine` with `aiosqlite`.
2. **Tenant Injection** – A FastAPI dependency `get_tenant_id` reads `X-Tenant-ID` header, validates it is non‑empty, and returns a `TenantID` value object. The service layer receives this and passes it to the repository.
3. **Cross‑Tenant Protection** – The repository always applies `.filter(Task.tenant_id == tenant_id)`. If a task ID does not match the tenant, the repository returns `None` → service raises `NotFoundError` → API returns `404`. This prevents information leakage about other tenants’ tasks.
4. **Request/Response Separation** – Pydantic schemas define the HTTP contract; ORM models are never serialised directly. Mapping happens in the application layer using a dedicated mapper or factory method.
5. **No Auto‑Migrations** – For simplicity, the application creates tables on startup with `await engine.begin() … create_all()`. The architecture can be extended with Alembic migrations later without altering the layered structure.

---

## Operational Constraints

### Tenant Isolation
- Every persisted record carries `tenant_id` and is indexed.
- Every read/write path includes `tenant_id` derived from the validated header.
- Cross‑tenant requests (e.g., fetching another tenant’s task by ID) return `404`, indistinguishable from a non‑existent task for the caller’s own tenant.
- The `tenant_id` is **never** exposed in API responses to avoid leaking tenant membership.

### Validation Gates (Implicit & Explicit)
- **Input Validation**: Pydantic `BaseModel` with `Field(min_length=1)` on required strings; enum validation ensures only allowed values.
- **Structural Validation** (aligned with team quality standards): upstream artifacts must contain required fields; downstream agents must verify these before proceeding.
- **Engineering Quality** (future SDLC): every endpoint is covered by E2E tests that exercise tenant isolation, invalid input, and success paths.

### Resumability
- The current architecture is stateless (no long‑running workflows), so checkpoints are not required. If batch operations (e.g., bulk import) are added later, idempotency keys and pending‑status state machines should be used.

### Sandbox Controls
- **Execution mode**: `containerized_build` inside a Docker image.
- **Network**: restricted to `files.pythonhosted.org` and `pypi.org` for package installation; no outbound connectivity to other hosts at runtime.
- **Dependency installation**: `pip` installs `fastapi`, `sqlalchemy`, `uvicorn`, `pytest`, `httpx`, `aiosqlite`, and their transitive dependencies.
- **System packages**: not allowed (all dependencies are pure Python).
- **Timeout**: 1800 seconds (30 minutes) – more than sufficient for test suite execution.
- **Startup**: `uvicorn` runs the FastAPI app; the test suite executes against the running container using `httpx.AsyncClient`.
- **Database**: SQLite file stored inside the container’s writable layer; no persistence across test runs is required.

### Deployment & Configuration
- All configuration is externalised via environment variables (`DATABASE_URL`, `HOST`, `PORT`), with sensible defaults for dev/staging.
- A `/healthz` endpoint returns `200` when the app is alive; no readiness check needed for a simple service.
- The container runs as a non‑root user after installing dependencies.
- Logging emits structured JSON with `request_id` (generated per request), `tenant_id`, and `endpoint`.

---

## Architecture Alignment with Acceptance Criteria

- **Architecture aligns with the product requirements handoff**: All CRUD endpoints, priority/status filtering, and tenant isolation are explicitly modeled.
- **Architecture decisions are documented**: This document captures every major design choice, rationale, and constraint.
- **Interfaces and constraints are defined**: The full API contract (request/response schemas, headers, error conditions) and operational constraints (tenant isolation, sandbox controls) are specified.
- **Tech stack reflected**: Python 3.12, FastAPI, SQLAlchemy (async), SQLite, Pydantic v2, Docker – all integrated into a layered architecture.
- **Sandbox controls documented**: Network restrictions, allowed hosts, dependency list, and runtime behavior are detailed.

---

## Output Payload

```json
{
  "output_payload": {
    "architecture_summary": "Layered FastAPI service with tenant isolation, CRUD endpoints, filtering, and async SQLAlchemy persistence on SQLite. All interfaces defined with Pydantic v2 schemas. Runs inside a Docker container with restricted network.",
    "primary_interfaces": [
      "POST /api/v1/tasks – Create task (TaskCreate → TaskResponse, 201)",
      "GET /api/v1/tasks – List tasks with optional status/priority filters (TaskListResponse, 200)",
      "GET /api/v1/tasks/{task_id} – Get single task (TaskResponse, 200/404)",
      "PUT /api/v1/tasks/{task_id} – Update task (TaskUpdate → TaskResponse, 200/404)",
      "DELETE /api/v1/tasks/{task_id} – Delete task (204/404)",
      "Common header: X-Tenant-ID enforced on all routes"
    ],
    "operational_constraints": {
      "tenant_isolation": "Every DB query filters by tenant_id; cross‑tenant access returns 404",
      "validation": "Pydantic v2 with Field(min_length=1) on required strings; enum validation",
      "sandbox": "Containerized build; network restricted to pypi.org/files.pythonhosted.org; pip dependencies only; SQLite in‑container"
    },
    "confidence_score": 0.95,
    "warnings": ["No authentication beyond tenant header; suitable for sandbox but must be replaced by JWT in production."],
    "risk_flags": []
  },
  "artifact": "# Architecture Design: FastAPI Task Manager API\n... (the full markdown document above)"
}
```