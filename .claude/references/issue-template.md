# GitHub Issue Template

Used by `/plan-project` and `/plan-feature` to create structured issues.

---

## Issue Structure

### Title Format
`[type]: brief description`

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`

### Body Template

```markdown
## Description

[1-2 sentences: what needs to be built/fixed and why]

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Technical Notes

- Key files to modify: `path/to/file`
- Pattern to follow: [reference existing similar implementation]
- Dependencies: [other issues that must be completed first]

## Size Estimate

[S / M / L / XL]

- **S** (< 1 hour): Config change, copy update, simple fix
- **M** (1-4 hours): Single component/endpoint, moderate logic
- **L** (4-16 hours): Multi-file feature, new module
- **XL** (> 16 hours): Consider breaking into smaller issues
```

### Labels

Apply these labels via `gh issue create --label`:

| Label | When |
|-------|------|
| `feat` | New functionality |
| `fix` | Bug fix |
| `refactor` | Code improvement, no behavior change |
| `docs` | Documentation only |
| `priority:high` | Blocks other work or critical path |
| `priority:medium` | Important but not blocking |
| `priority:low` | Nice to have |
| `size:S/M/L/XL` | Estimated effort |
