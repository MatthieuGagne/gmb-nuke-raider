# Patrol Feature — PR2: Shared vehicle_physics + player/racer Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every `src/*.c`/`.h` write fires the `bank-pre-write` PreToolUse hook automatically and must be preceded by a `gbdk-expert` consult; every `make` fires `bank-post-build` + `make memory-check` PostToolUse hooks automatically.

> **Prerequisite: PR1 (enemy_common) merged.** This plan assumes `src/enemy_common.c` / `src/enemy_common.h` already exist and are wired into the build and bank manifest (plan file `2026-06-09-patrol-pr1-enemy-common.md`). PR2 does not touch `enemy_common`; it adds a *separate* `vehicle_physics` module. If `enemy_common` is not merged, STOP and merge PR1 first.

**Goal:** Extract the terrain-physics math and the axis-separated wall-slide collision arithmetic shared by player and racer into one new `vehicle_physics` module, and **fully converge** both `player.c` and `racer.c` onto it — terrain physics AND collision. Player behavior must stay byte-identical (its existing test suite is the regression gate); racer gains terrain physics + slide collision routed through the shared helper. This is the highest-risk PR of the patrol series — the whole point is the regression gate proving convergence did not change observable behavior.

**The interleaving problem, and how the split API solves it:** in both `player_apply_physics` and `racer_update`, the velocity update is `friction → gear-accel → boost-delta → clamp`, and the **gear-accel step is caller-specific** (player uses `GEAR_ACCEL[current_gear]`, racer uses `RACER_GEAR_ACCEL_TBL[racer_gear[i]]`). A single helper that does friction-then-boost-then-clamp in one call cannot have the caller insert its gear accel *between* friction and boost. The solution is to **split the physics helper at the two natural seams** (friction|accel and accel|boost), so the caller drops its unchanged gear-accel code into the gap.

**Architecture:** New `src/vehicle_physics.c` + `src/vehicle_physics.h` (`#pragma bank 255`, autobank) expose exactly **five** BANKED functions — three for physics, two for collision:

- `void vehicle_apply_friction(int8_t *vx, int8_t *vy, uint8_t terrain, uint8_t gas, uint8_t dir) BANKED;` — applies SAND/OIL/ROAD friction to `*vx`/`*vy` (the **pre-accel** portion of the old `player_apply_physics`). SAND doubles friction; OIL zeroes it; `gas` relieves friction on the axis the vehicle is driving (via `VEH_DIR_DX/DY[dir]`). Does NOT touch gears or boost.
- `void vehicle_apply_boost_clamp(int8_t *vx, int8_t *vy, uint8_t terrain, uint8_t max_speed) BANKED;` — applies the BOOST `-TERRAIN_BOOST_DELTA` to `*vy` (when `terrain == TILE_BOOST`) then clamps both axes to `±max_speed` (the **post-accel** portion of the old `player_apply_physics`).
- `void vehicle_apply_physics(int8_t *vx, int8_t *vy, uint8_t terrain, uint8_t gas, uint8_t dir, uint8_t max_speed) BANKED;` — **gearless convenience** = `vehicle_apply_friction(...)` immediately followed by `vehicle_apply_boost_clamp(...)` with NO accel between. This is the no-gear-accel composition; `patrol.c` (PR4) calls it unchanged. (Contract: `vehicle_apply_physics` is byte-identical to friction-then-boost_clamp with zero gear accel — do NOT break this for the patrol caller.)
- `int16_t vehicle_step_axis_x(int16_t px, int16_t py, int8_t vx) BANKED;` — returns `px + vx` if the resulting 16×16 footprint is in-bounds (`0 <= px+vx <= active_map_w*8 - 16`) AND non-directionally passable (`track_passable` at all four 16×16 corners); otherwise returns `px` unchanged. The generic helper does NOT apply damage/gears/ram/SFX — callers wrap it and detect a block by comparing the returned value against the input.
- `int16_t vehicle_step_axis_y(int16_t px, int16_t py, int8_t vy) BANKED;` — same for the Y axis using `active_map_h`.

**Convergence model (the load-bearing design decision):**
- **player.c** — `player_apply_physics` calls `vehicle_apply_friction(&vx,&vy,terrain,gas,player_dir)`, then runs its EXISTING inline gear-accel code (`vx += GEAR_ACCEL[current_gear]*DIR_DX[...]`), then `vehicle_apply_boost_clamp(&vx,&vy,terrain,max_speed)`. The split lands exactly at the friction/accel and accel/boost boundaries, so the result is byte-identical. Gear shift + gear-reset-on-oil stay in `player.c`. The X/Y collision blocks call `vehicle_step_axis_x/y` for the bounds+passability arithmetic; **player keeps its directional `corners_passable` (turret + racer + dir-specific hitbox) as an extra gate AND its own wrapper** (damage / gear-reset / racer-ram / `SFX_HIT`). The player wrapper ANDs the helper result with its directional `corners_passable` and runs the ram/damage path on a block. Behavior stays byte-identical — verified by `test_player` staying green.
- **racer.c** — `racer_update` currently inlines the same terrain math (lines 323–391) and a dir-specific `racer_corners_passable` slide collision (lines 393–413). It converges the SAME way: `vehicle_apply_friction` → racer gear-accel inline (`RACER_GEAR_ACCEL_TBL[racer_gear[i]]`) → `vehicle_apply_boost_clamp`, with `terrain` from `track_tile_type` at the racer center; then the slide-collision block routes through `vehicle_step_axis_x/y`. The racer’s existing dir-specific `racer_corners_passable` check is preserved as an extra gate so the existing 4-corner racer tests stay green. **This is new behavior path** for the racer (same observable result, different call structure) — `test_racer` + `test_race_scenario` + the track2 P:1/P:2/P:3 HUD smoketest are the regression gate.

**Why the helper signature has no `dir`/turret/racer params for collision:** the canonical `vehicle_step_axis_x/y(px, py, v)` signature is intentionally generic so `patrol.c` (PR4) can reuse it without race/turret coupling. The directional hitbox and dynamic-blocker (turret/racer) checks are caller-specific and stay in the caller as an additional gate layered on top of the generic helper. The helper does the universal work (map-bounds clamp + static-terrain 16×16 corner passability); callers add their specialized gates. This keeps player byte-identical while giving patrol a clean reuse path.

**Why `vehicle_apply_physics` survives the split:** PR4’s patrol enemy has no gears — it calls the gearless convenience `vehicle_apply_physics` directly. Keeping it as a thin `friction → boost_clamp` wrapper preserves that single-call contract while the gear-bearing callers (player/racer) use the two split functions with their accel in the middle.

**Tech Stack:** C (SDCC/GBDK-2020), Unity test framework, gcc host tests (`make test`), `bank-manifest.json`, `#pragma bank 255` autobank, `track_test_set_map` / `track_test_set_collision_mask` test seams.

---

## File Structure

| File | Change |
|------|--------|
| `bank-manifest.json` | Add `src/vehicle_physics.c` bank 255 autobank |
| `src/vehicle_physics.h` | **New** — five BANKED signatures (`vehicle_apply_friction`, `vehicle_apply_boost_clamp`, `vehicle_apply_physics`, `vehicle_step_axis_x`, `vehicle_step_axis_y`) + `VEH_DIR_DX/DY` extern note (pure functions; no test accessors needed) |
| `src/vehicle_physics.c` | **New** — `vehicle_apply_friction`, `vehicle_apply_boost_clamp`, `vehicle_apply_physics` (= friction → boost_clamp), `vehicle_step_axis_x`, `vehicle_step_axis_y`, internal `veh_corners_passable` (non-directional 16×16) + `VEH_DIR_DX/DY` tables |
| `src/player.c` | `player_apply_physics`: friction → `vehicle_apply_friction`, then inline gear accel, then `vehicle_apply_boost_clamp`; X/Y collision blocks call `vehicle_step_axis_x/y`, keep directional `corners_passable` gate + ram/damage/gear-reset/SFX wrapper |
| `src/racer.c` | `racer_update`: friction → `vehicle_apply_friction`, then inline racer gear accel, then `vehicle_apply_boost_clamp`; slide block → `vehicle_step_axis_x/y` with the existing dir-specific gate preserved |
| `tests/test_vehicle_physics.c` | **New** — `vehicle_apply_friction` (SAND doubles, OIL no-gas), `vehicle_apply_boost_clamp` (BOOST delta + max-speed clamp), `vehicle_apply_physics` convenience (= friction then boost_clamp); slide collision blocked-axis via `track_test_set_collision_mask`; in-bounds clamp |
| `tests/test_player.c` | Unchanged — pure regression gate (must stay green) |
| `tests/test_racer.c` | Unchanged — pure regression gate (must stay green) |
| `tests/test_race_scenario.c` | Unchanged — pure regression gate (must stay green) |

