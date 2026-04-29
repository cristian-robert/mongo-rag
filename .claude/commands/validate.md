# /validate — Verification Orchestrator

Runs comprehensive verification: automated checks, visual testing, and code review.

## Process

### Phase 1: Automated Checks

Run in parallel:

```bash
# Lint (detect from project)
npm run lint 2>/dev/null || npx eslint . 2>/dev/null || echo "No linter configured"

# Type check (detect from project)
npx tsc --noEmit 2>/dev/null || echo "No TypeScript configured"

# Tests (detect from project)
npm test 2>/dev/null || npx jest 2>/dev/null || npx vitest run 2>/dev/null || echo "No test runner configured"
```

If any check fails, report the failure and offer to fix it before continuing.

### Phase 2: Visual Verification (if applicable)

Detect what was changed:
```bash
git diff --name-only main...HEAD
```

### Visual Pass — Anti-AI-Slop Check

If UI files changed (detect via `git diff --name-only <base>..<head>` matching `.tsx`, `.jsx`, `.vue`, `.css`, `.scss`, `.astro`, `.html`):
1. Load `.claude/rules/frontend-antislop.md` checklist
2. Dispatch `tester-agent` with `MODE=antislop`, passing the checklist
3. tester-agent takes screenshots + cross-checks each item against the rule's Conventions
4. Flag any match against the catalogue in `.claude/references/frontend-antislop-patterns.md`
5. Report findings as blockers (must fix before ship) or notes (non-blocking polish)

If no UI files changed, skip this step.

**If frontend files changed:**
- Dispatch tester-agent with VERIFY queries for affected pages
- Test at minimum: desktop and mobile viewports
- Check: elements render, navigation works, forms submit

**If mobile files changed:**
- Dispatch mobile-tester-agent with VERIFY queries for affected screens
- Check: elements visible, navigation works, interactions respond

**If API/backend files changed:**
- Run API tests if they exist
- Check: endpoints respond with correct status codes
- If Supabase: run `get_advisors` for schema safety

### Phase 2.5: 5D Visual Critique (design artifacts only)

If the changeset includes files under `design/<slug>/` (preview.html, motion MP4/GIF, slide decks, infographics, mockups), run the 5-Dimension Expert Critique before code review. Skip this phase entirely for production-code-only changes.

Backported from huashu-design's expert-critique pattern, with **blocking vs. advisory** split.

| Dimension | What to score | Status |
|---|---|---|
| **2. Visual hierarchy** | Can you tell what's primary, secondary, tertiary in 2 seconds? Is the eye guided, or scanning? Slop hallmark: every element shouts at the same volume. | **BLOCKING (≥7/10 to pass)** |
| **4. Functionality** | Does it solve the actual brief? Are user goals discoverable? For prototypes — does the click flow work end-to-end without confusion? | **BLOCKING (≥7/10 to pass)** |
| **1. Philosophical coherence** | Does the design have a single, identifiable point of view? Or is it a mash-up of references? Slop hallmark: "looks like every AI-generated landing page" — no distinguishable philosophy. | Advisory |
| **3. Execution craft** | Spacing rhythm consistent? Typography pairing intentional? Borders/shadows/radii varied by component role? Slop hallmark: every surface has the same `rounded-lg` + `shadow-sm`. | Advisory |
| **5. Innovation** | Is there at least one moment that doesn't look like training-data median? Or is the whole thing a recombination of common patterns? | Advisory |

**Why split:** the same model that produced the artifact also scores it; numeric LLM judgments are self-correlated. Hierarchy and Functionality have operationalizable definitions (eye-tracking proxy via screenshot inspection, click-flow assertion). Philosophy / Execution / Innovation are taste calls — useful as feedback, dangerous as ship gates. A perfectly fine internal admin tool gets "Innovation 6/10"; that's not a ship-blocker.

**Process:**

1. Dispatch a critique subagent with `MODE=visual-critique`, passing:
   - The artifact path(s) under `design/<slug>/`
   - `.design-system/brand-spec.md` (if present)
   - `.claude/references/frontend-antislop-patterns.md`
   - The deliverable type from the plan frontmatter (`internal-tool` / `external-marketing` / `pitch-deck` / etc.) so scoring can be context-aware
2. Subagent screenshots each artifact at desktop + mobile viewports, then scores each dimension.
3. Subagent returns a radar-shaped report:

   ```
   === 5D Visual Critique ===

   [BLOCKING]
   Visual hierarchy:         N/10  — [one-line rationale]
   Functionality:            N/10  — [one-line rationale]

   [ADVISORY]
   Philosophical coherence:  N/10  — [one-line rationale]
   Execution craft:          N/10  — [one-line rationale]
   Innovation:               N/10  — [one-line rationale]

   Keep:        [what works — preserve in revisions]
   Fix:         [what's blocking — must address before ship]
   Quick wins:  [high-leverage tweaks — 5-min fixes]

   Verdict: PASS (Hierarchy ≥7 AND Functionality ≥7) / FAIL — [which blocking axis]
   ```

