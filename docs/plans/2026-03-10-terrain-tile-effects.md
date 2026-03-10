# Terrain Tile Effects Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add sand/oil/boost terrain tiles managed in Tiled that affect car velocity via physics modifiers.

**Architecture:** Extend the Tiled tileset with 3 new tile types (sand GID 4, oil GID 5, boost GID 6); place them in the TMX at known track positions; regenerate `track_map.c`; implement `track_tile_type()` as a ROM LUT lookup (tile index → TileType); extract `player_apply_physics(buttons, terrain)` as a testable function; refactor `player_update()` to query terrain and delegate to `player_apply_physics()`.

**Tech Stack:** SDCC/GBDK-2020, Unity (host-side tests via gcc), Python 3 (PNG + TMX tooling), Tiled 1.10.

---

## Already Done (merged in master, do NOT re-implement)

- `PLAYER_ACCEL 1`, `PLAYER_FRICTION 1`, `PLAYER_MAX_SPEED 6` in `src/config.h`
- `static int8_t vx, vy` state in `src/player.c`
- `player_get_vx()`, `player_get_vy()` in `src/player.h` + `src/player.c`
- Full road-only velocity model in `player_update()` (accel, friction, clamp, wall zeroing)
- `tests/test_player_physics.c` — 6 tests, all passing
- Player sprite is now 8×16 (two OAM slots), `src/player_sprite.c`
- ISR stubs in `tests/mocks/gb/gb.h` (NONBANKED, add_VBL, etc.)

---

## Key SDCC / GBDK Constraints

- **No `typedef enum` for TileType** — SDCC makes enums 16-bit. Use `typedef uint8_t TileType` + `#define`.
- **`static const uint8_t __code lut[]`** — `__code` keeps the LUT in ROM. Without it, SDCC silently copies it to WRAM at boot.
- **`__code` is SDCC-only** — must be stubbed `#define __code` in the gcc mock (Task 2).
- **Cast int8_t arithmetic** — always cast results with `(int8_t)(...)` to suppress SDCC promotion warnings.
- **PLAYER_MAX_SPEED = 6** — boost/sand tests must use this value, not 3.

## Tile Index Reference

After this plan, tile indices in `track_map[]` map as follows:

| tile_id | Tiled GID | Name          | TileType   |
|---------|-----------|---------------|------------|
| 0       | 1         | wall/off-road | TILE_WALL  |
| 1       | 2         | road          | TILE_ROAD  |
| 2       | 3         | center dashes | TILE_ROAD  |
| 3       | 4         | sand          | TILE_SAND  |
| 4       | 5         | oil puddle    | TILE_OIL   |
| 5       | 6         | boost pad     | TILE_BOOST |

## Test Coordinate Reference

After the TMX is updated (Task 4), these world coords map to specific tile types:

| world (x, y) | tile col/row | tile_id | TileType  |
|-------------|--------------|---------|-----------|
| (80, 80)    | (10, 10)     | 1       | TILE_ROAD |
| (24, 80)    | (3, 10)      | 0       | TILE_WALL |
| (72, 0)     | (9, 0)       | 2       | TILE_ROAD |
| (48, 80)    | (6, 10)      | 3       | TILE_SAND |
| (88, 160)   | (11, 20)     | 4       | TILE_OIL  |
| (88, 240)   | (11, 30)     | 5       | TILE_BOOST|

---

## Task 1: Add Terrain Constants to config.h

**Files:**
- Modify: `src/config.h`

**Step 1: Add terrain constants**

In `src/config.h`, append before `#endif`:

```c
/* Terrain physics modifiers */
#define TERRAIN_SAND_FRICTION_MUL  2u   /* friction steps applied on sand (double) */
#define TERRAIN_BOOST_DELTA        2u   /* vy kick per frame on boost pad */
```

**Step 2: Verify tests still pass**

```
make test
```
Expected: all tests pass.

**Step 3: Commit**

```bash
cd /home/mathdaman/code/gmb-wasteland-racer/.worktrees/terrain-effects
git add src/config.h
git commit -m "feat: add terrain constants to config.h (sand friction mul, boost delta)"
```