> The test build uses `TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))` and `TEST_SRCS := $(wildcard tests/test_*.c)`. New `src/vehicle_physics.c` and `tests/test_vehicle_physics.c` are auto-discovered by the wildcards — **no Makefile edit required.** This task list contains a verification step rather than an edit step for the build wiring.

---

## Task 1: Add `vehicle_physics.c` to the bank manifest

**Files:**
- Modify: `bank-manifest.json`

- [ ] **Step 1: Add the manifest entry**

In `bank-manifest.json`, after the `"src/racer.c"` entry (line 44), add:
```json
  "src/vehicle_physics.c":       {"bank": 255, "reason": "autobank — shared vehicle terrain physics + axis-separated slide collision; called by player.c and racer.c (and patrol.c in PR4)"},
```
Ensure the preceding line keeps its trailing comma and the file remains valid JSON.

- [ ] **Step 2: Validate JSON**

```powershell
Get-Content bank-manifest.json | python -m json.tool
```
Expected: prints the object cleanly, no error.

- [ ] **Step 3: Commit**

```powershell
git add bank-manifest.json
git commit -m "chore: register vehicle_physics.c in bank manifest (bank 255)"
```

---

## Task 2: Create `src/vehicle_physics.h` (RED scaffolding)

**Files:**
- Create: `src/vehicle_physics.h`

> **GB gate:** `bank-pre-write` PreToolUse hook fires automatically on this write. Before writing, consult `gbdk-expert` in consultation mode: `"review header for a bank-255 module exposing five BANKED int16_t/void functions (three physics, two collision) consumed by other bank-255 modules — any BANKREF needs?"` (expected answer: no BANKREF for functions; cross-bank BANKED calls trampoline automatically). After the source compiles in a later task, `bank-post-build` + `make memory-check` fire automatically.

- [ ] **Step 1: Write the header**

Create `src/vehicle_physics.h` with EXACTLY these canonical signatures (do NOT rename):
```c
#ifndef VEHICLE_PHYSICS_H
#define VEHICLE_PHYSICS_H

#include <gb/gb.h>
#include <stdint.h>
#include "track.h"   /* TileType, active_map_w, active_map_h, track_passable */

/* Shared vehicle terrain physics + axis-separated slide collision.
 * The physics math is split into friction (pre gear-accel) and boost_clamp
 * (post gear-accel) so gear-bearing callers (player/racer) can drop their
 * caller-specific gear-accel between the two; a gearless convenience composes
 * them for callers with no accel (patrol, PR4).
 * Collision is generic: no gear/turret/racer/dir-hitbox coupling — callers layer
 * their own gates (directional hitbox, dynamic blockers, gear reset, damage). */

/* Direction → velocity-delta tables (0=T..7=LT), shared with player/racer.
 * Exposed so callers can keep their gas-axis decisions consistent. */
extern const int8_t VEH_DIR_DX[8];
extern const int8_t VEH_DIR_DY[8];

/* Friction portion (PRE gear-accel). Applies SAND/OIL/ROAD friction to *vx/*vy.
 *  terrain : TileType at the vehicle centre (SAND doubles friction; OIL zeroes it)
 *  gas     : 1 if the vehicle is under power this frame, else 0 (caller decides)
 *  dir     : facing 0..7 — indexes VEH_DIR_DX/DY to pick the gas-relieved axis
 * Does NOT touch gears or boost. Gear-reset-on-oil stays in the caller. */
void vehicle_apply_friction(int8_t *vx, int8_t *vy, uint8_t terrain,
                            uint8_t gas, uint8_t dir) BANKED;

/* Boost + clamp portion (POST gear-accel). Applies the BOOST -TERRAIN_BOOST_DELTA
 * to *vy when terrain == TILE_BOOST, then clamps both axes to ±max_speed.
 *  max_speed : caller-supplied per-axis velocity clamp magnitude. */
void vehicle_apply_boost_clamp(int8_t *vx, int8_t *vy, uint8_t terrain,
                               uint8_t max_speed) BANKED;

/* Gearless convenience = vehicle_apply_friction(...) then
 * vehicle_apply_boost_clamp(...) with NO accel between. For callers that have no
 * gear acceleration (patrol, PR4). Gear-bearing callers must instead call the
 * two split functions with their accel in the middle. */
void vehicle_apply_physics(int8_t *vx, int8_t *vy, uint8_t terrain,
                           uint8_t gas, uint8_t dir, uint8_t max_speed) BANKED;

/* Axis-separated slide step. Returns px+vx when the resulting 16x16 footprint
 * is in-bounds [0, active_map_w*8 - 16] AND all four 16x16 corners are
 * track_passable; otherwise returns px unchanged (caller detects the block by
 * comparing the return value to the input px). No damage/gear/ram side effects. */
int16_t vehicle_step_axis_x(int16_t px, int16_t py, int8_t vx) BANKED;

/* Same as vehicle_step_axis_x for the Y axis, using active_map_h. */
int16_t vehicle_step_axis_y(int16_t px, int16_t py, int8_t vy) BANKED;

#endif /* VEHICLE_PHYSICS_H */
```

- [ ] **Step 2: Commit**

```powershell
git add src/vehicle_physics.h
git commit -m "feat(vehicle_physics): add shared physics/collision header"
```

---

## Task 3: Write `tests/test_vehicle_physics.c` (RED)

**Files:**
- Create: `tests/test_vehicle_physics.c`

- [ ] **Step 1: Write the failing test file**

Create `tests/test_vehicle_physics.c`. These tests pin the extracted math BEFORE the implementation exists, so the binary fails to link (RED):

