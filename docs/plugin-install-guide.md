# Plugin and Skill Install Guide

## Required Plugins

### Core Workflow (Must Have)
```bash
claude plugin install superpowers
claude plugin install feature-dev
claude plugin install code-review
claude plugin install commit-commands
claude plugin install claude-md-management
claude plugin install security-guidance
claude plugin install skill-creator
```

### Framework Support (Recommended)
```bash
claude plugin install firecrawl
claude plugin install frontend-design
claude plugin install claude-code-setup
claude plugin install agent-sdk-dev
```

### Stack-Specific (Install What You Use)
```bash
# For any project using frameworks/libraries
claude plugin install context7

# For Supabase projects
claude plugin install supabase

# For TypeScript projects
claude plugin install typescript-lsp

# For Expo/React Native projects
claude plugin install expo-app-design --marketplace expo-plugins
```

## Global Skills

Skills are installed separately from plugins. Key categories:

**Web and Frontend:** agent-browser, frontend-design, frontend-aesthetics, ui-ux-pro-max, shadcn-ui, nextjs-app-router-patterns, vercel-react-best-practices, web-design-guidelines

**Design Artifacts (HTML prototypes, slide decks, motion, infographics):**

```bash
npx skills add alchaincyf/huashu-design
```

`huashu-design` is the framework's recommended path for **design artifacts** (clickable HTML prototypes, editable PPTX decks, MP4/GIF motion, print-grade infographics) as distinct from production app code. It's agent-agnostic, ships its own Core Asset Protocol, and pairs with the project-local `/brand-extract` skill (`.claude/skills/brand-extract/`) so brand assets are extracted once per project instead of asked for every run. License is free for personal/research use; commercial/client work requires authorization from the author. See `.claude/rules/frontend.md` for the design-skill gate that routes between huashu-design and the production-UI skills.

**Backend and Database:** fastapi-python, mongodb, mongodb-development, supabase-postgres-best-practices, stripe-best-practices

**Testing and Security:** qa-test-planner, security-audit, web-security-testing, pentest-expert

**Research and Content:** research, search, crawl, extract, multi-ai-research, tavily-best-practices

**Mobile:** All expo-app-design sub-skills (building-native-ui, native-data-fetching, expo-tailwind-setup, expo-dev-client, expo-api-routes, use-dom, expo-ui-swift-ui, expo-ui-jetpack-compose)

## MCP Servers

Configure per project as needed:

| Server | Purpose |
|--------|---------|
| context7 | Framework/library documentation |
| shadcn | shadcn/ui component search |
| supabase | Database operations |
| mobile-mcp | Mobile simulator testing |

## Checking Installation

Run `/setup` at any time to see what's installed and what's missing.
