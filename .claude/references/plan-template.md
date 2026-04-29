# Implementation Plan Template

Use this structure when generating plans via `/plan-feature`.

---

# [Feature Name] Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** [One sentence]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies]

**Confidence Score:** [1-10] for one-pass implementation success

**Context Reset:** [Recommended / Not needed] between planning and implementation

---

## Mandatory Reading

Before implementing, read these files to understand the codebase context:

| File | Lines | What to Learn |
|------|-------|--------------|
| `path/to/file` | 1-50 | Pattern for X |

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `path/to/new/file` | Description |

### Modified Files
| File | Changes |
|------|---------|
| `path/to/existing` | What changes and why |

## Dependencies

Install before starting:
```bash
<install commands if any>
```

## Tasks

### Task 1: [Component Name]

**Files:**
- Create: `exact/path/to/file`
- Modify: `exact/path/to/existing:lines`
- Test: `tests/exact/path/to/test`

- [ ] Step 1: Write the failing test
  ```language
  <actual test code>
  ```

- [ ] Step 2: Run test to verify it fails
  Run: `<exact command>`
  Expected: FAIL with "<message>"

- [ ] Step 3: Write minimal implementation
  ```language
  <actual implementation code>
  ```

- [ ] Step 4: Run test to verify it passes
  Run: `<exact command>`
  Expected: PASS

- [ ] Step 5: Commit
  ```bash
  git add <files>
  git commit -m "<conventional commit message>"
  ```

### Task 2: ...

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## GOTCHA Warnings

- **GOTCHA:** [Specific pitfall and how to avoid it]
