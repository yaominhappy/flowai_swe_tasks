---
name: production-software-engineering
description: Production-grade software engineering skills for AI agent teams delivering backend services, databases, frontends, and full-stack applications. Covers architecture design, implementation patterns, testing strategies, security hardening, performance optimization, reliability engineering, and AI-native service patterns. Use when planning, implementing, reviewing, or validating software delivery tasks.
---

# Production Software Engineering Skills

## 1. Backend Service Patterns

### FastAPI Async Services
- Define all route handlers as `async def` — never block the event loop with synchronous I/O.
- Use dependency injection for auth context, database sessions, and service instances.
- Validate all request bodies with Pydantic v2 schemas; add `Field(min_length=1)` to required strings.
- Return structured error responses with consistent error codes across all endpoints.
- Use `BackgroundTasks` for non-critical side effects (telemetry, notifications) that must not block the response.

### Repository Pattern
- Repositories encapsulate all database queries — services never build raw SQL or ORM queries.
- Every query on business data includes a `tenant_id` filter.
- Use `select()` with explicit column lists for read-heavy paths.
- Use `returning()` on INSERT/UPDATE to avoid extra round-trips when the caller needs the result.

### DTO and Schema Separation
- API schemas (Pydantic `BaseModel`) define the HTTP contract — what the client sends and receives.
- DTOs define the internal contract between application layers.
- Database models define the persistence schema.
- Never pass ORM models through the API layer; always map to DTOs or API schemas.

## 2. Database Patterns

### Schema Design
- Use UUID primary keys for business entities (users, tenants, workflows, agents).
- Use integer autoincrement primary keys for high-write ledger and event tables.
- Add compound indexes on `(tenant_id, created_at)` for time-range tenant queries.
- Add single-column indexes on every FK column and every column used in WHERE or ORDER BY.
- Use `UniqueConstraint` for all business uniqueness rules — never rely on application-layer dedup.

### Migration Discipline
- Each migration file has a descriptive docstring explaining what changed and why.
- Create indexes before FK constraints so constraint validation can use them.
- Use `batch_alter_table` for SQLite compatibility on constraint additions.
- Pre-cleanup: NULL-ify orphaned nullable FK references before adding constraints.
- Guard PostgreSQL-specific DDL with `if bind.dialect.name == "postgresql"`.
- Use `if_not_exists=True` on index creation for idempotent migrations.

### Connection Management
- Use `async_sessionmaker` with `expire_on_commit=False` and `autoflush=False`.
- Pin `search_path` at the engine level for PostgreSQL schema isolation.
- Use `pool_pre_ping=True` to detect stale connections.

## 3. Frontend Patterns

### React / Next.js
- Use the App Router with server components for static content and client components for interactive UI.
- Use `useTransition` + `startTransition` for all async form submissions.
- Disable all form inputs (not just submit buttons) during `isPending`.
- Show explicit success feedback after every mutation — silence is ambiguous UX.
- Use `Promise.allSettled` for dashboard data fetches so one failure does not block others.

### State Management
- Distinguish three states: loading, loaded-with-data, loaded-empty/error.
- Never show literal placeholder strings like "Not loaded" — use dashes or skeletons.
- Use `useEffect` cleanup (`return () => { active = false }`) to prevent state updates on unmounted components.

### Accessibility
- Every input has a `<label>` with `htmlFor` or is wrapped in a `<label>` element.
- Button text reflects current state: "Saving..." during pending, "Save" when idle.
- Error messages use `aria-describedby` to associate with the relevant field.
- Form validation errors appear inline next to the field, not just at the top.

## 4. Testing Strategies

### Test Pyramid
- **Unit tests**: Pure logic, no I/O. Mock only external HTTP calls. Fast, deterministic.
- **Integration tests**: Real database (SQLite in tests). Test repository queries, service coordination, and DB constraints.
- **E2E tests**: Full HTTP stack via `AsyncClient` with real in-memory DB. Test auth, routing, validation, and response shapes.

### What To Test
- Tenant isolation in every query path.
- Auth resolution and token verification.
- Billing enforcement (credit consumption, subscription limits, demo isolation).
- SDLC validation chain ordering and completeness.
- API contract: valid request (2xx), invalid request (422), cross-tenant (404/403).

### What Not To Test
- Third-party library internals (Stripe SDK, Supabase SDK behavior).
- Framework guarantees (Pydantic field validation, FastAPI 422 handling).
- Implementation details that change frequently (exact log message text).

### Async Test Patterns
```python
@pytest.fixture
async def db_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
```

## 5. Security Hardening

