# Center Dash Tile Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a solid center-dash tile (tile 2) to the track map every 5 rows, making camera scrolling visually obvious in the emulator.

**Architecture:** Two data-only edits — add the tile pixel data to `track_tiles.c`, then stamp it into the two center road columns on every 5th row in `track_map.c`. No logic changes; tile 2 is treated as road (passable) by the existing collision system.

**Tech Stack:** GBDK-2020, SDCC, make

---

### Task 1: Add tile 2 to track_tiles.c

**Files:**
- Modify: `src/track_tiles.c`

The tile data array currently has 2 tiles (16 bytes each). Append tile 2: 16 bytes all `0xFF` (solid black, all pixels on).

**Step 1: Edit `src/track_tiles.c`**

Replace:
```c
/* tile 1 */ 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
};

const uint8_t track_tile_data_count = 2u;
```

With:
```c
/* tile 1 */ 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
    /* tile 2 */ 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
};

const uint8_t track_tile_data_count = 3u;
```

**Step 2: Build to verify no compile errors**

```bash
cd /home/mathdaman/code/gmb-wasteland-racer/.worktrees/feat-upward-scroll
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: `build/wasteland-racer.gb` produced, no errors.

**Step 3: Commit**

```bash
git add src/track_tiles.c
git commit -m "feat: add solid center-dash tile (tile 2) to track tileset"
```

---

### Task 2: Stamp center-dash tile into track_map.c every 5 rows

**Files:**
- Modify: `src/track_map.c`

The map has 100 rows × 20 cols. Road center columns vary by section:
- rows 0–49: center cols are 9 and 10
- rows 50–74: center cols are 10 and 11
- rows 75–99: center cols are 11 and 12

On every 5th row (`row % 5 == 0`: rows 0, 5, 10, 15, …), replace the two center road columns with `2` instead of `1`.

**Step 1: Remove the stale generated-file comment at top of `src/track_map.c`**

Replace:
```c
/* GENERATED — do not edit by hand. Source: assets/maps/track.tmx */
/* Regenerate: python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c */
```

With:
```c
/* Hand-edited track map. 100 rows × 20 cols. tile 0=sand, 1=road, 2=center-dash */
```

**Step 2: Update every 5th row in the road section (rows 0–49, center cols 9–10)**

Rows 0, 5, 10, 15, 20, 25, 30, 35, 40, 45 — change cols 9 and 10 from `1` to `2`.

Example — row 0 before:
```c
    /* row  0 */ 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,
```
Row 0 after (col 9 and 10 → 2):
```c
    /* row  0 */ 0,0,0,0,1,1,1,1,1,2,2,1,1,1,1,1,0,0,0,0,
```

Apply the same pattern to rows 5, 10, 15, 20, 25, 30, 35, 40, 45.

**Step 3: Update every 5th row in the shifted section (rows 50–74, center cols 10–11)**

Rows 50, 55, 60, 65, 70 — change cols 10 and 11 from `1` to `2`.

Row 50 before:
```c
    /* row 50 */ 0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,
```
Row 50 after:
```c
    /* row 50 */ 0,0,0,0,0,1,1,1,1,1,2,2,1,1,1,1,1,0,0,0,
```

Apply to rows 55, 60, 65, 70.

**Step 4: Update every 5th row in the far-shifted section (rows 75–99, center cols 11–12)**

Rows 75, 80, 85, 90, 95 — change cols 11 and 12 from `1` to `2`.

Row 75 before:
```c
    /* row 75 */ 0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,
```
Row 75 after:
```c
    /* row 75 */ 0,0,0,0,0,0,1,1,1,1,1,2,2,1,1,1,1,1,0,0,
```

Apply to rows 80, 85, 90, 95.

**Step 5: Build to verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: clean build, `build/wasteland-racer.gb` produced.

**Step 6: Run tests to confirm no regression**

```bash
make test
```

Expected: 50 tests pass, 0 failures.

**Step 7: Commit**

```bash
git add src/track_map.c
git commit -m "feat: stamp center-dash tile every 5 rows for scroll debug visibility"
```
