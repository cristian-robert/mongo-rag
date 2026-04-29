# /prime — Context Loader (task-aware, lean)

Load a focused, task-aware slice of project context into the current session. Run at the start of any session, after a context reset, or when switching tasks.

The goal is to prime *just enough* context to orient — not to eagerly pull every plan, PRD, or full wiki article. Full bodies are loaded on demand as the task actually references them.

## Step 0: Task Scope

Ask the user:

> What's the scope for this session?
> 1. **Specific GitHub issue** — enter `#<number>`
> 2. **Task description** — one sentence
> 3. **No task** — prime with generic project context only

Wait for the answer. Capture **task keywords** for the KB search in Step 5:

- (1) Issue: run `gh issue view <number>` and extract keywords from the title + first paragraph of the body
- (2) Description: use the sentence itself as keywords
- (3) No task: default keywords to the project name from `package.json` (or `CLAUDE.md` project title)

**Non-interactive fallback:** If `/prime` is invoked non-interactively (e.g., scripted from a hook, CI, or another command that doesn't route through a user), skip the prompt entirely and default to **"no task"** behavior — load only generic project context. Do not block waiting for input.

## Step 1: Structure + History

Run these in parallel for speed:

```bash
git ls-files | head -200
```
```bash
tree -L 3 -I 'node_modules|.next|dist|build|.git|__pycache__|.expo' --dirsfirst
```
```bash
git log --oneline -10
```
```bash
git status --short
```
```bash
git branch --show-current
```

## Step 2: Project Docs (lean)

Read these files if they exist:

- `CLAUDE.md` (project root) — full
- `README.md` — full

**DO NOT** eagerly load `docs/plans/PRD.md`, feature plans, or any plan file based on the branch name alone. Plans are loaded selectively in Step 3 only when they match the Step 0 task scope, and even then only the lightweight sections. Loading every plan up front wastes context on work that isn't this session's focus.

## Step 3: Active Context

- If an issue number was supplied in Step 0 (and not already fetched): `gh issue view <number>`
- If on a feature branch, extract the issue number from the branch name as a secondary signal
- Look for a matching plan file under `docs/plans/` or `docs/superpowers/plans/` — match by issue number, branch name, or task description keywords
- If a plan file is found, **read only the "Goal", "Architecture", and "Mandatory Reading" sections** — not the full plan. Use a targeted read (grep for section headers and read those ranges) rather than a full-file Read. The rest of the plan is loaded on demand when execution reaches those tasks.

## Step 4: Configuration (indexes only)

Load table-of-contents-level views only. Do not follow internal links or expand nested files.

- `.claude/agents/architect-agent/index.md` — read the **TOC only** (top-level module list / link list). Do not recursively read the files it points to.
- `.claude/agents/tester-agent/test-patterns.md` — read the **inventory table only** (page/route listing). Do not expand per-page pattern details.
- Check `package.json` (or equivalent) for available scripts/commands.

## Step 5: Knowledge Base (LEAN)

Check `CLAUDE.md` for a `## Knowledge Base` section with a `Path:` value (e.g., `.obsidian/`). If KB is configured:

1. **Read the lean index:** `<kb-path>/_search/lean-index.json` — metadata-only view (title, type, tags, 1-line summary per article). Always small; load this even with no task. If the file does not exist (e.g., KB configured but never compiled), **skip silently** — do not error, do not try to regenerate it here.

2. **If task keywords were captured in Step 0:**
   - Run: `KB_PATH=<kb-path> node cli/kb-search.js search "<keywords>" --limit=3`
   - Display the top 3 results using their **lean summaries from `lean-index.json`** (title + type + tags + 1-line summary).
   - **DO NOT** read the full article bodies. The agent loads full bodies on demand when a task actually references a specific article.

3. **If no task (Step 0 option 3):**
   - Display `lean-index.json` entries grouped by `type` (overview / architecture / feature / decision / concept / etc.).
   - Do **not** load any article bodies.

If `## Knowledge Base` is not present in `CLAUDE.md`, skip Step 5 entirely.

## Output: Summary Panel

Present a structured summary:

```
=== Project Context ===

Project: [name from package.json/CLAUDE.md]
Branch: [current branch]
Task scope: [issue #<n> | "<description>" | none]
Issue: [linked issue if found, or "none"]
Plan: [active plan file if found (Goal+Architecture+Mandatory Reading only), or "none"]

Structure: [key directories and their purposes]

Recent Activity:
[last 5 commits, one line each]

Uncommitted Changes:
[summary of staged/unstaged changes]

Available Commands:
[dev, test, build commands from package.json]

Knowledge Base: [N articles in wiki, N stubs pending | "not configured"]
KB loaded: [lean-index (N docs) + 0-3 summaries | lean-index (N docs) grouped by type | "not configured" | "lean-index missing, skipped"]

=== Ready. Run /start to begin or specify a command. ===
```