### Authentication and Authorization
- Verify JWTs on every authenticated request — never cache auth decisions across requests.
- Resolve auth context once per request in the middleware/dependency layer.
- Reject requests from unverified or un-onboarded users at the API gateway.
- Never trust client-supplied tenant IDs — derive them from the verified auth token.

### Input Validation
- Validate at system boundaries: API input, webhook payloads, external API responses.
- Use `Field(min_length=1)` on all required string fields.
- Validate file paths stay within configured roots to prevent path traversal.
- Normalize blank strings from environment variables to `None` for optional fields.

### Secret Management
- Store secrets (API keys, OAuth tokens) on the filesystem, not in the database.
- Never log secret values — mask them in structured log output.
- Validate secret fields have minimum length at startup via `@field_validator`.
- Use obviously-placeholder default values for secrets so misconfiguration is visible.

### Common Vulnerabilities to Prevent
- SQL injection: use parameterized queries (ORM handles this; never build raw SQL strings).
- XSS: React auto-escapes by default; never use `dangerouslySetInnerHTML` with user content.
- CSRF: use token-based auth (Bearer JWT), not cookies, for API calls.
- Path traversal: validate all file paths against configured root directories.

## 6. Reliability Patterns

### Retry and Circuit Breaker
- Retry transient failures with exponential backoff and jitter (base delay 200-500ms, max 3 retries).
- Use circuit breakers on external service calls (LLM providers, Stripe, JWKS) — open after N consecutive failures, reset after a cooldown period.
- Fail-open for telemetry (usage logging, tracing) — never block business logic on observability writes.
- Fail-safe for auth and billing — never silently downgrade on transient errors.

### Idempotency
- Use idempotency keys for all state-mutating operations that may be retried.
- Store idempotency records to detect and deduplicate retries.
- Return the same response for duplicate requests with the same idempotency key.

### Graceful Degradation
- Dashboard KPI panels render independently — one failing data source does not block others.
- LLM provider failures trigger fallback to alternate providers via the router.
- Webhook processing records events first (status=received), processes later — never lose events.

## 7. Performance and Capacity

### Database Performance
- Use compound indexes for multi-column WHERE clauses (most selective column first).
- Use `selectin` loading for known-small relationship collections.
- Avoid N+1 queries: use `joinedload` or `selectinload` for relationships accessed in loops.
- Use integer PKs on high-write tables (ledgers, events) to avoid UUID B-tree fragmentation.

### API Performance
- Use `Promise.allSettled` or parallel `asyncio.gather` for independent data fetches.
- Paginate all list endpoints with cursor or offset-based pagination.
- Set appropriate `page_size` defaults (50) to prevent unbounded result sets.

### Frontend Performance
- Use Next.js server components for static content to reduce client JavaScript.
- Lazy-load heavy components (charts, editors) with `React.lazy` and `Suspense`.
- Avoid re-renders: use `useMemo` for expensive derived values, `useCallback` for stable function references.

## 8. AI-Native Service Patterns

### LLM Integration
- Route all LLM calls through a provider-agnostic router — never call provider SDKs directly from business logic.
- Use standardized request/response DTOs (`LLMRequest`, `LLMResponse`) across all providers.
- Extract and record token usage from every LLM response into the usage ledger.
- Apply per-provider retry logic with circuit breakers in the router layer.

### Agent Orchestration
- Build task graphs with explicit dependencies — never assume execution order.
- Persist agent output as durable artifacts immediately after execution.
- Pass full upstream context to each agent — never operate on isolated fragments.
- Enforce reviewer separation: peer reviewers must be different agents than implementers.
- Record execution memory (summary, citations, artifacts) for every completed task.

### Validation and Quality Gates
- Structural validation: verify all required fields exist in upstream output payloads.
- Engineering quality: verify test plans, verification commands, and sandbox execution metadata.
- Grounded truth: verify outputs are supported by goal context and retrieved knowledge.
- Emit structured validation decisions with `action` (pass, fail, retry, escalate) for the reflection layer.

### Human-in-the-Loop
- Human review is a designed escalation path, not a failure mode.
- Review tickets carry full context: task ID, requesting agent, review reason, upstream outputs.
- Review decisions (approve, reject, request_changes) trigger workflow resumption or remediation.
- Use idempotency keys on review tickets to prevent duplicate escalations.

## 9. Large-Scale Distributed Systems

### Event-Driven Architecture
- Use asynchronous messaging (message queues, event buses) to decouple services that do not need synchronous responses.
- Publish domain events when state changes occur — downstream consumers subscribe independently.
- Events must be idempotent: every consumer must tolerate receiving the same event more than once.
- Schema-version all event payloads so consumers can evolve independently of producers.
- Use dead-letter queues (DLQs) for messages that fail processing after maximum retries.

