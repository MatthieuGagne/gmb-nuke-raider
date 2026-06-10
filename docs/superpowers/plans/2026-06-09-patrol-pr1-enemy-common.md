# Patrol Feature — PR1: enemy_common Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the shared enemy-AI math (aim direction, direction-from-delta, waypoint reached/advance) out of `turret.c` and `racer.c` into a new `enemy_common` module, then refactor `turret.c` and `racer.c` to call it. This is a **pure refactor with zero behavior change** — it is PR1 of a 4-PR stacked feature (#144) that adds a patrol-vehicle enemy. After this PR the shared helpers are the single source of truth that PR4's `patrol.c` will compose from.

**Architecture:** New `enemy_common.c` (`#pragma bank 255` autobank) exposes exactly four `BANKED` functions:
- `enemy_aim_dir(tx, ty, player_px, player_py)` — verbatim body of `turret_dir_to_pixel`, moved and renamed. Returns a 16-way `player_dir_t`.
- `enemy_dir_from_delta(dx, dy)` — verbatim body of the (formerly `static`) `racer_dir_from_delta`, now exposed. Returns an 8-way `uint8_t` `DIR_*`.
- `enemy_wp_reached(dx, dy, threshold)` — returns 1 if `(uint8_t)(abs(dx)+abs(dy)) < threshold`. Extracted from racer's inline waypoint-reached check.
- `enemy_wp_advance(cur_idx, wp_count, reached)` — if `reached`, returns `(cur_idx+1 >= wp_count) ? 0 : cur_idx+1`; else returns `cur_idx`. Extracted from racer's inline waypoint-advance block.

`turret.c` deletes `turret_dir_to_pixel` (definition + declaration) and calls `enemy_aim_dir` at its one call site. `racer.c` deletes the `static racer_dir_from_delta`, calls `enemy_dir_from_delta`, and replaces the inline waypoint reached/advance block with `enemy_wp_reached` + `enemy_wp_advance`. All `race_state_update_cp` / finish-line logic stays inline in `racer.c` — only the pure waypoint math moves.

**Tech Stack:** C (SDCC/GBDK-2020), Unity test framework, gcc host tests, bank-manifest.json, `#pragma bank 255` autobank.

**Build wiring note (verified):** The Makefile compiles every `src/*.c` into the ROM automatically (`SRCS := $(wildcard src/*.c)`) AND into every test binary automatically (`TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))`, linked into each `tests/test_*.c` by the `test:` rule). Therefore **no per-binary wiring edit is required** — creating `src/enemy_common.c` makes it available to the ROM build and to `test_turret`, `test_racer`, `test_enemy_common`, and all other test binaries automatically. The only registry edit needed is `bank-manifest.json`.

---

## File Structure

| File | Change |
|------|--------|
| `bank-manifest.json` | Add `src/enemy_common.c` entry (`bank 255` autobank) |
| `src/enemy_common.h` | **New** — public API: `enemy_aim_dir`, `enemy_dir_from_delta`, `enemy_wp_reached`, `enemy_wp_advance` (all `BANKED`) |
| `src/enemy_common.c` | **New** — verbatim-moved aim body + dir-from-delta body + new wp reached/advance helpers |
| `src/turret.c` | Remove `turret_dir_to_pixel` definition; `#include "enemy_common.h"`; call `enemy_aim_dir` at the fire site |
| `src/turret.h` | Remove the `turret_dir_to_pixel` declaration |
| `src/racer.c` | Remove `static racer_dir_from_delta`; `#include "enemy_common.h"`; call `enemy_dir_from_delta`; replace inline wp reached/advance block with `enemy_wp_reached` + `enemy_wp_advance` |
| `tests/test_turret.c` | Update the aim tests (~lines 36–81) to call `enemy_aim_dir` instead of `turret_dir_to_pixel`; add `#include "enemy_common.h"` |
| `tests/test_enemy_common.c` | **New** — unit tests for all four functions |

No edits to `src/config.h`, `src/banking.h`, `tests/test_racer.c`, `tests/test_race_scenario.c`, or the Makefile are required.

---

## Task 1: Register `enemy_common.c` in the bank manifest

**Files:**
- Modify: `bank-manifest.json`

- [ ] **Step 1: Add the `enemy_common.c` entry**

Open `bank-manifest.json`. After the `"src/turret.c"` entry (line ~39), add a new line:

```json
  "src/enemy_common.c":          {"bank": 255, "reason": "autobank — shared enemy AI helpers (aim, dir-from-delta, waypoint math)"},
```

The surrounding context after the edit should read:

```json
  "src/turret.c":                {"bank": 255, "reason": "autobank — turret gameplay module called via invoke() in state_manager.c"},
  "src/enemy_common.c":          {"bank": 255, "reason": "autobank — shared enemy AI helpers (aim, dir-from-delta, waypoint math)"},
  "src/turret_sprite.c":         {"bank": 255, "reason": "autobank — loader.c handles BANK(sym) switching"},
```

Verify the JSON is still valid (no trailing comma on the last object key; this entry is mid-object so the trailing comma is correct):

```sh
python -c "import json; json.load(open('bank-manifest.json')); print('OK')"
```

