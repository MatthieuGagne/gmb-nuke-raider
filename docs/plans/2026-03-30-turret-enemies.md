# Turret Enemies Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add static turret emplacements to combat-run missions — turrets placed in the Tiled map fire enemy bullets at the player, can be destroyed by player bullets, and block passage until destroyed.

**Architecture:** A new `enemy.c` SoA pool scans the tilemap at init for `TILE_TURRET` markers, storing positions as tile coordinates. Each frame, turrets count down a fire timer and call `projectile_fire()` with `PROJ_OWNER_ENEMY`. Player collision treats `TILE_TURRET` as impassable only while `enemy_blocks_tile()` returns true. Collision detection lives in `projectile.c` via two new query functions.

**Tech Stack:** GBDK-2020, SDCC, GBDK sprite/OAM API, Unity (host tests), Tiled + TMX pipeline.

## Open questions

- None — all resolved in grill-me session (issue #143).

---

## Session Progress (2026-03-30)

**Status:** Batch 1 + Batch 2 complete. Smoketest 1 passed. Ready to start Batch 3.

| Task | Status | Commit |
|------|--------|--------|
| Task 1 | ✅ DONE | e7a9740 |
| Task 2 | ✅ DONE | 3f42896 |
| Task 3 | ✅ DONE | (sprite commit) |
| Smoketest 1 | ✅ DONE | — |
| Task 4 + 5 | ✅ DONE | 644f83e |
| Smoketest 2 | ⏳ NEXT | — |
| Task 6 | pending | — |
| Task 7 | pending | — |
| Task 8 | pending | — |
| Smoketest 3 | pending | — |
| Task 9 | pending | — |
| Smoketest 4 | pending | — |

## Architecture Adaptations (discovered during implementation)

> **Read before implementing Tasks 6–9.**

**1. turret_sprite symbol and loader.c pattern**
- Generated file: `src/turret_sprite.c` — symbol is `turret_tile_data` (NOT `turret_sprite`)
- No `turret_sprite.h` exists — the project convention uses `extern` declarations directly in the consumer
- The plan's `_load_tile_data()` helper in `enemy.c` is WRONG for this codebase
- **Correct approach:** add `load_turret_tiles()` NONBANKED to `loader.c` (same pattern as `load_bullet_tiles()`), add extern declarations there, declare in `loader.h`, call `load_turret_tiles()` from `enemy_init()` instead of inline `set_sprite_data()`
- `enemy.c` must `#include "loader.h"` and call `load_turret_tiles()` — do NOT call `set_sprite_data()` directly from banked code

**2. track.h uses #define style (not enum)**
- Task 2 adapted correctly: `#define TILE_TURRET 7u` added after TILE_FINISH
- No enum to modify — all TileType constants are `#define`

**3. track_passable() bypasses the LUT**
- `track_passable()` returns `active_map[...] != 0u` — TILE_TURRET (index 8) is therefore passable
- **Task 7 fix location is `corners_passable()` in player.c** — NOT `player_apply_physics()`
- Add a static helper `corner_active_turret(wx, wy)` that checks `track_tile_type(wx,wy) == TILE_TURRET && enemy_blocks_tile(tx, ty)`, then AND its negation into each corner check

**4. player.c fire button is J_A (not J_B)**
- Confirmed in source: `if (KEY_PRESSED(J_A))` — fire is A button

---

## Batch 1 — Foundation: constants, manifest, tile type, sprite asset

### Task 1: config.h and bank-manifest.json updates

**Files:**
- Modify: `src/config.h`
- Modify: `bank-manifest.json`

**Depends on:** none
**Parallelizable with:** Task 2, Task 3

**Step 1: Update `src/config.h`**

Add the following constants (place MAX_ENEMIES near MAX_PROJECTILES; place TURRET_TILE_BASE after PROJ_TILE_BASE):

```c
/* Enemy pool */
#define MAX_ENEMIES           8u
#define TURRET_TILE_BASE     18u    /* VRAM sprite tile slot — after bullet (17) */
#define TURRET_FIRE_INTERVAL 60u    /* frames between shots */
#define TURRET_HP             1u    /* hits to destroy */
#define TURRET_HIT_RADIUS     4u    /* px radius for collision detection */

/* Raise OAM pool to fit player(4) + projectiles(8) + turrets(8) + headroom */
/* Change: #define MAX_SPRITES  16 → 28 */
#define MAX_SPRITES  28
```

Also update the comment above `MAX_SPRITES` to:
```c
/* OAM budget: player=4, dialog_arrow=1 (fixed), projectiles≤8, turrets≤8; hardware cap=40 */
```

**Step 2: Update `bank-manifest.json`**

Add before the closing `}`:
```json
  "src/enemy.c": {"bank": 255, "reason": "autobank — gameplay module called via invoke() in state_manager.c"}
```

**Step 3: Verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM builds, zero errors. `bank-manifest.json` parses cleanly (no JSON syntax error).

**Step 4: Commit**

```bash
git add src/config.h bank-manifest.json
git commit -m "feat: add MAX_ENEMIES, TURRET_TILE_BASE, raise MAX_SPRITES to 28"
```

---

### Task 2: Add TILE_TURRET to track.h and track.c

**Files:**
- Modify: `src/track.h`
- Modify: `src/track.c`
- Modify: `tests/test_track.c` (if it exists; skip if not)

**Depends on:** none
**Parallelizable with:** Task 1, Task 3

**Step 1: Write the failing test**

In `tests/test_track.c`, add:

```c
void test_tile_turret_type(void) {
    /* Tileset index 8 must map to TILE_TURRET */
    TEST_ASSERT_EQUAL_INT(TILE_TURRET, track_tile_type_from_index(8u));
}

void test_tile_turret_not_passable(void) {
    /* TILE_TURRET must NOT be equal to TILE_ROAD, TILE_SAND, TILE_BOOST, or TILE_REPAIR */
    TEST_ASSERT_NOT_EQUAL(TILE_ROAD,   TILE_TURRET);
    TEST_ASSERT_NOT_EQUAL(TILE_SAND,   TILE_TURRET);
    TEST_ASSERT_NOT_EQUAL(TILE_BOOST,  TILE_TURRET);
    TEST_ASSERT_NOT_EQUAL(TILE_REPAIR, TILE_TURRET);
}
```

Run: `make test`
Expected: FAIL (TILE_TURRET undefined)

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Verify `bank-manifest.json` already has `src/track.c` (it does — autobank 255). `src/track.h` is a header, no manifest entry needed.

**Step 3: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm:
- Extending a `static const uint8_t` LUT is safe
- No GBDK API used — pure C

**Step 4: Update `src/track.h`**

Append `TILE_TURRET` to the `TileType` enum:

```c
/* Before: */
    TILE_FINISH = 6u
} TileType;

/* After: */
    TILE_FINISH = 6u,
    TILE_TURRET = 7u
} TileType;
```

**Step 5: Update `src/track.c`**

Extend the LUT:

```c
/* Before: */
#define TILE_LUT_LEN 8u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
    TILE_FINISH, /* 6: finish line */
    TILE_REPAIR, /* 7: repair pad */
};

/* After: */
#define TILE_LUT_LEN 9u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
    TILE_FINISH, /* 6: finish line */
    TILE_REPAIR, /* 7: repair pad */
    TILE_TURRET, /* 8: turret emplacement — impassable while active */
};
```

**Step 6: Run tests to verify they pass**

Run: `make test`
Expected: PASS

**Step 7: HARD GATE — build**

Invoke the `build` skill.
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify bank budgets within limits.

**Step 9: Refactor checkpoint**

`track_tile_type_from_index()` generalizes cleanly — out-of-bounds indices fall back to `TILE_ROAD`. No hard-coded assumption breaks at N > 1 turret.

**Step 10: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on `src/track.c`. Expect: no issues (LUT lookup is optimal).

**Step 11: Commit**

```bash
git add src/track.h src/track.c tests/test_track.c
git commit -m "feat: add TILE_TURRET type (LUT index 8) to track tile system"
```

---

### Task 3: Turret sprite asset

**Files:**
- Create: `assets/sprites/turret.aseprite`
- Create: `assets/sprites/turret.png`
- Create: `src/turret_sprite.c`, `src/turret_sprite.h`
- Modify: `bank-manifest.json`

**Depends on:** none
**Parallelizable with:** Task 1, Task 2

**Step 1: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `bank-manifest.json` does NOT yet have `src/turret_sprite.c` — add it before writing:

```json
"src/turret_sprite.c": {"bank": 255, "reason": "autobank — loader.c handles BANK(sym) switching"}
```

**Step 2: Invoke the `aseprite` skill**

Invoke the `aseprite` skill before running any Aseprite command.

**Step 3: Create the sprite in Aseprite**

Create an 8×8 pixel, 1-frame sprite representing a gun emplacement (a directional arrow or simple cannon shape). Export as `assets/sprites/turret.png` (indexed color, Game Boy 4-color palette: white/light gray/dark gray/black).

Suggested placeholder: a filled circle with a line pointing up (directional arrow style, consistent with project placeholder conventions).

**Step 4: Convert with png_to_tiles**

```bash
python3 tools/png_to_tiles.py assets/sprites/turret.png src/turret_sprite.c src/turret_sprite.h turret_sprite
```

Verify `src/turret_sprite.c` and `src/turret_sprite.h` are generated.

**Step 5: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm that `set_sprite_tile(oam, TURRET_TILE_BASE)` is the correct call to load a single 8×8 sprite tile from the generated data.

**Step 6: Build**

Invoke the `build` skill.
Expected: ROM builds, zero errors.

**Step 7: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 8: Commit**

```bash
git add assets/sprites/turret.aseprite assets/sprites/turret.png \
        src/turret_sprite.c src/turret_sprite.h bank-manifest.json
git commit -m "feat: add 8x8 turret placeholder sprite"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2, Task 3 | All write different files, no shared symbols |
| B (sequential) | Smoketest | Requires all Group A tasks complete |

### Smoketest Checkpoint 1 — ROM still builds; no regression

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
Expected: All budgets PASS. Fix any FAIL or ERROR before continuing.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Drive the car on a combat-run track. Confirm: game loads, car moves, existing mechanics (bullets, repair pads, finish line) work exactly as before. No turrets appear yet — this checkpoint is regression-only.

---

## Batch 2 — Projectile API extension

### Task 4: Extend projectile_fire() with owner parameter + add hit-check functions

**Files:**
- Modify: `src/projectile.h`
- Modify: `src/projectile.c`
- Modify: `tests/test_projectile.c`

**Depends on:** Task 1 (needs `PROJ_OWNER_ENEMY` — already defined; needs config.h compile cleanly)
**Parallelizable with:** none — Task 5 depends on the new signature

**Step 1: Write failing tests**

In `tests/test_projectile.c`, add:

```c
void test_projectile_fire_enemy_owner(void) {
    projectile_init();
    /* Fire an enemy bullet at (80, 80) heading down */
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_ENEMY);
    TEST_ASSERT_EQUAL_UINT8(1u, projectile_count_active());
}

