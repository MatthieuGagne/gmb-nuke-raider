# Overmap State Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `STATE_OVERMAP` hub screen between title and race that lets the player navigate a minimal world map, select a race, and return here after finishing.

**Architecture:** New `state_overmap` module manages a 20×18-tile BKG screen with three walkable tile types (hub, road, dest). The player car sprite snaps tile-by-tile on d-pad ticks. Stepping on a dest tile sets `current_race_id` and pushes `state_playing`. After the race ends (player tile Y == `track_finish_line_y`), the game replaces state back to `state_overmap`. The finish line row is authored in Tiled as an objectgroup rectangle; `tools/tmx_to_c.py` parses it and emits `track_finish_line_y` into `src/track_map.c`.

**Tech Stack:** GBDK-2020, SDCC, Unity (host tests), Python 3 (tool tests)

---

## Key Coordinates & Constants

- Overmap screen: 20×18 tiles (full GBC screen, no scrolling)
- Hub tile: `(tx=9, ty=8)`
- Left dest tile: `(tx=2, ty=8)` → `current_race_id = 0`
- Right dest tile: `(tx=17, ty=8)` → `current_race_id = 1`
- Finish row in track: tile row `ty=5` (pixel y=40 in TMX)
- Overmap tile indices: `0`=blank, `1`=road, `2`=hub, `3`=dest
- Finish tile in track: C index `6`, Tiled GID `7` (TMX uses 1-based GIDs)

## How `track_finish_line_y` flows

```
track.tmx  →  tools/tmx_to_c.py  →  src/track_map.c
objectgroup name="finish" rect y=40 → finish_tile_y = 40/8 = 5
emits: const uint8_t track_finish_line_y = 5;
track.h declares: extern const uint8_t track_finish_line_y;
state_playing.c checks: player tile Y == track_finish_line_y → transition
```

---

## Task 1: Add overmap and finish constants to `config.h`

**Files:**
- Modify: `src/config.h`

**Step 1: Add constants**

At the bottom of `src/config.h`, before `#endif`, add:

```c
/* Overmap layout constants */
#define OVERMAP_W            20u
#define OVERMAP_H            18u
#define OVERMAP_HUB_TX        9u
#define OVERMAP_HUB_TY        8u
#define OVERMAP_DEST_LEFT_TX  2u
#define OVERMAP_DEST_RIGHT_TX 17u

/* Overmap tile type indices (BKG tile data slots 0-3) */
#define OVERMAP_TILE_BLANK  0u
#define OVERMAP_TILE_ROAD   1u
#define OVERMAP_TILE_HUB    2u
#define OVERMAP_TILE_DEST   3u
```

**Step 2: Verify compile**

