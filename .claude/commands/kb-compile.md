# /kb compile — Knowledge Base Compiler

Deep-compiles the knowledge base: expands stubs into full articles, cross-links concepts, extracts new topics, runs a health check, and rebuilds indexes. This is where raw sources become structured, interlinked wiki knowledge.

## Arguments

Optional scope argument:

- **Tag name** (e.g., `architecture`) — compile only articles with that tag
- **Article filename** (e.g., `monads.md`) — compile that single article
- **`all`** or omitted — compile everything that needs work

## Prerequisites

Before running, verify:
1. CLAUDE.md has a `## Knowledge Base` section with a `Path:` value — if missing, stop and tell the user to configure it or run `/kb ingest` first
2. At least one article exists in `<kb-path>/wiki/` — if none, stop and suggest running `/kb ingest`

## Process

### Step 1: Detect KB Path

Read the project's CLAUDE.md and extract the `Path:` value from the `## Knowledge Base` section.

```bash
# Example extraction — adapt to actual CLAUDE.md format
grep -A5 "## Knowledge Base" CLAUDE.md | grep "^Path:" | awk '{print $2}'
```

If the section is missing or `Path:` is not set, default to `.obsidian/`. Store as `KB_PATH`.

### Step 2: Scan for Work

Identify what needs compilation:

**Pending/updated raw sources** — read `<KB_PATH>/raw/_manifest.md` and collect every row where the `Status` column is `pending` or `updated`. The manifest columns are:

```
| Source | Date | Type | Raw File | Status | Wiki Article |
```

These are sources whose content hasn't been woven into any article yet.

**Stub articles** — scan all `.md` files in `<KB_PATH>/wiki/` (excluding `_index.md` and `_tags.md`). Read each file's frontmatter and collect those with `status: stub`.

If a scope argument was given, filter both lists to only the matching tag or filename.

Report:
```
Pending sources:  N
Stub articles:    N
```

If both counts are 0 and scope is "all", report "KB is up to date — nothing to compile." and exit.

### Step 3: Expand Stubs

For each stub article (in order of most related pending sources first):

**3a. Gather source material**

Read the article's frontmatter `sources:` list. For each source filename listed, read the full content of `<KB_PATH>/raw/<filename>`.

**3b. Find related articles**

Search the wiki for articles semantically related to this stub:

```bash
KB_PATH=<kb-path> node cli/kb-search.js search "<article title and tags joined>"
```

Read the top 3–5 results (skip the stub itself). These provide cross-article context and prevent duplication.

**3c. Write comprehensive content**

Using the raw source material and related article context, write the full article body. The article must follow the wiki article template structure:

```markdown
## Overview

2–4 sentence summary of what this concept is and why it matters.

## Content

Comprehensive explanation. Use subheadings freely. Cover:
- Core definition and mechanics
- Why it exists / what problem it solves
- How it works in practice
- Key variants or subtypes (if applicable)
- Relationship to related concepts

## Key Takeaways

- Bullet-point distillation of the most important insights
- Each takeaway should be actionable or memorable
- Aim for 4–8 bullets

## Examples

Concrete examples, code snippets, or case studies where relevant.

## See Also

- [[Related Article 1]]
- [[Related Article 2]]
```

**3d. Update frontmatter**

Change `status: stub` to `status: compiled`. Update the `updated` date to today.

**3e. Write the file**

Write the expanded content back to `<KB_PATH>/wiki/<filename>`. Preserve all existing frontmatter fields — only change `status` and `updated`.

### Step 4: Cross-Link Articles

Scan all compiled articles to build a concept map and add wikilinks:

**4a. Build concept list**

Collect every article title and its aliases (from frontmatter `aliases:` if present). Build a lookup map: `concept name → article filename`.

**4b. Scan for unlinked mentions**

For each article body, find plain-text mentions of other article titles that are not already wrapped in `[[...]]`. Only match whole words/phrases (not partial matches inside longer words).

**4c. Add wikilinks**

Replace the first mention of each concept per article with `[[Article Title]]`. Do not link every occurrence — one wikilink per concept per article is enough.

**4d. Update `related:` frontmatter bidirectionally**

When article A links to article B, ensure:
- `related:` in article A includes B's filename
- `related:` in article B includes A's filename

Deduplicate the `related:` lists after updating.

### Step 5: Extract New Concepts

Identify concepts worth creating new stub articles for:

**5a. Find frequently mentioned concepts**

Scan all article bodies for noun phrases that appear in 3 or more articles but do not have their own wiki article. Focus on technical terms, named patterns, tools, and frameworks — not generic words.

**5b. Find comparison opportunities**

Look for pairs of articles whose titles or tags suggest a natural comparison (e.g., two tools in the same category, two approaches to the same problem). Flag these as candidates for a `type: comparison` article.

**5c. Create new stubs**

For each identified concept (up to 10 per run to avoid explosion), create a new stub article in `<KB_PATH>/wiki/` using the standard frontmatter:

```markdown
---
title: "<Concept Name>"
type: concept
tags: [<inferred tags>]
status: stub
sources: []
related: [<articles that mention it>]
created: <today>
updated: <today>
---

## Overview

_Stub — to be compiled._
```

### Step 6: Health Check

Run structural and content checks across the entire wiki. Write results to `<KB_PATH>/_search/stats.md`.

**Structural checks:**

