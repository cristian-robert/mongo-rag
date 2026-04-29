# /kb ingest — Knowledge Base Ingestion

Ingest a source (URL, file, directory, or session learnings) into the knowledge base.

## Arguments

- `$ARGUMENTS` — source to ingest. One of:
  - A URL (e.g. `https://example.com/paper`)
  - A local file path (e.g. `docs/architecture.md`)
  - A directory path (e.g. `docs/`)
  - The literal string `session` — extracts key learnings from this conversation

## Prerequisites

- Knowledge base configured in CLAUDE.md (`## Knowledge Base` section with `Path:`)
- For URL ingestion: Firecrawl MCP available (fall back to WebFetch if not)

---

### Ingesting web articles

- **Preferred path:** use the [Obsidian Web Clipper](https://obsidian.md/clipper) browser extension to save a page as `.md` directly into `<kb-path>/raw/articles/`. This preserves layout, alt text, and reliable metadata better than scraping — and the frontmatter it emits already matches this command's conventions.
- **Related images:** configure a hotkey or userscript in the Clipper to download inline images alongside the `.md` into a sibling directory (e.g. `<kb-path>/raw/articles/_assets/<slug>/`). Keeping images local lets the LLM reference them by relative path and survives source-site link rot.
- After clipping, run `/kb ingest <path-to-clipped-file>` so the manifest and stub are created the same way as a URL ingest. The command will detect the existing file and skip re-fetching.

---

## Process

### Step 1: Detect KB Path

1. Read the project's `CLAUDE.md`.
2. Find the `## Knowledge Base` section. Extract the `Path:` value (e.g. `Path: .kb/`). If the section is missing or has no `Path:`, stop and report: "Knowledge base not configured. Add a `## Knowledge Base` section with `Path: <directory>` to CLAUDE.md."
3. Resolve the path relative to the project root. Verify it exists. If not, create the full directory structure:

```
<kb-path>/
├── raw/
│   ├── articles/        # Blog posts, essays, opinion pieces
│   ├── papers/          # Academic papers, research reports
│   ├── docs/            # Official documentation, API references
│   ├── repos/           # Source code repositories, READMEs
│   └── sessions/        # Extracted session learnings
├── wiki/                # Synthesized wiki articles
└── (existing subdirectories preserved)
```

After creating missing directories, also create `raw/_manifest.md` if it does not exist:

```markdown
# Raw Ingestion Manifest

| Source | Date | Type | Raw File | Status | Wiki Article |
|--------|------|------|----------|--------|--------------|
```

And create `wiki/_index.md` if it does not exist:

```markdown
# Wiki Index

| Slug | Title | Tags | Status |
|------|-------|------|--------|
```

And create `wiki/_tags.md` if it does not exist:

```markdown
# Tag Index

| Tag | Articles |
|-----|----------|
```

---

### Step 2: Detect Source Type and Fetch Content

Inspect `$ARGUMENTS` to classify the source:

| Condition | Source Type | Category |
|-----------|-------------|----------|
| Starts with `http://` or `https://` | URL | Detect from content (see below) |
| Is the literal string `session` | Session | `sessions/` |
| Path ends with `.md`, `.txt`, `.pdf`, `.rst`, `.html` | Local file | Detect from content |
| Path is a directory | Directory | Detect from content |

**Fetching by source type:**

- **URL:** Use Firecrawl MCP (`scrape` with `formats: ["markdown"]`) to retrieve the page as markdown. If Firecrawl is unavailable, fall back to WebFetch. Extract the main body text; strip navigation, footers, and ads.
- **Local file:** Use the Read tool to load the file content.
- **Directory:** Use the Read tool on each file in the directory (non-recursive by default unless the user adds `--recursive`). Concatenate them into a single markdown document with `---` separators and file path headers.
- **Session:** Extract from the current conversation context: decisions made, patterns identified, bugs fixed, conventions established, tools or libraries used, and any key takeaways. Format as structured markdown.

**Category detection** (for URLs and files — not sessions):

Scan the title and first 500 characters:
- Contains "arxiv", "doi", "abstract", "proceedings", or "journal" → `papers/`
- Comes from a known docs domain (docs.*, developer.*, api.*, reference.*) → `docs/`
- Comes from github.com or gitlab.com → `repos/`
- Default → `articles/`

---

### Step 3: Save to Raw

Compute:
- `<date>` = today's date in `YYYY-MM-DD` format
- `<slug>` = slugified title (lowercase, spaces → hyphens, strip special characters, max 60 chars). If no clear title, derive from the URL hostname + path, filename, or directory name.
- `<category>` = one of `articles`, `papers`, `docs`, `repos`, `sessions`
- `<raw-path>` = `<kb-path>/raw/<category>/<date>-<slug>.md`

Write the raw file with this metadata header followed by the fetched content:

```markdown
---
source: <original URL or file path or "session">
ingested: <YYYY-MM-DD>
type: <articles | papers | docs | repos | sessions>
title: <extracted or inferred title>
---

<fetched content>
```

---

### Step 4: Update Manifest

Append one row to `<kb-path>/raw/_manifest.md`:

```
| <source> | <YYYY-MM-DD> | <category> | raw/<category>/<date>-<slug>.md | pending | — |
```

The table header (already present) is:

```
| Source | Date | Type | Raw File | Status | Wiki Article |
```

- **Source**: original URL or file path
- **Date**: ingestion date
- **Type**: article, paper, doc, repo, session
- **Raw File**: path to the raw file
- **Status**: starts as `pending`; updated to `compiled` by `/kb compile`
- **Wiki Article**: filename of the wiki article; filled by `/kb compile`, `—` until then

---

### Step 5: Create Stub Wiki Article

Read `.claude/references/kb-article-template.md` for the canonical stub format. If that file does not exist, use this structure:

```markdown
---
title: <title>
tags: [<tag1>, <tag2>, ...]
status: stub
source: <raw-path>
created: <YYYY-MM-DD>
---

# <title>

## Summary

<One paragraph summarising the source: what it is, what problem it addresses, and why it matters to this project.>

## Key Takeaways

- <Takeaway 1>
- <Takeaway 2>
- <Takeaway 3>

## Related

- <!-- link to related wiki articles once they exist -->
```

**Generating content for the stub:**

- **title:** From the fetched content's H1, `<title>` tag, or document heading. Clean it up for readability.
- **tags:** Choose 2–5 descriptive tags relevant to the content domain (e.g. `llm`, `architecture`, `performance`, `security`, `tooling`). Reuse existing tags from `wiki/_tags.md` where they fit.
- **summary:** Write one concise paragraph (3–5 sentences) summarising what the source covers and its relevance.
- **key takeaways:** List 3–7 concrete, actionable insights from the source.

6. Check if `wiki/<slug>.md` already exists. If so, append a numeric suffix: `wiki/<slug>-2.md`, `wiki/<slug>-3.md`, etc. Use the first available number.

Write the stub to `<kb-path>/wiki/<slug>.md` (or `<slug>-N.md` if a collision was resolved).

---

### Step 6: Update Wiki Index Files

**`wiki/_index.md`** — append one row:

```
| <slug> | <title> | <tag1>, <tag2> | stub |
```

**`wiki/_tags.md`** — for each tag assigned:
- If the tag row already exists, append `<slug>` to its Articles column (comma-separated)
- If the tag row does not exist, add a new row: `| <tag> | <slug> |`

---

### Step 7: Update Search Index

Run the indexer to make the new content discoverable via `/kb search`:

```bash
KB_PATH=<kb-path> node cli/kb-search.js index
```

If the command fails (e.g. `cli/kb-search.js` not found), skip silently and note it in the report — the content is still saved, just not yet indexed.

---

### Step 8: Report

Print a completion summary:

```
=== KB Ingestion Complete ===

Source:     <original URL, path, or "session">
Type:       <category>
Raw file:   <raw-path>
Wiki stub:  <kb-path>/wiki/<slug>.md
Tags:       <tag1>, <tag2>, ...

Summary:
<one-paragraph summary>

Next steps:
- Run /kb compile to synthesise wiki articles from raw sources
- Run /kb search <topic> to find related content
```

If any step failed (fetch error, write error, index error), report it here with the error message and suggest a manual fix.