```sh
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM builds successfully (no logic change yet).

**Step 3: Commit**

```sh
git add src/config.h
git commit -m "feat(config): add overmap layout and tile constants"
```

---

## Task 2: Add finish tile to `track.c` and extend `track.h`

The finish tile (C index 6) must be declared passable and have a visual loaded at startup. No changes to `tileset.png` or `track_tiles.c` — the visual is loaded directly.

**Files:**
- Modify: `src/track.h`
- Modify: `src/track.c`
- Modify: `tests/test_track.c`

**Step 1: Write the failing test** in `tests/test_track.c`

Add at the bottom (before the `main`/runner block):

```c
void test_finish_tile_is_road(void) {
    /* tile index 6 (finish visual) must be classified as road — passable */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(6));
}
```

Register it in `UnityMain` (or the RUN_TEST block at the bottom of the file).

**Step 2: Run to verify it fails**

```sh
make test 2>&1 | grep -A3 test_track
```
Expected: FAIL — index 6 hits the `>= TILE_LUT_LEN` branch which already returns `TILE_ROAD`. Wait — this test may PASS already due to the fallback. Run it and confirm either way. If it passes, skip to Step 4.

**Step 3: Add explicit entry to LUT** in `src/track.c`

Change:

```c
#define TILE_LUT_LEN 6u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
};
```

to:

```c
#define TILE_LUT_LEN 7u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
    TILE_ROAD,   /* 6: finish line visual — passable */
};
```

**Step 4: Load finish tile visual in `track_init()`** in `src/track.c`

Add after `set_bkg_data(0, track_tile_data_count, track_tile_data);`:

```c
/* Finish line tile — horizontal alternating stripes; color 1/3 */
static const uint8_t finish_tile_data[16] = {
    0xFF,0xFF, 0xFF,0x00, 0xFF,0xFF, 0xFF,0x00,
    0xFF,0xFF, 0xFF,0x00, 0xFF,0xFF, 0xFF,0x00,
};
set_bkg_data(6, 1, finish_tile_data);
```

**Step 5: Declare `track_finish_line_y` in `src/track.h`**

Add after the existing `extern` declarations:

```c
extern const uint8_t track_finish_line_y;
```

**Step 6: Run tests**

```sh
make test 2>&1 | grep -E "PASS|FAIL|test_track"
```
Expected: test_finish_tile_is_road PASS.

**Step 7: Commit**

```sh
git add src/track.h src/track.c tests/test_track.c
git commit -m "feat(track): add finish tile type, visual data, and finish_line_y declaration"
```

---

## Task 3: Update `tools/tmx_to_c.py` to parse finish objectgroup

**Files:**
- Modify: `tools/tmx_to_c.py`
- Modify: `tests/test_tmx_to_c.py`

**Step 1: Write the failing Python test** — open `tests/test_tmx_to_c.py` and add a test class:

```python
class TestFinishLineParsing(unittest.TestCase):
    def _make_tmx_with_finish(self, finish_y_px):
        """Return a minimal TMX string with a 'finish' objectgroup."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.0"
     orientation="orthogonal" renderorder="right-down"
     width="20" height="100" tilewidth="8" tileheight="8"
     infinite="0" nextlayerid="4" nextobjectid="3">
 <tileset firstgid="1" source="track.tsx"/>
 <layer id="1" name="Track" width="20" height="100">
  <data encoding="csv">
{','.join(['1'] * 2000)}
  </data>
 </layer>
 <objectgroup id="2" name="start">
  <object id="1" x="88" y="720" width="8" height="8"/>
 </objectgroup>
 <objectgroup id="3" name="finish">
  <object id="2" x="0" y="{finish_y_px}" width="160" height="8"/>
 </objectgroup>
</map>"""

    def test_finish_line_y_parsed_correctly(self):
        import tempfile, os
        tmx_content = self._make_tmx_with_finish(40)  # row 5
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tmx', delete=False) as f:
            f.write(tmx_content)
            tmx_path = f.name
        out_path = tmx_path.replace('.tmx', '.c')
        try:
            from tools.tmx_to_c import tmx_to_c
            tmx_to_c(tmx_path, out_path)
            with open(out_path) as f:
                content = f.read()
            self.assertIn('track_finish_line_y = 5', content)
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_missing_finish_raises(self):
        import tempfile, os
        # TMX without a 'finish' objectgroup should raise ValueError
        tmx_content = self._make_tmx_with_finish(40).replace(
            '<objectgroup id="3" name="finish">',
            '<objectgroup id="3" name="notfinish">'
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tmx', delete=False) as f:
            f.write(tmx_content)
            tmx_path = f.name
        out_path = tmx_path.replace('.tmx', '.c')
        try:
            from tools.tmx_to_c import tmx_to_c
            with self.assertRaises(ValueError):
                tmx_to_c(tmx_path, out_path)
        finally:
            os.unlink(tmx_path)
            if os.path.exists(out_path):
                os.unlink(out_path)
```

**Step 2: Run to verify tests fail**

```sh
PYTHONPATH=. python3 -m unittest tests.test_tmx_to_c -v 2>&1 | tail -20
```
Expected: `TestFinishLineParsing` tests FAIL.

**Step 3: Update `tools/tmx_to_c.py`**

After the `spawn_y` lines in `tmx_to_c()`, add finish parsing:

```python
    # Parse "finish" objectgroup for finish line tile row.
    finish_group = next(
        (og for og in root.findall('objectgroup')
         if og.get('name') == 'finish'),
        None
    )
    if finish_group is None:
        raise ValueError("TMX is missing an objectgroup named 'finish'")
    finish_obj = finish_group.find('object')
    if finish_obj is None:
        raise ValueError("'finish' objectgroup has no objects")
    finish_tile_y = int(float(finish_obj.get('y'))) // 8
```

In the file-writing block, after writing `track_start_y`, add:

```python
        f.write(f"const uint8_t track_finish_line_y = {finish_tile_y};\n\n")
```

**Step 4: Run tests to verify they pass**

```sh
PYTHONPATH=. python3 -m unittest tests.test_tmx_to_c -v 2>&1 | tail -10
```
Expected: all `TestFinishLineParsing` tests PASS.

**Step 5: Commit**

```sh
git add tools/tmx_to_c.py tests/test_tmx_to_c.py
git commit -m "feat(tools): parse finish objectgroup and emit track_finish_line_y"
```

---

## Task 4: Update `track.tmx` with finish tile row + objectgroup, then regenerate `track_map.c`

**Files:**
- Modify: `assets/maps/track.tmx`
- Regenerate: `src/track_map.c`

**Step 1: Edit `assets/maps/track.tmx`**

Change the `nextlayerid` attribute from `"3"` to `"4"` and `nextobjectid` from `"2"` to `"3"` in the `<map>` opening tag.

Change row 5 (the 6th CSV data line, 0-indexed) from:
```
1,1,1,1,2,2,2,2,2,2,2,2,2,2,2,2,1,1,1,1,
```
to (GID 7 = finish tile for road portion):
```
1,1,1,1,7,7,7,7,7,7,7,7,7,7,7,7,1,1,1,1,
```

Add the `finish` objectgroup AFTER the existing `start` objectgroup (which ends with `</objectgroup>`). Append before `</map>`:

```xml
 <objectgroup id="3" name="finish">
  <object id="2" x="0" y="40" width="160" height="8"/>
 </objectgroup>
```

**Step 2: Add `finish` objectgroup to the existing `start` objectgroup** — find the `start` objectgroup (already in the TMX) and leave it unchanged. Verify the file has BOTH objectgroups.

**Step 3: Regenerate `src/track_map.c`**

```sh
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

Verify the output contains:
```
const uint8_t track_finish_line_y = 5;
```
and row 5 of the map array has values `0,0,0,0,6,6,6,6,6,6,6,6,6,6,6,6,0,0,0,0` (GID 7 − firstgid 1 = 6).

**Step 4: Build to confirm no regressions**

```sh
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM builds successfully.

**Step 5: Commit**

```sh
git add assets/maps/track.tmx src/track_map.c
git commit -m "feat(track): add finish line row (tile 6) and finish objectgroup at row 5"
```

---

## Task 5: Create `src/state_overmap.h` and `tests/test_overmap.c` (TDD red phase)

**Files:**
- Create: `src/state_overmap.h`
- Create: `tests/test_overmap.c`

**Step 1: Create `src/state_overmap.h`**

```c
#ifndef STATE_OVERMAP_H
#define STATE_OVERMAP_H

#include <stdint.h>
#include "state_manager.h"

extern const State state_overmap;
extern uint8_t current_race_id;

/* Accessors used by unit tests */
uint8_t overmap_get_car_tx(void);
uint8_t overmap_get_car_ty(void);

#endif /* STATE_OVERMAP_H */
```

**Step 2: Create `tests/test_overmap.c`**

```c
#include "unity.h"
#include "state_overmap.h"
#include "config.h"
#include "input.h"

/* Provide definitions for input globals (main.c excluded from test build) */
uint8_t input     = 0;
uint8_t prev_input = 0;

/* Helper: simulate a single button tick */
static void tick(uint8_t btn) {
    prev_input = 0;
    input = btn;
    state_overmap.update();
    prev_input = input;
    input = 0;
}

void setUp(void) {
    input = 0;
    prev_input = 0;
    state_overmap.enter();
}

void tearDown(void) {}

void test_car_starts_at_hub(void) {
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX, overmap_get_car_tx());
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY, overmap_get_car_ty());
}