Expected output: `OK`

- [ ] **Step 2: Commit**

```sh
git add bank-manifest.json
git commit -m "$(cat <<'EOF'
chore(banking): register enemy_common.c (bank 255 autobank)

Part of #144

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Write the failing test for `enemy_common`

This is the RED step. We write `tests/test_enemy_common.c` first; it will FAIL to compile because `src/enemy_common.h` does not exist yet. That is the expected failure.

**Files:**
- Create: `tests/test_enemy_common.c`

- [ ] **Step 1: Create `tests/test_enemy_common.c` with the full test suite**

Write the complete file:

```c
/* tests/test_enemy_common.c */
#include "unity.h"
#include "enemy_common.h"
#include "player.h"   /* player_dir_t: DIR_T, DIR_R, DIR_NNE, ... */
#include "config.h"

void setUp(void) {}
void tearDown(void) {}

/* ---- enemy_aim_dir: ported verbatim from the old turret aim cases ---- */

void test_aim_right(void) {
    /* Source at tile (0,0) = pixel (0,0); player at (64,0) -> DIR_R */
    TEST_ASSERT_EQUAL_INT(DIR_R, enemy_aim_dir(0u, 0u, 64, 0));
}
void test_aim_down(void) {
    TEST_ASSERT_EQUAL_INT(DIR_B, enemy_aim_dir(0u, 0u, 0, 64));
}
void test_aim_down_right(void) {
    /* ax==ay==64, toward_x=0, SE quadrant -> DIR_SSE */
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_aim_dir(0u, 0u, 64, 64));
}
void test_aim_up_left(void) {
    /* ax==ay==80, toward_x=0, NW quadrant -> DIR_NNW */
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_aim_dir(10u, 10u, 0, 0));
}
void test_aim_nne(void) {
    TEST_ASSERT_EQUAL_INT(DIR_NNE, enemy_aim_dir(0u, 0u, 10, -15));
}
void test_aim_ene(void) {
    TEST_ASSERT_EQUAL_INT(DIR_ENE, enemy_aim_dir(0u, 0u, 15, -10));
}
void test_aim_ese(void) {
    TEST_ASSERT_EQUAL_INT(DIR_ESE, enemy_aim_dir(0u, 0u, 15, 10));
}
void test_aim_sse(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_aim_dir(0u, 0u, 10, 15));
}
void test_aim_ssw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSW, enemy_aim_dir(0u, 0u, -10, 15));
}
void test_aim_wsw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WSW, enemy_aim_dir(0u, 0u, -15, 10));
}
void test_aim_wnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WNW, enemy_aim_dir(0u, 0u, -15, -10));
}
void test_aim_nnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_aim_dir(0u, 0u, -10, -15));
}

/* ---- enemy_dir_from_delta: one case per 8-way DIR_* ---- */

void test_dir_from_delta_up(void) {
    /* ay>ax, dy<0 -> DIR_T */
    TEST_ASSERT_EQUAL_UINT8(DIR_T, enemy_dir_from_delta(0, -5));
}
void test_dir_from_delta_down(void) {
    /* ay>ax, dy>0 -> DIR_B */
    TEST_ASSERT_EQUAL_UINT8(DIR_B, enemy_dir_from_delta(0, 5));
}
void test_dir_from_delta_left(void) {
    /* ax>ay, dx<0 -> DIR_L */
    TEST_ASSERT_EQUAL_UINT8(DIR_L, enemy_dir_from_delta(-5, 0));
}
void test_dir_from_delta_right(void) {
    /* ax>ay, dx>0 -> DIR_R */
    TEST_ASSERT_EQUAL_UINT8(DIR_R, enemy_dir_from_delta(5, 0));
}
void test_dir_from_delta_up_left(void) {
    /* ax==ay, dy<0 && dx<0 -> DIR_LT */
    TEST_ASSERT_EQUAL_UINT8(DIR_LT, enemy_dir_from_delta(-5, -5));
}
void test_dir_from_delta_up_right(void) {
    /* ax==ay, dy<0 && dx>0 -> DIR_RT */
    TEST_ASSERT_EQUAL_UINT8(DIR_RT, enemy_dir_from_delta(5, -5));
}
void test_dir_from_delta_down_left(void) {
    /* ax==ay, dy>0 && dx<0 -> DIR_LB */
    TEST_ASSERT_EQUAL_UINT8(DIR_LB, enemy_dir_from_delta(-5, 5));
}
void test_dir_from_delta_down_right(void) {
    /* ax==ay, dy>0 && dx>0 (else branch) -> DIR_RB */
    TEST_ASSERT_EQUAL_UINT8(DIR_RB, enemy_dir_from_delta(5, 5));
}

/* ---- enemy_wp_reached: boundary tests around the threshold ---- */

