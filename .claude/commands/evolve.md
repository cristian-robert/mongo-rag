# /evolve — Self-Improvement

Updates the framework's rules, knowledge base, and patterns from what was learned in this session. This is what makes the system get smarter over time.

## Philosophy

"Every bug from the AI coding assistant isn't just something to fix — it's an opportunity to address the root cause in your system."

## Process

### Step 1: Reflect on Session

Review what happened in this session:
1. `git log --oneline main..HEAD` — what was built
2. Were there any:
   - Bugs that took multiple attempts to fix?
   - Patterns the AI got wrong repeatedly?
   - Missing context that caused mistakes?
   - New conventions established?
   - Architecture decisions made?

### Step 2: Capture Learnings (KB-first)

Every session learning — even "update CLAUDE.md" style — starts in the wiki:
1. For each learning, create `<kb-path>/raw/sessions/YYYY-MM-DD-<topic>.md` (raw notes)
2. Create stub wiki article (type: session-learning) in `<kb-path>/wiki/`
3. Update `raw/_manifest.md` (status: pending) and `wiki/_index.md`

### Step 2.5: Token-Budget Check

For every file in `.claude/rules/` and `CLAUDE.md`:
- If file exceeds 200 lines: extract overflow into a reference file (`.claude/references/<domain>-detail.md`) or into the wiki
- Replace extracted content in the rule with a pointer in the `## References` block
- Target after extraction: rule files <150 lines, CLAUDE.md <300 lines

### Step 3: Update Architect Knowledge Base

**Architect Knowledge Base** — If structural changes were made:
1. Dispatch architect-agent with RECORD query
2. Agent verifies changes exist in codebase
3. Agent updates relevant domain files in modules/ and frontend/
4. Agent updates index.md if new domains were added

After architect-KB updates, if wiki stubs from Step 2 have accumulated, suggest: "Run `/kb compile` to expand session learnings into full articles with cross-links." Then rebuild the KB indexes (this single command atomically rebuilds both `_search/index.json` and `_search/lean-index.json` — `/prime` reads the lean one, `/kb search` reads the TF-IDF one, so they must stay in lockstep):

```bash
KB_PATH=<kb-path> node cli/kb-search.js index
```

### Step 4: Update Rules (pointers only)

Rules get NO new prose. For each new convention:
1. Write the detail to the wiki (or the paired `*-detail.md` reference)
2. Add a single bullet in the rule's Conventions block OR a new entry in the References block
3. If a rule has no place for the pointer, create the paired detail file first

### Step 5: Update CLAUDE.md (pointers only)

Same policy — detail goes to wiki, CLAUDE.md only references.

Invoke `revise-claude-md` skill with explicit instruction: "pointer updates only; reject content additions over 3 lines."

**Post-processing required:** The `revise-claude-md` skill may not honor the "pointer updates only" constraint automatically. After the skill returns, diff its output against the prior CLAUDE.md and reject any addition that exceeds 3 lines — move the rejected detail into the wiki (or a `.claude/references/*-detail.md` file) and leave only a pointer in CLAUDE.md.

### Step 6: Update Code Patterns

If the /execute phase revealed patterns the AI should follow:
- Add to .claude/references/code-patterns.md
- Include real code examples from the current codebase
- Note common pitfalls with before/after examples

### Step 7: Health Report

Report:
- Learnings captured: N (raw + stubs)
- Rule-file overflow extractions: N (with before/after line counts)
- CLAUDE.md before/after line count
- Pending stubs awaiting /kb compile

Commit all updates:
```bash
git add CLAUDE.md .claude/
git commit -m "chore: evolve framework — update rules and knowledge base"
```