---

## Task 2: Add `__code` Mock to Test Headers

**Files:**
- Modify: `tests/mocks/gb/gb.h`

**Step 1: Add SDCC `__code` stub**

Immediately after `#include <stdint.h>` in `tests/mocks/gb/gb.h`:

```c
/* SDCC ROM-placement qualifier — noop on gcc */
#ifndef __code
#define __code
#endif
```

**Step 2: Verify tests still pass**

```
make test
```
Expected: all tests pass.

**Step 3: Commit**

```bash
git add tests/mocks/gb/gb.h
git commit -m "test: stub __code qualifier for gcc host-side compilation"
```

---

## Task 3: Extend Tileset PNG with Terrain Tiles

**Files:**
- Create: `tools/gen_tileset.py`
- Modify: `assets/maps/tileset.png` (16×8 → 48×8, 2 tiles → 6 tiles)
- Modify: `assets/maps/track.tsx` (tilecount 3→6, columns 3→6, width 24→48)

**Background:** `tileset.png` is 16×8 (2 tiles). `track.tsx` erroneously declares width=24 (3 tiles) — this task fixes the mismatch and adds tiles 3–5.

**Tile pixel patterns** (GB palette indices: 0=white, 1=light-grey, 2=dark-grey, 3=black):

```
tile 0 (wall):    solid 2 (dark-grey)
tile 1 (road):    solid 1 (light-grey)
tile 2 (dashes):  solid 3 (black)
tile 3 (sand):    checkerboard 1/2, alternating per pixel and row
tile 4 (oil):     solid 3, except a 4×2 dark-grey patch in the center
tile 5 (boost):   horizontal stripes: even rows=0, odd rows=1
```

**Step 1: Create `tools/gen_tileset.py`**

```python
#!/usr/bin/env python3
"""Generate the 6-tile Wasteland Racer tileset PNG (48×8, RGB).

Run: python3 tools/gen_tileset.py assets/maps/tileset.png
"""
import struct
import zlib
import sys

PALETTE = [
    (255, 255, 255),  # 0 = white
    (170, 170, 170),  # 1 = light-grey
    (85,  85,  85),   # 2 = dark-grey
    (0,   0,   0),    # 3 = black
]

def make_tile(fn):
    return [[fn(r, c) for c in range(8)] for r in range(8)]

TILES = [
    make_tile(lambda r, c: 2),                                          # 0: wall
    make_tile(lambda r, c: 1),                                          # 1: road
    make_tile(lambda r, c: 3),                                          # 2: center dashes
    make_tile(lambda r, c: 1 + ((r + c) % 2)),                         # 3: sand checkerboard
    make_tile(lambda r, c: 2 if (2 <= r <= 4 and 2 <= c <= 5) else 3), # 4: oil puddle
    make_tile(lambda r, c: r % 2),                                      # 5: boost stripes
]

WIDTH  = 8 * len(TILES)  # 48
HEIGHT = 8

def write_chunk(ctype, data):
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + ctype + data + struct.pack('>I', crc)

ihdr = struct.pack('>IIBBBBB', WIDTH, HEIGHT, 8, 2, 0, 0, 0)

raw = b''
for row in range(HEIGHT):
    raw += b'\x00'  # filter byte = None
    for tile in TILES:
        for col in range(8):
            raw += bytes(PALETTE[tile[row][col]])

out = (b'\x89PNG\r\n\x1a\n' +
       write_chunk(b'IHDR', ihdr) +
       write_chunk(b'IDAT', zlib.compress(raw)) +
       write_chunk(b'IEND', b''))

path = sys.argv[1] if len(sys.argv) > 1 else 'assets/maps/tileset.png'
with open(path, 'wb') as f:
    f.write(out)
print(f"Wrote {WIDTH}x{HEIGHT} PNG ({len(TILES)} tiles) to {path}")
```

**Step 2: Run the generator**

```bash
python3 tools/gen_tileset.py assets/maps/tileset.png
```
Expected: `Wrote 48x8 PNG (6 tiles) to assets/maps/tileset.png`

