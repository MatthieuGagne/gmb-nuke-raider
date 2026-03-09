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

These apply to every feature, no matter how small. Full rationale in `docs/plans/2026-03-09-scalability-design.md`.

**Module structure:**
- Each system gets its own `.c`/`.h` pair; new module checklist: public API in `.h`, all state `static` in `.c`, `tests/test_<system>.c` written first (TDD), `gb-c-optimizer` review before merge.

**Entity management:**
- No singletons for things that could multiply. Use fixed-size pools with an `active` flag.
- Capacity constants live in `src/config.h` — the single place to tune memory vs. features.
  ```c
  #define MAX_ENEMIES 8
  typedef struct { uint8_t x, y, active, type; } Enemy;
  static Enemy enemies[MAX_ENEMIES];
  ```

**Memory budgets:**
- OAM: 40 sprites total (player = 1; budget the rest for enemies/projectiles/HUD)
- VRAM: 192 tiles (DMG bank 0) + 192 (CGB bank 1 for color variants)
- WRAM: 8 KB — large arrays must be global or `static`, never local
- ROM: MBC1 up to 1 MB — assets tagged for banking, code stays in bank 0

**Refactor checkpoint — required before closing any task:**
> "Does this implementation generalize, or did we hard-code something that breaks when N > 1?"
> If hard-coded and not fixing now → open a follow-up issue immediately.

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

**Outer loop:** brainstorming → PRD (`/prd`) → [separate session] writing-plans → subagent-driven-development
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill)
**Build verification:** `GBDK_HOME=/home/mathdaman/gbdk make` (use `/build` skill)
**PRDs & design docs:** GitHub issues only — no local files. Use `/prd` skill.

**Smoketest gate:** NEVER commit or create a PR before the user has confirmed a smoketest in the emulator (`java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb`). Always ask and wait for confirmation.
**Branch policy:** NEVER commit directly to `master`. All work goes on a feature branch and merges via PR.
