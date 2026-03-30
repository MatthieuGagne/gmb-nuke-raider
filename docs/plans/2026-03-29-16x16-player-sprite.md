# 16×16 Player Car Sprite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the player car from a 2-tile 8×16 sprite to a 4-tile 2×2 grid (16×16), with 8-directional lookup-table rendering, a matching 16×16 collision hitbox, and corrected OAM/tile slot constants.

**Architecture:** Replace the two static slot variables and `DIR_TILE_TOP`/`DIR_FLIPX` tables with a 4-element slot array and four SoA tile-index tables (one per 2×2 position) plus a single flip table. Config constants shift to accommodate 16 player tiles. A separate task fixes `state_hub.c`'s hardcoded player-slot cleanup.

**Tech Stack:** GBDK-2020, SDCC, Aseprite CLI, `png_to_tiles.py` (Makefile-driven), Unity (host-side tests).

## Open questions (must resolve before starting)

None — all resolved in grill-me session.

---

## Progress (2026-03-29 session)

**DONE — branch:** `worktree-feat-240-16x16-player-sprite`

| Task | Status | Commit |
|------|--------|--------|
| Task 1: 64×16 sprite PNG | ✅ DONE | `97b8ed4` art: redesign player_car as 64x16 sheet |
| Task 2: config.h constants | ✅ DONE | `155649a` chore: update config.h for 16x16 player |
| Task 3: test_player.c RED | ✅ DONE | `6e03f7f` test: update test_player for 16x16 (RED) |
| Task 4: player.c GREEN | ✅ DONE | `b017d7f` feat: rewrite player for 16x16 2x2 OAM grid (GREEN) |
| Task 5: state_hub.c fix | ⬜ TODO | — |

**Resume here:** Start with **Task 5** (Batch 3). Then run **Smoketest Checkpoint 2** (drive in all 8 directions), then **Smoketest Checkpoint 3** (hub entry, no ghost sprites). Then finish with `finishing-a-development-branch`.

**Notes from this session:**
- PNG must be saved as indexed/palette mode (color_type=3, bit_depth=8), NOT RGB — `png_to_tiles.py`'s Sub filter decompression only works correctly for 1-byte-per-pixel. Pillow's RGB PNG uses Sub filter which the tool misparses.
- `test_player_physics.c:test_wall_zeros_vx_not_vy` was updated: old position px=136 was off-road with 16×16 hitbox; corrected to px=128.
- `PLAYER_ACCEL`, `PLAYER_FRICTION`, `PLAYER_MAX_SPEED`, `PLAYER_REVERSE_MAX_SPEED` now have `u` suffixes in config.h (gb-c-optimizer finding).
- `decode_dir` simplified to direct bit-tests (no intermediate bool variables).

---

## Batch 1 — Sprite art + config constants

### Task 1: Author 64×16 Aseprite sprite and export PNG ✅ DONE

**Files:**
- Modify: `assets/sprites/player_car.aseprite`
- Modify: `assets/sprites/player_car.png`

**Depends on:** none
**Parallelizable with:** Task 2

**Step 1: Invoke the `aseprite` skill**

Invoke the `aseprite` skill before running any `aseprite` CLI command.

**Step 2: Redesign the canvas**

Open `assets/sprites/player_car.aseprite` in Aseprite. Resize canvas to **64×16 pixels**.
Lay out four 16×16 direction sets left-to-right:

| x offset | Direction set | Notes |
|----------|---------------|-------|
| 0–15     | UP            | Hood (front) at top, exhaust at bottom |
| 16–31    | RIGHT         | Hood at right, exhaust at left |
| 32–47    | UP-RIGHT      | Hood at top-right diagonal corner |
| 48–63    | DOWN-RIGHT    | Hood at bottom-right diagonal corner |

Visual requirements (AC2):
- Each direction set must have a clear front/back distinction (e.g., front bumper detail, windscreen, or color band at the hood end — exhaust or engine detail at the rear).
- Use directional arrows (↑, →, ↗, ↘) as placeholder overlays if full art is not ready.
- Limit to 4 colors (2bpp GB palette: white, light grey, dark grey, black).

**Tile column order within each 16×16 set** (must match `png_to_tiles.py` column-first scan):
```
TL (col 0, row 0) | TR (col 1, row 0)
BL (col 0, row 1) | BR (col 1, row 1)
```
`png_to_tiles.py` iterates `tx` (column) outer, `ty` (row) inner → tile 0=TL, tile 1=BL, tile 2=TR, tile 3=BR per set.

