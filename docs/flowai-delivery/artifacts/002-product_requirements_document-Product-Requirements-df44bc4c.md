## Requirements Summary

The target service is a **tenant-isolated URL shortener** built with FastAPI, SQLAlchemy, and SQLite. It exposes three core endpoints: create a short link, serve a 302 redirect for a slug, and return per‑slug click statistics. All endpoints are scoped to the authenticated tenant. The service is designed to be tested inside a containerised sandbox using a full pytest suite.

| Requirement ID | Capability | Key Acceptance Criteria |
|----------------|------------|-------------------------|
| FR‑1 | Shorten URL | Valid URL generates a unique slug, persisted with tenant_id. Returns slug and original URL. |
| FR‑2 | Redirect | Visiting `/r/{slug}` issues a 302 redirect to the original URL and increments click count. |
| FR‑3 | Stats | `/stats/{slug}` returns slug, original URL, creation timestamp, and click count for the tenant’s slug. |
| FR‑4 | Error handling | Missing slug → 404; invalid input → 422; cross‑tenant access → 404/403; unsupported HTTP method → 405. |
| NFR‑1 | Tenant isolation | All operations are filtered by the tenant derived from the JWT auth context. |
| NFR‑2 | Performance | Redirect path responds in ≤ 30 ms (p95) under moderate load. Stats endpoint ≤ 50 ms. |
| NFR‑3 | Security | Input validation prevents injection; no internal details leaked in errors; all endpoints behind auth. |
| NFR‑4 | Observability | Structured logging with request_id; click counters updated atomically; health check endpoints. |

---

## Feature Requirements

### FR‑1 – Shorten a URL

**Endpoint**: `POST /shorten`  
**Auth**: Required (Bearer JWT)  
**Request body** (JSON):
```json
{
  "url": "https://example.com/some-long-path"
}
```

**Fields**:
- `url`: string, required, `Field(min_length=1, max_length=2048)`. Must be a valid absolute HTTP or HTTPS URL (accept `http://` and `https://` only).

**Behaviour**:
1. Validate input; return 422 on missing/invalid URL.
2. Extract `tenant_id` from the authenticated JWT token’s claims.
3. Generate a random alphanumeric slug of length 6–10 characters (a‑z, A‑Z, 0‑9).    
   *The generation must be collision‑resistant within the tenant scope – before persisting, verify uniqueness for the same tenant; retry on collision (max 3 attempts).*
4. Persist a new record with:
   - `id`: UUID PK
   - `tenant_id`: string (FK / index)
   - `slug`: string (unique per tenant)
   - `original_url`: string
   - `created_at`: UTC datetime
   - `click_count`: integer, default 0
   - `updated_at`: UTC datetime
5. Return HTTP 201 with JSON body:
   ```json
   {
     "slug": "aBc12X",
     "original_url": "https://example.com/some-long-path",
     "created_at": "2025-01-01T00:00:00Z"
   }
   ```

**Acceptance criteria – FR‑1**  
- AC‑1.1: POST with valid HTTPS URL creates a new slug and returns 201.  
- AC‑1.2: The slug is unique per tenant; two calls with the same URL produce different slugs.  
- AC‑1.3: POST with missing `url` field returns 422 with a structured error.  
- AC‑1.4: POST with an empty string or a URL that is not absolute HTTP(S) (e.g., `ftp://a.com`, `justtext`) returns 422.  
- AC‑1.5: POST with a URL longer than 2048 characters returns 422.  
- AC‑1.6: Unauthenticated request returns 401.  
- AC‑1.7: Request with a valid JWT but without a tenant claim (or with an unregistered tenant) returns 403.  
- AC‑1.8: After three consecutive collisions during slug generation, the service must return 500 (extremely rare edge case – verified by unit test with mocked RNG).

---

### FR‑2 – Redirect (slug resolution)

**Endpoint**: `GET /r/{slug}`  
**Auth**: Required (Bearer JWT) – the tenant context is derived from the token and used to look up the slug only within that tenant’s scope.

**Behaviour**:
1. Receive slug, look up by `slug` AND `tenant_id`.
2. If found:
   - Atomically increment `click_count` (use a database-side increment to avoid race conditions).
   - Update `updated_at` to current time.
   - Return HTTP 302 with `Location` header set to `original_url`.
3. If not found: return HTTP 404 with JSON body:
   ```json
   {
     "detail": "Slug not found"
   }
   ```

