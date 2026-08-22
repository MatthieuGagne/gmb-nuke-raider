# Document conventions (issues, board, ADRs)

Imported by [`CLAUDE.md`](../CLAUDE.md). Applies when filing, typing, or wiring a document
issue — PRDs, epics, bugs, chores, ADRs, run logs, plans, reviews, ideas.

**PRDs & design docs:** GitHub issues only — no local files. Use `/prd` skill, which labels the
issue `prd`, adds it to the "Nuke Raider — Documents" project and sets `Type = PRD` as three
explicit commands. `prd` joins `adr`, `log`, `plan`, `epic` and `idea` as the label set for
document kinds; `bug:`, `fix:`, `docs:` and `chore:` issues are not labeled — their kind is
expressed on the board via `Type`.
Exception: `CONTEXT.md` (repo root) — the glossary is the only design artifact versioned
in-repo, merged via PR. **Decisions are ADRs filed as `adr`-labeled GitHub issues.**

**These conventions govern both repositories** — gmb-nuke-raider and nuke-raiders-garage.
The two repos share one document board: every document issue from either is added to the
"Nuke Raider — Documents" project (project 3), and the label set, the `Type` table, `Status`
and the ADR rules in this file apply identically in both. A convention written here is not
a game-repo convention; it is the convention.

**Routing.** An issue is filed in the repo whose tracked files it changes — the game ROM, its
assets and its tooling in `gmb-nuke-raider`; the Garage desktop tool in `nuke-raiders-garage`.
Work that spans both becomes **one issue per repo**, cross-linked in each body, never one
issue whose implementation edits two repos. Both halves go on the board, because the board is
what makes the pair legible.

**Sub-issues.** An epic's child is wired as a **native** GitHub sub-issue at creation. A
body-text reference such as `Refines #432` is not enough: the board's Epics view groups on the
`Parent issue` field, and only native wiring populates it. The API takes the child's numeric
REST `id` — not its `node_id` and not its issue number — and works cross-repo under one owner.
The id is read from the **child's own** repo; the POST goes to the **epic's** repo:

```sh
child_id=$(gh api repos/MatthieuGagne/gmb-nuke-raider/issues/<child> --jq .id)
gh api -X POST repos/MatthieuGagne/gmb-nuke-raider/issues/<parent>/sub_issues \
  -F sub_issue_id=$child_id
```

**An ADR's key is the issue number of the work item being worked when the decision was taken** —
not a counter, and — except in the no-work-item case below — not the ADR issue's own number. The
work item is the PRD, bug or chore issue being implemented, never a run log, a review, or
another ADR. The title is `ADR <work item#>: <decision title>`.

**One ADR per work item.** Several decisions taken on the same work item share one ADR issue and
appear in its body as `### D1: …`, `### D2: …`. Before filing a second, search issue titles for
`ADR <key>`, closed issues included; if one exists, append the next `Dn` instead.

**Key resolution.** A decision taken while working a **child spec** under an epic keys off the
child spec, never the epic. A decision with **no work item** makes the ADR its own work item, so
its key is its own issue number — the ADR is **self-keyed**, and it is the one case that needs a
retitle after `gh issue create`.

**Lifecycle.** An ADR issue stays **open** while its work item is open and is closed when the
work item closes; a self-keyed ADR closes on acceptance. A decision taken later, against an
already-closed work item, is added by reopening the ADR, appending the next `Dn`, and closing it
again. Every `### Dn` carries its own `Status: Accepted` or
`Status: Superseded by ADR <key> D<n>` — status is per decision, not per issue.

**Citations** are written
`[ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467)` in markdown and
`(ADR 441)` in code comments. To cite one decision rather than the whole ADR, append its `Dn` to
the link text — `ADR 441 D2` — leaving the target unchanged. That target is always the
**ADR's own issue**, never the work item whose number is the key, and a citation never carries a
bare second issue number.

**Project `Type` means kind, and nothing else.** Every document issue is added to the
"Nuke Raider — Documents" project when it is created, with `Type` set from the title prefix:

| Title prefix | Type |
|---|---|
| `feat:` carrying the `epic` label | Epic |
| `feat:` | PRD |
| `fix:` / `bug:` | Bug |
| `docs:` / `chore:` / `refactor:` / `test:` | Chore |
| `ADR <work item#>:` | ADR |
| `run …` | Log |
| `plan: …` | Plan |
| `review:` | Review |
| `idea:` | Idea |

The `Epic` row is first: an epic is `feat:`-titled like any PRD, so the `epic` label — not the
title — is what distinguishes it. A master issue that owns a set of child specs (#432) gets
`--label epic` **in addition to** `prd`, and `Type = Epic` rather than `PRD`. Do not remove
`Epic` from the field.

Provenance is not a `Type` — "this came out of run N" lives in the issue body. `Log` and `Plan`
typing are both owned end-to-end by `tools/factory_publish.py` ([ADR 472](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/475); `Plan` added by #514); `PRD` by the `/prd` skill;
`ADR` by the `grill-with-docs` overlay; `Epic` by hand.

One documented exception to the table: #465 is `docs:`-titled but stays `PRD`.

**`Idea` is the uncommitted end of the board.** An `idea:` issue is a proposal nobody has
committed to yet: free-form body, no acceptance criteria, `Status = Todo`, label `idea`. It is
never worked directly — no branch, no worktree, no factory run — and `/factory` cannot run one
regardless, because GATE's `spec_lint` rejects a spec with no acceptance criteria. Promotion
files a **new** PRD issue linking back (`Refines #N`); the idea is then closed with a comment
naming the PRD, never converted in place — one issue keeps one kind, and closing preserves where
the PRD came from. Rejection closes it as *not planned* with a one-line reason. An idea left open
is an idea still unclaimed; nothing else may sit in that swimlane.

**Every document issue added to the board gets an explicit `Status` at creation** — `Type` says
what a document is, `Status` says where it is. `Todo` for anything a human or `/prd` files;
`In Progress` for a factory run issue, which is running by the time it exists. A factory run
moves its spec to `In Progress` at run start and back to `Todo` if the run fails, and moves its
own run issue to `Done` at terminal. Resolve the field and option ids by name from
`gh project field-list` — option ids are regenerated whenever the option set is edited.

**`gh issue view` quirk:** Always add `--json title,body,state` (or other fields) — plain
`gh issue view <n>` always errors with a projectCards GraphQL error.
