# /kb ask — Knowledge Base Q&A

Ask a question. The answer is synthesized from existing wiki articles and permanently filed as a new article. Every question improves the KB (Karpathy's "queries add up" principle).

## Arguments

- `$ARGUMENTS` — the question to answer

## Process

### Step 1: Detect KB Path

Read `CLAUDE.md` in the project root. Look for a `## Knowledge Base` section with a `Path:` line.

- If found: use that path as `<kb-path>`
- If not found: default to `.obsidian`

### Step 2: Search for Relevant Articles

Run `/kb search` with the question as the query:

```bash
KB_PATH=<kb-path> node cli/kb-search.js search "<question>"
```

### Step 3: Handle Empty Wiki

If no results are returned:

```
No wiki articles found to answer: "<question>"

The wiki is empty or has no content on this topic.
To add content first: /kb ingest <url-or-file>

Once articles are ingested, re-run: /kb ask <question>
```

Stop here.

### Step 4: Read Top 5 Articles

Take up to the top 5 results (highest score). For each, use the Read tool to load the full file from `<kb-path>/<file>`.

### Step 5: Synthesize Answer

Using the loaded articles as source material, write a comprehensive answer to the question. The answer must:

- Directly address the question
- Cite specific details from the source articles
- Be accurate — do not add information not present in the sources
- Be concise but complete — no padding
- Use markdown formatting (headers, bullets, code blocks) as appropriate

### Step 6: Choose Article Type

Based on the question and answer content, select the best type:

| Type | Use when |
|------|----------|
| `guide` | Question asks "how to" or "how do I" — answer is procedural |
| `comparison` | Question asks "which", "vs", "difference between" — answer compares options |
| `reference` | Question asks "what is", "what are", "list" — answer is reference material |
| `concept` | Question asks "why", "what does X mean" — answer explains a concept |

### Step 7: Generate Article Slug and Frontmatter

Create a slug from the question: lowercase, hyphens for spaces, strip punctuation. Keep it under 60 characters. Examples:
- "How do I set up the KB?" → `how-to-set-up-the-kb`
- "What is the difference between guide and reference?" → `guide-vs-reference-article-types`

Check if `wiki/<slug>.md` already exists. If so, append a numeric suffix: `wiki/<slug>-2.md`, `wiki/<slug>-3.md`, etc. Use the first available number.

Extract 2–4 relevant tags from the answer content.

Compose the frontmatter:

```yaml
---
title: "[The question, rephrased as a declarative title]"
type: [guide|comparison|reference|concept]
tags: [tag1, tag2, ...]
status: active
created: YYYY-MM-DD
sources:
  - [relative path to source article 1]
  - [relative path to source article 2]
---
```

### Step 8: Write the Answer Article

File the article at `<kb-path>/wiki/<slug>.md`.

Article structure:

```markdown
---
[frontmatter]
---

# [Title]

[Synthesized answer — the full, formatted content]

## Sources

- [[source-article-1]] — [one-line description of what it contributed]
- [[source-article-2]] — [one-line description]
```

### Step 9: Add Backlinks to Source Articles

For each source article read in Step 4, append a `## Referenced By` section (or append to an existing one):

```markdown
## Referenced By

- [[<slug>]] — [the question that triggered this reference]
```

Update each source file using the Edit tool.

### Step 10: Update Index and Tag Files

**Update `<kb-path>/wiki/_index.md`:**

If the file does not exist, create it. Add the new article to the appropriate type section:

```markdown
- [[<slug>]] — [title] *(added: YYYY-MM-DD)*
```

**Update `<kb-path>/wiki/_tags.md`:**

If the file does not exist, create it. For each tag in the new article, add or update the tag entry:

```markdown
## [tag]

- [[<slug>]] — [title]
```

### Step 11: Rebuild Search Index

```bash
KB_PATH=<kb-path> node cli/kb-search.js index
```

### Step 12: Display Answer

Present the answer to the user:

```
=== Answer ===

[The synthesized answer, fully formatted]

─────────────────────────────────────────────
Sources consulted:
  [title 1] — [file path]
  [title 2] — [file path]

Answer filed as: wiki/<slug>.md
This answer is now part of your wiki.

Next:
  /kb search <topic>   — explore related articles
  /kb ask <question>   — ask a follow-up question
  /kb ingest <source>  — add more source material
```
