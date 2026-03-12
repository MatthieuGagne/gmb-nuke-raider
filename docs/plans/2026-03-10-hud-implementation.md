# HUD — Race Timer & HP Display — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a fixed 2-row Window-layer HUD at the bottom of the screen showing HP:100 on the left and a MM:SS race timer on the right.

**Architecture:** A new `hud` module owns all HUD state and rendering. The Game Boy Window layer is pinned to the bottom 2 rows of the screen via `move_win(7, 128)`. Font tiles (digits 0–9, H, P, colon, space) are loaded into BG tile data at index 128+ to avoid collision with track tiles. A dirty flag prevents redundant VRAM writes — timer is redrawn only when a new second elapses.

**Tech Stack:** GBDK-2020, SDCC, Unity (host-side unit tests via `make test`)

**Reference:** Design doc at `docs/plans/2026-03-10-hud-design.md` | GitHub issue #55

---

## Hardware Notes (read before implementing)

- `set_win_tiles(x, y, w, h, tiles)` always writes to `SCRN1` (0x9C00). The Window layer only displays this tile map when **LCDC bit 6 = 1** (`LCDCF_WIN9C00 = 0x40`). This must be set in `hud_init()`.
- `set_bkg_data(first_tile, nb_tiles, data)` loads tile *pattern* data into VRAM — the Window layer shares this tile data with the BG layer.
- All VRAM writes in `hud_init()` are safe because it's called between `DISPLAY_OFF` and `DISPLAY_ON` in `state_playing.enter()`.
- `hud_render()` is called in the VBlank phase — `set_win_tiles` is safe there.
- `hud_update()` runs in the game logic phase — no VRAM writes allowed here.
- The 2bpp tile format: each 8×8 tile = 16 bytes; each pixel row = 2 bytes (low plane, high plane). For a solid color-3 pixel, both bytes have the corresponding bit set. For color-0 (background), both bits are 0. All our font tiles use only color 0 and color 3, so for each row: `low_byte == high_byte == pixel_bitmask`.

---

## Task 1: Add `PLAYER_HP_MAX` to `config.h`

**Files:**
- Modify: `src/config.h`

**Step 1: Edit `src/config.h`** — add after the `HUD_SCANLINE` define:

```c
#define PLAYER_HP_MAX 100
```

Final `config.h` should look like:

```c
#ifndef CONFIG_H
#define CONFIG_H

/* Entity capacity constants — all entity pools MUST use SoA (parallel arrays),
 * not AoS (struct arrays). See CLAUDE.md "Entity management" for rationale. */

#define MAX_NPCS     6
#define MAX_SPRITES  40

/* Player physics — these will become per-gear values when gears are added */
#define PLAYER_ACCEL      1
#define PLAYER_FRICTION   1
#define PLAYER_MAX_SPEED  6

#define MAP_TILES_W  20u
#define MAP_TILES_H  100u

#define HUD_SCANLINE 128  /* LYC fires here: 2-tile HUD = 16px at bottom */

#define PLAYER_HP_MAX 100

#endif /* CONFIG_H */
```

**Step 2: Commit**

```bash
git add src/config.h
git commit -m "feat: add PLAYER_HP_MAX to config.h"
```

---

## Task 2: Add `LCDC_REG` mock to the test mock headers

The real `LCDC_REG` lives in GBDK's `gb/hardware.h`. `hud.c` will write to it directly. The test mock needs a stub.

**Files:**
- Modify: `tests/mocks/gb/gb.h`

**Step 1: Add at the bottom of `tests/mocks/gb/gb.h`**, just before `#endif`:

```c
/* LCDC register — hud.c writes bit 6 (window tile map select) */
static uint8_t LCDC_REG = 0x91U; /* realistic boot value: LCD on, BG on, tile data at 0x8000 */
#define LCDCF_WIN9C00 0x40U       /* LCDC bit 6: window tile map at 0x9C00 */
```

**Step 2: Run existing tests to confirm nothing broke**

```bash
cd /home/mathdaman/code/gmb-junk-runner/.claude/worktrees/feat/hud
make test 2>&1 | tail -20
```

Expected: all existing tests still pass.

**Step 3: Commit**

```bash
git add tests/mocks/gb/gb.h
git commit -m "test: add LCDC_REG mock stub for hud tests"
```

---

## Task 3: Create `src/hud.h`

**Files:**
- Create: `src/hud.h`

**Step 1: Write `src/hud.h`**

