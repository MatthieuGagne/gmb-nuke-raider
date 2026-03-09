# 4-Screen Oval Track with Scrolling Camera — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the oval track from a single fixed 20×18-tile screen to a 40×36-tile world with a player-centered scrolling camera backed by a VRAM ring-buffer tile streamer.

**Architecture:** The GB background tilemap (32×32 tiles = 256×256 px) acts as a ring buffer; world tile `(tx, ty)` is always stored at VRAM slot `(tx % 32, ty % 32)`. `camera_update()` computes a clamped scroll position, writes any new tile columns/rows that just entered the viewport, then calls `move_bkg()`. Player position is stored in world pixel coordinates (`int16_t`); the sprite hardware position is computed as `world_pos - cam_pos + hw_offset` each render frame.

**Tech Stack:** GBDK-2020 (`~/gbdk`), SDCC, Unity (host-side tests via `gcc`), `make test` / `GBDK_HOME=~/gbdk make`

---

## Map Design Reference

World: 40 cols × 36 rows = 320×288 px. Tile row type key:

| Row range | Type | Pattern (40 tiles) |
|-----------|------|---------------------|
| 0–1, 34–35 | A (off) | `{0×40}` |
| 2–3, 32–33 | B (top/bottom straight) | `{0×8, 1×24, 0×8}` |
| 4–5, 30–31 | C (corner transition) | `{0×6, 1×28, 0×6}` |
| 6–29 | D (side straights) | `{0×4, 1×4, 0×24, 1×4, 0×4}` |

Track ring is 4 tiles wide throughout. Inner void = cols 8–31 in type-D rows.

Player start: world (160, 256) = tile (20, 32) — center of bottom straight.

Camera clamp:
- `cam_x ∈ [0, 160]` (MAP_PX_W 320 − screen 160)
- `cam_y ∈ [0, 144]` (MAP_PX_H 288 − screen 144)

---

## Task 1: Add `move_bkg` mock + track.h constants + track.h signature

**Files:**
- Modify: `tests/mocks/gb/gb.h`
- Modify: `src/track.h`

### Step 1: Add `move_bkg` to the mock

In `tests/mocks/gb/gb.h`, append before `#endif`:

```c
static inline void move_bkg(uint8_t x, uint8_t y) { (void)x; (void)y; }
```

### Step 2: Update `src/track.h`

Replace the entire file with:

```c
#ifndef TRACK_H
#define TRACK_H

#include <stdint.h>

/* World map dimensions */
#define MAP_TILES_W  40u
#define MAP_TILES_H  36u
#define MAP_PX_W     320u   /* MAP_TILES_W * 8 */
#define MAP_PX_H     288u   /* MAP_TILES_H * 8 */

void    track_init(void);
uint8_t track_passable(int16_t world_x, int16_t world_y);

#endif /* TRACK_H */
```

### Step 3: Run existing tests to confirm the break

```
make test
```

Expected: compile errors in `test_track.c` and `test_player.c` (wrong arg types to `track_passable`). This is the expected "red" state before we update tests and implementation.

### Step 4: Commit

```bash
git add tests/mocks/gb/gb.h src/track.h
git commit -m "feat: add move_bkg mock, add map dimension constants, update track_passable signature"
```

---

## Task 2: Rewrite `src/track.c`

**Files:**
- Modify: `src/track.c`

The new `track.c`:
- Keeps the same two tile graphics (off-track tile 0, road tile 1)
- Expands map to 40×36 using the row types defined above
- `track_init()` only loads tile graphics data + `SHOW_BKG` (tilemap loading moved to camera_init)
- `track_passable()` takes `int16_t` world coords, returns 0 for negative or out-of-bounds

Replace `src/track.c` entirely:

```c
#include <gb/gb.h>
#include "track.h"

/*
 * Tile 0: off-track (color index 2)  — 2bpp: low=0x00, high=0xFF
 * Tile 1: road surface (color index 1) — 2bpp: low=0xFF, high=0x00
 */
static const uint8_t track_tile_data[] = {
    /* Tile 0: off-track */
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    /* Tile 1: road */
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00
};

/*
 * 40×36 world tile map. 0=off-track, 1=road.
 * Row types (see plan):
 *   A: all zeros
 *   B: 8z 24o 8z   (top/bottom straight)
 *   C: 6z 28o 6z   (corner transition)
 *   D: 4z 4o 24z 4o 4z  (side straights)
 */
const uint8_t track_map[MAP_TILES_H * MAP_TILES_W] = {
    /* row 0  - A */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 1  - A */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 2  - B */ 0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,
    /* row 3  - B */ 0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,
    /* row 4  - C */ 0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,
    /* row 5  - C */ 0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,
    /* row 6  - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 7  - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 8  - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 9  - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 10 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 11 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 12 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 13 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 14 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 15 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 16 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 17 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 18 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 19 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 20 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 21 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 22 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 23 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 24 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 25 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 26 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 27 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 28 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 29 - D */ 0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,0,0,0,0,
    /* row 30 - C */ 0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,
    /* row 31 - C */ 0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,
    /* row 32 - B */ 0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,
    /* row 33 - B */ 0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,
    /* row 34 - A */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 35 - A */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
};

void track_init(void) {
    set_bkg_data(0, 2, track_tile_data);
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}

uint8_t track_passable(int16_t world_x, int16_t world_y) {
    if (world_x < 0 || world_y < 0) return 0u;
    uint8_t tx = (uint8_t)((uint16_t)world_x / 8u);
    uint8_t ty = (uint8_t)((uint16_t)world_y / 8u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return 0u;
    return track_map[(uint16_t)ty * MAP_TILES_W + tx] != 0u;
}
```

**Important:** `track_map` must be `const uint8_t` but NOT `static` — camera.c needs to access it for VRAM streaming. Declare it in `track.h` as `extern const uint8_t track_map[];`.

Add to `src/track.h` (after the `#define` block, before `track_init`):

```c
extern const uint8_t track_map[];
```

### Step 3: Verify it compiles (will fail tests — that's expected)

```
make test
```

Expected: compile errors because test_track.c uses old arg types. Proceed to Task 3.

### Step 4: Commit

```bash
git add src/track.c src/track.h
git commit -m "feat: expand track to 40x36 oval, update track_passable to world coords"
```

---

## Task 3: Rewrite `tests/test_track.c`

**Files:**
- Modify: `tests/test_track.c`

All tests now use world pixel coordinates. Verify against map design above before writing.

```c
#include "unity.h"
#include "track.h"

void setUp(void)    {}
void tearDown(void) {}

/* On-track: bottom straight, tile (20,32) = world (160,256) */
void test_track_passable_bottom_straight(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(160, 256));
}

/* On-track: top straight, tile (20,2) = world (160,16) */
void test_track_passable_top_straight(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(160, 16));
}

/* On-track: left side, tile (4,15) = world (32,120) */
void test_track_passable_left_side(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(32, 120));
}

/* On-track: right side, tile (34,15) = world (272,120) */
void test_track_passable_right_side(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(272, 120));
}

/* Off-track: outer corner, tile (0,0) = world (0,0) */
void test_track_passable_outer_corner(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(0, 0));
}

/* Off-track: inner void, tile (20,18) = world (160,144) - D-row center */
void test_track_passable_inner_void(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(160, 144));
}

/* Off-track: beyond map width */
void test_track_passable_out_of_bounds_x(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(320, 120));
}

/* Off-track: beyond map height */
void test_track_passable_out_of_bounds_y(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(160, 288));
}

/* Off-track: negative world coords */
void test_track_passable_negative_coords(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(-1, 120));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_track_passable_bottom_straight);
    RUN_TEST(test_track_passable_top_straight);
    RUN_TEST(test_track_passable_left_side);
    RUN_TEST(test_track_passable_right_side);
    RUN_TEST(test_track_passable_outer_corner);
    RUN_TEST(test_track_passable_inner_void);
    RUN_TEST(test_track_passable_out_of_bounds_x);
    RUN_TEST(test_track_passable_out_of_bounds_y);
    RUN_TEST(test_track_passable_negative_coords);
    return UNITY_END();
}
```

### Step 2: Run tests — expect test_track passes, test_player still fails

```
make test
```

Expected: `test_track` passes all 9 tests. `test_player` fails (old arg types to track_passable in player.c, plus type mismatch in player API). That's fine — proceed.

### Step 3: Commit

```bash
git add tests/test_track.c
git commit -m "test: rewrite test_track for 40x36 world coords"
```

---

## Task 4: Create `src/camera.h` and `src/camera.c`

**Files:**
- Create: `src/camera.h`
- Create: `src/camera.c`

### Step 1: Write `src/camera.h`

