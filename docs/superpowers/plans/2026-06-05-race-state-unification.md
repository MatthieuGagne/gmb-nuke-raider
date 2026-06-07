# Race State Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the duplicated checkpoint/lap tracking in `checkpoint.c`, `lap.c`, and `racer.c` with a single `race_state.c` module that owns all per-slot race-tracking state for every racer slot including the player.

**Architecture:** New `race_state.c` holds SoA arrays `rs_cp_next[MAX_RACERS]`, `rs_laps[MAX_RACERS]`, `rs_active[MAX_RACERS]`, and `rs_lap_total`. Slot 0 = enemy racer, slot 1 = player (`PLAYER_SLOT = 1`). Player and enemy call identical `race_state_update_cp(slot, x, y, dir)` / `race_state_advance_lap(slot)` APIs; `race_state_rank_player()` replaces the inline 3-level comparison in `state_playing.c`. `checkpoint.c`, `checkpoint.h`, `lap.c`, `lap.h` are deleted on completion.

**Tech Stack:** C (SDCC/GBDK-2020), Unity test framework, gcc host tests, bank-manifest.json, `#pragma bank 255` autobank

---

## File Structure

| File | Change |
|------|--------|
| `bank-manifest.json` | Add `race_state.c`; remove `checkpoint.c`, `lap.c` |
| `src/config.h` | `MAX_RACERS` 1→2; add `PLAYER_SLOT = 1` |
| `src/track.h` | Inline `CheckpointDef` struct + `CHECKPOINT_DIR_*` directly; remove `#include "checkpoint.h"` |
| `src/race_state.h` | New — full public API + `#ifndef __SDCC` test helpers |
| `src/race_state.c` | New — all per-slot cp/lap logic + `pos_from_manhattan`/`pos_from_dir` (moved from `state_playing.c`) |
| `src/state_playing.c` | Replace checkpoint/lap/racer-accessor call sites; remove `pos_from_dir`/`pos_from_manhattan`; replace inline position block with `race_state_rank_player()` |
| `src/state_playing.h` | Remove `pos_from_dir`, `pos_from_manhattan` test-seam declarations |
| `src/racer.c` | Remove `racer_cp_next[]`, `s_laps_done`, `racer_checkpoint_update()`; call `race_state`; update `racer_init`, `racer_init_empty`, `racer_update`, `racer_spawn_for_test` |
| `src/racer.h` | Remove `racer_get_cp_next()`, `racer_get_laps_done()`, `racer_set_cp_next_for_test()`, `racer_set_laps_done_for_test()`, `racer_checkpoint_update_for_test()` |
| `tests/test_race_state.c` | New — full test coverage for `race_state.c` (including `pos_from_dir`/`pos_from_manhattan` tests migrated from `test_state_playing.c`) |
| `tests/test_racer.c` | Update: replace `racer_get_cp_next()` → `race_state_get_cp()`, `racer_set_cp_next_for_test()` → `race_state_set_cp_for_test()`, `racer_set_laps_done_for_test()` → `race_state_set_laps_for_test()`, direct `race_state_update_cp()` calls; remove `test_racer_cp_next_resets_on_lap_wrap` |
| `tests/test_state_playing.c` | Remove `pos_from_dir` / `pos_from_manhattan` tests (covered in `test_race_state.c`); update includes |
| `src/checkpoint.c` | **Delete** |
| `src/checkpoint.h` | **Delete** |
| `src/lap.c` | **Delete** |
| `src/lap.h` | **Delete** |
| `tests/test_checkpoint.c` | **Delete** |
| `tests/test_lap.c` | **Delete** |

---

## Task 1: Update `bank-manifest.json`

**Files:**
- Modify: `bank-manifest.json`

- [ ] **Step 1: Add `race_state.c` entry and remove `checkpoint.c` / `lap.c`**

Open `bank-manifest.json` and apply three changes:

Remove the lines:
```json
  "src/checkpoint.c":            {"bank": 255, "reason": "autobank"},
```
and:
```json
  "src/lap.c":                   {"bank": 255, "reason": "autobank"},
```

Add (after the `"src/racer.c"` entry):
```json
  "src/race_state.c":            {"bank": 255, "reason": "autobank — unified per-slot cp/lap tracking; called from state_playing.c and racer.c"},
```

- [ ] **Step 2: Verify the manifest is valid JSON**

Run:
```powershell
Get-Content bank-manifest.json | python -m json.tool
```
Expected: no error, JSON prints cleanly.

- [ ] **Step 3: Commit**

```powershell
git add bank-manifest.json
git commit -m "chore: update bank-manifest for race_state unification"
```

---

## Task 2: Update `src/config.h` and `src/track.h`

**Files:**
- Modify: `src/config.h`
- Modify: `src/track.h`

### `src/config.h` changes

- [ ] **Step 1: Bump `MAX_RACERS` to 2 and add `PLAYER_SLOT`**

Find the line (around line 98):
```c
#define MAX_RACERS           1u   /* SoA pool capacity; design for N, implement 1 */
```
Replace with:
```c
#define MAX_RACERS           2u   /* SoA pool capacity; slot 0 = enemy, slot 1 = player */
#define PLAYER_SLOT          1u   /* race_state slot index for the human player */
```

### `src/track.h` changes

- [ ] **Step 2: Inline `CheckpointDef` and `CHECKPOINT_DIR_*` into `track.h`**

Find the line near line 38:
```c
#include "checkpoint.h"
```

Replace that single line with the full type definitions from `checkpoint.h`:
```c
/* Checkpoint direction constants — used by race_state and racer for AABB+direction matching */
#define CHECKPOINT_DIR_N 0u
#define CHECKPOINT_DIR_S 1u
#define CHECKPOINT_DIR_E 2u
#define CHECKPOINT_DIR_W 3u

/* Per-checkpoint descriptor — stored in ROM, loaded into WRAM buffer by track_init() */
typedef struct {
    int16_t x;          /* world-pixel left edge of AABB */
    int16_t y;          /* world-pixel top edge of AABB */
    uint8_t w;          /* AABB width in pixels */
    uint8_t h;          /* AABB height in pixels */
    uint8_t index;      /* sequential index (0-based) */
    uint8_t direction;  /* CHECKPOINT_DIR_N/S/E/W */
} CheckpointDef;
```

- [ ] **Step 3: Run tests — must still pass (no functional change)**

