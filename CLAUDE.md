# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```sh
make          # build
make clean    # clean
```

Output ROM: `build/nuke-raider.gb`. Toolchain paths and the emulator launch command are
machine-specific — see `CLAUDE.local.md`.

## Architecture

`src/main.c` is the entry point and game loop. It contains **only**: frame timing (`wait_vbl_done()`), input polling (`joypad()`), and state machine dispatch. No game logic lives inline in `main.c`. If a state handler grows beyond ~10 lines, extract it to a module.

States: `STATE_INIT` → `STATE_TITLE` → `STATE_OVERMAP` → `STATE_PLAYING` → `STATE_GAME_OVER`

Each game system lives in `src/<system>.c` + `src/<system>.h`. Asset source files (sprites, tiles, music) live under `assets/` and must be converted to C data arrays before use. Converted headers go in `src/`. All `.c` files in `src/` are automatically compiled by the Makefile.

## State Machine Rules

Three legal transitions (defined in `src/state_manager.c`, `STACK_MAX = 2`):

| Call | Effect | Use when |
|------|--------|----------|
| `state_push(next, args)` | depth +1 | Entering a sub-state (e.g. overmap → prerace) |
| `state_pop()` | depth -1 | Returning to the previous state (e.g. game_over → overmap) |
| `state_replace(next, args)` | depth unchanged | Lateral swap at the same level (e.g. prerace → playing) |

**WARNING: `state_replace` never reduces stack depth.** Using it to "go back" is a silent bug — the stack leaks one slot per navigation cycle. With `STACK_MAX = 2`, a leaked slot means the next `state_push` silently no-ops (push skipped, no error, no crash).

Canonical race path: `title(0) → overmap(0) → prerace(+1=1) → playing(1) → game_over(1) → state_pop() → overmap(0)`

`state_results` already uses `state_pop()` — follow this pattern for any "race ended" transition.

## Game Design & Influences

Full design doc: [`docs/game/game-design.md`](docs/game/game-design.md) — consult before making feature, tone, or UX decisions.

**Tone:** Post-apocalyptic wasteland (*Road Warrior*). Sparse, dry humor. Judas Priest energy — every word earns its place.

**Primary competitor:** Lunar Lancer (GB/GBC sci-fi racer) — differentiate via wasteland tone, hub/faction depth, and combat integration.

**Inspirations:** Jackal, Metal Gear 1 (NES); Spy Hunter, Micro Machines, RC Pro-Am, Super Off-Road, Contra: Operation C, Jurassic Park 2 (GB) — full rationale for each in the design doc.

## Scalability & C coding rules

Entity pools (SoA, `active` flag), memory budgets, the refactor checkpoint, and all GBDK/SDCC
constraints live in [`src/CLAUDE.md`](src/CLAUDE.md) (loads automatically when editing `src/`),
with full rationale in `docs/dev-workflow.md` §4.

## ROM Header

Current flags: `-Wm-yc` (CGB compatible, runs on DMG+GBC), `-Wm-yt25` (MBC5), `-Wm-yn"NUKERAIDER"`.
To target GBC-only (access extra VRAM bank, 8 BG/OBJ palettes): swap `-Wm-yc` for `-Wm-yC`.

**Bank 30 — the test command mailbox (#590):** debug-ROM-only, pinned one bank below music (31)
because banks 1 and 2 are too full to absorb a displaced module. `src/debug.c` compiles to
nothing under a release build, so bank 30 is uniform filler there. In the debug ROM it holds a
nine-byte WRAM wire that a headless test harness writes to drive the game through its own
functions — see `docs/dev-workflow.md`'s "The test command mailbox" section.

## Git & GitHub

Always use `gh` for git push/pull and GitHub operations. Run `gh auth setup-git` if push fails due to missing credentials.

**Settings tiers:** three layers, and only one of them is committed.
- **Machine** (`~/.claude/settings.json`, outside the repo): `env` values and any allow rule containing an absolute path. Template: `.claude/settings.user.example.json`.
- **Repo** (`.claude/settings.json`, tracked): the curated allowlist, the deny list, and all
  **agent** hook wiring — **repository** hook wiring lives in tracked `.githooks/` (see
  [ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467)). No absolute paths, no `env`. Validated by
  `python tools/allowlist_lint.py`, enforced by `make test-tools`. Any matcher naming one shell
  tool must name both (`Bash|PowerShell`) — the hygiene check fails otherwise.
- **Scratch** (`.claude/settings.local.json`, gitignored): transient session approvals. Never commit it.

**Promotion rule:** a permission approved during a session is either promoted deliberately — rewritten as a generalized rule in the canonical form for its tool (`Bash(prefix:*)`, `PowerShell(prefix *)`) and added to the tracked repo file — or discarded. Never copy a one-shot approval into version control. Rationale and the deny-gate design: [ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466).

**Always create a PR after pushing a branch** — no need to ask. Include `Closes #N` in the PR body to auto-close the related GitHub issue on merge. When a PR is merged, verify that the linked issue is closed; if not, close it manually with `gh issue close N`.