void test_wp_reached_below_threshold(void) {
    /* |3|+|3|=6 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(3, 3, 12u));
}
void test_wp_reached_at_threshold_not_reached(void) {
    /* |6|+|6|=12, NOT < 12 -> not reached */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_reached(6, 6, 12u));
}
void test_wp_reached_just_below_threshold(void) {
    /* |6|+|5|=11 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(6, 5, 12u));
}
void test_wp_reached_just_above_threshold(void) {
    /* |7|+|6|=13, NOT < 12 -> not reached */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_reached(7, 6, 12u));
}
void test_wp_reached_negative_deltas(void) {
    /* abs handles negatives: |-3|+|-3|=6 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(-3, -3, 12u));
}
void test_wp_reached_zero_distance(void) {
    /* 0 < 12 -> reached */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_reached(0, 0, 12u));
}

/* ---- enemy_wp_advance: advance + wrap behavior ---- */

void test_wp_advance_not_reached_keeps_index(void) {
    /* reached=0 -> index unchanged */
    TEST_ASSERT_EQUAL_UINT8(2u, enemy_wp_advance(2u, 4u, 0u));
}
void test_wp_advance_reached_increments(void) {
    /* reached=1, 0+1=1 < 4 -> 1 */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_wp_advance(0u, 4u, 1u));
}
void test_wp_advance_reached_wraps_at_last(void) {
    /* reached=1, 3+1=4 >= 4 -> wrap to 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_advance(3u, 4u, 1u));
}
void test_wp_advance_single_waypoint_wraps_to_self(void) {
    /* count=1: reached=1, 0+1=1 >= 1 -> wrap to 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_wp_advance(0u, 1u, 1u));
}
void test_wp_advance_mid_route(void) {
    /* reached=1, 1+1=2 < 4 -> 2 */
    TEST_ASSERT_EQUAL_UINT8(2u, enemy_wp_advance(1u, 4u, 1u));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_aim_right);
    RUN_TEST(test_aim_down);
    RUN_TEST(test_aim_down_right);
    RUN_TEST(test_aim_up_left);
    RUN_TEST(test_aim_nne);
    RUN_TEST(test_aim_ene);
    RUN_TEST(test_aim_ese);
    RUN_TEST(test_aim_sse);
    RUN_TEST(test_aim_ssw);
    RUN_TEST(test_aim_wsw);
    RUN_TEST(test_aim_wnw);
    RUN_TEST(test_aim_nnw);
    RUN_TEST(test_dir_from_delta_up);
    RUN_TEST(test_dir_from_delta_down);
    RUN_TEST(test_dir_from_delta_left);
    RUN_TEST(test_dir_from_delta_right);
    RUN_TEST(test_dir_from_delta_up_left);
    RUN_TEST(test_dir_from_delta_up_right);
    RUN_TEST(test_dir_from_delta_down_left);
    RUN_TEST(test_dir_from_delta_down_right);
    RUN_TEST(test_wp_reached_below_threshold);
    RUN_TEST(test_wp_reached_at_threshold_not_reached);
    RUN_TEST(test_wp_reached_just_below_threshold);
    RUN_TEST(test_wp_reached_just_above_threshold);
    RUN_TEST(test_wp_reached_negative_deltas);
    RUN_TEST(test_wp_reached_zero_distance);
    RUN_TEST(test_wp_advance_not_reached_keeps_index);
    RUN_TEST(test_wp_advance_reached_increments);
    RUN_TEST(test_wp_advance_reached_wraps_at_last);
    RUN_TEST(test_wp_advance_single_waypoint_wraps_to_self);
    RUN_TEST(test_wp_advance_mid_route);
    return UNITY_END();
}
```

- [ ] **Step 2: Run `make test` from the worktree dir and confirm the EXPECTED FAILURE (RED)**

```sh
make test
```

Expected output: the test build fails to compile `tests/test_enemy_common.c` with an error like `fatal error: enemy_common.h: No such file or directory` (the `test:` rule runs `|| exit 1`, so the run stops on the first failing binary). This is the expected RED state — `enemy_common.h`/`.c` do not exist yet.

- [ ] **Step 3: Commit the failing test**

```sh
git add tests/test_enemy_common.c
git commit -m "$(cat <<'EOF'
test(enemy_common): add failing unit tests for shared enemy helpers

RED: enemy_common.h/.c do not exist yet.

Part of #144

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create `src/enemy_common.h` and `src/enemy_common.c` (GREEN)

> **GB gate:** bank-pre-write hook fires automatically on these Write/Edit calls; consult the `gbdk-expert` agent (implementation mode) for the C — dispatch with `"implement this task: create src/enemy_common.h and src/enemy_common.c per the plan body below"`; build with `make`; bank-post-build hook fires automatically.

**Files:**
- Create: `src/enemy_common.h`
- Create: `src/enemy_common.c`

- [ ] **Step 1: Create `src/enemy_common.h`**

Write the complete file:

```c
#ifndef ENEMY_COMMON_H
#define ENEMY_COMMON_H

#include <stdint.h>
#include "player.h"    /* player_dir_t */
#include "banking.h"   /* BANKED */

/* Shared enemy-AI math used by turret.c, racer.c, and (PR4) patrol.c.
 * All functions are pure (no side effects, no static state). */

/* 16-way aim direction from a source tile toward a player pixel position.
 * tx, ty: source tile coordinates. player_px, player_py: player pixel coords.
 * Returns a player_dir_t (cardinal or one of the 8 intermediate sectors). */
player_dir_t enemy_aim_dir(uint8_t tx, uint8_t ty,
                           int16_t player_px, int16_t player_py) BANKED;

/* 8-way direction from a signed delta. Returns a uint8_t DIR_* value
 * (DIR_T/RT/R/RB/B/LB/L/LT). Diagonals chosen when |dx| == |dy|. */
uint8_t enemy_dir_from_delta(int8_t dx, int8_t dy) BANKED;

/* Returns 1 if the Manhattan distance |dx|+|dy| is strictly below threshold. */
uint8_t enemy_wp_reached(int8_t dx, int8_t dy, uint8_t threshold) BANKED;

/* Returns the next waypoint index. If reached is non-zero, advances cur_idx by
 * one, wrapping to 0 when it would reach wp_count. If reached is zero, returns
 * cur_idx unchanged. */
uint8_t enemy_wp_advance(uint8_t cur_idx, uint8_t wp_count, uint8_t reached) BANKED;

#endif /* ENEMY_COMMON_H */
```

- [ ] **Step 2: Create `src/enemy_common.c`**

`enemy_aim_dir` is the VERBATIM body of `turret_dir_to_pixel` (only the function name changes). `enemy_dir_from_delta` is the VERBATIM body of the old `static racer_dir_from_delta`. Write the complete file:

```c
#pragma bank 255

#include "enemy_common.h"

/* enemy_aim_dir — verbatim body of the former turret_dir_to_pixel(). */
player_dir_t enemy_aim_dir(uint8_t tx, uint8_t ty,
                           int16_t player_px, int16_t player_py) BANKED {
    int16_t dx = player_px - (int16_t)((uint16_t)tx * 8u);
    int16_t dy = player_py - (int16_t)((uint16_t)ty * 8u);
    int16_t ax = dx < 0 ? -dx : dx;
    int16_t ay = dy < 0 ? -dy : dy;
    uint8_t toward_x;

    /* Threshold 1: cardinal E/W — |dx| > 2*|dy| */
    if (ax > (int16_t)(ay << 1)) {
        return dx > 0 ? DIR_R : DIR_L;
    }
    /* Threshold 2: cardinal N/S — |dy| > 2*|dx| */
    if (ay > (int16_t)(ax << 1)) {
        return dy > 0 ? DIR_B : DIR_T;
    }
    /* Threshold 3: intermediate sector — |dx| vs |dy| */
    toward_x = (uint8_t)(ax > ay);
    if (dx >= 0 && dy < 0) { return toward_x ? DIR_ENE : DIR_NNE; }
    if (dx >= 0)            { return toward_x ? DIR_ESE : DIR_SSE; }
    if (dy >= 0)            { return toward_x ? DIR_WSW : DIR_SSW; }
    return toward_x ? DIR_WNW : DIR_NNW;
}

/* enemy_dir_from_delta — verbatim body of the former static racer_dir_from_delta(). */
uint8_t enemy_dir_from_delta(int8_t dx, int8_t dy) BANKED {
    int8_t ax = dx < 0 ? -dx : dx;
    int8_t ay = dy < 0 ? -dy : dy;
    if (ay > ax) {
        return (dy < 0) ? DIR_T : DIR_B;
    } else if (ax > ay) {
        return (dx < 0) ? DIR_L : DIR_R;
    } else {
        /* Diagonal: ax == ay */
        if (dy < 0 && dx < 0) return DIR_LT;
        if (dy < 0 && dx > 0) return DIR_RT;
        if (dy > 0 && dx < 0) return DIR_LB;
        return DIR_RB;
    }
}

/* enemy_wp_reached — Manhattan-distance threshold check. */
uint8_t enemy_wp_reached(int8_t dx, int8_t dy, uint8_t threshold) BANKED {
    uint8_t abs_dx = (uint8_t)(dx < 0 ? -dx : dx);
    uint8_t abs_dy = (uint8_t)(dy < 0 ? -dy : dy);
    return ((uint8_t)(abs_dx + abs_dy) < threshold) ? 1u : 0u;
}

/* enemy_wp_advance — advance/wrap a waypoint index when reached. */
uint8_t enemy_wp_advance(uint8_t cur_idx, uint8_t wp_count, uint8_t reached) BANKED {
    if (reached) {
        uint8_t next = (uint8_t)(cur_idx + 1u);
        return (next >= wp_count) ? 0u : next;
    }
    return cur_idx;
}
```

- [ ] **Step 3: Run `make test` and confirm `test_enemy_common` PASSES (GREEN)**

```sh
make test
```

Expected output: `build/test_enemy_common` compiles and runs; all tests in it report `OK` (Unity prints a final `XX Tests 0 Failures 0 Ignored` line). The whole `make test` run should now proceed past `test_enemy_common`. (Note: `test_racer`/`test_turret` may still fail at this point only if their compilation now sees a duplicate symbol — it will not, because `enemy_common.c` defines new names and we have not yet removed the old definitions; the old `turret_dir_to_pixel` and `racer_dir_from_delta` still exist. All suites should be green here.)

- [ ] **Step 4: Build the ROM to confirm SDCC compiles the new module**

```sh
make
```

