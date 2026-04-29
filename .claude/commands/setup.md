# /setup — Framework Health Check

Checks what external plugins, skills, and MCP servers are installed and reports any gaps.

## Process

### Step 1: Check Plugins

Verify each required plugin is installed. Present results as a checklist.

**Core Workflow (required):**

| Plugin | Install Command |
|--------|----------------|
| superpowers | `claude plugin install superpowers` |
| feature-dev | `claude plugin install feature-dev` |
| code-review | `claude plugin install code-review` |
| commit-commands | `claude plugin install commit-commands` |
| claude-md-management | `claude plugin install claude-md-management` |
| security-guidance | `claude plugin install security-guidance` |
| skill-creator | `claude plugin install skill-creator` |

**Framework Support (recommended):**

| Plugin | Install Command |
|--------|----------------|
| firecrawl | `claude plugin install firecrawl` |
| frontend-design | `claude plugin install frontend-design` |
| claude-code-setup | `claude plugin install claude-code-setup` |
| agent-sdk-dev | `claude plugin install agent-sdk-dev` |

**Stack-Specific (install what applies):**

| Plugin | When Needed | Install Command |
|--------|------------|----------------|
| context7 | Any framework/library project | `claude plugin install context7` |
| supabase | Supabase projects | `claude plugin install supabase` |
| typescript-lsp | TypeScript projects | `claude plugin install typescript-lsp` |
| expo-app-design | Expo/React Native projects | `claude plugin install expo-app-design --marketplace expo-plugins` |

### Step 1.5: Check Design-Artifact Skills + Version Drift

Verify external skills used for design artifacts (HTML prototypes, slide decks, motion, infographics):

| Skill | Install Command | Detection |
|-------|----------------|-----------|
| huashu-design | `npx skills add alchaincyf/huashu-design` | Check `~/.claude/skills/huashu-design/SKILL.md` exists |

Required vs. recommended:
- If the project commits design work to `design/` OR has `.design-system/brand-spec.md`, treat huashu-design as **required** and report `[missing]` if absent.
- Otherwise report it as a **recommended** skill the user can install on demand.

**Version-drift check (only if huashu-design is installed):**

1. Read `.claude/.versions.json` → `external_skills.huashu-design.skill_md_sha256`.
2. Compute the installed file's hash:
   ```bash
   shasum -a 256 ~/.claude/skills/huashu-design/SKILL.md | awk '{print $1}'
   ```
3. Compare:
   - **Pin empty** (`""`) → first-run population. Update `.claude/.versions.json` with the computed hash + today's date. Report `[ok] huashu-design — pinned at <short-hash>`.
   - **Hashes match** → report `[ok] huashu-design — pinned at <short-hash>`.
   - **Hashes differ** → report `[warn] huashu-design — drifted from pinned version`. Show both hashes (short form). Tell the operator: "The brand-spec.md schema in `.claude/.versions.json#schema_contract` may have changed. Run `/brand-extract` against a known-good project and confirm it still produces a spec with the expected sections before relying on the design path."
4. **Never auto-update** the pin on drift — only on first-run empty-pin population. The pin is meant to flag drift, not silently accept it.

### Step 2: Check MCP Servers

Verify project-level MCP server configuration if applicable:
- shadcn — for shadcn/ui component projects
- context7 — for documentation lookup
- supabase — for database operations
- mobile-mcp — for mobile testing

### Step 3: Check Framework Files

Verify .claude/ structure is complete:
- commands/ (10 files)
- agents/ (4 agents + template)
- rules/ (6 rules + template)
- references/ (5 templates)
- hooks/ (5 scripts)
- settings.local.json

### Step 4: Report

```
=== Framework Health Check ===

Plugins:
  [check] superpowers
  [check] feature-dev
  [missing] firecrawl — run: claude plugin install firecrawl

MCP Servers:
  [check] context7
  [missing] shadcn — add to .mcp.json if using shadcn/ui

Framework Files:
  [check] .claude/commands/ (10 commands)
  [check] .claude/agents/ (4 agents)
  [check] .claude/rules/ (6 rules)
  [check] .claude/references/ (5 templates)
  [check] .claude/hooks/ (5 hooks)

Status: Ready (install missing items above for full functionality)
```
