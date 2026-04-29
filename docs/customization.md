# Customization Guide

## Adding Custom Rules

1. Copy `.claude/rules/_template.md` to `.claude/rules/your-domain.md`
2. Set the `globs` pattern to match your file paths
3. Add your conventions and skill chains
4. Rules auto-load when editing matching files

## Adding Custom Agents

1. Copy `.claude/agents/_template/AGENT.md` to `.claude/agents/your-agent/AGENT.md`
2. Define query types, tools, and response format
3. Add knowledge base files as needed
4. Reference the agent from your commands or rules

## Customizing Commands

Commands are markdown files in `.claude/commands/`. Edit existing commands or add new ones. Commands are invoked as `/command-name` in Claude Code.

## Customizing Hooks

Hooks are shell scripts in `.claude/hooks/`. Edit existing hooks or add new ones. Make sure hooks are executable (`chmod +x`).

## Overriding Rules per Project

Each project gets its own `.claude/` folder. Customize CLAUDE.md, rules, and agent knowledge bases per project. The framework's commands stay the same.

## Configuring the Knowledge Base

The framework includes an optional project knowledge base (Obsidian-compatible) that gives the agent persistent project understanding across sessions.

### Enable

Add to your project's `CLAUDE.md`:

```markdown
## Knowledge Base

Path: .obsidian/
```

### Custom Path

Use any folder name:

```markdown
## Knowledge Base

Path: knowledge/
```

**Note:** The framework's `.gitignore` only covers Obsidian config files under `.obsidian/`. If you use a custom path and open it as an Obsidian vault, add these entries to your `.gitignore` (replacing `knowledge/` with your path):

```
knowledge/app.json
knowledge/appearance.json
knowledge/core-plugins.json
knowledge/core-plugins-migration.json
knowledge/workspace.json
knowledge/workspace-mobile.json
knowledge/hotkeys.json
knowledge/plugins/
knowledge/themes/
```

### Disable

Remove the `## Knowledge Base` section from CLAUDE.md. All knowledge operations are skipped — commands work exactly as before.

### What It Does

Pipeline commands automatically read from and write to the knowledge base:
- `/start` creates the structure when starting a new project
- `/prime` loads relevant notes for context before work
- `/create-prd` seeds the knowledge base from the PRD
- `/plan-project` creates feature notes alongside GitHub issues
- `/execute` reads related feature notes before implementing
- `/ship` updates feature notes after completing work

### Obsidian

If you have [Obsidian](https://obsidian.md/) installed, open your project folder as a vault. The `.obsidian/` directory makes it a valid vault. Notes are navigable, linkable, and searchable through Obsidian's UI. Obsidian is not required — the notes are plain markdown.

## Contributing

1. Fork the repository
2. Add your contribution
3. Submit a PR with description, usage, and testing notes