```c
/* tests/test_vehicle_physics.c */
#include "unity.h"
#include <gb/gb.h>
#include "vehicle_physics.h"
#include "track.h"
#include "config.h"

void setUp(void) {
    active_map_w = 8u;    /* 8 tiles * 8px = 64px; max px = 48 */
    active_map_h = 8u;
    mock_vram_clear();
}
void tearDown(void) {}

/* ---- vehicle_apply_friction: friction-only (PRE gear-accel) ---- */

/* ROAD with gas on the moving axis: no friction on that axis; perpendicular axis
 * loses PLAYER_FRICTION. gas=1, dir=DIR_R (DX!=0): vx relieved; vy (DY==0) -1. */
void test_veh_friction_road_gas_axis_relieved(void) {
    int8_t vx = 4, vy = 4;
    vehicle_apply_friction(&vx, &vy, TILE_ROAD, 1u, 2u /*DIR_R*/);
    TEST_ASSERT_EQUAL_INT8(4, vx);   /* gassed axis: no friction */
    TEST_ASSERT_EQUAL_INT8(3, vy);   /* perpendicular: -PLAYER_FRICTION(1) */
}

/* SAND doubles friction on the non-gassed axis vs ROAD. */
void test_veh_friction_sand_doubles(void) {
    int8_t road_vy, sand_vy;
    {
        int8_t vx = 0, vy = -4;
        vehicle_apply_friction(&vx, &vy, TILE_ROAD, 1u, 2u /*DIR_R, DY==0*/);
        road_vy = vy;   /* -4 + PLAYER_FRICTION(1) = -3 */
    }
    {
        int8_t vx = 0, vy = -4;
        vehicle_apply_friction(&vx, &vy, TILE_SAND, 1u, 2u /*DIR_R*/);
        sand_vy = vy;   /* -4 + 2*PLAYER_FRICTION = -2 */
    }
    TEST_ASSERT_EQUAL_INT8(-3, road_vy);
    TEST_ASSERT_EQUAL_INT8(-2, sand_vy);
    TEST_ASSERT_GREATER_THAN_INT8(road_vy, sand_vy); /* sand decelerates faster */
}

/* OIL zeroes friction (frictionless slide): velocity unchanged. The caller passes
 * gas=0 on oil; friction is zero regardless of the gas-axis decision. */
void test_veh_friction_oil_none(void) {
    int8_t vx = 4, vy = 4;
    vehicle_apply_friction(&vx, &vy, TILE_OIL, 0u /*oil disables gas*/, 2u);
    TEST_ASSERT_EQUAL_INT8(4, vx);
    TEST_ASSERT_EQUAL_INT8(4, vy);
}

/* vehicle_apply_friction does NOT apply boost: on TILE_BOOST it only does friction. */
void test_veh_friction_ignores_boost(void) {
    int8_t vx = 0, vy = 0;
    vehicle_apply_friction(&vx, &vy, TILE_BOOST, 1u, 0u /*DIR_T*/);
    TEST_ASSERT_EQUAL_INT8(0, vx);   /* boost delta is boost_clamp's job, not friction's */
    TEST_ASSERT_EQUAL_INT8(0, vy);
}

/* ---- vehicle_apply_boost_clamp: boost-delta + clamp (POST gear-accel) ---- */

/* BOOST kicks vy negative by TERRAIN_BOOST_DELTA and clamps to boost max speed. */
void test_veh_boost_clamp_accelerates_up(void) {
    int8_t vx = 0, vy = 0;
    vehicle_apply_boost_clamp(&vx, &vy, TILE_BOOST, TERRAIN_BOOST_MAX_SPEED);
    TEST_ASSERT_LESS_THAN_INT8(0, vy);    /* boost delta moved vy negative (upward) */
    TEST_ASSERT_EQUAL_INT8(0, vx);        /* x untouched by boost */
}

/* boost_clamp does NOT apply friction: ROAD leaves velocity unchanged below clamp. */
void test_veh_boost_clamp_no_friction(void) {
    int8_t vx = 3, vy = 3;
    vehicle_apply_boost_clamp(&vx, &vy, TILE_ROAD, 8u);
    TEST_ASSERT_EQUAL_INT8(3, vx);
    TEST_ASSERT_EQUAL_INT8(3, vy);
}

/* max_speed clamp: a velocity above max_speed is clamped to ±max_speed. */
void test_veh_boost_clamp_max_speed(void) {
    int8_t vx = 100, vy = -100;
    vehicle_apply_boost_clamp(&vx, &vy, TILE_ROAD, 5u);
    TEST_ASSERT_EQUAL_INT8(5, vx);
    TEST_ASSERT_EQUAL_INT8(-5, vy);
}

/* ---- vehicle_apply_physics: gearless convenience = friction then boost_clamp ---- */

/* The convenience equals calling friction then boost_clamp with NO accel between.
 * Verify composition for ROAD (friction only). */
void test_veh_physics_composes_road(void) {
    int8_t cx = 4, cy = 4;          /* via convenience */
    int8_t fx = 4, fy = 4;          /* via split: friction then boost_clamp */
    vehicle_apply_physics(&cx, &cy, TILE_ROAD, 1u, 2u /*DIR_R*/, 8u);
    vehicle_apply_friction(&fx, &fy, TILE_ROAD, 1u, 2u);
    vehicle_apply_boost_clamp(&fx, &fy, TILE_ROAD, 8u);
    TEST_ASSERT_EQUAL_INT8(fx, cx);
    TEST_ASSERT_EQUAL_INT8(fy, cy);
}

/* Composition holds on BOOST (friction then boost-delta then clamp). */
void test_veh_physics_composes_boost(void) {
    int8_t cx = 0, cy = 0;
    int8_t fx = 0, fy = 0;
    vehicle_apply_physics(&cx, &cy, TILE_BOOST, 1u, 0u /*DIR_T*/, TERRAIN_BOOST_MAX_SPEED);
    vehicle_apply_friction(&fx, &fy, TILE_BOOST, 1u, 0u);
    vehicle_apply_boost_clamp(&fx, &fy, TILE_BOOST, TERRAIN_BOOST_MAX_SPEED);
    TEST_ASSERT_EQUAL_INT8(fx, cx);
    TEST_ASSERT_EQUAL_INT8(fy, cy);
    TEST_ASSERT_LESS_THAN_INT8(0, cy);   /* boosted upward */
}

/* ---- vehicle_step_axis_x / _y: slide collision ---- */

static const uint8_t road_map_8x8[8u * 8u] = {
    1,1,1,0,1,1,1,1,   /* col 3 = WALL */
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
    1,1,1,0,1,1,1,1,
};

/* X step into a wall column is blocked: px returned unchanged. */
void test_veh_step_x_blocked_by_wall(void) {
    static const uint8_t road_pass[8] = {0,0,0,0,0,0,0,0}; /* all 8 px passable */
    static const uint8_t wall_block[8] = {255,255,255,255,255,255,255,255};
    track_test_set_map(road_map_8x8, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);   /* tile 1 ROAD: fully passable */
    track_test_set_collision_mask(0u, wall_block);  /* tile 0 WALL: fully blocked */
    /* px=8 (footprint cols 1..2 road); vx=+8 -> px=16, right corner px+15=31 -> col 3 WALL */
    {
        int16_t out = vehicle_step_axis_x(8, 0, 8);
        TEST_ASSERT_EQUAL_INT16(8, out);  /* blocked: unchanged */
    }
}

/* X step on clear road advances by vx. */
void test_veh_step_x_clear_advances(void) {
    static const uint8_t road_pass[8] = {0,0,0,0,0,0,0,0};
    static const uint8_t wall_block[8] = {255,255,255,255,255,255,255,255};
    static const uint8_t all_road[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    track_test_set_map(all_road, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    track_test_set_collision_mask(0u, wall_block);
    {
        int16_t out = vehicle_step_axis_x(8, 0, 4);
        TEST_ASSERT_EQUAL_INT16(12, out);
    }
}

/* Y step into a wall row is blocked: py returned unchanged. */
void test_veh_step_y_blocked_by_wall(void) {
    static const uint8_t road_pass[8] = {0,0,0,0,0,0,0,0};
    static const uint8_t wall_block[8] = {255,255,255,255,255,255,255,255};
    static const uint8_t row_wall[8u * 8u] = {
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        0,0,0,0,0,0,0,0,   /* row 3 = WALL */
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1,
    };
    track_test_set_map(row_wall, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    track_test_set_collision_mask(0u, wall_block);
    {
        int16_t out = vehicle_step_axis_y(8, 8, 8); /* py=8 -> 16, bottom corner 31 -> row 3 WALL */
        TEST_ASSERT_EQUAL_INT16(8, out);
    }
}

/* In-bounds clamp: moving X past the right map edge is blocked. */
void test_veh_step_x_oob_right_blocked(void) {
    static const uint8_t road_pass[8] = {0,0,0,0,0,0,0,0};
    static const uint8_t all_road[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    track_test_set_map(all_road, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    /* active_map_w=8 -> max px = 64-16 = 48. px=48, vx=+4 -> 52 > 48 -> blocked. */
    {
        int16_t out = vehicle_step_axis_x(48, 0, 4);
        TEST_ASSERT_EQUAL_INT16(48, out);
    }
}

/* In-bounds clamp: moving X below 0 is blocked. */
void test_veh_step_x_oob_left_blocked(void) {
    static const uint8_t road_pass[8] = {0,0,0,0,0,0,0,0};
    static const uint8_t all_road[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    track_test_set_map(all_road, 8u, 8u);
    track_test_set_collision_mask(1u, road_pass);
    {
        int16_t out = vehicle_step_axis_x(0, 0, -4); /* -4 < 0 -> blocked */
        TEST_ASSERT_EQUAL_INT16(0, out);
    }
}

int main(void) {
    UNITY_BEGIN();
    /* vehicle_apply_friction */
    RUN_TEST(test_veh_friction_road_gas_axis_relieved);
    RUN_TEST(test_veh_friction_sand_doubles);
    RUN_TEST(test_veh_friction_oil_none);
    RUN_TEST(test_veh_friction_ignores_boost);
    /* vehicle_apply_boost_clamp */
    RUN_TEST(test_veh_boost_clamp_accelerates_up);
    RUN_TEST(test_veh_boost_clamp_no_friction);
    RUN_TEST(test_veh_boost_clamp_max_speed);
    /* vehicle_apply_physics convenience (composition) */
    RUN_TEST(test_veh_physics_composes_road);
    RUN_TEST(test_veh_physics_composes_boost);
    /* vehicle_step_axis_x / _y */
    RUN_TEST(test_veh_step_x_blocked_by_wall);
    RUN_TEST(test_veh_step_x_clear_advances);
    RUN_TEST(test_veh_step_y_blocked_by_wall);
    RUN_TEST(test_veh_step_x_oob_right_blocked);
    RUN_TEST(test_veh_step_x_oob_left_blocked);
    return UNITY_END();
}
```