### Service Decomposition
- Decompose by business capability, not by technical layer — each service owns its data and API.
- Use API gateways to consolidate cross-cutting concerns (auth, rate limiting, request routing).
- Prefer synchronous HTTP for queries that need immediate results; prefer async messaging for commands that tolerate latency.
- Define explicit service contracts (OpenAPI schemas, Protobuf definitions) and version them.
- Avoid distributed transactions — use sagas (orchestration or choreography) for multi-service state changes.

### Data Consistency
- Prefer eventual consistency over distributed locks wherever business rules allow.
- Use the outbox pattern: write domain events to a local outbox table in the same transaction as the business write, then publish asynchronously.
- For operations that require strong consistency, keep them within a single service boundary.
- Implement compensating transactions (rollback sagas) for multi-step workflows that partially fail.

### API Versioning and Compatibility
- Version APIs in the URL path (`/v1/`, `/v2/`) for breaking changes.
- Prefer additive-only changes (new optional fields) over breaking changes wherever possible.
- Deprecate old API versions with a sunset date; emit deprecation warnings in response headers.
- Run old and new versions in parallel during migration periods — never break callers without notice.

## 10. CI/CD and Deployment Patterns

### Pipeline Design
- Every commit triggers: lint, type check, unit tests, integration tests in parallel.
- Merge to main triggers: full E2E test suite, container build, staging deployment.
- Production deployments use blue-green or canary strategies — never deploy directly to 100% of traffic.
- Pipeline fails fast: lint and compile checks run before expensive test suites.

### Container and Infrastructure
- Use multi-stage Docker builds: builder stage for dependencies, runtime stage for the final slim image.
- Pin base image versions to digests, not tags — tags are mutable and can change without notice.
- Run containers as non-root users with read-only filesystems where possible.
- Use health check endpoints (`/healthz`, `/readyz`) for load balancer and orchestrator integration.
- Store infrastructure configuration as code (Terraform, Pulumi, CloudFormation) — never configure by hand.

### Feature Flags and Gradual Rollout
- Use feature flags for any change that affects user-visible behavior in production.
- Roll out new features to internal users first, then a percentage of production traffic, then 100%.
- Feature flags must have an expiration date — remove them after rollout is complete.
- Never use feature flags as permanent configuration toggles — they are for rollout control only.

### Database Migration Safety
- Run migrations in a separate pipeline step before deploying new application code.
- Migrations must be backward-compatible: new code must work with the old schema during rollout.
- Use expand-contract pattern: first expand (add new column), deploy new code, then contract (remove old column) in a later release.
- Never drop columns, rename tables, or change types in the same deploy as the code that stops using them.

## 11. Monitoring, Alerting, and Incident Response

### Monitoring
- Instrument every service with the four golden signals: latency, traffic, errors, saturation.
- Use structured metrics with labels for tenant_id, endpoint, status_code, and provider.
- Set up dashboards for: API latency P50/P95/P99, error rate by endpoint, queue depth, database connection pool utilization.
- Monitor LLM provider health independently: latency, token throughput, error rate per provider.

### Alerting
- Alert on symptoms (elevated error rate, high latency) not causes (CPU usage).
- Set thresholds based on SLO burn rate: alert when error budget consumption accelerates.
- Page on customer-facing impact only; use non-urgent channels for internal-only degradation.
- Every alert must have a runbook link with investigation and remediation steps.

### Incident Response
- Define severity levels (SEV1–SEV4) with clear criteria and escalation paths.
- SEV1/SEV2: page on-call, open incident channel, assign incident commander.
- Write blameless postmortems for SEV1/SEV2 incidents within 48 hours.
- Track action items from postmortems to completion — recurring incidents indicate systemic issues.

## 12. Caching and Data Access Optimization

### Application-Level Caching
- Cache frequently-read, rarely-changing data (configuration, billing plans, team templates) with TTL-based expiration.
- Use `lru_cache` or `functools.cache` for in-process caching of deterministic computations.
- Invalidate caches on write: when data changes, clear the relevant cache entries immediately.
- Never cache tenant-scoped data in a shared cache without including tenant_id in the cache key.

### Database Query Optimization
- Use EXPLAIN ANALYZE on slow queries to identify missing indexes and inefficient join strategies.
- Avoid N+1 queries: use `selectinload` or `joinedload` for relationships accessed in loops.
- Use cursor-based pagination for large result sets — offset-based pagination degrades at high offsets.
- Partition high-volume tables (audit logs, usage ledger) by time range for query performance and data retention.

