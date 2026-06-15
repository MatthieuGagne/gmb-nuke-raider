# Enemy Racer Car Explosion on Death Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an enemy racer's HP reaches 0, play the same 16×16 car blast the player plays (from #267) on the racer's own 4 OAM slots for ~2 s, then free the slot — without affecting OAM budgets or the player's game-over timing.

**Architecture:** The player blast cheats positioning: the player is screen-centered and frozen on death, so `player_render` returns early and the 4 slots keep their last (center) position while `explosion_render` only swaps tiles. A racer moves in world space and the camera keeps scrolling, so its blast must be **repositioned every frame**. We give the racer a short **dying state**: on a lethal hit it sets `racer_active[i]=0` immediately (so it stops racing/colliding — preserving every existing test), sets `racer_dying[i]=1` with a `racer_death_timer[i]` counting down `RACER_DEATH_TICKS` (= the 120-tick blast length), zeroes its velocity, and spawns 4 car blasts on its own 4 OAM handles. While dying, `racer_render` keeps positioning those 4 slots at the racer's frozen world position (off-screen-aware), and `explosion_render` swaps the blast tiles — mirroring the player↔explosion contract. When `racer_death_timer` hits 0 the dying flag clears, and the existing inactive-render path hides the slots on the next frame.

Two cross-cutting concerns are handled in `explosion.c`:
1. **Game-over gate decoupling.** `explosion_is_done()` (which gates the player's game-over) counts only **player** car blasts. We introduce explicit kind constants (`EXPLOSION_KIND_TURRET=0`, `EXPLOSION_KIND_PLAYER=1`, `EXPLOSION_KIND_RACER=2`). Only `EXPLOSION_KIND_PLAYER` touches the `s_car_active` gate. Existing callers pass `0u`/`1u` which now equal `TURRET`/`PLAYER` — **no change to `player.c`/`turret.c` is required**.
2. **Slot-ownership during the blast.** Enemy-kind blasts skip the `clear_sprite()` call on completion (the racer owns hiding its own slots via its inactive-render path). This prevents the explosion from blanking a slot the racer is still positioning, which would otherwise flash sprite tile 0 for one frame.

**Tech Stack:** GBDK-2020 / SDCC (Game Boy Color ROM), C. Host-side unit tests with Unity + mock GBDK headers (gcc, no hardware). Both `explosion.c` and `racer.c` are bank 255 (autobank) — no `bank-manifest.json` change (no new files).

---

## File Structure

No new files. All changes are to existing modules:

- **`src/config.h`** — add `RACER_DEATH_TICKS` constant.
- **`src/explosion.h`** — add `EXPLOSION_KIND_*` constants; declare `explosion_car_base()`.
- **`src/explosion.c`** — store `car_base` in `explosion_init`; add `explosion_car_base()`; gate `s_car_active` on `EXPLOSION_KIND_PLAYER` only; skip `clear_sprite` for `EXPLOSION_KIND_RACER`.
- **`src/racer.h`** — declare new test helpers (`racer_is_dying_for_test`, `racer_get_death_timer_for_test`, `racer_set_oam_for_test`).
- **`src/racer.c`** — add `#include "explosion.h"`; add `racer_dying[]` + `racer_death_timer[]` SoA arrays; init them; dying branch in `racer_update`; dying branch in `racer_render`; spawn blasts on the lethal-hit path; new test helpers.
- **`tests/test_explosion.c`** — tests for kind-gating and racer-kind skip-clear.
- **`tests/test_racer.c`** — tests for the death→dying→blast→deactivate lifecycle and gate decoupling.
- **`README.md`** — note enemy cars now explode on death (user-visible).

**No Makefile change:** `TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))` (Makefile:21) links every `src/*.c` into every test binary, so `test_racer` already links `explosion.c`.

---

## Reference: existing code this plan builds on

**`src/explosion.c` (current — lines 17, 26–43, 45–60, 82):**
```c
static uint8_t s_car_active;
/* ... */
void explosion_spawn(uint8_t oam, uint8_t tile_base, uint8_t flip, uint8_t is_car, uint8_t wx, uint8_t wty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) {
        if (!exp_active[i]) {
            exp_active[i] = 1u;
            exp_frame[i]  = 0u;
            exp_timer[i]  = 0u;
            exp_oam[i]    = oam;
            exp_tile[i]   = tile_base;
            exp_flip[i]   = flip;
            exp_car[i]    = is_car;
            exp_wx[i]     = wx;
            exp_wty[i]    = wty;
            if (is_car) s_car_active++;
            return;
        }
    }
}

void explosion_update(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) {
        if (!exp_active[i]) continue;
        exp_timer[i]++;
        if (exp_timer[i] >= EXPLOSION_FRAME_TICKS) {
            exp_timer[i] = 0u;
            exp_frame[i]++;
            if (exp_frame[i] >= EXPLOSION_NUM_FRAMES) {
                exp_active[i] = 0u;
                if (exp_car[i] && s_car_active) s_car_active--;
                clear_sprite(exp_oam[i]);
            }
        }
    }
}

uint8_t explosion_is_done(void) BANKED { return (s_car_active == 0u) ? 1u : 0u; }
```

**`src/racer.c` lethal-hit path (current — lines 397–404):**
```c
if (projectile_check_hit_enemy((uint8_t)scr_cx, (uint8_t)scr_cy, RACER_HIT_RADIUS)) {
    racer_hp[i] = (uint8_t)(racer_hp[i] - 1u);
    racer_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
    if (racer_hp[i] == 0u) {
        racer_active[i] = 0u;
    }
}
```

**`src/racer.c` render positioning (current — lines 442–484):** screen pos is `scr_x = racer_px[i] + 8; scr_y = racer_py[i] - cam_y + 16;` then the 4 slots are placed as a 2×2 grid: slot0=`(hw_x,hw_y)` TL, slot1=`(hw_x,hw_y+8)` BL, slot2=`(hw_x+8,hw_y)` TR, slot3=`(hw_x+8,hw_y+8)` BR. Off-screen test: `scr_x < 0 || scr_x >= 168 || scr_y < 0 || scr_y >= 160`.

**Player blast call shape (for the quadrant flip mapping — `src/player.c` ~301–304):** TL=`0`, BL=`S_FLIPY`, TR=`S_FLIPX`, BR=`S_FLIPX|S_FLIPY`, all `is_car=1`, `wx=wty=0`.

---

## Task 1: Add `RACER_DEATH_TICKS` constant

**Files:**
- Modify: `src/config.h` (after the explosion pool block, lines 135–138)

- [ ] **Step 1: Add the constant**

In `src/config.h`, immediately after the existing explosion pool block:
```c
/* Explosion pool */
#define MAX_EXPLOSIONS        12u  /* simultaneous explosion instances (turret + car quadrants) */
#define EXPLOSION_NUM_FRAMES   3u  /* frames in the explosion sprite sheet */
#define EXPLOSION_FRAME_TICKS 40u  /* ticks per frame (~0.67 s total at 60 fps) */
```
add:
```c
/* Racer death blast: dying racer holds its 4 OAM slots for the full car-blast
 * length so the 16x16 explosion (#411) plays out before the slot is freed.
 * Equals the explosion lifetime: EXPLOSION_NUM_FRAMES * EXPLOSION_FRAME_TICKS = 120 ticks (~2 s). */
#define RACER_DEATH_TICKS     (EXPLOSION_NUM_FRAMES * EXPLOSION_FRAME_TICKS)
```

- [ ] **Step 2: Commit**

```bash
git add src/config.h
git commit -m "feat(racer): add RACER_DEATH_TICKS constant for death blast (#411)"
```

---

## Task 2: Explosion kind constants + `explosion_car_base()` accessor

**Files:**
- Modify: `src/explosion.h`
- Test: `tests/test_explosion.c`

- [ ] **Step 1: Write the failing test for `explosion_car_base()`**

In `tests/test_explosion.c`, add this test after `test_explosion_init_empty` (around line 21):
```c
void test_car_base_returns_init_value(void) {
    explosion_init(T_BASE, C_BASE);
    TEST_ASSERT_EQUAL_UINT8(C_BASE, explosion_car_base());
}
```
And register it in `main()` after `RUN_TEST(test_explosion_init_empty);`:
```c
    RUN_TEST(test_car_base_returns_init_value);
```

- [ ] **Step 2: Run test to verify it fails**

Run (from the worktree, PowerShell):
```powershell
$env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
make test
```
Expected: FAIL — `test_explosion` does not compile: `explosion_car_base` undeclared.

- [ ] **Step 3: Add the kind constants and the accessor declaration**

In `src/explosion.h`, between the `#include` and the `explosion_init` declaration:
```c
#ifndef EXPLOSION_H
#define EXPLOSION_H
#include <stdint.h>

/* Explosion kinds — the `is_car` parameter of explosion_spawn().
 * TURRET: self-positions each frame from world coords (wx px, wty tiles).
 * PLAYER: positioned by player_render; gates game-over via explosion_is_done().
 * RACER:  positioned by racer_render; does NOT gate game-over and skips
 *         clear_sprite on completion (the racer owns hiding its own slots). */
#define EXPLOSION_KIND_TURRET 0u
#define EXPLOSION_KIND_PLAYER 1u
#define EXPLOSION_KIND_RACER  2u

void explosion_init(uint8_t turret_base, uint8_t car_base) BANKED;
void explosion_spawn(uint8_t oam, uint8_t tile_base, uint8_t flip, uint8_t is_car, uint8_t wx, uint8_t wty) BANKED;
void explosion_update(void) BANKED;
void explosion_render(void) BANKED;
uint8_t explosion_is_done(void) BANKED;
uint8_t explosion_car_base(void) BANKED;
```
(Leave the `#ifndef __SDCC` / `explosion_active_count` block and `#endif` as they are.)

> Note: `explosion.h` does not currently include `banking.h`, yet uses `BANKED`. The existing declarations already rely on `BANKED` being visible via the includer's prior includes (every `.c` that includes `explosion.h` includes `<gb/gb.h>` or `banking.h` first). Follow the existing pattern — do not add includes.

- [ ] **Step 4: Implement `explosion_car_base()` and store `car_base` (in `explosion.c`)**

In `src/explosion.c`, add a file-scope variable next to the other statics (after line 17 `static uint8_t s_car_active;`):
```c
static uint8_t s_car_base;
```
Change `explosion_init` (lines 19–24) to store `car_base` instead of discarding it:
```c
void explosion_init(uint8_t turret_base, uint8_t car_base) BANKED {
    uint8_t i;
    (void)turret_base;
    s_car_base = car_base;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) exp_active[i] = 0u;
    s_car_active = 0u;
}
```
Add the accessor after `explosion_is_done` (after line 82):
```c
uint8_t explosion_car_base(void) BANKED { return s_car_base; }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `make test`
Expected: `test_explosion` passes (all its tests, including the new `test_car_base_returns_init_value`). Other test binaries unaffected.

- [ ] **Step 6: Commit**

```bash
git add src/explosion.h src/explosion.c tests/test_explosion.c
git commit -m "feat(explosion): add kind constants + explosion_car_base accessor (#411)"
```

---

## Task 3: Decouple the game-over gate by kind

**Files:**
- Modify: `src/explosion.c` (`explosion_spawn`, `explosion_update`)
- Test: `tests/test_explosion.c`

- [ ] **Step 1: Write the failing test — racer-kind blast does NOT gate done**

In `tests/test_explosion.c`, add after `test_car_blast_gates_done` (line 84):
```c
void test_racer_blast_does_not_gate_done(void) {
    explosion_init(T_BASE, C_BASE);
    /* Racer-kind car blast must animate but NOT make explosion_is_done() false. */
    explosion_spawn(0u, C_BASE, 0u,                          EXPLOSION_KIND_RACER, 0u, 0u);
    explosion_spawn(2u, C_BASE, S_FLIPX,                     EXPLOSION_KIND_RACER, 0u, 0u);
    explosion_spawn(1u, C_BASE, S_FLIPY,                     EXPLOSION_KIND_RACER, 0u, 0u);
    explosion_spawn(3u, C_BASE, (uint8_t)(S_FLIPX|S_FLIPY),  EXPLOSION_KIND_RACER, 0u, 0u);
    TEST_ASSERT_EQUAL_UINT8(4u, explosion_active_count());  /* 4 blasts active */
    TEST_ASSERT_TRUE(explosion_is_done());                  /* but game-over gate stays clear */
}
```
Register in `main()` after `RUN_TEST(test_car_blast_gates_done);`:
```c
    RUN_TEST(test_racer_blast_does_not_gate_done);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL — `test_racer_blast_does_not_gate_done`: `explosion_is_done()` returns false because the current `if (is_car) s_car_active++;` increments for any non-zero kind (RACER=2 included).

- [ ] **Step 3: Gate only on PLAYER kind**

In `src/explosion.c` `explosion_spawn`, change line 39:
```c
            if (is_car) s_car_active++;
```
to:
```c
            if (is_car == EXPLOSION_KIND_PLAYER) s_car_active++;
```
In `explosion_update`, change line 55:
```c
                if (exp_car[i] && s_car_active) s_car_active--;
```
to:
```c
                if (exp_car[i] == EXPLOSION_KIND_PLAYER && s_car_active) s_car_active--;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `make test`
Expected: PASS — `test_racer_blast_does_not_gate_done` passes; `test_car_blast_gates_done` (player kind = `1u` = `EXPLOSION_KIND_PLAYER`) still passes; `test_turret_spawn_starts_frame0` (kind `0u`) still passes.

- [ ] **Step 5: Commit**

```bash
git add src/explosion.c tests/test_explosion.c
git commit -m "feat(explosion): only player car blasts gate game-over (#411)"
```

---

## Task 4: Racer-kind blasts skip `clear_sprite` on completion

**Files:**
- Modify: `src/explosion.c` (`explosion_update`)
- Test: `tests/test_explosion.c`

**Why:** While a racer is dying, `racer_render` positions the 4 slots every frame and `explosion_render` swaps the tiles. If `explosion_update` called `clear_sprite()` (which does `move_sprite(slot,0,0)` + sets tile 0) on completion, the next `racer_render` would re-position that slot showing sprite tile 0 for one frame. Skipping `clear_sprite` for racer-kind lets the final blast frame persist until the racer's own inactive-render path hides the slot.

- [ ] **Step 1: Write the failing test — racer-kind completion does NOT call clear_sprite**

In `tests/test_explosion.c`, add after the test from Task 3:
```c
void test_racer_blast_skips_clear_sprite_on_done(void) {
    uint8_t i;
    explosion_init(T_BASE, C_BASE);
    mock_move_sprite_reset();
    explosion_spawn(5u, C_BASE, 0u, EXPLOSION_KIND_RACER, 0u, 0u);
    for (i = 0u; i < 120u; i++) explosion_update();   /* run to completion */
    TEST_ASSERT_EQUAL_UINT8(0, explosion_active_count());     /* pool entry freed */
    TEST_ASSERT_EQUAL_INT(0, mock_move_sprite_call_count);    /* but NO clear_sprite */
}
```
Register in `main()` after the Task 3 registration:
```c
    RUN_TEST(test_racer_blast_skips_clear_sprite_on_done);
```

> Contrast: `test_completes_and_frees_oam_after_120_ticks` (line 49) asserts `mock_move_sprite_call_count > 0` for a **turret** blast — that path still calls `clear_sprite`. This new test asserts the racer path does not.

- [ ] **Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL — `mock_move_sprite_call_count` is 1 (current `explosion_update` calls `clear_sprite` for every kind on completion).

- [ ] **Step 3: Skip clear_sprite for racer kind**

In `src/explosion.c` `explosion_update`, change line 56:
```c
                clear_sprite(exp_oam[i]);
```
to:
```c
                /* Racer-kind: the racer owns hiding its own slots (it keeps
                 * positioning them while dying). Clearing here would flash
                 * tile 0 for a frame. Turret/player blasts still self-clear. */
                if (exp_car[i] != EXPLOSION_KIND_RACER) clear_sprite(exp_oam[i]);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `make test`
Expected: PASS — new test passes; `test_completes_and_frees_oam_after_120_ticks` (turret) still passes.

- [ ] **Step 5: Commit**

```bash
git add src/explosion.c tests/test_explosion.c
git commit -m "feat(explosion): racer-kind blast skips clear_sprite, racer owns slot (#411)"
```

---

## Task 5: Racer dying state — arrays, init, and test accessors

**Files:**
- Modify: `src/racer.c` (SoA arrays + `racer_init` + `racer_init_empty` + `racer_spawn_for_test` + test helpers)
- Modify: `src/racer.h` (test helper declarations)
- Test: `tests/test_racer.c`

- [ ] **Step 1: Write the failing test — dying flag/timer default to 0**

In `tests/test_racer.c`, add after `test_racer_hit_flash_initialized_to_zero` (line 426):
```c
void test_racer_not_dying_after_init(void) {
    /* racer_init_empty() called in setUp; no racer is dying yet. */
    TEST_ASSERT_EQUAL_UINT8(0u, racer_is_dying_for_test(1u));
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_death_timer_for_test(1u));
}
```
Register in `main()` after `RUN_TEST(test_racer_hit_flash_initialized_to_zero);`:
```c
    RUN_TEST(test_racer_not_dying_after_init);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL — `test_racer` does not compile: `racer_is_dying_for_test` / `racer_get_death_timer_for_test` undeclared.

- [ ] **Step 3: Add the SoA arrays and the include**

In `src/racer.c`, add the include after the existing includes (after line 15 `#include "vehicle_physics.h"`):
```c
#include "explosion.h"        /* car-blast spawn on death (#411) */
```
Add two arrays to the SoA pool, after line 32 (`static uint8_t racer_hit_flash[MAX_RACERS];`):
```c
static uint8_t  racer_dying[MAX_RACERS];       /* 1 = playing death blast, frozen */
static uint8_t  racer_death_timer[MAX_RACERS]; /* counts down RACER_DEATH_TICKS while dying */
```

- [ ] **Step 4: Initialize the arrays in all three init paths**

In `racer_init` (inside the `for` loop at lines 163–178), add after `racer_hit_flash[i] = 0u;` (line 170):
```c
        racer_dying[i]        = 0u;
        racer_death_timer[i]  = 0u;
```
In `racer_init_empty` (inside the loop at lines 221–230), add after `racer_hit_flash[i] = 0u;` (line 228):
```c
        racer_dying[i]        = 0u;
        racer_death_timer[i]  = 0u;
```
In `racer_spawn_for_test` (after line 557 `racer_hit_flash[1] = 0u;`):
```c
    racer_dying[1]       = 0u;
    racer_death_timer[1] = 0u;
```

- [ ] **Step 5: Add the test accessors (in `racer.c`, inside `#ifndef __SDCC`)**

In `src/racer.c`, add after `racer_get_hit_flash_for_test` (line 599):
```c
uint8_t racer_is_dying_for_test(uint8_t slot)        { return racer_dying[slot]; }
uint8_t racer_get_death_timer_for_test(uint8_t slot) { return racer_death_timer[slot]; }
void    racer_set_oam_for_test(uint8_t slot, uint8_t h0, uint8_t h1, uint8_t h2, uint8_t h3) {
    racer_oam[slot * 4u + 0u] = h0;
    racer_oam[slot * 4u + 1u] = h1;
    racer_oam[slot * 4u + 2u] = h2;
    racer_oam[slot * 4u + 3u] = h3;
}
```

- [ ] **Step 6: Declare the test accessors in `racer.h`**

In `src/racer.h`, inside the `#ifndef __SDCC` block, add after `racer_set_dir_for_test` (line 40):
```c
uint8_t racer_is_dying_for_test(uint8_t slot);
uint8_t racer_get_death_timer_for_test(uint8_t slot);
void    racer_set_oam_for_test(uint8_t slot, uint8_t h0, uint8_t h1, uint8_t h2, uint8_t h3);
```

- [ ] **Step 7: Run test to verify it passes**

Run: `make test`
Expected: PASS — `test_racer_not_dying_after_init` passes; all existing `test_racer` tests still pass (arrays are inert until Task 6 wires them).

- [ ] **Step 8: Commit**

```bash
git add src/racer.c src/racer.h tests/test_racer.c
git commit -m "feat(racer): add dying state arrays + test accessors (#411)"
```

---

## Task 6: Lethal hit spawns the car blast and enters dying state

**Files:**
- Modify: `src/racer.c` (lethal-hit path in `racer_update`)
- Test: `tests/test_racer.c`

- [ ] **Step 1: Write the failing tests — death spawns 4 blasts, enters dying, gate stays clear**

In `tests/test_racer.c`, add after `test_racer_destroyed_when_hp_reaches_zero` (line 460). These rely on `explosion.h` — add the include at the top of the file, after `#include "sprite_pool.h"` (line 9):
```c
#include "explosion.h"
```
Then the tests:
```c
void test_racer_death_enters_dying_state(void) {
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    explosion_init(20u, 23u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(1u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();   /* lethal hit */
    TEST_ASSERT_EQUAL_UINT8(0u, racer_active[1]);                 /* stops racing immediately */
    TEST_ASSERT_EQUAL_UINT8(1u, racer_is_dying_for_test(1u));     /* now dying */
    TEST_ASSERT_EQUAL_UINT8(RACER_DEATH_TICKS, racer_get_death_timer_for_test(1u));
}

void test_racer_death_spawns_four_car_blasts(void) {
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    explosion_init(20u, 23u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(1u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();   /* lethal hit */
    TEST_ASSERT_EQUAL_UINT8(4u, explosion_active_count());   /* 4 quadrant car blasts */
}

void test_racer_death_does_not_gate_game_over(void) {
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    track_test_set_map(flat_map, 8u, 8u);
    explosion_init(20u, 23u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(1u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();   /* lethal hit — racer blasts must NOT gate the player game-over */
    TEST_ASSERT_TRUE(explosion_is_done());
}
```
Register all three in `main()` after `RUN_TEST(test_racer_destroyed_when_hp_reaches_zero);`:
```c
    RUN_TEST(test_racer_death_enters_dying_state);
    RUN_TEST(test_racer_death_spawns_four_car_blasts);
    RUN_TEST(test_racer_death_does_not_gate_game_over);
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `test_racer_death_enters_dying_state` fails (`racer_is_dying_for_test` returns 0; the current path only sets `racer_active[1]=0`). `test_racer_death_spawns_four_car_blasts` fails (`explosion_active_count()` is 0).

- [ ] **Step 3: Implement the death→dying transition + blast spawn**

In `src/racer.c` `racer_update`, replace the lethal-hit block (lines 400–402):
```c
                    if (racer_hp[i] == 0u) {
                        racer_active[i] = 0u;
                    }
```
with:
```c
                    if (racer_hp[i] == 0u) {
                        /* Stop racing/colliding immediately; play the car blast
                         * on this racer's own 4 OAM slots (#411). Quadrant flip
                         * + slot order mirror player_kill() and racer_render():
                         * slot0=TL, slot1=BL, slot2=TR, slot3=BR. */
                        uint8_t base = explosion_car_base();
                        racer_active[i]       = 0u;
                        racer_dying[i]        = 1u;
                        racer_death_timer[i]  = (uint8_t)RACER_DEATH_TICKS;
                        racer_vx[i]           = (int8_t)0;
                        racer_vy[i]           = (int8_t)0;
                        explosion_spawn(racer_oam[i * 4u + 0u], base, 0u,                          EXPLOSION_KIND_RACER, 0u, 0u);
                        explosion_spawn(racer_oam[i * 4u + 1u], base, S_FLIPY,                      EXPLOSION_KIND_RACER, 0u, 0u);
                        explosion_spawn(racer_oam[i * 4u + 2u], base, S_FLIPX,                      EXPLOSION_KIND_RACER, 0u, 0u);
                        explosion_spawn(racer_oam[i * 4u + 3u], base, (uint8_t)(S_FLIPX | S_FLIPY), EXPLOSION_KIND_RACER, 0u, 0u);
                    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: PASS — all three new tests pass. `test_racer_destroyed_when_hp_reaches_zero` (asserts `racer_active[1]==0`) still passes because the death path sets `racer_active=0` immediately. `test_racer_dead_does_not_trigger_game_over` still passes: the racer is now `active==0` with `dying==1`, but with no dying branch yet (Task 7), the existing `if (!racer_active[i]) continue;` skips it, so the second `racer_update()` returns 0. The death timer simply does not count down until Task 7 wires the dying branch — that is fine; no test depends on the countdown until Task 7.

- [ ] **Step 5: Commit**

```bash
git add src/racer.c tests/test_racer.c
git commit -m "feat(racer): lethal hit spawns car blast + enters dying state (#411)"
```

---

## Task 7: Dying countdown in `racer_update` (freeze + deactivate)

**Files:**
- Modify: `src/racer.c` (`racer_update` loop)
- Test: `tests/test_racer.c`

- [ ] **Step 1: Write the failing tests — dying counts down, then fully deactivates**

In `tests/test_racer.c`, add after the Task 6 tests:
```c
void test_racer_dying_counts_down_and_deactivates(void) {
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    uint8_t i;
    track_test_set_map(flat_map, 8u, 8u);
    explosion_init(20u, 23u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(1u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();   /* lethal hit -> dying, timer = RACER_DEATH_TICKS */
    /* One more update decrements the timer by 1 (no underflow, no game over). */
    TEST_ASSERT_EQUAL_UINT8(0u, racer_update());
    TEST_ASSERT_EQUAL_UINT8(RACER_DEATH_TICKS - 1u, racer_get_death_timer_for_test(1u));
    TEST_ASSERT_EQUAL_UINT8(1u, racer_is_dying_for_test(1u));
    /* Run out the remaining timer. After RACER_DEATH_TICKS total dying updates,
     * the racer is no longer dying. (1 update already done above.) */
    for (i = 0u; i < (uint8_t)RACER_DEATH_TICKS - 1u; i++) {
        TEST_ASSERT_EQUAL_UINT8(0u, racer_update());
    }
    TEST_ASSERT_EQUAL_UINT8(0u, racer_is_dying_for_test(1u));
    TEST_ASSERT_EQUAL_UINT8(0u, racer_active[1]);
}
```
Register in `main()` after the Task 6 registrations:
```c
    RUN_TEST(test_racer_dying_counts_down_and_deactivates);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL — without a dying branch, the loop hits `if (!racer_active[i]) continue;` (active is 0), so `racer_death_timer` never decrements; `racer_is_dying_for_test` stays 1 forever.

- [ ] **Step 3: Add the dying branch at the top of the `racer_update` loop**

In `src/racer.c` `racer_update`, the loop body currently begins (line 266) with `if (!racer_active[i]) continue;`. Insert the dying branch immediately **before** it:
```c
        /* Dying: frozen while the death blast plays. No AI, physics, or finish
         * detection. When the timer expires, drop fully inactive (#411). */
        if (racer_dying[i]) {
            if (racer_death_timer[i] != 0u) {
                racer_death_timer[i]--;
                if (racer_death_timer[i] == 0u) {
                    racer_dying[i] = 0u;
                }
            }
            continue;
        }

        if (!racer_active[i]) continue;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `make test`
Expected: PASS — `test_racer_dying_counts_down_and_deactivates` passes; `test_racer_dead_does_not_trigger_game_over` passes (the dying branch returns 0).

- [ ] **Step 5: Commit**

```bash
git add src/racer.c tests/test_racer.c
git commit -m "feat(racer): dying countdown freezes racer then deactivates (#411)"
```

---

## Task 8: Position the blast every frame in `racer_render`

**Files:**
- Modify: `src/racer.c` (`racer_render` loop)
- Test: `tests/test_racer.c`

**Why:** While dying, the racer is `active==0`, so the existing render path would hide its 4 slots (lines 425–431). The blast must instead be positioned at the racer's frozen world coords every frame (the camera keeps scrolling), with `explosion_render` swapping the tiles.

- [ ] **Step 1: Write the failing test — dying blast renders the car tile on the racer's own slots**

In `tests/test_racer.c`, add after the Task 7 test:
```c
void test_racer_dying_blast_renders_on_own_slots(void) {
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    cam_y = 0;
    track_test_set_map(flat_map, 8u, 8u);
    explosion_init(20u, 23u);   /* car_base = 23 */
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    /* Give the racer distinct OAM handles so we can verify the blast lands on them. */
    racer_set_oam_for_test(1u, 10u, 11u, 12u, 13u);
    racer_set_hp_for_test(1u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();             /* lethal hit -> dying, blasts spawned on 10..13 */
    /* Mirror the in-game frame order: racer_render positions, explosion_render tiles. */
    mock_move_sprite_reset();
    racer_render();
    explosion_render();
    /* Car blast frame 0 == car_base (23) on each of the racer's 4 slots. */
    TEST_ASSERT_EQUAL_UINT8(23u, mock_sprite_tile[10]);
    TEST_ASSERT_EQUAL_UINT8(23u, mock_sprite_tile[11]);
    TEST_ASSERT_EQUAL_UINT8(23u, mock_sprite_tile[12]);
    TEST_ASSERT_EQUAL_UINT8(23u, mock_sprite_tile[13]);
    /* DECISIVE: racer_render positioned the 4 slots at the racer's on-screen
     * world pos (scr_x=32+8=40, scr_y=32-cam_y+16=48), NOT hidden at (0,0).
     * 2x2 grid: slot0=TL(40,48) slot1=BL(40,56) slot2=TR(48,48) slot3=BR(48,56). */
    TEST_ASSERT_EQUAL_UINT8(40u, mock_sprite_x[10]);
    TEST_ASSERT_EQUAL_UINT8(48u, mock_sprite_y[10]);
    TEST_ASSERT_EQUAL_UINT8(40u, mock_sprite_x[11]);
    TEST_ASSERT_EQUAL_UINT8(56u, mock_sprite_y[11]);
    TEST_ASSERT_EQUAL_UINT8(48u, mock_sprite_x[12]);
    TEST_ASSERT_EQUAL_UINT8(48u, mock_sprite_y[12]);
    TEST_ASSERT_EQUAL_UINT8(48u, mock_sprite_x[13]);
    TEST_ASSERT_EQUAL_UINT8(56u, mock_sprite_y[13]);
}
```
Register in `main()` after the Task 7 registration:
```c
    RUN_TEST(test_racer_dying_blast_renders_on_own_slots);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `make test`
Expected: FAIL — with no dying branch in `racer_render`, the racer is `active==0`, so the `if (!racer_active[i])` branch (lines 425–431) moves all 4 slots to **(0,0)**. The position assertions (`mock_sprite_x[10]==40`, etc.) fail (they read 0). The tile assertions still pass — `explosion_render` sets the car tile regardless — but the decisive position assertions are RED. This is the exact in-game symptom: the blast would be hidden off-screen while `explosion_render` only swaps tiles (it never positions car-kind blasts).

- [ ] **Step 3: Add the dying branch to `racer_render`**

In `src/racer.c` `racer_render`, the loop body has the invalid-slot guard (lines 420–423) then the `if (!racer_active[i])` hide block (lines 425–431). Insert the dying branch **between** them — after the invalid guard, before the `!active` hide:
```c
        /* Unallocated slot (lazy OAM): no handles to move. */
        if (racer_oam[i * 4u + 0u] == SPRITE_POOL_INVALID) {
            continue;
        }

        /* Dying: keep the 4 slots positioned at the frozen world pos so the
         * car blast tracks the scrolling camera. explosion_render owns the
         * tiles/props; here we only position (off-screen aware) (#411). */
        if (racer_dying[i]) {
            scr_x = racer_px[i] + 8;
            scr_y = racer_py[i] - cam_y + 16;
            if (scr_x < 0 || scr_x >= 168 || scr_y < 0 || scr_y >= 160) {
                move_sprite(racer_oam[i * 4u + 0u], 0u, 0u);
                move_sprite(racer_oam[i * 4u + 1u], 0u, 0u);
                move_sprite(racer_oam[i * 4u + 2u], 0u, 0u);
                move_sprite(racer_oam[i * 4u + 3u], 0u, 0u);
            } else {
                hw_x = (uint8_t)scr_x;
                hw_y = (uint8_t)scr_y;
                move_sprite(racer_oam[i * 4u + 0u], hw_x,                 hw_y);
                move_sprite(racer_oam[i * 4u + 1u], hw_x,                 (uint8_t)(hw_y + 8u));
                move_sprite(racer_oam[i * 4u + 2u], (uint8_t)(hw_x + 8u), hw_y);
                move_sprite(racer_oam[i * 4u + 3u], (uint8_t)(hw_x + 8u), (uint8_t)(hw_y + 8u));
            }
            continue;
        }

        if (!racer_active[i]) {
            move_sprite(racer_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }
```
(`scr_x`, `scr_y`, `hw_x`, `hw_y` are already declared at the top of the loop, lines 413–416 — no new declarations.)

- [ ] **Step 4: Run test to verify it passes**

Run: `make test`
Expected: PASS — `test_racer_dying_blast_renders_on_own_slots` passes; all existing render tests (`test_racer_render_skips_invalid_slots`, etc.) still pass (no dying racers in those).

- [ ] **Step 5: Commit**

```bash
git add src/racer.c tests/test_racer.c
git commit -m "feat(racer): position car blast on own slots while dying (#411)"
```

---

## Task 9: Full host-test suite + README

**Files:**
- Modify: `README.md`
- Test: full `make test`

- [ ] **Step 1: Run the full host test suite**

Run: `make test`
Expected: PASS — every test binary green. Pay attention to early-exit: the Makefile uses `|| exit 1` and runs binaries alphabetically; if a binary fails, fix it before the later ones run.

- [ ] **Step 2: Update README**

In `README.md`, find the combat/racer feature description and add a line noting enemy cars now explode on death. Example (adapt to the existing wording/section — search for "racer" or "enemy"):
```markdown
- Enemy racers explode in a 16×16 car blast when destroyed, then vanish.
```
If no suitable bullet list exists, add it under the gameplay/features section consistent with surrounding entries.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: note enemy racer death explosion (#411)"
```

---

## Task 10: GB build verification + memory budgets

**Files:** none (verification only)

- [ ] **Step 1: Fetch + merge latest master**

From the worktree directory (PowerShell):
```powershell
git fetch origin
git merge origin/master
```
Resolve any conflicts (unlikely — touched files are `config.h`, `explosion.*`, `racer.*`, tests, README).

- [ ] **Step 2: Clean build the ROM**

From the worktree, PowerShell:
```powershell
$env:GBDK_HOME = "C:/gbdk"
$env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
make clean ; make
```
Expected: `build/nuke-raider.gb` produced with no compiler errors. The `gbdk-expert` agent should review any `src/*.c` change if SDCC emits warnings beyond the harmless "so said EVELYN".

- [ ] **Step 3: Check memory budgets**

`make memory-check` fires automatically via the PostToolUse hook after the build. Confirm OAM/VRAM/WRAM are PASS. The two new `uint8_t[MAX_RACERS]` arrays add `2 * MAX_RACERS` bytes WRAM (trivially small); OAM is unchanged (AC4: the blast reuses the racer's existing 4 slots — no `get_sprite()` call). If anything is FAIL/ERROR, stop and fix before continuing.

- [ ] **Step 4: Smoketest (user-gated)**

Per the project smoketest gate: ask the user for confirmation, then launch the ROM in Emulicious from the worktree:
```powershell
Start-Process java -ArgumentList '-jar','C:\Tools\Emulicious\Emulicious.jar','build/nuke-raider.gb'
```
Verify in-game: shoot an enemy racer until destroyed → it plays the 16×16 car blast for ~2 s at its position (tracking the camera) → then disappears. Confirm the player's HUD/HP and game-over are unaffected, and that multiple racers can be destroyed independently.

- [ ] **Step 5: Push + PR (only after smoketest passes)**

```bash
git push -u origin worktree-feat-racer-explosion-411
gh pr create --title "feat: enemy racer car explosion on death (#411)" --body "Closes #411"
```

---

## Acceptance Criteria coverage

- **AC1** (16×16 blast across 4 OAM slots, same art as player) → Task 6 (spawn 4 quadrant blasts with player's flip mapping + `explosion_car_base()`), Task 8 (positioning), verified by `test_racer_dying_blast_renders_on_own_slots`.
- **AC2** (~2 s / 120 ticks before slot freed) → Task 1 (`RACER_DEATH_TICKS = 120`), Task 7 (countdown), verified by `test_racer_dying_counts_down_and_deactivates`.
- **AC3** (multiple racers blast independently) → per-slot `racer_dying[]`/`racer_death_timer[]` SoA arrays (Task 5) + per-entry explosion pool (existing); each racer's death is self-contained. (No interference: gate is decoupled per kind; pool supports `MAX_EXPLOSIONS=12 ≥ 4×racers on-screen`.)
- **AC4** (no net OAM cost — reuses the dying racer's own 4 slots) → Task 6 passes `racer_oam[i*4+0..3]` to `explosion_spawn` with **no** `get_sprite()` call; Task 4 keeps the racer owning the slots; verified structurally + `test_racer_dying_blast_renders_on_own_slots` (blast lands on the racer's handles).
- **AC5** (`make memory-check` budgets unaffected) → Task 10 Step 3.
- **Issue note** ("separate the car-blast done gate per-entity if multiple cars dying") → Task 3 decouples the gate by kind; `test_racer_death_does_not_gate_game_over` + `test_racer_blast_does_not_gate_done` verify enemy blasts never delay the player's game-over.

## Out of scope (per issue)
SFX, screen shake, debris particles.