- [ ] **Step 2: Run the tests — expect FAIL (RED)**

```powershell
make test
```
Expected: the `test_vehicle_physics` binary fails to compile/link (undefined `vehicle_apply_friction`, `vehicle_apply_boost_clamp`, `vehicle_apply_physics`, `vehicle_step_axis_x/y`, `VEH_DIR_DX/DY`). This confirms the test is wired and the implementation is genuinely missing. (Note: `make test` early-exits at the first failing binary alphabetically — `test_vehicle_physics` sorts late, so other suites run first; if an earlier suite fails for an unrelated reason, fix that first.)

- [ ] **Step 3: Commit the RED test**

```powershell
git add tests/test_vehicle_physics.c
git commit -m "test(vehicle_physics): RED — pin terrain physics + slide collision"
```

---

## Task 4: Implement `src/vehicle_physics.c` (GREEN)

**Files:**
- Create: `src/vehicle_physics.c`

> **GB gate:** `bank-pre-write` hook fires automatically. Consult `gbdk-expert` in implementation mode: `"implement this task: create src/vehicle_physics.c (#pragma bank 255) with vehicle_apply_friction + vehicle_apply_boost_clamp + vehicle_apply_physics (= friction then boost_clamp) + vehicle_step_axis_x/y exactly as specified, splitting the terrain math from player_apply_physics lines 317-358 at the friction/accel and accel/boost seams, and the in-bounds+corner check from player_update lines 191/217; uint8_t loop counters, no float, no compound literals"`. After build, `bank-post-build` + `make memory-check` fire automatically.

- [ ] **Step 1: Write the implementation**

Create `src/vehicle_physics.c`. The terrain math is lifted **verbatim** from `player_apply_physics`, split at the two seams where the caller's gear accel lands: `vehicle_apply_friction` is the pre-accel friction loops; `vehicle_apply_boost_clamp` is the post-accel boost-delta + clamp. `vehicle_apply_physics` simply composes them (no accel between) for the gearless patrol caller.

> **Important extraction detail:** in `player_apply_physics`, gear **acceleration** (`vx += GEAR_ACCEL * DIR_DX`) is applied between friction and boost. That accel is *gear-specific* and stays in the caller. By splitting the helper at exactly that point, the player/racer call `vehicle_apply_friction`, run their unchanged inline accel, then call `vehicle_apply_boost_clamp` — byte-identical to the old inline sequence. The gearless `vehicle_apply_physics` convenience exists for callers (patrol, PR4) that have no accel to insert. See Tasks 5/6/7/8 for exact call placement.

```c
#pragma bank 255

#include <gb/gb.h>
#include "vehicle_physics.h"
#include "track.h"
#include "config.h"

/* Direction → velocity deltas: 0=T,1=RT,2=R,3=RB,4=B,5=LB,6=L,7=LT.
 * Identical values to player.c DIR_DX/DY and racer.c RACER_DIR_DX/DY. */
const int8_t VEH_DIR_DX[8] = {  0,  1,  1,  1,  0, -1, -1, -1 };
const int8_t VEH_DIR_DY[8] = { -1, -1,  0,  1,  1,  1,  0, -1 };

/* Non-directional 16x16 corner passability: four corners at offsets {0,15}.
 * Static terrain only — dynamic blockers (turret/racer) are caller gates. */
static uint8_t veh_corners_passable(int16_t wx, int16_t wy) {
    if (!track_passable(wx,        wy))        return 0u;
    if (!track_passable(wx + 15,   wy))        return 0u;
    if (!track_passable(wx,        wy + 15))   return 0u;
    if (!track_passable(wx + 15,   wy + 15))   return 0u;
    return 1u;
}

/* Friction portion (PRE gear-accel) — verbatim from player_apply_physics 317-337. */
void vehicle_apply_friction(int8_t *vx, int8_t *vy, uint8_t terrain,
                            uint8_t gas, uint8_t dir) BANKED {
    uint8_t i;
    uint8_t fric_x;
    uint8_t fric_y;

    if (terrain == TILE_SAND) {
        fric_x = (gas && VEH_DIR_DX[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = (gas && VEH_DIR_DY[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
    } else if (terrain == TILE_OIL) {
        fric_x = 0u;
        fric_y = 0u;
    } else {
        fric_x = (gas && VEH_DIR_DX[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
        fric_y = (gas && VEH_DIR_DY[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
    }

    for (i = 0u; i < fric_x; i++) {
        if      (*vx > 0) *vx = (int8_t)(*vx - 1);
        else if (*vx < 0) *vx = (int8_t)(*vx + 1);
    }
    for (i = 0u; i < fric_y; i++) {
        if      (*vy > 0) *vy = (int8_t)(*vy - 1);
        else if (*vy < 0) *vy = (int8_t)(*vy + 1);
    }
}

/* Boost-delta + max-speed clamp (POST gear-accel) — verbatim from 344-358. */
void vehicle_apply_boost_clamp(int8_t *vx, int8_t *vy, uint8_t terrain,
                               uint8_t max_speed) BANKED {
    if (terrain == TILE_BOOST) {
        *vy = (int8_t)(*vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    if (*vx >  (int8_t)max_speed) *vx =  (int8_t)max_speed;
    if (*vx < -(int8_t)max_speed) *vx = -(int8_t)max_speed;
    if (*vy >  (int8_t)max_speed) *vy =  (int8_t)max_speed;
    if (*vy < -(int8_t)max_speed) *vy = -(int8_t)max_speed;
}

/* Gearless convenience: friction then boost_clamp, NO accel between.
 * For callers with no gear acceleration (patrol, PR4). */
void vehicle_apply_physics(int8_t *vx, int8_t *vy, uint8_t terrain,
                           uint8_t gas, uint8_t dir, uint8_t max_speed) BANKED {
    vehicle_apply_friction(vx, vy, terrain, gas, dir);
    vehicle_apply_boost_clamp(vx, vy, terrain, max_speed);
}

int16_t vehicle_step_axis_x(int16_t px, int16_t py, int8_t vx) BANKED {
    int16_t new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 &&
        new_px <= (int16_t)((uint16_t)active_map_w * 8u - 16u) &&
        veh_corners_passable(new_px, py)) {
        return new_px;
    }
    return px;
}

int16_t vehicle_step_axis_y(int16_t px, int16_t py, int8_t vy) BANKED {
    int16_t new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= 0 &&
        new_py <= (int16_t)((uint16_t)active_map_h * 8u - 16u) &&
        veh_corners_passable(px, new_py)) {
        return new_py;
    }
    return py;
}
```

> **Note on `test_veh_friction_road_gas_axis_relieved` expectation:** `vehicle_apply_friction` does NOT add gear accel or boost — so with `vx=4, gas, dir=R`, `vx` stays 4 (friction relieved on the gassed X axis), and `vy=4` loses 1 friction step → 3. The test expects exactly `(4, 3)`. The composition tests (`test_veh_physics_composes_road/_boost`) prove `vehicle_apply_physics` == `vehicle_apply_friction` then `vehicle_apply_boost_clamp`. Confirm the tests match this; if the worker wrote a different expectation, fix the test to match the verbatim-extracted math, not the other way around.

- [ ] **Step 2: Run host tests — expect `test_vehicle_physics` GREEN**

```powershell
make test
```
Expected: all `test_vehicle_physics` assertions pass. If an earlier-sorted binary fails, that is a regression introduced elsewhere — STOP and investigate before proceeding (do not modify unrelated tests).

- [ ] **Step 3: Build the ROM**

```powershell
make
```
`bank-post-build` + `make memory-check` fire automatically — confirm no FAIL/ERROR in the hook output. The module is not yet *called* by ROM code, so this only verifies it compiles and banks cleanly.

- [ ] **Step 4: Commit**