```c
#ifndef HUD_H
#define HUD_H

#include <stdint.h>

/* --- Public API --- */
void    hud_init(void);          /* call in state_playing enter(), display must be OFF */
void    hud_update(void);        /* call in game logic phase each frame */
void    hud_render(void);        /* call in VBlank phase — writes win tiles when dirty */
void    hud_set_hp(uint8_t hp);  /* future use: wire to player damage system */

/* --- Test accessors (also useful for debug) --- */
uint16_t hud_get_seconds(void);  /* total elapsed seconds */
uint8_t  hud_is_dirty(void);     /* 1 if render needed, 0 if up to date */

#endif /* HUD_H */
```

---

## Task 4: Write `tests/test_hud.c` (failing tests — TDD red phase)

**Files:**
- Create: `tests/test_hud.c`

**Step 1: Write the test file**

```c
/* tests/test_hud.c — HUD timer logic and dirty-flag behavior */
#include "unity.h"
#include <gb/gb.h>
#include "../src/config.h"
#include "../src/hud.h"

void setUp(void) { hud_init(); }
void tearDown(void) {}

/* --- After init: state is zeroed and dirty is clear --- */

void test_init_seconds_zero(void) {
    TEST_ASSERT_EQUAL_UINT16(0u, hud_get_seconds());
}

void test_init_dirty_clear(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
}

/* --- Frame tick: 59 updates do NOT advance the second --- */

void test_update_no_second_before_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 59u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(0u, hud_get_seconds());
}

void test_update_not_dirty_before_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 59u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
}

/* --- 60th update advances the second and sets dirty --- */

void test_update_advances_second_at_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 60u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(1u, hud_get_seconds());
}

void test_update_dirty_after_60_frames(void) {
    uint8_t i;
    for (i = 0u; i < 60u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT8(1u, hud_is_dirty());
}

/* --- hud_render() clears the dirty flag --- */

void test_render_clears_dirty(void) {
    uint8_t i;
    for (i = 0u; i < 60u; i++) hud_update();
    hud_render();
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
}

/* --- Frame tick wraps: second frame after render advances normally --- */

void test_second_frame_after_render(void) {
    uint8_t i;
    /* First second */
    for (i = 0u; i < 60u; i++) hud_update();
    hud_render();
    /* 59 more updates should NOT advance second again */
    for (i = 0u; i < 59u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(1u, hud_get_seconds());
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
    /* 60th update DOES advance second */
    hud_update();
    TEST_ASSERT_EQUAL_UINT16(2u, hud_get_seconds());
    TEST_ASSERT_EQUAL_UINT8(1u, hud_is_dirty());
}

/* --- Three seconds: 180 updates --- */

void test_three_seconds(void) {
    uint8_t i;
    for (i = 0u; i < 180u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(3u, hud_get_seconds());
}

/* --- One minute: 3600 updates --- */

void test_one_minute(void) {
    uint16_t i;
    for (i = 0u; i < 3600u; i++) hud_update();
    TEST_ASSERT_EQUAL_UINT16(60u, hud_get_seconds());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_seconds_zero);
    RUN_TEST(test_init_dirty_clear);
    RUN_TEST(test_update_no_second_before_60_frames);
    RUN_TEST(test_update_not_dirty_before_60_frames);
    RUN_TEST(test_update_advances_second_at_60_frames);
    RUN_TEST(test_update_dirty_after_60_frames);
    RUN_TEST(test_render_clears_dirty);
    RUN_TEST(test_second_frame_after_render);
    RUN_TEST(test_three_seconds);
    RUN_TEST(test_one_minute);
    return UNITY_END();
}
```

