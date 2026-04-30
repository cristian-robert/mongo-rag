# Dashboard Supabase Auth Regressions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore four broken dashboard pages (`/bots`, `/documents`, `/webhooks`, `/api-keys`) by fixing three independent regressions introduced/exposed by the Supabase Auth migration (#65, #66).

**Architecture:** Three orthogonal fixes on one branch:
1. Backend: stop using `bool()` on `pymongo.AsyncDatabase` in `core/dependencies.py`.
2. Frontend: stop passing function `render` props from Server Components to the Client `<Button>`; use `asChild` instead.
3. Backend: make `core/authz.get_principal` Supabase-aware by delegating JWT verification to the same `verify_supabase_jwt` path used by `core/tenant.py`, then resolving role/tenant from the Mongo `users` doc keyed by `supabase_user_id`. Keep the legacy NextAuth path as a fallback.

**Tech Stack:** FastAPI / Pydantic / pymongo (async) / python-jose / Next.js App Router / Base UI / Supabase Auth.

**Mandatory Reading (load before implementing):**
- `apps/api/src/core/tenant.py` — reference pattern for Supabase-aware auth
- `apps/api/src/core/supabase_auth.py` — `_looks_like_supabase_token`, `verify_supabase_jwt`, `SupabaseClaims`
- `apps/api/src/core/principal.py` — note: separate `Principal` class; do NOT collapse in this PR
- `apps/api/src/core/authz.py` — the file we're modifying
- `apps/api/src/core/dependencies.py` — the file we're modifying
- `apps/api/tests/conftest.py` — `mock_deps` fixture, JWT helpers
- `apps/api/tests/test_authz.py`, `tests/test_supabase_auth.py` — patterns to follow
- `apps/web/components/ui/button.tsx` — confirms `asChild` slot API
- `.obsidian/wiki/concept-principal-tenant-isolation.md` — tenant_id sourcing rules
- GitHub issue #73

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `apps/api/src/core/dependencies.py` | Modify | Replace truthy sentinel checks with `is None` |
| `apps/api/tests/test_dependencies_bool.py` | Create | Regression test for `_get_collection` after `initialize()` |
| `apps/web/app/(dashboard)/dashboard/bots/page.tsx` | Modify | Server Component → use `asChild` for Button+Link |
| `apps/web/app/(dashboard)/dashboard/documents/[id]/not-found.tsx` | Modify | Server Component → use `asChild` for Button+Link |
| `apps/api/src/core/authz.py` | Modify | Add Supabase-aware branch in `get_principal`; new `_principal_from_supabase_claims` helper |
| `apps/api/tests/test_authz.py` | Modify | Add Supabase-token tests (success, missing user, missing tenant, expired) |

No new modules. No package additions.

---

## Task 1: Backend — Fix `AsyncDatabase` truthy check (Bug #2 / #4)

**Files:**
- Modify: `apps/api/src/core/dependencies.py:42, 47, 71, 88, 171`
- Create: `apps/api/tests/test_dependencies_bool.py`

- [ ] **Step 1.1 — Write the failing regression test**

Create `apps/api/tests/test_dependencies_bool.py`:

```python
"""Regression test: AgentDependencies must not invoke bool() on pymongo objects.

pymongo.AsyncDatabase and AsyncMongoClient deliberately raise NotImplementedError
from __bool__ (you must compare with `is None`). The accessors in
`AgentDependencies` historically used `if not self.db:` which broke every
endpoint that hit the Supabase JWT path after migration. This test pins the
fix to the public accessor surface so the regression cannot return.
"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
def test_get_collection_does_not_bool_check_db():
    """`_get_collection` must use `is None`, not truthy check, on `self.db`."""
    from src.core.dependencies import AgentDependencies

    deps = AgentDependencies()

    # Stub a `db` whose __bool__ raises — mirrors pymongo.AsyncDatabase.
    db_stub = MagicMock()
    db_stub.__bool__ = MagicMock(side_effect=NotImplementedError("compare with None"))
    db_stub.__getitem__ = MagicMock(return_value="<collection>")
    deps.db = db_stub

    settings_stub = MagicMock()
    settings_stub.mongodb_collection_users = "users"
    deps.settings = settings_stub

    # Must not raise NotImplementedError.
    assert deps.users_collection == "<collection>"


@pytest.mark.unit
def test_get_collection_raises_when_db_none():
    """Sanity check: when `db` is None we still raise the configured error."""
    from src.core.dependencies import AgentDependencies

    deps = AgentDependencies()
    deps.db = None
    settings_stub = MagicMock()
    settings_stub.mongodb_collection_users = "users"
    deps.settings = settings_stub

    with pytest.raises(RuntimeError, match="Dependencies not initialized"):
        _ = deps.users_collection
```

