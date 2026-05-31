# Bug Fix Summary: FastAPI Task Manager Service

## Audit Date

2026-06-01

## Files Changed

| File | Change |
|------|--------|
| `app/schemas/task.py` | Added field validators to reject explicit `null` for `title`, `priority`, `status`; allowed `description=null` to clear the field |
| `app/services/task_service.py` | Removed `if value is not None` filter that blocked clearing `description`; added clarifying comments |
| `app/database.py` | Added `autoflush=False` to `async_sessionmaker` |
| `app/main.py` | Added `/readyz` readiness endpoint; enhanced middleware with structured request logging |
| `pyproject.toml` | Set `asyncio_default_fixture_loop_scope = "function"` |
| `tests/conftest.py` | Added `autoflush=False` to test session factory |
| `tests/e2e/conftest.py` | Added `autoflush=False` to E2E session factory |
| `tests/test_health.py` | Added `test_readyz_endpoint` |
| `tests/unit/test_task_schemas.py` | Added tests for null rejection and null description acceptance |
| `tests/unit/test_task_service.py` | Added tests for clearing description and updated_at refresh |
| `tests/e2e/test_tasks_api.py` | Added E2E tests for null handling, readiness, and request IDs |

---

## Defect Catalog

### B1 — **CRITICAL**: Cannot clear description field via update
- **Module**: `app/services/task_service.py:89-92`
- **Impact**: Clients could set a description but could never remove it. Sending `"description": null` was silently ignored.
- **Root Cause**: The `update` method used `model_dump(exclude_unset=True)` followed by `if value is not None`, which filtered out explicitly-set `None` values for all fields.
- **Fix**: Removed the `if value is not None` guard. Schema-level validators now reject `None` for fields that must not be nulled (`title`, `priority`, `status`), while `description=None` is correctly allowed through.
- **Tests Added**:
  - Unit: `test_update_clears_description` (service), `test_null_description_accepted` (schema)
  - E2E: `test_update_clears_description`

### B2 — **HIGH**: TaskUpdate schema accepted null for required fields without validation
- **Module**: `app/schemas/task.py` (`TaskUpdate`)
- **Impact**: A client could send `"title": null`, `"priority": null`, or `"status": null` — these would either be silently ignored (before B1 fix) or set the field to null (after B1 fix without schema hardening).
- **Root Cause**: Field types declared as `str | None`, `Priority | None`, `Status | None` with `default=None` — `None` passed Pydantic type validation.
- **Fix**: Added `@field_validator` for `title`, `priority`, and `status` that explicitly reject `None` with a descriptive error message.
- **Tests Added**:
  - Unit: `test_null_title_rejected`, `test_null_priority_rejected`, `test_null_status_rejected`
  - E2E: `test_update_with_null_title_rejected`, `test_update_with_null_priority_rejected`, `test_update_with_null_status_rejected`

### B3 — **HIGH**: Missing `autoflush=False` on session factory
- **Module**: `app/database.py:46-49`
- **Impact**: Without `autoflush=False`, SQLAlchemy may issue implicit flushes during read operations, potentially causing unexpected database writes or constraint violations mid-read.
- **Root Cause**: The project guidelines specify `autoflush=False` for production-grade services. It was omitted from the session factory.
- **Fix**: Added `autoflush=False` to `async_sessionmaker(...)` in `_get_session_factory()` and in all test fixtures.
- **Tests**: Existing integration and E2E tests validate correct database behavior.

### B4 — **MEDIUM**: Missing `/readyz` readiness endpoint
- **Module**: `app/main.py`
- **Impact**: Production orchestrators (Kubernetes, Docker Compose) cannot distinguish between "process alive" and "ready to serve traffic." The `/healthz` liveness probe alone is insufficient.
- **Root Cause**: Architecture standards require both `/healthz` and `/readyz`. Only `/healthz` was implemented.
- **Fix**: Added `GET /readyz` endpoint returning `{"status": "ok", "database": "connected"}`.
- **Tests Added**:
  - Smoke: `test_readyz_endpoint`
  - E2E: `test_readyz_returns_ok`

### B5 — **MEDIUM**: No structured request logging with request_id
- **Module**: `app/main.py`
- **Impact**: The middleware attached `X-Request-ID` to responses but never logged it. Requirement FR3.3 calls for structured log entries including `request_id`, endpoint, and status code.
- **Root Cause**: The middleware only performed response header injection; no log emission.
- **Fix**: Enhanced the middleware to emit a structured log line with `request_id`, `method`, `path`, and `status_code` on every response.
- **Tests Added**:
  - E2E: `TestRequestId` class with tests for healthz, readyz, list, get, and delete endpoints

### B6 — **LOW**: Pytest deprecation warning
- **Module**: `pyproject.toml`
- **Impact**: `pytest-asyncio` emits a deprecation warning about `asyncio_default_fixture_loop_scope` being unset.
- **Root Cause**: Default value changed between pytest-asyncio versions.
- **Fix**: Set `asyncio_default_fixture_loop_scope = "function"` in `[tool.pytest.ini_options]`.
- **Tests**: The warning is eliminated; all existing tests continue to pass.

### B7 — **LOW**: Redundant `onupdate` on `updated_at`
- **Module**: `app/models/task.py:77-83`
- **Impact**: None functional. The model declares `onupdate=lambda: datetime.now(timezone.utc)` but the service always sets `updated_at` explicitly. The `onupdate` is dead code.
- **Root Cause**: Defensive coding — both layers try to update the timestamp.
- **Fix**: Not changed (non-blocking). The service's explicit set takes precedence; the `onupdate` serves as a safety net for direct ORM writes.
- **Tests**: Existing tests validate correct `updated_at` behavior.

---

## Non-Regression Verification

All 80 pre-existing tests continue to pass. The 17 new tests bring the total to 97 passing tests with zero failures, zero errors, and zero unexpected skips.

```
pytest -q: 97 passed in 0.67s
```