```c
#ifndef CAMERA_H
#define CAMERA_H

#include <stdint.h>

/* Current camera scroll position in world pixels.
 * cam_x ∈ [0, 160], cam_y ∈ [0, 144] — both fit safely in uint8_t. */
extern uint8_t cam_x;
extern uint8_t cam_y;

/* Call once when entering STATE_PLAYING (after track_init).
 * Preloads all world tiles into VRAM ring buffer and sets initial scroll. */
void camera_init(int16_t player_world_x, int16_t player_world_y);

/* Call every frame in STATE_PLAYING loop (after wait_vbl_done).
 * Centers camera on player, streams any new tile columns/rows into VRAM,
 * and calls move_bkg(). */
void camera_update(int16_t player_world_x, int16_t player_world_y);

#endif /* CAMERA_H */
```

### Step 2: Write `src/camera.c`

```c
#include <gb/gb.h>
#include "camera.h"
#include "track.h"

uint8_t cam_x;
uint8_t cam_y;

/* Camera clamp maxima: world px - screen px */
#define CAM_MAX_X  160u   /* MAP_PX_W(320) - SCREEN_W(160) */
#define CAM_MAX_Y  144u   /* MAP_PX_H(288) - SCREEN_H(144) */

/* Write one full world column to VRAM ring buffer.
 * VRAM x slot = world_tx % 32. Handles 36-row world (36 > 32 wraps). */
static void stream_column(uint8_t world_tx) {
    static uint8_t col_buf[MAP_TILES_H];
    uint8_t ty;
    uint8_t vram_x = world_tx & 31u;

    for (ty = 0u; ty < MAP_TILES_H; ty++) {
        col_buf[ty] = track_map[(uint16_t)ty * MAP_TILES_W + world_tx];
    }
    /* Write rows 0..31 in one call, then rows 32..35 wrap to VRAM rows 0..3 */
    set_bkg_tiles(vram_x, 0u, 1u, 32u, col_buf);
    set_bkg_tiles(vram_x, 0u, 1u, (uint8_t)(MAP_TILES_H - 32u), &col_buf[32]);
}

/* Write one full world row to VRAM ring buffer.
 * VRAM y slot = world_ty % 32. Handles 40-col world (40 > 32 wraps). */
static void stream_row(uint8_t world_ty) {
    static uint8_t row_buf[MAP_TILES_W];
    uint8_t tx;
    uint8_t vram_y = world_ty & 31u;

    for (tx = 0u; tx < MAP_TILES_W; tx++) {
        row_buf[tx] = track_map[(uint16_t)world_ty * MAP_TILES_W + tx];
    }
    /* Write cols 0..31 in one call, then cols 32..39 wrap to VRAM cols 0..7 */
    set_bkg_tiles(0u, vram_y, 32u, 1u, row_buf);
    set_bkg_tiles(0u, vram_y, (uint8_t)(MAP_TILES_W - 32u), 1u, &row_buf[32]);
}

/* Clamp a signed camera candidate to [0, max]. Returns uint8_t. */
static uint8_t clamp_cam(int16_t v, uint8_t max) {
    if (v < 0) return 0u;
    if ((uint16_t)v > max) return max;
    return (uint8_t)v;
}

void camera_init(int16_t player_world_x, int16_t player_world_y) {
    uint8_t ty;

    /* Preload all 36 world rows into VRAM ring buffer */
    for (ty = 0u; ty < MAP_TILES_H; ty++) {
        stream_row(ty);
    }

    /* Set initial scroll centered on player */
    cam_x = clamp_cam(player_world_x - 80, CAM_MAX_X);
    cam_y = clamp_cam(player_world_y - 72, CAM_MAX_Y);
    move_bkg(cam_x, cam_y);
}

void camera_update(int16_t player_world_x, int16_t player_world_y) {
    uint8_t ncx = clamp_cam(player_world_x - 80, CAM_MAX_X);
    uint8_t ncy = clamp_cam(player_world_y - 72, CAM_MAX_Y);

    /* Stream right column if right viewport edge crossed a tile boundary */
    {
        uint8_t old_right = (uint8_t)((cam_x + 159u) >> 3u);
        uint8_t new_right = (uint8_t)((ncx  + 159u) >> 3u);
        if (new_right != old_right && new_right < MAP_TILES_W) {
            stream_column(new_right);
        }
    }
    /* Stream left column if left viewport edge crossed a tile boundary */
    {
        uint8_t old_left = (uint8_t)(cam_x >> 3u);
        uint8_t new_left = (uint8_t)(ncx  >> 3u);
        if (new_left != old_left && new_left < MAP_TILES_W) {
            stream_column(new_left);
        }
    }
    /* Stream bottom row if bottom viewport edge crossed a tile boundary */
    {
        uint8_t old_bot = (uint8_t)((cam_y + 143u) >> 3u);
        uint8_t new_bot = (uint8_t)((ncy  + 143u) >> 3u);
        if (new_bot != old_bot && new_bot < MAP_TILES_H) {
            stream_row(new_bot);
        }
    }
    /* Stream top row if top viewport edge crossed a tile boundary */
    {
        uint8_t old_top = (uint8_t)(cam_y >> 3u);
        uint8_t new_top = (uint8_t)(ncy  >> 3u);
        if (new_top != old_top && new_top < MAP_TILES_H) {
            stream_row(new_top);
        }
    }

    cam_x = ncx;
    cam_y = ncy;
    move_bkg(cam_x, cam_y);
}
```

