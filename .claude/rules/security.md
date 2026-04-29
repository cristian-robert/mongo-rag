---
description: Security rules — auto-loads when editing auth, API security, middleware, or infrastructure files
globs: ["**/auth/**", "**/authentication/**", "**/login*", "**/register*", "**/session*", "**/token*", "**/jwt*", "**/middleware/**", "**/guard*", "**/cors*", "**/ssl*", "**/tls*", "**/encrypt*", "**/hash*", "**/password*", "**/security*"]
---

# Security Rules

## Skill Chain

1. **architect-agent RETRIEVE** — understand current auth/security architecture before changes
2. **context7 MCP** — verify framework security APIs (passport, bcrypt, helmet, etc.)
3. **Implement** — follow the full checklist in `.claude/references/security-checklist.md`
4. **architect-agent RECORD** — update knowledge base after security-related changes
5. Run `/validate` (Phase 2.5) and `/ship` (Step 1.7) — both enforce the checklist

## Conventions

- Passwords hashed with bcrypt (≥12 rounds) or argon2 — never plaintext
- Tokens in httpOnly cookies — never localStorage
- Every route verifies authentication; every object access verifies authorization
- Inputs validated with schema validation (Zod, Joi, etc.); no SQL string concatenation
- Secrets in env vars only — never committed, never in source
- Error messages never reveal stack traces, file paths, or system internals
- CORS restricted to specific origins — no wildcard `*` in production

## Checklist

- [ ] Full `.claude/references/security-checklist.md` run before `/ship`
- [ ] `npm audit` shows no critical vulnerabilities
- [ ] No hardcoded credentials or secrets anywhere in the diff
- [ ] `.env` absent from git history (`git log -- .env` empty)
- [ ] Auth + authz verified on every new or modified route
- [ ] Rate limiting in place on public-facing endpoints

## References

Load only when the rule triggers:

- `.claude/references/security-checklist.md` — load for the authoritative pre-ship checklist (auth, API, code, infra)
- `.claude/references/backend-detail.md` — load for auth/authz implementation detail and logging rules
- `<kb-path>/wiki/_index.md` — search for existing auth/session/security decision articles before changing behavior