**Step 3: Verify png_to_tiles.py can parse it**

```bash
python3 tools/png_to_tiles.py assets/maps/tileset.png /tmp/track_tiles_test.c track_tile_data
cat /tmp/track_tiles_test.c
```
Expected: 6 tile entries, no errors.

**Step 4: Update `assets/maps/track.tsx`**

Replace the full file content with:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" tiledversion="1.10.0"
         name="track" tilewidth="8" tileheight="8"
         spacing="0" margin="0" tilecount="6" columns="6">
 <image source="tileset.png" width="48" height="8"/>
</tileset>
```

**Step 5: Commit**

```bash
git add tools/gen_tileset.py assets/maps/tileset.png assets/maps/track.tsx
git commit -m "feat: extend tileset to 6 tiles — add sand/oil/boost graphics"
```

---

## Task 4: Place Terrain Tiles in Tiled Map + Regenerate C Sources

**Files:**
- Modify: `assets/maps/track.tmx`
- Regenerate: `src/track_map.c`, `src/track_tiles.c`

**Terrain tile placements** (GID values; tile_id = GID − 1):
- **Sand (GID 4 → tile_id 3):** row 10, cols 6–7 → world x=48–63, y=80–87
- **Oil (GID 5 → tile_id 4):** row 20, col 11 → world x=88, y=160–167
- **Boost (GID 6 → tile_id 5):** row 30, col 11 → world x=88, y=240–247

**Step 1: Edit `assets/maps/track.tmx` — row 10**

Find row 10 in the CSV (11th data line). Before:
```
1,1,1,1,2,2,2,2,2,3,3,2,2,2,2,2,1,1,1,1,
```
After (cols 6,7: GID 2 → GID 4):
```
1,1,1,1,2,2,4,4,2,3,3,2,2,2,2,2,1,1,1,1,
```

**Step 2: Edit `assets/maps/track.tmx` — row 20**

Before:
```
1,1,1,1,2,2,2,2,2,3,3,2,2,2,2,2,1,1,1,1,
```
After (col 11: GID 2 → GID 5):
```
1,1,1,1,2,2,2,2,2,3,3,5,2,2,2,2,1,1,1,1,
```

**Step 3: Edit `assets/maps/track.tmx` — row 30**

Before:
```
1,1,1,1,2,2,2,2,2,3,3,2,2,2,2,2,1,1,1,1,
```
After (col 11: GID 2 → GID 6):
```
1,1,1,1,2,2,2,2,2,3,3,6,2,2,2,2,1,1,1,1,
```

**Step 4: Regenerate C sources**

```bash
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
python3 tools/png_to_tiles.py assets/maps/tileset.png src/track_tiles.c track_tile_data
```

**Step 5: Verify new tile_ids in track_map.c**

```bash
grep "row 10\|row 20\|row 30" src/track_map.c
```
Expected (tile_id = GID − 1):
```
/* row 10 */ 0,0,0,0,1,1,3,3,1,2,2,1,1,1,1,1,0,0,0,0,
/* row 20 */ 0,0,0,0,1,1,1,1,1,2,2,4,1,1,1,1,0,0,0,0,
/* row 30 */ 0,0,0,0,1,1,1,1,1,2,2,5,1,1,1,1,0,0,0,0,
```

**Step 6: Verify all existing tests still pass**

```
make test
```
Expected: all pass. (Sand tile_id=3, oil=4, boost=5 are all != 0, so still "passable" via `track_passable`. Existing passability tests hit different cols, unaffected.)

**Step 7: Commit**

```bash
git add assets/maps/track.tmx src/track_map.c src/track_tiles.c
git commit -m "feat: place sand/oil/boost tiles in track map (rows 10/20/30)"
```

---

## Task 5: TDD `TileType` + `track_tile_type_from_index()` + `track_tile_type()`

**Files:**
- Modify: `src/track.h`
- Modify: `tests/test_track.c`
- Modify: `src/track.c`

**Step 1: Write failing tests — append to `tests/test_track.c`**

Add before `int main(void)`:

```c
/* --- TileType: track_tile_type_from_index -------------------------------- */

