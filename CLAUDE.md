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

**State machine:** three legal transitions (`state_push` / `state_pop` / `state_replace`,
`STACK_MAX = 2`). **`state_replace` never reduces stack depth** — using it to "go back" silently
leaks a slot and the next `state_push` no-ops. Full table and the canonical race path:
[`src/CLAUDE.md`](src/CLAUDE.md).

## Game Design & Influences

Full design doc: [`docs/game/game-design.md`](docs/game/game-design.md) — consult before making feature, tone, or UX decisions.

**Tone:** Post-apocalyptic wasteland (*Road Warrior*). Sparse, dry humor. Judas Priest energy — every word earns its place.

**Primary competitor:** Lunar Lancer (GB/GBC sci-fi racer) — differentiate via wasteland tone, hub/faction depth, and combat integration.

**Inspirations:** listed with full rationale in the design doc.

## Scalability & C coding rules

Entity pools (SoA, `active` flag), memory budgets, the refactor checkpoint, and all GBDK/SDCC
constraints live in [`src/CLAUDE.md`](src/CLAUDE.md) (loads automatically when editing `src/`),
with full rationale in `docs/dev-workflow.md` §4.

## ROM Header

Current flags: `-Wm-yc` (CGB compatible, runs on DMG+GBC), `-Wm-yt25` (MBC5), `-Wm-yn"NUKERAIDER"`.
To target GBC-only (access extra VRAM bank, 8 BG/OBJ palettes): swap `-Wm-yc` for `-Wm-yC`.

Bank pinning (30 = debug-only test command mailbox, 31 = music) is documented in
[`src/CLAUDE.md`](src/CLAUDE.md); the mailbox wire itself in `docs/dev-workflow.md`.

## Git & GitHub

Always use `gh` for git push/pull and GitHub operations. Run `gh auth setup-git` if push fails due to missing credentials.

**Settings tiers:** machine (`~/.claude/settings.json`) holds `env` and any absolute path; repo
(`.claude/settings.json`, tracked) holds the allowlist, deny list and agent hook wiring —
repository hooks live in `.githooks/`; scratch (`.claude/settings.local.json`, gitignored) is
never committed. A matcher naming one shell tool must name both (`Bash|PowerShell`). A session
approval is either rewritten as a generalized rule in the tracked repo file or discarded — never
copied in verbatim. Validated by `python tools/allowlist_lint.py`; rationale in
[ADR 441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/467) and
[ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466).

**Always create a PR after pushing a branch** — no need to ask. Include `Closes #N` in the PR body to auto-close the related GitHub issue on merge. When a PR is merged, verify that the linked issue is closed; if not, close it manually with `gh issue close N`.

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

Running under the Pi agent (`pi`) instead of Claude Code? Two gates are absent there: **skill
overlays never inject** (read `.claude/skill-overlays/` yourself) and **the `pwsh-*` background-job
tools bypass every hook** (#572) — run builds and pushes through the shell tool, not a job.
Full setup, the remaining missing gates, and why the two harnesses' hook anchors must not be
copied between files: @docs/pi-harness.md

## Debugging Rules

- **Shifted crash ≠ known issue**: If a fix moves a crash from time X to time Y (e.g. 24s → 33s), do NOT treat it as the same known bug. Investigate whether it is a different root cause before closing the loop.
- **One variable per test**: Never make two changes between test runs. Instrument, build, observe, conclude — one hypothesis at a time.
- **Worktree CWD**: Before every `make` or emulator launch, verify the current directory is the correct worktree directory (`pwd`). After any worktree cleanup, `cd` to a valid directory before running further commands.
- **PR navigation**: When the user says "go back again", "next one", or any relative reference during sequential PR testing, state the exact PR number out loud and confirm before doing the checkout.

## PRD vs Implementation Plan

When the user asks for a brainstorm or PRD: stay at the **requirements and design level only**. Do not write implementation details, code snippets, or file-level task breakdowns. If the user wants an implementation plan they will explicitly ask for one.

## Build & Test Rules

- Always use a clean build (`make clean && make`) when testing historical PRs or comparing versions. Never assume a prior build is still valid.

**Two ROMs:** `make` builds the release ROM; `make build-debug` builds the debug ROM, which adds
`DBG_STATIC` symbols, the bank-30 test command mailbox and a stack reserved to 0xDF00. The two
ROMs differ **by design** in every bank, bank 0 included — do not treat a byte difference as a
defect. What parity actually requires is defined by `tests/test_rom_parity.py`; read it before
changing anything about the debug build.

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
**PRDs & design docs:** GitHub issues only — no local files (`/prd` skill files them). **Decisions
are ADRs filed as `adr`-labeled GitHub issues**, keyed by the work item's issue number. Every
document issue goes on the "Nuke Raider — Documents" board with an explicit `Type` and `Status`,
and these conventions govern **both** repositories (gmb-nuke-raider and nuke-raiders-garage).
Exception: `CONTEXT.md` (repo root) is the only design artifact versioned in-repo.

Routing, sub-issue wiring, the ADR key/lifecycle/citation rules, the `Type` table and the `Idea`
swimlane: @docs/document-conventions.md

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
- Before writing any `src/*.c` or `src/*.h` file → `bank-pre-write` fires **automatically** via PreToolUse hook; invoke the `gbdk-expert` agent (its frontmatter defines consultation vs implementation mode)
- After a successful build → `bank-post-build` + `make memory-check` fire **automatically** via PostToolUse hook; no manual invocation needed
- When debugging any runtime issue → invoke `emulicious-debug` agent (Agent tool)

**Parallel agents policy:** ALWAYS fire concurrent Agent calls (one message) for independent, non-conflicting tasks; NEVER parallelize tasks that write the same file, share git state, or have sequential data dependencies.

**Explore agent mandate:** For ANY exploration touching more than 2 files or any open-ended search, use the Explore agent — inline Read/Glob/Grep is reserved for targeted lookups of known paths. Full reference for both: `dispatching-parallel-agents` skill.

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
