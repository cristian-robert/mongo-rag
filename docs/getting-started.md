# Getting Started

## Quick Start (Existing Project)

1. Copy the `.claude/` folder into your project root
2. Run `/setup` to check what plugins/skills you need
3. Install missing dependencies (commands provided by /setup)
4. Run `/prime` to load your codebase context
5. Run `/start` to begin your first task

## Quick Start (New Project)

1. Copy the `.claude/` folder into your project root
2. Run `/setup` to check dependencies
3. Run `/start` — it will detect a new project and guide you through:
   - `/create-prd` — brainstorm and define what you're building
   - `/plan-project` — create GitHub issues from the PRD
   - Per-issue implementation via the PIV+E loop

## Your First Feature (Walkthrough)

### 1. Start
```
/start
> What are you working on? -> 3. Working on a specific GitHub issue
> Issue number? -> #1
```

### 2. Plan
```
/plan-feature #1
```
Review the plan. Adjust if needed.

### 3. Implement
```
/execute docs/plans/my-feature.md
```

### 4. Validate
```
/validate
```

### 5. Ship
```
/ship
```

### 6. Evolve (after merge)
```
/evolve
```

## Commands Quick Reference

| Command | When to Use |
|---------|------------|
| `/start` | Beginning of any work session |
| `/prime` | Load/reload codebase context |
| `/create-prd` | Planning a new project from scratch |
| `/plan-project` | Breaking a PRD into GitHub issues |
| `/plan-feature` | Planning a specific feature |
| `/execute` | Implementing a plan |
| `/validate` | Verifying work before shipping |
| `/ship` | Committing, pushing, creating PR |
| `/evolve` | Updating the system after completing work |
| `/setup` | Checking framework health |