void test_check_hit_player_enemy_bullet(void) {
    projectile_init();
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_ENEMY);
    /* Hit check at same position, radius 8 */
    TEST_ASSERT_EQUAL_UINT8(1u, projectile_check_hit_player(80u, 80u, 8u));
    /* Bullet consumed */
    TEST_ASSERT_EQUAL_UINT8(0u, projectile_count_active());
}

void test_check_hit_player_ignores_player_bullet(void) {
    projectile_init();
    /* A player bullet must NOT trigger check_hit_player */
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_PLAYER);
    TEST_ASSERT_EQUAL_UINT8(0u, projectile_check_hit_player(80u, 80u, 8u));
    TEST_ASSERT_EQUAL_UINT8(1u, projectile_count_active());
}

void test_check_hit_enemy_player_bullet(void) {
    projectile_init();
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_PLAYER);
    TEST_ASSERT_EQUAL_UINT8(1u, projectile_check_hit_enemy(80u, 80u, 8u));
    TEST_ASSERT_EQUAL_UINT8(0u, projectile_count_active());
}

void test_check_hit_enemy_ignores_enemy_bullet(void) {
    projectile_init();
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_ENEMY);
    TEST_ASSERT_EQUAL_UINT8(0u, projectile_check_hit_enemy(80u, 80u, 8u));
    TEST_ASSERT_EQUAL_UINT8(1u, projectile_count_active());
}