```powershell
Set-Location C:\Code\nuke-raider\.claude\worktrees\feat-race-state-unification
make test
```
Expected: all tests pass (checkpoint.c/lap.c still exist and compile).

- [ ] **Step 4: Commit**

```powershell
git add src/config.h src/track.h
git commit -m "chore: bump MAX_RACERS to 2, add PLAYER_SLOT, inline CheckpointDef into track.h"
```

---

## Task 3: Create `src/race_state.h`

**Files:**
- Create: `src/race_state.h`

- [ ] **Step 1: Write `src/race_state.h`**

```c
#ifndef RACE_STATE_H
#define RACE_STATE_H

#include <stdint.h>
#include "banking.h"
#include "track.h"   /* CheckpointDef, CHECKPOINT_DIR_*, track_get_checkpoints() */

/* Lifecycle */
void    race_state_init(uint8_t lap_total) BANKED;
void    race_state_set_active(uint8_t slot, uint8_t active) BANKED;

/* Per-frame update: AABB+direction checkpoint detection for one slot */
void    race_state_update_cp(uint8_t slot, int16_t x, int16_t y, uint8_t dir) BANKED;

/* Lap gate — call when finish tile + direction validated for this slot.
 * Returns 1 if race is over for this slot, 0 if lap incremented. */
uint8_t race_state_advance_lap(uint8_t slot) BANKED;

/* Accessors */
uint8_t race_state_get_cp(uint8_t slot) BANKED;
uint8_t race_state_get_laps(uint8_t slot) BANKED;   /* 0-based completed laps */
uint8_t race_state_get_lap_total(void) BANKED;
uint8_t race_state_all_cp_cleared(uint8_t slot) BANKED;

/* Position ranking — returns player's 1-based ordinal rank among all active slots */
uint8_t race_state_rank_player(void) BANKED;

#ifndef __SDCC
/* Test-only seams */
void    race_state_set_laps_for_test(uint8_t slot, uint8_t n);
void    race_state_set_cp_for_test(uint8_t slot, uint8_t n);
/* Direction-aware position comparison (static in SDCC, exposed for host tests). */
uint8_t pos_from_dir(uint8_t dir,
                     int16_t px,  int16_t py,
                     int16_t rpx, int16_t rpy);
/* Manhattan-distance tiebreaker to checkpoint center. */
uint8_t pos_from_manhattan(int16_t px,  int16_t py,
                           int16_t rpx, int16_t rpy,
                           const CheckpointDef *next);
#endif

#endif /* RACE_STATE_H */
```

- [ ] **Step 2: Commit the header**

```powershell
git add src/race_state.h
git commit -m "feat: add race_state.h public API"
```

---

## Task 4: Write `tests/test_race_state.c` (TDD RED)

**Files:**
- Create: `src/race_state.c` (stubs — so the test file compiles)
- Create: `tests/test_race_state.c`

### Step 1: Create stub `src/race_state.c` so tests compile

- [ ] **Write stub `src/race_state.c`**

```c
#pragma bank 255
#include "race_state.h"

static uint8_t rs_cp_next[MAX_RACERS];
static uint8_t rs_laps[MAX_RACERS];
static uint8_t rs_active[MAX_RACERS];
static uint8_t rs_lap_total;

void    race_state_init(uint8_t lap_total) BANKED { (void)lap_total; }
void    race_state_set_active(uint8_t slot, uint8_t active) BANKED { (void)slot; (void)active; }
void    race_state_update_cp(uint8_t slot, int16_t x, int16_t y, uint8_t dir) BANKED {
    (void)slot; (void)x; (void)y; (void)dir;
}
uint8_t race_state_advance_lap(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_get_cp(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_get_laps(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_get_lap_total(void) BANKED { return 0u; }
uint8_t race_state_all_cp_cleared(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_rank_player(void) BANKED { return 1u; }

#ifndef __SDCC
void race_state_set_laps_for_test(uint8_t slot, uint8_t n) { (void)slot; (void)n; }
void race_state_set_cp_for_test(uint8_t slot, uint8_t n) { (void)slot; (void)n; }
uint8_t pos_from_dir(uint8_t dir, int16_t px, int16_t py, int16_t rpx, int16_t rpy) {
    (void)dir; (void)px; (void)py; (void)rpx; (void)rpy; return 0u;
}
uint8_t pos_from_manhattan(int16_t px, int16_t py, int16_t rpx, int16_t rpy,
                            const CheckpointDef *next) {
    (void)px; (void)py; (void)rpx; (void)rpy; (void)next; return 0u;
}
#endif
```

### Step 2: Write `tests/test_race_state.c`

- [ ] **Write `tests/test_race_state.c`**

