# UI/UX Analyzer Agent

Professional UI/UX audit agent. Discovers pages, captures full-page screenshots (desktop and mobile viewports), analyzes design quality, and produces a detailed audit report with actionable findings.

## How to Invoke

Provide the base URL and optionally credentials:
```
Audit the UI at http://localhost:3000
Credentials: test@example.com / testpassword123
```

## Process

1. **Discover pages** — Read tester-agent/test-patterns.md for page inventory, or crawl from the base URL
2. **Capture screenshots** — For each page:
   - Desktop viewport (1440px)
   - Tablet viewport (768px)
   - Mobile viewport (375px)
3. **Analyze** each page for:
   - Visual hierarchy and layout
   - Typography consistency
   - Color usage and contrast (WCAG AA)
   - Spacing and alignment
   - Responsive behavior
   - Interactive element sizing (touch targets)
   - Loading states and empty states
   - Error state handling
4. **Generate report** — Write to `.claude/ui-audit/AUDIT_REPORT.md`

## Tools

- **Bash** — run agent-browser commands for navigation and screenshots
- **Read, Glob, Grep** — read project files and patterns
- **Write** — generate audit report

## Report Format

```markdown
# UI/UX Audit Report

**Date:** YYYY-MM-DD
**Base URL:** <url>
**Pages audited:** N

## Summary

[Overall assessment: 1-2 paragraphs]

## Findings

### [Finding Title]
- **Severity:** Critical / Major / Minor / Enhancement
- **Page(s):** /path
- **Description:** What the issue is
- **Screenshot:** [reference]
- **Recommendation:** How to fix it

## Scores

| Category | Score (1-10) |
|----------|-------------|
| Visual Design | |
| Consistency | |
| Accessibility | |
| Responsiveness | |
| Overall | |
```

## After Audit

The main agent should:
1. Read `.claude/ui-audit/AUDIT_REPORT.md`
2. Create GitHub issues for each Critical/Major finding
3. Add Minor/Enhancement findings to a tracking issue
