---
description: Testing rules — auto-loads when editing test files
globs: ["**/*.test.*", "**/*.spec.*", "**/test/**", "**/tests/**", "**/__tests__/**", "**/e2e/**"]
---

# Testing Rules

## Skill Chain

1. Check existing test files for the feature area — prefer adding to existing over creating new
2. For QA test planning, spawn a test-planning subagent (plans placement, does not write tests)
3. **Implement** — unit + integration + QA E2E per the matrix in the detail reference
4. Run tests locally before shipping

## Conventions

- Name tests by behavior, not implementation (`it('returns 404 when user not found')`)
- Arrange / Act / Assert structure with visual separation
- Cover happy path, edge cases, and error cases — skip framework internals
- Use real DBs for integration tests where possible; mock only external services
- Never mock the module under test; prefer DI over module mocking
- QA automation (API/Browser/Mobile E2E) is mandatory after every dev task, not just unit tests
- Test credentials come from env (`TEST_USER_EMAIL` etc.) — never hardcoded

## Checklist

- [ ] Tests describe behavior, not implementation
- [ ] Happy path, edge cases, and error cases covered for new code
- [ ] No new test file created when one already exists for the feature area
- [ ] QA E2E tests added/updated per the domain matrix
- [ ] No hardcoded credentials — reads from env or GitHub secrets
- [ ] All tests pass locally before shipping

## References

Load only when the rule triggers:

- `.claude/references/testing-detail.md` — load for AAA structure, mock policy detail, QA matrix, placement rules, test users
- `.claude/references/security-checklist.md` — load for security-sensitive test areas (auth, authz, input validation)
- `<kb-path>/wiki/_index.md` — search for feature articles to align tests with documented behavior
