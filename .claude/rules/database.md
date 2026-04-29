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

- Every migration is reversible (include up AND down)
- Never modify existing migrations — always create a new one
- Add indexes for frequently queried columns
- Use foreign key constraints for referential integrity
- RLS policies on all user-facing tables (Supabase)
- No SQL string concatenation — parameterized queries or ORM only
- App connects with a limited-permission DB user — never root

## Checklist

After any schema change:

- [ ] Supabase advisors (`get_advisors`) or equivalent linter clean
- [ ] RLS policies verified to still work
- [ ] TypeScript types regenerated (`generate_typescript_types` or equivalent)
- [ ] architect-agent knowledge base updated
- [ ] KB wiki articles updated for schema changes (if KB configured)
- [ ] Backup + restore procedure still valid for new schema

## References

Load only when the rule triggers:

- `.claude/references/security-checklist.md` — load for DB infrastructure/security checks (encryption at rest, network isolation, backups)
- `<kb-path>/wiki/_index.md` — search for existing schema/domain articles before DDL changes
