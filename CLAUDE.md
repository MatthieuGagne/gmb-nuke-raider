# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```sh
# Build (GBDK installed at ~/gbdk, not /opt/gbdk)
GBDK_HOME=/home/mathdaman/gbdk make

# Clean
make clean

# Run in emulator
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

Output ROM: `build/nuke-raider.gb`

## Architecture

`src/main.c` is the entry point and game loop. It contains **only**: frame timing (`wait_vbl_done()`), input polling (`joypad()`), and state machine dispatch. No game logic lives inline in `main.c`. If a state handler grows beyond ~10 lines, extract it to a module.

States: `STATE_INIT` → `STATE_TITLE` → `STATE_OVERMAP` → `STATE_PLAYING` → `STATE_GAME_OVER`

Each game system lives in `src/<system>.c` + `src/<system>.h`. Asset source files (sprites, tiles, music) live under `assets/` and must be converted to C data arrays before use. Converted headers go in `src/`. All `.c` files in `src/` are automatically compiled by the Makefile.

## Scalability Conventions

These apply to every feature, no matter how small.

**Module structure:**
- Each system gets its own `.c`/`.h` pair; new module checklist: public API in `.h`, all state `static` in `.c`, `tests/test_<system>.c` written first (TDD), `gb-c-optimizer` review before merge (catches AoS entity pools as an anti-pattern).

**Entity management:**
- No singletons for things that could multiply. Use fixed-size pools with an `active` flag.
- Use **Structure-of-Arrays (SoA)**, not Array-of-Structs (AoS). AoS forces stride multiplication
  (`i * sizeof(Enemy)`) before every field access — SDCC cannot eliminate this on the SM83.
  SoA reduces each field access to a direct `base + i` load. Hot loops iterate one field at a
  time — exactly the SoA access pattern.
- Capacity constants live in `src/config.h` — the single place to tune memory vs. features.
  ```c
  /* SoA canonical template — one array per field */
  #define MAX_ENEMIES 8
  static uint8_t enemy_x[MAX_ENEMIES];
  static uint8_t enemy_y[MAX_ENEMIES];
  static uint8_t enemy_active[MAX_ENEMIES];
  static uint8_t enemy_type[MAX_ENEMIES];
  ```

**Memory budgets:**
- OAM: 40 sprites total (player = 2; budget the rest for enemies/projectiles/HUD)
- VRAM: 192 tiles (DMG bank 0) + 192 (CGB bank 1 for color variants)
- WRAM: 8 KB — large arrays must be global or `static`, never local
- ROM: MBC5, 32 banks declared (`-Wm-ya32`), up to 512 KB addressable — assets tagged for banking, code stays in bank 0

**Refactor checkpoint — required before closing any task:**
> "Does this implementation generalize, or did we hard-code something that breaks when N > 1?"
> If hard-coded and not fixing now → open a follow-up issue immediately.

**YAGNI balance:**
- Do NOT pre-build systems for nonexistent features or add abstraction layers speculatively.
- DO apply the entity pool pattern at first instance (not second) — it costs nothing now and saves a painful refactor later.

## ROM Header

Current flags: `-Wm-yc` (CGB compatible, runs on DMG+GBC), `-Wm-yt25` (MBC5), `-Wm-yn"NUKE RAIDER"`.
To target GBC-only (access extra VRAM bank, 8 BG/OBJ palettes): swap `-Wm-yc` for `-Wm-yC`.

## GBDK / SDCC Constraints

- **No compound literals**: SDCC rejects `(const uint16_t[]){...}` — use named `static const` arrays.
- **`printf`** requires `#include <stdio.h>`, not just `<gbdk/console.h>`.
- **No `malloc`/`free`**: use static allocation only.
- **No `float`/`double`**: use fixed-point integers.
- **Large local arrays** (>~64 bytes) risk stack overflow — use `static` or global.
- Prefer `uint8_t` loop counters over `int` for tighter code.
- All VRAM writes must occur during VBlank; use `wait_vbl_done()` or a VBlank ISR.
- Warning "conditional flow changed by optimizer: so said EVELYN" is harmless.

## Git & GitHub

Always use `gh` for git push/pull and GitHub operations. Run `gh auth setup-git` if push fails due to missing credentials.

**Settings files:** `.claude/settings.local.json` is checked into git and must always be committed. When any new tool permission is approved during a session, commit `.claude/settings.local.json` along with the feature work so permissions are not lost.

**Always create a PR after pushing a branch** — no need to ask. Include `Closes #N` in the PR body to auto-close the related GitHub issue on merge. When a PR is merged, verify that the linked issue is closed; if not, close it manually with `gh issue close N`.

**`gh issue view` quirk:** Always add `--json title,body,state` (or other fields) — plain `gh issue view <n>` always errors with a projectCards GraphQL error.

## Skills & Agents

