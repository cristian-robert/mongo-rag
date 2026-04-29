# /kb search — Knowledge Base Search

Search the wiki for articles matching a query. Supports optional filters for article type and tags.

## Arguments

- `$ARGUMENTS` — search query, optionally followed by `--type=X` and/or `--tag=X`

## Process

### Step 1: Detect KB Path

Read `CLAUDE.md` in the project root. Look for a `## Knowledge Base` section with a `Path:` line.

- If found: use that path as `<kb-path>`
- If not found: default to `.obsidian`

### Step 2: Run Search

Parse `$ARGUMENTS` to extract:
- Query text: everything before any `--` flag
- `--type=X`: filter by article type (e.g., `guide`, `reference`, `comparison`, `concept`)
- `--tag=X`: filter by tag

Run the search:

```bash
KB_PATH=<kb-path> node cli/kb-search.js search "<query>" [--type=X] [--tag=X]
```

The output is a JSON array. Each item has:
- `file` — relative path (e.g., `wiki/my-article.md`)
- `title` — article title
- `type` — article type
- `tags` — array of tags
- `score` — relevance score
- `excerpt` — first ~200 characters of body

### Step 3: Handle No Results

If the JSON array is empty:
```
No articles found for: "<query>"

The wiki may not have articles on this topic yet.
To add content: /kb ingest <url-or-file>
To ask a question and auto-file an answer: /kb ask <question>
```

Stop here.

### Step 4: Read Top 3 Articles

Take the top 3 results (highest score). For each, use the Read tool to load the full file content from `<kb-path>/<file>`.

### Step 5: Present Results

Display results in this format:

```
=== KB Search: "<query>" ===

Found N article(s)

─── Result 1 ────────────────────────────────
Title:  [title]
Type:   [type]   Tags: [tag1, tag2, ...]
Score:  [score]
File:   [file path]

[Full article content]

─── Result 2 ────────────────────────────────
[same structure]

─── Result 3 ────────────────────────────────
[same structure]

─── More results (not loaded) ───────────────
[list remaining titles with their file paths, one per line]

═════════════════════════════════════════════
Actions:
  /kb ask <question>    — synthesize an answer + file it in the wiki
  /kb ingest <source>   — add new content from a URL or file
```

If fewer than 4 total results, omit the "More results" section.
