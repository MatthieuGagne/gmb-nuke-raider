# src/ — C coding rules (loads when editing source)

Authoritative copy with rationale lives in [`docs/dev-workflow.md`](../docs/dev-workflow.md) §4.

## Architecture

`src/main.c` is the entry point and game loop. It contains **only**: frame timing
(`wait_vbl_done()`), input polling (`joypad()`), and state machine dispatch. No game logic lives
inline in `main.c`. If a state handler grows beyond ~10 lines, extract it to a module.

Each game system lives in `src/<system>.c` + `src/<system>.h`. Asset source files (sprites, tiles,
music) live under `assets/` and must be converted to C data arrays before use. Converted headers go
in `src/`. All `.c` files in `src/` are automatically compiled by the Makefile.

There is **no `STATE_*` enum**. A state is a `const State` value (`src/state_manager.h`) holding a
bank plus `enter`/`update`/`exit` function pointers; the modules are `state_title`, `state_overmap`,
`state_hub`, `state_prerace`, `state_playing`, `state_results`, `state_game_over`. `main.c` boots
with `state_push(&state_title, BANK(state_title))`.

## ROM Header

Current flags: `-Wm-yc` (CGB compatible, runs on DMG+GBC), `-Wm-yt25` (MBC5), `-Wm-yn"NUKERAIDER"`.
To target GBC-only (access extra VRAM bank, 8 BG/OBJ palettes): swap `-Wm-yc` for `-Wm-yC`.

## Scalability Conventions (every feature, no matter how small)

- **Module structure:** each system gets its own `.c`/`.h` pair. New-module checklist: public API in `.h`, all state `static` in `.c`, `tests/test_<system>.c` written first (TDD), `gb-c-optimizer` review before merge — dispatched by the controller after the commit (#633 R5).
- **Entity management:** no singletons for things that could multiply — fixed-size pools with an `active` flag. Use **Structure-of-Arrays (SoA)**, not Array-of-Structs (AoS). Capacity constants live in `src/config.h`.
  ```c
  /* SoA canonical template — one array per field */
  #define MAX_ENEMIES 8
  static uint8_t enemy_x[MAX_ENEMIES];
  static uint8_t enemy_y[MAX_ENEMIES];
  static uint8_t enemy_active[MAX_ENEMIES];
  static uint8_t enemy_type[MAX_ENEMIES];
  ```
- **Refactor checkpoint (before closing any task):** "Does this generalize, or did we hard-code something that breaks when N > 1?" If hard-coded and not fixing now → open a follow-up issue.
- **YAGNI balance:** don't pre-build systems for nonexistent features; DO apply the entity-pool pattern at first instance (not second).

## State Machine Rules

Three legal transitions (defined in `src/state_manager.c`, `STACK_MAX = 2`):

| Call | Effect | Use when |
|------|--------|----------|
| `state_push(const State *s, uint8_t bank)` | depth +1 | Entering a sub-state (e.g. overmap → prerace) |
| `state_pop(void)` | depth -1 | Returning to the previous state (e.g. game_over → overmap) |
| `state_replace(const State *s, uint8_t bank)` | depth unchanged | Lateral swap at the same level (e.g. prerace → playing) |

**WARNING: `state_replace` never reduces stack depth.** Using it to "go back" is a silent bug — the stack leaks one slot per navigation cycle. With `STACK_MAX = 2`, a leaked slot means the next `state_push` silently no-ops (push skipped, no error, no crash).

Canonical race path: `title(0) → overmap(0) → prerace(+1=1) → playing(1) → game_over(1) → state_pop() → overmap(0)`

`state_results` already uses `state_pop()` — follow this pattern for any "race ended" transition.

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

## Memory budgets

- OAM: hardware cap is 40 sprites, but the pool is `MAX_SPRITES = 32` (`src/config.h`). Player
  claims slots 0-3 (16x16 quad: TL/BL/TR/BR), `DIALOG_ARROW_OAM_SLOT = 4` is fixed; budget the
  rest for projectiles (≤8), turrets (≤8) and the lazy racer pool
- VRAM: 192 tiles (DMG bank 0) + 192 (CGB bank 1 for color variants)
- WRAM: 8 KB — large arrays must be global or `static`, never local
- ROM: MBC5, 512 KB = 32 banks — auto-sized by makebin (an lcc-internal behaviour; there is no `-yo` flag in the Makefile to grep for), recorded in cartridge header byte `0x148`, and read from there by `tools/bank_post_build.py`. **Not** declared by `-Wm-ya32`: `-ya` is makebin's RAM bank count and that value is discarded. Assets are tagged for banking, and `-autobank` spills code past bank 0 into the autobank pool, banks 1-29 (state code lives in banks 2-3). Two banks are pinned by hand instead: 31 for `src/music_data.c`, 30 for `src/debug.c` (the debug-ROM-only test command mailbox, #590)

## GBDK / SDCC constraints

- **No compound literals**: SDCC rejects `(const uint16_t[]){...}` — use named `static const` arrays.
- **`printf`** requires `#include <stdio.h>`, not just `<gbdk/console.h>`.
- **No `malloc`/`free`**: static allocation only.
- **No `float`/`double`**: use fixed-point integers.
- **Large local arrays** (>~64 bytes) risk stack overflow — use `static` or global.
- Prefer `uint8_t` loop counters over `int`.
- All VRAM writes must occur during VBlank; use `wait_vbl_done()` or a VBlank ISR.
- Only bank-0 files (no `#pragma bank`) may call `SET_BANK` / `SWITCH_ROM`.
- Warning "conditional flow changed by optimizer: so said EVELYN" is harmless.