**Step 2: Run tests — expect FAIL (hud.c doesn't exist yet)**

```bash
make test 2>&1 | grep -E "test_hud|error|FAIL|PASS"
```

Expected: compile error — `hud_init`, `hud_update`, etc. not found.

---

## Task 5: Create `src/hud.c` (TDD green phase)

**Files:**
- Create: `src/hud.c`

**Step 1: Write `src/hud.c`**

Key design decisions embedded in comments:
- `__code` storage class keeps the font tile array in ROM (not WRAM copy).
- Tile index offset `HUD_FONT_BASE = 128` avoids collision with track tiles (0–127).
- Font tiles use only color 0 (background) and color 3 (foreground) — so each row pair is `(bitmask, bitmask)`.
- `hud_render()` only writes 5 timer tiles when dirty — not the full 20-tile row.
- `hud_init()` writes the full row 0 (HP + timer) and blank row 1 while display is OFF (safe).

```c
#include <gb/gb.h>
#include "config.h"
#include "hud.h"

/* --- Tile index constants --- */
#define HUD_FONT_BASE  128u  /* first font tile in BG tile data — above track tiles */
#define HUD_FONT_COUNT  14u  /* tiles: 0-9 (10) + H(10) + P(11) + :(12) + space(13) */
#define HUD_TILE_H      10u
#define HUD_TILE_P      11u
#define HUD_TILE_COLON  12u
#define HUD_TILE_SPACE  13u

/* --- Font tile data (2bpp, 8x8 each, color 0 + color 3 only)
 *
 * Glyph layout: 5 pixels wide, bits 7..3, 7 rows tall, 1 blank row at bottom.
 * Each row pair: (pattern, pattern) — lo==hi for monochrome (color 3).
 *
 * Order: digits 0–9, then H, P, colon, space.
 */
static const uint8_t __code hud_font_tiles[] = {
    /* 0: .###. / #...# / #...# / #...# / #...# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 1: ..#.. / .##.. / ..#.. / ..#.. / ..#.. / ..#.. / .###. / ..... */
    0x20,0x20, 0x60,0x60, 0x20,0x20, 0x20,0x20, 0x20,0x20, 0x20,0x20, 0x70,0x70, 0x00,0x00,
    /* 2: .###. / #...# / ....# / ..##. / .#... / #.... / ##### / ..... */
    0x70,0x70, 0x88,0x88, 0x08,0x08, 0x30,0x30, 0x40,0x40, 0x80,0x80, 0xF8,0xF8, 0x00,0x00,
    /* 3: .###. / #...# / ....# / ..##. / ....# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x08,0x08, 0x30,0x30, 0x08,0x08, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 4: #...# / #...# / #...# / ##### / ....# / ....# / ....# / ..... */
    0x88,0x88, 0x88,0x88, 0x88,0x88, 0xF8,0xF8, 0x08,0x08, 0x08,0x08, 0x08,0x08, 0x00,0x00,
    /* 5: ##### / #.... / #.... / ####. / ....# / ....# / .###. / ..... */
    0xF8,0xF8, 0x80,0x80, 0x80,0x80, 0xF0,0xF0, 0x08,0x08, 0x08,0x08, 0x70,0x70, 0x00,0x00,
    /* 6: .###. / #.... / #.... / ####. / #...# / #...# / .###. / ..... */
    0x70,0x70, 0x80,0x80, 0x80,0x80, 0xF0,0xF0, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 7: ##### / ....# / ...#. / ...#. / ..#.. / ..#.. / ..#.. / ..... */
    0xF8,0xF8, 0x08,0x08, 0x10,0x10, 0x10,0x10, 0x20,0x20, 0x20,0x20, 0x20,0x20, 0x00,0x00,
    /* 8: .###. / #...# / #...# / .###. / #...# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x88,0x88, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* 9: .###. / #...# / #...# / .#### / ....# / #...# / .###. / ..... */
    0x70,0x70, 0x88,0x88, 0x88,0x88, 0x78,0x78, 0x08,0x08, 0x88,0x88, 0x70,0x70, 0x00,0x00,
    /* H: #...# / #...# / #...# / ##### / #...# / #...# / #...# / ..... */
    0x88,0x88, 0x88,0x88, 0x88,0x88, 0xF8,0xF8, 0x88,0x88, 0x88,0x88, 0x88,0x88, 0x00,0x00,
    /* P: ####. / #...# / #...# / ####. / #.... / #.... / #.... / ..... */
    0xF0,0xF0, 0x88,0x88, 0x88,0x88, 0xF0,0xF0, 0x80,0x80, 0x80,0x80, 0x80,0x80, 0x00,0x00,
    /* :: ..... / ..##. / ..##. / ..... / ..... / ..##. / ..##. / ..... */
    0x00,0x00, 0x30,0x30, 0x30,0x30, 0x00,0x00, 0x00,0x00, 0x30,0x30, 0x30,0x30, 0x00,0x00,
    /* ' ' (space): all zeros */
    0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00,
};

/* --- Module state --- */
static uint8_t  hud_hp;           /* current HP value */
static uint8_t  hud_frame_tick;   /* 0–59, resets each second */
static uint16_t hud_seconds;      /* total elapsed seconds */
static uint8_t  hud_dirty;        /* 1 = timer tiles need rewrite */

/* --- Public API --- */

void hud_init(void) {
    static uint8_t row0[20];
    static uint8_t row1[20];
    uint8_t i;

    hud_hp         = PLAYER_HP_MAX;
    hud_frame_tick = 0u;
    hud_seconds    = 0u;
    hud_dirty      = 0u;

    /* Load font tile patterns into BG/Win tile data starting at tile 128 */
    set_bkg_data(HUD_FONT_BASE, HUD_FONT_COUNT, hud_font_tiles);

    /* Build row 0: HP:100 at cols 0-5, spaces at 6-14, 00:00 at cols 15-19 */
    for (i = 0u; i < 20u; i++) row0[i] = HUD_FONT_BASE + HUD_TILE_SPACE;
    row0[0]  = HUD_FONT_BASE + HUD_TILE_H;
    row0[1]  = HUD_FONT_BASE + HUD_TILE_P;
    row0[2]  = HUD_FONT_BASE + HUD_TILE_COLON;
    row0[3]  = HUD_FONT_BASE + 1u;            /* digit '1' */
    row0[4]  = HUD_FONT_BASE + 0u;            /* digit '0' */
    row0[5]  = HUD_FONT_BASE + 0u;            /* digit '0' */
    row0[15] = HUD_FONT_BASE + 0u;            /* MM tens */
    row0[16] = HUD_FONT_BASE + 0u;            /* MM units */
    row0[17] = HUD_FONT_BASE + HUD_TILE_COLON;
    row0[18] = HUD_FONT_BASE + 0u;            /* SS tens */
    row0[19] = HUD_FONT_BASE + 0u;            /* SS units */

    /* Build blank row 1 (reserved for future use) */
    for (i = 0u; i < 20u; i++) row1[i] = HUD_FONT_BASE + HUD_TILE_SPACE;

    /* LCDC bit 6: Window tile map uses 0x9C00 (where set_win_tiles writes) */
    LCDC_REG |= LCDCF_WIN9C00;

    /* Pin window to bottom 2 tile rows: WX=7 (left edge), WY=128 (pixel row 128) */
    move_win(7u, 128u);
    SHOW_WIN;

    /* Write initial tile data to window tile map — safe: display is OFF here */
    set_win_tiles(0u, 0u, 20u, 1u, row0);
    set_win_tiles(0u, 1u, 20u, 1u, row1);
}

void hud_update(void) {
    hud_frame_tick++;
    if (hud_frame_tick >= 60u) {
        hud_frame_tick = 0u;
        hud_seconds++;
        hud_dirty = 1u;
    }
}

void hud_render(void) {
    uint8_t mm, ss;
    uint8_t timer[5];

    if (!hud_dirty) return;

    mm = (uint8_t)(hud_seconds / 60u);
    ss = (uint8_t)(hud_seconds % 60u);
    timer[0] = HUD_FONT_BASE + (uint8_t)(mm / 10u);
    timer[1] = HUD_FONT_BASE + (uint8_t)(mm % 10u);
    timer[2] = HUD_FONT_BASE + HUD_TILE_COLON;
    timer[3] = HUD_FONT_BASE + (uint8_t)(ss / 10u);
    timer[4] = HUD_FONT_BASE + (uint8_t)(ss % 10u);
    set_win_tiles(15u, 0u, 5u, 1u, timer);
    hud_dirty = 0u;
}

void hud_set_hp(uint8_t hp) {
    hud_hp    = hp;
    hud_dirty = 1u;
}

uint16_t hud_get_seconds(void) { return hud_seconds; }
uint8_t  hud_is_dirty(void)    { return hud_dirty;   }
```

**Step 2: Run tests — expect PASS**

```bash
make test 2>&1 | grep -E "test_hud|FAIL|PASS|OK"
```

Expected: `10 Tests, 0 Failures, 0 Ignored` for the hud test suite.

**Step 3: Run all tests to confirm no regressions**

```bash
make test 2>&1 | tail -5
```

Expected: all test suites pass.

**Step 4: Commit**

```bash
git add src/hud.h src/hud.c tests/test_hud.c
git commit -m "feat: hud module — race timer and HP display with dirty-flag rendering"
```

---

## Task 6: Integrate HUD into `state_playing.c`

**Files:**
- Modify: `src/state_playing.c`

**Step 1: Add `#include "hud.h"` at the top** (after existing includes)

```c
#include "hud.h"
```

**Step 2: Call `hud_init()` in `enter()`**, after `camera_init()` and before `DISPLAY_ON`:

```c
static void enter(void) {
    DISPLAY_OFF;
    track_init();
    camera_init(player_get_x(), player_get_y());
    hud_init();    /* ← add this line */
    DISPLAY_ON;
}
```

**Step 3: Add `hud_render()` in the VBlank phase and `hud_update()` in the game logic phase**:

```c
static void update(void) {
#ifdef DEBUG
    frame_count++;
    if (frame_count % 60u == 0u) {
        DBG_INT("frame", (int)frame_count);
        DBG_INT("px", (int)player_get_x());
        DBG_INT("py", (int)player_get_y());
    }
#endif
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    hud_render();           /* ← add this line */
    camera_flush_vram();
    /* Game logic phase: runs during active display */
    player_update();
    camera_update(player_get_x(), player_get_y());
    hud_update();           /* ← add this line */
}
```

**Step 4: Run all tests to confirm no regressions**

```bash
make test 2>&1 | tail -5
```

Expected: all pass.

**Step 5: Commit**

```bash
git add src/state_playing.c
git commit -m "feat: integrate hud_init/render/update into state_playing"
```

---

## Task 7: Build the ROM

**Step 1: Run the build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make 2>&1
```

Expected: `build/junk-runner.gb` produced with zero errors. Warnings about "so said EVELYN" are harmless and expected.

If compile errors appear:
- `LCDC_REG` / `LCDCF_WIN9C00` undefined → add `#include <gb/hardware.h>` to `hud.c`
- Any other error → read the GBDK error message and fix before continuing.

**Step 2: Commit the clean build (no extra files)**

If the build produced any generated files that changed, add them:
```bash
git status
```

If nothing new, no commit needed here.

---

## Task 8: Smoketest in Emulicious

**Step 1: Launch the emulator in the background**

```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/junk-runner.gb &
```

**Step 2: Tell the user to confirm the following in the emulator:**

> "The Emulicious emulator is running. Please confirm:
> 1. The play area (track + car) renders correctly in the top 16 tile rows.
> 2. A 2-row HUD panel is visible at the bottom of the screen.
> 3. `HP:100` appears on the left side of the HUD.
> 4. A timer starting at `00:00` is visible on the right side and increments in real time.
> 5. No graphical corruption or flickering."

Do NOT proceed to the PR until the user confirms the smoketest passes.

---

## Task 9: Create the Pull Request

After smoketest confirmation:

**Step 1: Push the branch**

```bash
gh auth setup-git 2>/dev/null; git push -u origin worktree-feat/hud
```

**Step 2: Create the PR**

```bash
gh pr create \
  --title "feat: HUD — race timer and HP display (#55)" \
  --body "$(cat <<'EOF'
## Summary
- Adds `hud` module (`src/hud.c` + `src/hud.h`) with Window-layer HUD pinned to bottom 2 tile rows
- Displays `HP:100` at the left and a `MM:SS` race timer at the right of row 0
- Timer counts up from `00:00` using frame ticks (60 frames = 1 second); dirty-flag rendering avoids redundant VRAM writes
- Font tiles (0–9, H, P, colon, space) loaded at tile index 128+ to avoid collision with track tiles
- `state_playing.c` calls `hud_init()` on enter, `hud_render()` in VBlank phase, `hud_update()` in logic phase

## Test plan
- [ ] `make test` passes (10 hud tests + all existing tests)
- [ ] `GBDK_HOME=/home/mathdaman/gbdk make` builds without errors
- [ ] Emulicious smoketest: HUD visible, timer increments, play area unaffected
- [ ] Closes #55

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Window tiles show garbage | `LCDCF_WIN9C00` not set | Confirm `LCDC_REG |= LCDCF_WIN9C00` runs in `hud_init()` |
| Window appears at wrong position | `move_win` args wrong | `move_win(7, 128)` — WX=7 (left edge), WY=128 (pixel 128 from top) |
| Track tiles corrupted | Font loaded at wrong index | Confirm `set_bkg_data(128, 14, ...)` — must not overlap track range |
| Timer increments too fast/slow | Wrong frame rate assumption | Game runs at 60 fps; 60 ticks = 1 second |
| `LCDC_REG` undefined in compiler | Header missing | Add `#include <gb/hardware.h>` to `src/hud.c` |
| Window shows BG tiles instead of font | LCDC bit 6 = 0 | `LCDCF_WIN9C00 = 0x40` must be ORed into `LCDC_REG` |