void test_left_moves_onto_road(void) {
    tick(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX - 1u, overmap_get_car_tx());
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY,      overmap_get_car_ty());
}

void test_right_moves_onto_road(void) {
    tick(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX + 1u, overmap_get_car_tx());
}

void test_up_blocked_by_blank(void) {
    /* Row 7 above the road row is blank — movement must be blocked */
    tick(J_UP);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY, overmap_get_car_ty());
}

void test_down_blocked_by_blank(void) {
    tick(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY, overmap_get_car_ty());
}

void test_held_button_does_not_repeat(void) {
    /* KEY_TICKED fires only on the rising edge, not while held */
    prev_input = J_LEFT;
    input      = J_LEFT;
    state_overmap.update();
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX, overmap_get_car_tx());
}

void test_dest_left_sets_race_id(void) {
    /* Walk left from hub to dest (7 tiles: hub=9 → dest=2) */
    uint8_t moves = OVERMAP_HUB_TX - OVERMAP_DEST_LEFT_TX;
    uint8_t i;
    for (i = 0; i < moves; i++) {
        tick(J_LEFT);
    }
    TEST_ASSERT_EQUAL_UINT8(0u, current_race_id);
}

void test_dest_right_sets_race_id(void) {
    uint8_t moves = OVERMAP_DEST_RIGHT_TX - OVERMAP_HUB_TX;
    uint8_t i;
    for (i = 0; i < moves; i++) {
        tick(J_RIGHT);
    }
    TEST_ASSERT_EQUAL_UINT8(1u, current_race_id);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_car_starts_at_hub);
    RUN_TEST(test_left_moves_onto_road);
    RUN_TEST(test_right_moves_onto_road);
    RUN_TEST(test_up_blocked_by_blank);
    RUN_TEST(test_down_blocked_by_blank);
    RUN_TEST(test_held_button_does_not_repeat);
    RUN_TEST(test_dest_left_sets_race_id);
    RUN_TEST(test_dest_right_sets_race_id);
    return UNITY_END();
}
```

**Step 3: Run to verify tests fail** (state_overmap.c doesn't exist yet)

```sh
make test 2>&1 | grep -E "error|FAIL|test_overmap" | head -20
```
Expected: compile error — `state_overmap.c` not found.

**Step 4: Commit stubs**

```sh
git add src/state_overmap.h tests/test_overmap.c
git commit -m "test(overmap): add failing tests for overmap state (TDD red)"
```

---

## Task 6: Implement `src/state_overmap.c` (TDD green phase)

**Files:**
- Create: `src/state_overmap.c`

**Step 1: Create `src/state_overmap.c`**

```c
#include <gb/gb.h>
#include "state_overmap.h"
#include "state_playing.h"
#include "state_manager.h"
#include "config.h"
#include "input.h"
#include "player.h"
#include "track.h"

