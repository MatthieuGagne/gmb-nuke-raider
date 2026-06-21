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

## Git & GitHub

Always use `gh` for git push/pull and GitHub operations. Run `gh auth setup-git` if push fails due to missing credentials.

**Settings files:** `.claude/settings.local.json` is checked into git and must always be committed. When any new tool permission is approved during a session, commit `.claude/settings.local.json` along with the feature work so permissions are not lost.

**Always create a PR after pushing a branch** — no need to ask. Include `Closes #N` in the PR body to auto-close the related GitHub issue on merge. When a PR is merged, verify that the linked issue is closed; if not, close it manually with `gh issue close N`.

**`gh issue view` quirk:** Always add `--json title,body,state` (or other fields) — plain `gh issue view <n>` always errors with a projectCards GraphQL error.

## Skills & Agents

Agents live in `.claude/agents/`, skills in `.claude/skills/` — each file's frontmatter
(`description` / when-to-use) is the authoritative trigger and is surfaced automatically; don't
duplicate those descriptions here. `docs/dev-workflow.md` is co-authoritative and maps each one
to its workflow step.

Two things not obvious from frontmatter alone:
- Several skills are **project-local shadows** of global `superpowers:` skills (brainstorming,
  writing-plans, executing-plans, systematic-debugging, finishing-a-development-branch,
  subagent-driven-development, grill-me) — the local copy wins when invoked by name and adds the GB gates.
- `bank-pre-write` / `bank-post-build` / `gb-memory-validator` fire **automatically** via hooks
  (PreToolUse on `src/*` writes, PostToolUse after a non-clean `make`); the skills are fallback references.

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

## Workflow

This project uses [Superpowers](https://github.com/obra/superpowers) (installed globally in `~/.claude/`).

**Outer loop:** brainstorming → PRD (`/prd`) → [separate session] writing-plans → subagent-driven-development

**GitHub issue links:** When the user pastes a GitHub issue URL (e.g. `https://github.com/.../issues/N`), first fetch the issue and check its **Files Impacted** or **Out of Scope** sections. If ALL touched files qualify as doc-only (`.md`, `.txt`, `.json` except `bank-manifest.json`, files under `.claude/skills/` or `.claude/agents/`), invoke the `doc-review` skill. Otherwise invoke `writing-plans`. Do not ask for confirmation.
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill). **Early-exit behavior:** the Makefile uses `|| exit 1` — it stops at the first failing test binary (alphabetical order). Test binaries after the first failure do NOT run. Fix all failures starting from the earliest binary; re-run `make test` after each fix to reveal the next hidden failure.
**Bank manifest maintenance:** Every new `src/*.c` file must have an entry in `bank-manifest.json` before it is written. `bank-pre-write` hook (`tools/bank_check_hook.py`) and `bank_check.py` (Makefile dependency) both enforce this. Every banking-related PR must update ALL artifacts: `bank-manifest.json`, both bank skills, `bank_check.py`, `gbdk-expert`, `gb-memory-validator`, and this file.
**Build verification:** `make` (use `/build` skill)
**Map source of truth:** `assets/maps/track.tmx` (and `assets/maps/overmap.tmx`) are the authoritative sources for all map tile data. Never patch tile values directly into generated files (`src/track_map.c`, `src/overmap_map.c`). If a tile must be placed (e.g. `TILE_REPAIR`), add it to the TMX in Tiled, then re-run `make clean && make` to regenerate. Hand-edits to generated files are silently overwritten on the next build.
**PRDs & design docs:** GitHub issues only — no local files. Use `/prd` skill.

**Worktree policy:** ALL file operations — creating, editing, or deleting files — MUST happen inside a git worktree. This applies to implementation plans, code, tests, docs, and any other file. Before touching any file, use the `using-git-worktrees` skill or `EnterWorktree` tool to enter a worktree. Never write, edit, or delete files directly in the main working tree. If you are not currently in a worktree, STOP and enter one first. **`make test` must also be run from the worktree directory** — running it from the main repo root tests stale compiled binaries and silently masks real failures in the worktree.

**Smoketest gate:** NEVER push or create a PR before running a smoketest in the emulator. Always push AFTER the smoketest passes.
1. Fetch and merge latest master: `git fetch origin && git merge origin/master` (from the worktree directory). NEVER use `git merge master` alone — the local master ref may be stale.
2. Always do a clean build: `make clean && make`
3. `make memory-check` fires automatically via PostToolUse hook after step 2 — check the hook output; if any budget is FAIL or ERROR, stop and fix before continuing.
4. Ask the user for confirmation before launching the ROM. If they confirm, launch in the background from the worktree directory (NEVER from the main repo's `build/` — it may be stale): `java -jar C:\Tools\Emulicious\Emulicious.jar build/nuke-raider.gb`
5. Ask them to confirm it looks correct before proceeding.
6. Only after the user confirms: update `README.md` if the feature adds or changes any user-visible behavior, then push the branch and create the PR.

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