- [ ] **Step 1.2 — Run the test, watch it fail**

Run: `cd apps/api && uv run pytest tests/test_dependencies_bool.py -v`
Expected: FAIL on `test_get_collection_does_not_bool_check_db` with `NotImplementedError: compare with None`.

- [ ] **Step 1.3 — Apply the fix**

Edit `apps/api/src/core/dependencies.py`. Replace **every** `if not self.X:` sentinel check with `if self.X is None:`. Exact replacements:

- Line 42: `if not self.settings:` → `if self.settings is None:`
- Line 47: `if not self.mongo_client:` → `if self.mongo_client is None:`
- Line 71: `if not self.openai_client:` → `if self.openai_client is None:`
- Line 88: `if not self.db:` → `if self.db is None:`
- Line 171: `if not self.openai_client:` → `if self.openai_client is None:`

Also update line 152 inside `cleanup`:
- `if self.mongo_client:` → `if self.mongo_client is not None:`

Rationale: pymongo's async types (`AsyncDatabase`, `AsyncMongoClient`) raise `NotImplementedError` from `__bool__`. Standardizing every sentinel check on `is None` / `is not None` removes both the live bug and the latent ones.

- [ ] **Step 1.4 — Run the regression test, watch it pass**

Run: `cd apps/api && uv run pytest tests/test_dependencies_bool.py -v`
Expected: 2 passed.

- [ ] **Step 1.5 — Run the full unit suite to confirm no other regression**

Run: `cd apps/api && uv run pytest -m unit -x -q`
Expected: all green.

- [ ] **Step 1.6 — Lint and format**

Run: `cd apps/api && uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 1.7 — Commit**

```bash
git add apps/api/src/core/dependencies.py apps/api/tests/test_dependencies_bool.py
git commit -m "fix(api): use 'is None' on AgentDependencies sentinels (#73)

pymongo.AsyncDatabase and AsyncMongoClient raise NotImplementedError from
__bool__. The truthy checks in AgentDependencies broke every endpoint that
reached the Supabase JWT path (documents, webhooks, etc.) with a 500.
Standardize all sentinel checks on 'is None' and pin the regression."
```

---

## Task 2: Frontend — Replace Server-Component `render={fn}` with `asChild` (Bug #1)

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/bots/page.tsx:48-55`
- Modify: `apps/web/app/(dashboard)/dashboard/documents/[id]/not-found.tsx:17-19`

> Audit confirmed only these two files pass `render={fn}` from a Server Component to `<Button>`. All other call sites are inside `"use client"` files (`bots-table.tsx`, `bot-form.tsx`, dialogs, `components/documents/*`) and are unaffected.

- [ ] **Step 2.1 — Apply the fix in `bots/page.tsx`**

Edit `apps/web/app/(dashboard)/dashboard/bots/page.tsx`. Replace lines 48–55:

```tsx
        <Button
          render={(props) => (
            <Link {...props} href="/dashboard/bots/new" />
          )}
        >
          <Plus />
          New bot
        </Button>
```

with:

```tsx
        <Button asChild>
          <Link href="/dashboard/bots/new">
            <Plus />
            New bot
          </Link>
        </Button>
```

- [ ] **Step 2.2 — Apply the fix in `documents/[id]/not-found.tsx`**

Edit `apps/web/app/(dashboard)/dashboard/documents/[id]/not-found.tsx`. Replace lines 17–19:

```tsx
      <Button render={(props) => <Link {...props} href="/dashboard/documents" />}>
        Back to documents
      </Button>
```

with:

```tsx
      <Button asChild>
        <Link href="/dashboard/documents">Back to documents</Link>
      </Button>
```

- [ ] **Step 2.3 — Type-check and lint the web app**