void test_check_hit_miss(void) {
    projectile_init();
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_ENEMY);
    /* Far away — no hit */
    TEST_ASSERT_EQUAL_UINT8(0u, projectile_check_hit_player(20u, 20u, 4u));
}
```

Run: `make test`
Expected: FAIL (wrong number of args to `projectile_fire`, undefined `projectile_check_hit_player/enemy`)

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `src/projectile.c` is already in `bank-manifest.json` (bank 255). No new entry needed.

**Step 3: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm:
- Adding a `uint8_t owner` parameter to a `BANKED` function is safe
- No stack concern (all args are uint8_t / small)
- Hit radius math using `uint8_t` subtraction: use `int8_t` delta (world coords are screen-space 0–159, fits int8_t for difference)

**Step 4: Update `src/projectile.h`**

```c
/* Change signature: */
void    projectile_fire(uint8_t scr_x, uint8_t scr_y, player_dir_t dir) BANKED;

/* To: */
void    projectile_fire(uint8_t scr_x, uint8_t scr_y, player_dir_t dir, uint8_t owner) BANKED;

/* Add after projectile_count_active: */
uint8_t projectile_check_hit_player(uint8_t cx, uint8_t cy, uint8_t r) BANKED;
uint8_t projectile_check_hit_enemy(uint8_t cx, uint8_t cy, uint8_t r) BANKED;
```

**Step 5: Update `src/projectile.c`**

In `projectile_fire()` — change the owner assignment:
```c
/* Before: */
proj_owner[i] = PROJ_OWNER_PLAYER;

/* After: */
proj_owner[i] = owner;
```

Also update the function signature line to match the header.

Add the two new functions after `projectile_count_active()`:

```c
uint8_t projectile_check_hit_player(uint8_t cx, uint8_t cy, uint8_t r) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        int16_t dx, dy;
        if (!proj_active[i]) continue;
        if (proj_owner[i] != PROJ_OWNER_ENEMY) continue;
        dx = (int16_t)proj_x[i] - (int16_t)cx;
        dy = (int16_t)proj_y[i] - (int16_t)cy;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if ((uint8_t)dx <= r && (uint8_t)dy <= r) {
            proj_active[i] = 0u;
            clear_sprite(proj_oam[i]);
            return 1u;
        }
    }
    return 0u;
}

