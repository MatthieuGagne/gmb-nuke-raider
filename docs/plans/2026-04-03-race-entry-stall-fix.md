# Race Entry Stall Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate the 2-3s freeze when entering a race by pre-computing turret spawn positions at build time and replacing VBlank-polling `set_bkg_tiles()` calls in `camera_init()` with direct VRAM writes.

**Architecture:** Two independent fixes. Fix 1 extends the `tmx_to_c.py` pipeline to parse a Tiled object layer named `"turrets"` and emit SoA position arrays (`*_turret_tx[]`, `*_turret_ty[]`, `*_turret_count`) into each `*_map.c` file; `enemy_init()` reads from these ROM arrays via a new NONBANKED `load_turret_positions()` helper in `loader.c`. Fix 2 adds a `load_bkg_row()` NONBANKED helper that writes tile indices directly to VRAM (no VBlank wait); `camera_init()` uses a new `stream_row_direct()` helper (display-off path only) instead of the existing `stream_row()` (VBlank path, unchanged).

**Tech Stack:** Python 3 (`xml.etree.ElementTree`), Tiled TMX object layers, GBDK-2020, SDCC, Unity (host tests)

## Open questions (must resolve before starting)

- none

---

## Batch 1: Pipeline + Declarations (Tasks 1–3)

### Task 1: Update `tmx_to_c.py` to emit turret position arrays

**Files:**
- Modify: `tools/tmx_to_c.py`

**Depends on:** none
**Parallelizable with:** Task 2 — different files, no compile dependency between them

**Step 1: Write the content**

Add at the top of `tmx_to_c.py` (after `GID_CLEAR_FLAGS`):

```python
# Must match MAX_ENEMIES in src/config.h
MAX_TURRETS = 8
```

Add a new function after `gid_to_tile_id()`:

```python
def parse_turret_objects(root):
    """Extract turret spawn tile coords from the 'turrets' object layer.

    Objects must be named 'turret' and snapped to an 8px tile grid.
    Returns a list of (tx, ty) tuples capped at MAX_TURRETS.
    """
    turrets = []
    turret_group = next(
        (og for og in root.findall('objectgroup')
         if og.get('name') == 'turrets'),
        None
    )
    if turret_group is not None:
        for obj in turret_group.findall('object'):
            if obj.get('name') == 'turret':
                px = int(float(obj.get('x', 0)))
                py = int(float(obj.get('y', 0)))
                turrets.append((px // 8, py // 8))
    if len(turrets) > MAX_TURRETS:
        print(f"WARNING: {len(turrets)} turret objects found; "
              f"capped at {MAX_TURRETS} (MAX_ENEMIES in config.h)")
        turrets = turrets[:MAX_TURRETS]
    return turrets
```

In `tmx_to_c()`, call `parse_turret_objects(root)` after the `checkpoint_defs` block
(before `with open(out_path, 'w') as f:`):

```python
    turrets = parse_turret_objects(root)
    turret_count = len(turrets)
    tx_vals = [f'{t[0]}u' for t in turrets] + ['0u'] * (MAX_TURRETS - turret_count)
    ty_vals = [f'{t[1]}u' for t in turrets] + ['0u'] * (MAX_TURRETS - turret_count)
```

At the end of the `with open(out_path, 'w') as f:` block (after the checkpoint lines), append:

```python
        f.write(f"\nBANKREF({prefix}_turret_count)\n")
        f.write(f"const uint8_t {prefix}_turret_count = {turret_count}u;\n")
        f.write(f"BANKREF({prefix}_turret_tx)\n")
        f.write(f"const uint8_t {prefix}_turret_tx[{MAX_TURRETS}] = "
                f"{{ {', '.join(tx_vals)} }};\n")
        f.write(f"BANKREF({prefix}_turret_ty)\n")
        f.write(f"const uint8_t {prefix}_turret_ty[{MAX_TURRETS}] = "
                f"{{ {', '.join(ty_vals)} }};\n")
```

**Step 2: Verify (manual)**

Run the script on `track.tmx` directly (before Task 2 adds objects) and confirm:
- Output `track_map.c` compiles (make) without error
- `track_turret_count = 0u` is emitted (no objects yet = empty arrays)

```bash
python3 tools/tmx_to_c.py assets/maps/track.tmx /tmp/track_map_test.c --prefix track
grep "turret" /tmp/track_map_test.c
```

