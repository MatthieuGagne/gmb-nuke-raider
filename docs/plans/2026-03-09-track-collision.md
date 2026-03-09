# Track & Collision Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a static oval BG tile track and block the player from leaving it.

**Architecture:** Two BG tiles (off-track / track surface) drawn from a 20×18 ROM tile map. `track_passable(screen_x, screen_y)` checks the map directly. `player_update()` tests all 4 sprite corners before committing each axis of movement independently (enables sliding along edges).

**Tech Stack:** GBDK-2020 (`gb/gb.h`), Unity (host-side tests via `make test`), SDCC/lcc for ROM.

---

## Key Notes Before Starting

- `set_bkg_data(first_tile, nb_tiles, data)` — loads tile graphics into BG VRAM
- `set_bkg_tiles(x, y, w, h, tiles)` — writes tile IDs into the BG tile map
- `SHOW_BKG` — enables BG layer (already on by default in GBDK runtime; call anyway for clarity)
- **Font conflict:** GBDK's default font uses BG tile IDs 0–95. Calling `set_bkg_data(0, ...)` during init would corrupt it. Solution: call `track_init()` during the `STATE_TITLE → STATE_PLAYING` transition, after the console font is no longer needed.
- `track_map` passed to `set_bkg_tiles` must be a flat `uint8_t*`. Define as flat array `[18*20]`, index with `ty*20+tx` in `track_passable()`.
- All VRAM writes must occur after `wait_vbl_done()` (already called at top of game loop).
- Player sprite hardware coords → screen coords: `screen_x = px - 8`, `screen_y = py - 16`.
- Sprite corners for collision: `(sx, sy)`, `(sx+7, sy)`, `(sx, sy+7)`, `(sx+7, sy+7)`.

---

## Task 1: Add BG mock stubs

**Files:**
- Modify: `tests/mocks/gb/gb.h`

The test build compiles all `src/*.c` (except main.c). Once `src/track.c` exists, its `track_init()` body will reference `set_bkg_data`, `set_bkg_tiles`, and `SHOW_BKG`. These need stubs.

**Step 1: Add stubs to mock header**

Open `tests/mocks/gb/gb.h` and add after the existing sprite stubs (before `#endif`):

```c
/* Background tile functions */
#define SHOW_BKG ((void)0)
#define HIDE_BKG ((void)0)

static inline void set_bkg_data(uint8_t first_tile, uint8_t nb_tiles,
                                 const uint8_t *data) {
    (void)first_tile; (void)nb_tiles; (void)data;
}
static inline void set_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                                  const uint8_t *tiles) {
    (void)x; (void)y; (void)w; (void)h; (void)tiles;
}
```

**Step 2: Verify existing tests still pass**

Run: `make test`
Expected: all tests pass, no new errors.

**Step 3: Commit**

```bash
git add tests/mocks/gb/gb.h
git commit -m "test: add BG tile mock stubs for track compilation"
```

---

## Task 2: TDD — `track_passable()`

**Files:**
- Create: `tests/test_track.c`
- Create: `src/track.h`
- Create: `src/track.c`

### Step 1: Write failing tests

Create `tests/test_track.c`:

```c
#include "unity.h"
#include "track.h"

void setUp(void)    {}
void tearDown(void) {}

/* On-track: bottom straight, row 14 col 10 — screen (80, 112) */
void test_track_passable_bottom_straight(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(80, 112));
}

/* On-track: left side, row 7 col 2 — screen (16, 56) */
void test_track_passable_left_side(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(16, 56));
}

/* On-track: top straight, row 1 col 10 — screen (80, 8) */
void test_track_passable_top_straight(void) {
    TEST_ASSERT_EQUAL_UINT8(1, track_passable(80, 8));
}

/* Off-track: outer corner, row 0 col 0 — screen (0, 0) */
void test_track_passable_outer_corner(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(0, 0));
}

/* Off-track: inner void, row 7 col 9 — screen (72, 56) */
void test_track_passable_inner_void(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(72, 56));
}

/* Off-track: below bottom of oval, row 15 col 10 — screen (80, 120) */
void test_track_passable_below_oval(void) {
    TEST_ASSERT_EQUAL_UINT8(0, track_passable(80, 120));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_track_passable_bottom_straight);
    RUN_TEST(test_track_passable_left_side);
    RUN_TEST(test_track_passable_top_straight);
    RUN_TEST(test_track_passable_outer_corner);
    RUN_TEST(test_track_passable_inner_void);
    RUN_TEST(test_track_passable_below_oval);
    return UNITY_END();
}
```

### Step 2: Run to verify red

Run: `make test`
Expected: compile error — `track.h` not found.

### Step 3: Create `src/track.h`

