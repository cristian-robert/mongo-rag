---
name: e2e-test
description: End-to-end testing orchestration. Discovers user journeys, runs browser tests, validates database state, auto-fixes bugs found during testing, generates report.
---

# E2E Test Skill

Orchestrates a comprehensive end-to-end testing run across the application.

## When to Use

- After implementing a feature (before /ship)
- As part of /validate
- When verifying existing functionality still works

## Process

### Phase 1: Pre-flight
1. Check that the application is running (curl the base URL)
2. If not running, start it using the dev command from test-patterns.md
3. Verify agent-browser or playwright-cli is available

### Phase 2: Discovery
Launch 2-3 parallel sub-agents to gather intelligence:

**Agent 1 — App Structure:**
- Read tester-agent/test-patterns.md
- Identify all user-facing pages/routes
- Map critical user journeys (signup, login, use feature, logout)

**Agent 2 — Data Flows:**
- Read architect-agent knowledge base
- Identify data-modifying operations (create, update, delete)
- Note expected database state changes

**Agent 3 — Bug Hunting:**
- Read recent git changes (git diff main...HEAD)
- Identify areas most likely to have bugs
- Prioritize testing for changed code paths

### Phase 3: Test Execution

For each discovered user journey:

1. **Navigate** to the starting page
2. **Execute** each step in the journey
3. **Verify** UI state after each step (elements visible, correct content)
4. **Verify** database state after data-modifying steps (query DB directly)
5. **Test** at 3 viewports: desktop (1440px), tablet (768px), mobile (375px)
6. **Screenshot** on failures only

### Phase 4: Fix Loop

When a test fails:
1. Diagnose the root cause
2. Fix the code
3. Re-run the failing step
4. Screenshot the fix
5. Continue testing

### Phase 5: Report

Generate a test report:

```markdown
# E2E Test Report — YYYY-MM-DD

## Summary
- Journeys tested: N
- Steps executed: N
- Passed: N
- Failed: N (M auto-fixed)

## Journeys

### [Journey Name]
- Status: PASS / FAIL
- Steps: N/N passed
- Viewports: desktop, tablet, mobile
- Fixes applied: [list if any]

## Auto-Fixes Applied
- [File: change description]

## Remaining Issues
- [Issue description — create GitHub issue]
```
