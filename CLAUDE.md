# Software Engineering Agent Team Operating Guide

This guide defines how the software engineering agent team collaborates to deliver production-grade software. Every agent on this team must follow these protocols.

## Team Composition

| Role | Responsibility | Upstream | Downstream |
|------|---------------|----------|------------|
| Product Manager | Translate business goals into explicit, testable requirements | Goal input | Architect, Engineer |
| Solution Architect | Design system architecture, interfaces, and constraints | Requirements | Engineer |
| Software Engineer | Produce implementation plan with test plan and verification commands | Architecture | Peer Reviewer |
| Peer Reviewer | Independent review of implementation; must not be the implementer | Implementation | SDET |
| SDET | Structural, engineering quality, and delivery readiness validation | Peer Review | Groundedness Validator |
| Groundedness Validator | Verify outputs are grounded in goal and retrieved evidence | All upstream | Final Delivery Gate |

## Collaboration Protocol

### Handoff Contract
Every upstream agent must produce output that downstream agents can consume without ambiguity:
- The output payload must contain all fields listed in the agent's output contract.
- Artifact drafts must be self-contained markdown documents with structured headings.
- Citations and evidence refs must trace back to retrieved knowledge or upstream artifacts.

### Reviewer Separation
The peer reviewer must be a different agent instance than the implementation engineer. This is enforced by the agent matcher during task dispatch. If only one engineer agent is available, the workflow must escalate to human review rather than self-reviewing.

### Validation Chain
The SDLC validation chain is sequential and non-skippable:
1. Structural Validation — verify all upstream artifacts exist and contain required fields
2. Engineering Quality Validation — verify test plan, verification commands, sandbox execution metadata, and peer review approval
3. Final Delivery Gate — verify no blocking validation outcomes remain from prior stages

Each validation stage receives the full upstream context. Validators must never operate on isolated fragments.

### Implementation Planning And Subtasks
Before writing code, the full-stack software engineer must generate an implementation plan by using the LLM chat API. The coding executor must not be used to create this plan. The plan must include delivery steps, test strategy, verification commands, effort estimate, complexity estimate, and subtask breakdown when effort or complexity is medium or higher.

When implementation work is decomposed, the parent Implementation task owns the final deliverable set and each child implementation subtask delivers one assigned slice in the shared workspace. A child subtask must preserve earlier child changes, add focused tests and verification evidence, and rely on the platform-managed git commit flow for traceability. The engineer must never manually run git history commands such as commit, push, checkout, or reset.

Before any implementation subtask writes code, it must inspect the existing workspace deeply enough to understand the current project: git history, git status, top-level structure, `.flowai/CODEBASE_CONTEXT.md` when present, relevant source files, tests, configuration, migrations, and docs. The subtask must build directly on prior subtask deliverables already committed in the shared workspace and must include a `Workspace analysis performed` section in its final response describing the files reviewed and how the changes extend the existing codebase.

### Escalation Path
When an agent encounters a blocking issue that cannot be resolved by retry or reassignment:
1. Record the issue with full context in the validation decision
2. Set the action to `require_human_review`
3. The orchestration layer will create a human review ticket with the requesting agent, review reason, and all upstream context

## Quality Standards

### Every Output Must Include
- A structured `output_payload` dictionary with role-specific fields
- At least one artifact draft (markdown document)
- An `instruction_profile` reference in the output payload
- A `confidence_score` between 0.0 and 1.0
- Any `warnings` or `risk_flags` discovered during execution

### Evidence-Based Reasoning
- Never fabricate data, metrics, or claims not supported by upstream outputs or retrieved knowledge
- Flag uncertainty explicitly with `uncertainty_flags` rather than presenting guesses as facts
- Prefer `retrieve_more_context` over unsupported conclusions when evidence is insufficient

### Tenant Isolation
- Every workflow run, task, artifact, and memory record is scoped to a tenant
- Never reference or leak data from one tenant's context into another's
- Preserve tenant ID propagation through all service calls and persistence operations


---

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


---

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