```c
#include "unity.h"
#include "race_state.h"
#include "track.h"
#include "player.h"    /* DIR_T, DIR_B, DIR_L, DIR_R, DIR_LT, DIR_RT, DIR_LB, DIR_RB */

void setUp(void) {
    race_state_init(3u);
}
void tearDown(void) {}

/* ---- race_state_init ---- */

void test_init_sets_lap_total(void) {
    race_state_init(5u);
    TEST_ASSERT_EQUAL_UINT8(5u, race_state_get_lap_total());
}

void test_init_zeros_all_cp(void) {
    race_state_set_cp_for_test(0u, 7u);
    race_state_set_cp_for_test(1u, 7u);
    race_state_init(2u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(1u));
}

void test_init_zeros_all_laps(void) {
    race_state_set_laps_for_test(0u, 4u);
    race_state_set_laps_for_test(1u, 4u);
    race_state_init(2u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_laps(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_laps(1u));
}

void test_init_deactivates_all_slots(void) {
    race_state_set_active(0u, 1u);
    race_state_set_active(1u, 1u);
    race_state_init(2u);
    /* rank_player with no active slots should return 1 (default) */
    race_state_set_active(PLAYER_SLOT, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

/* ---- race_state_update_cp ---- */

void test_update_cp_clears_when_inside_and_correct_dir(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);   /* inside, facing south */
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
}

void test_update_cp_ignored_wrong_direction(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_T);   /* inside, wrong direction */
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_update_cp_ignored_outside_aabb(void) {
    CheckpointDef defs[1];
    defs[0].x = 100; defs[0].y = 100; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);   /* outside rect */
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_update_cp_sequential_enforced(void) {
    CheckpointDef defs[2];
    defs[0].x = 200; defs[0].y = 200; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    defs[1].x = 0;   defs[1].y = 0;   defs[1].w = 32; defs[1].h = 32;
    defs[1].index = 1u; defs[1].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 2u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    /* Try to clear cp[1] (at origin) while cp[0] not yet cleared */
    race_state_update_cp(0u, 5, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_update_cp_per_slot_independent(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(1u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);   /* slot 0 clears */
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(1u));  /* slot 1 unaffected */
}

void test_update_cp_all_4_directions(void) {
    CheckpointDef defs[1];
    /* Direction N */
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_N;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_T);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));

    /* Direction E */
    defs[0].direction = CHECKPOINT_DIR_E;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_R);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));

    /* Direction W */
    defs[0].direction = CHECKPOINT_DIR_W;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_L);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
}

/* ---- race_state_all_cp_cleared ---- */

void test_all_cp_cleared_zero_checkpoints(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_all_cp_cleared(0u));
}

void test_all_cp_cleared_not_cleared(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_all_cp_cleared(0u));
}

void test_all_cp_cleared_after_clearing(void) {
    CheckpointDef defs[1];
    defs[0].x = 0; defs[0].y = 0; defs[0].w = 32; defs[0].h = 32;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_update_cp(0u, 5, 5, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_all_cp_cleared(0u));
}

/* ---- race_state_advance_lap ---- */

void test_advance_lap_mid_race_returns_zero(void) {
    /* lap_total=3, laps=0 → 0+1=1 < 3 → returns 0 */
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_advance_lap(0u));
}

void test_advance_lap_increments_laps(void) {
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_advance_lap(0u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_laps(0u));
}

void test_advance_lap_resets_cp_next(void) {
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_cp_for_test(0u, 5u);
    race_state_advance_lap(0u);  /* mid-race: resets cp */
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}

void test_advance_lap_final_returns_one(void) {
    /* lap_total=3, laps=2 → 2+1=3 >= 3 → returns 1 (race over) */
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_laps_for_test(0u, 2u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_advance_lap(0u));
}

void test_advance_lap_single_lap_race_returns_one(void) {
    /* lap_total=1, laps=0 → 0+1=1 >= 1 → returns 1 */
    race_state_init(1u);
    race_state_set_active(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_advance_lap(0u));
}

void test_advance_lap_per_slot_independent(void) {
    /* Slot 0 advances; slot 1 is unaffected */
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(1u, 1u);
    race_state_advance_lap(0u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_laps(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_laps(1u));
}

/* ---- race_state_rank_player ---- */

void test_rank_player_alone_is_1(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(PLAYER_SLOT, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

void test_rank_player_more_laps_is_1(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(PLAYER_SLOT, 2u);
    race_state_set_laps_for_test(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

void test_rank_player_fewer_laps_is_2(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(0u, 2u);
    TEST_ASSERT_EQUAL_UINT8(2u, race_state_rank_player());
}

void test_rank_player_same_laps_more_cp_is_1(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_cp_for_test(PLAYER_SLOT, 3u);
    race_state_set_cp_for_test(0u, 1u);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

void test_rank_player_same_laps_fewer_cp_is_2(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_cp_for_test(PLAYER_SLOT, 1u);
    race_state_set_cp_for_test(0u, 3u);
    TEST_ASSERT_EQUAL_UINT8(2u, race_state_rank_player());
}

void test_rank_player_tiebreaker_player_closer_is_1(void) {
    /* Same laps and cp — next checkpoint at (100, 100, 20, 20).
     * Player at (112, 112), distance=4. Enemy at (90, 90), distance=40. */
    CheckpointDef defs[1];
    defs[0].x = 100; defs[0].y = 100; defs[0].w = 20; defs[0].h = 20;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 1u);

    race_state_init(3u);
    race_state_set_active(0u, 1u);
    race_state_set_active(PLAYER_SLOT, 1u);
    /* cp_next=0 for both → next cp is defs[0] */
    /* rank_player calls pos_from_manhattan internally for the tiebreaker */
    /* We can't easily inject positions via race_state alone, so test pos_from_manhattan directly */
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(112, 112, 90, 90, &defs[0]));
}

void test_rank_player_inactive_enemy_not_counted(void) {
    track_test_set_checkpoints(NULL, 0u);
    race_state_init(3u);
    race_state_set_active(0u, 0u);   /* enemy inactive */
    race_state_set_active(PLAYER_SLOT, 1u);
    race_state_set_laps_for_test(0u, 99u);   /* irrelevant: inactive */
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_rank_player());
}

/* ---- pos_from_dir (moved from test_state_playing.c) ---- */

void test_pos_from_dir_N_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_N, 0,  50, 0, 100));
}
void test_pos_from_dir_N_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_N, 0, 100, 0,  50));
}
void test_pos_from_dir_S_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_S, 0, 100, 0,  50));
}
void test_pos_from_dir_S_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_S, 0,  50, 0, 100));
}
void test_pos_from_dir_E_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_E, 100, 0,  50, 0));
}
void test_pos_from_dir_E_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_E,  50, 0, 100, 0));
}
void test_pos_from_dir_W_player_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_dir(CHECKPOINT_DIR_W,  50, 0, 100, 0));
}
void test_pos_from_dir_W_racer_ahead(void) {
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_dir(CHECKPOINT_DIR_W, 100, 0,  50, 0));
}

/* ---- pos_from_manhattan (moved from test_state_playing.c) ---- */

void test_pos_from_manhattan_player_closer(void) {
    CheckpointDef cp = {100, 100, 20, 20, 0, CHECKPOINT_DIR_N};
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(112, 112, 90, 90, &cp));
}
void test_pos_from_manhattan_racer_closer(void) {
    CheckpointDef cp = {100, 100, 20, 20, 0, CHECKPOINT_DIR_N};
    TEST_ASSERT_EQUAL_UINT8(2u, pos_from_manhattan(90, 90, 112, 112, &cp));
}
void test_pos_from_manhattan_equal_distance_favors_player(void) {
    CheckpointDef cp = {100, 100, 20, 20, 0, CHECKPOINT_DIR_N};
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(120, 110, 110, 120, &cp));
}
void test_pos_from_manhattan_nonsquare_checkpoint(void) {
    CheckpointDef cp = {0, 0, 40, 10, 0, CHECKPOINT_DIR_E};
    TEST_ASSERT_EQUAL_UINT8(1u, pos_from_manhattan(21, 5, 0, 5, &cp));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_sets_lap_total);
    RUN_TEST(test_init_zeros_all_cp);
    RUN_TEST(test_init_zeros_all_laps);
    RUN_TEST(test_init_deactivates_all_slots);
    RUN_TEST(test_update_cp_clears_when_inside_and_correct_dir);
    RUN_TEST(test_update_cp_ignored_wrong_direction);
    RUN_TEST(test_update_cp_ignored_outside_aabb);
    RUN_TEST(test_update_cp_sequential_enforced);
    RUN_TEST(test_update_cp_per_slot_independent);
    RUN_TEST(test_update_cp_all_4_directions);
    RUN_TEST(test_all_cp_cleared_zero_checkpoints);
    RUN_TEST(test_all_cp_cleared_not_cleared);
    RUN_TEST(test_all_cp_cleared_after_clearing);
    RUN_TEST(test_advance_lap_mid_race_returns_zero);
    RUN_TEST(test_advance_lap_increments_laps);
    RUN_TEST(test_advance_lap_resets_cp_next);
    RUN_TEST(test_advance_lap_final_returns_one);
    RUN_TEST(test_advance_lap_single_lap_race_returns_one);
    RUN_TEST(test_advance_lap_per_slot_independent);
    RUN_TEST(test_rank_player_alone_is_1);
    RUN_TEST(test_rank_player_more_laps_is_1);
    RUN_TEST(test_rank_player_fewer_laps_is_2);
    RUN_TEST(test_rank_player_same_laps_more_cp_is_1);
    RUN_TEST(test_rank_player_same_laps_fewer_cp_is_2);
    RUN_TEST(test_rank_player_tiebreaker_player_closer_is_1);
    RUN_TEST(test_rank_player_inactive_enemy_not_counted);
    RUN_TEST(test_pos_from_dir_N_player_ahead);
    RUN_TEST(test_pos_from_dir_N_racer_ahead);
    RUN_TEST(test_pos_from_dir_S_player_ahead);
    RUN_TEST(test_pos_from_dir_S_racer_ahead);
    RUN_TEST(test_pos_from_dir_E_player_ahead);
    RUN_TEST(test_pos_from_dir_E_racer_ahead);
    RUN_TEST(test_pos_from_dir_W_player_ahead);
    RUN_TEST(test_pos_from_dir_W_racer_ahead);
    RUN_TEST(test_pos_from_manhattan_player_closer);
    RUN_TEST(test_pos_from_manhattan_racer_closer);
    RUN_TEST(test_pos_from_manhattan_equal_distance_favors_player);
    RUN_TEST(test_pos_from_manhattan_nonsquare_checkpoint);
    return UNITY_END();
}
```

