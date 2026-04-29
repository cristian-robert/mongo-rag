# CLAUDE.md Generation Template

Used by `/create-rules` to auto-generate a project CLAUDE.md.
Fill in sections based on codebase analysis.

---

# [Project Name]

## Overview

[Auto-generated: 1-2 sentences about the project, detected from README/package.json]

## Tech Stack

[Auto-detected from package.json, requirements.txt, go.mod, etc.]

| Layer | Technology |
|-------|-----------|
| Language | |
| Framework | |
| Database | |
| ORM | |
| Auth | |
| Styling | |
| Testing | |
| Package Manager | |

## Pipeline Commands (PIV+E)

| Command | Phase | Purpose |
|---------|-------|---------|
| `/start` | Router | Detects scope level, routes to correct pipeline |
| `/prime` | Plan | Loads codebase context |
| `/create-prd` | Plan | Generates PRD (includes brainstorming) |
| `/plan-project` | Plan | PRD → GitHub milestones + issues |
| `/plan-feature` | Plan | Creates implementation plan |
| `/execute` | Implement | Executes plan with TDD |
| `/validate` | Validate | Verification + testing agents |
| `/ship` | Validate | Commit + push + PR |
| `/evolve` | Evolve | Updates rules + knowledge base |
| `/setup` | Utility | Checks plugin/skill health |

## Project Structure

[Auto-generated: tree -L 2 output of key directories]

```
project/
├── src/          # [detected purpose]
├── tests/        # [detected purpose]
└── ...
```

## Development Commands

[Auto-detected from package.json scripts, Makefile, etc.]

```bash
# Start development
<detected dev command>

# Run tests
<detected test command>

# Build
<detected build command>
```

## Code Conventions

[Auto-detected from codebase analysis]

- [Naming convention: camelCase/snake_case/etc.]
- [Import style: absolute/relative]
- [Component pattern: functional/class]
- [Error handling pattern]

## Agents

- **architect-agent** — Call before structural changes (RETRIEVE/IMPACT/RECORD/PATTERN)
- **tester-agent** — Web UI testing after changes (VERIFY/FLOW)
- **mobile-tester-agent** — Mobile testing after changes (VERIFY/FLOW)
- **ui-ux-analyzer** — Design audits on request

## Rules & References

- Domain rules auto-load from `.claude/rules/` based on file paths
- Code patterns in `.claude/references/code-patterns.md`
- See `docs/customization.md` for extending the framework

## Output Compaction

State: off

Controls the `.claude/hooks/output-compact.sh` Stop hook. Defaults to OFF — flip to `on` to enable. Read the rules in `.claude/references/output-compaction.md` first. Does not affect agent-to-agent communication.

Override per-session: `CLAUDE_OUTPUT_COMPACT=on` (force on) or `CLAUDE_OUTPUT_COMPACT=off` (force off).
