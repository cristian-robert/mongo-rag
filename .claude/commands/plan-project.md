# /plan-project — PRD to GitHub Issues Decomposer

Decomposes a PRD into GitHub milestones and issues. This bridges the gap between project vision and actionable work items.

## Arguments

- `$ARGUMENTS` — optional: path to PRD file (default: `docs/plans/PRD.md`)

## Prerequisites

- A PRD must exist (run `/create-prd` first if it doesn't)
- GitHub CLI (`gh`) must be authenticated
- Repository must have a GitHub remote

## Process

### Phase 1: Parse PRD

1. Read the PRD file
2. Identify the implementation phases — each becomes a **GitHub milestone**
3. Within each phase, identify discrete features — each becomes a **GitHub issue**

### Phase 2: Decompose into Issues

For each feature/task identified:

1. Write issue title: `[type]: brief description`
2. Write issue body using `.claude/references/issue-template.md` format:
   - Description (what and why)
   - Acceptance criteria (testable checkboxes)
   - Technical notes (files to modify, patterns to follow)
   - Size estimate (S/M/L/XL)
3. Assign labels: type (`feat`/`fix`/`chore`), priority, size
4. Map dependencies: which issues block which

### Phase 3: Determine Order

1. Build dependency graph
2. Identify critical path (longest chain of blocking dependencies)
3. Identify parallelizable work (independent issues that can be worked simultaneously)
4. Order issues by: dependencies first, then critical path, then highest value, then smallest size

### Phase 4: Present for Review

Present the full breakdown to the user:

```
## Milestone 1: [Phase Name]

### Issue 1: [feat: description] (Size: M, Priority: High)
- Acceptance criteria: ...
- Depends on: nothing
- Blocks: Issue 2, Issue 3

### Issue 2: [feat: description] (Size: L, Priority: High)
- Acceptance criteria: ...
- Depends on: Issue 1
- Blocks: Issue 5
```

Ask: "Does this breakdown look right? Any issues to add, remove, or resize?"

### Phase 5: Create in GitHub

After user approval, create milestones and issues using `gh` CLI:

```bash
# Create milestones
gh api repos/{owner}/{repo}/milestones -f title="Phase 1: [Name]" -f description="[Description]"

# Create issues with labels and milestone
gh issue create --title "[type]: description" --body "..." --label "feat,priority:high,size:M" --milestone "Phase 1: [Name]"
```

For issues with dependencies, add a "Blocked by #N" line in the issue body.

#### Knowledge Base Integration (if configured)

Check CLAUDE.md for a `## Knowledge Base` section with a `Path:` value. If configured, after creating each GitHub issue:

1. Search for an existing feature article: `KB_PATH=<kb-path> node cli/kb-search.js search "<feature name>" --type=feature`
2. If found: update the article's `## GitHub Issues` section with the new issue number and title
3. If not found: create a new feature article in `wiki/<feature-name>.md` using `.claude/references/kb-article-template.md` feature template, with:
   - Summary from the issue description
   - GitHub Issues section listing the new issue
   - Tags relevant to the feature domain
4. If architectural decisions were made, create decision articles in `wiki/adr-NNN-<title>.md` using the decision template
5. Update `wiki/_index.md`, `wiki/_tags.md`
6. Run: `KB_PATH=<kb-path> node cli/kb-search.js index`

Stage knowledge base files for commit:

```bash
git add <kb-path>/wiki/
```

If no knowledge base configured, skip this step.

### Phase 6: Generate Roadmap

Save a roadmap file to `docs/plans/roadmap.md`:

```markdown
# Project Roadmap

Generated from PRD on YYYY-MM-DD

## Milestone 1: [Phase Name]
- [ ] #1 — [title] (Size: M)
- [ ] #2 — [title] (Size: L) — blocked by #1

## Critical Path
#1 → #2 → #4 → #7 → #9

## Parallel Tracks
Track A: #1 → #2 → #4
Track B: #1 → #3 → #5
```

Commit:

```bash
git add docs/plans/roadmap.md
git commit -m "docs: add project roadmap with GitHub issues"
```

## Re-running

When the PRD is updated, run `/plan-project` again. It will:

1. Read existing GitHub issues
2. Diff against updated PRD
3. Suggest: new issues to create, existing issues to update, obsolete issues to close
4. Present changes for approval before executing