- [ ] **Step 3: Run tests — `test_race_state` must fail (stubs return 0)**

```powershell
make test
```
Expected: `test_race_state` binary shows multiple FAIL. All other test binaries still pass.

- [ ] **Step 4: Commit stubs + test file**

```powershell
git add src/race_state.c tests/test_race_state.c
git commit -m "test: add test_race_state.c (TDD red) + stub race_state.c"
```

---

## Task 5: Implement `src/race_state.c` (TDD GREEN)

**Files:**
- Modify: `src/race_state.c`

- [ ] **Step 1: Replace stubs with full implementation**

```c
#pragma bank 255
#include "race_state.h"
#include "track.h"
#include "player.h"   /* DIR_T, DIR_B, DIR_L, DIR_R, DIR_LT, DIR_RT, DIR_LB, DIR_RB */

static uint8_t rs_cp_next[MAX_RACERS];
static uint8_t rs_laps[MAX_RACERS];
static uint8_t rs_active[MAX_RACERS];
static uint8_t rs_lap_total;

void race_state_init(uint8_t lap_total) BANKED {
    uint8_t i;
    rs_lap_total = lap_total;
    for (i = 0u; i < MAX_RACERS; i++) {
        rs_cp_next[i] = 0u;
        rs_laps[i]    = 0u;
        rs_active[i]  = 0u;
    }
}

void race_state_set_active(uint8_t slot, uint8_t active) BANKED {
    rs_active[slot] = active;
}

void race_state_update_cp(uint8_t slot, int16_t x, int16_t y, uint8_t dir) BANKED {
    const CheckpointDef *defs;
    const CheckpointDef *cp;
    uint8_t count;

    if (!rs_active[slot]) return;
    count = track_get_checkpoint_count();
    if (rs_cp_next[slot] >= count) return;
    defs = track_get_checkpoints();
    cp   = &defs[rs_cp_next[slot]];

    if (x < cp->x)                                        return;
    if (x >= (int16_t)((uint16_t)cp->x + (uint16_t)cp->w)) return;
    if (y < cp->y)                                        return;
    if (y >= (int16_t)((uint16_t)cp->y + (uint16_t)cp->h)) return;

    if      (cp->direction == CHECKPOINT_DIR_N) { if (dir != DIR_T  && dir != DIR_RT && dir != DIR_LT) return; }
    else if (cp->direction == CHECKPOINT_DIR_S) { if (dir != DIR_B  && dir != DIR_RB && dir != DIR_LB) return; }
    else if (cp->direction == CHECKPOINT_DIR_E) { if (dir != DIR_R  && dir != DIR_RT && dir != DIR_RB) return; }
    else if (cp->direction == CHECKPOINT_DIR_W) { if (dir != DIR_L  && dir != DIR_LT && dir != DIR_LB) return; }

    rs_cp_next[slot]++;
}

uint8_t race_state_advance_lap(uint8_t slot) BANKED {
    if ((uint8_t)(rs_laps[slot] + 1u) >= rs_lap_total) {
        return 1u;
    }
    rs_laps[slot]    = (uint8_t)(rs_laps[slot] + 1u);
    rs_cp_next[slot] = 0u;
    return 0u;
}

uint8_t race_state_get_cp(uint8_t slot) BANKED { return rs_cp_next[slot]; }

uint8_t race_state_get_laps(uint8_t slot) BANKED { return rs_laps[slot]; }

uint8_t race_state_get_lap_total(void) BANKED { return rs_lap_total; }

uint8_t race_state_all_cp_cleared(uint8_t slot) BANKED {
    return (rs_cp_next[slot] >= track_get_checkpoint_count());
}

/* Direction-aware position comparison. Static in SDCC build; exposed for host tests. */
#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
pos_from_dir(uint8_t dir,
             int16_t px,  int16_t py,
             int16_t rpx, int16_t rpy) {
    if (dir == CHECKPOINT_DIR_N) return (py  <= rpy) ? 1u : 2u;
    if (dir == CHECKPOINT_DIR_S) return (py  >= rpy) ? 1u : 2u;
    if (dir == CHECKPOINT_DIR_E) return (px  >= rpx) ? 1u : 2u;
    return (px <= rpx) ? 1u : 2u;   /* CHECKPOINT_DIR_W */
}

/* Manhattan-distance tiebreaker. Static in SDCC build; exposed for host tests. */
#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
pos_from_manhattan(int16_t px,  int16_t py,
                   int16_t rpx, int16_t rpy,
                   const CheckpointDef *next) {
    int16_t cx  = next->x + (int16_t)(next->w >> 1u);
    int16_t cy  = next->y + (int16_t)(next->h >> 1u);
    int16_t pdx = px  - cx; if (pdx < 0) pdx = -pdx;
    int16_t pdy = py  - cy; if (pdy < 0) pdy = -pdy;
    int16_t rdx = rpx - cx; if (rdx < 0) rdx = -rdx;
    int16_t rdy = rpy - cy; if (rdy < 0) rdy = -rdy;
    uint16_t pd = (uint16_t)pdx + (uint16_t)pdy;
    uint16_t rd = (uint16_t)rdx + (uint16_t)rdy;
    return (pd <= rd) ? 1u : 2u;
}

uint8_t race_state_rank_player(void) BANKED {
    uint8_t i;
    uint8_t pos = 1u;
    uint8_t player_laps = rs_laps[PLAYER_SLOT];
    uint8_t player_cp   = rs_cp_next[PLAYER_SLOT];
    int16_t player_px;
    int16_t player_py;

    /* Defer player position read until needed for Manhattan tiebreaker */
    for (i = 0u; i < MAX_RACERS; i++) {
        if (i == PLAYER_SLOT) continue;
        if (!rs_active[i]) continue;

        if (player_laps > rs_laps[i]) {
            /* player ahead on laps — pos stays 1 */
        } else if (player_laps < rs_laps[i]) {
            pos = 2u;
        } else if (player_cp > rs_cp_next[i]) {
            /* tied on laps, player ahead on checkpoints */
        } else if (player_cp < rs_cp_next[i]) {
            pos = 2u;
        } else {
            /* Full tie: Manhattan distance to next checkpoint */
            const CheckpointDef *next;
            uint8_t finish_dir;
            uint8_t count = track_get_checkpoint_count();

            player_px = player_get_x();
            player_py = player_get_y();

            if (player_cp < count) {
                next = &track_get_checkpoints()[player_cp];
                if (pos_from_manhattan(player_px, player_py,
                                       racer_get_px(i), racer_get_py(i),
                                       next) == 2u) {
                    pos = 2u;
                }
            } else {
                /* Past all CPs — compare by finish direction */
                finish_dir = track_get_finish_direction();
                if (pos_from_dir(finish_dir, player_px, player_py,
                                 racer_get_px(i), racer_get_py(i)) == 2u) {
                    pos = 2u;
                }
            }
        }
    }
    return pos;
}

#ifndef __SDCC
void race_state_set_laps_for_test(uint8_t slot, uint8_t n) { rs_laps[slot] = n; }
void race_state_set_cp_for_test(uint8_t slot, uint8_t n)   { rs_cp_next[slot] = n; }
#endif
```

