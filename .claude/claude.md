# Software Engineering Agent Instructions

These instructions define the project context, architectural standards, and coding conventions that every AI agent on this software engineering team must follow when producing implementation plans, code, and validation outputs.

## Shared Workspace Collaboration Protocol

You are operating inside a **shared, git-tracked project workspace**. Multiple specialist agents (Product Manager, Architect, Engineer, Peer Reviewer, SDET, Validators) work in this same directory in sequence. Each agent's changes are committed as a separate git commit after execution.

### Before Writing Any File

1. Run `git log --oneline -10` to see what previous agents have already committed.
2. Run `git status --short` to verify your starting point.
3. Run `ls -la` to inspect the top-level directory structure.
4. Read `.flowai/CODEBASE_CONTEXT.md` (if it exists) for full context about the existing repository.
5. Inspect the relevant existing source files, tests, configuration, migrations, and docs before adding or modifying anything.
6. If FlowAI selected an existing repository, stay on the pre-created feature branch and treat the cloned codebase as the source of truth for all deliverables.
7. Include `Workspace analysis performed` in your final response, listing the key existing files you read and how your changes build on them.

### Core Rules

- **Build on existing code** — never recreate project structures that prior agents already established.
- **Work inside the existing directory layout** — add files to the directories already in use.
- **Do NOT run `git add`, `git commit`, `git push`, `git checkout`, `git reset`, or history-rewriting commands** — the FlowAI platform creates the feature branch, commits each agent's changes, and opens the final PR/MR automatically after final delivery is complete. Manual git commands create duplicate or conflicting history.
- **Do NOT create a new top-level project directory** if one already exists. The workspace IS the project.
- **Do NOT reinitialise the project** (e.g. `npm init`, `poetry new`, `django-admin startproject`) if the project is already initialised.

### For Implementation Engineers

- Before writing or editing code, generate and follow the implementation plan prepared by the LLM chat API.
- If this is a child implementation subtask, deliver only the assigned subtask scope and preserve all committed outputs from earlier subtasks.
- If this is a child implementation subtask, inspect prior subtask commits and files first, then extend the existing project in place instead of recreating modules or scaffolding.
- Treat the parent Implementation task as the owner of the final deliverables; each subtask contributes code, tests, configuration, documentation, and verification evidence into the same shared workspace.
- Read all files in `app/` (or the main source directory) before adding new modules.
- Write tests in the same `tests/` directory used by existing tests.
- Use the same dependencies and import paths already established in the codebase.

### For SDET / Validators

- Run existing tests with `python3 -m pytest -q` (or equivalent) to establish a baseline.
- Write new tests that import from the same source tree the engineer used.
- Do not change file structure — validate what is there.

## Architecture Standards

### Service Layer Structure
Organize backend services in four layers. Never bypass layers.

```
API layer        → Request validation, auth context resolution, HTTP routing
Application layer → Business logic coordination, workflow orchestration
Infrastructure   → Database repositories, external service clients
Domain           → Value objects, DTOs, enums, business rules
```

- API schemas validate input at the boundary using Pydantic v2 `Field(min_length=1)` on required strings.
- Application services receive resolved tenant context, never raw tokens or headers.
- Repositories are the only layer that issues SQL queries.
- All I/O operations use `async def`.

### Database Design
- Use SQLAlchemy `Mapped[T]` with `mapped_column()` — never legacy `Column()` syntax.
- Every FK column must have a named `Index(...)` in `__table_args__`.
- Use `UniqueConstraint` for all business uniqueness rules.
- High-write ledger tables use integer autoincrement PKs for insert performance.
- Use UUID PKs for all business entity tables.

### API Design
- RESTful endpoints with consistent naming: plural nouns for collections, IDs for resources.
- Return HTTP 422 for validation failures (handled automatically by Pydantic).
- Return HTTP 404 for missing resources within the tenant scope.
- Return HTTP 403 for cross-tenant access attempts.
- Include `request_id` in all structured log entries.

### Error Handling
- Validate at system boundaries (user input, external APIs) — trust internal code and framework guarantees.
- Use structured error responses with machine-readable error codes.
- Log errors as structured JSON with context (tenant_id, request_id, operation).
- Never expose internal stack traces in API responses.

## Coding Conventions

### Python
- Type-annotate all function signatures and return types.
- Use `from __future__ import annotations` at the top of every module.
- Prefer `str | None` over `Optional[str]`.
- Use Pydantic `BaseModel` for all DTOs; use `Field(default_factory=...)` for mutable defaults.
- Never use bare `except:` — always catch specific exception types.
- Keep functions under 50 lines; extract helpers when logic becomes nested.

### TypeScript / React
- Use TypeScript strict mode for all frontend code.
- Use `useTransition` with `startTransition` for async form submissions.
- Disable all form inputs during `isPending`, not just the submit button.
- Show explicit success/error feedback after every async action.
- Distinguish loading, loaded, and error states — never show literal "Not loaded" strings.
- Use `Promise.allSettled` for parallel dashboard data fetches.