**`gh issue view` quirk:** Always add `--json title,body,state` (or other fields) — plain `gh issue view <n>` always errors with a projectCards GraphQL error.

## Skills & Agents

Agents live in `.claude/agents/`, skills in `.claude/skills/` — each file's frontmatter
(`description` / when-to-use) is the authoritative trigger and is surfaced automatically; don't
duplicate those descriptions here. `docs/dev-workflow.md` is co-authoritative and maps each one
to its workflow step.

Two things not obvious from frontmatter alone:
- The superpowers workflow skills (brainstorming, writing-plans, executing-plans,
  subagent-driven-development, finishing-a-development-branch, dispatching-parallel-agents,
  plus grill-with-docs) run from their auto-updating baselines; project deltas live in
  `.claude/skill-overlays/<name>.md` and are injected automatically by
  `tools/skill_overlay_hook.py` (PostToolUse on Skill + UserPromptSubmit hooks in
  `.claude/settings.json`). On conflict, the overlay wins. Each overlay's `baseline:`
  frontmatter pins the superpowers version it was written against; the hook warns when
  the installed version has moved (re-sync the overlay when it fires).
- `bank-pre-write` / `bank-post-build` / `gb-memory-validator` fire **automatically** via hooks
  (PreToolUse on `src/*` writes, PostToolUse after a non-clean `make`); the skills are fallback references.
- `factory` (`.claude/skills/factory/`) is the unattended orchestrator. It is invoked
  explicitly as `/factory <issue#>` and never fires automatically. It writes run state only
  through `tools/factory_event.py` and publishes to GitHub only through
  `tools/factory_publish.py` — never directly.

### Pi harness

`.pi/settings.json` exposes the same project skills and agents to the Pi coding agent
(`pi`), so a session started there is not flying blind. It wires `skills: ["../.claude/skills"]`
(all 18 project skills), the `pi-subagents` and `@hsingjui/pi-hooks` packages, and the four
portable hooks with Pi's lowercase tool matchers (`bash|powershell`, `write|edit`). `.pi/agents/*.md` are
thin wrappers: each carries Pi-native frontmatter and tells the child to read the matching
`.claude/agents/<name>.md` and follow it, so persona text lives in exactly one place.

**One-time step:** run `pi` from the repo root and accept the `/trust` prompt. Untrusted, Pi
loads none of the above.

**Gates that do not exist under Pi** — assume they are absent, do not rely on them:
- `tools/skill_overlay_hook.py` — not ported. Both halves are Claude-shaped: the `PostToolUse`
  half matches a `Skill` tool Pi does not have, and the `UserPromptSubmit` half parses `/<name>`
  while Pi registers skills as `/skill:<name>`. **Skill overlays never inject under Pi**, so a
  project delta in `.claude/skill-overlays/` is silently missing — read it yourself.
- `tools/factory_permission_hook.py` — not ported. It is a `Notification` hook and pi-hooks
  exposes no `Notification` event, so factory's permission-escalation path is unguarded.
