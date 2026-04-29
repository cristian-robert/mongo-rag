# Config Merge Strategy

Canonical reference for merging project-specific configuration with framework files after an install, update, or manual framework upgrade. Consumed by `/merge-configs` and `/start` Step 0.

## File Categories

| Category | Files | Strategy |
|----------|-------|----------|
| CLAUDE.md | Project root | Section-preserving merge (preserve user sections, update framework sections) |
| Rules | `.claude/rules/*.md` | Append user additions; dedupe |
| Commands | `.claude/commands/*.md` | Diff vs previous framework version; user-edited → prompt; unchanged → discard backup |
| References — project-specific | `.claude/references/code-patterns.md` | Always restore from backup |
| References — templates | `.claude/references/*.md` (other) | Keep framework version |
| Agents — project KB | `.claude/agents/architect-agent/**` | Always restore from backup |
| Agents — test patterns | `.claude/agents/tester-agent/**`, `mobile-tester-agent/**` | Always restore from backup |
| KB content | `<kb-path>/**` | Always restore from backup |
| Hooks | `.claude/hooks/*.sh` | User-edited → prompt; unchanged → discard |
| Settings | `.claude/settings.local.json` | **Deep-merge** via `cli/merge-settings.js`. Hook arrays union by `(matcher, type, command)` tuple — user entries preserved, framework entries added if missing, exact duplicates deduped. `permissions.allow` / `deny` arrays union-sorted-deduped. Other top-level keys: user value wins on scalar conflicts. Run `--dry-run` first to show the plan, then `--apply` on approval. |

## Process

For each `.backup` file found:
1. Categorize using the table above
2. Compute merge plan for the category
3. Present plan to user; await approval
4. Apply merge
5. Delete `.backup`

## Detection sources

- `.claude/.init-meta.json` — presence indicates post-init merge pending
- User-invoked via `/merge-configs` — scans for any `.backup` files plus optionally a user-supplied directory

## Notes on Settings

The `.claude/settings.local.json` deep-merge is implemented in `cli/merge-settings.js`. Specifics:

- **Hooks**: union by `(matcher, type, command)` tuple. User's existing entries are preserved in their original order; framework entries are appended only if not already present. Same matcher with a different command means the user customised one and the framework added a separate hook on the same trigger — both run.
- **Permissions**: `allow` and `deny` arrays are union-sorted-deduped.
- **Other top-level keys** (e.g. `enableAllProjectMcpServers`): user value wins on scalar conflicts. Nested objects merge recursively with the same rule.

Always run with `--dry-run` first to surface the merge plan, then `--apply` on user approval. The script writes atomically (tmp file + rename), so a failed run cannot leave settings.local.json in a corrupt state.