**Note:** `race_state_rank_player()` calls `player_get_x()`, `player_get_y()`, `racer_get_px()`, `racer_get_py()`. Add forward declarations to `race_state.h` or keep the includes in `race_state.c`. The implementation file must `#include "player.h"` and `#include "racer.h"`.

Update the `#include` block in `race_state.c`:
```c
#pragma bank 255
#include "race_state.h"
#include "track.h"
#include "player.h"    /* player_get_x(), player_get_y(), DIR_T/B/L/R/... */
#include "racer.h"     /* racer_get_px(), racer_get_py() */
```

And add forward declarations for `pos_from_dir` / `pos_from_manhattan` to the top of `race_state.c` (before `race_state_rank_player`) or place those functions before `race_state_rank_player` in the file.

- [ ] **Step 2: Run tests — `test_race_state` must now pass**

```powershell
make test
```
Expected: ALL tests pass including `test_race_state`.

- [ ] **Step 3: Commit**

```powershell
git add src/race_state.c
git commit -m "feat: implement race_state.c — unified per-slot cp/lap tracking"
```

---

## Task 6: Migrate `state_playing.c` and `state_playing.h`

**Files:**
- Modify: `src/state_playing.c`
- Modify: `src/state_playing.h`
- Modify: `tests/test_state_playing.c`

### `src/state_playing.c` changes

- [ ] **Step 1: Update includes**

At the top of `state_playing.c`, find:
```c
#include "checkpoint.h"
```
and:
```c
... (lap.h somewhere in the includes) ...
```
Replace both with:
```c
#include "race_state.h"
```
Remove `#include "lap.h"` and `#include "checkpoint.h"`.

- [ ] **Step 2: Remove `pos_from_dir` and `pos_from_manhattan` functions from `state_playing.c`**

Delete the entire `pos_from_dir` function (lines 48–60):
```c
#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
pos_from_dir(uint8_t dir, ...) { ... }
```

Delete the entire `pos_from_manhattan` function (lines 62–79):
```c
#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
pos_from_manhattan(...) { ... }
```

These now live in `race_state.c`.

- [ ] **Step 3: Update `enter()` — replace `lap_init` + `checkpoint_init` with `race_state_init`**

Find in `enter()` (around lines 127–133):
```c
    lap_init(track_get_lap_count());
    ...
    checkpoint_init(track_get_checkpoints(), track_get_checkpoint_count());
```
Replace with:
```c
    race_state_init(track_get_lap_count());
    race_state_set_active(PLAYER_SLOT, 1u);
```

Also update the HUD lap init line (around line 137):
```c
    hud_set_lap(lap_get_current(), lap_get_total());
```
Replace with:
```c
    hud_set_lap(race_state_get_laps(PLAYER_SLOT) + 1u, race_state_get_lap_total());
```