/* ── Tile visual data (2bpp, 4 tiles × 16 bytes = 64 bytes in ROM) ── */
/* Tile 0: blank — all color 0 */
/* Tile 1: road  — horizontal band color 1 in rows 2-5 */
/* Tile 2: hub   — filled color 3 */
/* Tile 3: dest  — outline color 2 */
static const uint8_t overmap_tile_data[64] = {
    /* tile 0: blank */
    0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00,
    0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00,
    /* tile 1: road (horizontal band) */
    0x00,0x00, 0x00,0x00, 0xFF,0x00, 0xFF,0x00,
    0xFF,0x00, 0xFF,0x00, 0x00,0x00, 0x00,0x00,
    /* tile 2: hub (filled color 3) */
    0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF,
    0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF,
    /* tile 3: dest (border color 2 = high=1 low=0) */
    0x00,0xFF, 0x00,0x81, 0x00,0x81, 0x00,0x81,
    0x00,0x81, 0x00,0x81, 0x00,0x81, 0x00,0xFF,
};

/* ── Overmap BKG tile map (20×18 = 360 bytes in ROM) ── */
/*   0=blank  1=road  2=hub  3=dest                      */
static const uint8_t overmap_map[OVERMAP_H * OVERMAP_W] = {
    /* rows 0-7: all blank */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 8: dest–road–hub–road–dest */
    0,0,
    OVERMAP_TILE_DEST,
    OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,
    OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,
    OVERMAP_TILE_HUB,
    OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,
    OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,OVERMAP_TILE_ROAD,
    OVERMAP_TILE_ROAD,
    OVERMAP_TILE_DEST,
    0,0,
    /* rows 9-17: all blank */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
};