**Acceptance criteria – FR‑2**  
- AC‑2.1: GET a valid slug returns 302 and redirects to the stored URL.  
- AC‑2.2: The response includes the `Location` header with the exact original URL.  
- AC‑2.3: After a redirect, the `click_count` for that slug increases by exactly 1.  
- AC‑2.4: Simultaneous redirects (concurrent requests) each correctly increment the counter – no lost updates (verified via integration test).  
- AC‑2.5: GET a slug that belongs to another tenant returns 404 (never leaks existence of a slug from another tenant).  
- AC‑2.6: GET a non‑existent slug for the current tenant returns 404.  
- AC‑2.7: Unauthenticated request returns 401.  
- AC‑2.8: GET request with unsupported method (POST, PUT, DELETE) on the same path returns 405.

---

### FR‑3 – Per‑slug statistics

**Endpoint**: `GET /stats/{slug}`  
**Auth**: Required (Bearer JWT) – tenant‑scoped lookup.

**Behaviour**:
1. Look up slug by `slug` AND `tenant_id`.
2. If found, return HTTP 200 with JSON:
   ```json
   {
     "slug": "aBc12X",
     "original_url": "https://example.com/some-long-path",
     "created_at": "2025-01-01T00:00:00Z",
     "click_count": 42
   }
   ```
3. If not found, return 404 (as in FR‑2).

**Acceptance criteria – FR‑3**  
- AC‑3.1: GET stats for a slug that exists in the tenant returns 200 with all fields present and correct.  
- AC‑3.2: The `click_count` matches the number of previous redirects.  
- AC‑3.3: Accessing stats for a slug that belongs to another tenant returns 404.  
- AC‑3.4: Accessing stats for a non‑existent slug returns 404.  
- AC‑3.5: Unauthenticated request returns 401.

---

### FR‑4 – Health and readiness checks

**Endpoint**: `GET /healthz` (liveness) and `GET /readyz` (readiness)  
**Auth**: None (public)

**Behaviour**:
- `/healthz`: always returns 200 `{"status":"ok"}` while the process is alive.
- `/readyz`: returns 200 when the database is reachable; otherwise 503. Used for Kubernetes probes.

**Acceptance criteria – FR‑4**  
- AC‑4.1: GET `/healthz` returns 200 and `{"status":"ok"}`.  
- AC‑4.2: GET `/readyz` returns 200 when the database is available.  
- AC‑4.3: If the database is unreachable (e.g., missing file for SQLite), `/readyz` returns 503.

---

## Non‑Functional Requirements

### NFR‑1 – Tenant Isolation
- All business endpoints (`/shorten`, `/r/{slug}`, `/stats/{slug}`) must derive `tenant_id` from the authenticated JWT.
- Database queries include a `WHERE tenant_id = :tenant_id` filter on every select, insert, update.
- Cross‑tenant access attempts must never reveal information; they must return 404 (or 403 where appropriate) – as specified in FR‑2 and FR‑3.
- The JWT verification library must expect a standard `sub` and custom `tenant_id` claim.

### NFR‑2 – Performance
- Under a local test load of 20 concurrent users (via `httpx.AsyncClient`), the p95 response time for:
  - `GET /r/{slug}` ≤ 30 ms (excluding network latency from test client to server).
  - `POST /shorten` ≤ 50 ms.
  - `GET /stats/{slug}` ≤ 50 ms.
- Database writes (shorten, redirect) use atomic operations; clicks are incremented with a single `UPDATE … SET click_count = click_count + 1 WHERE slug = … AND tenant_id = …` to avoid race conditions without extra locking.
- The service must be stateless (no in‑memory caches) so it can be horizontally scaled.

### NFR‑3 – Security
- Input validation on all endpoints using Pydantic v2 `BaseModel` with `Field(min_length=1)` and custom URL validation (absolute HTTP/HTTPS).
- Reject requests where the URL contains internal schemes (`file://`, `ftp://`, `javascript:`, etc.).
- Never return stack traces or internal error details in 500 responses – use a structured JSON error with a `request_id`.
- Use `log.error(…, extra={"request_id": request_id})` for server errors.
- Authentication must be enforced via a FastAPI dependency that verifies JWT signature and expiration.  
  *For the sandbox, a hard‑coded mock JWKS endpoint or a pre‑shared secret is acceptable, as long as the dependency pattern is the same as production.*