```c
#ifndef TRACK_H
#define TRACK_H

#include <stdint.h>

void    track_init(void);
uint8_t track_passable(uint8_t screen_x, uint8_t screen_y);

#endif /* TRACK_H */
```

### Step 4: Create `src/track.c`

```c
#include <gb/gb.h>
#include "track.h"

/*
 * Tile 0: off-track — all pixels color index 2 (dark gray / wasteland)
 *         2bpp: low=0x00, high=0xFF per row
 * Tile 1: track surface — all pixels color index 1 (light gray / road)
 *         2bpp: low=0xFF, high=0x00 per row
 */
static const uint8_t track_tile_data[] = {
    /* Tile 0: off-track (color 2) */
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    /* Tile 1: track surface (color 1) */
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00
};

/*
 * 20x18 tile map. 0 = off-track, 1 = track.
 * Oval ring ~4 tiles wide; player (8x8 = 1 tile) fits with room to move.
 */
static const uint8_t track_map[18 * 20] = {
    /* row 0  */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 1  */ 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,
    /* row 2  */ 0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,
    /* row 3  */ 0,0,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,0,0,
    /* row 4  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 5  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 6  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 7  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 8  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 9  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 10 */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 11 */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 12 */ 0,0,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,0,0,
    /* row 13 */ 0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,
    /* row 14 */ 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,
    /* row 15 */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 16 */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 17 */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
};

void track_init(void) {
    set_bkg_data(0, 2, track_tile_data);
    set_bkg_tiles(0, 0, 20, 18, track_map);
    SHOW_BKG;
}

uint8_t track_passable(uint8_t screen_x, uint8_t screen_y) {
    uint8_t tx = screen_x / 8u;
    uint8_t ty = screen_y / 8u;
    if (tx >= 20u || ty >= 18u) return 0u;
    return track_map[(uint8_t)(ty * 20u + tx)] != 0u;
}
```

### Step 5: Run to verify green

Run: `make test`
Expected: all tests pass including the 6 new track tests.

### Step 6: Commit

```bash
git add src/track.h src/track.c tests/test_track.c
git commit -m "feat: add track tile map and track_passable collision query"
```

---

## Task 3: TDD — Player track collision

**Files:**
- Modify: `tests/test_player.c`
- Modify: `src/player.c`
- Modify: `src/player.h` (update start position constants, if exposed)

### Step 1: Write failing collision tests

Add these tests to `tests/test_player.c` (add before the `int main` runner, and add `RUN_TEST` calls for each):

```c
/* Collision: player blocked at left track boundary
 * hw (32, 120) = screen (24, 104) = tile (3, 13) — on track (row 13 col 3 = 1)
 * moving left: screen x=23, tile col 2 = 0 (off-track) → blocked */
void test_player_blocked_by_track_left(void) {
    player_set_pos(32, 120);
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(32, player_get_x());
}

/* Collision: player blocked at bottom track boundary
 * hw (88, 128) = screen (80, 112) = tile (10, 14) — on track (row 14 col 10 = 1)
 * moving down: bottom corner at screen y=120, tile row 15 = 0 → blocked */
void test_player_blocked_by_track_bottom(void) {
    player_set_pos(88, 128);
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(128, player_get_y());
}

/* Collision: player blocked moving up into off-track top
 * hw (88, 24) = screen (80, 8) = tile (10, 1) — on track (row 1 col 10 = 1)
 * moving up: screen y=7, tile row 0 = 0 → blocked */
void test_player_blocked_by_track_top(void) {
    player_set_pos(88, 24);
    player_update(J_UP);
    TEST_ASSERT_EQUAL_UINT8(24, player_get_y());
}

/* Sliding: player blocked moving up (off-track), but can still move right (on track)
 * Same start position as above */
void test_player_slides_right_when_up_blocked(void) {
    player_set_pos(88, 24);
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(89, player_get_x());
}
```

Also update the existing tests that use the old start position (`px=80, py=72` which is now off-track):

```c
/* test_player_init_sets_center_position: update expected values */
/* New start: hw (88, 124) = screen (80, 108) = tile (10, 13) — center of bottom straight */
void test_player_init_sets_center_position(void) {
    TEST_ASSERT_EQUAL_UINT8(88, player_get_x());
    TEST_ASSERT_EQUAL_UINT8(124, player_get_y());
}

/* Movement tests: update expected values to match new start position */
void test_player_update_moves_left(void) {
    player_update(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(87, player_get_x());
}
void test_player_update_moves_right(void) {
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(89, player_get_x());
}
void test_player_update_moves_up(void) {
    player_update(J_UP);
    TEST_ASSERT_EQUAL_UINT8(123, player_get_y());
}
void test_player_update_moves_down(void) {
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(125, player_get_y());
}
```