Expected output: clean build, ROM at `build/nuke-raider.gb`. bank-post-build + `make memory-check` hooks fire automatically; confirm no FAIL/ERROR.

- [ ] **Step 5: Commit**

```sh
git add src/enemy_common.h src/enemy_common.c
git commit -m "$(cat <<'EOF'
feat(enemy_common): add shared enemy AI helpers module

GREEN: enemy_aim_dir, enemy_dir_from_delta, enemy_wp_reached,
enemy_wp_advance. Bodies of aim and dir-from-delta moved verbatim
from turret.c / racer.c (not yet removed there).

Part of #144

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Point `test_turret.c` aim tests at `enemy_aim_dir` (RED)

We migrate the turret aim tests to call `enemy_aim_dir` before deleting `turret_dir_to_pixel`. After this edit, `test_turret` still compiles and passes because both functions currently exist; the RED proof for the turret refactor comes in Task 5 Step 2 (where removing `turret_dir_to_pixel` would break any remaining caller). We do this test edit first so the symbol is no longer referenced from the test by the time we remove it.

**Files:**
- Modify: `tests/test_turret.c`

- [ ] **Step 1: Add the `enemy_common.h` include**

In `tests/test_turret.c`, after the existing includes (lines 1–4), add:

```c
#include "enemy_common.h"
```

The include block should read:

```c
#include "unity.h"
#include "turret.h"
#include "player.h"   /* player_dir_t */
#include "camera.h"   /* cam_x, cam_y */
#include "enemy_common.h"
```

- [ ] **Step 2: Replace every `turret_dir_to_pixel` call with `enemy_aim_dir`**

Replace all 12 occurrences in the aim test functions (lines ~38–80). The expected `DIR_*` values are unchanged — only the function name changes. The functions to edit and their resulting bodies:

```c
void test_turret_direction_to_player_right(void) {
    /* Turret at tile (0,0) = pixel (0,0); player at pixel (64,0) → DIR_R */
    TEST_ASSERT_EQUAL_INT(DIR_R, enemy_aim_dir(0u, 0u, 64, 0));
}

void test_turret_direction_to_player_down(void) {
    TEST_ASSERT_EQUAL_INT(DIR_B, enemy_aim_dir(0u, 0u, 0, 64));
}

/* ax == ay tie → toward_x = (ax > ay) = 0 → NNE-side direction */
void test_turret_direction_to_player_down_right(void) {
    /* Was DIR_RB; 3-threshold: ax=ay=64, toward_x=0, SE quadrant → DIR_SSE */
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_aim_dir(0u, 0u, 64, 64));
}
void test_turret_direction_to_player_up_left(void) {
    /* Was DIR_LT; 3-threshold: ax=ay=80, toward_x=0, NW quadrant → DIR_NNW */
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_aim_dir(10u, 10u, 0, 0));
}

/* 16-direction tests — intermediate sectors */
void test_turret_direction_nne(void) {
    /* ax=10 < ay=15, NE quadrant → DIR_NNE */
    TEST_ASSERT_EQUAL_INT(DIR_NNE, enemy_aim_dir(0u, 0u, 10, -15));
}
void test_turret_direction_ene(void) {
    /* ax=15 > ay=10, NE quadrant → DIR_ENE */
    TEST_ASSERT_EQUAL_INT(DIR_ENE, enemy_aim_dir(0u, 0u, 15, -10));
}
void test_turret_direction_ese(void) {
    TEST_ASSERT_EQUAL_INT(DIR_ESE, enemy_aim_dir(0u, 0u, 15, 10));
}
void test_turret_direction_sse(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSE, enemy_aim_dir(0u, 0u, 10, 15));
}
void test_turret_direction_ssw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_SSW, enemy_aim_dir(0u, 0u, -10, 15));
}
void test_turret_direction_wsw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WSW, enemy_aim_dir(0u, 0u, -15, 10));
}
void test_turret_direction_wnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_WNW, enemy_aim_dir(0u, 0u, -15, -10));
}
void test_turret_direction_nnw(void) {
    TEST_ASSERT_EQUAL_INT(DIR_NNW, enemy_aim_dir(0u, 0u, -10, -15));
}
```

(The `RUN_TEST(...)` lines in `main()` keep their original names — only the call inside each function body changes.)

- [ ] **Step 3: Run `make test` and confirm `test_turret` still PASSES**

```sh
make test
```

Expected output: all suites green, including `build/test_turret` (`enemy_aim_dir` returns identical values to the old `turret_dir_to_pixel`). This proves the migrated tests are still correct before we delete the old function.

- [ ] **Step 4: Commit**

```sh
git add tests/test_turret.c
git commit -m "$(cat <<'EOF'
test(turret): aim tests call enemy_aim_dir instead of turret_dir_to_pixel

Same expected DIR_* values; prep for removing turret_dir_to_pixel.

Part of #144

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Refactor `turret.c` / `turret.h` to use `enemy_aim_dir`

> **GB gate:** bank-pre-write hook fires automatically on these Write/Edit calls; consult the `gbdk-expert` agent (implementation mode) if needed: `"implement this task: remove turret_dir_to_pixel from turret.c/.h and call enemy_aim_dir at the fire site"`; build with `make`; bank-post-build hook fires automatically.

