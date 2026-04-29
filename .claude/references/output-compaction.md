# Output Compaction Rules (Caveman-style)

## Goal
Reduce user-facing assistant output tokens while preserving all semantic meaning. Applies ONLY to agent→user text, never agent↔agent payloads.

## PRESERVE (do not compact)
- Fenced code blocks (```lang ... ```)
- File paths with line numbers (`foo.ts:42`)
- Numeric data, dates, IDs, URLs
- Headings, lists, tables
- Text inside inline code backticks
- Multi-sentence reasoning the user explicitly asked for

## COMPACT
- Hedging: "it seems", "I think", "I believe" → drop
- Redundant politeness: "Great!", "Absolutely!", "Of course" → drop
- Filler: "as you can see", "essentially", "basically" → drop
- Repetition of user's prompt back at them → drop
- Verbose acknowledgments: "I'll now do X as you asked" → "Doing X"
- Passive voice → active (where mechanically safe)

## OFF-LIMITS
- Error messages (must remain exact)
- Security/warning text
- Anything marked with HTML comment `<!-- no-compact -->` — the entire output is passed through unchanged if this marker appears anywhere in it

## Opt-in (default is OFF)

The hook is **opt-in**. It runs compaction only when an explicit signal is present:

- Env var `CLAUDE_OUTPUT_COMPACT=on` (per-session opt-in), OR
- `## Output Compaction` section in `CLAUDE.md` containing the directive `State: on` (project-level opt-in)

Anything else — no section, missing `State` line, `State: off`, or env unset — leaves output untouched.

### Why opt-in

The hedge word-list is Anglocentric. It will strip tokens like "I think", "Basically", "Of course" from prose lines outside fenced code, inline backticks, and lists. That's fine for English-only summaries, but risks dropping legitimate words inside:

- Quoted speech ("She said, 'I think the build is fine.'")
- Numeric prose where a stripped word changes parsing
- Non-English content where the heuristic doesn't apply
- Technical writing where "essentially" / "basically" carry meaning

Read this whole file before flipping `State: on`. If you only want a one-off bypass, use `<!-- no-compact -->` instead of disabling the hook.

## Per-session escape hatches

- Set env var `CLAUDE_OUTPUT_COMPACT=off` to force OFF even if the project opted in.
- Emit `<!-- no-compact -->` anywhere in the output to bypass on a per-message basis.

## Implementation

See `.claude/hooks/output-compact.sh` (registered as a Stop hook in `.claude/settings.local.json`).
