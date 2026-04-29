# Backend Detail

Detailed backend patterns, security bullets, and testing-by-layer notes. Loaded on demand by `.claude/rules/backend.md`.

## Error Response Format

All API error responses follow a consistent shape so clients can parse them uniformly:

```json
{ "error": "human-readable message", "statusCode": 4xx|5xx }
```

- Never include stack traces, file paths, or internal module names in the `error` field.
- Log the full error server-side with a correlation id; return the correlation id (not the trace) to the client if helpful.
- 4xx errors: include enough context for the client to correct the request.
- 5xx errors: opaque message, details in server logs.

## Dependency Injection & Layering

- Controllers/route handlers: HTTP concerns only (parse, validate, call service, shape response).
- Services: business logic, orchestration, and transactions.
- Repositories: data access only — no business rules.
- Inject dependencies via constructor or framework DI container; avoid module-level singletons that make tests hard to isolate.
- No service should import from a controller; controllers depend on services, services depend on repositories.

## Logging

- Structured logs (JSON) in non-dev environments.
- Every request logs: method, path, status, latency, user id (if authenticated), correlation id.
- Never log secrets, tokens, password hashes, or raw request bodies that may contain PII.
- Error logs include stack trace server-side; never forwarded to clients.

## Authentication & Authorization Detail

- Passwords hashed with bcrypt (≥12 rounds) or argon2 — never plaintext, never reversible encryption.
- Tokens in httpOnly, Secure, SameSite cookies — never localStorage.
- JWT secrets: random, ≥32 characters, loaded from env, rotated on compromise.
- Access tokens expire within 15–60 minutes; implement refresh token rotation with server-side revocation tracking.
- Rate limiting on `/login`, `/register`, password reset, and all public-facing endpoints.
- Account lockout after N failed attempts (configurable per project, default 5 in 15 minutes).
- Sessions invalidated server-side on logout — don't rely on client-side token deletion.

## API Surface Security

- Every route verifies authentication — audit all endpoints, not just obvious ones. Default deny, explicit allow.
- Authorization enforced on every object access: users can only read/write their own data unless explicitly allowed.
- API responses never expose: password hashes, internal ids from other users, raw JWT secrets, internal file paths.
- CORS restricted to specific allowed origins — never wildcard `*` in production.
- HTTPS enforced in production; HTTP redirected.

## Ops Hygiene

- No hardcoded credentials, API keys, or secrets anywhere in the codebase — env vars only.
- Run `npm audit` (or equivalent) before shipping; resolve all critical vulnerabilities.
- `.env` files gitignored and never committed; verify `git log -- .env` is empty.

## Testing by Layer

- **Service methods**: unit test with mocked dependencies (repository, external clients).
- **Controllers / route handlers**: integration tests with real service, mocked DB if needed. Verify status codes, response shapes, auth enforcement.
- **E2E**: full API endpoint tests against a real database for critical paths (auth flow, payment flow, core CRUD).
- **Contract tests**: if the API has external consumers, verify response shape stability.

See also:
- `.claude/references/security-checklist.md` — full security pre-ship checklist
- `.claude/references/code-patterns.md` — project-specific code patterns