Run: `cd apps/web && pnpm lint`
Expected: clean. (If a `tsc` script exists also run `pnpm tsc --noEmit`; otherwise lint covers it.)

- [ ] **Step 2.4 — Confirm no other Server-Component `<Button render=>` uses regressed in**

Run from repo root: `grep -RIn "<Button render=" apps/web/app apps/web/components`
Expected output: zero matches in files **without** a `"use client"` directive on line 1. (Easy visual scan — there should be no matches at all in `app/**/page.tsx`, `app/**/layout.tsx`, `app/**/not-found.tsx`, `app/**/error.tsx`.)

- [ ] **Step 2.5 — Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/bots/page.tsx apps/web/app/\(dashboard\)/dashboard/documents/\[id\]/not-found.tsx
git commit -m "fix(web): use Button asChild slot in server components (#73)

Server Components cannot pass functions to Client Components, so
'<Button render={(props) => ...}>' broke /dashboard/bots and the document
not-found page with 'Functions cannot be passed directly to Client
Components'. Switch the two affected server pages to the existing asChild
slot API; client components keep using render."
```

---

## Task 3: Backend — Make `authz.get_principal` Supabase-aware (Bug #3)

**Files:**
- Modify: `apps/api/src/core/authz.py`
- Modify: `apps/api/tests/test_authz.py`

> Approach is **Option A** from issue #73: delegate JWT verification to `verify_supabase_jwt` (already used by `tenant.py`), then resolve the user's role and tenant from the Mongo `users` doc keyed by `supabase_user_id`. NextAuth HS256 path stays as a fallback so existing tests and any not-yet-migrated callers continue to work. Collapsing the two `Principal` classes is **out of scope** for this PR.

- [ ] **Step 3.1 — Write the failing tests for the Supabase path**

Append to `apps/api/tests/test_authz.py`:

```python
# -- Supabase JWT path (issue #73) --

from unittest.mock import patch
from time import time as _time

SUPABASE_ISSUER = "https://supa-test.supabase.co/auth/v1"
SUPABASE_AUDIENCE = "authenticated"
SUPABASE_HS256_SECRET = "supabase-shared-secret-32-chars-aa"


def _supabase_token(
    *,
    sub: str = "supabase-user-1",
    email: str = "u@example.com",
    extra_claims: dict | None = None,
) -> str:
    payload = {
        "sub": sub,
        "email": email,
        "iss": SUPABASE_ISSUER,
        "aud": SUPABASE_AUDIENCE,
        "exp": int(_time()) + 600,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, SUPABASE_HS256_SECRET, algorithm="HS256")


@pytest.fixture
def supabase_app(monkeypatch):
    """An app whose Settings advertise Supabase HS256 as enabled."""
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_ISSUER.replace("/auth/v1", ""))
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "supa-test")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SUPABASE_HS256_SECRET)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", SUPABASE_AUDIENCE)

    # Force settings re-load so the new env vars take effect.
    from src.core import settings as settings_module
    settings_module.load_settings.cache_clear()  # type: ignore[attr-defined]

    from src.core.authz import Principal, require_role
    from src.core.deps import get_deps
    from src.models.user import UserRole

    app = FastAPI()

    @app.get("/admin-plus")
    async def admin(p: Principal = Depends(require_role(UserRole.ADMIN))):
        return {"ok": True, "tenant_id": p.tenant_id, "role": p.role, "user_id": p.user_id}

    deps = MagicMock()
    deps.users_collection.find_one = AsyncMock(
        return_value={
            "_id": "mongo-uid-1",
            "supabase_user_id": "supabase-user-1",
            "tenant_id": "tenant-supa-1",
            "role": "admin",
            "email": "u@example.com",
        }
    )
    app.dependency_overrides[get_deps] = lambda: deps
    return TestClient(app), deps