- **The `pwsh-*` background-job tools are ungated** (#572). `@marcfargas/pi-powershell` registers
  `pwsh-start-job` and friends alongside the shell tools; those names match no hook matcher, so
  a command run through a job bypasses the deny gate, the Emulicious window hook and the
  post-build memory check. Widening the matchers is not enough for the deny gate: it filters
  again internally on `SHELL_TOOLS` in `tools/deny_gate_hook.py`, which admits only `bash` /
  `powershell` (either case). Run builds and pushes through the shell tool, not a job.

Also note the deny gate and bank check must exit **2** to block; under pi-hooks any other
non-zero exit is reported as a hook error and the tool call proceeds anyway.

The matchers are regex, not exact strings — pi-hooks does `new RegExp(matcher).test(toolName)`
(`@hsingjui/pi-hooks`, `src/config.ts` `matcherMatches`) — which is what lets one matcher name
both shell tools.

**The two harnesses anchor their hook commands differently, and the Pi anchor is the weaker of
the two.** `.claude/settings.json` uses Claude Code's `${CLAUDE_PROJECT_DIR}` placeholder;
`.pi/settings.json` uses the bash-evaluated
`$(git rev-parse --show-toplevel 2>/dev/null || echo .)`. That is not a stylistic difference:
pi-hooks (0.0.2) substitutes no placeholders and runs every hook command under `bash -c`, so
`${CLAUDE_PROJECT_DIR}` in `.pi/settings.json` would be expanded by bash as an undefined
variable and every Pi hook would resolve to `python "/tools/<name>.py"` — broken from every
directory, repository root included. The coverage is not equal either: the Claude placeholder
resolves from any working directory, while the Pi expression resolves only from a working
directory inside the repository. Outside one, `git rev-parse` fails and the `|| echo .` fallback
degrades the command to the pre-existing relative path rather than to `/tools/<name>.py`.
**Do not copy either form into the other file.**

Pi shell setup is **machine-local**, deliberately not committed: the build needs PowerShell,
`GBDK_HOME`, and Git's `bin`/`usr\bin` on `PATH`, and pointing Pi's `shellPath` at them takes
absolute paths. Configure that in `~/.pi/agent/settings.json`, not here.

## Debugging Rules

- **Shifted crash ≠ known issue**: If a fix moves a crash from time X to time Y (e.g. 24s → 33s), do NOT treat it as the same known bug. Investigate whether it is a different root cause before closing the loop.
- **One variable per test**: Never make two changes between test runs. Instrument, build, observe, conclude — one hypothesis at a time.
- **Worktree CWD**: Before every `make` or emulator launch, verify the current directory is the correct worktree directory (`pwd`). After any worktree cleanup, `cd` to a valid directory before running further commands.
- **PR navigation**: When the user says "go back again", "next one", or any relative reference during sequential PR testing, state the exact PR number out loud and confirm before doing the checkout.

## Game Logic Sharp Edges

**Race position — raw Y coordinate is not a valid "who is ahead" metric on winding tracks:**
Track2 is an oval: down the right side (ty increases), up the left side (ty decreases). Two competitors at the same Y value can be at completely different positions on the track — the comparison flips randomly. Use section-aware comparison:
- Detect side: `player_tx > 10` = right side; `racer_wp_idx < 6` = right side
- Right side (going down): higher `ty` = further ahead
- Left side (going up): lower `ty` = further ahead
- Different sides: the competitor on the left side is further along
- General rule: use waypoint progress scores (`laps × wp_count + wp_idx`), not raw pixel coordinates.

**Player waypoint tracking uses different thresholds than the racer:**
The racer steers toward waypoints; the player drives freely. `RACER_WP_THRESHOLD * 2 = 24px` is too tight for player WP detection on track2 (player start at (96,40), WP0 at (124,44) — 32px east, never within 24px). Use ≥32px threshold or initialize to nearest waypoint at race start.

**Contact/ram damage vs a SOLID enemy — a strict AABB silently misses "from behind":**
Racers are solid to the player (`corner_active_racer` in `player.c` `corners_passable`), so the player is blocked *flush* against the racer's bumper: the boxes only touch (`px+16 == racer_px`), and a strict overlap test (`px+16 > racer_px`) is **false** → no ram registers when chasing from behind. Head-on/side hits work only because closing velocity interpenetrates for a frame. Fix: detect contact with a small reach margin, not strict overlap — `enemy_ram_overlap()` in `enemy_common.c` inflates the enemy box by `ENEMY_RAM_REACH` (2px) on every side so flush contact rams from any direction. Both racer.c and patrol.c MUST use that shared helper (identical collision logic). Any new player↔enemy contact-damage feature has the same trap (#417).

## PRD vs Implementation Plan

When the user asks for a brainstorm or PRD: stay at the **requirements and design level only**. Do not write implementation details, code snippets, or file-level task breakdowns. If the user wants an implementation plan they will explicitly ask for one.

## Build & Test Rules

- Always use a clean build (`make clean && make`) when testing historical PRs or comparing versions. Never assume a prior build is still valid.

**Two ROMs:** `make` builds the release ROM; `make build-debug` builds the debug ROM, which
adds `DBG_STATIC` symbols, the bank-30 test command mailbox and a stack reserved to 0xDF00. The
two ROMs no longer hold identical bytes anywhere, bank 0 included: the reserved stack and the
`BANKED` trampolines it needs live in bank 0, and a `BANKED` function's trampoline shifts
bank-0 addresses, which shifts the absolute operands banked code (banks 1-3) uses to call it.
`tests/test_rom_parity.py` no longer checks byte identity for banks 1-3 — it checks that every
differing byte there is an operand relocated to another bank-0 address, that the relocation
mapping is consistent, and that the number of distinct relocated targets and deltas stays
small.

## Workflow

This project uses [Superpowers](https://github.com/obra/superpowers) (installed globally in `~/.claude/`).

**Outer loop:** brainstorming → PRD (`/prd`) → [separate session] writing-plans → subagent-driven-development

**Factory loop (unattended):** `/factory <issue#>` drives a lint-passing PRD issue through
GATE → PLAN → BUILD → VERIFY → SHIP with no interactive input, ending at a reviewable PR.
Flags: `--stage <NAME>`, `--resume`, `--dry-run`. Run state lives in `.factory/runs/issue-<N>/`
at the **main** repo root, so any session locates a run from the issue number alone
(`python tools/factory_status.py`). The factory never merges, never commits to `master`, never
force-pushes, never passes `--no-verify`, and never deletes a worktree or branch. Full contract:
`.claude/skills/factory/SKILL.md` and its `references/stages.md`.

**GitHub issue links:** When the user pastes a GitHub issue URL (e.g. `https://github.com/.../issues/N`), first fetch the issue and check its **Files Impacted** or **Out of Scope** sections. If ALL touched files qualify as doc-only (`.md`, `.txt`, `.json` except `bank-manifest.json`, files under `.claude/skills/` or `.claude/agents/`), invoke the `doc-review` skill. Otherwise invoke `writing-plans`. Do not ask for confirmation.
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill). **Early-exit behavior:** the Makefile uses `|| exit 1` — it stops at the first failing test binary (alphabetical order). Test binaries after the first failure do NOT run. Fix all failures starting from the earliest binary; re-run `make test` after each fix to reveal the next hidden failure.
**Bank manifest maintenance:** Every new `src/*.c` file must have an entry in `bank-manifest.json` before it is written. `bank-pre-write` hook (`tools/bank_check_hook.py`) and `tools/bank_check.py` (Makefile dependency) both enforce this. Every banking-related PR must update ALL artifacts: `bank-manifest.json`, both bank skills, `tools/bank_check.py`, `gbdk-expert`, `gb-memory-validator`, and this file.
**Build verification:** `make` (use `/build` skill)
**Map source of truth:** `assets/maps/track.tmx` (and `assets/maps/overmap.tmx`) are the authoritative sources for all map tile data. Never patch tile values directly into generated files (`src/track_map.c`, `src/overmap_map.c`). If a tile must be placed (e.g. `TILE_BOOST`), add it to the TMX in Tiled, then re-run `make clean && make` to regenerate. Hand-edits to generated files are silently overwritten on the next build.
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
and the ADR rules in this section apply identically in both. A convention written here is not
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

**Worktree policy:** ALL file operations — creating, editing, or deleting files — MUST happen inside a git worktree. This applies to implementation plans, code, tests, docs, and any other file. Before touching any file, use the `using-git-worktrees` skill or `EnterWorktree` tool to enter a worktree. Never write, edit, or delete files directly in the main working tree. If you are not currently in a worktree, STOP and enter one first. **`make test` must also be run from the worktree directory** — running it from the main repo root tests stale compiled binaries and silently masks real failures in the worktree.

**Smoketest gate:** NEVER push or create a PR before running a smoketest in the emulator. Always push AFTER the smoketest passes.
1. Fetch and merge latest master: `git fetch origin && git merge origin/master` (from the worktree directory). NEVER use `git merge master` alone — the local master ref may be stale.
2. Always do a clean build: `make clean && make`
3. `make memory-check` fires automatically via PostToolUse hook after step 2 — check the hook output; if any budget is FAIL or ERROR, stop and fix before continuing.
4. Ask the user for confirmation before launching the ROM. If they confirm, launch in the background from the worktree directory (NEVER from the main repo's `build/` — it may be stale), using the emulator launch command in `CLAUDE.local.md`.
5. Ask them to confirm it looks correct before proceeding.
6. Only after the user confirms: update `README.md` if the feature adds or changes any
   user-visible behavior, then push the branch and create the PR. The `pre-push` repository hook
   runs `make clean && make` and blocks the push if it fails — steps 2–3 are still yours to run,
   the hook only guarantees the tree you publish builds.

*Factory-only exception:* during a `/factory` run (`NUKE_FACTORY_RUN` set) steps 4-5 — the
Emulicious launch and the human visual confirmation — are replaced by the blocking headless
smoketest, `python tools/smoketest_headless.py --scenario generic-smoke --json`. Steps 1-3
(fetch+merge, clean build, `make memory-check`) and step 6 (README + push + PR) are unchanged,
and a memory FAIL still aborts. This exception applies **only** inside a factory run; every
manual session keeps the human gate verbatim.

**GB skill gates:**
- Before writing any `src/*.c` or `src/*.h` file → `bank-pre-write` fires **automatically** via PreToolUse hook; invoke `gbdk-expert` agent:
  - **Consultation mode** (API questions): `"how do I set up CGB palettes"`, `"why is my sprite flickering"`
  - **Implementation mode** (C implementation tasks): dispatch with `"implement this task: <full task text>"` — `gbdk-expert` writes the code applying all project constraints
- After a successful build → `bank-post-build` + `make memory-check` fire **automatically** via PostToolUse hook; no manual invocation needed
- When debugging any runtime issue → invoke `emulicious-debug` agent (Agent tool)

**Parallel agents policy:** ALWAYS fire concurrent Agent calls (one message) for independent, non-conflicting tasks — separate files, reviews on different files, read-only exploration. NEVER parallelize tasks that write the same file, share git state (multiple committers on one branch), or have sequential data dependencies. Full reference: `dispatching-parallel-agents` skill.

**Explore agent mandate:** For ANY codebase exploration involving more than 2 files or any open-ended search (e.g. "find where X is used", "what calls Y", "search for pattern Z"), use the Explore agent — do NOT accumulate inline Read/Glob/Grep calls. Inline file reads are reserved for targeted lookups of known file paths. See `dispatching-parallel-agents` skill for the full offload and parallelize reference.

**Branch policy:** NEVER commit directly to `master`. All work goes on a feature branch and merges via PR.

**Doc-only workflow:** When ALL files changed in a session are non-compiled doc files, use this abbreviated path instead of the full gate sequence. **For doc-only PRD implementations, invoke the `doc-review` skill instead of `writing-plans` + `executing-plans`.**

*Qualifies as doc-only:* `*.md`, `*.txt`, `*.json` (except `bank-manifest.json`), and any file under `.claude/skills/` or `.claude/agents/`.

*Conservative rule:* If ANY `.c` or `.h` file is touched in the same session, the **full workflow applies** — no exceptions.

*Gates skipped for doc-only:* bank-pre-write, gbdk-expert consultation, bank-post-build bank validation, gb-memory-validator, TDD red/green cycle.

*Gates kept for doc-only (sanity check):* clean ROM build and smoketest — full sequence still applies (fetch + merge origin/master, clean build, launch ROM, user confirms); only the `bank-post-build` and `gb-memory-validator` gate invocations are skipped.

*Abbreviated doc-only step sequence:*
1. Enter worktree
2. Edit doc file(s)
3. Fetch + merge: `git fetch origin && git merge origin/master`
4. Clean build: `make clean && make`
5. Smoketest: ask user for confirmation, then launch ROM in Emulicious if confirmed, confirm no pre-existing breakage
6. Commit
7. Push branch and create PR

**Override passphrase:** defined in `CLAUDE.local.md` (personal, gitignored).