- **Orphaned articles** — articles with no incoming wikilinks and no `related:` entries. List filenames.
- **Broken wikilinks** — `[[Title]]` references that don't match any article title or alias. List each broken link with the source article.
- **Old stubs** — articles with `status: stub` and `created` date older than 30 days. List filenames and age.
- **Incomplete frontmatter** — articles missing required fields (`title`, `type`, `tags`, `status`). List filenames and missing fields.

**Content checks:**

- **Potential duplicates** — pairs of articles with very similar titles or high tag overlap. List pairs with a suggested action (merge or differentiate).
- **Inconsistencies** — articles that contradict each other on key claims (flag manually; note filenames for human review).
- **Stale sources** — entries in `_manifest.md` with `status: compiled` but `updated` date older than 90 days. These may need re-ingestion.
- **Missing Key Takeaways** — compiled articles that have no `## Key Takeaways` section.

**Suggestions:**

- **Merge candidates** — orphaned articles that could be folded into a more popular related article.
- **Missing concepts** — top 5 frequently mentioned concepts that lack their own article (beyond what was created in Step 5).
- **Stale articles** — compiled articles not updated in 6+ months whose source domain changes frequently.

**Write `stats.md`** in the format shown below.

### Step 7: Rebuild Indexes

**7a. Rebuild `wiki/_index.md`**

Generate an alphabetical index of all articles:

```markdown
# Knowledge Base Index

_Last updated: <date>. Total: N articles._

## A
- [[Article Title]] — one-line description from Overview

## B
...
```

**7b. Rebuild `wiki/_tags.md`**

Generate a tag-grouped index:

```markdown
# Articles by Tag

_Last updated: <date>._

## <tag-name> (N)
- [[Article Title]]
- [[Article Title]]

## <tag-name> (N)
...
```

Sort tags alphabetically. Sort articles within each tag by title.

**7c. Rebuild search index**

```bash
KB_PATH=<kb-path> node cli/kb-search.js index
```

`kb-search.js index` also rebuilds `<kb-path>/_search/lean-index.json` — the metadata-only view used by `/prime`. Confirm both files exist after this step. If you need to rebuild just the lean index (e.g. after a quick edit that only changed titles/tags/summaries), run:

```bash
KB_PATH=<kb-path> node cli/lean-index.js
```

### Step 7d: Health Check (Karpathy lint pass)

After the mechanical index rebuild, run an LLM-assisted content audit — this is the Karpathy-style lint pass that catches issues the structural checks in Step 6 cannot. Work through each sub-step and report findings before editing:

1. **Inconsistent data across articles** — scan compiled articles for conflicting facts (e.g., two articles give different values for the same constant, different descriptions of the same pattern). Flag the pair and the specific disagreement.
2. **Missing data imputation** — for concepts referenced but underspecified, use web search (or the existing `/kb ingest`/WebSearch tools) to fetch authoritative data and propose an update diff. Do not silently edit — show the user.
3. **Orphan-concept → new article candidates** — list concepts mentioned in 3+ articles without their own wiki page (beyond what Step 5 created). Propose new stub titles.
4. **Report first, edit after approval** — print all findings to the user. Wait for explicit approval per item before applying edits. Do not batch-apply.

### Step 8: Update Manifest

For each source that was successfully woven into a compiled article, update its row in `<KB_PATH>/raw/_manifest.md`:

- Change the `Status` column from `pending` or `updated` to `compiled`
- Set the `Wiki Article` column to the wiki article filename (e.g. `wiki/<slug>.md`)

### Step 9: Report

```
=== /kb compile ===

Sources processed:  N  (N pending, N updated)
Stubs expanded:     N
New stubs created:  N
Cross-links added:  N
Articles indexed:   N

Health issues:
  Structural: N  (N orphans, N broken links, N old stubs, N incomplete)
  Content:    N  (N duplicates, N stale sources, N missing takeaways)

Suggestions:        N
Full report:        <KB_PATH>/_search/stats.md

Next: Run /kb compile again after resolving stubs, or /kb ask to query the KB.
```

If errors occurred (e.g., missing source files, unreadable articles), list them separately:
```
Errors (N):
  - <filename>: <reason>
```

---

## `stats.md` Output Format

The health check writes `<KB_PATH>/_search/stats.md` in this format:

```markdown
# Knowledge Base Health Report

_Generated: <ISO timestamp>_

## Stats

| Metric | Count |
|--------|-------|
| Total articles | N |
| Compiled | N |
| Stubs | N |
| Orphaned | N |
| Total sources | N |
| Pending sources | N |

## Structural Issues

### Orphaned Articles
- `filename.md` — no incoming links, no related entries

### Broken Wikilinks
- `source-article.md` → `[[Missing Title]]`

### Old Stubs (>30 days)
- `filename.md` — created YYYY-MM-DD (N days old)

### Incomplete Frontmatter
- `filename.md` — missing: title, tags

## Content Issues

### Potential Duplicates
| Article A | Article B | Shared Tags | Suggestion |
|-----------|-----------|-------------|------------|
| `a.md` | `b.md` | tag1, tag2 | Consider merging |

### Missing Key Takeaways
- `filename.md`

### Stale Sources (>90 days since compile)
- `source.md` — last compiled YYYY-MM-DD

## Suggestions

### Merge Candidates
- `orphan.md` → could be folded into `[[Related Article]]`

### Missing Concepts
Top concepts mentioned in 3+ articles without their own article:
1. Concept Name (mentioned in N articles)
2. ...

### Stale Articles
- `filename.md` — last updated YYYY-MM-DD, domain changes frequently
```