**Files:**
- Modify: `src/turret.c`
- Modify: `src/turret.h`

- [ ] **Step 1: Add the `enemy_common.h` include to `turret.c`**

In `src/turret.c`, after the existing `#include "camera.h"` line (line 10), add:

```c
#include "enemy_common.h"  /* enemy_aim_dir — shared aim math */
```

- [ ] **Step 2: Delete the `turret_dir_to_pixel` definition from `turret.c`**

Remove the entire function (lines ~86–108), i.e. delete this exact block:

```c
player_dir_t turret_dir_to_pixel(uint8_t tx, uint8_t ty,
                                  int16_t player_px, int16_t player_py) BANKED {
    int16_t dx = player_px - (int16_t)((uint16_t)tx * 8u);
    int16_t dy = player_py - (int16_t)((uint16_t)ty * 8u);
    int16_t ax = dx < 0 ? -dx : dx;
    int16_t ay = dy < 0 ? -dy : dy;
    uint8_t toward_x;

    /* Threshold 1: cardinal E/W — |dx| > 2*|dy| */
    if (ax > (int16_t)(ay << 1)) {
        return dx > 0 ? DIR_R : DIR_L;
    }
    /* Threshold 2: cardinal N/S — |dy| > 2*|dx| */
    if (ay > (int16_t)(ax << 1)) {
        return dy > 0 ? DIR_B : DIR_T;
    }
    /* Threshold 3: intermediate sector — |dx| vs |dy| */
    toward_x = (uint8_t)(ax > ay);
    if (dx >= 0 && dy < 0) { return toward_x ? DIR_ENE : DIR_NNE; }
    if (dx >= 0)            { return toward_x ? DIR_ESE : DIR_SSE; }
    if (dy >= 0)            { return toward_x ? DIR_WSW : DIR_SSW; }
    return toward_x ? DIR_WNW : DIR_NNW;
}
```

- [ ] **Step 3: Update the fire call site in `turret_update`**

In `turret_update` (the `else` branch of the fire timer, line ~149), change the call. Replace:

```c
        } else {
            player_dir_t dir = turret_dir_to_pixel(
                turret_tx[i], turret_ty[i], player_px, player_py);
            projectile_fire(scr_x, scr_y, dir, PROJ_OWNER_ENEMY);
            turret_timer[i] = TURRET_FIRE_INTERVAL;
        }
```

with:

```c
        } else {
            player_dir_t dir = enemy_aim_dir(
                turret_tx[i], turret_ty[i], player_px, player_py);
            projectile_fire(scr_x, scr_y, dir, PROJ_OWNER_ENEMY);
            turret_timer[i] = TURRET_FIRE_INTERVAL;
        }
```

- [ ] **Step 4: Remove the `turret_dir_to_pixel` declaration from `turret.h`**

In `src/turret.h`, delete these lines (~33–35):

```c
/* Pure-logic helpers exposed for testing — not for production callers. */
player_dir_t turret_dir_to_pixel(uint8_t tx, uint8_t ty,
                                 int16_t player_px, int16_t player_py) BANKED;
```

(Leave the `#include "player.h"` at the top of `turret.h` — `player_dir_t` is no longer referenced in this header after the removal, but the include is harmless and other declarations are unaffected. If a `-Wextra` unused-include warning is undesirable it can stay; includes are not flagged by gcc. Do NOT remove it, to avoid breaking transitive consumers.)

- [ ] **Step 5: Run `make test` and confirm `test_turret` PASSES**

```sh
make test
```

Expected output: all suites green. `test_turret` no longer references `turret_dir_to_pixel` (migrated in Task 4) and the symbol no longer exists — confirming the removal is complete with no dangling caller.

- [ ] **Step 6: Build the ROM**

```sh
make
```

Expected output: clean build; bank-post-build + `make memory-check` hooks fire automatically, no FAIL/ERROR.

- [ ] **Step 7: Commit**

```sh
git add src/turret.c src/turret.h
git commit -m "$(cat <<'EOF'
refactor(turret): use enemy_aim_dir; remove turret_dir_to_pixel

Pure refactor — identical aim behavior, now via enemy_common.

Part of #144

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Refactor `racer.c` to use `enemy_dir_from_delta` + waypoint helpers

> **GB gate:** bank-pre-write hook fires automatically on these Write/Edit calls; consult the `gbdk-expert` agent (implementation mode) if needed: `"implement this task: remove static racer_dir_from_delta from racer.c, call enemy_dir_from_delta, and replace the inline waypoint reached/advance block with enemy_wp_reached + enemy_wp_advance"`; build with `make`; bank-post-build hook fires automatically.

**Files:**
- Modify: `src/racer.c`

- [ ] **Step 1: Add the `enemy_common.h` include to `racer.c`**

In `src/racer.c`, after the existing `#include "projectile.h"` line (line 13), add:

```c
#include "enemy_common.h"  /* enemy_dir_from_delta, enemy_wp_reached, enemy_wp_advance */
```

- [ ] **Step 2: Delete the `static racer_dir_from_delta` definition**

Remove the entire function (lines ~137–152), i.e. delete this exact block:

```c
/* ---- Direction from delta ---- */
static uint8_t racer_dir_from_delta(int8_t dx, int8_t dy) {
    int8_t ax = dx < 0 ? -dx : dx;
    int8_t ay = dy < 0 ? -dy : dy;
    if (ay > ax) {
        return (dy < 0) ? DIR_T : DIR_B;
    } else if (ax > ay) {
        return (dx < 0) ? DIR_L : DIR_R;
    } else {
        /* Diagonal: ax == ay */
        if (dy < 0 && dx < 0) return DIR_LT;
        if (dy < 0 && dx > 0) return DIR_RT;
        if (dy > 0 && dx < 0) return DIR_LB;
        return DIR_RB;
    }
}
```

- [ ] **Step 3: Replace the inline waypoint reached/advance block in `racer_update`**

In `racer_update` (lines ~289–300), replace this block:

```c
        abs_dx = (uint8_t)(dx < 0 ? -dx : dx);
        abs_dy = (uint8_t)(dy < 0 ? -dy : dy);

        if ((uint8_t)(abs_dx + abs_dy) < RACER_WP_THRESHOLD) {
            racer_wp_idx[i]++;
            if (racer_wp_idx[i] >= s_wp_count[i - 1u]) {
                racer_wp_idx[i] = 0u;
            }
        }

        dir = racer_dir_from_delta(dx, dy);
        racer_dir[i] = dir;
```

with this block:

```c
        racer_wp_idx[i] = enemy_wp_advance(
            racer_wp_idx[i],
            s_wp_count[i - 1u],
            enemy_wp_reached(dx, dy, RACER_WP_THRESHOLD));

        dir = enemy_dir_from_delta(dx, dy);
        racer_dir[i] = dir;
```

Note: `abs_dx` and `abs_dy` are now unused locals. Remove their declarations from the top of the `racer_update` loop to avoid `-Wextra` unused-variable warnings. In the local declaration block (lines ~265–266), delete:

```c
        uint8_t abs_dx;
        uint8_t abs_dy;
```

Behavioral equivalence check: the old code incremented `racer_wp_idx[i]` then wrapped to 0 when `>= s_wp_count`. `enemy_wp_advance(cur, count, reached)` returns `(cur+1 >= count) ? 0 : cur+1` when `reached`, which is identical. `enemy_wp_reached(dx, dy, RACER_WP_THRESHOLD)` computes `(uint8_t)(abs(dx)+abs(dy)) < RACER_WP_THRESHOLD`, identical to the old condition.

- [ ] **Step 4: Run `make test` and confirm `test_racer` + `test_race_scenario` PASS (regression)**

```sh
make test
```

Expected output: all suites green — specifically `build/test_racer` and `build/test_race_scenario` unchanged. The waypoint-advance and waypoint-wrap tests (`test_racer_advances_waypoint_when_close`, `test_racer_wraps_waypoints`) and all finish-line tests pass, proving the refactor preserved behavior.

- [ ] **Step 5: Build the ROM**

```sh
make
```

Expected output: clean build; bank-post-build + `make memory-check` hooks fire automatically, no FAIL/ERROR.

- [ ] **Step 6: Commit**