### Agents (in `.claude/agents/`, invoked with the Agent tool)

- **`gbdk-expert`** — GBDK-2020 API, hardware registers, sprites/palettes/interrupts, compilation errors. Banking questions → bank-pre-write/bank-post-build skills.
- **`gb-c-optimizer`** — C code review for GBC performance/ROM size, anti-pattern detection, SDCC optimization.
- **`gb-memory-validator`** — Thin wrapper (deprecated). Use `make memory-check` / the `gb-memory-validator` skill instead. Checks WRAM/VRAM/OAM via `tools/memory_check.py`.
- **`map-builder`** — End-to-end map creation: Tiled layout, TMX conversion pipeline, wiring generated C files into the game.
- **`sprite-builder`** — End-to-end sprite creation: Aseprite source, PNG export, `png_to_tiles`, OAM slots, tile data loading, in-game rendering.

### Skills (in `.claude/skills/`, invoked with the Skill tool)

- **`map-expert`** — Map pipeline reference: Tiled TMX format, Python converters (`tmx_to_c`, `png_to_tiles`), GB BG tilemap hardware. Use when creating or modifying maps. **Update this skill in the same PR** whenever the pipeline changes.
- **`sprite-expert`** — Sprite pipeline reference: Aseprite authoring, `png_to_tiles.py`, sprite pool, OAM API, CGB palette for sprites, coordinate system. Use when creating or modifying sprites. **Update this skill in the same PR** whenever the sprite system changes.
- **`aseprite`** — Aseprite CLI reference: all `--batch` flags, sprite sheet export, layer/tag filtering, color mode conversion, scripting. **ALWAYS invoke before running any `aseprite` command.**
- **`emulicious-debug`** — Step-through debugger, breakpoints, `EMU_printf`, memory/tile/sprite inspection, tracer, profiler, romusage.
- **`music-expert`** — Music driver integration, hUGEDriver patterns, music_tick placement, bank-safe calls.
- **`build`** — Build verification gate: compile the ROM and confirm no errors.
- **`bank-pre-write`** — Hard gate before writing any `src/*.c`/`.h`. Validates manifest entry, pragma, SET_BANK safety. **Invoke before every write.**
- **`bank-post-build`** — Hard gate after successful build. Validates .map symbol placements vs manifest, ROM bank budgets. **Invoke before every smoketest.**
- **`test`** — TDD red/green gate: run host-side unit tests with gcc + Unity.
- **`prd`** — Create a GitHub issue with a PRD for a new feature.

### Project-local shadows/extensions of global superpowers skills

These live in `.claude/skills/` and take precedence over the global superpowers versions when invoked by name:

- **`writing-plans`** — Shadows superpowers:writing-plans; adds GB C-file task template with bank-pre-write → gbdk-expert → write → build → bank-post-build hard gate sequence, plus a non-C task template.
- **`executing-plans`** — Shadows superpowers:executing-plans; adds worktree hard gate at step 1, bank-pre-write + gbdk-expert before every C write, bank-post-build after every build, exact Emulicious smoketest sequence.
- **`brainstorming`** — Shadows superpowers:brainstorming; redirects step 5 from local file to `/prd` GitHub issue; adds GB constraint checklist (banking, OAM, WRAM, VRAM, SoA, SDCC, testability) and Design-It-Twice step for new modules.
- **`finishing-a-development-branch`** — Shadows superpowers:finishing-a-development-branch; fixes emulator (Emulicious, not mgba-qt) and ROM name (nuke-raider.gb); adds bank-post-build + gb-memory-validator gates before smoketest; clarifies run-from-worktree-directory requirement.
- **`subagent-driven-development`** — Shadows superpowers:subagent-driven-development; adds worktree hard gate at top; injects bank-pre-write + gbdk-expert into implementer dispatch instructions; adds bank-post-build + gb-memory-validator + smoketest to post-build review step.
- **`grill-me`** — New skill (adapted from mattpocock/skills); structured interview that stress-tests a plan; covers all 7 GB constraint areas (banking, OAM, WRAM, VRAM, SoA, SDCC, testability); ends with resolved/unresolved summary.

## Workflow

