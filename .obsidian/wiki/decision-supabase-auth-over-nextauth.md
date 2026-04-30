---
title: "Decision: Supabase Auth as primary, NextAuth retained as fallback"
type: decision
tags: [decision, auth, supabase, nextjs, fastapi, jwt]
sources:
  - "apps/api/src/core/supabase_auth.py"
  - "apps/api/src/core/security.py"
  - "apps/api/src/routers/auth.py"
  - "apps/web/lib/supabase/{client,server,middleware}.ts"
  - "apps/web/middleware.ts"
  - "PRs #65 (web), #66 (api JWT verify), #72 (stale NEXTAUTH_SECRET test removed)"
related:
  - "[[concept-principal-tenant-isolation]]"
  - "[[decision-postgres-mongo-storage-split]]"
  - "[[feature-api-key-management]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

The dashboard uses Supabase Auth (`@supabase/ssr`, email/password) and the FastAPI backend verifies the resulting JWT against the Supabase JWKS endpoint. **However, the legacy NextAuth HS256 path is still wired into the API** — both paths coexist with token-shape-based routing. NextAuth is *not* fully removed.

## Content

### Web layer (Supabase, no fallback)

`apps/web/`:
- `lib/supabase/client.ts` — `createBrowserClient()` (`@supabase/ssr`), reads `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `lib/supabase/server.ts` — `createServerClient<Database>()` with `cookies()` from `next/headers`, guarded by `"server-only"` import
- `lib/supabase/middleware.ts` — `updateSession()` calls `supabase.auth.getUser()` to refresh on every request
- `middleware.ts` — runs `updateSession`, then route protection (marketing public, auth pages redirect signed-in users to `/dashboard`, dashboard requires auth and redirects unauthenticated to `/login?next=…`); also injects `x-request-id`
- Login: `signInWithPassword()` client-side → `router.refresh()` to `/dashboard`

### API layer (dual JWT, with shape-based routing)

`apps/api/src/core/supabase_auth.py` + `apps/api/src/core/security.py` — both use **python-jose**:

- **Supabase JWKS path:** `verify_supabase_jwt()` fetches JWKS from `{supabase_url}/auth/v1/.well-known/jwks.json`, caches it for `supabase_jwks_cache_seconds` (default 3600s), uses an `asyncio.Lock` to prevent thundering-herd refreshes. Verifies RS256/RS384/RS512/ES256/ES384/ES512 against the `kid`-matched key. **Issuer (`iss`) and audience (`aud`) are pinned from settings, not read from the token header** — this guards algorithm-confusion attacks.
- **Legacy NextAuth path:** `decode_jwt(token, secret, algorithms=["HS256"])` against `nextauth_secret` setting.

**Routing between the two:** the verifier peeks (without verification) at the token's `iss` claim. If it matches `supabase_issuer`, only the Supabase path runs; otherwise only the NextAuth path runs. There is **no fall-through bypass** — a token can be verified by exactly one path.

JWT claims → Principal: `tenant_id`, `sub` → `user_id`, `role`, `email`.

### Auth router (credentials-based, NOT pure Supabase)

`apps/api/src/routers/auth.py` — endpoints exposed by the FastAPI backend itself:

- `POST /api/v1/auth/signup` — creates auth.users + tenant + profile + free subscription via `AuthService.signup`
- `POST /api/v1/auth/login` — email + password (NextAuth-compatible response shape)
- `POST /api/v1/auth/forgot-password` — email-enumeration-safe; sends reset token via Resend
- `POST /api/v1/auth/reset-password` — token + new password
- `GET /api/v1/auth/me` — returns current user; **role read from DB, not from JWT** (avoids stale-claim drift)
- `POST /api/v1/auth/ws-ticket` — exchanges JWT/API key for a single-use 30-second WebSocket ticket

All credential endpoints are rate-limited by `enforce_auth_ip_rate_limit`. Failures return generic 401/400 to prevent user enumeration.

### Two auth methods feed the same Principal

- **JWT (web dashboard):** Supabase JWKS (primary) or NextAuth HS256 (legacy) → `Principal(auth_method="jwt", ...)`
- **API key (widget / programmatic):** `mrag_*` prefix → bcrypt lookup in Postgres `api_keys` → `Principal(auth_method="api_key", ...)`

Business code uses the Principal directly and rarely branches on `auth_method`. See `[[concept-principal-tenant-isolation]]`.

### Why both paths still exist

NextAuth was the initial pick. The migration to Supabase Auth (#65, #66) added the new path and pointed the web frontend at it, but the legacy HS256 verifier was retained for compatibility. The repo still has a NextAuth-shaped `/login` response and a `nextauth_secret` setting; the cleanup PR (#72) only removed an obsolete env-required test. Future work should fully retire the HS256 path and the `nextauth_secret` setting.

## Key Takeaways

- Web: pure Supabase via `@supabase/ssr`. Cookies handle session; middleware refreshes on every request.
- API: dual JWT verifier (Supabase JWKS + legacy NextAuth HS256) with non-overlapping shape-based routing.
- The auth router exposes credential endpoints (`/signup`, `/login`, `/forgot-password`, `/reset-password`, `/me`, `/ws-ticket`) — Supabase doesn't handle these directly.
- Issuer / audience pinning + JWKS path matching are what makes the Supabase verifier safe.
- Don't reintroduce NextAuth as a primary path; treat the HS256 path as deprecated and earmark it for removal.

## See Also

- [[concept-principal-tenant-isolation]] — what JWT verification produces
- [[decision-postgres-mongo-storage-split]] — Postgres is also the identity store
- [[feature-api-key-management]] — the second auth method that feeds into the same Principal
