# Hook Ordering and Coupling

This file documents the lifecycle ordering of the hooks shipped in `.claude/hooks/` and the coupling rules that prevent any hook from corrupting another's input.

## Lifecycle order (per turn)

Claude Code runs hooks at well-defined points. Within one user turn, the rough order is:

1. **PreToolUse / PostToolUse hooks** — fire during the tool loop, once per matched tool call. Examples in this repo:
   - `spec-reviewer-enforce.sh` (PostToolUse on `TodoWrite|TaskUpdate`)
   - `architect-sync.sh`, `branch-guard.sh`, `plan-required.sh`, `evolve-reminder.sh`, `session-primer.sh` — fired by the matchers configured in `.claude/settings.local.json`.
2. **Stop hook** — fires once on the final assistant message after the tool loop concludes. Only `output-compact.sh` is configured for Stop.

This means PostToolUse hooks see structural inter-agent payloads (TodoWrite items, dispatch announcements, marker writes), while the Stop hook only sees the final user-facing message. Compaction never touches inter-agent payloads, because those never reach Stop.

## Coupling rules

Hooks must not corrupt each other's inputs. The compact hook is the only one that rewrites text, so the rules below are scoped to it.

### Marker-safe lines (output-compact.sh)

`output-compact.sh` preserves any line matching one of these patterns:

- Begins with ```` ``` ```` (fenced code block toggle)
- Begins with `|` (markdown table)
- Begins with a list bullet (`-`, `*`, or `N.`)
- Begins with `#` (heading)
- Begins with `>` (blockquote — used for quoted user text)
- Contains a `file:line` pattern (e.g. `foo.ts:42`)
- Contains the substring `[dispatch] role=` (structural coupling token consumed by `spec-reviewer-enforce.sh` — see `.claude/commands/execute.md` Step 3)
- Contains the literal `[no-compact]` (explicit per-line bypass)
- Contains the HTML comment `<!-- no-compact -->` anywhere (whole-output bypass)

If you add a new structural marker that may appear in user-facing text and must survive compaction, document it here and add a regex to the awk preserve list in `output-compact.sh`.

### Why dispatch markers are preserved

`/execute` Step 3 announces implementer/reviewer dispatches with literal lines like:

```
Starting Task 3: KB integration — [dispatch] role=task-implementer task=3
Task 3 implementer complete — [dispatch] role=spec-reviewer task=3
```

These announcements appear in the assistant's user-facing text, which means they pass through the Stop hook. If compaction rewrote them (e.g. stripped a hedging word that happened to be on the same line), the marker substring could be split across the awk preserve check and the sed rewrite, breaking the contract with `spec-reviewer-enforce.sh`. Preserving the whole line keeps the structural coupling intact.

## Adding a new hook

When introducing a new hook:

1. Decide its lifecycle slot (PreToolUse / PostToolUse / Stop) and document it here.
2. If the hook reads or writes a marker file, document the marker location, format, and lifecycle (write → read → clear).
3. If the hook produces a structural token that must appear in user-facing text, add the token's literal substring to the compact-hook preserve list AND a regression test in `cli/hook-compact.test.sh`.
