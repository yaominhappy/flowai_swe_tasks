## Implementation Plan: Build a FastAPI URL Shortener Service

### Objective
Deliver a production-grade FastAPI URL shortener service that accepts long URLs via a REST API, generates unique 6-character slugs, persists mappings in SQLite via SQLAlchemy async ORM, serves HTTP 302 redirects while atomically incrementing per-slug click counters, and exposes a stats endpoint. The service must be containerised with Docker, fully covered by a pytest suite (unit, integration, and E2E layers), and satisfy all five mandatory quality gates before delivery.

### Effort & Complexity
| Dimension   | Rating   | Reasoning |
|-------------|----------|----------|
| Effort      | medium   | Coordinated work across ORM model, repository, service, API layer, Dockerfile, and a multi-layer test suite exceeds a trivial scaffold but fits within a single sprint. |
| Complexity  | medium   | Domain logic is simple, but correct async SQLAlchemy layering, slug collision handling, dependency injection, and simultaneous satisfaction of all five quality gates adds meaningful coordination complexity. |

### Dependencies & Risks
**External dependencies**
- PyPI packages: fastapi, sqlalchemy[asyncio], uvicorn, pytest, httpx, aiosqlite — all must be resolvable from pypi.org and files.pythonhosted.org (the only allowed hosts in the sandbox).
- Python 3.12 runtime available in the sandbox.
- Docker daemon available for container build verification.

**Internal dependencies**
- Subtask 2 (repository + service) depends on Subtask 1 (ORM model + database bootstrap).
- Subtask 3 (API + E2E) depends on both Subtask 1 and Subtask 2.

**Risks and mitigations**
1. **aiosqlite driver availability** — SQLAlchemy async requires `aiosqlite` for SQLite. Risk: package not pinned or not installed. Mitigation: include `aiosqlite` explicitly in requirements.txt with a pinned version; verify with `python3 -m pip install -r requirements.txt` in setup.
2. **Slug collision under test** — random slug generation may produce collisions in tests, causing flakiness. Mitigation: seed the random generator in unit tests or mock `secrets.token_urlsafe` to produce deterministic values; integration tests use a fresh DB per test.
3. **Async session lifecycle in tests** — improper session teardown can leave SQLite file locks. Mitigation: use `tmp_path` fixture with `engine.dispose()` in teardown; use `AsyncClient` with `app` lifespan override for E2E tests.

### Test Strategy
**Unit tests** (`tests/test_models.py`, `tests/test_service.py`)
- Pure logic, no real I/O beyond in-memory SQLite for model tests.
- Mock the repository in service tests to verify slug generation, collision retry (up to 5 attempts), and delegation.
- Fast, deterministic, no network.

**Integration tests** (`tests/test_repository.py`)
- Real async SQLite database created in `tmp_path` per test.
- Verify repository CRUD: create mapping, retrieve by slug, increment click count, return None for unknown slug.
- Verify ORM constraints: duplicate slug raises IntegrityError.

**End-to-end tests** (`tests/e2e/test_api.py`)
- Full HTTP stack via `httpx.AsyncClient` with the FastAPI app and a real in-memory SQLite database.
- No mocks at the HTTP layer.
- Cover: POST /shorten success, GET /{slug} redirect + click increment, GET /stats/{slug} stats, 404 for unknown slug, 422 for missing/empty URL field.

**Coverage gate**: `pytest --cov=app --cov-report=term-missing --cov-fail-under=80 -q` must pass.

### Phases

#### Phase 1. Scaffold Project Structure, Dependencies, and Database Layer
**Objectives**
- Establish the canonical directory layout that all subsequent subtasks build on.
- Pin all dependencies to explicit versions.
- Define the SQLAlchemy async ORM model and database bootstrap.
- Prove the database layer works with unit tests.

**Steps**
1. Create top-level files: `requirements.txt`, `Dockerfile`, `README.md`, `.dockerignore`.
2. Pin dependencies in `requirements.txt`: `fastapi==0.111.0`, `sqlalchemy==2.0.30`, `uvicorn==0.29.0`, `httpx==0.27.0`, `pytest==8.2.0`, `pytest-asyncio==0.23.6`, `pytest-cov==5.0.0`, `aiosqlite==0.20.0`, `anyio==4.3.0`.
3. Create `app/__init__.py`, `app/models.py` (ORM model with Mapped[T] syntax), `app/database.py` (async engine, async_sessionmaker, create_all coroutine).
4. Create `tests/__init__.py`, `tests/test_models.py` with unit tests for model field presence and table creation.
5. Create `conftest.py` at the project root with shared async pytest fixtures.
6. Run `python3 -m compileall app tests` and `pytest -q` to verify.