```powershell
git add src/vehicle_physics.c
git commit -m "feat(vehicle_physics): implement shared terrain physics + slide collision (GREEN)"
```

---

## Task 5: Converge `player.c` terrain math onto `vehicle_apply_friction` + `vehicle_apply_boost_clamp`

**Files:**
- Modify: `src/player.c`

> **GB gate:** `bank-pre-write` hook fires automatically. Consult `gbdk-expert`: `"I am replacing the inline friction in player_apply_physics with vehicle_apply_friction, keeping the inline gear accel in place, then replacing the inline boost-delta + clamp with vehicle_apply_boost_clamp; gear shift + gear-reset-on-oil stay in player.c — confirm the split lands at the friction/accel and accel/boost seams and is byte-identical"`. After build, `bank-post-build` + `make memory-check` fire automatically.

- [ ] **Step 1: Add the include**

In `src/player.c`, after `#include "racer.h"` (line 15), add:
```c
#include "vehicle_physics.h"
```

- [ ] **Step 2: Split the inline friction/boost/clamp around the unchanged gear accel**

The original `player_apply_physics` body (lines 317–358) interleaves: friction → gear accel → boost → clamp. The split API lands **exactly** at the friction/accel and accel/boost seams: replace the friction block with `vehicle_apply_friction`, keep the gear accel inline, and replace the boost-delta + clamp with `vehicle_apply_boost_clamp`. The gear-shift block (computing `max_speed` first) stays. The result is byte-identical.

BEFORE (lines 317–358; the gear-shift block continues afterward unchanged):
```c
    if (terrain == TILE_SAND) {
        fric_x = (gas && DIR_DX[player_dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = (gas && DIR_DY[player_dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
    } else if (terrain == TILE_OIL) {
        fric_x = 0u;
        fric_y = 0u;
        current_gear    = 0u;   /* gear resets immediately on oil */
        downshift_timer = 0u;
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
        vx = (int8_t)(vx + (int8_t)((int8_t)GEAR_ACCEL[current_gear] * DIR_DX[player_dir]));
        vy = (int8_t)(vy + (int8_t)((int8_t)GEAR_ACCEL[current_gear] * DIR_DY[player_dir]));
    }

    if (terrain == TILE_BOOST) {
        vy = (int8_t)(vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    {
        uint8_t max_speed = (terrain == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED
                                                    : GEAR_MAX_SPEED[current_gear];
        uint8_t spd_x;
        uint8_t spd_y;
        uint8_t speed;

        if (vx >  (int8_t)max_speed) vx =  (int8_t)max_speed;
        if (vx < -(int8_t)max_speed) vx = -(int8_t)max_speed;
        if (vy >  (int8_t)max_speed) vy =  (int8_t)max_speed;
        if (vy < -(int8_t)max_speed) vy = -(int8_t)max_speed;

        /* Gear shift: compute speed magnitude (no multiply, no stdlib abs) */
        spd_x = (vx < 0) ? (uint8_t)(-vx) : (uint8_t)vx;
        spd_y = (vy < 0) ? (uint8_t)(-vy) : (uint8_t)vy;
        speed = (spd_x > spd_y) ? spd_x : spd_y;
        ...gear shift continues...
```

AFTER — friction → helper, accel stays inline, boost+clamp → helper. The gear-reset-on-oil stays in `player.c` (it is gear state, not friction); `vehicle_apply_friction` zeroes friction on OIL on its own. `max_speed` must be computed BEFORE the clamp helper call (it feeds the helper) but the gear-shift speed magnitude is computed AFTER, exactly as before:
```c
    /* Gear-reset-on-oil stays here (gear state is the caller's). */
    if (terrain == TILE_OIL) {
        current_gear    = 0u;
        downshift_timer = 0u;
    }

    /* Friction (pre-accel) via the shared helper. */
    vehicle_apply_friction(&vx, &vy, terrain, gas, player_dir);

    /* Gear accel stays inline — caller-specific, lands between friction and boost. */
    if (gas) {
        vx = (int8_t)(vx + (int8_t)((int8_t)GEAR_ACCEL[current_gear] * DIR_DX[player_dir]));
        vy = (int8_t)(vy + (int8_t)((int8_t)GEAR_ACCEL[current_gear] * DIR_DY[player_dir]));
    }

    {
        uint8_t max_speed = (terrain == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED
                                                    : GEAR_MAX_SPEED[current_gear];
        uint8_t spd_x;
        uint8_t spd_y;
        uint8_t speed;

        /* Boost-delta + clamp (post-accel) via the shared helper. */
        vehicle_apply_boost_clamp(&vx, &vy, terrain, max_speed);

        /* Gear shift: compute speed magnitude (no multiply, no stdlib abs) */
        spd_x = (vx < 0) ? (uint8_t)(-vx) : (uint8_t)vx;
        spd_y = (vy < 0) ? (uint8_t)(-vy) : (uint8_t)vy;
        speed = (spd_x > spd_y) ? spd_x : spd_y;
        ...gear shift continues unchanged...
    }
```

> **Byte-identical reasoning:** `vehicle_apply_friction` is the verbatim friction block (SAND/OIL/ROAD selection + the two friction loops), minus the gear-reset-on-oil which is hoisted up (it is order-independent of the friction math — it only writes `current_gear`/`downshift_timer`, not `vx`/`vy`). The inline gear accel is unchanged. `vehicle_apply_boost_clamp` is the verbatim boost-delta + the four clamp lines. The sequence `friction → accel → boost → clamp` is preserved exactly. `i`, `fric_x`, `fric_y` locals are now unused in `player_apply_physics` — remove them from the declarations at the top of the function (the `gbdk-expert` consult should confirm SDCC warns on unused otherwise). `test_player` is the proof.

- [ ] **Step 3: Run host tests — `test_player` must stay GREEN**

```powershell
make test
```
Expected: `test_player` stays green — the split is byte-identical, so every player friction/boost/clamp/gear-shift test passes unchanged. Any red → STOP, do not edit tests; re-examine the seam placement (gear-reset-on-oil hoist, accel position, `max_speed` computed before the clamp helper).

- [ ] **Step 4: Build + commit**

```powershell
make
```
`bank-post-build` + `make memory-check` auto-fire — confirm clean.
```powershell
git add src/player.c
git commit -m "feat(player): converge terrain physics onto vehicle_apply_friction/boost_clamp"
```

---

## Task 6: Converge `player.c` collision onto `vehicle_step_axis_x/y`

**Files:**
- Modify: `src/player.c`

> **GB gate:** `bank-pre-write` auto-fires. Consult `gbdk-expert`: `"replace player_update X/Y in-bounds+corners_passable position commit with vehicle_step_axis_x/y, keeping the directional corners_passable gate + ram/damage/gear-reset/SFX wrapper byte-identical"`. After build, `bank-post-build` + `make memory-check` auto-fire.

- [ ] **Step 1: Replace the X-axis commit (lines 190–213)**

BEFORE:
```c
    new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 && new_px <= (int16_t)((uint16_t)active_map_w * 8u - 16u) && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        uint8_t k;
        uint8_t racer_hit;
        vx = 0;
        current_gear    = 0u;
        downshift_timer = 0u;
        racer_hit = 0u;
        for (k = 0u; k < 4u; k++) {
            if (corner_active_racer(new_px + HITBOX_X[player_dir][k],
                                    py     + HITBOX_Y[player_dir][k])) {
                racer_hit = 1u;
                break;
            }
        }
        if (racer_hit) {
            damage_apply(RACER_RAM_DAMAGE);
        } else {
            damage_apply(1u);
        }
        sfx_play(SFX_HIT);
    }
```

AFTER:
```c
    new_px = (int16_t)(px + (int16_t)vx);
    /* Shared in-bounds + static-terrain corner check, then the player's
     * directional hitbox + dynamic-blocker gate. Block iff either rejects. */
    if (vehicle_step_axis_x(px, py, vx) == new_px && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        uint8_t k;
        uint8_t racer_hit;
        vx = 0;
        current_gear    = 0u;
        downshift_timer = 0u;
        racer_hit = 0u;
        for (k = 0u; k < 4u; k++) {
            if (corner_active_racer(new_px + HITBOX_X[player_dir][k],
                                    py     + HITBOX_Y[player_dir][k])) {
                racer_hit = 1u;
                break;
            }
        }
        if (racer_hit) {
            damage_apply(RACER_RAM_DAMAGE);
        } else {
            damage_apply(1u);
        }
        sfx_play(SFX_HIT);
    }
```