@pytest.mark.unit
def test_supabase_token_resolves_principal_with_role(supabase_app):
    client, _ = supabase_app
    r = client.get("/admin-plus", headers={"Authorization": f"Bearer {_supabase_token()}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == "tenant-supa-1"
    assert body["role"] == "admin"
    assert body["user_id"] == "mongo-uid-1"


@pytest.mark.unit
def test_supabase_token_user_not_found_is_401(supabase_app):
    client, deps = supabase_app
    deps.users_collection.find_one = AsyncMock(return_value=None)
    r = client.get("/admin-plus", headers={"Authorization": f"Bearer {_supabase_token()}"})
    assert r.status_code == 401


@pytest.mark.unit
def test_supabase_token_with_role_below_required_is_403(supabase_app):
    client, deps = supabase_app
    deps.users_collection.find_one = AsyncMock(
        return_value={
            "_id": "mongo-uid-1",
            "supabase_user_id": "supabase-user-1",
            "tenant_id": "tenant-supa-1",
            "role": "viewer",
            "email": "u@example.com",
        }
    )
    r = client.get("/admin-plus", headers={"Authorization": f"Bearer {_supabase_token()}"})
    assert r.status_code == 403


@pytest.mark.unit
def test_legacy_nextauth_token_still_works(supabase_app):
    """Belt-and-braces: the NextAuth HS256 fallback must still resolve."""
    client, _ = supabase_app
    r = client.get("/admin-plus", headers=_hdr("admin"))
    assert r.status_code == 200
```

> If `load_settings` is not LRU-cached, the `cache_clear()` line will need adjusting — read `src/core/settings.py:load_settings` first and either drop the line (if it builds Settings fresh each call) or call the appropriate reset hook.

- [ ] **Step 3.2 — Run the failing tests**

Run: `cd apps/api && uv run pytest tests/test_authz.py -v -k supabase`
Expected: 3 of 4 fail with 401 "Invalid or expired token" (Supabase tokens go through `decode_jwt(token, nextauth_secret)` and fail). The legacy test should still pass.

- [ ] **Step 3.3 — Implement the Supabase branch in `authz.py`**

Edit `apps/api/src/core/authz.py`. Replace the file body with:

```python
"""Role-based authorization helpers for dashboard JWT principals.

API-key requests do NOT carry a role and are rejected here. Use
``get_tenant_id`` (in ``core.tenant``) for endpoints that must accept API
keys; use these helpers for dashboard-only management endpoints.

Supports both Supabase-issued JWTs (post-migration) and legacy NextAuth
HS256 tokens. Routing between paths is done by a cheap ``iss`` peek; there
is **no fall-through** between paths — a Supabase token with a bad
signature must NOT fall back to the NextAuth verifier (algorithm-confusion
guard, mirroring ``core/tenant.py``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from src.core.dependencies import AgentDependencies
from src.core.deps import get_deps
from src.core.observability import set_request_context
from src.core.security import decode_jwt
from src.core.settings import load_settings
from src.core.supabase_auth import (
    SupabaseClaims,
    _looks_like_supabase_token,
    verify_supabase_jwt,
)
from src.models.user import UserRole, has_min_role

logger = logging.getLogger(__name__)

_API_KEY_PREFIX = "mrag_"


@dataclass(frozen=True)
class Principal:
    """An authenticated dashboard user."""

    user_id: str
    tenant_id: str
    role: str


async def get_principal(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    deps: AgentDependencies = Depends(get_deps),
) -> Principal:
    """Decode a dashboard JWT (Supabase or legacy NextAuth) and return the principal.

    Raises:
        HTTPException 401: missing / invalid token, or token lacks required claims.
        HTTPException 403: caller used an API key — keys cannot manage team.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token is required",
        )

    token = authorization[7:]
    if token.startswith(_API_KEY_PREFIX):
        raise HTTPException(
            status_code=403,
            detail="API keys cannot access this endpoint",
        )

    settings = load_settings()

    if _looks_like_supabase_token(token, settings):
        try:
            claims = await verify_supabase_jwt(token, settings)
        except ValueError as exc:
            logger.debug("Supabase JWT rejected by authz.get_principal: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid or expired token") from None
        principal = await _principal_from_supabase_claims(claims, deps)
    else:
        principal = _principal_from_nextauth(token, settings)

    request.state.tenant_id = principal.tenant_id
    set_request_context(tenant_id=principal.tenant_id)
    return principal


def _principal_from_nextauth(token: str, settings) -> Principal:
    """Verify a legacy NextAuth-issued HS256 token and build a Principal.

    Kept for rollback safety until every dashboard caller has migrated to
    Supabase Auth.
    """
    payload = decode_jwt(token, settings.nextauth_secret)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    user_id = payload.get("sub")
    role = payload.get("role")
    if not tenant_id or not user_id or not role:
        raise HTTPException(
            status_code=401,
            detail="Token missing required claims",
        )
    if role not in {r.value for r in UserRole}:
        raise HTTPException(status_code=401, detail="Token has unknown role claim")

    return Principal(user_id=user_id, tenant_id=tenant_id, role=role)


async def _principal_from_supabase_claims(
    claims: SupabaseClaims, deps: AgentDependencies
) -> Principal:
    """Resolve a Principal from verified Supabase claims.

    Tenant precedence:
        1. ``tenant_id`` claim (server-controlled ``app_metadata`` is preferred).
        2. ``users`` doc keyed by ``supabase_user_id`` (the JWT ``sub``).
        3. ``users`` doc keyed by email.

    Role precedence:
        1. ``users`` doc ``role`` field, if recognized.
        2. ``UserRole.MEMBER`` as a safe default (RBAC fail-closed for
           privileged routes — admin/owner endpoints will return 403).

    Fail-closed: if no ``tenant_id`` can be determined, raise 401. Mirrors the
    pattern in ``core/tenant.py::_tenant_id_from_supabase_claims`` so the two
    auth chokepoints behave consistently.
    """
    users = deps.users_collection
    user_doc = await users.find_one({"supabase_user_id": claims.sub})
    if user_doc is None and claims.email:
        user_doc = await users.find_one({"email": claims.email.lower()})

    tenant_id = claims.tenant_id or (user_doc.get("tenant_id") if user_doc else None)
    if not tenant_id:
        logger.info(
            "supabase_user_without_tenant",
            extra={"sub": claims.sub, "has_email": claims.email is not None},
        )
        raise HTTPException(status_code=401, detail="User has no tenant assigned")

    raw_role = (user_doc or {}).get("role")
    valid_roles = {r.value for r in UserRole}
    role = raw_role if raw_role in valid_roles else UserRole.MEMBER.value

    user_id = (
        str(user_doc["_id"])
        if user_doc is not None and user_doc.get("_id") is not None
        else claims.sub
    )

    return Principal(user_id=user_id, tenant_id=tenant_id, role=role)


def require_role(minimum: UserRole):
    """Build a FastAPI dependency that enforces a minimum role.

    Example::

        @router.post(...)
        async def endpoint(principal: Principal = Depends(require_role(UserRole.ADMIN))):
            ...
    """

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not has_min_role(principal.role, minimum):
            logger.info(
                "rbac_denied",
                extra={
                    "tenant_id": principal.tenant_id,
                    "user_id": principal.user_id,
                    "role": principal.role,
                    "required": minimum.value,
                },
            )
            raise HTTPException(
                status_code=403,
                detail=f"Requires '{minimum.value}' role or higher",
            )
        return principal

    return _dep
```

- [ ] **Step 3.4 — Run the new Supabase tests; expect green**

Run: `cd apps/api && uv run pytest tests/test_authz.py -v`
Expected: all tests pass — both the original NextAuth tests and the four new Supabase tests.

- [ ] **Step 3.5 — Run the broader suite to catch fallout**

Run: `cd apps/api && uv run pytest -m unit -x -q`
Expected: all green. Pay particular attention to `tests/test_billing_router.py`, `tests/test_bot_router.py`, `tests/test_team_service.py`, `tests/test_api_key_router.py`, `tests/test_auth_router.py` — these exercise the routers that depend on `authz`.

If any of those tests now fail, read the failure: it is almost certainly because the test client lacks `app.dependency_overrides[get_deps]`. Fix the test by overriding `get_deps`, not by softening `authz.py`.

- [ ] **Step 3.6 — Lint and format**

Run: `cd apps/api && uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 3.7 — Commit**

```bash
git add apps/api/src/core/authz.py apps/api/tests/test_authz.py
git commit -m "fix(api): make authz.get_principal Supabase-aware (#73)

After the Supabase Auth migration the dashboard sends Supabase JWTs, but
core/authz.get_principal still only ran NextAuth HS256 verification, so
every router using require_role (keys, billing, bots, team, auth) returned
401. Delegate JWT verification to verify_supabase_jwt for Supabase issuers
and resolve role+tenant from the Mongo users doc keyed by supabase_user_id;
keep the NextAuth path as a fallback for rollback safety. No fall-through
between paths (alg-confusion guard mirrors core/tenant.py)."
```

---

## Task 4: End-to-end verification

**Files:** none modified — verification only.

- [ ] **Step 4.1 — Start the backend dev server**

Run: `cd apps/api && uv run uvicorn src.main:app --reload --port 8100 &` (or in a separate terminal).

- [ ] **Step 4.2 — Start the web dev server**

Run: `cd apps/web && pnpm dev`.

- [ ] **Step 4.3 — Spawn the tester-agent for FLOW verification**

Use the Agent tool with `subagent_type: "general-purpose"`, `model: "sonnet"`. Prompt:

```
You are the tester-agent for the MongoRAG project. Read
.claude/agents/tester-agent/AGENT.md for your instructions. Then run this test:

FLOW: Dashboard pages load post-Supabase-auth-fix
Steps:
1. Sign in via the existing test account (test-patterns.md auth-state.md)
2. Visit http://localhost:3100/dashboard/bots — page must render with no
   "Functions cannot be passed directly to Client Components" error in the
   browser console; the bots list (or empty state) must be visible
3. Visit /dashboard/documents — page renders, GET /api/v1/documents returns 200
4. Visit /dashboard/webhooks — page renders, GET /api/v1/webhooks returns 200
5. Visit /dashboard/api-keys — page renders, GET /api/v1/keys returns 200
6. Visit /dashboard/team — page renders without 401
7. Visit /dashboard/billing — page renders without 401
8. Visit /dashboard/bots/new — button-as-Link still navigates correctly
9. Visit a non-existent document URL like /dashboard/documents/does-not-exist —
   the not-found page renders with the "Back to documents" button working
Report PASS/FAIL per step with the exact console error message on FAIL.
```

- [ ] **Step 4.4 — Address any FAIL by returning to the relevant Task**

If the tester-agent reports a FAIL: STOP. Do not patch ad-hoc. Map the failure back to Task 1, 2, or 3 and return to its first step. Three failed iterations = re-open systematic-debugging Phase 1.

- [ ] **Step 4.5 — Final code-review pass**

Spawn the `feature-dev:code-reviewer` agent on the diff for issue #73. Address any high-confidence findings.

- [ ] **Step 4.6 — Push and open PR via `/commit-push-pr`**

Use the project's `/commit-push-pr` skill — never raw `git push` / `gh pr create`. Title: `fix(dashboard): three regressions after Supabase migration (#73)`. Link `Closes #73` in the body.

---

## Self-Review

**Spec coverage**

| Issue #73 requirement | Task |
|-----------------------|------|
| Bug 1 — RSC render-prop on Server Components | Task 2 |
| Bug 2 / 4 — `AsyncDatabase` `bool()` | Task 1 |
| Bug 3 — `authz.get_principal` not Supabase-aware | Task 3 |
| Test plan: `_get_collection` callable post-init | Task 1.1, 1.4 |
| Test plan: Supabase JWT through `require_role` | Task 3.1, 3.4 |
| Test plan: NextAuth JWT still works | Task 3.1 (`test_legacy_nextauth_token_still_works`), 3.5 |
| Test plan: API key → 403 | covered by existing `test_api_key_rejected` (preserved) |
| Test plan: web E2E for all four dashboard pages | Task 4.3 |
| Test plan: ruff + pnpm lint clean | Task 1.6, 2.3, 3.6 |
| Out-of-scope: collapse Principal classes | not in plan ✓ |

**Placeholder scan:** none — every step has full code or an exact command.

**Type consistency:**
- `Principal` (in `authz.py`) keeps fields `user_id: str, tenant_id: str, role: str` — unchanged from current.
- `UserRole` enum values used: `"owner" | "admin" | "member" | "viewer"` — sourced from `src/models/user.py`.
- `SupabaseClaims` fields used: `sub: str, email: Optional[str], tenant_id: Optional[str]` — match `src/core/supabase_auth.py:39`.
- `_looks_like_supabase_token` and `verify_supabase_jwt` signatures match `src/core/supabase_auth.py:97, 115`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-dashboard-supabase-auth-regressions.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session via `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
