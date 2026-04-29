# MongoRAG Security Posture

This document is the operator-facing summary of the controls in place.
Implementation lives in `apps/api/src/core/{settings,middleware,security,
rate_limit_dep}.py` and `apps/web/{next.config.ts,middleware.ts}`.

## Tenant isolation

- Every MongoDB query filters by `tenant_id` (enforced at the query layer).
- `tenant_id` is **never** trusted from the request body; it is derived
  from a verified JWT (Auth.js) or hashed API key (`mrag_…`) lookup.
- A `TenantGuardMiddleware` logs (does not block) any successful
  `/api/v1/*` response that ran without a tenant context.

## Input validation

- All request bodies use Pydantic models with `extra="forbid"` (see
  `StrictRequest` in `apps/api/src/models/api.py`) so unknown fields are
  rejected — defending against mass-assignment.
- All free-text fields have explicit `min_length` / `max_length` caps.
- `Literal[...]` types are used for enum-like fields (`type`,
  `search_type`) so injected values are rejected at parse time.
- File uploads validate extension and size (per-tenant plan limit).

## CORS

- Origins are read from `CORS_ALLOWED_ORIGINS` (comma-separated).
- The middleware refuses to start in production if `*` appears in the
  list (see `_configure_middleware` in `apps/api/src/main.py`).
- `allow_credentials=True` is used; combined with explicit origins this
  closes the standard CORS-with-credentials bypass.

## Security headers

- API responses (Helmet equivalent): `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`,
  `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`,
  `Cache-Control: no-store`. `Strict-Transport-Security` only when
  `APP_ENV=production`.
- Dashboard CSP (in `apps/web/next.config.ts`):
  - `default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`,
    `base-uri 'self'`, `form-action 'self' https://checkout.stripe.com`.
  - `connect-src` includes the API origin and Stripe.
  - Production drops `'unsafe-eval'`/`'unsafe-inline'` from `script-src`
    and adds `upgrade-insecure-requests`.

## Body-size limits

- `BodySizeLimitMiddleware` (`MAX_REQUEST_BODY_BYTES`, default 1 MiB)
  rejects oversized JSON / form bodies with HTTP 413 before any handler
  runs.
- Multipart upload paths (`/api/v1/documents/...`) are exempt — they
  enforce the plan-aware `MAX_UPLOAD_SIZE_MB` limit inside the handler.

## Rate limiting (#11)

- `enforce_rate_limit` and `enforce_query_quota` dependencies apply
  per-principal limits at chat, ingest, and quota-sensitive endpoints
  using the tenant's plan (`PlanLimits.for_plan`).
- Limits are keyed by API key hash when the caller authenticates with an
  `mrag_…` key, otherwise by tenant id. The raw key is never logged.

## SSRF hardening on Stripe redirects

- `_validate_redirect_url` rejects URLs that:
  - use a scheme other than `http`/`https`;
  - embed user credentials (`user@host`);
  - resolve to a private, loopback, link-local, or reserved IP literal;
  - use plain `http` outside of `localhost`/`127.x`.

## Webhook signature verification

- Stripe webhooks are out of scope for this issue (see #43). The
  setting `STRIPE_WEBHOOK_SECRET` is wired into `Settings`; the webhook
  handler must call `stripe.Webhook.construct_event(...)` with this
  secret before trusting the payload.

## Secrets management

- All secrets live in `apps/api/.env` (gitignored) and `apps/web/.env.local`
  (gitignored). `.env*` is matched by the root `.gitignore`.
- `.env.example` files document the full set of variables — populated
  with placeholder values only. CI must fail any commit that introduces
  a real secret (a static check in `tests/test_security_hardening.py`
  guards against `sk_live_…` keys leaking into the apps tree).
- Local Claude Code knowledge with credentials lives under
  `.claude/secrets/` (also gitignored).

## Pre-ship checklist

- [ ] `git log -- apps/api/.env apps/web/.env.local apps/web/.env` is empty.
- [ ] `pip audit` / `npm audit` show no critical vulnerabilities.
- [ ] `CORS_ALLOWED_ORIGINS` enumerates production origins (no `*`).
- [ ] `APP_ENV=production` is set so HSTS and strict CSP turn on.
- [ ] Stripe keys in production env are `sk_live_…`; webhook secret is set.
- [ ] All new request models inherit from `StrictRequest`.
