---
description: Database rules — auto-loads when editing migrations, schemas, SQL files
globs: ["**/migrations/**", "**/*.sql", "**/schema*", "**/prisma/**", "**/drizzle/**", "**/supabase/**"]
---

# Database Rules

## Skill Chain

1. **KB search** (if KB configured) — search for relevant schema/database articles before starting
2. **Supabase MCP** (if using Supabase): `list_tables` → `execute_sql` → `apply_migration` → `get_advisors`
3. **`/supabase-postgres-best-practices`** — for schema design and query optimization
4. **`/mongodb`** or **`/mongodb-development`** — if using MongoDB

## Conventions

- **Storage split**: identity/billing/api-keys live in **Postgres (Supabase)**; RAG content (`documents`, `chunks`, `conversations`, `bots`) lives in **MongoDB Atlas**. See `[[decision-postgres-mongo-storage-split]]`.
- Every migration is reversible (include up AND down)
- Never modify existing migrations — always create a new one
- Add indexes for frequently queried columns
- Use foreign key constraints for referential integrity
- RLS policies on all user-facing tables (Supabase)
- No SQL string concatenation — parameterized queries or ORM only
- App connects with a limited-permission DB user — never root
- Tenant-scoped queries (Mongo and Postgres) source `tenant_id` from a `Principal` only — see `[[concept-principal-tenant-isolation]]`

## Checklist

After any schema change:

- [ ] Supabase advisors (`get_advisors`) or equivalent linter clean
- [ ] RLS policies verified to still work
- [ ] TypeScript types regenerated (`generate_typescript_types` or equivalent)
- [ ] architect-agent knowledge base updated
- [ ] KB wiki articles updated for schema changes (if KB configured)
- [ ] Backup + restore procedure still valid for new schema

## Supabase Project (this repo)

- Supabase work runs against org `kdvcxztadqnitzzznqzg`, project `vmuybfmxermgwhmhevou`.
- Prefer the Supabase CLI (`supabase`) over ad-hoc SQL whenever it is available on PATH.
- Credentials (publishable key, secret key, DB password, env values) live in `.claude/secrets/supabase.md` — gitignored, local-only. Read that file before any Supabase task; never paste its contents into tracked files.

## References

Load only when the rule triggers:

- `.claude/secrets/supabase.md` — load for Supabase credentials, project refs, and CLI invocation patterns (gitignored, local-only)
- `.claude/references/security-checklist.md` — load for DB infrastructure/security checks (encryption at rest, network isolation, backups)
- `<kb-path>/wiki/_index.md` — search for existing schema/domain articles before DDL changes
- `<kb-path>/wiki/decision-postgres-mongo-storage-split.md` — load before adding a table or collection so it lands in the correct store