void test_tile_type_from_index_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type_from_index(0));
}
void test_tile_type_from_index_road(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(1));
}
void test_tile_type_from_index_dashes_is_road(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(2));
}
void test_tile_type_from_index_sand(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_SAND, track_tile_type_from_index(3));
}
void test_tile_type_from_index_oil(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_OIL, track_tile_type_from_index(4));
}
void test_tile_type_from_index_boost(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_BOOST, track_tile_type_from_index(5));
}
void test_tile_type_from_index_unknown_defaults_to_road(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(99));
}

/* --- TileType: track_tile_type (world coords, uses updated track_map) ---- */

void test_track_tile_type_road(void) {
    /* tile (10,10) = tile_id 1 */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type(80, 80));
}
void test_track_tile_type_wall(void) {
    /* tile (3,10) = tile_id 0 */
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(24, 80));
}
void test_track_tile_type_dashes_is_road(void) {
    /* tile (9,0) = tile_id 2 */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type(72, 0));
}
void test_track_tile_type_sand(void) {
    /* tile (6,10) = tile_id 3 — placed in Task 4 */
    TEST_ASSERT_EQUAL_UINT8(TILE_SAND, track_tile_type(48, 80));
}
void test_track_tile_type_oil(void) {
    /* tile (11,20) = tile_id 4 — placed in Task 4 */
    TEST_ASSERT_EQUAL_UINT8(TILE_OIL, track_tile_type(88, 160));
}
void test_track_tile_type_boost(void) {
    /* tile (11,30) = tile_id 5 — placed in Task 4 */
    TEST_ASSERT_EQUAL_UINT8(TILE_BOOST, track_tile_type(88, 240));
}
void test_track_tile_type_oob_x_is_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(160, 80));
}
void test_track_tile_type_negative_is_wall(void) {
    TEST_ASSERT_EQUAL_UINT8(TILE_WALL, track_tile_type(-1, 80));
}
```

Add to `main()`:

```c
RUN_TEST(test_tile_type_from_index_wall);
RUN_TEST(test_tile_type_from_index_road);
RUN_TEST(test_tile_type_from_index_dashes_is_road);
RUN_TEST(test_tile_type_from_index_sand);
RUN_TEST(test_tile_type_from_index_oil);
RUN_TEST(test_tile_type_from_index_boost);
RUN_TEST(test_tile_type_from_index_unknown_defaults_to_road);
RUN_TEST(test_track_tile_type_road);
RUN_TEST(test_track_tile_type_wall);
RUN_TEST(test_track_tile_type_dashes_is_road);
RUN_TEST(test_track_tile_type_sand);
RUN_TEST(test_track_tile_type_oil);
RUN_TEST(test_track_tile_type_boost);
RUN_TEST(test_track_tile_type_oob_x_is_wall);
RUN_TEST(test_track_tile_type_negative_is_wall);
```

**Step 2: Run tests — expect FAIL**

```
make test
```
Expected: compilation error — `TileType`, `TILE_ROAD`, `track_tile_type_from_index` undeclared.

**Step 3: Add TileType to `src/track.h`**

Add after `#include "config.h"`:

```c
/* Terrain tile types — uint8_t, NOT typedef enum (SDCC makes enums 16-bit) */
typedef uint8_t TileType;
#define TILE_WALL   0u
#define TILE_ROAD   1u
#define TILE_SAND   2u
#define TILE_OIL    3u
#define TILE_BOOST  4u

TileType track_tile_type_from_index(uint8_t tile_idx);
TileType track_tile_type(int16_t world_x, int16_t world_y);
```

**Step 4: Implement in `src/track.c`**

Add after the `#include` block:

```c
/* Tile index → TileType lookup table
 * __code keeps this in ROM — without it SDCC copies it to WRAM at boot */
#define TILE_LUT_LEN 6u
static const uint8_t __code tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
};

TileType track_tile_type_from_index(uint8_t tile_idx) {
    if (tile_idx >= TILE_LUT_LEN) return TILE_ROAD;
    return (TileType)tile_type_lut[tile_idx];
}

TileType track_tile_type(int16_t world_x, int16_t world_y) {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return TILE_WALL;
    tx = (uint8_t)((uint16_t)world_x >> 3u);
    ty = (uint8_t)((uint16_t)world_y >> 3u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return TILE_WALL;
    return track_tile_type_from_index(track_map[(uint16_t)ty * MAP_TILES_W + tx]);
}
```

**Step 5: Run tests — expect PASS**

```
make test
```
Expected: all tests pass, including the 15 new tile type tests.

**Step 6: Commit**

```bash
git add src/track.h src/track.c tests/test_track.c
git commit -m "feat: add TileType + track_tile_type_from_index/track_tile_type with ROM LUT"
```

---

## Task 6: TDD Terrain Physics — Extract `player_apply_physics` + Refactor `player_update`

**Files:**
- Modify: `src/player.h`
- Modify: `src/player.c`
- Create: `tests/test_terrain_physics.c`

### Physics model

The existing `player_update()` road-only model (accel OR friction, exclusive) becomes:

1. **Determine friction steps per axis:**
   - Sand: `PLAYER_FRICTION × TERRAIN_SAND_FRICTION_MUL` — always applied even while pressing
   - Oil: 0 (coast, no friction)
   - Road / Boost: `PLAYER_FRICTION` — only when that axis button is NOT held
2. **Apply friction** (loop, one step at a time, clamp at 0)
3. **Apply input acceleration** (disabled on oil)
4. **Apply boost kick** if `terrain == TILE_BOOST`: `vy -= TERRAIN_BOOST_DELTA`
5. **Clamp** `vx`, `vy` to `±PLAYER_MAX_SPEED`

Verification that road behavior is unchanged for existing `test_player_physics.c` tests:
- Road + pressing: friction=0, accel +1/frame → same as before ✓
- Road + not pressing (vx>0): friction=1 step → vx-=1, clamped ≥ 0 → same as before ✓

### Sub-task 6a: Write failing tests

**Step 1: Create `tests/test_terrain_physics.c`**

```c
/* tests/test_terrain_physics.c — AC2/AC3/AC4 terrain modifier tests */
#include "unity.h"
#include <gb/gb.h>
#include "../src/input.h"
#include "../src/config.h"
#include "player.h"
#include "track.h"

void setUp(void) {
    input = 0;
    prev_input = 0;
    mock_vram_clear();
    camera_init(88, 720);
    player_init();  /* resets px, py, vx=0, vy=0 */
}
void tearDown(void) {}

/* AC2: Sand produces lower velocity than road after N presses */
void test_sand_produces_lower_vx_than_road(void) {
    uint8_t i;
    int8_t road_vx, sand_vx;

    for (i = 0; i < (uint8_t)(PLAYER_MAX_SPEED + 2u); i++) {
        player_apply_physics(J_RIGHT, TILE_ROAD);
    }
    road_vx = player_get_vx();

    player_reset_vel();

    for (i = 0; i < (uint8_t)(PLAYER_MAX_SPEED + 2u); i++) {
        player_apply_physics(J_RIGHT, TILE_SAND);
    }
    sand_vx = player_get_vx();

    /* road_vx > sand_vx — TEST_ASSERT_GREATER_THAN_INT8(threshold, actual) */
    TEST_ASSERT_GREATER_THAN_INT8(sand_vx, road_vx);
}

/* AC3: Oil does not increase speed beyond entry velocity */
void test_oil_does_not_increase_vx(void) {
    int8_t entry_vx;
    uint8_t i;

    /* Build up speed on road */
    player_apply_physics(J_RIGHT, TILE_ROAD);
    player_apply_physics(J_RIGHT, TILE_ROAD);
    entry_vx = player_get_vx();   /* 2 */

    /* On oil: input ignored, no friction */
    for (i = 0; i < 4u; i++) {
        player_apply_physics(J_RIGHT, TILE_OIL);
    }

    TEST_ASSERT_TRUE(player_get_vx() <= entry_vx);
}

/* AC3: Oil does not decelerate (coasts) */
void test_oil_preserves_velocity_without_input(void) {
    int8_t entry_vx;

    player_apply_physics(J_RIGHT, TILE_ROAD);
    player_apply_physics(J_RIGHT, TILE_ROAD);
    entry_vx = player_get_vx();   /* 2 */

    /* No input on oil — should not decelerate */
    player_apply_physics(0, TILE_OIL);
    player_apply_physics(0, TILE_OIL);

    TEST_ASSERT_EQUAL_INT8(entry_vx, player_get_vx());
}

/* AC4: Boost increases vy in the upward direction (negative) */
void test_boost_increases_vy_upward(void) {
    /* No input, just boost tile — vy should go negative */
    player_apply_physics(0, TILE_BOOST);
    TEST_ASSERT_LESS_THAN_INT8(0, player_get_vy());
}

/* AC4: Boost cannot exceed max speed */
void test_boost_capped_at_max_speed(void) {
    uint8_t i;
    /* Pressing J_UP + boost each frame maximises upward velocity */
    for (i = 0; i < 10u; i++) {
        player_apply_physics(J_UP, TILE_BOOST);
    }
    TEST_ASSERT_EQUAL_INT8(-(int8_t)PLAYER_MAX_SPEED, player_get_vy());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_sand_produces_lower_vx_than_road);
    RUN_TEST(test_oil_does_not_increase_vx);
    RUN_TEST(test_oil_preserves_velocity_without_input);
    RUN_TEST(test_boost_increases_vy_upward);
    RUN_TEST(test_boost_capped_at_max_speed);
    return UNITY_END();
}
```

