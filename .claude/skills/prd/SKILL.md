---
name: prd
description: Use when creating a new PRD for a feature — creates a GitHub issue with the PRD content. No local file is created. Can be used with or without a prior brainstorming session.
---

## Before You Begin

The grill step is user-invoked: `grill-with-docs` carries `disable-model-invocation`, so ask the user to run `/grill-with-docs` — it surfaces requirements, acceptance criteria, scope, and GB hardware constraints. Once the grilling is satisfied (or the user skips it), proceed to drafting.

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

   **Write it plain:** short sentences, active voice, simple tense, concrete verbs, and the terms
   `CONTEXT.md` defines (`docs/dev-workflow.md` §10). A PRD is a bound surface — rewriting it after
   it is filed costs an edit and a notification.

2. **Decide which repo the PRD belongs to.** Per `CLAUDE.md`'s **Routing.** rule, a PRD is filed
   in the repo whose tracked files it changes. List the files the implementation will touch:

   - all under this repo → file here, no `-R` flag needed;
   - all under the Garage tool → file with `-R MatthieuGagne/nuke-raiders-garage`;
   - **both** → stop and write **two** PRDs, one per repo, each scoped to its own files and
     cross-linked to the other in its body. Never file one PRD whose implementation edits two
     repos.

   The chosen repo is fixed for the life of the issue. Record it — every later `gh` command in
   these steps needs it, and `## Updating an Existing PRD` below needs it too.

3. **Create a GitHub issue** with the full PRD content as the body, labeled `prd`:
   ```sh
   # same repo:
   gh issue create --title "feat: <feature name>" --label prd --body "<PRD content>"
   # Garage:
   gh issue create -R MatthieuGagne/nuke-raiders-garage --title "feat: <feature name>" --label prd --body "<PRD content>"
   ```
   Capture the issue number and URL from the output.

4. **Add the issue to the "Nuke Raider — Documents" board with `Type = PRD` and
   `Status = Todo`** — run the four-command sequence in `references/board-wiring.md` with those
   two values. A factory run moves that `Status` to `In Progress` when it starts
   (`factory_publish.py --run-start`) and back to `Todo` if the run fails.

5. **If this PRD refines an epic, wire it as a native sub-issue.** Per `CLAUDE.md`'s
   **Sub-issues.** rule, a body-text `Refines #<epic>` line does not populate the board's
   `Parent issue` field — only native wiring does, and the Epics view groups on it. The API
   takes the child's numeric REST `id` — not its `node_id` and not its issue number:

   ```sh
   child_id=$(gh api repos/<owner>/<child repo>/issues/<new PRD number> --jq .id)
   gh api -X POST repos/<owner>/<epic repo>/issues/<epic number>/sub_issues \
     -F sub_issue_id=$child_id
   ```

   The child id is read from the **PRD's own** repo; the POST goes to the **epic's** repo — the
   two can differ. Wiring works cross-repo under one owner, so a Garage PRD may be wired to a
   game-repo epic. Verify by running the same summary command **twice** — once before the POST
   and once after — and confirming the total rose by one:

   ```sh
   gh api repos/<owner>/<epic repo>/issues/<epic number> --jq .sub_issues_summary.total
   ```

   A count alone cannot catch a child id resolved from the wrong repo, so also confirm the new
   PRD's own number appears in the epic's sub-issue list:

   ```sh
   gh api repos/<owner>/<epic repo>/issues/<epic number>/sub_issues --jq '.[].number'
   ```

   If the PRD refines no epic, skip this step.

6. Report the issue URL to the user.

## Updating an Existing PRD

When updating a PRD (e.g., after a new brainstorming session or scope change):

- **Always use `gh issue edit`** to rewrite the issue body directly — never add a comment:
  ```sh
  # same repo:
  gh issue edit <N> --repo MatthieuGagne/gmb-nuke-raider --body "<full updated PRD content>"
  # Garage:
  gh issue edit <N> --repo MatthieuGagne/nuke-raiders-garage --body "<full updated PRD content>"
  ```
  Use the repo chosen at step 2 — a PRD never moves repos.
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