**Step 3: Export PNG**

Export the flattened sprite as `assets/sprites/player_car.png` (64×16, indexed/RGBA).

Using Aseprite CLI (after invoking `aseprite` skill for exact flags):
```bash
aseprite -b assets/sprites/player_car.aseprite --save-as assets/sprites/player_car.png
```

**Step 4: Verify**

```bash
file assets/sprites/player_car.png
```
Expected: PNG image data, 64 x 16.

**Step 5: Commit**

```bash
git add assets/sprites/player_car.aseprite assets/sprites/player_car.png
git commit -m "art: redesign player_car as 64x16 sheet with 4 direction sets"
```

---

### Task 2: Update config.h — tile constants, OAM slot, and comment ✅ DONE

**Files:**
- Modify: `src/config.h`

**Depends on:** none
**Parallelizable with:** Task 1

**Step 1: Write the failing test**

No direct unit test for `config.h` constants — the test coverage comes from Task 3 (player tests that use these constants). Skip to Step 2.

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `src/config.h` has no bank entry (it is a header only, never compiled as its own TU) — this gate is satisfied. Do NOT add config.h to bank-manifest.json.

**Step 3: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm all new constants fit in `uint8_t` and that `DIALOG_ARROW_OAM_SLOT = 4u` does not conflict with any GBDK-internal OAM slot reservation.

**Step 4: Apply the diff to `src/config.h`**

Replace lines 8–19 (OAM budget comment + player tile constants + dialog constants) with:

```c
/* OAM budget: player=4 (2x2 grid), slot 4=dialog_arrow HUD, remaining=11 for projectiles */
#define MAX_SPRITES  16

/* Sprite VRAM tile slots — player car occupies tiles 0-15 (4 direction sets × 4 tiles each).
 * png_to_tiles.py column-first order per 16x16 set: tile+0=TL, +1=BL, +2=TR, +3=BR. */
#define PLAYER_TILE_UP_BASE        0u  /* tiles  0-3:  UP direction set        */
#define PLAYER_TILE_RIGHT_BASE     4u  /* tiles  4-7:  RIGHT direction set      */
#define PLAYER_TILE_UPRIGHT_BASE   8u  /* tiles  8-11: UP-RIGHT direction set   */
#define PLAYER_TILE_DOWNRIGHT_BASE 12u /* tiles 12-15: DOWN-RIGHT direction set */
#define DIALOG_ARROW_TILE_BASE    16u  /* tile  16:    dialog overflow arrow    */

/* OAM slot assignments (fixed HUD sprites — after player's 4 pool slots 0-3) */
#define DIALOG_ARROW_OAM_SLOT      4u  /* OAM slot 4 — hub dialog overflow indicator */
```

Also update the `PROJ_TILE_BASE` line (currently line 72):

```c
#define PROJ_TILE_BASE       17u    /* VRAM sprite tile slot — after dialog arrow (16) */
```

**Step 5: Verify**

```bash
grep -E "PLAYER_TILE|DIALOG_ARROW|PROJ_TILE_BASE" src/config.h
```
Expected: shows the new constant names and values (0, 4, 8, 12, 16, 17, OAM slot 4).

**Step 6: HARD GATE — build**

