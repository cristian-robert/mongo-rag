# Command Reference

## /start — Smart Router
**Phase:** Router | **Arguments:** None
Detects scope level and routes to the correct pipeline.

## /prime — Context Loader
**Phase:** Plan | **Arguments:** None
Loads codebase context. Run at session start or after context reset.

## /create-prd — PRD Generator
**Phase:** Plan (L0) | **Arguments:** Optional idea description
Brainstorms and generates a Product Requirements Document. Output: `docs/plans/PRD.md`

## /plan-project — PRD Decomposer
**Phase:** Plan (L0) | **Arguments:** Optional PRD path (default: `docs/plans/PRD.md`)
Breaks PRD into GitHub milestones and issues. Output: GitHub issues + `docs/plans/roadmap.md`

## /plan-feature — Feature Planner
**Phase:** Plan (L1/L2) | **Arguments:** Feature description or issue number (e.g., `#42`)
5-phase analysis producing a detailed implementation plan. Output: `docs/plans/<feature>.md`

## /execute — Plan Executor
**Phase:** Implement | **Arguments:** Optional plan path (auto-detected if omitted)
Executes plan task-by-task with TDD. Reads mandatory files, runs validation commands.

## /validate — Verification Orchestrator
**Phase:** Validate | **Arguments:** None
Runs lint, tests, type-check, visual testing (tester agents), and code review.

## /ship — Commit + Push + PR
**Phase:** Validate | **Arguments:** None
Stages, commits (conventional), pushes, creates PR linked to issue.

## /evolve — Self-Improvement
**Phase:** Evolve | **Arguments:** None
Updates CLAUDE.md, architect knowledge base, rules, code patterns, test patterns.

## /setup — Health Check
**Phase:** Utility | **Arguments:** None
Checks installed plugins, skills, MCP servers. Reports health and install commands.
