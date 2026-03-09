# VBlank Frame Order Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move all VRAM writes to immediately after `wait_vbl_done()` so they land in the VBlank window, eliminating the progressive slowdown caused by per-byte HBlank spin-waits.

**Architecture:** `camera_update()` is split: the compute phase (boundary detection, cam_x/cam_y update) runs during active display; a new `camera_flush_vram()` drains a small pending-stream buffer at VBlank start. `main.c` reorders the loop: VRAM writes first, game logic second.

**Tech Stack:** GBDK-2020, SDCC, Unity test framework (gcc), mock VRAM in `tests/mocks/`

---

### Task 1: Add set_bkg_tiles call counter to the VRAM mock

**Why:** Tests need to verify that `camera_update()` does NOT write VRAM immediately, and that `camera_flush_vram()` does. The call counter tracks this without relying on specific tile data values.

**Files:**
- Modify: `tests/mocks/mock_bkg.c`
- Modify: `tests/mocks/gb/gb.h`

**Step 1: Rewrite mock_bkg.c to add the counter**

Replace the full contents of `tests/mocks/mock_bkg.c` with:

```c
#include <stdint.h>

/* Shared mock VRAM: 32x32 tile BG map */
uint8_t mock_vram[32u * 32u];

/* Counts every set_bkg_tiles call; reset by mock_vram_clear() */
int mock_set_bkg_tiles_call_count = 0;

void mock_vram_clear(void) {
    uint16_t i;
    mock_set_bkg_tiles_call_count = 0;
    for (i = 0u; i < 32u * 32u; i++) mock_vram[i] = 0u;
}

/* Writes a w×h rectangle of tiles into mock_vram, wrapping mod 32 */
void set_bkg_tiles(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                   const uint8_t *tiles) {
    uint8_t dy, dx;
    mock_set_bkg_tiles_call_count++;
    for (dy = 0u; dy < h; dy++) {
        for (dx = 0u; dx < w; dx++) {
            uint8_t vx = (uint8_t)((x + dx) & 31u);
            uint8_t vy = (uint8_t)((y + dy) & 31u);
            mock_vram[(uint16_t)vy * 32u + vx] = *tiles++;
        }
    }
}
```

**Step 2: Declare the counter in gb.h**

In `tests/mocks/gb/gb.h`, after the existing `mock_vram` declarations (line 70–71), add:

```c
extern int mock_set_bkg_tiles_call_count;
```

**Step 3: Run the existing tests to confirm they still pass**

```
make test
```
Expected: all existing tests pass (counter is additive; no behavior changed).

**Step 4: Commit**

```bash
git add tests/mocks/mock_bkg.c tests/mocks/gb/gb.h
git commit -m "test: add set_bkg_tiles call counter to VRAM mock"
```

---

### Task 2: Write failing tests for buffer and flush behavior

**Files:**
- Modify: `tests/test_camera.c`

**Step 1: Add the four new test functions**

Insert the following four test functions in `tests/test_camera.c` before `int main(void)`:

```c
/* --- camera_update: buffers streams, does NOT write VRAM immediately ---- */

/* When camera_update() crosses a tile boundary, it must queue the stream in
 * the pending buffer — NOT call set_bkg_tiles directly. The call count must
 * not change between camera_init and camera_update. */
void test_camera_update_does_not_write_vram_directly(void) {
    int count_after_init;
    camera_init(160, 144); /* cam_x=80, cam_y=72; preloads VRAM */
    count_after_init = mock_set_bkg_tiles_call_count;
    /* Move right to cross right tile boundary: cam_x 80→88, triggers stream_column(30) */
    camera_update(168, 144);
    TEST_ASSERT_EQUAL_INT(count_after_init, mock_set_bkg_tiles_call_count);
}

/* --- camera_flush_vram: drains buffer and writes VRAM ------------------- */

void test_camera_flush_vram_writes_pending_streams(void) {
    int count_after_update;
    camera_init(160, 144);
    camera_update(168, 144); /* buffers stream_column(30) */
    count_after_update = mock_set_bkg_tiles_call_count;
    camera_flush_vram();
    /* At least one set_bkg_tiles call must have occurred during flush */
    TEST_ASSERT_GREATER_THAN_INT(count_after_update, mock_set_bkg_tiles_call_count);
}

/* --- camera_flush_vram: clears buffer so second flush is a no-op -------- */

void test_camera_flush_vram_clears_buffer(void) {
    int count_after_first_flush;
    camera_init(160, 144);
    camera_update(168, 144); /* buffers stream_column(30) */
    camera_flush_vram();
    count_after_first_flush = mock_set_bkg_tiles_call_count;
    camera_flush_vram(); /* second flush — buffer must be empty */
    TEST_ASSERT_EQUAL_INT(count_after_first_flush, mock_set_bkg_tiles_call_count);
}

/* --- camera_flush_vram: no-op when no streams are pending --------------- */

void test_camera_flush_vram_noop_on_empty_buffer(void) {
    camera_init(160, 144);
    /* No camera_update call — no pending streams */
    mock_set_bkg_tiles_call_count = 0; /* baseline after init */
    camera_flush_vram();
    TEST_ASSERT_EQUAL_INT(0, mock_set_bkg_tiles_call_count);
}
```