- [ ] **Step 4: Update `update()` — replace checkpoint update call**

Find (around line 206):
```c
        checkpoint_update(px, py, pdir);
```
Replace with:
```c
        race_state_update_cp(PLAYER_SLOT, px, py, pdir);
```

- [ ] **Step 5: Update `update()` — replace inline position block with `race_state_rank_player()`**

Find the entire position ranking block (lines 219–246):
```c
        /* Race position: 3-level comparison ... */
        {
            uint8_t player_laps = (uint8_t)(lap_get_current() - 1u);
            uint8_t racer_laps  = racer_get_laps_done(0u);
            uint8_t pos;
            if (player_laps > racer_laps) {
                pos = 1u;
            } else if (player_laps < racer_laps) {
                pos = 2u;
            } else {
                ...
            }
            hud_set_position(pos);
        }
```
Replace the entire block with:
```c
        hud_set_position(race_state_rank_player());
```

- [ ] **Step 6: Update `update()` — replace finish detection (checkpoint + lap)**

Find in the finish detection block (around lines 262–284):
```c
            uint8_t cps_ok = checkpoint_all_cleared();
            if (finish_eval(active_map_type_cache, finish_armed,
                            pdir, finish_dir_cache,
                            cps_ok)) {
                finish_armed = 0u;
                if (active_map_type_cache == TRACK_TYPE_COMBAT) {
                    state_pop();
                    return;
                }
                if (lap_advance()) {
                    /* Final lap complete — award scrap and show results */
                    { ... }
                    state_replace(&state_results, BANK(state_results));
                    return;
                }
                /* Lap complete — reset checkpoints for next lap, update HUD */
                checkpoint_reset();
                hud_set_lap(lap_get_current(), lap_get_total());
            }
```
Replace with:
```c
            uint8_t cps_ok = race_state_all_cp_cleared(PLAYER_SLOT);
            if (finish_eval(active_map_type_cache, finish_armed,
                            pdir, finish_dir_cache,
                            cps_ok)) {
                finish_armed = 0u;
                if (active_map_type_cache == TRACK_TYPE_COMBAT) {
                    state_pop();
                    return;
                }
                if (race_state_advance_lap(PLAYER_SLOT)) {
                    /* Final lap complete — award scrap and show results */
                    {
                        uint16_t reward = track_get_reward();
                        state_results_set_earned(reward);
                        economy_add_scrap(reward);
                    }
                    state_replace(&state_results, BANK(state_results));
                    return;
                }
                /* Lap complete — checkpoint reset is internal to race_state_advance_lap */
                hud_set_lap(race_state_get_laps(PLAYER_SLOT) + 1u, race_state_get_lap_total());
            }
```

### `src/state_playing.h` changes

- [ ] **Step 7: Remove `pos_from_dir` / `pos_from_manhattan` declarations**

In `state_playing.h`, delete the `#ifndef __SDCC` block for these two functions:
```c
/* Test-only seam: direction-aware position comparison. */
uint8_t pos_from_dir(uint8_t dir,
                     int16_t px,  int16_t py,
                     int16_t rpx, int16_t rpy);
/* Test-only seam: Manhattan-distance tiebreaker to checkpoint center. */
uint8_t pos_from_manhattan(int16_t px,  int16_t py,
                           int16_t rpx, int16_t rpy,
                           const CheckpointDef *next);
```

### `tests/test_state_playing.c` changes

- [ ] **Step 8: Remove `pos_from_dir` / `pos_from_manhattan` tests and update includes**

In `tests/test_state_playing.c`:

1. Change the comment on the `track.h` include:
```c
#include "track.h"         /* TRACK_TYPE_RACE, TRACK_TYPE_COMBAT, CHECKPOINT_DIR_* */
```

2. Delete all test functions that test `pos_from_dir` and `pos_from_manhattan` (these are now in `test_race_state.c`):
   - `test_pos_from_dir_N_player_ahead`
   - `test_pos_from_dir_N_racer_ahead`
   - `test_pos_from_dir_S_player_ahead`
   - `test_pos_from_dir_S_racer_ahead`
   - `test_pos_from_dir_E_player_ahead`
   - `test_pos_from_dir_E_racer_ahead`
   - `test_pos_from_dir_W_player_ahead`
   - `test_pos_from_dir_W_racer_ahead`
   - `test_pos_from_manhattan_player_closer`
   - `test_pos_from_manhattan_racer_closer`
   - `test_pos_from_manhattan_equal_distance_favors_player`
   - `test_pos_from_manhattan_nonsquare_checkpoint`

3. Remove corresponding `RUN_TEST(...)` calls from `main()`.

- [ ] **Step 9: Run tests — all must pass**

```powershell
make test
```
Expected: all tests pass. `test_state_playing` runs only `finish_eval` and `cd_advance` tests.

- [ ] **Step 10: Commit**

```powershell
git add src/state_playing.c src/state_playing.h tests/test_state_playing.c
git commit -m "feat: migrate state_playing.c to race_state API"
```

---

## Task 7: Migrate `racer.c` and `racer.h`

**Files:**
- Modify: `src/racer.c`
- Modify: `src/racer.h`
- Modify: `tests/test_racer.c`

### `src/racer.c` changes

- [ ] **Step 1: Update includes**

Replace `#include "checkpoint.h"` with `#include "race_state.h"` in the include block of `racer.c`.

- [ ] **Step 2: Remove `racer_cp_next[]` array and `s_laps_done` / `s_lap_total` variables**

In the SoA pool section (lines 31, 39–40), remove:
```c
static uint8_t  racer_cp_next[MAX_RACERS];
```
and:
```c
static uint8_t  s_laps_done;  /* completed wp cycles so far */
static uint8_t  s_lap_total;  /* number of full wp cycles required to win */
```

- [ ] **Step 3: Remove `racer_checkpoint_update()` static function**

Delete the entire `racer_checkpoint_update()` function (lines 255–285):
```c
static void racer_checkpoint_update(uint8_t slot) { ... }
```

- [ ] **Step 4: Update `racer_init()` — remove cp/lap setup, add `race_state` calls**

In `racer_init()`, in the loop that zeros each slot (lines 180–189), remove:
```c
        racer_cp_next[i]   = 0u;
```

Also remove both lines:
```c
    s_laps_done  = 0u;
```
and:
```c
    s_lap_total  = track_get_lap_count();
```