### CDN and Edge Caching
- Serve static frontend assets (JS, CSS, images) through a CDN with long cache-control headers and content-hash filenames.
- Use `stale-while-revalidate` for API responses that tolerate brief staleness.
- Never cache authenticated API responses at the CDN layer — they contain tenant-specific data.

## 13. Advanced Testing and Quality Validation

### Contract Testing
- Define API contracts (request/response schemas) and validate them in both producer and consumer test suites.
- Use schema-first development: generate client SDKs and server stubs from OpenAPI specifications.
- Run contract tests on every PR to catch breaking changes before they reach staging.

### Load and Performance Testing
- Define performance baselines: P95 latency, max throughput (requests/second), and resource utilization at steady state.
- Run load tests against staging with realistic traffic patterns (not just constant throughput).
- Test with tenant-realistic data volumes — empty databases do not reveal production query performance.
- Include LLM provider latency in performance models — LLM calls dominate response time for AI-native services.

### Chaos and Resilience Testing
- Inject failures in non-production environments: kill service instances, add network latency, simulate provider outages.
- Verify circuit breakers trip correctly under sustained failure and recover after the cooldown.
- Test graceful degradation: verify dashboards still render when one data source is unavailable.
- Validate retry logic handles partial failures (e.g., LLM call succeeds but usage ledger write fails).

### Regression Testing
- Maintain a regression test suite for every bug fix — the test must fail before the fix and pass after.
- Run the full regression suite on every PR merge, not just on release branches.
- Tag regression tests by severity: critical regressions block the release, non-critical are tracked.

### Acceptance Testing
- Map every acceptance criterion from the product requirements to at least one automated test.
- Run acceptance tests in an environment that mirrors production (same database engine, same auth provider).
- Include negative test cases: verify the system correctly rejects invalid inputs and unauthorized access.

### Security Testing
- Run static analysis (SAST) on every PR: detect SQL injection patterns, hardcoded secrets, insecure deserialization.
- Run dependency scanning (SCA) on every build: flag known vulnerabilities in third-party packages.
- Perform periodic penetration testing on the full API surface, focusing on auth bypass and tenant isolation.
- Test for privilege escalation: verify that a user in one tenant cannot access another tenant's resources by manipulating IDs or tokens.

### Validation Report Quality Standards
- Every validation report must include: validation scope, pass/fail status, action required, specific issues found, and actionable recommendations.
- Issues must be specific: "Implementation output is missing verification commands" not "quality issues found."
- Recommendations must be actionable: "Add pytest verification commands to the implementation plan" not "improve quality."
- Validation decisions must use structured enums (pass, fail, retry_same_agent, reassign, require_human_review) — never free-text decisions.

## 14. Software Quality Gates

These gates are mandatory for every code change. All gates must pass before a task is reported complete.

### Gate 1 — Line Coverage ≥ 80%

**Requirement**: Line coverage for the changed codebase must be ≥ 80% at all times.

**How to measure**:
```bash
# Backend
pytest --cov=app --cov-report=term-missing -q

# With per-file breakdown
pytest --cov=app --cov-report=term-missing --cov-fail-under=80 -q
```

**Rules**:
- Any new module or class must reach ≥ 80% line coverage independently.
- Global coverage must not regress below the pre-change baseline.
- Uncovered branches in business logic, auth, and billing paths are blocking defects — no exceptions.
- Use `# pragma: no cover` only for explicitly documented exclusions (e.g., unreachable defensive branches).

**Industry patterns**:
- Track coverage trends in CI; alert on coverage drops > 2% between PRs.
- Use `pytest-cov` with `--cov-fail-under` to make CI fail automatically below threshold.
- Use branch coverage (`--cov-branch`) for conditional-heavy code to catch untested branches, not just lines.
- Mutation testing (e.g., `mutmut`) complements line coverage: a line can be covered by a test that never asserts the outcome — mutation testing catches this.

### Gate 2 — E2E Test Coverage for Every New Feature

**Requirement**: Every new user-facing feature or API endpoint must have at least one E2E test.

**What counts as E2E**:
- Full HTTP stack via `AsyncClient` with a real in-memory database — no mock responses at the HTTP layer.
- Tests reside in `tests/e2e/`.
- Covers the primary success path AND at least one failure path (missing auth, invalid input, cross-tenant isolation violation).

**Feature coverage checklist**:
```
For every new endpoint or feature:
  ☐ E2E test: primary success path (2xx, correct response shape)
  ☐ E2E test: auth boundary (401/403 when unauthenticated or unauthorized)
  ☐ E2E test: input validation (422 on missing required fields)
  ☐ E2E test: tenant isolation (404/403 for cross-tenant resource access)
  ☐ E2E test: at least one business rule enforcement path
```