```sh
git add src/racer.c
git commit -m "$(cat <<'EOF'
refactor(racer): use enemy_common dir/waypoint helpers

Pure refactor — removes static racer_dir_from_delta and inline wp
math in favor of enemy_dir_from_delta / enemy_wp_reached /
enemy_wp_advance. Identical movement behavior.

Part of #144

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Full regression gate

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite from the worktree dir**

```sh
make test
```

Expected output: every `tests/test_*.c` binary compiles and runs to `OK`. Confirm in particular: `test_enemy_common` (new), `test_turret`, `test_racer`, `test_race_scenario`, `test_player` all green. Because the `test:` rule stops at the first failure (`|| exit 1`, alphabetical order), a complete run with no early exit is the pass signal.

- [ ] **Step 2: Clean build**

```sh
make clean && make
```

Expected output: full clean rebuild succeeds; ROM at `build/nuke-raider.gb`. bank-post-build + `make memory-check` hooks fire automatically — confirm OAM/VRAM/WRAM/bank budgets show no FAIL or ERROR. (No budget change is expected: this PR moves code between bank-255 modules and adds no data or sprites.)

---

## Task 8: Smoketest gate + push + PR (per CLAUDE.md)

**Files:** none (integration only)

- [ ] **Step 1: Fetch and merge latest master from the worktree dir**

```sh
git fetch origin && git merge origin/master
```

Expected: clean merge (or resolve conflicts if any). Never use `git merge master` alone.

- [ ] **Step 2: Clean build**

```sh
make clean && make
```

Expected output: clean build; ROM at `build/nuke-raider.gb`. bank-post-build + `make memory-check` hooks fire automatically.

- [ ] **Step 3: Memory check (explicit confirmation)**

```sh
make memory-check
```

Expected output: WRAM/VRAM/OAM all PASS (no change from baseline — pure refactor).

- [ ] **Step 4: Smoketest in Emulicious (after user confirmation)**

Ask the user to confirm before launching. On confirmation, launch from the worktree dir (Windows: use PowerShell `Start-Process`, not Bash `java -jar`):

```powershell
Start-Process java -ArgumentList '-jar','C:\Tools\Emulicious\Emulicious.jar','build/nuke-raider.gb'
```

Ask the user to confirm Track 1 plays normally — turret aiming/firing at the player and racer waypoint following both behave exactly as before (no behavior change is expected from this refactor). Track 2 race-position HUD (P:1/P:2/P:3) must still be correct.

- [ ] **Step 5: After user confirms, push and open the PR**

```sh
git push -u origin HEAD
gh pr create --title "Patrol PR1: extract enemy_common shared helpers" --body "$(cat <<'EOF'
PR1 of the stacked patrol feature (#144). Pure refactor, no behavior change.

Extracts shared enemy-AI math into a new `enemy_common` module:
- `enemy_aim_dir` — moved verbatim from `turret_dir_to_pixel`.
- `enemy_dir_from_delta` — moved verbatim from racer's former static helper.
- `enemy_wp_reached` / `enemy_wp_advance` — extracted from racer's inline waypoint math.

`turret.c` and `racer.c` refactored to call the shared helpers. New `tests/test_enemy_common.c`; `test_turret.c` aim tests retargeted to `enemy_aim_dir`. `test_turret`, `test_racer`, and `test_race_scenario` stay green.

Part of #144

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected output: branch pushed; PR URL printed. (Use `Part of #144` — not `Closes #144` — since #144 is completed only by the final PR in the stack.)

---

## Self-Review

### Spec-coverage table

| PR1 requirement | Covered by |
|-----------------|------------|
| New `src/enemy_common.h` + `src/enemy_common.c`, bank 255 autobank | Task 3 (Steps 1–2), Task 1 (manifest) |
| `enemy_aim_dir(tx, ty, player_px, player_py)` — verbatim body of `turret_dir_to_pixel`, renamed | Task 3 Step 2 |
| `enemy_dir_from_delta(dx, dy)` — verbatim body of `racer_dir_from_delta`, now exposed | Task 3 Step 2 |
| `enemy_wp_reached(dx, dy, threshold)` — `(uint8_t)(abs(dx)+abs(dy)) < threshold` | Task 3 Step 2 |
| `enemy_wp_advance(cur_idx, wp_count, reached)` — advance/wrap-or-keep | Task 3 Step 2 |
| `turret.c`: remove `turret_dir_to_pixel`, call `enemy_aim_dir` | Task 5 Steps 2–3 |
| `turret.h`: remove `turret_dir_to_pixel` declaration | Task 5 Step 4 |
| `racer.c`: remove static `racer_dir_from_delta`, call `enemy_dir_from_delta` | Task 6 Steps 2–3 |
| `racer.c`: replace inline wp reached/advance with `enemy_wp_reached`+`enemy_wp_advance`; keep cp/finish logic inline | Task 6 Step 3 |
| `tests/test_turret.c`: aim tests call `enemy_aim_dir` (same expected DIR_*) | Task 4 Steps 1–2 |
| New `tests/test_enemy_common.c`: all 4 functions (aim cases; dir-from-delta per 8-way; wp_reached boundaries; wp_advance wrap) | Task 2 Step 1 |
| `bank-manifest.json`: add `src/enemy_common.c` entry | Task 1 Step 1 |
| Wire `enemy_common.c` into every test binary that needs it | Auto-handled by Makefile glob (`TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))`) — documented in "Build wiring note"; verified in Task 7 |
| Regression: `test_turret` + `test_racer` stay green | Task 5 Step 5, Task 6 Step 4, Task 7 Step 1 |
| Smoketest gate (fetch+merge, clean build, memory-check, Emulicious, push, PR with `Part of #144`) | Task 8 |

### Placeholder scan

Confirmed: no `TBD`, no `...`, no "similar to above", no "(omitted)" placeholders. Every code block in Tasks 2, 3, 4, 5, and 6 is complete and self-contained (full file contents for new files; full before/after blocks for edits).

### Type-consistency confirmation

Function names and signatures match the canonical PR1 contracts exactly:
- `player_dir_t enemy_aim_dir(uint8_t tx, uint8_t ty, int16_t player_px, int16_t player_py) BANKED;` ✓
- `uint8_t enemy_dir_from_delta(int8_t dx, int8_t dy) BANKED;` ✓
- `uint8_t enemy_wp_reached(int8_t dx, int8_t dy, uint8_t threshold) BANKED;` ✓
- `uint8_t enemy_wp_advance(uint8_t cur_idx, uint8_t wp_count, uint8_t reached) BANKED;` ✓

Return-type fidelity: `enemy_aim_dir` returns `player_dir_t` (matches old `turret_dir_to_pixel`); `enemy_dir_from_delta` returns `uint8_t` (matches old `racer_dir_from_delta`, which returned `uint8_t` and is assigned to `racer_dir[i]`, a `uint8_t`). `RACER_WP_THRESHOLD` (`12u`, `uint8_t`) is passed unchanged as the `threshold` argument. No C `enum` is introduced (SDCC-safe); `DIR_*` constants come from `player.h` via the existing `player_dir_t` enum already used project-wide.