After the `if (found && s_wp_count > 0u)` block activates slot 0 (after `racer_active[0] = 1u;`), add:
```c
        race_state_set_active(0u, 1u);
```

- [ ] **Step 5: Update `racer_init_empty()` — remove cp/lap setup, add `race_state_init`**

In `racer_init_empty()`, in the loop, remove:
```c
        racer_cp_next[i]   = 0u;
```

Remove:
```c
    s_laps_done = 0u;
    s_lap_total = 1u;
```

Add at the end of the function:
```c
    race_state_init(1u);
```

- [ ] **Step 6: Update `racer_update()` — replace checkpoint call and finish detection**

In the waypoint advance block (lines 323–330), find:
```c
        if ((uint8_t)(abs_dx + abs_dy) < RACER_WP_THRESHOLD) {
            racer_wp_idx[i]++;
            if (racer_wp_idx[i] >= s_wp_count) {
                racer_wp_idx[i] = 0u;
                s_laps_done++;
                racer_cp_next[i] = 0u;
            }
        }
```
Replace with:
```c
        if ((uint8_t)(abs_dx + abs_dy) < RACER_WP_THRESHOLD) {
            racer_wp_idx[i]++;
            if (racer_wp_idx[i] >= s_wp_count) {
                racer_wp_idx[i] = 0u;
            }
        }
```

Replace the call to `racer_checkpoint_update(i)` (line 335) with:
```c
        race_state_update_cp(i, racer_px[i], racer_py[i], dir);
```

Replace the finish detection block (lines 343–347):
```c
        if (s_laps_done >= s_lap_total && tile_type == TILE_FINISH) {
            if (racer_dir_matches_finish(dir, s_finish_dir)) {
                return 1u;
            }
        }
```
With:
```c
        if (tile_type == TILE_FINISH) {
            if (racer_dir_matches_finish(dir, s_finish_dir)) {
                if (race_state_all_cp_cleared(i)) {
                    if (race_state_advance_lap(i)) {
                        return 1u;
                    }
                }
            }
        }
```

- [ ] **Step 7: Remove `racer_get_cp_next()` and `racer_get_laps_done()` from accessors (lines 539–540)**

Delete:
```c
uint8_t racer_get_cp_next(uint8_t slot) BANKED { return racer_cp_next[slot]; }
uint8_t racer_get_laps_done(uint8_t slot) BANKED { (void)slot; return s_laps_done; }
```

- [ ] **Step 8: Update `racer_spawn_for_test()` — replace `s_laps_done` with `race_state` calls**

In `racer_spawn_for_test()`, remove:
```c
    s_laps_done  = lap_total;  /* ready to trigger finish detection */
    racer_cp_next[0]   = 0u;
```
Replace with:
```c
    race_state_init(lap_total);
    race_state_set_active(0u, 1u);
```

- [ ] **Step 9: Remove `racer_set_laps_done_for_test()`, `racer_set_cp_next_for_test()`, and `racer_checkpoint_update_for_test()` from `#ifndef __SDCC` block**

Delete these three functions from `racer.c`:
```c
void racer_set_laps_done_for_test(uint8_t n) { s_laps_done = n; }
...
void    racer_set_cp_next_for_test(uint8_t slot, uint8_t val) { racer_cp_next[slot] = val; }
...
void racer_checkpoint_update_for_test(uint8_t slot)    { racer_checkpoint_update(slot); }
```

### `src/racer.h` changes

- [ ] **Step 10: Remove old declarations**

In `racer.h`, delete the two BANKED function declarations:
```c
uint8_t racer_get_cp_next(uint8_t slot) BANKED;
uint8_t racer_get_laps_done(uint8_t slot) BANKED;
```

In the `#ifndef __SDCC` block, delete:
```c
void    racer_set_laps_done_for_test(uint8_t n);
...
void    racer_set_cp_next_for_test(uint8_t slot, uint8_t val);
...
void    racer_checkpoint_update_for_test(uint8_t slot);
```

### `tests/test_racer.c` changes

- [ ] **Step 11: Update includes**

Replace:
```c
#include "checkpoint.h"
```
with:
```c
#include "race_state.h"
```

- [ ] **Step 12: Update `test_racer_no_finish_before_all_laps_done`**

Find:
```c
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    racer_set_laps_done_for_test(2u);  /* 2 of 3 laps done */
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_update());
```
Replace with:
```c
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    race_state_set_laps_for_test(0u, 1u);  /* 1 of 3 laps done — 2 more needed */
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_update());
```

- [ ] **Step 13: Update `test_racer_finishes_after_all_laps_done`**

Find:
```c
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    /* racer_spawn_for_test sets s_laps_done = lap_total = 3 */
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_update());
```
Replace with:
```c
    racer_spawn_for_test(44u, 44u, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    race_state_set_laps_for_test(0u, 2u);  /* 2 of 3 laps done — one more finishes */
    racer_place_on_finish_for_test(5u, 6u, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, racer_update());
```

- [ ] **Step 14: Update `test_racer_get_cp_next_initial_zero`**

Replace:
```c
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_cp_next(0u));
```
With:
```c
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
```

- [ ] **Step 15: Update `test_racer_spawn_resets_cp_next`**

Replace:
```c
    racer_set_cp_next_for_test(0u, 5u);  /* pre-pollute */
    racer_spawn_for_test(80, 80, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_cp_next(0u));
```
With:
```c
    race_state_set_cp_for_test(0u, 5u);  /* pre-pollute */
    racer_spawn_for_test(80, 80, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
```

- [ ] **Step 16: Update `test_racer_cp_next_increments_on_matching_dir`**

The old test used `racer_checkpoint_update_for_test`. Replace it with a direct call to `race_state_update_cp`. The racer is spawned at (110, 408) with direction set to DIR_B:
```c
void test_racer_cp_next_increments_on_matching_dir(void) {
    CheckpointDef defs[1];
    setup_one_checkpoint_south(defs);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(110, 408, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    race_state_update_cp(0u, 110, 408, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(1u, race_state_get_cp(0u));
}
```

- [ ] **Step 17: Update `test_racer_cp_next_no_increment_wrong_dir`**

```c
void test_racer_cp_next_no_increment_wrong_dir(void) {
    CheckpointDef defs[1];
    setup_one_checkpoint_south(defs);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(110, 408, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    race_state_update_cp(0u, 110, 408, DIR_T);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}
```