Expected: three lines with `_turret_count`, `_turret_tx`, `_turret_ty`.

**Step 3: Commit**

```bash
git add tools/tmx_to_c.py
git commit -m "feat(pipeline): emit turret spawn position arrays from tmx_to_c.py"
```

---

### Task 2: Add turret point objects to all three TMX files in Tiled

**Files:**
- Modify: `assets/maps/track.tmx`
- Modify: `assets/maps/track2.tmx`
- Modify: `assets/maps/track3.tmx`

**Depends on:** none
**Parallelizable with:** Task 1 — different files, no compile dependency

> This is a manual authoring step. Do NOT hand-edit TMX XML directly.
> Open each file in Tiled and use the UI to place objects.

**Step 1: Add turret object layer to each TMX**

For each of the three tracks:

1. Open the TMX in Tiled (`File → Open`, navigate to `assets/maps/`)
2. In the Layers panel, add a new **Object Layer** (`Layer → New → Object Layer`)
3. Name it exactly: `turrets`
4. Enable **Snap to Grid** (`View → Snapping → Snap to Grid`; tile size is 8×8)
5. Use the **Insert Point** tool (`Objects → Insert Point`) to place a point object at the
   pixel position of each `TILE_TURRET` tile (raw tile index 7 = GID 8 in Tiled's 1-based count)
6. Name each point object exactly: `turret` (double-click the object → Properties → Name)
7. Save the file

**How to identify TILE_TURRET tiles:** In Tiled, tile 8 in the tileset (1-indexed) is the turret tile. Use `View → Show Tile IDs` to overlay IDs on the map. Any tile showing ID 8 needs a `"turret"` point object at its top-left corner (snap to grid = exact tile corner).

Expected counts (from `gid=8` scan of current TMX files):
- `track.tmx`: 6 turret tiles → 6 point objects
- `track2.tmx`: 3 turret tiles → 3 point objects
- `track3.tmx`: 4 turret tiles → 4 point objects

**Step 2: Verify**

After saving all three files, confirm the object layer was written:

```bash
grep -c 'name="turret"' assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx
```

Expected: `6`, `3`, `4` respectively.

**Step 3: Commit**

```bash
git add assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx
git commit -m "feat(maps): add turret point objects to all three TMX files"
```

---

### Task 3: `track.c`/`track.h` — add `track_get_id()` and declare turret array symbols

**Files:**
- Modify: `src/track.h`
- Modify: `src/track.c`
- Modify: `tests/test_track.c`

**Depends on:** Tasks 1 and 2 must be committed and a clean build done before Task 3's build
step — the linker needs `BANKREF(track_turret_tx)` etc. to be present in the regenerated
`*_map.c` files.
**Parallelizable with:** none — writes `track.h`/`track.c` exclusively; must come after Tasks 1+2

**Step 1: Write the failing tests**

Append to `tests/test_track.c`:

```c
void test_track_get_id_returns_0_after_select_0(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_UINT8(0u, track_get_id());
}

void test_track_get_id_returns_1_after_select_1(void) {
    track_select(1u);
    TEST_ASSERT_EQUAL_UINT8(1u, track_get_id());
}

void test_track_get_id_returns_2_after_select_2(void) {
    track_select(2u);
    TEST_ASSERT_EQUAL_UINT8(2u, track_get_id());
}
```

Add to `RUN_TEST` block in `tests/test_track.c` `main()`:

```c
RUN_TEST(test_track_get_id_returns_0_after_select_0);
RUN_TEST(test_track_get_id_returns_1_after_select_1);
RUN_TEST(test_track_get_id_returns_2_after_select_2);
```

**Step 2: Run test to verify it fails**

```bash
make test
```

Expected: FAIL — `track_get_id` undefined.

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `bank-manifest.json` has entries for `src/track.c`
and `src/track.h` (both already exist — no new files, no new entries needed).

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm:
- `track_get_id()` declared `BANKED` is correct (autobank module, safe)
- `BANKREF_EXTERN` macro usage for the new turret symbols is correct
- `extern const uint8_t track_turret_tx[8]` size matches generated arrays

**Step 5: Write minimal implementation**

In `src/track.h`, after the existing `BANKREF_EXTERN(track2_map_type)` /
`BANKREF_EXTERN(track3_map_type)` block, add:

```c
/* Per-track turret spawn arrays — emitted by tmx_to_c.py into *_map.c */
extern const uint8_t  track_turret_count;
extern const uint8_t  track_turret_tx[8];
extern const uint8_t  track_turret_ty[8];
BANKREF_EXTERN(track_turret_count)
BANKREF_EXTERN(track_turret_tx)
BANKREF_EXTERN(track_turret_ty)

extern const uint8_t  track2_turret_count;
extern const uint8_t  track2_turret_tx[8];
extern const uint8_t  track2_turret_ty[8];
BANKREF_EXTERN(track2_turret_count)
BANKREF_EXTERN(track2_turret_tx)
BANKREF_EXTERN(track2_turret_ty)

extern const uint8_t  track3_turret_count;
extern const uint8_t  track3_turret_tx[8];
extern const uint8_t  track3_turret_ty[8];
BANKREF_EXTERN(track3_turret_count)
BANKREF_EXTERN(track3_turret_tx)
BANKREF_EXTERN(track3_turret_ty)

uint8_t track_get_id(void) BANKED;
```

In `src/track.c`, after `track_get_reward()`:

```c
uint8_t track_get_id(void) BANKED { return active_track_id; }
```

**Step 6: Run tests to verify they pass**

```bash
make test
```

Expected: PASS (all three new `track_get_id` tests + all prior tests).

**Step 7: HARD GATE — build**

First ensure Tasks 1+2 are committed (regenerated `*_map.c` files contain turret arrays):

```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify no bank budget exceeded.

**Step 9: Refactor checkpoint**

`track_get_id()` is a single-track getter — generalizes trivially. No hard-coded
assumptions for N>1 tracks. Proceed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/track.c` and `src/track.h`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/track.c src/track.h tests/test_track.c
git commit -m "feat(track): add track_get_id() getter and declare turret array symbols"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files — Python script and TMX assets |
| B (sequential) | Task 3 | Depends on Group A — link step needs regenerated `*_map.c` with turret symbols |

### Smoketest Checkpoint 1 — build succeeds with turret arrays in ROM; game plays normally

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors. Verify turret arrays appear in the generated map files:
```bash
grep "turret" src/track_map.c src/track2_map.c src/track3_map.c
```
Expected: six lines per file (`BANKREF`, count, tx, ty for each track).

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

Ask the user to navigate from title → overmap → enter a race and confirm:
- No regression: game still loads, enemies still appear, race plays normally
- No functional change expected yet (enemy_init still scans, camera still uses `set_bkg_tiles`)

---

## Batch 2: Helpers + Wiring (Tasks 4–6)

### Task 4: `loader.c`/`loader.h` + mock infrastructure — add `load_turret_positions()` and `load_bkg_row()`

**Files:**
- Modify: `src/loader.c`
- Modify: `src/loader.h`
- Modify: `tests/mocks/mock_bkg.c`
- Modify: `tests/mocks/gb/gb.h`
- Modify: `tests/test_loader.c`

**Depends on:** Task 3 (needs `track_turret_tx` etc. declared in `track.h`)
**Parallelizable with:** none — prerequisite for Tasks 5 and 6; writes `loader.c`/`loader.h` exclusively

**Step 1: Write the failing tests**

Append to `tests/test_loader.c`:

```c
void test_load_turret_positions_id0_returns_count(void) {
    uint8_t tx[8], ty[8], count = 99u;
    load_turret_positions(0u, tx, ty, &count);
    /* track has 6 turrets from Task 2 Tiled authoring */
    TEST_ASSERT_EQUAL_UINT8(6u, count);
}

void test_load_turret_positions_id1_returns_count(void) {
    uint8_t tx[8], ty[8], count = 99u;
    load_turret_positions(1u, tx, ty, &count);
    /* track2 has 3 turrets */
    TEST_ASSERT_EQUAL_UINT8(3u, count);
}

void test_load_turret_positions_id2_returns_count(void) {
    uint8_t tx[8], ty[8], count = 99u;
    load_turret_positions(2u, tx, ty, &count);
    /* track3 has 4 turrets */
    TEST_ASSERT_EQUAL_UINT8(4u, count);
}

void test_load_bkg_row_increments_mock_count(void) {
    uint8_t tiles[4] = { 1u, 2u, 3u, 4u };
    int before = mock_load_bkg_row_call_count;
    load_bkg_row(0u, 0u, 4u, tiles);
    TEST_ASSERT_EQUAL_INT(before + 1, mock_load_bkg_row_call_count);
}

void test_load_bkg_row_writes_to_mock_vram(void) {
    uint8_t tiles[3] = { 5u, 6u, 7u };
    mock_vram_clear();
    load_bkg_row(2u, 1u, 3u, tiles);
    TEST_ASSERT_EQUAL_UINT8(5u, mock_vram[1u * 32u + 2u]);
    TEST_ASSERT_EQUAL_UINT8(6u, mock_vram[1u * 32u + 3u]);
    TEST_ASSERT_EQUAL_UINT8(7u, mock_vram[1u * 32u + 4u]);
}
```

Add `RUN_TEST` calls for all five new tests in `main()`.

> **Note on turret count tests:** These test the actual per-track turret counts from the Tiled
> authoring in Task 2. If those counts change, update the expected values here accordingly.

**Step 2: Run test to verify it fails**

```bash
make test
```

Expected: FAIL — `load_turret_positions` and `load_bkg_row` undefined; `mock_load_bkg_row_call_count` undefined.

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `bank-manifest.json` has entries for `src/loader.c`
and `src/loader.h` (both exist — no new files, no new entries needed).

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm:
- `SWITCH_ROM` + `CURRENT_BANK` pattern for `load_turret_positions()` is correct
- Raw volatile pointer arithmetic for BG tilemap (`0x9800u + row*32 + col`) is correct on SM83
- `NONBANKED` on both helpers is appropriate (bank-0 VRAM writers)
- Writing to `0x9800` directly while display is OFF and VBK=0 is safe on CGB

**Step 5: Write minimal implementation**

**`tests/mocks/mock_bkg.c`** — add `mock_load_bkg_row_call_count` and its mock:

```c
/* Tracks load_bkg_row calls (display-off direct VRAM write path) */
int mock_load_bkg_row_call_count = 0;
```

In `mock_vram_clear()`, add:

```c
    mock_load_bkg_row_call_count = 0;
```

At end of `mock_bkg.c`, add:

```c
/* Mock for direct VRAM row write (no VBlank wait) */
void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) {
    uint8_t i;
    mock_load_bkg_row_call_count++;
    for (i = 0u; i < count; i++) {
        uint8_t vx = (uint8_t)((vram_x + i) & 31u);
        mock_vram[(uint16_t)(vram_y & 31u) * 32u + vx] = tiles[i];
    }
}
```

**`tests/mocks/gb/gb.h`** — add after the `mock_set_bkg_tiles_call_count` extern:

```c
extern int mock_load_bkg_row_call_count;
```

**`src/loader.h`** — add after existing NONBANKED declarations:

```c
void load_turret_positions(uint8_t id,
                            uint8_t *out_tx,
                            uint8_t *out_ty,
                            uint8_t *out_count) NONBANKED;
void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) NONBANKED;
```

**`src/loader.c`** — add externs near top (after existing `BANKREF_EXTERN` declarations):

```c
BANKREF_EXTERN(track_turret_count)
BANKREF_EXTERN(track_turret_tx)
BANKREF_EXTERN(track_turret_ty)
BANKREF_EXTERN(track2_turret_count)
BANKREF_EXTERN(track2_turret_tx)
BANKREF_EXTERN(track2_turret_ty)
BANKREF_EXTERN(track3_turret_count)
BANKREF_EXTERN(track3_turret_tx)
BANKREF_EXTERN(track3_turret_ty)
```

Then add after the existing loader functions:

```c
void load_turret_positions(uint8_t id,
                            uint8_t *out_tx,
                            uint8_t *out_ty,
                            uint8_t *out_count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 1u) {
        SWITCH_ROM(BANK(track2_turret_count));
        n = track2_turret_count;
        for (i = 0u; i < n; i++) {
            out_tx[i] = track2_turret_tx[i];
            out_ty[i] = track2_turret_ty[i];
        }
    } else if (id == 2u) {
        SWITCH_ROM(BANK(track3_turret_count));
        n = track3_turret_count;
        for (i = 0u; i < n; i++) {
            out_tx[i] = track3_turret_tx[i];
            out_ty[i] = track3_turret_ty[i];
        }
    } else {
        SWITCH_ROM(BANK(track_turret_count));
        n = track_turret_count;
        for (i = 0u; i < n; i++) {
            out_tx[i] = track_turret_tx[i];
            out_ty[i] = track_turret_ty[i];
        }
    }
    *out_count = n;
    SWITCH_ROM(saved);
}

void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) NONBANKED {
    uint8_t i;
    volatile uint8_t *dst = (volatile uint8_t *)
        (0x9800u + ((uint16_t)(vram_y & 31u) << 5u) + (vram_x & 31u));
    for (i = 0u; i < count; i++) dst[i] = tiles[i];
}
```

**Step 6: Run tests to verify they pass**

```bash
make test
```

Expected: PASS (all five new tests + all prior tests).

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify no bank budget exceeded.

**Step 9: Refactor checkpoint**

`load_turret_positions()` uses `if/else if/else` over track IDs matching the existing
`load_track_header()` and `load_checkpoints()` pattern — consistent with established
multi-track dispatch. No generalisation issue for current 3-track scope. Proceed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/loader.c` and `src/loader.h`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/loader.c src/loader.h \
        tests/mocks/mock_bkg.c tests/mocks/gb/gb.h \
        tests/test_loader.c
git commit -m "feat(loader): add load_turret_positions() and load_bkg_row() NONBANKED helpers"
```

---

### Task 5: `camera.c` — replace `set_bkg_tiles()` in `camera_init()` with direct VRAM writes

**Files:**
- Modify: `src/camera.c`
- Modify: `tests/test_camera.c`

**Depends on:** Task 4 (`load_bkg_row()` must exist in `loader.h`)
**Parallelizable with:** Task 6 — different output files (`camera.c` vs `enemy.c`), no shared state

**Step 1: Write the failing test**

In `tests/test_camera.c`, replace the body of `test_camera_init_preloads_18_rows`:

```c
void test_camera_init_preloads_18_rows(void) {
    /* camera_init() must use load_bkg_row() (display-off direct write),
     * NOT set_bkg_tiles() (which polls VBlank). */
    mock_vram_clear();
    active_map_w = 20u;
    active_map_h = 100u;
    camera_init(88, 8);
    /* cam_y=8 -> first_row=1; preloads rows 1-18 = 18 load_bkg_row calls */
    TEST_ASSERT_EQUAL_INT(18, mock_load_bkg_row_call_count);
    /* Must NOT call set_bkg_tiles during init (no VBlank stall) */
    TEST_ASSERT_EQUAL_INT(0, mock_set_bkg_tiles_call_count);
}
```

**Step 2: Run test to verify it fails**

```bash
make test
```

Expected: FAIL — `mock_load_bkg_row_call_count` is 0 (camera_init still calls `set_bkg_tiles`).

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `bank-manifest.json` has an entry for `src/camera.c`
(already exists — no new file, no new entry needed).

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm:
- `stream_row_direct()` as a `static` function calling `load_bkg_row()` from a BANKED module is correct
- The split-write logic (when `vram_x + VIS_COLS > 32`) must be preserved in `stream_row_direct()`
- `load_bkg_row()` is NONBANKED (bank 0) — callable from any BANKED module safely

**Step 5: Write minimal implementation**

In `src/camera.c`, add `#include "loader.h"` if not already present.

Add a new `static` function immediately before `camera_init()`:

```c
/* stream_row_direct — display-OFF path only.
 * Writes one tile row directly to VRAM (no VBlank wait).
 * Call only when LCD is disabled (e.g. during camera_init).
 * For the VBlank streaming path use stream_row() instead. */
static void stream_row_direct(uint8_t world_ty) {
    uint8_t vram_y = world_ty & 31u;
    uint8_t vram_x = cam_tile_x_snap & 31u;
    uint8_t first_count;
    track_fill_row_range(world_ty, cam_tile_x_snap, VIS_COLS, row_buf);
    if ((uint8_t)(vram_x + VIS_COLS) > 32u) {
        first_count = 32u - vram_x;
        load_bkg_row(vram_x, vram_y, first_count, row_buf);
        load_bkg_row(0u,     vram_y, (uint8_t)(VIS_COLS - first_count),
                     row_buf + first_count);
    } else {
        load_bkg_row(vram_x, vram_y, VIS_COLS, row_buf);
    }
}
```

In `camera_init()`, replace the `stream_row(ty)` call inside the preload loop with
`stream_row_direct(ty)`. The loop itself is unchanged:

```c
    for (ty = first_row; ty < first_row + 18u && ty < active_map_h; ty++) {
        stream_row_direct(ty);   /* was: stream_row(ty) */
    }
```

`stream_row()` is NOT changed — it remains the VBlank streaming path used by
`camera_flush_vram()` and `camera_update()`.

**Step 6: Run tests to verify they pass**

```bash
make test
```

Expected: PASS (updated `test_camera_init_preloads_18_rows` + all prior camera tests).

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify no bank budget exceeded.

**Step 9: Refactor checkpoint**

Two separate functions (`stream_row_direct` / `stream_row`) for two distinct call contexts is
the correct design — no generalisation issue. Proceed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/camera.c`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/camera.c tests/test_camera.c
git commit -m "perf(camera): use direct VRAM writes in camera_init() — no VBlank stall"
```

---

### Task 6: `enemy.c` — replace tilemap scan in `enemy_init()` with `load_turret_positions()`

**Files:**
- Modify: `src/enemy.c`
- Modify: `src/enemy.h`

**Depends on:** Task 3 (`track_get_id()`) and Task 4 (`load_turret_positions()`)
**Parallelizable with:** Task 5 — different output files, no shared state

> No new unit tests are added here: host tests use `enemy_init_empty()` exclusively
> (real `enemy_init()` requires hardware-banked track data). Correctness is verified by the
> Smoketest 2 integration check (enemies spawn at expected positions).

**Step 1: (No new failing test — see note above)**

Verify existing enemy tests still pass before touching `enemy.c`:

```bash
make test
```

Expected: all tests PASS (baseline confirmation).

**Step 2: (No new test to run red)**

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `bank-manifest.json` has entries for `src/enemy.c`
and `src/enemy.h` (both exist — no new files, no new entries needed).

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm:
- Calling `track_get_id()` (BANKED) from `enemy_init()` (BANKED) is safe via GBDK trampolines
- Passing `enemy_tx` and `enemy_ty` (WRAM static arrays) as `out_tx`/`out_ty` to the NONBANKED
  `load_turret_positions()` is correct — WRAM addresses are accessible from bank 0

**Step 5: Write minimal implementation**

In `src/enemy.c`, replace `enemy_init()` (the nested tilemap scan) with:

```c
void enemy_init(void) BANKED {
    uint8_t i;
    uint8_t count = 0u;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        enemy_active[i] = 0u;
        enemy_oam[i]    = SPRITE_POOL_INVALID;
    }
    load_turret_tiles();
    load_turret_positions(track_get_id(), enemy_tx, enemy_ty, &count);
    for (i = 0u; i < count; i++) {
        _spawn_at(i, enemy_tx[i], enemy_ty[i]);
    }
}
```

Add `#include "loader.h"` at the top of `src/enemy.c` if not already present.

In `src/enemy.h`, update the `enemy_init` comment:

```c
/* Initialise enemy pool from pre-computed turret positions in ROM.
 * Reads track_get_id() to select the correct per-track array.
 * Must be called after track_select(). */
void enemy_init(void) BANKED;
```

**Step 6: Run tests to verify they pass**

```bash
make test
```

Expected: PASS (no enemy tests changed; all prior tests still pass).

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Verify no bank budget exceeded.

**Step 9: Refactor checkpoint**

`enemy_init()` now reads `count` from the ROM array (capped at `MAX_ENEMIES` by the pipeline).
The `_spawn_at()` loop is bounded by `count`. Generalises correctly for any number of turrets
≤ `MAX_ENEMIES`. Proceed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/enemy.c` and `src/enemy.h`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/enemy.c src/enemy.h
git commit -m "perf(enemy): read turret positions from ROM array instead of tilemap scan"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 2

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 4 | Prerequisite — defines `load_turret_positions()` and `load_bkg_row()` |
| B (parallel) | Task 5, Task 6 | Both depend on Task 4; write different files (`camera.c`, `enemy.c`) |

### Smoketest Checkpoint 2 — no race entry stall; enemies spawn correctly; camera renders correctly

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

Ask the user to verify:
1. **No stall:** Navigate to a race node on the overmap and enter. The screen should transition
   to the race within ~1 frame — no visible freeze, no music stutter.
2. **Enemies spawn:** Turrets appear on the track at their expected positions.
3. **Camera correct:** Track tilemap renders correctly from the start of the race
   (no missing rows, no garbage tiles).
4. **All tracks:** Test at least two different tracks to confirm turret counts are correct.
5. **Hub entry:** Confirm hub state entry is unaffected (no regression).