**Step 2: Add RUN_TEST calls inside main()**

In the `int main(void)` block, after the existing `RUN_TEST` calls, add:

```c
    RUN_TEST(test_camera_update_does_not_write_vram_directly);
    RUN_TEST(test_camera_flush_vram_writes_pending_streams);
    RUN_TEST(test_camera_flush_vram_clears_buffer);
    RUN_TEST(test_camera_flush_vram_noop_on_empty_buffer);
```

**Step 3: Run tests to confirm they fail**

```
make test
```
Expected: compile error — `camera_flush_vram` undefined. This is the red phase.

---

### Task 3: Implement the pending-stream buffer and camera_flush_vram() in camera.c

**Files:**
- Modify: `src/camera.c`

**Step 1: Add buffer struct and state after the existing `#define` lines (~line 10)**

```c
#define STREAM_BUF_SIZE 4u

typedef struct {
    uint8_t index;
    uint8_t is_row;  /* 0 = column, 1 = row */
} StreamEntry;

static StreamEntry stream_buf[STREAM_BUF_SIZE];
static uint8_t     stream_buf_len = 0u;
```

**Step 2: Replace camera_update() body**

Replace the entire `camera_update()` function (lines 70–110) with:

```c
void camera_update(int16_t player_world_x, int16_t player_world_y) {
    uint8_t ncx = clamp_cam(player_world_x - 80, CAM_MAX_X);
    uint8_t ncy = clamp_cam(player_world_y - 72, CAM_MAX_Y);

    /* Buffer right column if right viewport edge crossed a tile boundary */
    {
        uint8_t old_right = (uint8_t)((cam_x + 159u) >> 3u);
        uint8_t new_right = (uint8_t)((ncx  + 159u) >> 3u);
        if (new_right != old_right && new_right < MAP_TILES_W
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_right;
            stream_buf[stream_buf_len].is_row = 0u;
            stream_buf_len++;
        }
    }
    /* Buffer left column if left viewport edge crossed a tile boundary */
    {
        uint8_t old_left = (uint8_t)(cam_x >> 3u);
        uint8_t new_left = (uint8_t)(ncx  >> 3u);
        if (new_left != old_left && new_left < MAP_TILES_W
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_left;
            stream_buf[stream_buf_len].is_row = 0u;
            stream_buf_len++;
        }
    }
    /* Buffer bottom row if bottom viewport edge crossed a tile boundary */
    {
        uint8_t old_bot = (uint8_t)((cam_y + 143u) >> 3u);
        uint8_t new_bot = (uint8_t)((ncy  + 143u) >> 3u);
        if (new_bot != old_bot && new_bot < MAP_TILES_H
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_bot;
            stream_buf[stream_buf_len].is_row = 1u;
            stream_buf_len++;
        }
    }
    /* Buffer top row if top viewport edge crossed a tile boundary */
    {
        uint8_t old_top = (uint8_t)(cam_y >> 3u);
        uint8_t new_top = (uint8_t)(ncy  >> 3u);
        if (new_top != old_top && new_top < MAP_TILES_H
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_top;
            stream_buf[stream_buf_len].is_row = 1u;
            stream_buf_len++;
        }
    }

    cam_x = ncx;
    cam_y = ncy;
    /* move_bkg() removed — called from main.c VBlank phase after camera_flush_vram() */
}
```

**Step 3: Add camera_flush_vram() at the end of camera.c**

```c
void camera_flush_vram(void) {
    uint8_t i;
    for (i = 0u; i < stream_buf_len; i++) {
        if (stream_buf[i].is_row) {
            stream_row(stream_buf[i].index);
        } else {
            stream_column(stream_buf[i].index);
        }
    }
    stream_buf_len = 0u;
}
```

**Step 4: Run tests**

```
make test
```
Expected: compile error — `camera_flush_vram` not declared in the header. Proceed to Task 4.

---

### Task 4: Declare camera_flush_vram() in camera.h

**Files:**
- Modify: `src/camera.h`

**Step 1: Update the camera_update() comment and add camera_flush_vram() declaration**

Replace the existing `camera_update()` declaration and comment (lines 15–18):

```c
/* Call every frame in STATE_PLAYING game-logic phase (after player_update).
 * Centers camera on player and buffers any new tile column/row streams.
 * Does NOT write VRAM or call move_bkg() directly — see camera_flush_vram(). */
void camera_update(int16_t player_world_x, int16_t player_world_y);

/* Call every frame in STATE_PLAYING VBlank phase, immediately after
 * wait_vbl_done() and before move_bkg(). Drains the pending tile-stream
 * buffer accumulated by camera_update() and resets it to empty. */
void camera_flush_vram(void);
```