> **Byte-identical reasoning:** `vehicle_step_axis_x(px,py,vx) == new_px` is true iff `new_px` passed the in-bounds clamp AND `veh_corners_passable(new_px,py)` (non-directional 16×16). The original committed iff in-bounds AND `corners_passable(new_px,py)` (directional + turret + racer). The non-directional check is a SUPERSET-allow of the directional one only where the directional hitbox is laxer; ANDing both reproduces the original gate exactly **only if** `veh_corners_passable` never blocks something `corners_passable` would allow. Because the directional hitbox points are all within [0,15] (the same 16×16 box the 4 corners bound), and the player’s existing tests pin the directional behavior, the AND of (in-bounds) ∧ (directional corners) is the binding gate. **Verify via `test_player` staying green** — the directional `corners_passable` remains the deciding gate, the helper only adds the (already-present) in-bounds clamp.

- [ ] **Step 2: Replace the Y-axis commit (lines 216–239)** analogously:

BEFORE:
```c
    new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= 0 && new_py <= (int16_t)((uint16_t)active_map_h * 8u - 16u) && corners_passable(px, new_py)) {
        py = new_py;
    } else {
```

AFTER:
```c
    new_py = (int16_t)(py + (int16_t)vy);
    if (vehicle_step_axis_y(px, py, vy) == new_py && corners_passable(px, new_py)) {
        py = new_py;
    } else {
```
(The `else` body — ram/damage/gear-reset/SFX — is unchanged.)

- [ ] **Step 3: Run host tests — `test_player` + `test_race_scenario` must stay GREEN**

```powershell
make test
```
Expected: ALL suites green, especially `test_player` (collision, clamp, hitbox, ram-damage tests) and `test_race_scenario`. Any red here means the AND-gate is not byte-identical — STOP, do not edit tests, re-examine the helper vs. directional-hitbox equivalence.

- [ ] **Step 4: Build + smoketest-light**

```powershell
make
```
`bank-post-build` + `make memory-check` auto-fire — confirm clean.

- [ ] **Step 5: Commit**

```powershell
git add src/player.c
git commit -m "feat(player): route wall-slide collision through vehicle_step_axis_x/y"
```

---

## Task 7: Converge `racer.c` terrain math onto `vehicle_apply_friction` + `vehicle_apply_boost_clamp`

**Files:**
- Modify: `src/racer.c`

> **GB gate:** `bank-pre-write` auto-fires. Consult `gbdk-expert`: `"implement this task: replace the inline racer friction in racer_update with vehicle_apply_friction, keep the inline racer gear accel (RACER_GEAR_ACCEL_TBL), then replace the inline boost-delta + clamp with vehicle_apply_boost_clamp; gear shift + gear-reset-on-oil stay in racer.c; preserve byte-identical racer behavior"`. After build, `bank-post-build` + `make memory-check` auto-fire.

The racer math (lines 323–391) has the SAME friction → accel → boost → clamp → gear-shift ordering as the player, so it converges the SAME way via the split API: `vehicle_apply_friction` for the pre-accel friction, the racer's unchanged inline gear accel in the middle, then `vehicle_apply_boost_clamp` for the post-accel boost-delta + clamp. The racer's `dir` indexes `VEH_DIR_DX/DY` (identical values to `RACER_DIR_DX/DY`); `terrain` is the already-computed `tile_type` from `track_tile_type_from_index` at the racer center.

- [ ] **Step 1: Add the include**

In `src/racer.c`, after `#include "projectile.h"` (line 13), add:
```c
#include "vehicle_physics.h"
```

- [ ] **Step 2: Split the inline racer friction/boost/clamp around the unchanged gear accel**

BEFORE (lines 323–371; the gear-shift block at 373–390 continues unchanged):
```c
        /* ---- Gear physics (mirrors player_apply_physics, always full throttle) ---- */
        {
            uint8_t fric_x;
            uint8_t fric_y;
            uint8_t gas;
            uint8_t j;
            uint8_t max_speed;
            uint8_t spd_x;
            uint8_t spd_y;
            uint8_t speed;

            gas = (tile_type != TILE_OIL) ? 1u : 0u;

            if (tile_type == TILE_SAND) {
                fric_x = (gas && RACER_DIR_DX[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
                fric_y = (gas && RACER_DIR_DY[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
            } else if (tile_type == TILE_OIL) {
                fric_x = 0u;
                fric_y = 0u;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            } else {
                fric_x = (gas && RACER_DIR_DX[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
                fric_y = (gas && RACER_DIR_DY[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
            }

            for (j = 0u; j < fric_x; j++) {
                if      (racer_vx[i] > 0) racer_vx[i] = (int8_t)(racer_vx[i] - 1);
                else if (racer_vx[i] < 0) racer_vx[i] = (int8_t)(racer_vx[i] + 1);
            }
            for (j = 0u; j < fric_y; j++) {
                if      (racer_vy[i] > 0) racer_vy[i] = (int8_t)(racer_vy[i] - 1);
                else if (racer_vy[i] < 0) racer_vy[i] = (int8_t)(racer_vy[i] + 1);
            }

            if (gas) {
                racer_vx[i] = (int8_t)(racer_vx[i] + (int8_t)((int8_t)RACER_GEAR_ACCEL_TBL[racer_gear[i]] * RACER_DIR_DX[dir]));
                racer_vy[i] = (int8_t)(racer_vy[i] + (int8_t)((int8_t)RACER_GEAR_ACCEL_TBL[racer_gear[i]] * RACER_DIR_DY[dir]));
            }

            if (tile_type == TILE_BOOST) {
                racer_vy[i] = (int8_t)(racer_vy[i] - (int8_t)TERRAIN_BOOST_DELTA);
            }

            max_speed = (tile_type == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : RACER_GEAR_MAX_SPD[racer_gear[i]];
            if (racer_vx[i] >  (int8_t)max_speed) racer_vx[i] =  (int8_t)max_speed;
            if (racer_vx[i] < -(int8_t)max_speed) racer_vx[i] = -(int8_t)max_speed;
            if (racer_vy[i] >  (int8_t)max_speed) racer_vy[i] =  (int8_t)max_speed;
            if (racer_vy[i] < -(int8_t)max_speed) racer_vy[i] = -(int8_t)max_speed;

            spd_x = (racer_vx[i] < 0) ? (uint8_t)(-racer_vx[i]) : (uint8_t)racer_vx[i];
            spd_y = (racer_vy[i] < 0) ? (uint8_t)(-racer_vy[i]) : (uint8_t)racer_vy[i];
            speed = (spd_x > spd_y) ? spd_x : spd_y;
            ...gear shift continues unchanged...
```

AFTER — friction → helper, racer gear accel stays inline, boost+clamp → helper. Gear-reset-on-oil is hoisted (it writes only gear state, not velocity, so it is order-independent of friction; `vehicle_apply_friction` zeroes friction on OIL on its own):
```c
        /* ---- Gear physics (shared friction/boost_clamp, always full throttle) ---- */
        {
            uint8_t gas;
            uint8_t max_speed;
            uint8_t spd_x;
            uint8_t spd_y;
            uint8_t speed;

            gas = (tile_type != TILE_OIL) ? 1u : 0u;

            /* Gear-reset-on-oil stays here (gear state is the caller's). */
            if (tile_type == TILE_OIL) {
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            }

            /* Friction (pre-accel) via the shared helper. */
            vehicle_apply_friction(&racer_vx[i], &racer_vy[i], tile_type, gas, dir);

            /* Racer gear accel stays inline — caller-specific, between friction and boost. */
            if (gas) {
                racer_vx[i] = (int8_t)(racer_vx[i] + (int8_t)((int8_t)RACER_GEAR_ACCEL_TBL[racer_gear[i]] * RACER_DIR_DX[dir]));
                racer_vy[i] = (int8_t)(racer_vy[i] + (int8_t)((int8_t)RACER_GEAR_ACCEL_TBL[racer_gear[i]] * RACER_DIR_DY[dir]));
            }

            /* Boost-delta + clamp (post-accel) via the shared helper. */
            max_speed = (tile_type == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : RACER_GEAR_MAX_SPD[racer_gear[i]];
            vehicle_apply_boost_clamp(&racer_vx[i], &racer_vy[i], tile_type, max_speed);

            spd_x = (racer_vx[i] < 0) ? (uint8_t)(-racer_vx[i]) : (uint8_t)racer_vx[i];
            spd_y = (racer_vy[i] < 0) ? (uint8_t)(-racer_vy[i]) : (uint8_t)racer_vy[i];
            speed = (spd_x > spd_y) ? spd_x : spd_y;
            ...gear shift continues unchanged...
```