### Testing
- Unit tests: pure logic, no I/O, mock only external HTTP calls.
- Integration tests: real database (SQLite for tests), not mocks.
- E2E tests: full HTTP stack via test client with real in-memory DB.
- Every API endpoint needs at least: valid request test, invalid request test (422), cross-tenant test (404/403).

## Quality Gates

Every code change must pass ALL of the following gates before it is considered complete.

### Gate 1 — Line Coverage ≥ 80%
- Run `pytest --cov=app --cov-report=term-missing -q` and verify overall line coverage is **≥ 80%**.
- Any new module, class, or function introduced by the change must individually reach ≥ 80% line coverage.
- Coverage is measured over the changed files; global coverage must not regress below the baseline.
- Uncovered lines in new code are a blocking defect — add tests or justify the exclusion explicitly.

### Gate 2 — E2E Test Coverage for Every New Feature
- Every new user-facing feature or API endpoint must have at least one E2E test that exercises the full HTTP stack from request to response.
- The E2E test must cover the primary success path and at least one failure path (invalid input, missing auth, or tenant isolation violation).
- E2E tests live in `tests/e2e/` and use `AsyncClient` with a real in-memory database — no mocks at the HTTP layer.
- Features without a corresponding E2E test are incomplete regardless of unit test coverage.

### Gate 3 — Feature and Acceptance Criterion Coverage
- Every acceptance criterion in the task description maps to at least one automated test (unit, integration, or E2E).
- Before marking a task done, enumerate each acceptance criterion and confirm the test that validates it.
- Negative acceptance criteria (e.g. "must not allow cross-tenant access") must have explicit negative tests that assert the rejection.

### Gate 4 — Non-Regression
- All existing tests must pass with zero failures: `pytest -q` exits 0.
- No existing test may be deleted or marked `xfail` to make the suite green — fix the regression.
- Frontend: `npm run typecheck` and `npm run test` must both pass.
- Any test that fails because of the change must be fixed in the same PR, not deferred.

### Gate 5 — Static Analysis and Type Safety
- Python: `python -m compileall app tests` must produce zero syntax errors.
- TypeScript: `npm run typecheck` (strict mode) must produce zero type errors.
- No new `# type: ignore` or `@ts-ignore` suppressions without an inline comment explaining why they are safe.

### Enforcement
- Agents must self-assess against all five gates before reporting a task as complete.
- Validation agents (SDET) must verify gate compliance as part of structural and engineering quality validation.
- Any gate failure is a blocking defect — return the task to the implementer with the specific gate that failed and the exact coverage or test output.

## Security Requirements

### Authentication
- Backend verifies JWTs on every authenticated request.
- Auth context is resolved once per request in the dependency layer.
- Never trust raw headers for identity or tenant resolution.

### Authorization
- All business queries include tenant_id filter.
- Demo and paid tenants have separate code paths.
- Secret values (API keys, OAuth credentials) are stored on the filesystem, not in the database.

### Input Validation
- Every required string field has `Field(min_length=1)`.
- Every enum field is validated against allowed values.
- File paths are validated to stay within configured roots (memory root, artifact root).

## Production Deployment

### Reliability
- Retry with exponential backoff and jitter on transient external calls (JWKS fetch, Stripe, LLM providers).
- Circuit breaker on LLM provider calls to prevent cascade failures.
- Fail-open for telemetry (LangSmith, usage ledger) — never block the user on observability writes.
- Fail-safe for auth and billing — never silently downgrade security or entitlement checks.

### Observability
- Structured JSON logs with request_id and trace_id propagation.
- Token usage recorded in the usage ledger after every LLM call.
- Optional LangSmith tracing as a fail-open overlay.

### Database Migrations
- Every Alembic migration has a human-readable docstring.
- Use `batch_alter_table` for all constraint additions (required for SQLite compatibility).
- Create indexes before adding FK constraints.
- NULL-ify orphaned nullable FK references before adding constraints.
- Guard PostgreSQL-specific operations with dialect checks.

### Scalability
- Design every service to be horizontally scalable — no local state between requests.
- Use connection pooling for databases; monitor pool utilization and tune pool size.
- Paginate all list endpoints; use cursor-based pagination for large datasets.
- Decouple write-heavy paths (event logging, usage ledger) from read-heavy paths where possible.

### Multi-Environment Configuration
- Support at least three environments: local development, staging, production.
- Use environment variables for all environment-specific configuration — never hardcode URLs or credentials.
- Validate all required configuration at startup via `@field_validator` — fail fast on misconfigured deployments.
- Keep staging as close to production as possible: same database engine, same auth provider, same external service integrations.

### Health Checks and Graceful Shutdown
- Expose `/healthz` (liveness) and `/readyz` (readiness) endpoints for load balancers and orchestrators.
- On shutdown signal (SIGTERM), stop accepting new requests, finish in-flight requests, then exit.
- Set readiness probe to fail during startup (before migrations are applied and dependencies are verified).
- Include database connectivity and critical dependency checks in the readiness probe.
