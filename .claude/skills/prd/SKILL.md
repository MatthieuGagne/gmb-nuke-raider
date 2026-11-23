---
name: prd
description: Use when creating a new PRD for a feature — creates a GitHub issue with the PRD content. No local file is created. Can be used with or without a prior brainstorming session.
---

# PRD — Nuke Raider

Read `~/.claude/skills/base-prd/SKILL.md` first: it owns the PRD structure, the filing and update commands, and
the rules about local files and `writing-plans`. Apply the project rules below on top of it.

## Before You Begin

**Read [`docs/document-conventions.md`](../../../docs/document-conventions.md) first.** It is the
authoritative source for issue routing between the two repositories, native sub-issue wiring, the
ADR key/lifecycle/citation rules, the project `Type` table and the `Idea` swimlane. It is no
longer auto-loaded into every session, so this skill is responsible for pulling it in.

The grill step is user-invoked: `grill-with-docs` carries `disable-model-invocation`, so ask the
user to run `/grill-with-docs` — it surfaces requirements, acceptance criteria, scope, and GB
hardware constraints. Once the grilling is satisfied (or the user skips it), proceed to drafting.

## Project content

`Files Impacted` lists C sources:

```
- `src/foo.c` — ...
```

`Notes` must cover, when relevant: budget numbers (OAM slots used, WRAM bytes, VRAM tiles), known
constraints, and bank assignments. Use the terms `CONTEXT.md` defines (`docs/dev-workflow.md` §10).

## Filing

1. **Decide which repo the PRD belongs to** — per the **Routing.** rule in
   `docs/document-conventions.md`, list the files the implementation will touch: all here → file
   here; all Garage → `-R MatthieuGagne/nuke-raiders-garage`; **both** → write **two** PRDs (one
   per repo, cross-linked), never one PRD editing two repos.

   The chosen repo is fixed for the life of the issue — record it; every later `gh` command needs it.

2. **Create the issue** labeled `prd`:

   ```sh
   # same repo:
   gh issue create --title "feat: <feature name>" --label prd --body-file <file>
   # Garage:
   gh issue create -R MatthieuGagne/nuke-raiders-garage --title "feat: <feature name>" --label prd --body-file <file>
   ```

3. **Add the issue to the "Nuke Raider — Documents" board with `Type = PRD` and `Status = Todo`** —
   run the four-command sequence in `references/board-wiring.md` with those two values. A factory
   run moves that `Status` to `In Progress` when it starts (`factory_publish.py --run-start`) and
   back to `Todo` if the run fails.

4. **If this PRD refines an epic, wire it as a native sub-issue.** A body-text `Refines #<epic>`
   line is not enough — see `references/subissue-wiring.md` for the exact commands and
   verification steps. If the PRD refines no epic, skip this step.

Updates use the repo chosen at step 1:

```sh
gh issue edit <N> --repo MatthieuGagne/gmb-nuke-raider --body-file <file>
gh issue edit <N> --repo MatthieuGagne/nuke-raiders-garage --body-file <file>
```

## Factory-ready

A PRD is only runnable by `/factory` if it passes `python tools/spec_lint.py --issue <N>` — all
five sections (`Goal`, `Requirements`, `Acceptance Criteria`, `Out of Scope`, `Files Impacted`)
present and non-empty, at least one `- R<n>:` requirement, at least one `- [ ]` acceptance
criterion, and at least one `- ` bullet under Files Impacted. Run the linter before reporting the
issue URL.

**Files Impacted decides the route.** The linter classifies a spec doc-only when *every* listed
path is `*.md`, `*.txt`, `*.json` (except `bank-manifest.json`), or lives under `.claude/skills/`
or `.claude/agents/`. A single stray path — including one annotated "no change needed" — sends the
whole spec down the full code workflow. List only files the implementation will actually touch.
