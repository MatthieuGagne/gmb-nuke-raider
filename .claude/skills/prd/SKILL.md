---
name: prd
description: Use when creating a new PRD for a feature — creates a GitHub issue with the PRD content. No local file is created. Requires a completed brainstorming session; if no approved design exists in the conversation, invoke the brainstorming skill first.
---

## Before You Begin

Check whether this conversation contains an approved design from a brainstorming session.

> **Is there an approved design in this conversation?**
> - **Yes** → proceed to draft the PRD below
> - **No** → invoke `brainstorming` first (`Skill` tool, `skill: "brainstorming"`); return here only after the user has approved a design

This gate fires only when starting cold (no prior design). If brainstorming was already completed in this session, skip it.

Create a new PRD as a GitHub issue.

## Steps

1. **Draft the PRD content** from the brainstorming session. Use this structure:

```
## Goal
One sentence: what this feature does and why it matters for the game.

## Requirements
- R1: ...

## Acceptance Criteria
- [ ] AC1: ...

## Out of Scope
- ...

## Files Impacted
- `src/foo.c` — ...

## Notes
<!-- Design decisions, open questions, references -->
```

2. **Create a GitHub issue** with the full PRD content as the body:
   ```sh
   gh issue create --title "feat: <feature name>" --body "<PRD content>"
   ```
   Capture the issue number from the URL in the output.

3. Report the issue URL to the user.

## Important

- **No local file is created.** The GitHub issue is the single source of truth for the PRD.
- Do NOT invoke `writing-plans` after this. The implementation plan is written in a separate session when the user is ready to build.