**Industry patterns**:
- Use test fixtures that provision a fresh tenant + user per test to ensure isolation between test cases.
- Parameterize E2E tests to cover multiple valid and invalid input combinations without duplicating boilerplate.
- Record API contract snapshots (response schema) and fail E2E tests on unexpected schema changes.
- Run E2E tests in CI against a staging-like environment (same DB engine, same auth provider) — not just SQLite.

### Gate 3 — Feature and Acceptance Criterion Coverage

**Requirement**: Every acceptance criterion in the task description must map to at least one automated test.

**Process**:
1. Before implementation, enumerate all acceptance criteria from the task spec.
2. For each criterion, write the test first (TDD) or write the test in the same PR as the code.
3. Negative criteria (e.g., "must reject cross-tenant access") require explicit negative tests that assert rejection.
4. Before marking done, verify each criterion has a corresponding passing test.

**Traceability**:
- Use test names or docstrings to reference the acceptance criterion they validate.
- Example: `def test_demo_tenant_cannot_consume_paid_credits():` clearly maps to a specific invariant.

**Industry patterns**:
- Behavior-Driven Development (BDD): write acceptance criteria as `Given / When / Then` scenarios; map each to a test.
- Use `pytest` markers (e.g., `@pytest.mark.acceptance`) to tag acceptance tests and run them separately.
- Generate a test coverage matrix (criterion → test) as part of the validation report.

### Gate 4 — Non-Regression

**Requirement**: Every existing test must pass after the change. Zero test deletions or `xfail` suppressions to hide regressions.

**Rules**:
- `pytest -q` must exit 0 with no failures, no errors, and no unexpected skips.
- `npm run test` must pass for all frontend tests.
- `npm run typecheck` must produce zero type errors.
- `python -m compileall app tests` must produce zero syntax errors.
- Any test that breaks because of the change must be fixed in the same PR — never deferred.
- If a test was wrong (not the code), the fix must include a comment explaining why the test was incorrect.

**Industry patterns**:
- Maintain a regression test suite tagged `@pytest.mark.regression` that runs on every PR.
- Pin test-breaking changes to the commit that introduced the regression using `git bisect` before fixing.
- Use test flakiness tracking (retry counts, failure rates) to distinguish regressions from flaky infrastructure.
- Treat `xfail` as technical debt: track `xfail` tests in a backlog and resolve them within one sprint.

### Gate 5 — Static Analysis and Type Safety

**Requirement**: Static analysis and type checking must pass cleanly before any code is merged.

**Backend**:
```bash
python -m compileall app tests   # Zero syntax errors
mypy app --strict                 # Zero type errors (where mypy is configured)
```

**Frontend**:
```bash
npm run typecheck   # Zero TypeScript errors (strict mode)
npm run lint        # Zero ESLint violations
```

**Rules**:
- No new `# type: ignore` or `@ts-ignore` suppressions without an inline comment explaining why they are safe.
- No new `Any` type annotations in strongly-typed paths (service layer, API schemas, DTOs).
- Linting violations are treated as defects, not warnings — zero tolerance for new violations.

**Industry patterns**:
- Integrate `ruff` or `flake8` for Python linting in CI alongside `mypy`.
- Use pre-commit hooks to catch type errors and linting violations before they reach CI.
- Use `eslint` with `@typescript-eslint/recommended-type-checked` for TypeScript — stricter than base recommended.
- Run SAST (e.g., `bandit` for Python, `semgrep`) on every PR to catch security anti-patterns early.

### Quality Gate Summary Table

| Gate | Tool | Threshold | Blocking |
|------|------|-----------|----------|
| Line coverage | `pytest --cov` | ≥ 80% per changed file | Yes |
| E2E coverage | `pytest tests/e2e/` | 1+ test per feature | Yes |
| Acceptance coverage | Manual + test matrix | 100% criteria mapped | Yes |
| Non-regression | `pytest -q` | 0 failures | Yes |
| Type safety | `mypy` / `npm run typecheck` | 0 errors | Yes |
| Static analysis | `compileall` / `eslint` | 0 errors | Yes |

### Enforcement in the SDLC Chain

- **Implementation agent**: self-assess all gates before submitting output.
- **Peer review agent**: verify coverage reports and test matrix are present in the implementation output.
- **SDET validation agent**: re-run the test suite and coverage check as part of structural validation; fail the gate if coverage is below threshold or tests are missing.
- **Engineering quality validation agent**: verify the quality gate summary is included in the implementation artifact.
- **Final delivery gate**: no workflow run reaches `completed` status if any quality gate has a recorded failure.
