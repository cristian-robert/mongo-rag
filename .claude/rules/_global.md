# Global Rules

## Git Workflow

- Branch naming: `{type}/{description}` (e.g., `feat/user-auth`, `fix/login-redirect`)
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`
- Always link PRs to GitHub issues
- Never commit directly to main/master — use feature branches

## Code Standards

- TypeScript strict mode where applicable
- Self-documenting code — comments only for non-obvious logic
- No unnecessary abstractions or over-engineering (YAGNI)
- DRY — but three similar lines beats a premature abstraction

## Knowledge Base Integration

When the project's CLAUDE.md has a `## Knowledge Base` section with a `Path:` value, the KB is active. Follow these rules:

**Before starting work:**
- Search the KB for context relevant to the task: `KB_PATH=<path> node cli/kb-search.js search "<keywords>"`
- Read the top results — they contain architecture decisions, patterns, and feature context that prevent redundant work and inconsistent implementations

**After structural changes** (new modules, endpoints, routes, screens, DB tables, components):
- Search for existing articles to update: `KB_PATH=<path> node cli/kb-search.js search "<feature or area>"`
- Update existing wiki articles rather than creating duplicates
- If creating a new article, use the template from `.claude/references/kb-article-template.md`
- Rebuild KB indexes (both TF-IDF and lean) with the single command: `KB_PATH=<path> node cli/kb-search.js index` — this atomically rebuilds `_search/index.json` AND `_search/lean-index.json` so `/prime` (lean reader) and `/kb search` (TF-IDF reader) never see stale state.

**Skip KB** for: trivial changes, typo fixes, config tweaks, dependency bumps.

## Pipeline Discipline

- For non-trivial work: choose Superpowers or Standard mode before starting
- Plans are mandatory for L/XL tasks — run `/plan-feature` first
- Run `/validate` before claiming work is done
- Run `/evolve` after merging to keep the system improving
- When dispatching subagents to execute multi-task plans, include the boilerplate guards from `[[concept-subagent-driven-execution-gotchas]]` (direct-git fallback for commits, `cd` reset before commits, `tee` instead of `tail` for monitorable output)

## Rule File Budget

- Rule files are indexes, not encyclopedias. Target ≤150 lines, soft cap 200.
- Detail lives in `.claude/references/*.md` or the wiki (when KB is configured).
- Every rule file ends with a `## References` block listing `path — when to load`.
- `/evolve` enforces this — if a rule exceeds 200 lines, /evolve extracts overflow to a reference file on the next run.
