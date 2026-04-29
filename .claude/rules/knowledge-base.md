---
globs: [".obsidian/**/*.md", "**/wiki/**/*.md", "**/raw/**/*.md", "**/knowledge/**/*.md", "**/_search/**"]
description: Auto-loads when editing knowledge base files. Enforces wiki article format, backlinks, and index consistency.
---

# Knowledge Base Rules

## Skill Chain

When editing or creating KB wiki articles, follow this order:

1. **`/kb search`** — search for related articles before creating new ones to avoid duplicates
2. **Create/update article** — follow frontmatter format from `.claude/references/kb-article-template.md`
3. **Update backlinks** — add wikilinks in both directions (source article and all referenced articles)
4. **Update index files** — reflect changes in `wiki/_index.md` and add any new tags to `wiki/_tags.md`
5. **Rebuild KB indexes** — run `KB_PATH=<kb-path> node cli/kb-search.js index` after changes (rebuilds BOTH the TF-IDF `_search/index.json` and the lean `_search/lean-index.json` atomically)

## Conventions

- Never edit `raw/` files — these are source-of-truth snapshots; treat as read-only
- Wiki articles are LLM-maintained — users rarely touch them directly; prefer `/kb` commands
- Every article must have complete frontmatter with all required fields (title, tags, created, updated, related)
- Wikilinks use `[[filename-without-extension]]` syntax (Obsidian-compatible)
- Tags: lowercase, hyphenated (e.g., `machine-learning`, `data-pipeline`)
- Filenames: slugified titles (e.g., `my-article-title.md`)
- Stubs must be expanded in the next `/kb compile` run — never leave a stub indefinitely
- Files starting with `_` are index files — auto-generated, do not manually edit

## Checklist

- [ ] Frontmatter is complete (all required fields present and populated)
- [ ] Backlinks updated bidirectionally (every `[[link]]` has a reciprocal entry in the target article)
- [ ] `_index.md` reflects article additions, removals, or title changes
- [ ] `_tags.md` reflects any new or removed tags
- [ ] No broken wikilinks (all `[[references]]` point to existing files)
- [ ] Both KB indexes rebuilt after changes (`node cli/kb-search.js index` does both — TF-IDF and lean)

## Karpathy Workflow Checklist

Karpathy-style KB maintenance treats the wiki as a living artifact: raw sources flow in, compile into wiki articles, get lint-passed for consistency, and expose a lean metadata view for cheap context loading. After a maintenance session, confirm:

- [ ] raw → compile loop exercised (new/updated raw sources turned into wiki stubs, stubs expanded into full articles)
- [ ] Health-check lint pass run (inconsistencies, missing data, orphan concepts — see `/kb compile` Step 7d)
- [ ] Both KB indexes rebuilt after changes — run `KB_PATH=<kb-path> node cli/kb-search.js index` (rebuilds TF-IDF and lean atomically; auto-triggered by `/kb compile`'s index step, run manually after out-of-band edits)