/* ── State ── */
static uint8_t car_tx;
static uint8_t car_ty;
uint8_t current_race_id = 0u;

uint8_t overmap_get_car_tx(void) { return car_tx; }
uint8_t overmap_get_car_ty(void) { return car_ty; }

/* ── Helpers ── */
static uint8_t overmap_walkable(uint8_t tx, uint8_t ty) {
    return overmap_map[(uint8_t)(ty * OVERMAP_W) + tx] != OVERMAP_TILE_BLANK;
}

static void overmap_move_sprite(void) {
    /* OAM offsets: x+8, y_top+16, y_bottom+24 */
    uint8_t sx = (uint8_t)(car_tx * 8u + 8u);
    uint8_t sy = (uint8_t)(car_ty * 8u + 16u);
    move_sprite(0, sx, sy);
    move_sprite(1, sx, (uint8_t)(sy + 8u));
}

/* ── State callbacks ── */
static void enter(void) {
    car_tx = OVERMAP_HUB_TX;
    car_ty = OVERMAP_HUB_TY;

    wait_vbl_done();
    DISPLAY_OFF;
    set_bkg_data(0, 4u, overmap_tile_data);
    set_bkg_tiles(0, 0, OVERMAP_W, OVERMAP_H, overmap_map);
    DISPLAY_ON;

    SHOW_BKG;
    SHOW_SPRITES;
    overmap_move_sprite();
}

static void update(void) {
    uint8_t new_tx = car_tx;
    uint8_t new_ty = car_ty;

    if      (KEY_TICKED(J_LEFT)  && car_tx > 0u)            new_tx = car_tx - 1u;
    else if (KEY_TICKED(J_RIGHT) && car_tx < OVERMAP_W - 1u) new_tx = car_tx + 1u;
    else if (KEY_TICKED(J_UP)    && car_ty > 0u)            new_ty = car_ty - 1u;
    else if (KEY_TICKED(J_DOWN)  && car_ty < OVERMAP_H - 1u) new_ty = car_ty + 1u;

    if (new_tx == car_tx && new_ty == car_ty) return;
    if (!overmap_walkable(new_tx, new_ty))    return;

    car_tx = new_tx;
    car_ty = new_ty;
    overmap_move_sprite();

    if (overmap_map[(uint8_t)(car_ty * OVERMAP_W) + car_tx] == OVERMAP_TILE_DEST) {
        current_race_id = (car_tx < OVERMAP_HUB_TX) ? 0u : 1u;
        state_replace(&state_playing);
    }
}

static void om_exit(void) {
}

const State state_overmap = { enter, update, om_exit };
```

> **Note on `overmap_map` row 8 element count:** Count the items in row 8 manually to verify they total exactly 20:
> `0,0` (2) + `DEST` (1) + `ROAD×6` (6) + `HUB` (1) + `ROAD×7` (7) + `DEST` (1) + `0,0` (2) = 20 ✓

**Step 2: Run tests**

```sh
make test 2>&1 | grep -E "PASS|FAIL|test_overmap"
```
Expected: all 8 tests PASS.

**Step 3: Commit**

```sh
git add src/state_overmap.c
git commit -m "feat(overmap): implement state_overmap — tile map, d-pad movement, dest detection"
```

---

## Task 7: Wire `state_title` to transition to `state_overmap`

**Files:**
- Modify: `src/state_title.c`

**Step 1: Add include and change transition**

In `src/state_title.c`, add `#include "state_overmap.h"` after the existing includes.

