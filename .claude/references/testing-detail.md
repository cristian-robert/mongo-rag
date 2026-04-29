# Testing Detail

Detailed testing patterns, QA automation matrix, and test placement rules. Loaded on demand by `.claude/rules/testing.md`.

## Test Naming

- Describe behavior, not implementation: `it('returns 404 when user not found')` not `it('tests getUserById')`.
- Group by feature/module with `describe` blocks.

## Test Structure — Arrange / Act / Assert

- **Arrange** — set up test data and dependencies.
- **Act** — call the function/endpoint under test.
- **Assert** — verify the result.

Keep the three phases visually separated (blank line between) for readability.

## What to Test

- **Happy path**: expected inputs → expected outputs.
- **Edge cases**: empty inputs, boundary values, null/undefined, very large inputs.
- **Error cases**: invalid inputs, network failures, permission denied, timeouts.
- Do NOT test framework internals or third-party libraries — trust them until proven otherwise.

## Mock Policy

- Use real databases for integration tests where possible (Testcontainers, local Postgres, ephemeral Supabase project).
- Mock external APIs and third-party services — but match their real response shapes, not idealized ones.
- Never mock the module under test.
- Prefer dependency injection over module mocking (`jest.mock`/`vi.mock` is a last resort).

## Coverage Philosophy

- Critical business logic: aim for high coverage.
- UI components: test behavior (clicks, form submissions, visibility), not rendering details or snapshot diffs.
- Don't chase 100% — test what matters; 100% coverage with trivial tests is worse than 70% meaningful coverage.

## QA Automation Matrix (Mandatory)

After every development task, QA automation tests are mandatory — not just unit tests.

| Domain | QA Test Type | Default Tool | What to test |
|--------|-------------|-------------|-------------|
| Backend API | API E2E tests | Supertest / Pactum | Endpoints respond correctly, auth works, error responses match format |
| Frontend Web | Browser E2E tests | Playwright | User flows, form submissions, navigation, responsive viewports |
| Mobile | Mobile E2E tests | Detox / Maestro | Screen navigation, gestures, form inputs, platform-specific behavior |
| Database | Migration tests | Project test runner | Migrations up/down, seed data, constraints hold |

Override defaults in the project CLAUDE.md `## QA Tools` section.

## QA Test Placement

- NEVER create a new test file without first checking existing test files for the same feature area.
- Prefer adding test cases to existing files over creating new ones.
- One E2E test file per feature area, not per implementation task.
- Spawn a test-planning subagent before writing QA tests to avoid context bloat.
- The subagent scans, plans placement, reports — it does NOT write tests.

## Test Users & Credentials

- Credentials stored as GitHub secrets: `TEST_USER_EMAIL`, `TEST_USER_PASSWORD`, `TEST_ADMIN_EMAIL`, `TEST_ADMIN_PASSWORD`.
- For local development: stored in `.env.test` (gitignored).
- Never hardcode test credentials in test files — read from environment.
- Rotate test credentials on any suspected exposure.
