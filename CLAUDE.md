# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```sh
# Build (GBDK installed at ~/gbdk, not /opt/gbdk)
GBDK_HOME=/home/mathdaman/gbdk make

# Clean
make clean

# Run in emulator
mgba-qt build/wasteland-racer.gb
```

Output ROM: `build/wasteland-racer.gb`

## Architecture

`src/main.c` is the single source file containing the entry point and game loop. The game uses a state machine (`GameState` enum) driven by a `while(1)` loop that calls `wait_vbl_done()` each frame.

States: `STATE_INIT` → `STATE_TITLE` → `STATE_PLAYING` → `STATE_GAME_OVER`

Asset source files (sprites, tiles, music) live under `assets/` and must be converted to C data arrays before use. Converted headers go in `src/`. All `.c` files in `src/` are automatically compiled by the Makefile.

## ROM Header

Current flags: `-Wm-yc` (CGB compatible, runs on DMG+GBC), `-Wm-yt1` (MBC1), `-Wm-yn"WSTLND RACER"`.
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

## Specialized Agents

- **`gbdk-expert`** — GBDK-2020 API, hardware registers, sprites/palettes/interrupts, MBC banking, compilation errors.
- **`gb-c-optimizer`** — C code review for GBC performance/ROM size, anti-pattern detection, SDCC optimization.

## Workflow

This project uses [Superpowers](https://github.com/obra/superpowers) (installed globally in `~/.claude/`).

**Outer loop:** brainstorming → writing-plans → subagent-driven-development
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill)
**Build verification:** `GBDK_HOME=/home/mathdaman/gbdk make` (use `/build` skill)
**PRDs:** saved to `docs/prd/YYYY-MM-DD-<topic>.md`
**Design docs & plans:** saved to `docs/plans/YYYY-MM-DD-<topic>-design.md`

**Smoketest gate:** NEVER commit or create a PR before the user has confirmed a smoketest in the emulator (`mgba-qt build/wasteland-racer.gb`). Always ask and wait for confirmation.
**Branch policy:** NEVER commit directly to `master`. All work goes on a feature branch and merges via PR.