**Note:** `col_buf` and `row_buf` are `static` — they're >64 bytes combined and the SDCC stack is tiny. Static placement is mandatory.

### Step 3: Verify the new files compile in the test build

```
make test
```

Expected: camera.c compiles (it has no test of its own yet, but it's compiled as part of `TEST_LIB_SRC`). `test_player` still fails. That's fine.

### Step 4: Commit

```bash
git add src/camera.h src/camera.c
git commit -m "feat: add camera module with VRAM ring-buffer tile streaming"
```

---

## Task 5: Create `tests/test_camera.c`

**Files:**
- Create: `tests/test_camera.c`

Tests cover: `clamp_cam` logic (via `camera_init` observable side effects), centering, and all four edge clamps.

Since `cam_x` and `cam_y` are `extern`, tests can read them directly after calling `camera_init()`.

```c
#include "unity.h"
#include "camera.h"
#include "track.h"

void setUp(void)    {}
void tearDown(void) {}

/* --- camera_init centering ------------------------------------------ */

/* Player at world center (160, 144): cam should center on player.
 * cam_x = 160 - 80 = 80, cam_y = 144 - 72 = 72 */
void test_camera_init_centers_on_player(void) {
    camera_init(160, 144);
    TEST_ASSERT_EQUAL_UINT8(80, cam_x);
    TEST_ASSERT_EQUAL_UINT8(72, cam_y);
}

/* --- camera_update centering ---------------------------------------- */

void test_camera_update_centers_on_player(void) {
    camera_init(160, 144);
    camera_update(200, 180);
    /* cam_x = 200-80=120, cam_y = 180-72=108 */
    TEST_ASSERT_EQUAL_UINT8(120, cam_x);
    TEST_ASSERT_EQUAL_UINT8(108, cam_y);
}

/* --- Camera clamp: left / top edge ---------------------------------- */

/* Player so far left that cam would go negative: clamp to 0 */
void test_camera_clamp_left_edge(void) {
    camera_init(40, 144);
    /* cam_x = 40-80 = -40 → clamped to 0 */
    TEST_ASSERT_EQUAL_UINT8(0, cam_x);
}

void test_camera_clamp_top_edge(void) {
    camera_init(160, 40);
    /* cam_y = 40-72 = -32 → clamped to 0 */
    TEST_ASSERT_EQUAL_UINT8(0, cam_y);
}

/* --- Camera clamp: right / bottom edge ------------------------------ */

/* Player so far right that cam would exceed CAM_MAX_X (160): clamp */
void test_camera_clamp_right_edge(void) {
    /* MAP_PX_W=320, CAM_MAX_X=160. Player at x=280: cam=280-80=200 → clamp to 160 */
    camera_init(280, 144);
    TEST_ASSERT_EQUAL_UINT8(160, cam_x);
}

void test_camera_clamp_bottom_edge(void) {
    /* MAP_PX_H=288, CAM_MAX_Y=144. Player at y=260: cam=260-72=188 → clamp to 144 */
    camera_init(160, 260);
    TEST_ASSERT_EQUAL_UINT8(144, cam_y);
}

/* --- Exact clamp boundaries ----------------------------------------- */

/* Player exactly at center of map edge — cam hits max exactly */
void test_camera_update_clamp_exact_max_x(void) {
    camera_init(160, 144);
    camera_update(240, 144);   /* cam_x = 240-80 = 160 = CAM_MAX_X exactly */
    TEST_ASSERT_EQUAL_UINT8(160, cam_x);
}

void test_camera_update_clamp_exact_max_y(void) {
    camera_init(160, 144);
    camera_update(160, 216);   /* cam_y = 216-72 = 144 = CAM_MAX_Y exactly */
    TEST_ASSERT_EQUAL_UINT8(144, cam_y);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_camera_init_centers_on_player);
    RUN_TEST(test_camera_update_centers_on_player);
    RUN_TEST(test_camera_clamp_left_edge);
    RUN_TEST(test_camera_clamp_top_edge);
    RUN_TEST(test_camera_clamp_right_edge);
    RUN_TEST(test_camera_clamp_bottom_edge);
    RUN_TEST(test_camera_update_clamp_exact_max_x);
    RUN_TEST(test_camera_update_clamp_exact_max_y);
    return UNITY_END();
}
```

### Step 2: Run tests — expect test_camera passes, test_player still fails

```
make test
```

Expected: `test_camera` passes all 8 tests. `test_track` still passes. `test_player` still fails.

### Step 3: Commit

```bash
git add tests/test_camera.c
git commit -m "test: add test_camera for clamp and centering logic"
```

---

## Task 6: Refactor `src/player.h` and `src/player.c`

**Files:**
- Modify: `src/player.h`
- Modify: `src/player.c`

### Step 1: Write new `src/player.h`

Removes `clamp_u8` (no longer used), changes position types to `int16_t`:

```c
#ifndef PLAYER_H
#define PLAYER_H

#include <gb/gb.h>
#include <stdint.h>

void     player_init(void);
void     player_update(uint8_t input);
void     player_render(void);
void     player_set_pos(int16_t x, int16_t y);
int16_t  player_get_x(void);
int16_t  player_get_y(void);

#endif /* PLAYER_H */
```

### Step 2: Write new `src/player.c`

```c
#include <gb/gb.h>
#include "player.h"
#include "track.h"
#include "camera.h"

/* Solid 8x8 sprite: all pixels color index 3 */
static const uint8_t player_tile_data[] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
};

/* Player start: bottom straight center — world (160, 256) = tile (20, 32) */
#define PLAYER_START_X  160
#define PLAYER_START_Y  256

static int16_t px;
static int16_t py;

/* Returns 1 if all 4 corners of a player at world (wx, wy) are on track. */
static uint8_t corners_passable(int16_t wx, int16_t wy) {
    return track_passable(wx,       wy) &&
           track_passable(wx + 7,   wy) &&
           track_passable(wx,       wy + 7) &&
           track_passable(wx + 7,   wy + 7);
}

void player_init(void) {
    SPRITES_8x8;
    set_sprite_data(0, 1, player_tile_data);
    set_sprite_tile(0, 0);
    px = PLAYER_START_X;
    py = PLAYER_START_Y;
    SHOW_SPRITES;
}

void player_update(uint8_t input) {
    if (input & J_LEFT) {
        int16_t new_px = px - 1;
        if (corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_RIGHT) {
        int16_t new_px = px + 1;
        if (corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_UP) {
        int16_t new_py = py - 1;
        if (corners_passable(px, new_py)) py = new_py;
    }
    if (input & J_DOWN) {
        int16_t new_py = py + 1;
        if (corners_passable(px, new_py)) py = new_py;
    }
}

void player_render(void) {
    /* hw coords = world coords - camera scroll + GB sprite hardware offsets */
    uint8_t hw_x = (uint8_t)(px - (int16_t)cam_x + 8);
    uint8_t hw_y = (uint8_t)(py - (int16_t)cam_y + 16);
    move_sprite(0, hw_x, hw_y);
}

void player_set_pos(int16_t x, int16_t y) {
    px = x;
    py = y;
}

int16_t player_get_x(void) { return px; }
int16_t player_get_y(void) { return py; }
```

### Step 3: Run tests (still red — test_player uses old types)

```
make test
```

Expected: `test_player` has compile errors (old uint8_t types, old expected values). That's the signal to update tests next.

### Step 4: Commit

```bash
git add src/player.h src/player.c
git commit -m "feat: convert player position to int16_t world coords, remove screen-bound clamping"
```

---

## Task 7: Rewrite `tests/test_player.c`

**Files:**
- Modify: `tests/test_player.c`

Remove: `clamp_u8` tests, all screen-boundary clamping tests.
Update: init position test, movement tests, collision tests — all to world coords.

### Collision test reference values

| Test | Setup position | Direction | Blocked? | Reason |
|------|---------------|-----------|----------|--------|
| blocked_left | (32, 120) | J_LEFT → (31,120) | Yes | corner (31,120) = tile(3,15) D-row = 0 |
| blocked_right | (280, 120) | J_RIGHT → (281,120) | Yes | corner (288,120) = tile(36,15) = 0 |
| blocked_top | (160, 16) | J_UP → (160,15) | Yes | corner (160,15) = tile(20,1) A-row = 0 |
| blocked_bottom | (160, 264) | J_DOWN → (160,265) | Yes | corner (160,272) = tile(20,34) A-row = 0 |

Verify each against the map design before trusting the tests.

```c
#include "unity.h"
#include "player.h"

void setUp(void)    { player_init(); }
void tearDown(void) {}

/* player_init -------------------------------------------------------- */

/* Start position: world (160, 256) = tile (20,32), bottom straight center */
void test_player_init_sets_start_position(void) {
    TEST_ASSERT_EQUAL_INT16(160, player_get_x());
    TEST_ASSERT_EQUAL_INT16(256, player_get_y());
}

/* player_update movement --------------------------------------------- */

void test_player_update_moves_left(void) {
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_INT16(159, player_get_x());
}

void test_player_update_moves_right(void) {
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_INT16(161, player_get_x());
}

void test_player_update_moves_up(void) {
    player_update(J_UP);
    TEST_ASSERT_EQUAL_INT16(255, player_get_y());
}

void test_player_update_moves_down(void) {
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_INT16(257, player_get_y());
}

/* player_update track collision -------------------------------------- */

/* Left outer wall: tile col 3 (D-row) is off-track */
void test_player_blocked_by_track_left(void) {
    player_set_pos(32, 120);
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_INT16(32, player_get_x());
}

/* Right outer wall: tile col 36 (D-row) is off-track */
void test_player_blocked_by_track_right(void) {
    player_set_pos(280, 120);
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_INT16(280, player_get_x());
}

/* Top outer wall: tile row 1 (A-row) is off-track */
void test_player_blocked_by_track_top(void) {
    player_set_pos(160, 16);
    player_update(J_UP);
    TEST_ASSERT_EQUAL_INT16(16, player_get_y());
}

/* Bottom outer wall: tile row 34 (A-row) is off-track */
void test_player_blocked_by_track_bottom(void) {
    player_set_pos(160, 264);
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_INT16(264, player_get_y());
}

/* runner ------------------------------------------------------------- */

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_player_init_sets_start_position);
    RUN_TEST(test_player_update_moves_left);
    RUN_TEST(test_player_update_moves_right);
    RUN_TEST(test_player_update_moves_up);
    RUN_TEST(test_player_update_moves_down);
    RUN_TEST(test_player_blocked_by_track_left);
    RUN_TEST(test_player_blocked_by_track_right);
    RUN_TEST(test_player_blocked_by_track_top);
    RUN_TEST(test_player_blocked_by_track_bottom);
    return UNITY_END();
}
```

### Step 2: Run tests — all must pass

```
make test
```

Expected output: all three test suites pass — `test_track`, `test_camera`, `test_player`.

If `test_player_blocked_by_track_right` fails: double-check tile (36, 15) — it is in cols 36–39 of a D-row, which are zeros in the pattern `{0×4, 1×4, 0×24, 1×4, 0×4}`. Col 36 = index 36: 4+4+24+4=36, so index 36 is the 1st zero of the last group. ✓

### Step 3: Commit

```bash
git add tests/test_player.c
git commit -m "test: rewrite test_player for world coords, remove screen-bound clamping tests"
```

---

## Task 8: Update `src/main.c`

**Files:**
- Modify: `src/main.c`

Two changes:
1. Add `#include "camera.h"`
2. Call `camera_init(player_get_x(), player_get_y())` on `STATE_PLAYING` transition
3. Call `camera_update(player_get_x(), player_get_y())` each `STATE_PLAYING` frame

```c
#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "player.h"
#include "track.h"
#include "camera.h"

typedef enum {
    STATE_INIT,
    STATE_TITLE,
    STATE_PLAYING,
    STATE_GAME_OVER
} GameState;

static GameState state = STATE_INIT;

static const uint16_t bkg_pal[] = {
    RGB(31, 31, 31),
    RGB(20, 20, 20),
    RGB(10, 10, 10),
    RGB(0,  0,  0)
};
static const uint16_t spr_pal[] = {
    RGB(31, 31, 31),
    RGB(20, 20, 20),
    RGB(10, 10, 10),
    RGB(0,  0,  0)
};

static void init_palettes(void) {
    if (_cpu == CGB_TYPE) {
        set_bkg_palette(0, 1, bkg_pal);
        set_sprite_palette(0, 1, spr_pal);
    }
}

static void show_title(void) {
    cls();
    gotoxy(2, 6);
    printf("WASTELAND RACER");
    gotoxy(3, 10);
    printf("Press START");
    state = STATE_TITLE;
}

void main(void) {
    DISPLAY_OFF;

    init_palettes();
    player_init();

    DISPLAY_ON;

    show_title();

    while (1) {
        wait_vbl_done();

        switch (state) {
            case STATE_TITLE:
                if (joypad() & J_START) {
                    track_init();
                    camera_init(player_get_x(), player_get_y());
                    state = STATE_PLAYING;
                }
                break;

            case STATE_PLAYING:
                player_update(joypad());
                camera_update(player_get_x(), player_get_y());
                player_render();
                break;

            case STATE_GAME_OVER:
                break;

            default:
                break;
        }
    }
}
```

### Step 2: Run all tests (no main.c changes affect tests)

```
make test
```

Expected: all pass (unchanged).

### Step 3: Build the ROM

```
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: `build/wasteland-racer.gb` produced with no new warnings beyond the EVELYN harmless notice.

If SDCC warns about `int16_t` arithmetic, ensure all arithmetic expressions are fully typed. Common fix: `(int16_t)(px - (int16_t)cam_x + 8)`.

### Step 4: Commit

```bash
git add src/main.c
git commit -m "feat: wire camera_init and camera_update into main game loop"
```

---

## Task 9: Smoketest gate

**Do not push or create a PR until the user confirms this step.**

Run the emulator:

```bash
mgba-qt build/wasteland-racer.gb
```

Checklist:
- [ ] Title screen appears, press START transitions to game
- [ ] Player visible on bottom straight
- [ ] Driving left/right/up/down moves player — camera follows
- [ ] Camera clamps at all four map edges (no black border)
- [ ] No tile seams or corruption visible during a full lap
- [ ] Player cannot leave the track

Ask the user: **"Smoketest complete? Any issues visible in mgba-qt?"**

---

## Task 10: Push and create PR

Only after user confirms smoketest.

```bash
git push -u origin chore/update-claude-md
```

Wait — check current branch first. If still on `chore/update-claude-md`, create a new branch for this feature:

```bash
git checkout -b feat/scrolling-oval-track
git push -u origin feat/scrolling-oval-track
gh pr create --title "feat: 4-screen oval track with scrolling camera" \
  --body "$(cat <<'EOF'
Closes #4

## Summary
- Expanded track to 40×36 tiles (320×288 px) with oval redesigned to fill the larger canvas
- New `camera` module: `camera_init()` / `camera_update()` center viewport on player each frame, clamped to map edges
- VRAM ring-buffer tile streaming: world tile `(tx, ty)` written to VRAM at `(tx % 32, ty % 32)`; new columns/rows streamed during VBlank as camera scrolls
- Player position converted to `int16_t` world pixel coords; screen bounds removed from `player.c`; `track_passable()` now takes world coords
- Map dimension constants (`MAP_TILES_W/H`, `MAP_PX_W/H`) in `src/track.h`

## Test plan
- [ ] `make test` passes (test_track, test_camera, test_player)
- [ ] `GBDK_HOME=~/gbdk make` produces valid ROM with no new warnings
- [ ] Smoketest confirmed in mgba-qt: full lap, no seams, camera clamps at all edges

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Refactor Checkpoint

Before closing this task, answer:

> "Does this implementation generalize, or did we hard-code something that breaks when N > 1?"

Known hard-codes that are intentional and acceptable:
- Single player (OAM sprite 0) — follow-up required if multiplayer added
- Two tile types (off-track = 0, road = 1) — tile ID system needed for richer terrain
- 40×36 world size baked into `MAP_TILES_W/H` — easy to change in `track.h`, no code changes needed

No immediate follow-up issues required.