**Step 2: Run tests — expect FAIL**

```
make test
```
Expected: compilation error — `player_apply_physics` and `player_reset_vel` undeclared.

### Sub-task 6b: Implement

**Step 3: Add declarations to `src/player.h`**

Add after `player_get_vy()`:

```c
#include "track.h"

void player_reset_vel(void);
void player_apply_physics(uint8_t buttons, TileType terrain);
```

**Step 4: Implement `player_reset_vel` and `player_apply_physics` in `src/player.c`**

Add `#include "config.h"` if not already present (it already is).

Add after `player_get_vy()`:

```c
void player_reset_vel(void) {
    vx = 0;
    vy = 0;
}

void player_apply_physics(uint8_t buttons, TileType terrain) {
    uint8_t i;
    uint8_t fric_x;
    uint8_t fric_y;

    /* Step 1: determine friction */
    if (terrain == TILE_SAND) {
        fric_x = (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = fric_x;
    } else if (terrain == TILE_OIL) {
        fric_x = 0;
        fric_y = 0;
    } else {
        /* Road / Boost: friction only on unpressed axis */
        fric_x = (buttons & (J_LEFT | J_RIGHT)) ? 0u : (uint8_t)PLAYER_FRICTION;
        fric_y = (buttons & (J_UP   | J_DOWN))  ? 0u : (uint8_t)PLAYER_FRICTION;
    }

    /* Step 2: apply X friction */
    for (i = 0; i < fric_x; i++) {
        if      (vx > 0) vx = (int8_t)(vx - 1);
        else if (vx < 0) vx = (int8_t)(vx + 1);
    }

    /* Step 3: apply Y friction */
    for (i = 0; i < fric_y; i++) {
        if      (vy > 0) vy = (int8_t)(vy - 1);
        else if (vy < 0) vy = (int8_t)(vy + 1);
    }

    /* Step 4: input acceleration (disabled on oil) */
    if (terrain != TILE_OIL) {
        if (buttons & J_LEFT)  vx = (int8_t)(vx - (int8_t)PLAYER_ACCEL);
        if (buttons & J_RIGHT) vx = (int8_t)(vx + (int8_t)PLAYER_ACCEL);
        if (buttons & J_UP)    vy = (int8_t)(vy - (int8_t)PLAYER_ACCEL);
        if (buttons & J_DOWN)  vy = (int8_t)(vy + (int8_t)PLAYER_ACCEL);
    }

    /* Step 5: boost kick (upward = negative vy) */
    if (terrain == TILE_BOOST) {
        vy = (int8_t)(vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    /* Step 6: clamp to ±PLAYER_MAX_SPEED */
    if (vx >  (int8_t)PLAYER_MAX_SPEED) vx =  (int8_t)PLAYER_MAX_SPEED;
    if (vx < -(int8_t)PLAYER_MAX_SPEED) vx = -(int8_t)PLAYER_MAX_SPEED;
    if (vy >  (int8_t)PLAYER_MAX_SPEED) vy =  (int8_t)PLAYER_MAX_SPEED;
    if (vy < -(int8_t)PLAYER_MAX_SPEED) vy = -(int8_t)PLAYER_MAX_SPEED;
}
```

