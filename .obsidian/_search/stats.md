# Knowledge Base Health Report

_Generated: 2026-05-02 (post `/kb compile` after #79 merge)_

## Stats

| Metric | Count |
|--------|-------|
| Total articles | 27 |
| Compiled | 19 |
| Active / accepted / draft (alternate but valid status) | 8 |
| Stubs | 0 |
| Total raw sources | 4 |
| Pending sources | 0 |

## What this run did

Two stubs created in the prior `/evolve` run were expanded to full articles, manifest updated, KB indexes rebuilt.

**Compiled this run:**

1. `wiki/concept-subagent-driven-execution-gotchas.md` — three (now four) recurring subagent dispatch failure modes, with a drop-in subagent prompt boilerplate. Source: `raw/sessions/2026-05-02-blobstore-fly-deploy-learnings.md`. Cross-linked from `_global.md`.
2. `wiki/tooling-test-web-app.md` — restructured the rich stub into the canonical `Overview / Content / Key takeaways / Examples / See also` template; added bidirectional `related:` link with `feature-embeddable-widget.md`. Source: `raw/sessions/2026-04-30-test-web-app-scaffold.md`.

## Structural Issues

### Orphaned Articles
- None.

### Broken Wikilinks
- `[[2026-05-02-blobstore-fly-deploy-learnings]]` referenced from two wiki articles. **Not actually broken** — it links to the raw session note at `raw/sessions/2026-05-02-blobstore-fly-deploy-learnings.md`, which Obsidian's linkpath resolver finds via vault search. Flagged here only because `cli/kb-search.js` scans only `wiki/` for resolution targets; this is a known limitation of the indexer, not a content bug.

### Old Stubs (>30 days)
- None.

### Incomplete Frontmatter
- None.

## Content Issues

### Potential Duplicates
| Article A | Article B | Shared Tags | Suggestion |
|---|---|---|---|
| (none new this run) | | | |

### Missing Key Takeaways
- None — all 27 articles have a `Key takeaways` section.

### Stale Sources
- None.

## Suggestions

### Merge Candidates
- None new this run.

### Missing Concepts (mentioned in 3+ articles without their own page)
- A dedicated `concept-celery-autoretry-and-terminal-failure.md` could capture the `_will_celery_retry(task, exc)` predicate + the `_is_terminal_failure` symmetry introduced in Wave C of #79. Currently lives only in `worker.py` source. Worth elevating only if reused beyond ingestion.
- A dedicated `decision-blob-uri-scheme.md` — the choice between `fs://` / `supabase://` / future `s3://` is documented inside `decision-blobstore-handoff.md`. If a third backend lands, split it out.

### Stale Articles
- None.

## Karpathy Lint-Pass Findings (Step 7d)

1. **Indexer wikilink-resolution gap** — `cli/kb-search.js` scans only `wiki/` for link targets. Wikilinks pointing at `raw/sessions/*` (legitimate in Obsidian) are flagged as broken by the indexer's own check. Not a content issue; consider widening the resolver or accepting the false positive.
2. **Mixed status vocabulary** — articles use `compiled` (concepts/features), `active` (some features), `accepted` (decisions), `draft` (one stripe-billing article in progress). The `/kb compile` health check needs to recognize all four as valid. Currently only `compiled` and `stub` are checked; the others slip through as MISSING in naive greps.
3. **No speculative edits** — every change traceable to a raw source file. The two compiled articles fold in additional learnings (4th and 5th from the raw session) that were noted but not pasted verbatim.
