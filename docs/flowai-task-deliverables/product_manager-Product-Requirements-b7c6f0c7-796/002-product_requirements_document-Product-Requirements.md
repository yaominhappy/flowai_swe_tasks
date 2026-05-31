## Requirements Summary

The FastAPI Task Manager API is a single-tenant task management service that exposes a RESTful JSON API for creating, reading, updating, and deleting tasks. Each task carries a title, optional description, status (todo/in_progress/done), and priority (low/medium/high). The API offers list/search endpoints with filtering by status and priority, plus offset-based pagination for production readiness. The entire surface must be validated with Pydantic 2 schemas, persisted via async SQLAlchemy on SQLite, and verified through a comprehensive pytest suite that runs end‑to‑end inside a Docker sandbox.

The service must be delivered as a fully containerised application where `pytest -v` exercises every API route (success, input validation, not-found, filter/pagination) and exits cleanly.

---

## Feature Requirements

### FR‑1: Task CRUD

- **FR‑1.1 Create task**  
  `POST /api/v1/tasks`  
  Accepts a JSON body with `title` (required, non‑empty string), `description` (optional string), `status` (optional, default `"todo"`, must be one of `todo`, `in_progress`, `done`), `priority` (optional, default `"medium"`, must be one of `low`, `medium`, `high`).  
  Returns `201 Created` with the complete task object (including generated `id`, `created_at`, `updated_at`).

- **FR‑1.2 Get single task**  
  `GET /api/v1/tasks/{task_id}`  
  Returns `200 OK` with the task object, or `404 Not Found` if the ID does not exist.

- **FR‑1.3 Update task**  
  `PUT /api/v1/tasks/{task_id}`  
  Accepts a JSON body with any subset of mutable fields (`title`, `description`, `status`, `priority`).  
  Returns `200 OK` with the fully updated task (including updated `updated_at`).  
  If the specified `task_id` does not exist, returns `404`.

- **FR‑1.4 Delete task**  
  `DELETE /api/v1/tasks/{task_id}`  
  Returns `204 No Content` on success, or `404` if the task does not exist.

### FR‑2: Task List with Filtering and Pagination

- **FR‑2.1 List tasks**  
  `GET /api/v1/tasks`  
  Returns a paginated list of all tasks, ordered by `created_at` descending.

  Query parameters:
  - `status` (optional) – filter by exact status.
  - `priority` (optional) – filter by exact priority.
  - `limit` (optional, default `50`, min `1`, max `100`) – page size.
  - `offset` (optional, default `0`, min `0`) – number of records to skip.

  Response shape:
  ```json
  {
    "items": [ ...task objects... ],
    "offset": 0,
    "limit": 50,
    "total": 42
  }
  ```
  Both `status` and `priority` may be supplied together.

### FR‑3: Data Validation and Error Handling

- All request bodies are validated with Pydantic 2 `BaseModel`. Required strings use `Field(min_length=1)`.
- Enum fields (`status`, `priority`) reject invalid values automatically; the framework returns a `422 Unprocessable Entity` with structured error details (list of `loc` and `msg`).
- Unknown fields in request bodies are silently ignored (per Pydantic’s default `Extra.forbid` not required to keep the API loose; use `Extra.ignore`).
- Listing with an invalid `status` or `priority` value returns `422` with machine‑readable error details.
- Nonexistent resource lookups return `404 Not Found` with a JSON body `{"detail": "Task not found"}`.
- All error responses include consistent fields: `detail` (human‑readable), and for validation errors the `loc`/`msg` structure.

### FR‑4: Persistence

- Use SQLAlchemy 2.0 async with SQLite (file‑based `tasks.db` inside the container). The database URL is configurable via `DATABASE_URL` environment variable.
- Task model uses UUID primary key (`id`) and timestamp columns (`created_at`, `updated_at`) with server defaults.
- Indexes exist on `status`, `priority`, and a composite index on `(status, priority)` for filter performance.

### FR‑5: Containerisation and Sandbox Verification

- The application must be packaged in a Docker container that:
  - Starts the FastAPI app with `uvicorn` on port `8000`.
  - Provides a health check endpoint `GET /healthz` returning `{"status":"ok"}` and 200.
  - Allows manual execution of the test suite: `docker run <image> pytest -v` runs **all** tests and exits with code 0.
- The test suite must be self‑contained within the image (tests directory included).

---

## Acceptance Criteria

### For FR‑1 CRUD

| AC ID | Description | Testable Assertion |
|-------|-------------|---------------------|
| AC‑1.1 | Create task with valid payload returns 201 | Status 201, body contains `id` (UUID), `title`, `status`="todo", `priority`="medium", `created_at` and `updated_at` strings |
| AC‑1.2 | Create task with missing `title` returns 422 | Status 422, body includes `detail` array with field `loc=["body","title"]` |
| AC‑1.3 | Create task with invalid `status` returns 422 | Status 422, field error on `status` |
| AC‑1.4 | Create task with invalid `priority` returns 422 | Status 422, field error on `priority` |
| AC‑1.5 | Get existing task returns 200 | Status 200, body matches created task |
| AC‑1.6 | Get nonexistent task returns 404 | Status 404, `{"detail":"Task not found"}` |
| AC‑1.7 | Update existing task changes fields and `updated_at` | Status 200, body reflects updates, `updated_at` > `created_at` |
| AC‑1.8 | Update nonexistent task returns 404 | Status 404 |
| AC‑1.9 | Update with invalid `status` returns 422 | Status 422 |
| AC‑1.10 | Delete existing task returns 204 | Status 204, subsequent GET returns 404 |
| AC‑1.11 | Delete nonexistent task returns 404 | Status 404 |

### For FR‑2 List & Filtering