**Exit Criteria**
- [ ] `requirements.txt` lists all dependencies with pinned versions.
- [ ] `app/models.py` defines `ShortenedUrl` with id, slug (unique), original_url, click_count, created_at.
- [ ] `app/database.py` exposes `async_engine`, `AsyncSessionLocal`, and `create_all()`.
- [ ] `python3 -m compileall app tests` exits 0.
- [ ] `pytest tests/test_models.py -q` passes.
- [ ] Coverage on `app/models.py` and `app/database.py` ≥ 80%.

**Verification Commands**
```bash
python3 -m pip install -r requirements.txt
python3 -m compileall app tests
python3 -m pytest tests/test_models.py --cov=app --cov-report=term-missing -q
```

#### Phase 2. Implement Repository and Application Service Layer
**Objectives**
- Encapsulate all database queries in a repository class.
- Implement slug generation with collision retry in the service layer.
- Achieve ≥ 80% coverage on both new modules.

**Steps**
1. Inspect Phase 1 deliverables: `app/models.py`, `app/database.py`, `conftest.py`.
2. Create `app/repository.py` with `UrlRepository`: async methods `create`, `get_by_slug`, `increment_clicks`.
3. Create `app/service.py` with `UrlShortenerService`: `shorten(original_url)` generates slug via `secrets.token_urlsafe(4)[:6]`, retries on collision (max 5), calls repository; `get_stats(slug)` delegates to repository.
4. Write `tests/test_repository.py`: integration tests with real async SQLite (tmp_path), covering create, get, increment, not-found, duplicate-slug constraint.
5. Write `tests/test_service.py`: unit tests mocking repository, covering slug generation, collision retry exhaustion, and stats delegation.
6. Run full test suite.

**Exit Criteria**
- [ ] `app/repository.py` implements `create`, `get_by_slug`, `increment_clicks` as async methods.
- [ ] `app/service.py` implements `shorten` and `get_stats` with collision retry.
- [ ] `tests/test_repository.py` covers create, get, increment, not-found, and duplicate-slug paths.
- [ ] `tests/test_service.py` covers slug generation, collision retry, and stats delegation.
- [ ] `python3 -m compileall app tests` exits 0.
- [ ] `pytest -q --cov=app --cov-fail-under=80` passes.

**Verification Commands**
```bash
python3 -m compileall app tests
python3 -m pytest tests/test_repository.py tests/test_service.py --cov=app --cov-report=term-missing -q
```

#### Phase 3. Expose FastAPI Endpoints, Wire Application, and Deliver E2E Tests
**Objectives**
- Implement all three API endpoints with correct HTTP semantics.
- Wire FastAPI dependency injection for session and service.
- Deliver E2E tests covering all acceptance criteria.
- Verify Dockerfile builds and all quality gates pass.

**Steps**
1. Inspect Phase 1 and Phase 2 deliverables: all app/ modules and existing tests.
2. Create `app/schemas.py` with Pydantic v2 request/response models: `ShortenRequest` (url: str, Field(min_length=1)), `ShortenResponse`, `StatsResponse`.
3. Create `app/main.py`: FastAPI app with lifespan (calls `create_all` on startup), dependency `get_session`, dependency `get_service`, three route handlers.
4. Implement `POST /shorten`: validate input, call service.shorten, return ShortenResponse.
5. Implement `GET /{slug}`: call service.get_stats (read-only), increment via repository, return RedirectResponse(302); return 404 if not found.
6. Implement `GET /stats/{slug}`: return StatsResponse; return 404 if not found.
7. Create `tests/e2e/__init__.py` and `tests/e2e/test_api.py` with AsyncClient E2E tests.
8. Verify Dockerfile: `FROM python:3.12-slim`, COPY, pip install, EXPOSE 8000, CMD uvicorn.
9. Run full suite with coverage.

**Exit Criteria**
- [ ] `POST /shorten` returns 200 with short_url and slug for valid input.
- [ ] `POST /shorten` returns 422 for missing or empty url field.
- [ ] `GET /{slug}` returns 302 to original_url and increments click_count.
- [ ] `GET /{slug}` returns 404 for unknown slug.
- [ ] `GET /stats/{slug}` returns slug, original_url, click_count.
- [ ] `GET /stats/{slug}` returns 404 for unknown slug.
- [ ] E2E tests in `tests/e2e/test_api.py` cover all six paths above.
- [ ] `python3 -m compileall app tests` exits 0.
- [ ] `pytest -q --cov=app --cov-fail-under=80` passes with 0 failures.
- [ ] All five quality gates explicitly verified and passing.

**Verification Commands**
```bash
python3 -m compileall app tests
python3 -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=80
python3 -m pytest tests/e2e/ -v
```

### Verification
Final end-to-end verification across all phases:
```bash
# 1. Install dependencies
python3 -m pip install -r requirements.txt

# 2. Static analysis
python3 -m compileall app tests

# 3. Full test suite with coverage gate
python3 -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=80

# 4. E2E tests in isolation
python3 -m pytest tests/e2e/ -v

# 5. Collect-only sanity check
python3 -m pytest --collect-only -q

# 6. Docker build verification
docker build -t url-shortener:latest .
```