Invoke the `build` skill: `GBDK_HOME=/home/mathdaman/gbdk make`.
Expected: zero errors (existing code uses the old constant names — it will fail to compile if any file still references `PLAYER_TILE_T` etc. Those renames happen in Task 4; they're parallel to this task, so build gate runs after Task 4).

> **Note for executor:** This build gate runs as part of Smoketest Checkpoint 1, after both Task 1 and Task 2 complete. Do not run it mid-task.

**Step 7: Commit**

```bash
git add src/config.h
git commit -m "chore: update config.h for 16x16 player — shift tile/OAM slot constants"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files, no shared state |
| B (sequential) | Smoketest build | Depends on both Task 1 (PNG) and Task 2 (config.h) completing first; `make` auto-regenerates `src/player_sprite.c` |

### Smoketest Checkpoint 1 — ROM builds; player_sprite.c has 16 tiles; no crash

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.
`src/player_sprite.c` is regenerated by `png_to_tiles.py` — confirm `player_tile_data_count = 16` in the generated file.

> **Note:** The build will fail if `player.c` still references `PLAYER_TILE_T`/`PLAYER_TILE_RT`/`PLAYER_TILE_R`/`PLAYER_TILE_RB` after Task 2's config.h rename. Tasks 1–2 and 3–4 MUST both complete before running this smoketest. If working sequentially: complete Batch 1 (Tasks 1+2) first, then expect a build error from player.c — that's the signal to proceed to Batch 2 immediately.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Ask user: "ROM launched. Do you see the game start without a crash? Player sprite may render incorrectly until Task 4 is complete — that is expected."

---

## Batch 2 — TDD: tests then player.c rewrite

### Task 3: Update tests/test_player.c — failing tests for 16×16 behavior ✅ DONE

**Files:**
- Modify: `tests/test_player.c`

**Depends on:** Task 2 (new constant names used in tests)
**Parallelizable with:** none

**Step 1: Check mock infrastructure for sprite tile tracking**

```bash
grep -r "mock_sprite_tile\|set_sprite_tile" tests/mocks/
```

If `mock_sprite_tile[]` does not exist, add it to the mock `gb.h` or equivalent mock source:
```c
/* in tests/mocks/gb.h or mock_gb.c */
extern uint8_t mock_sprite_tile[40];  /* indexed by OAM slot */

/* in set_sprite_tile mock implementation */
void set_sprite_tile(uint8_t nb, uint8_t tile) {
    mock_sprite_tile[nb] = tile;
}
```

**Step 2: Write all failing tests**

Replace/update the following existing tests and add new ones in `tests/test_player.c`:

```c
/* --- sprite slot count (updated: 4 slots) -------------------------------- */

void test_player_init_claims_four_sprite_slots(void) {
    /* setUp called player_init(); it should have claimed slots 0-3.
     * The next free slot must be 4. */
    uint8_t next = get_sprite();
    TEST_ASSERT_EQUAL_UINT8(4u, next);
}

/* --- four-sprite render -------------------------------------------------- */

void test_player_render_calls_move_sprite_four_times(void) {
    mock_move_sprite_reset();
    player_render();
    TEST_ASSERT_EQUAL_INT(4, mock_move_sprite_call_count);
}

void test_player_render_2x2_grid_layout(void) {
    /* TL and BL share same X; TR and BR share same X = TL_x + 8.
     * TL and TR share same Y; BL and BR share same Y = TL_y + 8. */
    mock_move_sprite_reset();
    player_render();
    /* Slots: 0=TL, 1=BL, 2=TR, 3=BR */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_x[0], mock_sprite_x[1]);           /* TL.x == BL.x */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_x[2], mock_sprite_x[3]);           /* TR.x == BR.x */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_x[0] + 8u, mock_sprite_x[2]);     /* TR.x == TL.x+8 */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_y[0], mock_sprite_y[2]);           /* TL.y == TR.y */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_y[1], mock_sprite_y[3]);           /* BL.y == BR.y */
    TEST_ASSERT_EQUAL_UINT8(mock_sprite_y[0] + 8u, mock_sprite_y[1]);     /* BL.y == TL.y+8 */
}

/* --- direction → tile mapping ------------------------------------------- */

void test_dir_T_tile_tl_is_up_base(void) {
    /* DIR_T: no flip, TL slot uses PLAYER_TILE_UP_BASE + 0 */
    mock_move_sprite_reset();
    player_apply_physics(J_UP, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 0u, mock_sprite_tile[0]);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 1u, mock_sprite_tile[1]);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 2u, mock_sprite_tile[2]);
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 3u, mock_sprite_tile[3]);
}

void test_dir_B_tile_tl_is_up_bl_with_flipy(void) {
    /* DIR_B = UP + FLIPY + row-swap: TL slot gets UP's BL tile, flip = S_FLIPY */
    mock_move_sprite_reset();
    player_apply_physics(J_DOWN, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 1u, mock_sprite_tile[0]); /* TL = UP BL */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 0u, mock_sprite_tile[1]); /* BL = UP TL */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 3u, mock_sprite_tile[2]); /* TR = UP BR */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_UP_BASE + 2u, mock_sprite_tile[3]); /* BR = UP TR */
    TEST_ASSERT_EQUAL_UINT8(S_FLIPY, mock_sprite_prop[0]);
}