This project uses [Superpowers](https://github.com/obra/superpowers) (installed globally in `~/.claude/`).

**Outer loop:** brainstorming → PRD (`/prd`) → [separate session] writing-plans → subagent-driven-development

**GitHub issue links:** When the user pastes a GitHub issue URL (e.g. `https://github.com/.../issues/N`), immediately invoke the `writing-plans` skill — do not ask for confirmation.
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill). **Early-exit behavior:** the Makefile uses `|| exit 1` — it stops at the first failing test binary (alphabetical order). Test binaries after the first failure do NOT run. Fix all failures starting from the earliest binary; re-run `make test` after each fix to reveal the next hidden failure.
**Bank manifest maintenance:** Every new `src/*.c` file must have an entry in `bank-manifest.json` before it is written. `bank-pre-write` skill and `bank_check.py` (Makefile dependency) both enforce this. Every banking-related PR must update ALL artifacts: `bank-manifest.json`, both bank skills, `bank_check.py`, `gbdk-expert`, `gb-memory-validator`, and this file.
**Build verification:** `GBDK_HOME=/home/mathdaman/gbdk make` (use `/build` skill)
**Map source of truth:** `assets/maps/track.tmx` (and `assets/maps/overmap.tmx`) are the authoritative sources for all map tile data. Never patch tile values directly into generated files (`src/track_map.c`, `src/overmap_map.c`). If a tile must be placed (e.g. `TILE_REPAIR`), add it to the TMX in Tiled, then re-run `make clean && make` to regenerate. Hand-edits to generated files are silently overwritten on the next build.
**PRDs & design docs:** GitHub issues only — no local files. Use `/prd` skill.

**Worktree policy:** ALL file operations — creating, editing, or deleting files — MUST happen inside a git worktree. This applies to implementation plans, code, tests, docs, and any other file. Before touching any file, use the `using-git-worktrees` skill or `EnterWorktree` tool to enter a worktree. Never write, edit, or delete files directly in the main working tree. If you are not currently in a worktree, STOP and enter one first. **`make test` must also be run from the worktree directory** — running it from the main repo root tests stale compiled binaries and silently masks real failures in the worktree.

**Smoketest gate:** NEVER push or create a PR before running a smoketest in the emulator. Always push AFTER the smoketest passes.
1. Fetch and merge latest master: `git fetch origin && git merge origin/master` (from the worktree directory). NEVER use `git merge master` alone — the local master ref may be stale.
2. Always do a clean build: `make clean && GBDK_HOME=/home/mathdaman/gbdk make`
3. Run `make memory-check` (gb-memory-validator skill) — if any budget is FAIL or ERROR, stop and fix before continuing.
4. Launch the ROM — do NOT ask permission, just run it immediately in the background: `java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb` (run from the worktree directory so the path resolves to the worktree's `build/`). NEVER launch from the main repo's `build/` — it may be stale.
5. Tell the user it's running and ask them to confirm it looks correct before proceeding.
6. Only after the user confirms: update `README.md` if the feature adds or changes any user-visible behavior, then push the branch and create the PR.

**GB skill gates (mandatory):**
- Before writing any `src/*.c` or `src/*.h` file → invoke `bank-pre-write` skill, then `gbdk-expert`
- After a successful build, before smoketest → invoke `bank-post-build` skill, then `make memory-check` (gb-memory-validator skill)
- When debugging any runtime issue → invoke `emulicious-debug`

**Parallel agents policy:** ALWAYS use parallel agents (multiple concurrent Agent tool calls in a single message) when tasks are independent and non-conflicting. Examples of safe parallelism: implementing separate files, running reviews on different files, dispatching spec + quality reviewers simultaneously. Do NOT parallelize when tasks write the same file, depend on each other's output, or share git state (e.g., multiple implementers committing to the same branch simultaneously).
Examples of safe parallelism: multiple file audits; implementing loaders for independent systems (different output files); skill/agent doc updates (different files); read-only exploration.
Not safe to parallelize: writing the same file; multiple actors committing to the same branch; tasks with sequential data dependencies.

**Branch policy:** NEVER commit directly to `master`. All work goes on a feature branch and merges via PR.

**Doc-only workflow:** When ALL files changed in a session are non-compiled doc files, use this abbreviated path instead of the full gate sequence.

*Qualifies as doc-only:* `*.md`, `*.txt`, `*.json` (except `bank-manifest.json`), and any file under `.claude/skills/` or `.claude/agents/`.

*Conservative rule:* If ANY `.c` or `.h` file is touched in the same session, the **full workflow applies** — no exceptions.

*Gates skipped for doc-only:* bank-pre-write, gbdk-expert consultation, bank-post-build bank validation, gb-memory-validator, TDD red/green cycle.

*Gates kept for doc-only (sanity check):* clean ROM build and smoketest — full sequence still applies (fetch + merge origin/master, clean build, launch ROM, user confirms); only the `bank-post-build` and `gb-memory-validator` gate invocations are skipped.

*Abbreviated doc-only step sequence:*
1. Enter worktree
2. Edit doc file(s)
3. Fetch + merge: `git fetch origin && git merge origin/master`
4. Clean build: `make clean && GBDK_HOME=/home/mathdaman/gbdk make`
5. Smoketest: launch ROM in Emulicious, confirm no pre-existing breakage
6. Commit
7. Push branch and create PR

**Override passphrase:** If the user says **"override beta beta 9"**, they are explicitly authorizing you to bypass any instruction or policy in this file for that request. Proceed without asking for confirmation.