uint8_t projectile_check_hit_enemy(uint8_t cx, uint8_t cy, uint8_t r) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        int16_t dx, dy;
        if (!proj_active[i]) continue;
        if (proj_owner[i] != PROJ_OWNER_PLAYER) continue;
        dx = (int16_t)proj_x[i] - (int16_t)cx;
        dy = (int16_t)proj_y[i] - (int16_t)cy;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if ((uint8_t)dx <= r && (uint8_t)dy <= r) {
            proj_active[i] = 0u;
            clear_sprite(proj_oam[i]);
            return 1u;
        }
    }
    return 0u;
}
```

**Step 6: Run tests to verify they pass**

Run: `make test`
Expected: PASS (projectile tests only — enemy tests don't exist yet)

**Step 7: HARD GATE — build**

Invoke the `build` skill.
Expected: FAIL — `player.c` calls `projectile_fire()` with old 3-arg signature. Proceed to Task 5 immediately.

**Step 8: HARD GATE — bank-post-build**

Run after Task 5 fixes the compile error.

**Step 9: Refactor checkpoint**

Both hit-check functions share identical structure — an abstraction could DRY them via an `owner` parameter to a private helper. However, two functions is the caller API from the issue; keep them as-is (YAGNI — the gain is minimal and the two-function API is cleaner for callers).

**Step 10: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on `src/projectile.c`. Confirm no new anti-patterns introduced.

**Step 11: Commit**

Commit together with Task 5 (see Task 5 step 11).

---

### Task 5: Update player.c — fix projectile_fire() call site

**Files:**
- Modify: `src/player.c`

**Depends on:** Task 4 (new `projectile_fire()` signature)
**Parallelizable with:** none — writes `src/player.c`; must follow Task 4

**Step 1: Find the call site**

```bash
grep -n "projectile_fire" src/player.c
```

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `src/player.c` is already in `bank-manifest.json` (bank 255).

**Step 3: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm adding `PROJ_OWNER_PLAYER` as the fourth argument is the only change needed here.

**Step 4: Update the call site**

```c
/* Before: */
projectile_fire(scr_x, scr_y, player_dir);

/* After: */
projectile_fire(scr_x, scr_y, player_dir, PROJ_OWNER_PLAYER);
```

(The exact variable names may differ — match what `grep` found in Step 1.)

**Step 5: Run tests**

Run: `make test`
Expected: PASS

**Step 6: HARD GATE — build**

Invoke the `build` skill.
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 7: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 8: Refactor checkpoint**

Single call site, single token change. No generalization concern.

**Step 9: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on `src/player.c`. Expect: no issues from this change.

**Step 10: Commit (Tasks 4 + 5 together)**

```bash
git add src/projectile.h src/projectile.c src/player.c tests/test_projectile.c
git commit -m "feat: add owner param to projectile_fire(), add hit-check functions"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 2

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 4 → Task 5 | Task 5 requires Task 4's new signature |
| B (sequential) | Smoketest | Requires Task 5 complete |

### Smoketest Checkpoint 2 — Player can still fire; bullets behave correctly

**Step 1: Fetch and merge latest master**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Drive on a track and fire (B button). Confirm: bullets fire in the direction the car faces, travel across the screen, and despawn. No crashes. No change to player behavior.

---

## Batch 3 — Enemy module + integration

### Task 6: New enemy.c / enemy.h module

**Files:**
- Create: `src/enemy.c`, `src/enemy.h`
- Create: `tests/test_enemy.c`
- Modify: `src/loader.c` — add `load_turret_tiles()` NONBANKED + extern declarations
- Modify: `src/loader.h` — declare `load_turret_tiles(void) NONBANKED`

**Depends on:** Task 1 (MAX_ENEMIES, TURRET_TILE_BASE, TURRET_FIRE_INTERVAL, TURRET_HP, TURRET_HIT_RADIUS), Task 4 (projectile_check_hit_enemy signature)
**Parallelizable with:** none — Task 7 and Task 8 both depend on enemy.h symbols

**Step 1: Write failing tests**

Create `tests/test_enemy.c`:

```c
#include "unity.h"
#include "enemy.h"
#include "player_dir.h"   /* or player.h — wherever player_dir_t is defined */

void setUp(void) { enemy_init_empty(); }
void tearDown(void) {}

/* enemy_init_empty() zeros the pool without scanning the map —
 * used by tests to get a clean state without touching hardware. */

void test_enemy_pool_empty_after_init(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_count_active());
}

void test_enemy_spawn_and_active(void) {
    enemy_spawn(10u, 20u);   /* tile coords */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_count_active());
}

void test_enemy_blocks_tile_active(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_blocks_tile(10u, 20u));
}

void test_enemy_blocks_tile_inactive(void) {
    /* No spawn — tile should not be blocked */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_blocks_tile(10u, 20u));
}

void test_enemy_blocks_tile_wrong_position(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_blocks_tile(5u, 5u));
}

void test_enemy_direction_to_player_right(void) {
    /* Turret at tile (0,0) = pixel (0,0); player at pixel (64,0) → DIR_R */
    TEST_ASSERT_EQUAL_INT(DIR_R, enemy_dir_to_pixel(0u, 0u, 64, 0));
}

void test_enemy_direction_to_player_down(void) {
    TEST_ASSERT_EQUAL_INT(DIR_B, enemy_dir_to_pixel(0u, 0u, 0, 64));
}

void test_enemy_direction_to_player_down_right(void) {
    TEST_ASSERT_EQUAL_INT(DIR_RB, enemy_dir_to_pixel(0u, 0u, 64, 64));
}

void test_enemy_direction_to_player_up_left(void) {
    TEST_ASSERT_EQUAL_INT(DIR_LT, enemy_dir_to_pixel(10u, 10u, 0, 0));
    /* turret pixel = (80, 80); player at (0,0): dx=-80, dy=-80 → DIR_LT */
}

void test_enemy_timer_does_not_fire_early(void) {
    enemy_spawn(10u, 20u);
    /* Timer starts at TURRET_FIRE_INTERVAL; should not fire until it reaches 0 */
    /* We test indirectly: no crash and active count unchanged after partial tick */
    enemy_tick_timers();   /* 1 frame */
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_count_active());
}
```

Run: `make test`
Expected: FAIL (enemy.h not found)

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `bank-manifest.json` now has `src/enemy.c` (added in Task 1).

**Step 3: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm:
- `set_sprite_tile(oam, TURRET_TILE_BASE)` loads the 8×8 turret tile from the sprite VRAM slot
- `get_sprite()` / `clear_sprite()` are the correct pool calls
- VBL timing: `enemy_render()` must be called during VBlank (same constraint as `player_render()`)
- Tile scanning: `track_tile_type()` is safe to call at init (before first VBL)
- `int16_t` arithmetic for direction deltas is correct on SDCC

**Step 4: Write `src/enemy.h`**

```c
#ifndef ENEMY_H
#define ENEMY_H

#include <stdint.h>
#include "player.h"    /* player_dir_t */
#include "config.h"

/* Initialise enemy pool by scanning the active tilemap for TILE_TURRET.
 * Call after track data is loaded and before the first frame. */
void    enemy_init(void) BANKED;

/* Zero the pool without map scan — host-test helper only. */
void    enemy_init_empty(void) BANKED;

/* Spawn a turret at tile coordinates (tx, ty).
 * Returns 1 on success, 0 if pool is full. */
uint8_t enemy_spawn(uint8_t tx, uint8_t ty) BANKED;

/* Per-frame update: decrement fire timers, fire bullets, check for destruction. */
void    enemy_update(int16_t player_px, int16_t player_py) BANKED;

/* Per-frame VBlank render: move OAM sprites to screen positions. */
void    enemy_render(void) BANKED;

/* Returns 1 if an active turret occupies tile (tx, ty). Used by player collision. */
uint8_t enemy_blocks_tile(uint8_t tx, uint8_t ty) BANKED;

/* Returns number of active enemies — used by tests. */
uint8_t enemy_count_active(void) BANKED;

/* Pure-logic helpers exposed for testing — not for production callers. */
player_dir_t enemy_dir_to_pixel(uint8_t tx, uint8_t ty,
                                 int16_t player_px, int16_t player_py) BANKED;
void         enemy_tick_timers(void) BANKED;

#endif /* ENEMY_H */
```

**Step 5: Write `src/enemy.c`**