void test_dir_L_tile_tl_is_right_tr_with_flipx(void) {
    /* DIR_L = RIGHT + FLIPX + col-swap: TL slot gets RIGHT's TR tile, flip = S_FLIPX */
    mock_move_sprite_reset();
    player_apply_physics(J_LEFT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 2u, mock_sprite_tile[0]); /* TL = R TR */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 3u, mock_sprite_tile[1]); /* BL = R BR */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 0u, mock_sprite_tile[2]); /* TR = R TL */
    TEST_ASSERT_EQUAL_UINT8(PLAYER_TILE_RIGHT_BASE + 1u, mock_sprite_tile[3]); /* BR = R BL */
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, mock_sprite_prop[0]);
}

void test_dir_R_no_flip(void) {
    player_apply_physics(J_RIGHT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_prop[0]);
}

void test_dir_RB_no_flip(void) {
    player_apply_physics(J_DOWN | J_RIGHT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(0u, mock_sprite_prop[0]);
}

void test_dir_LB_flipx(void) {
    player_apply_physics(J_DOWN | J_LEFT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, mock_sprite_prop[0]);
}

void test_dir_LT_flipx(void) {
    player_apply_physics(J_UP | J_LEFT, TILE_ROAD);
    player_render();
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, mock_sprite_prop[0]);
}

/* --- 16x16 hitbox: corners at +15, not +7 -------------------------------- */

void test_player_blocked_by_right_wall_16px(void) {
    /* Right corner = px+15. Road cols 6-17 (x=48-143). Col 16 starts at x=128. */
    /* px=112: right corner = 127 (col 15, road). Moving right: px=113, corner=128 → blocked */
    player_set_pos(112, 80);
    input = J_RIGHT | J_A;
    player_update();
    TEST_ASSERT_EQUAL_INT16(112, player_get_x());
}

/* --- screen X clamp [0, 144] (= 160-16) ---------------------------------- */

void test_player_clamped_at_screen_right_16px(void) {
    player_set_pos(144, 80);
    input = J_RIGHT | J_A;
    player_update();  /* new_px=145 > 144 -> blocked */
    TEST_ASSERT_EQUAL_INT16(144, player_get_x());
}

/* --- map Y clamp [0, MAP_PX_H-16] ---------------------------------------- */

void test_player_clamped_at_bottom_map_bound_16px(void) {
    player_set_pos(80, (int16_t)(MAP_PX_H - 16u));
    input = J_DOWN;
    player_update();  /* new_py = MAP_PX_H-15 > MAP_PX_H-16 -> blocked */
    TEST_ASSERT_EQUAL_INT16((int16_t)(MAP_PX_H - 16u), player_get_y());
}

void test_player_moves_near_bottom_map_bound(void) {
    /* MAP_PX_H - 16 = 784. Player at 785, gas north: new_py=784 <= 784 -> allowed */
    player_set_pos(80, (int16_t)(MAP_PX_H - 15u));
    input = J_UP;
    player_update();
    TEST_ASSERT_EQUAL_INT16((int16_t)(MAP_PX_H - 16u), player_get_y());
}
```

Also **update** these existing tests (they test old behavior that changes):

- Rename `test_player_init_claims_two_sprite_slots` → `test_player_init_claims_four_sprite_slots` (see new version above).
- Rename `test_player_render_calls_move_sprite_twice` → `test_player_render_calls_move_sprite_four_times` (see above).
- Rename `test_player_render_both_halves_aligned` → `test_player_render_2x2_grid_layout` (see above).
- Update `test_player_clamped_at_screen_right`: change `player_set_pos(159, 80)` to `player_set_pos(144, 80)` (use new version above instead).
- Update `test_player_blocked_by_right_wall`: change to `test_player_blocked_by_right_wall_16px` (see above).
- Update `test_player_moves_above_old_screen_bottom`: replace with `test_player_moves_near_bottom_map_bound` and `test_player_clamped_at_bottom_map_bound_16px` (see above).
- Add `mock_sprite_prop[]` mock (similar to `mock_sprite_tile[]`) if not already present.

Also add/update RUN_TEST registrations in `main()` to match all renamed and new tests.

**Step 3: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — undefined reference to new mock functions, or assertion failures in updated test expectations.

**Step 4: Commit (failing tests)**

```bash
git add tests/test_player.c
git commit -m "test: update test_player for 16x16 OAM grid, hitbox, and tile mapping (RED)"
```

---

### Task 4: Rewrite player.c + rename PLAYER_TILE_* constants in config.h ✅ DONE

**Files:**
- Modify: `src/player.c`
- Modify: `src/config.h` (remove old PLAYER_TILE_T/RT/R/RB constants — already replaced in Task 2)

**Depends on:** Task 2, Task 3
**Parallelizable with:** none (TDD: Task 3 must be RED first)

**Step 1: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Verify `bank-manifest.json` has `"src/player.c": {"bank": 255, "reason": "autobank"}`. No new entry needed.

**Step 2: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm:
- `static uint8_t player_sprite_slot[4]` is valid SDCC static array syntax.
- `set_sprite_prop(slot, S_FLIPY)` is the correct GBDK API call.
- No `float`, `malloc`, or compound literals in the new code.

**Step 3: Write minimal implementation**

Replace the body of `src/player.c` with the following (keep `#pragma bank 255` and all includes):