4. **Verdict handling:**
   - **PASS** → record advisory scores in `design/<slug>/_critique.md` for future reference; proceed to Phase 3.
   - **FAIL** on a blocking axis → do not proceed. Return findings to the user; either iterate (re-dispatch huashu-design with the fix list) or accept with explicit user override (the user can say "ship anyway" — we don't decide for them).
   - Advisory scores **never block**, but if any advisory axis is ≤4, surface it loudly: that's a "this is shippable but you should know" signal, not a gate.

**Override path:** if the user explicitly types `override: ship anyway` or runs `/validate --skip-visual-critique`, log the override in `design/<slug>/_critique.md` (with timestamp + reason if provided) and proceed. The framework does not block humans; it surfaces signals.

### Phase 3: QA Test Verification

QA automation tests are mandatory for all domains affected by the implementation.

**Step 1: Detect changed domains**

```bash
git diff --name-only main...HEAD
```

Categorize changed files:
- Backend API files (routes, controllers, services) → needs API E2E tests
- Frontend files (pages, components) → needs browser E2E tests
- Mobile files (.ios.tsx, .android.tsx, Expo screens) → needs mobile E2E tests
- Database files (migrations, schemas) → needs migration tests

**Step 2: Spawn test-planning subagent**

Before writing any QA tests, spawn a subagent to plan test placement. The subagent:
1. Scans existing test directories for E2E/integration tests
2. Maps which features/routes/endpoints already have coverage
3. Checks if current changes affect assertions in existing tests
4. Reports back: list of test files to update + new test files to create (if any)

The subagent does NOT write tests — it only produces the placement plan.

**Step 3: Update affected existing tests**

If the planning subagent identified existing tests affected by the implementation, update them first:
- Fix broken assertions caused by the implementation changes
- Add new test cases to existing files for new behavior

**Step 4: Create new QA tests (only where no coverage exists)**

Using the planning subagent's report, create new test files only for uncovered areas:
- One E2E test file per feature area, not per implementation task
- Use the project's QA tool (check CLAUDE.md `## QA Tools` section, or defaults: Playwright for web, Supertest for API, Detox for mobile)
- Test users: read credentials from `.env.test` (local) or reference GitHub secrets documentation

**Step 5: Run all QA tests**

```bash
# Detect and run (project-specific command takes priority)
npm run test:e2e 2>/dev/null || npx playwright test 2>/dev/null || echo "No E2E test runner configured"
```

If any QA test fails, report the failure and offer to fix it before continuing.

### Phase 4: Security Verification

Run the automated security checks from `.claude/references/security-checklist.md`:

1. **Scan for common vulnerabilities:**
   ```bash
   # Check for console.log in production code
   grep -r "console\.log" --include="*.ts" --include="*.js" --exclude-dir=node_modules --exclude-dir=__tests__ . || echo "PASS: No console.log found"

   # Check for hardcoded secrets
   grep -rn "password\s*=\s*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules .
   grep -rn "secret\s*=\s*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules .
   grep -rn "api[_-]key\s*=\s*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules .

   # Check .env in git history
   git log --all --full-history -- .env

   # Check for SQL string concatenation
   grep -rn "query.*+.*\"\|query.*\`.*\${" --include="*.ts" --include="*.js" --exclude-dir=node_modules .

   # Check for wildcard CORS
   grep -rn "origin:\s*['\"]\\*['\"]" --include="*.ts" --include="*.js" --exclude-dir=node_modules .

   # Check for tokens in localStorage
   grep -rn "localStorage.*token\|localStorage.*jwt\|localStorage.*auth" --include="*.ts" --include="*.js" --include="*.tsx" --include="*.jsx" --exclude-dir=node_modules .

   # Run npm audit
   npm audit --audit-level=critical 2>/dev/null || echo "SKIP: npm audit not available"
   ```

2. **Review auth/API changes** (if authentication or API files changed):
   - Verify password hashing uses bcrypt/argon2 with minimum 12 rounds
   - Confirm tokens use httpOnly cookies, not localStorage
   - Check JWT secret length (minimum 32 characters, not hardcoded)
   - Verify access token expiration (15–60 minutes)
   - Confirm rate limiting on /login, /register, and public endpoints
   - Verify authorization checks: users can only access their own data
   - Confirm input validation with schema validation (Zod, Joi, etc.)
   - Check that API responses don't expose passwords, hashes, or internal fields
   - Verify error messages don't reveal system internals or file paths
   - Confirm CORS is restricted to specific domains (no wildcard `*`)

3. **Review database changes** (if schema or query files changed):
   - No SQL string concatenation — parameterized queries or ORM only
   - Application uses limited-permission DB user, not root
   - Sensitive fields encrypted at rest

4. **Verdict:**
   - All automated checks pass + manual review clean → **Security: PASSED**
   - Non-critical items flagged → **Security: PASSED WITH WARNINGS** — list items
   - Critical items found (hardcoded secrets, SQL injection, missing auth) → **Security: FAILED** — must fix before shipping

### Phase 5: Code Review

Invoke the code review skill:
- Review against the implementation plan (does the code match the plan?)
- Check for common issues: error handling, edge cases, security
- Verify no debug code left (console.log, TODO comments, commented-out code)

### Phase 6: Report

```
=== Validation Report ===

Automated Checks:
- Lint: PASS / N issues
- Types: PASS / N errors
- Tests: PASS (N/N) / N failures

Visual Verification:
- [Page/Screen]: PASS / FAIL — [description]

QA Tests:
- API E2E: PASS (N/N) / N failures / not applicable
- Browser E2E: PASS (N/N) / N failures / not applicable
- Mobile E2E: PASS (N/N) / N failures / not applicable

Security Verification:
- Hardcoded secrets: PASS / FAIL
- SQL injection vectors: PASS / FAIL
- Console.log in production: PASS / FAIL
- npm audit: PASS / N critical vulnerabilities
- Auth/API review: PASS / FAIL — [details if applicable]
- Overall: PASSED / PASSED WITH WARNINGS / FAILED

Code Review:
- [Finding 1]
- [Finding 2]

Verdict: Ready to ship / Needs fixes

Next: Run /ship when ready, or fix issues and re-run /validate
```