```c
#pragma bank 255
#include <gb/gb.h>
#include "enemy.h"
#include "config.h"
#include "track.h"
#include "projectile.h"
#include "damage.h"
#include "sprite_pool.h"
#include "loader.h"   /* load_turret_tiles() NONBANKED — do NOT include turret_sprite.h (it does not exist) */

/* SoA enemy pool — tile coordinates */
static uint8_t enemy_tx[MAX_ENEMIES];
static uint8_t enemy_ty[MAX_ENEMIES];
static uint8_t enemy_type[MAX_ENEMIES];
static uint8_t enemy_hp[MAX_ENEMIES];
static uint8_t enemy_active[MAX_ENEMIES];
static uint8_t enemy_timer[MAX_ENEMIES];
static uint8_t enemy_oam[MAX_ENEMIES];

/* ---- internal helpers ---- */
/* NOTE: _load_tile_data() from the original plan is REMOVED.
 * Banked code cannot call set_sprite_data() directly (would need SWITCH_ROM → crash).
 * VRAM loading is handled by load_turret_tiles() NONBANKED in loader.c — call that instead. */

static void _spawn_at(uint8_t i, uint8_t tx, uint8_t ty) {
    enemy_tx[i]     = tx;
    enemy_ty[i]     = ty;
    enemy_type[i]   = 0u;   /* 0 = TURRET (only type for now) */
    enemy_hp[i]     = TURRET_HP;
    enemy_active[i] = 1u;
    enemy_timer[i]  = TURRET_FIRE_INTERVAL;
    enemy_oam[i]    = get_sprite();
    if (enemy_oam[i] != SPRITE_POOL_INVALID) {
        set_sprite_tile(enemy_oam[i], TURRET_TILE_BASE);
    }
}

/* ---- public API ---- */

void enemy_init(void) BANKED {
    uint8_t i, tx, ty;
    uint8_t count = 0u;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        enemy_active[i] = 0u;
        enemy_oam[i]    = SPRITE_POOL_INVALID;
    }
    load_turret_tiles();   /* NONBANKED in loader.c — safe to call from any bank */
    for (ty = 0u; ty < MAP_TILES_H && count < MAX_ENEMIES; ty++) {
        for (tx = 0u; tx < MAP_TILES_W && count < MAX_ENEMIES; tx++) {
            if (track_tile_type((int16_t)((uint16_t)tx * 8u),
                                (int16_t)((uint16_t)ty * 8u)) == TILE_TURRET) {
                _spawn_at(count, tx, ty);
                count++;
            }
        }
    }
}

void enemy_init_empty(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        enemy_active[i] = 0u;
        enemy_oam[i]    = SPRITE_POOL_INVALID;
    }
}

uint8_t enemy_spawn(uint8_t tx, uint8_t ty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (!enemy_active[i]) {
            _spawn_at(i, tx, ty);
            return 1u;
        }
    }
    return 0u;
}

player_dir_t enemy_dir_to_pixel(uint8_t tx, uint8_t ty,
                                  int16_t player_px, int16_t player_py) BANKED {
    int16_t dx = player_px - (int16_t)((uint16_t)tx * 8u);
    int16_t dy = player_py - (int16_t)((uint16_t)ty * 8u);
    int16_t ax = dx < 0 ? -dx : dx;
    int16_t ay = dy < 0 ? -dy : dy;

    /* Diagonal threshold: |dx| and |dy| within 2x of each other */
    if (ax > ay * 2) {
        return dx > 0 ? DIR_R : DIR_L;
    }
    if (ay > ax * 2) {
        return dy > 0 ? DIR_B : DIR_T;
    }
    /* Diagonal */
    if (dx >= 0 && dy >= 0) return DIR_RB;
    if (dx >= 0 && dy <  0) return DIR_RT;
    if (dx <  0 && dy >= 0) return DIR_LB;
    return DIR_LT;
}

void enemy_tick_timers(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (enemy_active[i] && enemy_timer[i] > 0u) {
            enemy_timer[i]--;
        }
    }
}

void enemy_update(int16_t player_px, int16_t player_py) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        uint8_t scr_x, scr_y;
        if (!enemy_active[i]) continue;

        /* Check if a player bullet hit this turret */
        scr_x = (uint8_t)((uint16_t)enemy_tx[i] * 8u);
        scr_y = (uint8_t)((uint16_t)enemy_ty[i] * 8u);
        if (projectile_check_hit_enemy(scr_x, scr_y, TURRET_HIT_RADIUS)) {
            enemy_hp[i]--;
            if (enemy_hp[i] == 0u) {
                enemy_active[i] = 0u;
                if (enemy_oam[i] != SPRITE_POOL_INVALID) {
                    clear_sprite(enemy_oam[i]);
                    enemy_oam[i] = SPRITE_POOL_INVALID;
                }
                continue;
            }
        }

        /* Fire timer */
        if (enemy_timer[i] > 0u) {
            enemy_timer[i]--;
        } else {
            player_dir_t dir = enemy_dir_to_pixel(
                enemy_tx[i], enemy_ty[i], player_px, player_py);
            projectile_fire(scr_x, scr_y, dir, PROJ_OWNER_ENEMY);
            enemy_timer[i] = TURRET_FIRE_INTERVAL;
        }
    }

    /* Check if any enemy bullet hit the player */
    if (projectile_check_hit_player(
            (uint8_t)player_px, (uint8_t)player_py, TURRET_HIT_RADIUS)) {
        damage_apply(10u);
    }
}

void enemy_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (!enemy_active[i] || enemy_oam[i] == SPRITE_POOL_INVALID) continue;
        /* OAM coords: hardware adds 8 to x and 16 to y vs screen coords */
        move_sprite(enemy_oam[i],
                    (uint8_t)((uint16_t)enemy_tx[i] * 8u + 8u),
                    (uint8_t)((uint16_t)enemy_ty[i] * 8u + 16u));
    }
}

uint8_t enemy_blocks_tile(uint8_t tx, uint8_t ty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (enemy_active[i] && enemy_tx[i] == tx && enemy_ty[i] == ty) {
            return 1u;
        }
    }
    return 0u;
}

uint8_t enemy_count_active(void) BANKED {
    uint8_t i, count = 0u;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (enemy_active[i]) count++;
    }
    return count;
}
```

**Step 6: Run tests to verify they pass**

Run: `make test`
Expected: PASS (enemy tests + all prior tests)

**Step 7: HARD GATE — build**

Invoke the `build` skill.
Expected: ROM builds, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify bank budgets within limits.

**Step 9: Refactor checkpoint**