**Step 2: Run tests**

```
make test
```
Expected: all tests pass including the four new ones. Note the result for `test_camera_vertical_move_at_left_does_not_corrupt_vram_col0` — it passes, but only because `camera_update()` no longer writes VRAM at all. Task 5 fixes this.

**Step 3: Commit**

```bash
git add src/camera.c src/camera.h
git commit -m "feat: add pending-stream buffer and camera_flush_vram() to camera"
```

Also commit the tests:

```bash
git add tests/test_camera.c
git commit -m "test: add buffer and flush tests for camera VBlank refactor"
```

---

### Task 5: Update existing VRAM-corruption regression test to call flush

**Files:**
- Modify: `tests/test_camera.c`

The test `test_camera_vertical_move_at_left_does_not_corrupt_vram_col0` currently passes trivially after the refactor (no VRAM write occurs at all). It must call `camera_flush_vram()` to actually exercise the stream logic and remain a genuine regression test against the wrap-around corruption bug.

**Step 1: Update the test (around line 84)**

Replace:

```c
void test_camera_vertical_move_at_left_does_not_corrupt_vram_col0(void) {
    camera_init(40, 144); /* cam_x=0, cam_y=72 */
    /* Move down 8px crossing a tile boundary → stream_row(27) fires.
     * Row 27 (D-row): world col 0 = 0 (off-track), world col 32 = 1 (road). */
    camera_update(40, 152); /* new cam_y=80, new_bot=27 != old_bot=26 */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[27u * 32u + 0u]);
}
```

With:

```c
void test_camera_vertical_move_at_left_does_not_corrupt_vram_col0(void) {
    camera_init(40, 144); /* cam_x=0, cam_y=72 */
    /* Move down 8px crossing a tile boundary → stream_row(27) buffered.
     * Row 27 (D-row): world col 0 = 0 (off-track), world col 32 = 1 (road). */
    camera_update(40, 152); /* new cam_y=80, new_bot=27 != old_bot=26 */
    camera_flush_vram();    /* flush pending streams to VRAM */
    TEST_ASSERT_EQUAL_UINT8(0u, mock_vram[27u * 32u + 0u]);
}
```

**Step 2: Run tests**

```
make test
```
Expected: all tests pass.

**Step 3: Commit**

```bash
git add tests/test_camera.c
git commit -m "test: add camera_flush_vram() to VRAM-corruption regression test"
```

---

### Task 6: Reorder the frame loop in main.c

**Files:**
- Modify: `src/main.c`

**Step 1: Update the STATE_PLAYING case (lines 72–76)**

Replace:

```c
            case STATE_PLAYING:
                player_update(joypad());
                camera_update(player_get_x(), player_get_y());
                player_render();
                break;
```

With:

```c
            case STATE_PLAYING:
                /* VBlank phase: all VRAM writes immediately after wait_vbl_done() */
                player_render();
                camera_flush_vram();
                move_bkg(cam_x, cam_y);
                /* Game logic phase: runs during active display */
                player_update(joypad());
                camera_update(player_get_x(), player_get_y());
                break;
```

**Step 2: Run tests**

```
make test
```
Expected: all tests pass.

**Step 3: Build the ROM**

```
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: `build/wasteland-racer.gb` produced, zero errors.

**Step 4: Commit**

```bash
git add src/main.c
git commit -m "fix: reorder frame loop — VRAM writes before game logic (#15)"
```

---

### Task 7: Smoketest and PR

**Step 1: Ask the user to run the emulator smoketest**

```
mgba-qt build/wasteland-racer.gb
```

Verify:
- Title screen appears; START begins gameplay
- Extended play session (2+ minutes, moving and standing still) shows stable frame rate
- No progressive slowdown or freeze (this was reproducible in ~30 seconds before the fix)

**Do not create the PR until the user confirms the smoketest passes.**

**Step 2: Push and create PR**

```bash
git push -u origin HEAD
gh pr create --title "fix: VBlank frame order — VRAM writes before game logic" --body "$(cat <<'EOF'
Closes #15

## Summary
- Adds a 4-entry pending-stream buffer to `camera.c`; `camera_update()` now buffers tile-stream requests instead of calling `set_bkg_tiles()` directly
- New `camera_flush_vram()` drains the buffer at VBlank start
- `move_bkg()` moved to VBlank phase in `main.c`, synchronized with tile flush
- Frame loop reordered: `player_render()` → `camera_flush_vram()` → `move_bkg()` → `player_update()` → `camera_update()`

## Root cause fixed
`set_bkg_tiles()` uses a per-byte `WAIT_STAT` spin loop. Running it during active display stalled on HBlanks each frame; the accumulated latency compounded until the game halted. Fix confirmed in emulator smoketest.

## Test coverage
- New tests: buffer behavior (no VRAM write until flush), flush drains and clears, no-op flush on empty buffer
- Updated existing wrap-around corruption regression test to call `camera_flush_vram()` before asserting

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
