---
name: prd
description: Use when creating a new PRD for a feature — creates a GitHub issue with the PRD content. No local file is created. Can be used with or without a prior brainstorming session.
---

## Before You Begin

Check whether this conversation contains an approved design from a brainstorming session.

> **Is there an approved design in this conversation?**
> - **Yes** → proceed to draft the PRD below
> - **No** → run the inline clarify+grill block below before drafting

### Inline Clarify+Grill (when no prior design exists)

Ask the user these questions **one at a time** — do not ask multiple at once:

1. "What is the goal of this feature? (one sentence: what it does and why it matters for the game)"
2. "What are the key requirements? (list the must-haves)"
3. "What are the acceptance criteria? (how do you know it's done?)"
4. "What is explicitly out of scope?"
5. "Are there any GB hardware constraints to consider? (OAM budget, WRAM, VRAM, banking, SDCC limitations)"

After collecting answers, do a **grill-me pass** inline — ask 2-3 probing questions one at a time to surface assumptions, edge cases, or risks. Examples:
- "What happens when [edge case]?"
- "Is [constraint] a hard requirement or a nice-to-have?"
- "Have you considered [alternative approach]?"

Once all questions are resolved, proceed to draft the PRD.

---

Create a new PRD as a GitHub issue.

## Steps

1. **Draft the PRD content** from the brainstorming session or inline clarify+grill. Use this structure:

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
<!-- Technical context: budget numbers, known constraints, bank assignments, open questions -->
```

   **Required in Notes:** include any relevant technical context gathered during design — budget numbers (OAM slots used, WRAM bytes, VRAM tiles), known constraints, bank assignments, and specific files impacted when known. This ensures subsequent sessions start informed.

2. **Create a GitHub issue** with the full PRD content as the body:
   ```sh
   gh issue create --title "feat: <feature name>" --body "<PRD content>"
   ```
   Capture the issue number from the URL in the output.

3. Report the issue URL to the user.

## Updating an Existing PRD

When updating a PRD (e.g., after a new brainstorming session or scope change):

- **Always use `gh issue edit`** to rewrite the issue body directly — never add a comment:
  ```sh
  gh issue edit <N> --repo MatthieuGagne/gmb-nuke-raider --body "<full updated PRD content>"
  ```
- The issue body is the single source of truth — it must always reflect the current design.

## Important

- **No local file is created.** The GitHub issue is the single source of truth for the PRD.
- Do NOT invoke `writing-plans` after this. The implementation plan is written in a separate session when the user is ready to build.
