---
name: prd
description: Use when creating a new PRD for a feature — creates a GitHub issue with the PRD content. No local file is created. Can be used with or without a prior brainstorming session.
---

## Before You Begin

Always invoke the `grill-with-docs` skill — it will surface requirements, acceptance criteria, scope, and GB hardware constraints. Once the grilling is satisfied, proceed to drafting.

---

Create a new PRD as a GitHub issue.

## Steps

1. **Draft the PRD content** from the brainstorming session or the user's description. Use this structure:

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

2. **Run an ASD-STE100 pass over the drafted body.** Do this before `spec_lint.py` and before you
   create the issue — a PRD is a bound surface (#517 R3), and rewriting it after it is filed costs
   an edit and a notification.

   Apply the `simplified-technical-english` skill to the draft. Then write the drafted body to a
   scratch file and lint that file:

   ```bash
   python tools/ste_lint.py /tmp/prd-draft.md
   ```

   Or, once the issue exists and you are revising it:

   ```bash
   python tools/ste_lint.py --issue <N>
   ```

   An ASD-STE100 finding reports only — fix what is worth fixing and move on. A banned-synonym hit
   exits 1 and must be fixed: `CONTEXT.md` outranks ASD-STE100 on word choice.

3. **Create a GitHub issue** with the full PRD content as the body, labeled `prd`:
   ```sh
   gh issue create --title "feat: <feature name>" --label prd --body "<PRD content>"
   ```
   Capture the issue number and URL from the output.

4. **Add the issue to the "Nuke Raider — Documents" project, then set `Type = PRD` and
   `Status = Todo`.** These are four commands, not a convention — a PRD that is not on the board
   is invisible to the board, and one with no `Status` is invisible to anyone reading the board
   for what is in flight. Resolve **every field id and option id by name**; option ids are
   regenerated whenever the field's option set is edited, and `tools/factory_publish.py` already
   resolves `Log`, `Todo`, `In Progress` and `Done` this way. The project id
   (`PVT_kwHOAv4a5M4BepB5`) is a stable constant and is written literally, as
   `factory_publish.py` also does.

   ```sh
   # a. add the issue to the project, capturing the new item id
   gh project item-add 3 --owner MatthieuGagne --url <issue URL> --format json
   ```

   ```sh
   # b. resolve the Type field id + its PRD option id, and the Status field id
   #    + its Todo option id — one call, both fields
   gh project field-list 3 --owner MatthieuGagne --format json
   ```

   ```sh
   # c. set Type = PRD on the item created in (a)
   gh project item-edit --id <item id from a> --project-id PVT_kwHOAv4a5M4BepB5 \
     --field-id <Type field id from b> --single-select-option-id <PRD option id from b>
   ```

   ```sh
   # d. set Status = Todo on the same item
   gh project item-edit --id <item id from a> --project-id PVT_kwHOAv4a5M4BepB5 \
     --field-id <Status field id from b> --single-select-option-id <Todo option id from b>
   ```

   A factory run moves that `Status` to `In Progress` when it starts
   (`factory_publish.py --run-start`) and back to `Todo` if the run fails.

5. Report the issue URL to the user.

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
- **Factory-ready:** a PRD is only runnable by `/factory` if it passes
  `python tools/spec_lint.py --issue <N>` — all five sections (`Goal`, `Requirements`,
  `Acceptance Criteria`, `Out of Scope`, `Files Impacted`) present and non-empty, at least one
  `- R<n>:` requirement, at least one `- [ ]` acceptance criterion, and at least one
  `- ` bullet under Files Impacted. Run the linter before reporting the issue URL.
- **Files Impacted decides the route.** The linter classifies a spec doc-only when *every*
  listed path is `*.md`, `*.txt`, `*.json` (except `bank-manifest.json`), or lives under
  `.claude/skills/` or `.claude/agents/`. A single stray path — including one annotated "no
  change needed" — sends the whole spec down the full code workflow. List only files the
  implementation will actually touch.