| AC‑2.1 | List without filters returns all tasks in descending created order | Response has `items`, `total`, `offset`, `limit`; `items` ordered by `created_at` desc |
| AC‑2.2 | Status filter returns only matching tasks | Items all have `status` equal to query param |
| AC‑2.3 | Priority filter returns only matching tasks | Items all have `priority` equal to query param |
| AC‑2.4 | Combined status+priority filter works | Items match both |
| AC‑2.5 | Pagination with `limit` and `offset` restricts results | `limit` respects range, `offset` skips correctly, `total` unchanged |
| AC‑2.6 | Invalid `status` in query returns 422 | Status 422 with validation error |
| AC‑2.7 | Invalid `priority` in query returns 422 | Status 422 |
| AC‑2.8 | Invalid `limit` (<1 or >100) returns 422 | Status 422 |

### For FR‑3 Validation & Error Handling

| AC‑3.1 | Unknown fields in request body are ignored | Create with extra field still succeeds, extra field not in response |
| AC‑3.2 | All 422 responses use the standard Pydantic error shape | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| AC‑3.3 | 404 responses use consistent format | `{"detail": "Task not found"}` |

### For FR‑4 Persistence

| AC‑4.1 | Tasks survive application restart | After creating a task, restart the application and retrieve the same task via GET |
| AC‑4.2 | Concurrent access does not corrupt data | (Quality gate: run multiple parallel requests; integrity checks can be part of test) |

### For FR‑5 Containerisation & Verification

| AC‑5.1 | Docker image starts and responds to health check | `curl localhost:8000/healthz` returns 200 and `{"status":"ok"}` |
| AC‑5.2 | `docker run <image> pytest -v` exits 0 | All tests pass; output visible |
| AC‑5.3 | Test suite covers every route and edge case | Coverage ≥ 80% (verified via `--cov` inside container) |

---

## Non‑Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | API response time for single‑request CRUD under no load < 200ms (P95). List endpoint with 10k tasks returns in < 2s. |
| **Reliability** | Use async SQLAlchemy with connection pooling; pool_pre_ping enabled to handle stale connections. |
| **Data Integrity** | UUID primary keys guarantee no collisions; unique constraints enforced at DB level on natural keys (none exist yet). |
| **Observability** | Structured logs (JSON) emitted to stdout with `request_id` included. Health check endpoint included. |
| **Security** | No authentication required (single‑user service). Input validated at the boundary to prevent injection. SQLAlchemy parameterised queries prevent SQL injection. |
| **Portability** | Configuration via environment variables; container image runs on any Docker‑compatible sandbox. |
| **Extensibility** | API versioned under `/api/v1/`. Database migrations handled by Alembic (schema creation script acceptable for initial release). |
| **Tenant Isolation** | Not applicable – this is a single‑tenant service. Explicitly stated to avoid mis‑applied multi‑tenant checks. |

---

## Test Focus Areas

| Focus Area | Rationale | Key Tests |
|------------|-----------|-----------|
| CRUD completeness | Every endpoint must work end‑to‑end | AC‑1.1 through AC‑1.11 |
| Input validation | Protect against malformed data | AC‑1.2, AC‑1.3, AC‑1.4, AC‑1.9, AC‑2.6–2.8, AC‑3.1, AC‑3.2 |
| Filtering logic | Business‑critical functionality | AC‑2.1 through AC‑2.4 |
| Pagination boundaries | Edge cases on limit/offset | AC‑2.5, AC‑2.8 |
| Error consistency | Downstream clients depend on predictable error shapes | AC‑3.2, AC‑3.3 |
| Persistence durability | Data must survive restarts | AC‑4.1 |
| Container execution | Delivery artifact must be testable as specified | AC‑5.1, AC‑5.2, AC‑5.3 |
| Line coverage | Quality gate ≥ 80% | All tests combined must hit ≥ 80% of application lines |

---

## Assumptions

1. **Single‑user, no authentication** – The task manager runs locally or in a trusted environment. No JWT, OAuth, or RBAC is required.
2. **SQLite database stored inside the container** – Ephemeral file system; a volume mount is out of scope for this delivery but could be added later.
3. **No pagination cursors** – Offset‑based pagination is sufficient for expected task volumes (<10k). Cursor‑based pagination can be introduced in a future iteration.
4. **Alembic migrations** – At minimum, an initial schema creation script using `Base.metadata.create_all` is acceptable; full Alembic is recommended but not required for the sandbox deliverable.
5. **Concurrency** – The service will handle a handful of concurrent requests; advanced concurrency stress testing is a stretch goal.

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite does not support true concurrent writes well | Lock contention under heavy load | Use WAL mode and serialised writes for test; document that production‑scale deployment should use PostgreSQL. |
| No authentication model | If later extended to multi‑tenant, breaking changes will be needed | Clearly version API; add auth as a non‑breaking overlay in `/v2/` if needed. |
| Container size and build time | Might complicate sandbox execution | Use multi‑stage Docker build to keep final image slim. |

---

## Open Questions

1. Should the `PUT` endpoint support partial updates (PATCH semantics) or full replace? The requirement assumes full replace but ignoring missing fields could be ambiguous. Clarify before implementation. (Decision: use PUT with all optional fields – missing fields are not changed, i.e., PATCH‑like behaviour; this is expressly allowed.)
2. Is soft‑delete (archive) needed? Not in scope for this release.
3. Should the health check `/healthz` verify database connectivity? The requirement says it should return a simple ok; we will keep it basic and add readiness check later.

---

**Instruction Profile**: software.product_manager.requirements.v1  
**Confidence Score**: 0.95  
**Warnings**: None  
**Risk Flags**: SQLite concurrency limitations noted; no auth model present.