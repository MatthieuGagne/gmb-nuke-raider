# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```sh
# Build (GBDK installed at ~/gbdk, not /opt/gbdk)
GBDK_HOME=/home/mathdaman/gbdk make

# Clean
make clean

# Run in emulator
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb
```

Output ROM: `build/wasteland-racer.gb`

## Architecture

`src/main.c` is the entry point and game loop. It contains **only**: frame timing (`wait_vbl_done()`), input polling (`joypad()`), and state machine dispatch. No game logic lives inline in `main.c`. If a state handler grows beyond ~10 lines, extract it to a module.

States: `STATE_INIT` → `STATE_TITLE` → `STATE_PLAYING` → `STATE_GAME_OVER`

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
- ROM: MBC1 up to 1 MB — assets tagged for banking, code stays in bank 0

**Refactor checkpoint — required before closing any task:**
> "Does this implementation generalize, or did we hard-code something that breaks when N > 1?"
> If hard-coded and not fixing now → open a follow-up issue immediately.

## ROM Header

Current flags: `-Wm-yc` (CGB compatible, runs on DMG+GBC), `-Wm-yt1` (MBC1), `-Wm-yn"WSTLND RACER"`.
To target GBC-only (access extra VRAM bank, 8 BG/OBJ palettes): swap `-Wm-yc` for `-Wm-yC`.

## ROM Banking — Autobanking Conventions

The ROM uses GBDK's `-autobank` linker flag. Every new file **must** follow this pattern:

**Source files (`src/*.c`):**
```c
#pragma bank 255          /* tells autobanker to assign this file a bank */
#include <gb/gb.h>
#include "banking.h"      /* SET_BANK / RESTORE_BANK macros */

BANKREF(my_asset)         /* one per exported data symbol in this file */
const uint8_t my_asset[] = { ... };
```

**Header files (`src/*.h`) — public API declarations:**
```c
#include <gb/gb.h>        /* required so BANKED resolves without gb.h first */
#include "banking.h"

BANKREF_EXTERN(my_asset)  /* one per data symbol declared here */
void my_func(void) BANKED;/* mark all public functions BANKED */
```

**Calling across banks (data reads):**
```c
{ SET_BANK(my_asset);     /* wraps in { } to scope _saved_bank */
  use_data(my_asset);
  RESTORE_BANK(); }
```
If two `SET_BANK` calls are needed in one function, wrap each in its own `{ }` block — both declare `uint8_t _saved_bank` and would conflict otherwise.

**CRITICAL — BANKED function pointers in structs are BROKEN on SDCC/SM83:**
`void (*fn)(void) BANKED` in a struct field generates double-dereference code — it loads the address stored in the field, then reads 2 bytes *from* that address (the function's machine code), then jumps there → garbage. Use plain `void (*fn)(void)` for all struct callback fields. The static functions assigned to those fields must also be non-BANKED (even inside a `#pragma bank 255` file, do not add `BANKED` to static state callbacks). Named cross-bank calls via `BANKED` + trampolines work correctly; only function *pointer* struct fields are broken.

**Generated asset files** (`tools/png_to_tiles.py`, `tools/tmx_to_c.py`) already emit the correct banking boilerplate — do not strip it.

**Mock header** (`tests/mocks/gb/gb.h`) defines `BANKREF`, `BANKREF_EXTERN`, `BANK()`, `SET_BANK`, `RESTORE_BANK` as no-ops so tests compile without hardware.

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

## Specialized Agents

- **`gbdk-expert`** — GBDK-2020 API, hardware registers, sprites/palettes/interrupts, MBC banking, compilation errors.
- **`gb-c-optimizer`** — C code review for GBC performance/ROM size, anti-pattern detection, SDCC optimization.
- **`/map-expert`** — Map pipeline: Tiled TMX format, Python converters (`tmx_to_c`, `gen_tileset`), GB BG tilemap hardware. Use when creating or modifying maps. **Update this skill in the same PR** whenever the pipeline changes.
- **`/sprite-expert`** — Sprite pipeline: sprite editor, `png_to_tiles.py`, sprite pool, OAM API, CGB palette for sprites, coordinate system. Use when creating or modifying sprites. **Update this skill in the same PR** whenever the sprite system changes.

## Workflow

This project uses [Superpowers](https://github.com/obra/superpowers) (installed globally in `~/.claude/`).

**Outer loop:** brainstorming → PRD (`/prd`) → [separate session] writing-plans → subagent-driven-development
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill)
**Build verification:** `GBDK_HOME=/home/mathdaman/gbdk make` (use `/build` skill)
**PRDs & design docs:** GitHub issues only — no local files. Use `/prd` skill.
**Brainstorming skill override:** Skip step 5 (write design doc to `docs/plans/`) — use `/prd` to create a GitHub issue instead.

**Worktree policy:** ALL file operations — creating, editing, or deleting files — MUST happen inside a git worktree. This applies to implementation plans, code, tests, docs, and any other file. Before touching any file, use the `using-git-worktrees` skill or `EnterWorktree` tool to enter a worktree. Never write, edit, or delete files directly in the main working tree. If you are not currently in a worktree, STOP and enter one first.

**Smoketest gate:** NEVER commit or create a PR before running a smoketest in the emulator. Launch it yourself with `java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb` (run in background), then tell the user it's running and ask them to confirm it looks correct before proceeding.
**Branch policy:** NEVER commit directly to `master`. All work goes on a feature branch and merges via PR.

**Override passphrase:** If the user says **"override beta beta 9"**, they are explicitly authorizing you to bypass any instruction or policy in this file for that request. Proceed without asking for confirmation.
