---
title: "Feature: Team management & RBAC"
type: feature
tags: [feature, team, rbac, roles, invitations]
sources:
  - "apps/api/src/services/team.py"
  - "apps/api/src/routers/team.py"
  - "supabase/migrations/20260429190107_init_tenancy.sql (profiles role enum)"
  - "PR #64"
related:
  - "[[concept-principal-tenant-isolation]]"
  - "[[decision-postgres-mongo-storage-split]]"
created: 2026-04-30
updated: 2026-04-30
status: compiled
---

## Overview

Each tenant has multiple users with one of four roles: `owner / admin / member / viewer`. Owners are protected against accidental removal (last-owner check). Invitations are SHA-256-hashed single-use tokens with email-match required at acceptance.

## GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| (PR #64) | feat(team): team management and role-based access control | merged |

## Content

### Role enum

`UserRole.OWNER, ADMIN, MEMBER, VIEWER` — defined in code; mirrored in Postgres `profiles.role` enum (`supabase/migrations/20260429190107_init_tenancy.sql`).

Permission semantics (enforced in routers via decorator + service-level checks):

| Role | Can |
|---|---|
| owner | full admin including billing + transfer ownership |
| admin | manage team, bots, api keys, webhooks; cannot touch billing |
| member | read all, create/edit documents, run chat |
| viewer | read-only |

### Service interface — `services/team.py`

- `list_members(tenant_id) → list[dict]`
- `update_member_role(tenant_id, target_user_id, new_role, actor_user_id, actor_role)`
- `remove_member(tenant_id, target_user_id, actor_user_id, actor_role)`
- `create_invitation(tenant_id, email, role, invited_by_user_id, actor_role) → (record, raw_token)`
- `accept_invitation_existing_user(...)`, `accept_invitation_new_user(...)`

### Last-owner protection

Every demotion / removal that targets an owner runs a **two-phase check** to defend against concurrent ops:

1. Pre-write: query owner count. Refuse if this op would drop it to zero.
2. Post-write: re-count owners. If the count is now zero (because another concurrent op succeeded between checks), the operation is rolled back.

### Owner-promotion lockdown

Only owners can:

- Promote any role to `OWNER`
- Demote an existing `OWNER`

Admins can manage `MEMBER` and `VIEWER`; they cannot create or remove owners.

### Invitations (currently in Mongo `invitations`)

- Token: random URL-safe bytes, **SHA-256 hashed at rest** (raw token shown once when invitation is sent)
- Single-use (atomic mark-consumed at acceptance)
- TTL: configurable, default 168 hours (7 days)
- Email-match required: the acceptance request must come from the same email address the invite was issued to (CSRF defense — prevents an attacker who steals the URL from claiming it under a different identity)

### Storage note

Per the auth migration, `profiles` (with `role` enum) is in **Postgres**. Per the team service code, invitations and the `users`/`tenants` records the team service reads still live in **MongoDB**. This is part of the partial migration tracked in `[[decision-postgres-mongo-storage-split]]`. Future work consolidates team storage on Postgres.

## Key Takeaways

- Four roles: owner / admin / member / viewer.
- Last-owner protection is two-phase to defend against concurrent demote+demote races.
- Only owners can mint or unseat owners.
- Invitations: SHA-256 hashed tokens, single-use, default 7-day TTL, email-match required at acceptance.
- `profiles.role` is in Postgres; invitation/team mutations still hit Mongo (partial migration).

## See Also

- [[concept-principal-tenant-isolation]] — how role flows through `Principal.role`
- [[decision-postgres-mongo-storage-split]] — why the team domain is mid-migration