SoA confirmed. `MAX_ENEMIES` comes from config.h. `enemy_update()` generalizes for all N ≤ 8 turrets. No hard-coded turret count. Pool is ready for patrol vehicle type (#144) — just add a new `enemy_type` value.

**Step 10: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on `src/enemy.c` and `src/enemy.h`. Pay attention to: the tile-scan nested loop, the `int16_t` direction math, and OAM coordinate arithmetic.

**Step 11: Commit**

```bash
git add src/enemy.c src/enemy.h tests/test_enemy.c
git commit -m "feat: add enemy module with SoA turret pool, fire timer, collision"
```

---

### Task 7: Wire player.c — TILE_TURRET passability gate

**Files:**
- Modify: `src/player.c`

**Depends on:** Task 6 (enemy_blocks_tile), Task 2 (TILE_TURRET constant)
**Parallelizable with:** Task 8 — writes different files

**Step 1: Find existing tile collision code**

```bash
grep -n "TILE_WALL\|tile_type\|track_tile\|impassable\|passable" src/player.c
```

Identify the switch/if block that handles tile types for collision. `TILE_WALL` currently causes the car to stop/bounce.

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `src/player.c` is already in `bank-manifest.json`.

**Step 3: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm that adding a call to `enemy_blocks_tile()` (a `BANKED` function in bank 255, same bank as player.c) is a safe same-bank call.

**Step 4: Add `#include "enemy.h"` to player.c**

Add near the top with other includes.

**Step 5: Update tile collision handling**

**IMPORTANT — actual fix location:** `track_passable()` checks `raw_map_byte != 0`, so TILE_TURRET (index 8) is always passable. The `player_apply_physics` path (terrain type) handles physics effects only, not movement blocking. The correct fix is in `corners_passable()` (lines 81-86 of player.c).

Add a private helper and modify `corners_passable()`:

```c
/* Add before corners_passable: */
static uint8_t corner_active_turret(int16_t wx, int16_t wy) {
    uint8_t tx = (uint8_t)((uint16_t)wx >> 3u);
    uint8_t ty = (uint8_t)((uint16_t)wy >> 3u);
    return (track_tile_type(wx, wy) == TILE_TURRET) && enemy_blocks_tile(tx, ty);
}

/* Replace corners_passable: */
static uint8_t corners_passable(int16_t wx, int16_t wy) {
    return track_passable(wx,        wy) && !corner_active_turret(wx,        wy) &&
           track_passable(wx + 15,   wy) && !corner_active_turret(wx + 15,   wy) &&
           track_passable(wx,     wy + 15) && !corner_active_turret(wx,     wy + 15) &&
           track_passable(wx + 15, wy + 15) && !corner_active_turret(wx + 15, wy + 15);
}
```

**Step 6: Write a test for passability logic (if player collision is host-testable)**

This test is emulator-only — `corners_passable()` calls `track_tile_type()` + `enemy_blocks_tile()` which need hardware or full mock setup. Document as emulator-only verification in the smoketest below.

**Step 7: Run tests**

Run: `make test`
Expected: PASS

**Step 8: HARD GATE — build**

Invoke the `build` skill. Expected: zero errors.

**Step 9: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 10: Refactor checkpoint**

`enemy_blocks_tile()` is a narrow predicate — player.c knows nothing about enemy internals. Coupling is minimal and one-directional.

**Step 11: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on the modified section of `src/player.c`.

**Step 12: Commit**

```bash
git add src/player.c
git commit -m "feat: treat TILE_TURRET as impassable via enemy_blocks_tile() gate"
```

---

### Task 8: Wire state_playing.c — call enemy_init, enemy_update, enemy_render

**Files:**
- Modify: `src/state_playing.c`

**Depends on:** Task 6 (enemy_update, enemy_render, enemy_init)
**Parallelizable with:** Task 7 — writes different files

**Step 1: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `src/state_playing.c` is already in `bank-manifest.json` (bank 255).

**Step 2: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm:
- `enemy_render()` must be called during VBlank phase (same constraint as `player_render()` and `projectile_render()`)
- `enemy_update()` must be called in the game-logic phase (same as `projectile_update()`)
- `enemy_init()` must be called after track data is loaded (check init order — track loader runs before `state_playing` enters)

**Step 3: Add `#include "enemy.h"` to state_playing.c**

**Step 4: Add `enemy_init()` to the state init function**

Find where `projectile_init()` is called at state entry and add immediately after:

```c
enemy_init();
```

**Step 5: Add `enemy_render()` to the VBlank render phase**

Find where `projectile_render()` is called in the VBlank section and add immediately after:

```c
enemy_render();
```

**Step 6: Add `enemy_update()` to the game-logic phase**

Find where `projectile_update()` is called and add immediately after:

```c
{
    int16_t px = player_get_x();
    int16_t py = player_get_y();
    enemy_update(px, py);
}
```

(If `px`/`py` are already computed nearby, reuse those variables instead of calling `player_get_x/y()` again.)

**Step 7: Run tests**

Run: `make test`
Expected: PASS

**Step 8: HARD GATE — build**

Invoke the `build` skill. Expected: zero errors.

**Step 9: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 10: Refactor checkpoint**

`enemy_update(px, py)` reuses already-computed player position — no redundant `player_get_x/y()` calls if px/py are in scope.

**Step 11: HARD GATE — gb-c-optimizer**

Invoke the `gb-c-optimizer` agent on the modified `src/state_playing.c`.

**Step 12: Commit**

```bash
git add src/state_playing.c
git commit -m "feat: wire enemy_init/update/render into state_playing game loop"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 3

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 6 | enemy.c/h must exist before Tasks 7 and 8 can compile |
| B (parallel) | Task 7, Task 8 | Write different files; both depend only on Task 6 |
| C (sequential) | Smoketest | Requires all of A + B |

### Smoketest Checkpoint 3 — Turrets appear, fire, and are destroyable

**Step 1: Fetch and merge latest master**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

At this point the map has no `TILE_TURRET` tiles yet (Task 9 is next), so turrets will NOT appear visually. This checkpoint verifies:
- Game loads and runs without crash
- Player fires normally (B button)
- No memory corruption or OAM glitching
- HUD and existing mechanics intact

After Task 9 adds turrets to the map, a follow-up visual verification will confirm turrets render and fire.

---

## Batch 4 — Map: place turret tiles in Tiled

### Task 9: Add turret tile to tileset and place in track.tmx

**Files:**
- Modify: `assets/tiles/track_tiles.png` (add tile at position 8)
- Modify: `assets/maps/track.tmx` (place TILE_TURRET tiles)
- Regenerated: `src/track_map.c`, `src/track_tiles.c` (auto-generated on build)

**Depends on:** Task 2 (TILE_TURRET = LUT index 8), Task 3 (turret visual)
**Parallelizable with:** none — only task in this batch

**Step 1: Invoke the `map-expert` agent**

Before touching any map files, invoke the `map-expert` agent. Ask it:
1. How to add a new tile to `assets/tiles/track_tiles.png` at index 8
2. How to add the new tile to the `track.tmx` tileset definition
3. Where to place turret tiles in the track layout (off to the side of the road so they're reachable but don't block the critical path — place 2–3 turrets for initial testing)
4. How to verify the TMX pipeline regenerates `src/track_map.c` correctly

**Step 2: Edit the tileset**

Add the turret visual (reuse or reference `assets/sprites/turret.png`) to `assets/tiles/track_tiles.png` as tile index 8. Match the 8×8 grid spacing.

**Step 3: Update track.tmx in Tiled**

Open `assets/maps/track.tmx` in Tiled. Refresh the tileset. Place 2–3 `TILE_TURRET` (index 8) tiles at positions on or near the road — not blocking the only path through (so the track is completable without destroying all turrets, unless that's the intended design).

**Step 4: Rebuild**

```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```

Verify `src/track_map.c` and `src/track_tiles.c` are regenerated and contain the new tile data.

**Step 5: Commit**

```bash
git add assets/tiles/track_tiles.png assets/maps/track.tmx \
        src/track_map.c src/track_tiles.c
git commit -m "feat: add turret tile to tileset and place 2-3 turrets in track.tmx"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 4

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 9 | Only task; no parallelism |
| B (sequential) | Smoketest | Requires Task 9 |

### Smoketest Checkpoint 4 — Full turret feature end-to-end

**Step 1: Fetch and merge latest master**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user — full acceptance checklist**

Verify each item:
- [ ] Turret sprites appear at expected map positions
- [ ] Turrets fire bullets toward the player approximately every 60 frames (~1 second)
- [ ] Enemy bullets travel across the screen and despawn
- [ ] Player HP decreases when an enemy bullet hits the car
- [ ] Player bullets destroy turrets (turret sprite disappears)
- [ ] Destroyed turret tile becomes drivable (car passes through freely)
- [ ] Active turret tile blocks the car (car bounces/stops on contact)
- [ ] No OAM flicker or sprite corruption
- [ ] Game over triggers correctly when HP reaches 0 from enemy fire
- [ ] No crash after destroying all turrets

---

## Summary of all tasks

| Task | File(s) | Type | Depends on | Parallelizable with |
|------|---------|------|-----------|-------------------|
| 1 | config.h, bank-manifest.json | non-C | — | Task 2, Task 3 |
| 2 | track.h, track.c | C | — | Task 1, Task 3 |
| 3 | turret_sprite assets, turret_sprite.c/h | C + asset | — | Task 1, Task 2 |
| 4 | projectile.h, projectile.c | C | Task 1 | — |
| 5 | player.c (call site fix) | C | Task 4 | — |
| 6 | enemy.c, enemy.h | C | Task 1, Task 4 | — |
| 7 | player.c (passability) | C | Task 6, Task 2 | Task 8 |
| 8 | state_playing.c | C | Task 6 | Task 7 |
| 9 | track.tmx, tileset PNG | non-C + asset | Task 2, Task 3 | — |