> **Byte-identical reasoning:** `vehicle_apply_friction` reproduces the racer's SAND/OIL/ROAD friction selection + loops verbatim (`VEH_DIR_DX/DY` == `RACER_DIR_DX/DY`). The gear-reset-on-oil is hoisted out of the `else if` but runs on the same condition and only touches gear state, so velocity is unaffected. The inline racer gear accel is unchanged. `vehicle_apply_boost_clamp` reproduces the boost-delta + four clamp lines. Sequence `friction → accel → boost → clamp` preserved. The `fric_x`, `fric_y`, `j` locals are now unused — remove them from the block's declarations (SDCC warns on unused otherwise). `test_racer` + `test_race_scenario` are the proof.

- [ ] **Step 3: Run host tests — `test_racer` + `test_race_scenario` stay GREEN**

```powershell
make test
```
Expected: all suites green — the racer terrain split is byte-identical. Any red → STOP, do not edit tests; re-examine the gear-reset-on-oil hoist, accel position, and `max_speed` computed before the clamp helper.

- [ ] **Step 4: Build + commit**

```powershell
make
```
`bank-post-build` + `make memory-check` auto-fire — confirm clean.
```powershell
git add src/racer.c
git commit -m "feat(racer): converge terrain physics onto vehicle_apply_friction/boost_clamp"
```

---

## Task 8: Converge `racer.c` slide collision onto `vehicle_step_axis_x/y`

**Files:**
- Modify: `src/racer.c`

> **GB gate:** `bank-pre-write` auto-fires. Consult `gbdk-expert`: `"replace the racer axis-split collision (racer_corners_passable) with vehicle_step_axis_x/y, keeping the dir-specific racer_corners_passable as an extra gate so the 4-corner racer tests stay green; preserve vx/vy/gear-zeroing on block"`. After build, `bank-post-build` + `make memory-check` auto-fire.

- [ ] **Step 1: Replace the axis-split collision block (lines 393–413)**

BEFORE:
```c
        /* ---- Axis-split collision ---- */
        {
            int16_t new_px = (int16_t)(racer_px[i] + (int16_t)racer_vx[i]);
            int16_t new_py = (int16_t)(racer_py[i] + (int16_t)racer_vy[i]);

            if (racer_corners_passable(new_px, racer_py[i], dir)) {
                racer_px[i] = new_px;
            } else {
                racer_vx[i] = (int8_t)0;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            }

            if (racer_corners_passable(racer_px[i], new_py, dir)) {
                racer_py[i] = new_py;
            } else {
                racer_vy[i] = (int8_t)0;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            }
        }
```

AFTER:
```c
        /* ---- Axis-split collision (shared helper + dir-specific gate) ---- */
        {
            int16_t new_px = (int16_t)(racer_px[i] + (int16_t)racer_vx[i]);
            int16_t new_py;

            /* X: shared in-bounds+static-terrain step AND the racer's dir hitbox. */
            if (vehicle_step_axis_x(racer_px[i], racer_py[i], racer_vx[i]) == new_px &&
                racer_corners_passable(new_px, racer_py[i], dir)) {
                racer_px[i] = new_px;
            } else {
                racer_vx[i] = (int8_t)0;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            }

            /* Y uses the post-X racer_px[i] (slide), matching the original. */
            new_py = (int16_t)(racer_py[i] + (int16_t)racer_vy[i]);
            if (vehicle_step_axis_y(racer_px[i], racer_py[i], racer_vy[i]) == new_py &&
                racer_corners_passable(racer_px[i], new_py, dir)) {
                racer_py[i] = new_py;
            } else {
                racer_vy[i] = (int8_t)0;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            }
        }
```

> **Behavioral note vs. original:** the original racer collision had NO map-bounds clamp (it relied on `racer_corners_passable` / `track_passable` returning blocked at the edge). Adding the helper’s in-bounds clamp is a STRICTER gate. On a well-authored track the racer never reaches a raw map edge (walls bound the road), so observable behavior is unchanged — but this is the one place the racer convergence is a tightening, not a pure refactor. The existing racer collision tests (`test_racer_4corner_blocks_when_corner_hits_wall`, `test_racer_slides_along_wall_on_y_collision`, `test_racer_wall_collision_zeroes_vx_and_gear`) use `active_map_w/h` large enough that the clamp does not fire — confirm they stay green.

- [ ] **Step 2: Run host tests — `test_racer` + `test_race_scenario` stay GREEN**

```powershell
make test
```
Expected: ALL suites green. The three racer collision tests above plus the full `test_race_scenario` lap/CP/ranking suite are the regression gate. Any red → STOP and re-examine the in-bounds clamp interaction; do NOT edit the regression tests.

- [ ] **Step 3: Build**

```powershell
make
```
`bank-post-build` + `make memory-check` auto-fire — confirm clean.

- [ ] **Step 4: Commit**

```powershell
git add src/racer.c
git commit -m "feat(racer): route wall-slide collision through vehicle_step_axis_x/y"
```

---

## Task 9: Verify build wiring (no Makefile edit expected)

**Files:**
- Read-only: `Makefile`

- [ ] **Step 1: Confirm wildcard discovery**

`Makefile` uses `TEST_LIB_SRC := $(filter-out src/main.c,$(wildcard src/*.c))` and `TEST_SRCS := $(wildcard tests/test_*.c)`. Confirm `src/vehicle_physics.c` and `tests/test_vehicle_physics.c` are picked up by running a clean test build:
```powershell
make clean && make test
```
Expected: a `build/test_vehicle_physics` binary is produced and all suites pass. If `vehicle_physics.c` is NOT compiled into the test lib (link errors), the wildcard failed — only then add it explicitly; otherwise no Makefile change is needed.

- [ ] **Step 2: No commit if no change.** If the Makefile required an edit, commit it:
```powershell
git add Makefile
git commit -m "build: wire vehicle_physics into test binaries"
```

---

## Task 10: Full regression gate + smoketest + PR

**Files:**
- Read-only verification; then push + PR.

- [ ] **Step 1: Clean host test run — ALL suites GREEN**

```powershell
make clean && make test
```
Expected: every `test_*` binary passes. The named regression gate: `test_player`, `test_racer`, `test_race_scenario` ALL green, plus the new `test_vehicle_physics`.

- [ ] **Step 2: Fetch + merge latest master (from the worktree dir)**

```powershell
git fetch origin && git merge origin/master
```
Resolve any conflicts (likely none — new module). Re-run `make clean && make test` if master moved.

- [ ] **Step 3: Clean ROM build**

```powershell
make clean && make
```
`bank-post-build` + `make memory-check` auto-fire — confirm no FAIL/ERROR (OAM/WRAM/VRAM/ROM-bank budgets PASS). Note: PR2 adds no sprites, so OAM is unchanged from baseline.

- [ ] **Step 4: Mandatory track2 ranking smoketest (per CLAUDE.md)**

Ask the user to confirm before launching. On confirmation, launch from the worktree directory:
```powershell
Start-Process java -ArgumentList '-jar','C:\Tools\Emulicious\Emulicious.jar','build/nuke-raider.gb'
```
Drive Track 2 (the multi-racer track) and confirm:
- Player movement, wall-slide, sand/oil/boost feel **identical** to pre-PR (collision convergence regression check).
- Enemy racers still drive their waypoint loops, slide along walls, and respect terrain.
- **P:1 / P:2 / P:3 race-position HUD is correct** across the race (the explicit ranking regression gate — racer movement/collision now flows through the shared helper).
- No sprite flicker / OAM corruption.

Ask the user to confirm it looks correct before proceeding.

- [ ] **Step 5: Push + PR (only after smoketest passes)**