### NFR‑4 – Observability
- Structured JSON logs for each request, including `request_id`, `tenant_id`, `method`, `path`, and status code.
- Log a warning on slug collision retry (rare).
- `/healthz` and `/readyz` endpoints for liveness/readiness probes.

### NFR‑5 – Deployment and Sandbox Readiness
- The application runs in a single Docker container built from a provided `Dockerfile`.
- SQLite database file is stored inside the container at `/data/urlshort.db` (volume mount compatible).
- Tables are created automatically on startup (`Base.metadata.create_all`).
- The container exposes port `8000`.
- The pytest suite is runnable with `pytest -q` and all tests pass before container finalisation.

---

## Test Focus Areas (QA and Automated)

### 1. Functional Correctness
- **Shortening**  
  - Valid URL → 201 with correct slug, original URL, creation time.  
  - Duplicate requests produce distinct slugs.  
  - Invalid URLs (malformed, disallowed schemes) → 422.  
  - Missing body / required field → 422.  
  - URL length > 2048 → 422.  

- **Redirect**  
  - Correct slug → 302 redirect to original URL.  
  - Click count increments atomically (including concurrency test).  
  - Non‑existent slug → 404.  
  - Slug of another tenant → 404.  
  - Unauthenticated request → 401.  

- **Stats**  
  - Returns all fields with correct values.  
  - Click count matches previous redirects.  
  - 404 for missing or cross‑tenant slug.  

### 2. Tenant Isolation
- Every endpoint test must be run with at least two separate tenants.  
- Ensure that a shortened URL created for Tenant‑A is invisible to Tenant‑B on all three endpoints.  
- Verify that direct manipulation of the slug in the URL (e.g., guessing) never reveals cross‑tenant data.  

### 3. Security & Input Validation
- Fuzz the `/shorten` endpoint with malicious payloads (XSS attempts, SQL injection strings, extremely long values).  
- Verify that the response never reflects injected content unsafely.  
- Confirm that internal server errors (500) do not contain stack traces.  

### 4. Error Handling & Edge Cases
- 405 when using wrong HTTP method on endpoints.  
- 404 for non‑existent routes.  
- 503 for `readyz` when database is inaccessible (e.g., after deleting the DB file while the server is running – test via temporary file removal in integration test).  

### 5. Performance & Concurrency
- Load test (using `pytest‑benchmark` or a simple script inside the test harness) to verify p95 latencies are within bounds.  
- Concurrency test on the click counter to guarantee no lost updates – use multiple async tasks hitting the same slug simultaneously and assert final count equals number of requests.  

### 6. Non‑Regression & Test Suite Quality
- Run full suite with `pytest -q` – zero failures.  
- Achieve ≥ 80% line coverage over the application code.  
- Each acceptance criterion from FR‑1 through FR‑4 must be traceable to at least one test (via marker or docstring).  

---

## Assumptions and Constraints

- **Authentication**: A JWT is provided with each request. The test harness may supply a mock token generator for the sandbox; the service must validate the signature against a locally available public key (hardcoded or loaded from an env‑described path).
- **Slug length**: Fixed to 6–10 characters, generated randomly. Custom slugs are out of scope for this version.
- **Database**: SQLite via `aiosqlite` and `aiosqlalchemy`. The schema is created on startup; no Alembic migrations in the initial sandbox.
- **Tenant claim**: The JWT payload contains `"tenant_id": "uuid_string"`. The app must extract it and fail the request if missing or invalid.
- **No expiration or deletion**: Short URLs never expire. No delete endpoint.

## Open Questions & Risks

- **Slug collision handling**: While extremely unlikely with alphanumeric 6‑char slugs and per‑tenant uniqueness, the retry limit of 3 could in principle fail. For a production system, we would switch to a longer slug or use a pre‑generated pool.  
  *Decision: keep the retry limit; log and 500 if exceeded.*
- **Redirect cache**: Not planned. The redirect endpoint is fast enough for the initial release.
- **Name reserve / custom slugs**: Would add complexity and conflict potential; deferred.
- **Cross‑tenant visibility for `/healthz`**: No tenant context is required for health endpoints – they are global. This is acceptable as they reveal only operational status, not data.

---

*All requirements above are ready for handoff to the Solution Architect and subsequent implementation agents. Each acceptance criterion is designed to be directly mapped to an automated test, and non‑functional thresholds are measurable inside the sandbox.*