- [ ] **Step 18: Replace `test_racer_cp_next_resets_on_lap_wrap` with a simpler test**

The old test verified waypoint wrap resets cp — behavior that no longer exists. Replace the test with one that confirms waypoint wrap does NOT implicitly reset cp (behavior remains in race_state_advance_lap):

```c
void test_racer_wp_wrap_does_not_reset_cp(void) {
    /* After waypoint cycle wraps, cp_next is unchanged — only race_state_advance_lap resets it */
    CheckpointDef defs[1];
    track_test_set_checkpoints(defs, 0u);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(80, 80, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 3u);
    race_state_set_cp_for_test(0u, 2u);
    racer_set_wp_idx_for_test(0u, 0u);
    racer_set_pos_for_test(0u, 80, 80);
    static const uint8_t flat[16*16] = {0};
    track_test_set_map(flat, 16u, 16u);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(2u, race_state_get_cp(0u));  /* unchanged by wp wrap */
}
```

- [ ] **Step 19: Update `test_racer_cp_next_sequential_order_enforced`**

```c
void test_racer_cp_next_sequential_order_enforced(void) {
    CheckpointDef defs[2];
    defs[0].x = 200; defs[0].y = 200; defs[0].w = 8;  defs[0].h = 8;
    defs[0].index = 0u; defs[0].direction = CHECKPOINT_DIR_S;
    defs[1].x = 96;  defs[1].y = 400; defs[1].w = 40; defs[1].h = 16;
    defs[1].index = 1u; defs[1].direction = CHECKPOINT_DIR_S;
    track_test_set_checkpoints(defs, 2u);
    uint8_t wp_tx[1] = { 10u }, wp_ty[1] = { 10u };
    racer_spawn_for_test(110, 408, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_S, 3u);
    /* Try to clear cp[1] (at 96,400) while cp[0] (at 200,200) not cleared */
    race_state_update_cp(0u, 110, 408, DIR_B);
    TEST_ASSERT_EQUAL_UINT8(0u, race_state_get_cp(0u));
}
```

- [ ] **Step 20: Update `main()` in `test_racer.c`**

Replace:
```c
    RUN_TEST(test_racer_cp_next_resets_on_lap_wrap);
```
With:
```c
    RUN_TEST(test_racer_wp_wrap_does_not_reset_cp);
```

- [ ] **Step 21: Run tests — all must pass**

```powershell
make test
```
Expected: all tests pass.

- [ ] **Step 22: Commit**

```powershell
git add src/racer.c src/racer.h tests/test_racer.c
git commit -m "feat: migrate racer.c to race_state API; remove duplicate cp/lap tracking"
```

---

## Task 8: Delete old modules and run final build

**Files:**
- Delete: `src/checkpoint.c`, `src/checkpoint.h`, `src/lap.c`, `src/lap.h`
- Delete: `tests/test_checkpoint.c`, `tests/test_lap.c`

- [ ] **Step 1: Confirm no remaining references to deleted modules**

```powershell
Select-String -Path "src\*.c","src\*.h","tests\*.c" -Pattern "checkpoint\.h|lap\.h|lap_init|lap_get|lap_advance|checkpoint_init|checkpoint_update|checkpoint_all_cleared|checkpoint_reset|checkpoint_get" | Where-Object { $_.Filename -notmatch "checkpoint\.(c|h)|lap\.(c|h)|test_checkpoint|test_lap" }
```
Expected: no output (zero matches outside the files being deleted).

- [ ] **Step 2: Delete the files**

```powershell
Remove-Item src\checkpoint.c, src\checkpoint.h, src\lap.c, src\lap.h
Remove-Item tests\test_checkpoint.c, tests\test_lap.c
```

- [ ] **Step 3: Run tests — all must pass**

```powershell
make test
```
Expected: all tests pass. `test_checkpoint` and `test_lap` no longer appear in output.

- [ ] **Step 4: Build ROM**

```powershell
make clean && make
```
Expected: ROM builds with no errors or warnings.

- [ ] **Step 5: Commit deletion**

```powershell
git add -A
git commit -m "chore: delete checkpoint.c/h, lap.c/h and their test files (replaced by race_state)"
```

---

## Task 9: Smoketest and PR

**Files:**
- Modify: `README.md` (if needed — no user-visible behavior change, likely none)

- [ ] **Step 1: Fetch and merge latest master**

```powershell
git fetch origin && git merge origin/master
```

- [ ] **Step 2: Clean build**

```powershell
make clean && make
```
Expected: no errors. `make memory-check` fires automatically via hook — check output for no FAIL/ERROR.

- [ ] **Step 3: Ask user to confirm smoketest**

Ask: "Ready to launch the ROM in Emulicious for smoketest — go ahead?"

If confirmed:
```powershell
Start-Process "java" "-jar C:\Tools\Emulicious\Emulicious.jar build\nuke-raider.gb"
```

- [ ] **Step 4: Verify in emulator**

Check:
- HUD shows correct lap (1-based) and position rank during a race
- Player wins by crossing finish after clearing all CPs on final lap
- Enemy win triggers game-over state
- No crashes or visual glitches vs. pre-refactor behavior

- [ ] **Step 5: Push and create PR**

```powershell
git push -u origin worktree-feat-race-state-unification
gh pr create --title "feat: unify race tracking state into race_state.c" --body "$(cat <<'EOF'
## Summary
- New `race_state.c` owns all per-slot checkpoint/lap tracking for both player (slot 1) and enemy racers (slot 0+)
- Deleted `checkpoint.c`, `checkpoint.h`, `lap.c`, `lap.h` — logic consolidated into `race_state.c`
- `state_playing.c` and `racer.c` now call identical `race_state_update_cp()` / `race_state_advance_lap()` APIs
- `race_state_rank_player()` replaces the inline 3-level position comparison in `state_playing.c`
- `MAX_RACERS` bumped 1→2; `PLAYER_SLOT = 1` constant added to `config.h`
- `pos_from_dir` / `pos_from_manhattan` moved from `state_playing.c` to `race_state.c`

## Test plan
- [ ] `make test` passes with no failures
- [ ] `make clean && make` succeeds with no errors
- [ ] `make memory-check` shows no FAIL/ERROR budgets
- [ ] Smoketest in Emulicious: HUD lap and position correct; player win and enemy win both trigger correctly

Closes #398
EOF
)"
```
