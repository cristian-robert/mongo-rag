# KB Health Metrics

_Last rebuild: never (run `KB_PATH=.obsidian node cli/kb-search.js index` to build the search index)_

| Metric | Value |
|--------|-------|
| Wiki articles | 7 |
| Stub articles | 0 |
| Raw sources | 0 |
| Tags | — |
| Index size | not built |

## Notes

- Rebuild indexes after ANY edit: `KB_PATH=.obsidian node cli/kb-search.js index` (writes both TF-IDF and lean indexes atomically)
- `/kb compile` triggers an index rebuild automatically
- Health checks: orphan articles (no inbound wikilinks), stub articles never expanded, missing frontmatter fields