```c
#pragma bank 255
#include <gb/gb.h>
#include "input.h"
#include "player.h"
#include "banking.h"
#include "track.h"
#include "camera.h"
#include "loader.h"
#include "sprite_pool.h"
#include "config.h"
#include "damage.h"
#include "projectile.h"

static int16_t px;
static int16_t py;
static int8_t  vx;
static int8_t  vy;
static uint8_t player_sprite_slot[4];  /* 0=TL, 1=BL, 2=TR, 3=BR */
static uint8_t player_flicker_tick;
static player_dir_t player_dir = DIR_T;

/* Direction → velocity delta tables. Indexed by player_dir_t (0=T..7=LT). */
static const int8_t DIR_DX[8] = {  0,  1,  1,  1,  0, -1, -1, -1 };
static const int8_t DIR_DY[8] = { -1, -1,  0,  1,  1,  1,  0, -1 };

/* Direction → tile index for each 2×2 OAM position.
 * Derived directions use col-swap (FLIPX) or row-swap (FLIPY).
 * Tile layout per 16×16 set: base+0=TL, base+1=BL, base+2=TR, base+3=BR. */
static const uint8_t DIR_TILE_TL[8] = {
    PLAYER_TILE_UP_BASE        + 0u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 0u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 0u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 0u, /* RB */
    PLAYER_TILE_UP_BASE        + 1u, /* B  = UP FLIPY+row-swap → TL gets UP BL */
    PLAYER_TILE_DOWNRIGHT_BASE + 2u, /* LB = DR FLIPX+col-swap → TL gets DR TR */
    PLAYER_TILE_RIGHT_BASE     + 2u, /* L  = R  FLIPX+col-swap → TL gets R  TR */
    PLAYER_TILE_UPRIGHT_BASE   + 2u, /* LT = UR FLIPX+col-swap → TL gets UR TR */
};
static const uint8_t DIR_TILE_BL[8] = {
    PLAYER_TILE_UP_BASE        + 1u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 1u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 1u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 1u, /* RB */
    PLAYER_TILE_UP_BASE        + 0u, /* B  → BL gets UP TL */
    PLAYER_TILE_DOWNRIGHT_BASE + 3u, /* LB → BL gets DR BR */
    PLAYER_TILE_RIGHT_BASE     + 3u, /* L  → BL gets R  BR */
    PLAYER_TILE_UPRIGHT_BASE   + 3u, /* LT → BL gets UR BR */
};
static const uint8_t DIR_TILE_TR[8] = {
    PLAYER_TILE_UP_BASE        + 2u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 2u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 2u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 2u, /* RB */
    PLAYER_TILE_UP_BASE        + 3u, /* B  → TR gets UP BR */
    PLAYER_TILE_DOWNRIGHT_BASE + 0u, /* LB → TR gets DR TL */
    PLAYER_TILE_RIGHT_BASE     + 0u, /* L  → TR gets R  TL */
    PLAYER_TILE_UPRIGHT_BASE   + 0u, /* LT → TR gets UR TL */
};
static const uint8_t DIR_TILE_BR[8] = {
    PLAYER_TILE_UP_BASE        + 3u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 3u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 3u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 3u, /* RB */
    PLAYER_TILE_UP_BASE        + 2u, /* B  → BR gets UP TR */
    PLAYER_TILE_DOWNRIGHT_BASE + 1u, /* LB → BR gets DR BL */
    PLAYER_TILE_RIGHT_BASE     + 1u, /* L  → BR gets R  BL */
    PLAYER_TILE_UPRIGHT_BASE   + 1u, /* LT → BR gets UR BL */
};
static const uint8_t DIR_FLIP[8] = {
    0u,      /* T  */
    0u,      /* RT */
    0u,      /* R  */
    0u,      /* RB */
    S_FLIPY, /* B  */
    S_FLIPX, /* LB */
    S_FLIPX, /* L  */
    S_FLIPX, /* LT */
};

/* Returns 1 if all 4 corners of the 16×16 hitbox at (wx, wy) are on track. */
static uint8_t corners_passable(int16_t wx, int16_t wy) {
    return track_passable(wx,        wy) &&
           track_passable(wx + 15,   wy) &&
           track_passable(wx,        wy + 15) &&
           track_passable(wx + 15,   wy + 15);
}

void player_init(void) BANKED {
    SPRITES_8x8;
    sprite_pool_init();
    player_sprite_slot[0] = get_sprite();  /* TL */
    player_sprite_slot[1] = get_sprite();  /* BL */
    player_sprite_slot[2] = get_sprite();  /* TR */
    player_sprite_slot[3] = get_sprite();  /* BR */
    load_player_tiles();
    set_sprite_tile(player_sprite_slot[0], 0u);
    set_sprite_tile(player_sprite_slot[1], 1u);
    set_sprite_tile(player_sprite_slot[2], 2u);
    set_sprite_tile(player_sprite_slot[3], 3u);
    load_track_start_pos(&px, &py);
    vx = 0;
    vy = 0;
    player_dir = DIR_T;
    player_flicker_tick = 0u;
    SHOW_SPRITES;
}

void player_update(void) BANKED {
    int16_t new_px;
    int16_t new_py;
    TileType terrain;

    damage_tick();

    /* Query terrain at 16×16 centre */
    terrain = track_tile_type((int16_t)(px + 8), (int16_t)(py + 8));
    player_apply_physics(input, terrain);

    /* Fire: spawn projectile from visual centre of 16×16 car */
    if (KEY_PRESSED(J_A)) {
        uint8_t scr_x = (uint8_t)((int16_t)px + 16);
        uint8_t scr_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 24);
        projectile_fire(scr_x, scr_y, player_dir);
    }

    /* Apply X velocity — X clamp: [0, 144] (= 160 - 16) */
    new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 && new_px <= 144 && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        vx = 0;
        damage_apply(1u);
    }

    /* Apply Y velocity — Y clamp: [0, MAP_PX_H - 16] */
    new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= 0 && new_py <= (int16_t)(MAP_PX_H - 16u) && corners_passable(px, new_py)) {
        py = new_py;
    } else {
        vy = 0;
        damage_apply(1u);
    }

    if (terrain == TILE_REPAIR) {
        damage_heal(DAMAGE_REPAIR_AMOUNT);
    }
}

void player_render(void) BANKED {
    uint8_t hw_x = (uint8_t)(px + 8u);
    uint8_t hw_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 16);
    uint8_t flip = DIR_FLIP[player_dir];

    set_sprite_tile(player_sprite_slot[0], DIR_TILE_TL[player_dir]);
    set_sprite_tile(player_sprite_slot[1], DIR_TILE_BL[player_dir]);
    set_sprite_tile(player_sprite_slot[2], DIR_TILE_TR[player_dir]);
    set_sprite_tile(player_sprite_slot[3], DIR_TILE_BR[player_dir]);
    set_sprite_prop(player_sprite_slot[0], flip);
    set_sprite_prop(player_sprite_slot[1], flip);
    set_sprite_prop(player_sprite_slot[2], flip);
    set_sprite_prop(player_sprite_slot[3], flip);

    player_flicker_tick++;
    if (damage_get_hp() <= 20u && (player_flicker_tick & 8u)) {
        move_sprite(player_sprite_slot[0], 0u, 0u);
        move_sprite(player_sprite_slot[1], 0u, 0u);
        move_sprite(player_sprite_slot[2], 0u, 0u);
        move_sprite(player_sprite_slot[3], 0u, 0u);
    } else {
        move_sprite(player_sprite_slot[0], hw_x,                     hw_y);
        move_sprite(player_sprite_slot[1], hw_x,                     (uint8_t)(hw_y + 8u));
        move_sprite(player_sprite_slot[2], (uint8_t)(hw_x + 8u),     hw_y);
        move_sprite(player_sprite_slot[3], (uint8_t)(hw_x + 8u),     (uint8_t)(hw_y + 8u));
    }
}

void player_set_pos(int16_t x, int16_t y) BANKED { px = x; py = y; }
int16_t player_get_x(void) BANKED  { return px; }
int16_t player_get_y(void) BANKED  { return py; }
int8_t  player_get_vx(void) BANKED { return vx; }
int8_t  player_get_vy(void) BANKED { return vy; }

void player_reset_vel(void) BANKED { vx = 0; vy = 0; }

static player_dir_t decode_dir(uint8_t buttons) {
    uint8_t up    = (buttons & J_UP)    ? 1u : 0u;
    uint8_t down  = (buttons & J_DOWN)  ? 1u : 0u;
    uint8_t left  = (buttons & J_LEFT)  ? 1u : 0u;
    uint8_t right = (buttons & J_RIGHT) ? 1u : 0u;
    if (up   && right) return DIR_RT;
    if (down && right) return DIR_RB;
    if (down && left)  return DIR_LB;
    if (up   && left)  return DIR_LT;
    if (up)    return DIR_T;
    if (right) return DIR_R;
    if (down)  return DIR_B;
    if (left)  return DIR_L;
    return player_dir;
}

player_dir_t player_get_dir(void) BANKED { return player_dir; }
int8_t player_dir_dx(player_dir_t dir) BANKED { return DIR_DX[dir]; }
int8_t player_dir_dy(player_dir_t dir) BANKED { return DIR_DY[dir]; }

void player_apply_physics(uint8_t buttons, TileType terrain) BANKED {
    uint8_t i;
    uint8_t fric_x;
    uint8_t fric_y;
    uint8_t gas;

    player_dir = decode_dir(buttons);
    gas = (terrain != TILE_OIL && (buttons & (J_UP | J_DOWN | J_LEFT | J_RIGHT))) ? 1u : 0u;

    if (terrain == TILE_SAND) {
        fric_x = (gas && DIR_DX[player_dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = (gas && DIR_DY[player_dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
    } else if (terrain == TILE_OIL) {
        fric_x = 0u;
        fric_y = 0u;
    } else {
        fric_x = (gas && DIR_DX[player_dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
        fric_y = (gas && DIR_DY[player_dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
    }

    for (i = 0u; i < fric_x; i++) {
        if      (vx > 0) vx = (int8_t)(vx - 1);
        else if (vx < 0) vx = (int8_t)(vx + 1);
    }
    for (i = 0u; i < fric_y; i++) {
        if      (vy > 0) vy = (int8_t)(vy - 1);
        else if (vy < 0) vy = (int8_t)(vy + 1);
    }

    if (gas) {
        vx = (int8_t)(vx + (int8_t)((int8_t)PLAYER_ACCEL * DIR_DX[player_dir]));
        vy = (int8_t)(vy + (int8_t)((int8_t)PLAYER_ACCEL * DIR_DY[player_dir]));
    }

    if (terrain == TILE_BOOST) {
        vy = (int8_t)(vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    {
        uint8_t max_speed = (terrain == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : PLAYER_MAX_SPEED;
        if (vx >  (int8_t)max_speed) vx =  (int8_t)max_speed;
        if (vx < -(int8_t)max_speed) vx = -(int8_t)max_speed;
        if (vy >  (int8_t)max_speed) vy =  (int8_t)max_speed;
        if (vy < -(int8_t)max_speed) vy = -(int8_t)max_speed;
    }
}
```