Change:
```c
        state_replace(&state_playing);
```
to:
```c
        state_replace(&state_overmap);
```

Remove the now-unused `#include "state_playing.h"` if it was only there for this transition.

**Step 2: Run tests**

```sh
make test
```
Expected: all tests PASS.

**Step 3: Build**

```sh
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM builds without errors.

**Step 4: Commit**

```sh
git add src/state_title.c
git commit -m "feat(title): redirect START to state_overmap instead of state_playing"
```

---

## Task 8: Add finish line detection and player reset to `state_playing`

**Files:**
- Modify: `src/state_playing.c`

**Step 1: Add includes**

In `src/state_playing.c`, add:
```c
#include "state_overmap.h"
```

**Step 2: Reset player position at race start**

In `state_playing.enter()`, add before `track_init()`:

```c
    player_set_pos(track_start_x, track_start_y);
    player_reset_vel();
```

Also add `#include "track.h"` if not already present (it already is via transitive includes — verify).

**Step 3: Add finish line detection in `state_playing.update()`**

At the end of `update()`, before the closing brace, add:

```c
    /* Finish line check — must be last so physics runs first this frame */
    {
        uint8_t fin_ty = (uint8_t)((uint16_t)player_get_y() >> 3u);
        if (fin_ty == track_finish_line_y) {
            state_replace(&state_overmap);
            return;
        }
    }
```

**Step 4: Run tests**

```sh
make test
```
Expected: all tests PASS (no regressions).

**Step 5: Build**

```sh
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM builds without errors.

**Step 6: Commit**

```sh
git add src/state_playing.c
git commit -m "feat(playing): reset player on race start; detect finish line and return to overmap"
```

---

## Task 9: Full build and smoketest

**Step 1: Run all tests**

```sh
make test
```
Expected: ALL tests PASS.

**Step 2: Build ROM**

```sh
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: `build/wasteland-racer.gb` produced with no errors.

**Step 3: Launch emulator** (run in background; ask user to verify)

```sh
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb
```

**Verify these scenarios manually:**

1. Title screen shows "WASTELAND RACER / Press START"
2. Pressing START shows the overmap — horizontal road with hub center, dest squares at left+right
3. D-pad left/right moves the car sprite along the road; up/down do nothing
4. Car cannot move past the dest tiles (screen edge direction is blank)
5. Stepping onto either dest tile transitions to the race
6. After playing, reaching the finish row (near top of track — distinctive striped tiles) transitions back to the overmap
7. Car reappears at hub after returning from race
8. Second race starts from `track_start` position, not from where previous race ended

**Step 4: Final commit (if any tweaks needed)**

```sh
git add -p   # review and stage only intended changes
git commit -m "fix(overmap): <describe any smoketest fix>"
```

---

## Notes for Implementer

- **VBlank pattern**: `state_overmap.enter()` uses `wait_vbl_done(); DISPLAY_OFF; ... DISPLAY_ON;`. This is safe regardless of when `enter()` is called.
- **Sprite slots**: Overmap reuses OAM slots 0 and 1 (same as the player car). `player_init()` already loaded the sprite tile data into VRAM at startup in `main.c` — no need to reload.
- **`cam_y` on overmap**: The VBL ISR calls `move_bkg(0, cam_y)`. On the overmap, `cam_y` is zero (camera never updated), so the BKG stays fixed. ✓
- **`current_race_id` is a stub**: Both values load the same track. This is intentional (R9). When a second track is added, `state_playing.enter()` reads `current_race_id` to select the track file.
- **track.tsx Tiled compatibility**: The TSX still says `tilecount="6"`. Tiled will flag GID 7 as missing in the editor. This is cosmetic only — the game doesn't use Tiled at runtime. Fix by updating `track.tsx` to `tilecount="7" columns="7"` and extending `tileset.png` to 56×8 in a future art-polish pass.
- **`overmap_map` row 8 starts at byte offset `8 * 20 = 160`** in the array. Double-check the element count totals 20.