**Step 5: Refactor `player_update()` to call `player_apply_physics`**

Replace the existing velocity blocks in `player_update()` with:

```c
void player_update(void) {
    int16_t new_px;
    int16_t new_py;
    TileType terrain;

    /* Query terrain at player centre (4px = centre of 8-wide hitbox) */
    terrain = track_tile_type((int16_t)(px + 4), (int16_t)(py + 4));
    player_apply_physics(input, terrain);

    /* Apply X velocity — zero on wall/edge collision */
    new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 && new_px <= 159 && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        vx = 0;
    }

    /* Apply Y velocity — zero on wall/edge collision */
    new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= (int16_t)cam_y &&
        new_py <= (int16_t)(cam_y + 143u) &&
        corners_passable(px, new_py)) {
        py = new_py;
    } else {
        vy = 0;
    }
}
```

> **Note on `input`:** `player_update()` reads the `input` global from `input.h`, same as before. All existing `test_player_physics.c` tests set `input = J_XXX` and call `player_update()` — they are unaffected since road physics is identical.

**Step 6: Run all tests — expect all pass**

```
make test
```
Expected: all suites pass, including both `test_player_physics` and `test_terrain_physics`.

> **Why existing tests still pass:**
> Player positions in `test_player_physics.c` are at (88,720) and (136,720) — both in row 90 (road). `player_apply_physics(input, TILE_ROAD)` produces identical velocity results to the old inline road-only code.

**Step 7: Commit**

```bash
git add src/player.h src/player.c tests/test_terrain_physics.c
git commit -m "feat: terrain physics — sand/oil/boost modifiers via player_apply_physics"
```

---

## Task 7: Build Verification + Smoketest

**Step 1: Build the ROM**

Use the `/build` skill or:

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: `build/wasteland-racer.gb` produced, 0 errors (ignore "EVELYN" optimizer notice).

**Step 2: Launch smoketest in Emulicious**

```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb &
```

Ask the user to confirm:
- Driving on open road: smooth acceleration, gradual deceleration on release
- Driving over the sand patch (visible at ~row 10): feels sluggish, car barely builds speed
- Driving over the boost pad (row 30): noticeable upward velocity burst
- Driving over the oil puddle (row 20): car coasts, ignores steering input

**Step 3: Create PR**

```bash
gh pr create \
  --title "feat: terrain tile effects — sand/oil/boost velocity modifiers (#49)" \
  --body "$(cat <<'EOF'
## Summary
- Adds `TileType` + `track_tile_type()` / `track_tile_type_from_index()` with ROM LUT in `track.c`
- Extracts `player_apply_physics(buttons, terrain)` from `player_update()` — testable in isolation
- Sand: double friction always → max vx=1 vs road max=6; Oil: no accel/friction (coast); Boost: upward vy kick of TERRAIN_BOOST_DELTA per frame, clamped to PLAYER_MAX_SPEED
- Terrain tiles (sand/oil/boost) placed in Tiled map at rows 10/20/30, regenerated into C via pipeline

## Test plan
- [ ] `make test` passes (all suites including new test_terrain_physics, existing test_player_physics unchanged)
- [ ] `GBDK_HOME=~/gbdk make` builds without errors
- [ ] Smoketest: sand sluggish, boost burst visible, oil coasting confirmed

Closes #49

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
