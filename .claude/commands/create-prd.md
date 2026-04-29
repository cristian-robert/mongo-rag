# /create-prd — Product Requirements Document Generator

Generate a comprehensive PRD from a product idea. This command ALWAYS starts with brainstorming.

## Arguments

- `$ARGUMENTS` — optional: the product idea in brief (can also be discussed interactively)

## Process

### Phase 1: Brainstorm (MANDATORY)

Invoke the brainstorming skill to explore the idea before writing anything:

1. If `$ARGUMENTS` is provided, use it as the starting point
2. If not, ask: "What are you building? Give me the elevator pitch."
3. Explore through conversation:
   - What problem does this solve?
   - Who is the target user?
   - What are the constraints (timeline, budget, team size, tech preferences)?
   - What does success look like?
   - What's explicitly OUT of scope?
4. Propose 2-3 architectural approaches with tradeoffs
5. Get user's choice before proceeding

### Phase 2: Generate PRD

1. Read `.claude/references/prd-template.md` for the structure
2. Fill in every section based on the brainstorming conversation
3. Be specific — no placeholder text, no "TBD" sections
4. User stories should be concrete and testable
5. Implementation phases should be ordered by dependency and value

### Phase 2.5: Seed Knowledge Base (if configured)

Check CLAUDE.md for a `## Knowledge Base` section with a `Path:` value. If configured:

1. Read `.claude/references/kb-article-template.md` for templates
2. Create the KB structure if it doesn't exist (same as `/start` L0 step)
3. Create `<kb-path>/wiki/project-overview.md` (type: `reference`):
   - Vision from Executive Summary
   - Goals from Goals & Success Criteria
   - Target Users from Target Users section
   - Tech Stack from Technical Architecture
   - Feature Areas listing each epic/feature with wikilinks
4. Create `<kb-path>/wiki/system-design.md` (type: `concept`):
   - Architecture from Technical Architecture and System Diagram sections
5. For each epic or major feature in the PRD, create `<kb-path>/wiki/<feature-name>.md` (type: `feature`):
   - Summary from the epic description
   - GitHub Issues section left empty (populated by `/plan-project`)
   - Key Decisions from brainstorming
   - Related articles linking to project-overview and system-design
6. Update `wiki/_index.md` and `wiki/_tags.md`
7. Run: `KB_PATH=<kb-path> node cli/kb-search.js index`

If no knowledge base configured, skip this phase.

### Phase 3: Review and Save

1. Present the PRD to the user section by section
2. Ask for feedback on each major section
3. Incorporate feedback
4. Save to `docs/plans/PRD.md`

### Phase 4: Next Steps

After saving, tell the user:

> **PRD saved to `docs/plans/PRD.md`.**
>
> Next steps:
> - Run `/plan-project` to decompose this into GitHub milestones and issues
> - Or run `/plan-feature` to start planning a specific feature from the PRD

Commit the PRD and knowledge base files (if created):
```bash
git add docs/plans/PRD.md
# If knowledge base was seeded:
git add <kb-path>/wiki/ <kb-path>/raw/_manifest.md
git commit -m "docs: add PRD and seed project knowledge base"
```