**Step 4: Run tests to verify they pass**

```bash
make test
```
Expected: PASS — all new and updated test cases pass.

**Step 5: HARD GATE — build**

Invoke the `build` skill: `GBDK_HOME=/home/mathdaman/gbdk make`.
Expected: ROM produced at `build/nuke-raider.gb`, zero errors.

**Step 6: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify bank placements and ROM budgets are within limits.

**Step 7: Refactor checkpoint**

Ask: "Does this implementation generalize, or did I hard-code something that breaks when N > 1?"
- Player entity is a singleton by design — 4 OAM slots hardcoded is intentional.
- If a multi-player or split-screen feature ever appears, open a follow-up issue for a player pool.

**Step 8: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on `src/player.c`. Verify: SoA slot array is acceptable (it's a small fixed array, not an entity pool), no AoS, `uint8_t` loop counters, no wasteful int arithmetic.

**Step 9: Commit**

```bash
git add src/player.c src/config.h tests/test_player.c
git commit -m "feat: rewrite player for 16x16 2x2 OAM grid with lookup table render (GREEN)"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 2

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 3 → Task 4 | TDD: tests must be RED before implementation |

### Smoketest Checkpoint 2 — 16×16 player renders correctly in all 8 directions

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS. OAM: player=4, dialog=1, pool≤16 → total ≤21/40. VRAM: player=16 tiles.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Ask user to verify:
- AC1: Car appears 16×16 in all 8 directions.
- AC2: Front faces the correct direction for all 8 (drive into each direction on the track).
- AC3: FLIPX-mirrored directions (LEFT, UP-LEFT, DOWN-LEFT) are correct mirror images.
- AC4: DOWN direction shows correct FLIPY (front at bottom, not a doubled top).
- AC5: Car collides with walls using the 16×16 hitbox — no clipping through obstacles smaller than 16px.

---

## Batch 3 — Hub state OAM slot fix

### Task 5: Update state_hub.c — clear all 4 player OAM slots

**Files:**
- Modify: `src/state_hub.c`

**Depends on:** Task 2 (DIALOG_ARROW_OAM_SLOT=4 already in config.h)
**Parallelizable with:** none

**Step 1: Write the failing test**

No direct unit test for `state_hub.c` — the hub state is verified in the smoketest. The "failure" is visual: without this fix, player OAM slots 2–3 remain visible (ghosting) when entering the hub. Skip to Step 2.

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Verify `bank-manifest.json` has an entry for `src/state_hub.c`.

**Step 3: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm that calling `move_sprite(n, 0u, 0u)` for n=2 and n=3 is the correct way to hide those OAM slots when the game is in hub state.

**Step 4: Write minimal implementation**

In `src/state_hub.c`, find the player-sprite cleanup block (currently around lines 375–378):

```c
/* BEFORE */
move_sprite(0u, 0u, 0u);
move_sprite(1u, 0u, 0u);
move_sprite(DIALOG_ARROW_OAM_SLOT, 0u, 0u);
```

Replace with:

```c
/* AFTER — clear all 4 player OAM slots (player uses pool slots 0-3) */
move_sprite(0u, 0u, 0u);
move_sprite(1u, 0u, 0u);
move_sprite(2u, 0u, 0u);
move_sprite(3u, 0u, 0u);
move_sprite(DIALOG_ARROW_OAM_SLOT, 0u, 0u);
```

Also grep `state_hub.c` for any other hardcoded references to player OAM slots:
```bash
grep -n "move_sprite(0\|move_sprite(1\|move_sprite(2\|move_sprite(3" src/state_hub.c
```
Update any other instances that are clearing player sprites.

**Step 5: HARD GATE — build**

Invoke the `build` skill: `GBDK_HOME=/home/mathdaman/gbdk make`.
Expected: ROM produced at `build/nuke-raider.gb`, zero errors.

**Step 6: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 7: Refactor checkpoint**

Ask: "Breaks when N > 1?" — Player is singleton; hardcoding slots 0-3 is intentional for this feature. No follow-up issue needed.

**Step 8: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on `src/state_hub.c`. Verify no regressions introduced.

**Step 9: Commit**

```bash
git add src/state_hub.c
git commit -m "fix: clear all 4 player OAM slots on hub entry (16x16 sprite uses slots 0-3)"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 3

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 5 | Only task in batch |

### Smoketest Checkpoint 3 — Hub state: dialog arrow appears; no ghost player sprites

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Ask user to verify:
- Drive to a hub location and enter it.
- No ghost player car sprites visible in the hub dialog screen.
- Dialog overflow arrow (small arrow indicator) appears and disappears correctly when dialog has/lacks overflow.
- Return to the overmap and back to the track — player car renders correctly as 16×16.

---

## Acceptance Criteria Checklist

| AC | Description | Verified by |
|----|-------------|-------------|
| AC1 | Car appears 16×16 in all 8 directions | Smoketest 2 |
| AC2 | Front faces correct direction | Smoketest 2 |
| AC3 | FLIPX-mirrored directions are correct | Smoketest 2 |
| AC4 | DOWN = correct FLIPY (not doubled top) | Smoketest 2 |
| AC5 | 16×16 hitbox — no clipping | Smoketest 2 |
| AC6 | `make test` passes | Task 4, Step 4 |
| AC7 | `make` zero errors | Task 4, Step 5 |
| AC8 | OAM ≤ 21/40 | Smoketest 2 memory-check |
| AC9 | VRAM ≤ 192 tiles | Smoketest 2 memory-check |
