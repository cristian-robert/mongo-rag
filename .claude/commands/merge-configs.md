# /merge-configs — Merge Existing Config with Framework

Usable any time: post-init, after manual framework upgrade, after repo merge, or when adopting the framework mid-project.

## Arguments

- `$ARGUMENTS` — optional path to a user config directory to merge (defaults to scanning current repo for `.backup` files and `.claude/.init-meta.json`)

## Process

### Step 1: Discover

1. Check for `.claude/.init-meta.json` (post-init marker). If present, read it for the list of backed-up files and version info.
2. Find all `*.backup` files under the repo:
   ```
   find . -name "*.backup" -not -path "./node_modules/*" -not -path "./.git/*"
   ```
3. If `$ARGUMENTS` is provided: also scan that directory for `CLAUDE.md`, `.claude/**`, and the configured KB path (e.g., `.obsidian/**`). Treat files found there as the "user" side and the current repo copies as the "framework" side.

If nothing is found: exit with "No config to merge."

### Step 2: Categorize

Load `.claude/references/merge-strategy.md`. For every discovered file, assign a category from the table (CLAUDE.md, Rules, Commands, References — project-specific, References — templates, Agents — project KB, Agents — test patterns, KB content, Hooks, Settings).

### Step 3: Plan

Present a per-file plan to the user grouped by category. For each entry show:
- File path
- Category and strategy
- A short diff preview for merge-requiring cases (CLAUDE.md sections, Rules, Commands, Hooks, Settings)

### Step 4: Execute (per-file approval)

For each file in the plan:
1. Show the file + strategy
2. Ask: **apply / skip / show full diff / edit**
3. Apply on approval; track applied/skipped counts

Category-specific execution:
- **CLAUDE.md** — identify project sections in the backup (`## Tech Stack`, `## Knowledge Base`, `## Design Skill Preference`, `## QA Tools`, user-added sections not in framework template); splice into new template; write merged file
- **Rules** — diff old vs new; extract user-added conventions, checklist items, skill-chain lines; append to new file; dedupe
- **Commands** — compare backup to the PREVIOUS framework version. Identical → silent discard. User-modified → show diff, prompt for keep/merge/drop
- **References — `code-patterns.md`** — restore from backup verbatim
- **References — other** — discard backup (framework templates)
- **Agents (architect/tester/mobile-tester)** — restore from backup verbatim
- **KB content** — restore from backup verbatim
- **Hooks** — diff old vs new; user-edited → prompt; unchanged → discard
- **Settings (`.claude/settings.local.json`)** — **deep-merge with `cli/merge-settings.js`**:
  1. Run `node cli/merge-settings.js --dry-run --user .claude/settings.local.json.backup --framework .claude/settings.local.json` (or analogous paths for the user/framework copies). The script unions hook arrays by `(matcher, type, command)` tuple, unions `permissions.allow`/`deny`, and lets user values win on scalar conflicts. Show the resulting JSON to the user as the merge plan.
  2. On approval, run the same command with `--apply` instead of `--dry-run` (it writes atomically: tmp file + rename).
  3. The "keep user / keep framework / manual edit" chooser is no longer used for the hooks/permissions case — it dropped one side or the other and broke setups in practice. Use the deep-merge.
  4. If the user wants to skip the deep-merge for some reason (e.g. they want to discard the framework's new hook entirely), they can still hand-edit the file after the merge runs — `--apply` is reversible from the `.backup`.

### Step 5: Cleanup

- Delete all `.backup` files that were processed
- Delete `.claude/.init-meta.json` if present
- Report: **N merged, N restored, N skipped**

## Delegation

`/start` Step 0 delegates to this command when `.claude/.init-meta.json` is found. No merge logic is duplicated between the two commands — `.claude/references/merge-strategy.md` is the single source of truth.