Add new `RUN_TEST` calls to `main()` in `tests/test_player.c`:
```c
RUN_TEST(test_player_blocked_by_track_left);
RUN_TEST(test_player_blocked_by_track_bottom);
RUN_TEST(test_player_blocked_by_track_top);
RUN_TEST(test_player_slides_right_when_up_blocked);
```

### Step 2: Run to verify red

Run: `make test`
Expected: failures on the new collision tests + the updated position/movement tests.

### Step 3: Implement collision in `player.c`

Update `src/player.c`:

1. Add `#include "track.h"` after `#include "player.h"`

2. Update start position constants:
```c
#define PLAYER_START_X  88u   /* was 80u — must be on track: screen (80,108) = tile (10,13) */
#define PLAYER_START_Y  124u  /* was 72u */
```

3. Add a static helper after the `#define` block:
```c
/* Returns 1 if all 4 corners of a sprite at (hw_px, hw_py) are on driveable track */
static uint8_t corners_passable(uint8_t hw_px, uint8_t hw_py) {
    uint8_t sx = (uint8_t)(hw_px - 8u);
    uint8_t sy = (uint8_t)(hw_py - 16u);
    return track_passable(sx, sy) &&
           track_passable((uint8_t)(sx + 7u), sy) &&
           track_passable(sx, (uint8_t)(sy + 7u)) &&
           track_passable((uint8_t)(sx + 7u), (uint8_t)(sy + 7u));
}
```

4. Replace `player_update()` with:
```c
void player_update(uint8_t input) {
    if (input & J_LEFT) {
        uint8_t new_px = clamp_u8((uint8_t)(px - 1u), PX_MIN, PX_MAX);
        if (corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_RIGHT) {
        uint8_t new_px = clamp_u8((uint8_t)(px + 1u), PX_MIN, PX_MAX);
        if (corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_UP) {
        uint8_t new_py = clamp_u8((uint8_t)(py - 1u), PY_MIN, PY_MAX);
        if (corners_passable(px, new_py)) py = new_py;
    }
    if (input & J_DOWN) {
        uint8_t new_py = clamp_u8((uint8_t)(py + 1u), PY_MIN, PY_MAX);
        if (corners_passable(px, new_py)) py = new_py;
    }
}
```

### Step 4: Run to verify green

Run: `make test`
Expected: all tests pass.

### Step 5: Commit

```bash
git add src/player.c tests/test_player.c
git commit -m "feat: add track collision to player_update, update start position"
```

---

## Task 4: Wire track into main.c

**Files:**
- Modify: `src/main.c`

### Step 1: Add `#include "track.h"` at the top of `main.c`

Add after `#include "player.h"`:
```c
#include "track.h"
```

### Step 2: Call `track_init()` on transition to PLAYING

In the `STATE_TITLE` case, replace:
```c
case STATE_TITLE:
    if (joypad() & J_START) {
        cls();
        state = STATE_PLAYING;
    }
    break;
```
with:
```c
case STATE_TITLE:
    if (joypad() & J_START) {
        track_init();   /* load BG tiles + tile map (VRAM write, safe after wait_vbl_done) */
        state = STATE_PLAYING;
    }
    break;
```

Note: `cls()` is removed — `track_init()` fully overwrites the 20×18 BG tile map, so there is nothing left to clear. Note also `wait_vbl_done()` is called at the top of the game loop, so VRAM writes here are safe.

### Step 3: Run tests

Run: `make test`
Expected: all tests still pass.

### Step 4: Commit

```bash
git add src/main.c
git commit -m "feat: call track_init on transition to STATE_PLAYING"
```

---

## Task 5: Build and smoketest

### Step 1: Build the ROM

Run: `GBDK_HOME=/home/mathdaman/gbdk make`
Expected: `build/wasteland-racer.gb` produced with no errors (EVELYN warning is harmless).

### Step 2: Ask user to smoketest in emulator

Tell the user: "Build successful. Please run `mgba-qt build/wasteland-racer.gb` and confirm:
1. Title screen appears correctly
2. Pressing START shows the oval track
3. Player starts on the track (bottom straight)
4. Player cannot leave the track in any direction
5. Player slides along track edges (not stuck at corners)"

**Do not commit or create a PR until the user confirms the smoketest.**

### Step 3: After user confirms smoketest — create PR

```bash
git push -u origin HEAD
gh pr create --title "feat: add oval track with boundary collision" --body "$(cat <<'EOF'
## Summary
- Adds a static 20×18 BG tile map forming an oval racing track
- Player is blocked from leaving the track (4-corner collision, independent axes for sliding)
- Track loaded on transition from title to playing state to avoid font tile conflict

## Test plan
- [ ] `make test` passes (track_passable tests + updated player collision tests)
- [ ] Title screen renders correctly
- [ ] Oval track visible when game starts
- [ ] Player cannot exit the track in any direction
- [ ] Player can slide along track edges

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