```powershell
git push -u origin <branch>
gh pr create --title "Patrol PR2: shared vehicle_physics + player/racer convergence" --body @'
Extracts terrain physics + axis-separated slide collision into a shared `vehicle_physics` module (bank 255) and FULLY converges both player and racer onto it — terrain AND collision.

- New `src/vehicle_physics.c`/`.h`: split physics API — `vehicle_apply_friction` (pre-accel), `vehicle_apply_boost_clamp` (post-accel), `vehicle_apply_physics` (gearless convenience = friction then boost_clamp, for PR4's patrol caller) + `vehicle_step_axis_x/y`.
- `player.c`: terrain physics converged via `vehicle_apply_friction` → inline gear accel → `vehicle_apply_boost_clamp` (byte-identical); wall-slide collision routed through `vehicle_step_axis_x/y`; directional hitbox + ram/damage/gear-reset/SFX wrapper preserved.
- `racer.c`: same split terrain convergence (racer gear accel inline between the two helpers); wall-slide collision routed through the shared helper; dir-specific gate preserved.
- New `tests/test_vehicle_physics.c` covering each physics function separately + composition; regression gate: `test_player`, `test_racer`, `test_race_scenario` all green.
- The gear-accel interleaving is handled by splitting the helper at the friction/accel and accel/boost seams, so terrain convergence is full and byte-identical (no deferral).

Smoketest: Track 2 P:1/P:2/P:3 HUD verified correct; player/racer movement unchanged.

Part of #144

🤖 Generated with [Claude Code](https://claude.com/claude-code)
'@
```

- [ ] **Step 6: After merge, confirm the PR shows `Part of #144`.** (Issue #144 is the umbrella; it is NOT auto-closed by this PR — PR4 closes it.)

---

## Self-Review

### Spec-coverage table (PR2 requirements)

| PR2 spec item | Task(s) | Status |
|---------------|---------|--------|
| New `src/vehicle_physics.c` + `.h`, bank 255 autobank | 1, 2, 4 | Covered |
| `vehicle_apply_friction(vx*,vy*,terrain,gas,dir)` — pre-accel friction extracted | 4 | Covered |
| `vehicle_apply_boost_clamp(vx*,vy*,terrain,max_speed)` — post-accel boost+clamp extracted | 4 | Covered |
| `vehicle_apply_physics(...)` — gearless convenience = friction then boost_clamp (PR4 patrol contract preserved) | 4 | Covered |
| `vehicle_step_axis_x(px,py,vx)` — in-bounds + slide, `active_map_w` | 4 | Covered |
| `vehicle_step_axis_y(px,py,vy)` — in-bounds + slide, `active_map_h` | 4 | Covered |
| player.c: terrain via `vehicle_apply_friction` → inline accel → `vehicle_apply_boost_clamp`, byte-identical | 5 | Covered (FULL terrain convergence) |
| player.c: X/Y collision via `vehicle_step_axis_x/y` + ram/damage/gear/SFX wrapper, byte-identical | 6 | Covered |
| racer.c: terrain via `vehicle_apply_friction` → inline accel → `vehicle_apply_boost_clamp` | 7 | Covered (FULL terrain convergence) |
| racer.c: move via `vehicle_step_axis_x/y` instead of direct px/py writes | 8 | Covered |
| `tests/test_vehicle_physics.c`: friction (SAND doubles/OIL), boost_clamp (delta+clamp), convenience composition, slide block, in-bounds clamp | 3 | Covered |
| `bank-manifest.json`: add `vehicle_physics.c` bank 255 | 1 | Covered |
| Wire `vehicle_physics.c` into test build | 9 | Covered (wildcard auto-discovery; verified, no edit) |
| Regression: `test_player`, `test_racer`, `test_race_scenario` green | 6, 8, 10 | Covered |
| track2 P:1/P:2/P:3 HUD smoketest before merge | 10 | Covered |

### Placeholder scan

No `TODO`, `TBD`, `placeholder`, or `similar to` stand-ins. The only `...` markers are the explicit `...gear shift continues unchanged...` elisions in the player/racer BEFORE/AFTER blocks (Tasks 5, 7), which point at the existing, unchanged gear-shift code below the edited region — they are not omitted new code. Every other BEFORE/AFTER block is complete and copy-pasteable.

### Type-consistency vs. canonical signatures

| Canonical signature (from task brief) | Used in plan | Match |
|---|---|---|
| `void vehicle_apply_friction(int8_t *vx, int8_t *vy, uint8_t terrain, uint8_t gas, uint8_t dir) BANKED` | header Task 2, impl Task 4, tests Task 3, callers Tasks 5/7 | Exact |
| `void vehicle_apply_boost_clamp(int8_t *vx, int8_t *vy, uint8_t terrain, uint8_t max_speed) BANKED` | header Task 2, impl Task 4, tests Task 3, callers Tasks 5/7 | Exact |
| `void vehicle_apply_physics(int8_t *vx, int8_t *vy, uint8_t terrain, uint8_t gas, uint8_t dir, uint8_t max_speed) BANKED` | header Task 2, impl Task 4 (= friction then boost_clamp), tests Task 3; PR4 patrol caller | Exact |
| `int16_t vehicle_step_axis_x(int16_t px, int16_t py, int8_t vx) BANKED` | header Task 2, impl Task 4, callers Tasks 6/8 | Exact |
| `int16_t vehicle_step_axis_y(int16_t px, int16_t py, int8_t vy) BANKED` | header Task 2, impl Task 4, callers Tasks 6/8 | Exact |

No renames. `TileType`/terrain passed as `uint8_t` (TileType is `typedef uint8_t`). `dir` is `uint8_t` (not the 16-bit enum), per SDCC constraint.

### Regression risk + mitigation

1. **Player collision not byte-identical (highest risk).** The helper's non-directional 16×16 corner check is ANDed with the player's directional `corners_passable`. If `veh_corners_passable` ever blocks a position the directional check would allow, the player gets stuck where it previously moved. **Mitigation:** the directional hitbox points all lie within the same [0,15] box the 4 corners bound, so the directional check is the binding (laxer-or-equal where it matters) gate; `test_player`'s hitbox/diagonal-slide/wall-block/clamp tests (Task 6 Step 3) are the proof. If any go red, the AND-gate is not equivalent — the fallback is to revert to the original inline check (keep the helper for patrol-only use).

2. **Racer in-bounds clamp is a tightening.** The original racer collision had no map-bounds clamp; the helper adds one. **Mitigation:** documented in Task 8; the existing racer collision tests use map dims where the clamp never fires, and Track 2 walls bound the road before the raw edge. Verified by `test_racer` + `test_race_scenario` + the track2 HUD smoketest.

3. **Terrain-math convergence is FULL for both player and racer (split API).** The physics helper is split at the friction/accel and accel/boost seams (`vehicle_apply_friction` + `vehicle_apply_boost_clamp`), so each caller drops its unchanged gear accel into the gap and the friction→accel→boost→clamp ordering is reproduced exactly — no double-clamp, no deferral. The gear-bearing callers (player Task 5, racer Task 7) use the two split functions; the gearless `vehicle_apply_physics` convenience composes them for PR4's patrol caller, which has no accel. **Mitigation:** byte-identical proof is `test_player` (Task 5), `test_racer` + `test_race_scenario` (Task 7), the per-function tests in `test_vehicle_physics` (Task 3) including the composition tests that pin `vehicle_apply_physics == friction then boost_clamp`, and the track2 P:1/P:2/P:3 HUD smoketest. **The one subtle point to verify is the gear-reset-on-oil hoist** (moved out of the friction `else if` to its own `if (terrain == TILE_OIL)`): it writes only gear state, never velocity, so it is order-independent of the friction math — confirmed byte-identical by the green regression suites. No follow-up issue needed; terrain convergence is complete in this PR.

4. **Race ranking regression (the named gate).** Racer movement now flows through the shared terrain physics (`vehicle_apply_friction` + `vehicle_apply_boost_clamp`) AND the shared collision helper; a subtle friction/slide difference could desync lap/checkpoint timing and corrupt P:1/P:2/P:3. **Mitigation:** `test_race_scenario` (lap/CP/position across boundaries) stays green in CI, AND the mandatory manual track2 P:1/P:2/P:3 HUD smoketest (Task 10 Step 4) before any push.
