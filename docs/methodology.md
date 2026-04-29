# PIV+E Methodology

A tool-agnostic methodology for reliable AI-assisted software development.

## The Problem

AI coding assistants are powerful but unpredictable. They write code that looks right but subtly isn't. They lose context. They make the same mistakes repeatedly. The solution isn't a better AI — it's a better system around the AI.

## The PIV+E Loop

```
PLAN -> IMPLEMENT -> VALIDATE -> EVOLVE
  ^                               |
  +-------------------------------+
        System gets smarter
```

### Plan (Human decides, AI structures)

The human owns what gets built. The AI helps structure the thinking.

- **Brainstorm** the idea — explore alternatives, constraints, tradeoffs
- **Write a spec** (PRD for projects, plan for features)
- **Decompose** into implementable units (GitHub issues)

The key output is a plan document that passes the "no prior knowledge test."

### Implement (AI executes, guided by plan)

The AI does the heavy lifting, constrained by the plan.

- **Test-Driven Development** — write the test first, then make it pass
- **Follow the plan** — don't improvise, don't add features, don't refactor unrelated code
- **Use specialists** — architecture agents, design skills, framework-specific tools
- **Commit frequently** — small, atomic commits after each task

### Validate (Human + AI verify together)

Both human and AI verify the work.

- **Automated checks** — lint, type-check, test suite (AI runs these)
- **Visual verification** — browser/mobile testing agents (AI runs these)
- **Code review** — review agents flag issues (AI runs, human decides)
- **Human review** — the final authority (human approves the PR)

### Evolve (System learns from each cycle)

The system improves after every cycle.

- **Update rules** — new patterns become rules, mistakes become warnings
- **Update knowledge base** — architecture agent learns new modules/endpoints
- **Update test patterns** — new pages/screens get added to test inventories
- **Record decisions** — why things were done this way

## Context Management

- **Plans are artifacts** — they survive session boundaries
- **Context resets are a feature** — start fresh for implementation after heavy planning
- **Progressive disclosure** — load information as needed, not all at once
- **Knowledge bases** — structured information that agents can query

## Discipline Scaling

| Complexity | Ceremony Level |
|-----------|---------------|
| XL (new module) | Full PIV+E with brainstorming, PRD, parallel agents |
| L (new feature) | Plan + TDD + testing agents |
| M (single task) | Quick plan + implement + verify |
| S (tweak) | Just do it + verify |
| Bug | Debug + fix + verify |

## Principles

1. Context is precious — manage it deliberately
2. Plans are artifacts — they survive session boundaries
3. Discipline scales with complexity
4. The system self-improves — every mistake becomes a rule
5. Human stays in control — AI assists, human decides
