# Race and Combat Map Types Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `map_type` support to the playing-state pipeline so TMX maps can be either `race` (existing behaviour) or `combat` (finish line once, no lap/checkpoint gate, no lap HUD).

**Architecture:** `tmx_to_c.py` reads a new `map_type` map property and emits a `const uint8_t {prefix}_map_type` constant. `track.c` caches the value in `active_map_type` at `track_select()` time and exposes it via `track_get_map_type()`. `state_playing.c` caches the type at `enter()` and branches its finish-line logic. `hud.c` accepts `map_type` + `lap_total` at init time and skips the lap counter columns for combat maps.

**Tech Stack:** C (SDCC/GBDK-2020), Python (tmx_to_c.py pipeline), Tiled (TMX map authoring), Unity (host-side tests).

## Open questions (must resolve before starting)

- None — all resolved in grill-me session.

---

## Batch 1 — Pipeline + Asset Changes

### Task 1: Update tmx_to_c.py to emit track_map_type

**Files:**
- Modify: `tools/tmx_to_c.py`

**Depends on:** none
**Parallelizable with:** none — Task 2 and 3 require this change to regenerate correctly.

**Step 1: Write the change**

In `tools/tmx_to_c.py`, after the existing map property parsing block, read the `map_type` property and emit the constant. Find where the file emits `{prefix}_start_x` and add the new emission nearby.

Add reading of the `map_type` map-level custom property:

```python
# Read map_type property (map-level custom properties)
map_type_val = 0  # default: TRACK_TYPE_RACE
map_props_el = root.find('properties')
if map_props_el is not None:
    for p in map_props_el.findall('property'):
        if p.get('name') == 'map_type':
            val = p.get('value', 'race')
            map_type_val = 0 if val == 'race' else 1
```

Emit the constant in the output C file, following the same `BANKREF` + `const` pattern as existing symbols:

```python
out.write(f'BANKREF({prefix}_map_type)\n')
out.write(f'const uint8_t {prefix}_map_type = {map_type_val}u;\n\n')
```

**Step 2: Verify with Python tool tests**

```bash
cd /path/to/worktree
PYTHONPATH=. python3 -m unittest tests.test_tmx_to_c -v
```
Expected: all tests pass. If `test_tmx_to_c` doesn't cover the new property yet, that's OK — test coverage is added in Task 2/3.

**Step 3: Commit**

```bash
git add tools/tmx_to_c.py
git commit -m "feat: tmx_to_c.py emits track_map_type constant from map_type property"
```

---

### Task 2: Add map_type="race" to track.tmx and track2.tmx, regenerate C files

**Files:**
- Modify: `assets/maps/track.tmx`
- Modify: `assets/maps/track2.tmx`
- Regenerate: `src/track_map.c`, `src/track2_map.c`

**Depends on:** Task 1
**Parallelizable with:** Task 3 (different TMX files and output C files)

**Step 1: Add map property to both TMX files**

Open each TMX in a text editor or Tiled. Add a map-level `<properties>` block (or append to an existing one) at the top of the `<map>` element:

```xml
<properties>
  <property name="map_type" value="race"/>
</properties>
```

For `track.tmx` and `track2.tmx` — same change to both.

**Step 2: Regenerate track_map.c**

```bash
python3 tools/tmx_to_c.py assets/maps/track.tmx src/track_map.c
```

Verify `src/track_map.c` now contains:
```c
BANKREF(track_map_type)
const uint8_t track_map_type = 0u;
```

**Step 3: Regenerate track2_map.c**

```bash
python3 tools/tmx_to_c.py assets/maps/track2.tmx src/track2_map.c --prefix track2
```

Verify `src/track2_map.c` contains:
```c
BANKREF(track2_map_type)
const uint8_t track2_map_type = 0u;
```

**Step 4: Commit**

```bash
git add assets/maps/track.tmx assets/maps/track2.tmx src/track_map.c src/track2_map.c
git commit -m "feat: add map_type=race property to track.tmx and track2.tmx"
```

---

### Task 3: Create track3.tmx (combat test map) and generate track3_map.c

**Files:**
- Create: `assets/maps/track3.tmx`
- Create: `src/track3_map.c`

**Depends on:** Task 1
**Parallelizable with:** Task 2

**Step 1: Create track3.tmx**

Create a minimal 20×20 Tiled map named `assets/maps/track3.tmx`. It is a linear combat map — no loop required. Structure:

- Dimensions: 20 columns × 20 rows, tile size 8×8 px
- Tile layer named `"tiles"` using the existing tileset (`tileset.png`, tile size 8×8)
- Map-level property: `map_type = "combat"`
- Road corridor: cols 4–15 (12 tiles wide), all rows = tile index 1 (TILE_ROAD)
- Remaining columns: tile index 0 (TILE_WALL/off-road)
- TILE_FINISH row: row 18 (tile index 6) in cols 4–15
- Spawn position: col 8, row 2 (pixel coords: 8×8=64, 2×8=16 → spawn_x=64+4=68, spawn_y=16+4=20... use object at pixel (68, 20))
- No checkpoints (omit the checkpoints objectgroup entirely)

TMX format follows the same structure as `track.tmx` and `track2.tmx`. The key map-level property block:

```xml
<properties>
  <property name="map_type" value="combat"/>
</properties>
```

**Step 2: Generate track3_map.c**

```bash
python3 tools/tmx_to_c.py assets/maps/track3.tmx src/track3_map.c --prefix track3
```

Verify `src/track3_map.c` contains:
```c
/* GENERATED — do not edit by hand. Source: assets/maps/track3.tmx */
#pragma bank 255
...
BANKREF(track3_map_type)
const uint8_t track3_map_type = 1u;
...
const uint8_t track3_checkpoint_count = 0u;
```

**Step 3: Commit**

```bash
git add assets/maps/track3.tmx src/track3_map.c
git commit -m "feat: add combat test track (track3.tmx) and generated track3_map.c"
```

---

### Task 4: Add track3_map.c to bank-manifest.json and Makefile

**Files:**
- Modify: `bank-manifest.json`
- Modify: `Makefile`

**Depends on:** Task 3
**Parallelizable with:** none — depends on Task 3.

**Step 1: Add to bank-manifest.json**

Add the entry for `src/track3_map.c` in `bank-manifest.json`, following the pattern of `track2_map.c`:

```json
"src/track3_map.c": {
  "bank": 255,
  "reason": "autobank — generated from track3.tmx; independently autobanked from track_map.c"
}
```

**Step 2: Add Makefile rule**

In `Makefile`, after the `src/track2_map.c` rule, add:

```makefile
src/track3_map.c: assets/maps/track3.tmx tools/tmx_to_c.py
	python3 tools/tmx_to_c.py assets/maps/track3.tmx src/track3_map.c --prefix track3
```

And add the dependency line:

```makefile
$(TARGET): src/track3_map.c
```

Place it immediately after `$(TARGET): src/track_map.c src/track2_map.c`.

**Step 3: Verify**

```bash
python3 tools/bank_check.py .
```
Expected: no error about missing entry for `src/track3_map.c`.

**Step 4: Commit**

```bash
git add bank-manifest.json Makefile
git commit -m "feat: register track3_map.c in bank-manifest.json and Makefile"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 1 | Must run before Tasks 2 and 3 |
| B (parallel) | Task 2, Task 3 | Both depend on Task 1; write different files |
| C (sequential) | Task 4 | Depends on Task 3 output |

### Smoketest Checkpoint 1 — Build passes with new generated files

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors. `track3_map.c` compiles harmlessly alongside existing code — no C changes yet reference the new `track_map_type` symbols, so no link errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Verify existing race tracks still behave normally (no regression). The combat track is not yet wired into the overmap.

---

## Batch 2 — Core C: track.c + loader.c + Tests

### Task 5: Update track.h — add TRACK_TYPE_* defines, externs, and getter declaration

**Files:**
- Modify: `src/track.h`
- Test: `tests/test_track.c`

**Depends on:** Task 2 (track_map.c now has track_map_type), Task 3 (track3_map.c exists)
**Parallelizable with:** Task 8 (hud.h update — different file)

**Step 1: Write the failing tests**

In `tests/test_track.c`, add:

```c
void test_track_get_map_type_race_track0(void) {
    track_select(0u);
    TEST_ASSERT_EQUAL_UINT8(TRACK_TYPE_RACE, track_get_map_type());
}

void test_track_get_map_type_race_track1(void) {
    track_select(1u);
    TEST_ASSERT_EQUAL_UINT8(TRACK_TYPE_RACE, track_get_map_type());
}

void test_track_get_map_type_combat_track2(void) {
    track_select(2u);
    TEST_ASSERT_EQUAL_UINT8(TRACK_TYPE_COMBAT, track_get_map_type());
}
```

Also add `RUN_TEST(...)` calls for each in `main()`.

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL (undefined `TRACK_TYPE_RACE`, `TRACK_TYPE_COMBAT`, `track_get_map_type`)

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Verify `bank-manifest.json` has an entry for `src/track.c` (it does — bank 255, autobank).

**Step 4: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm the planned API:
- `#define TRACK_TYPE_RACE   0u` and `#define TRACK_TYPE_COMBAT 1u` in `track.h`
- `extern const uint8_t track_map_type;` and `extern const uint8_t track2_map_type;` and `extern const uint8_t track3_map_type;`
- `BANKREF_EXTERN(track_map_type)`, `BANKREF_EXTERN(track2_map_type)`, `BANKREF_EXTERN(track3_map_type)`
- `uint8_t track_get_map_type(void) BANKED;`

**Step 5: Write track.h changes**

Add after the `TILE_TURRET` define block:

```c
/* Map type constants — emitted by tmx_to_c.py as track_map_type in generated files */
#define TRACK_TYPE_RACE   0u
#define TRACK_TYPE_COMBAT 1u
```

Add extern declarations after the existing `track2_checkpoints` externs:

```c
extern const uint8_t track_map_type;
extern const uint8_t track2_map_type;
extern const uint8_t track3_map_type;
```

Add BANKREF_EXTERN entries after existing ones:

```c
BANKREF_EXTERN(track_map_type)
BANKREF_EXTERN(track2_map_type)
BANKREF_EXTERN(track3_map_type)
```

Add getter declaration after `track_get_lap_count`:

```c
uint8_t track_get_map_type(void) BANKED;
```

**Step 6: Run tests to verify they pass (after track.c is also updated — see Task 6)**

Tests will pass once Task 6 provides the implementation. Hold off on this step until Task 6 is complete.

**Step 7: HARD GATE — build**

Run after Task 6: `GBDK_HOME=/home/mathdaman/gbdk make`. Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill after successful build.

**Step 9: Refactor checkpoint**

`track_get_map_type()` is a simple accessor — generalizes cleanly (no hard-coding). No follow-up needed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/track.h`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/track.h tests/test_track.c
git commit -m "feat: add TRACK_TYPE_* constants and track_get_map_type() declaration to track.h"
```

---

### Task 6: Update track.c — active_map_type static, id==2 branch, getter

**Files:**
- Modify: `src/track.c`

**Depends on:** Task 5 (track.h changes must exist), Task 3 (track3_map.c symbols referenced)
**Parallelizable with:** none — requires Task 5 header changes.

**Step 1: Write the failing test**

Tests from Task 5 already cover this. Re-run `make test` after this task's implementation to close the red/green cycle.

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — `track_get_map_type` undefined symbol.

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write` skill. `src/track.c` is in bank 255 (autobank) — confirmed in manifest.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm:
- `active_map_type` is a `static uint8_t` in `track.c` (file scope, not stack)
- `track_select(2u)` reads `track3_map_type` directly (same bank 255, no SWITCH_ROM needed)
- `track_get_map_type()` returns `active_map_type`

**Step 5: Write minimal implementation**

Add `static uint8_t active_map_type = 0u;` after the existing statics in `track.c`.

Update `track_select()` with a third branch:

```c
void track_select(uint8_t id) BANKED {
    active_track_id = id;
    load_track_header(id);
    if (id == 0u) {
        active_map       = track_map + 2;
        active_start_x   = track_start_x;
        active_start_y   = track_start_y;
        active_lap_count = 1u;
        active_map_type  = track_map_type;
    } else if (id == 1u) {
        active_map       = track2_map + 2;
        active_start_x   = track2_start_x;
        active_start_y   = track2_start_y;
        active_lap_count = 3u;
        active_map_type  = track2_map_type;
    } else {
        active_map       = track3_map + 2;
        active_start_x   = track3_start_x;
        active_start_y   = track3_start_y;
        active_lap_count = 1u;
        active_map_type  = track3_map_type;
    }
    load_checkpoints(id, wram_checkpoints, &active_checkpoint_count);
}
```

Add the extern declarations needed at the top of `track.c` (after the existing `#include`s):

```c
extern const int16_t track3_start_x;
extern const int16_t track3_start_y;
extern const uint8_t track3_map[];
```

Add getter:

```c
uint8_t track_get_map_type(void) BANKED { return active_map_type; }
```

**Step 6: Run tests to verify they pass**

```bash
make test
```
Expected: all track_get_map_type tests PASS.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill.

**Step 9: Refactor checkpoint**

Does this generalize beyond 3 tracks? If a 4th track were added, another `else if` branch is needed. This is intentional (YAGNI — no need for a data-driven dispatch table for 3 tracks). No follow-up issue needed unless track count is expected to grow.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/track.c`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/track.c
git commit -m "feat: add active_map_type to track.c with track3 dispatch and track_get_map_type() getter"
```

---

### Task 7: Update loader.c — add id==2 branches for load_track_header and load_checkpoints

**Files:**
- Modify: `src/loader.c`
- Test: `tests/test_loader.c`

**Depends on:** Task 3 (track3_map.c symbols exist), Task 6 (track.c now references track3 symbols — ensures track3 is in the build)
**Parallelizable with:** none — depends on Task 6 completing (must confirm build passes before touching bank-0 loader).

**Step 1: Write the failing tests**

In `tests/test_loader.c`, add:

```c
void test_load_track_header_id2_is_callable(void) {
    load_track_header(2u);
    /* active_map_w and active_map_h are updated — verify non-zero */
    TEST_ASSERT_NOT_EQUAL(0u, active_map_w);
    TEST_ASSERT_NOT_EQUAL(0u, active_map_h);
}

void test_load_checkpoints_id2_returns_zero_count(void) {
    CheckpointDef buf[MAX_CHECKPOINTS];
    uint8_t count = 99u;
    load_checkpoints(2u, buf, &count);
    TEST_ASSERT_EQUAL_UINT8(0u, count);  /* track3 has no checkpoints */
}
```

Add `RUN_TEST(...)` calls for each in `main()`.

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — `load_track_header(2u)` falls into the `else` branch (reads `track2_map`), wrong dimensions; `load_checkpoints(2u)` also reads `track2_checkpoints`, wrong.

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write` skill. `src/loader.c` is bank 0 (no `#pragma bank`) — confirmed in manifest.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm:
- Adding `extern const uint8_t track3_map[];` and `BANKREF_EXTERN(track3_map)` at top of `loader.c`
- `load_track_header(2)` switches to `BANK(track3_map)` before reading header bytes
- `load_checkpoints(2)` uses an empty array — track3 has 0 checkpoints, so `n = track3_checkpoint_count = 0u`, loop never runs, `*count = 0u`
- All `SWITCH_ROM(saved)` calls restore bank correctly

**Step 5: Write minimal implementation**

Add at top of `loader.c` (after existing externs):

```c
extern const uint8_t track3_map[];
BANKREF_EXTERN(track3_map)

BANKREF_EXTERN(track3_checkpoints)
extern const CheckpointDef track3_checkpoints[];
extern const uint8_t        track3_checkpoint_count;
```

Update `load_track_header()`:

```c
void load_track_header(uint8_t id) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    if (id == 0u) {
        SWITCH_ROM(BANK(track_map));
        active_map_w = track_map[0];
        active_map_h = track_map[1];
    } else if (id == 1u) {
        SWITCH_ROM(BANK(track2_map));
        active_map_w = track2_map[0];
        active_map_h = track2_map[1];
    } else {
        SWITCH_ROM(BANK(track3_map));
        active_map_w = track3_map[0];
        active_map_h = track3_map[1];
    }
    SWITCH_ROM(saved);
}
```

Update `load_checkpoints()`:

```c
void load_checkpoints(uint8_t id, CheckpointDef *dst, uint8_t *count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 0u) {
        SWITCH_ROM(BANK(track_checkpoints));
        n = track_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) dst[i] = track_checkpoints[i];
    } else if (id == 1u) {
        SWITCH_ROM(BANK(track2_checkpoints));
        n = track2_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) dst[i] = track2_checkpoints[i];
    } else {
        SWITCH_ROM(BANK(track3_checkpoints));
        n = track3_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) dst[i] = track3_checkpoints[i];
    }
    *count = n;
    SWITCH_ROM(saved);
}
```

**Step 6: Run tests to verify they pass**

```bash
make test
```
Expected: all loader tests PASS.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill.

**Step 9: Refactor checkpoint**

Same YAGNI note as Task 6 — the if/else chain is fine for 3 tracks. No follow-up needed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/loader.c`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/loader.c tests/test_loader.c
git commit -m "feat: add track id==2 (track3) support to load_track_header and load_checkpoints"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 2

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 5 | track.h must exist before Task 6 |
| B (sequential) | Task 6 | Depends on Task 5 headers |
| C (sequential) | Task 7 | Depends on Task 6 (build must pass before touching bank-0 loader) |

### Smoketest Checkpoint 2 — Track getter + loader work; race tracks unchanged

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
Expected: All budgets PASS.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Verify both existing race tracks navigate and complete normally. Combat track not yet wired into overmap (no visible change there).

---

## Batch 3 — HUD + State Playing Integration

### Task 8: Update hud.h — new hud_init signature

**Files:**
- Modify: `src/hud.h`

**Depends on:** Task 5 (TRACK_TYPE_* defines must exist in track.h, included by state_playing.c)
**Parallelizable with:** Task 5 — both are header-only changes to different files. Task 8 can start as soon as Task 5's `track.h` changes are written (since `hud.h` itself doesn't include `track.h`).

**Step 1: Write the failing test**

In `tests/test_hud.c`, update `setUp()`:

```c
void setUp(void) { hud_init(TRACK_TYPE_RACE, 3u); }
```

Add new test:

```c
void test_hud_init_combat_mode_sets_map_type(void) {
    hud_init(TRACK_TYPE_COMBAT, 1u);
    /* After combat init, hud_is_dirty should be 0 (no mid-frame render triggered) */
    TEST_ASSERT_EQUAL_UINT8(0u, hud_is_dirty());
}
```

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — `hud_init` called with wrong argument count; `TRACK_TYPE_RACE` undefined if track.h not yet updated (Task 5 must complete first).

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write` skill. `src/hud.c` is bank 255 — confirmed.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm new signature:

```c
void hud_init(uint8_t map_type, uint8_t lap_total) BANKED;
```

**Step 5: Write hud.h change**

Replace the existing declaration:

```c
/* Before */
void    hud_init(void) BANKED;

/* After */
void    hud_init(uint8_t map_type, uint8_t lap_total) BANKED;
```

Add `#include "track.h"` at the top of `hud.h` if `TRACK_TYPE_RACE`/`TRACK_TYPE_COMBAT` are needed by callers. Alternatively, callers include `track.h` themselves — prefer NOT adding the include to `hud.h` to keep the header light (callers already include `track.h`).

**Step 6: Run tests — will still FAIL until Task 9 updates hud.c implementation**

```bash
make test
```
Expected: FAIL — hud.c body still has the old `void hud_init(void)` definition.

**Step 7–11:** Complete after Task 9.

**Commit (combined with Task 9 below).**

---

### Task 9: Update hud.c — new hud_init implementation with map_type and lap_total

**Files:**
- Modify: `src/hud.c`

**Depends on:** Task 8 (hud.h signature change)
**Parallelizable with:** none — depends on Task 8.

**Step 1: Write failing test (from Task 8)**

Already written in Task 8 Step 1.

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — old `hud_init(void)` definition.

**Step 3: HARD GATE — bank-pre-write**

Already confirmed in Task 8.

**Step 4: HARD GATE — gbdk-expert**

Already confirmed in Task 8. Additional detail: the combat HUD skips writing lap tiles to window cols 6–8. Store `hud_map_type` as a `static uint8_t` in `hud.c`. In `hud_render()`, guard the lap tile write behind `if (hud_map_type != TRACK_TYPE_COMBAT)`.

**Step 5: Write minimal implementation**

In `hud.c`, add static field:

```c
static uint8_t hud_map_type;
```

Update `hud_init()`:

```c
void hud_init(uint8_t map_type, uint8_t lap_total) BANKED {
    hud_map_type    = map_type;
    hud_hp          = PLAYER_MAX_HP;
    hud_frame_tick  = 0u;
    hud_seconds     = 0u;
    hud_dirty       = 0u;
    hud_mm          = 0u;
    hud_ss          = 0u;
    hud_lap_current = 1u;
    hud_lap_total   = lap_total;   /* caller passes track_get_lap_count() — no hardcoded 3 */
    /* ... rest of existing init (LCDC setup, window positioning, tile writes) ... */
}
```

In `hud_render()`, wrap the lap tile write block:

```c
if (hud_map_type != TRACK_TYPE_COMBAT) {
    /* existing lap tile rendering: cols 6-8 */
    uint8_t lap_tiles[3];
    lap_tiles[0] = HUD_FONT_BASE + hud_lap_current;
    lap_tiles[1] = HUD_FONT_BASE + HUD_TILE_SLASH;
    lap_tiles[2] = HUD_FONT_BASE + hud_lap_total;
    set_win_tiles(6u, 0u, 3u, 1u, lap_tiles);
}
```

Also update the initial `hud_init()` tile layout build: for combat maps, write `HUD_FONT_BASE + HUD_TILE_SPACE` (space) into cols 6–8 of the initial row0 tile buffer.

Add `#include "track.h"` at the top of `hud.c` for `TRACK_TYPE_COMBAT`.

**Step 6: Run tests to verify they pass**

```bash
make test
```
Expected: all hud tests PASS (including updated setUp with new signature and new combat test).

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: FAIL — `state_playing.c` still calls `hud_init()` with old signature. Fix in Task 10 before this gate passes.

**Step 8: HARD GATE — bank-post-build**

Run after Task 10 fixes state_playing.c.

**Step 9: Refactor checkpoint**

`hud_map_type` is a separate static — not combined with other state. Generalizes cleanly. No follow-up needed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/hud.c`. Report issues; do not apply fixes.

**Step 11: Commit (combined with Task 8)**

```bash
git add src/hud.h src/hud.c tests/test_hud.c
git commit -m "feat: hud_init accepts map_type and lap_total; hide lap counter for combat maps"
```

---

### Task 10: Update state_playing.c — cache map type, new hud_init call, finish_eval, combat win condition

**Files:**
- Modify: `src/state_playing.c`
- Modify: `src/state_playing.h` (add finish_eval test seam)
- Create: `tests/test_state_playing.c`

**Depends on:** Task 8+9 (hud.h new signature), Task 5 (TRACK_TYPE_* defines), Task 6 (track_get_map_type())
**Parallelizable with:** none — depends on Tasks 5, 6, 8, 9.

**Step 1: Write the failing tests**

Create `tests/test_state_playing.c`:

```c
#include "unity.h"
#include "track.h"        /* TRACK_TYPE_RACE, TRACK_TYPE_COMBAT */
#include "state_playing.h" /* finish_eval */

void setUp(void) {}
void tearDown(void) {}

/* finish_eval(map_type, armed, pvy, cps_cleared) → 1 = should transition */

/* Race: requires armed + downward velocity + all checkpoints */
void test_finish_eval_race_all_conditions_met(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_RACE, 1u, 1, 1u));
}

void test_finish_eval_race_missing_checkpoint(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, 1, 0u));
}

void test_finish_eval_race_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 0u, 1, 1u));
}

void test_finish_eval_race_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_RACE, 1u, -1, 1u));
}

/* Combat: requires only armed + downward velocity (no checkpoint gate) */
void test_finish_eval_combat_no_checkpoint_needed(void) {
    TEST_ASSERT_EQUAL_UINT8(1u, finish_eval(TRACK_TYPE_COMBAT, 1u, 1, 0u));
}

void test_finish_eval_combat_not_armed(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 0u, 1, 0u));
}

void test_finish_eval_combat_wrong_direction(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, finish_eval(TRACK_TYPE_COMBAT, 1u, -1, 0u));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_finish_eval_race_all_conditions_met);
    RUN_TEST(test_finish_eval_race_missing_checkpoint);
    RUN_TEST(test_finish_eval_race_not_armed);
    RUN_TEST(test_finish_eval_race_wrong_direction);
    RUN_TEST(test_finish_eval_combat_no_checkpoint_needed);
    RUN_TEST(test_finish_eval_combat_not_armed);
    RUN_TEST(test_finish_eval_combat_wrong_direction);
    return UNITY_END();
}
```

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — `finish_eval` undefined, `state_playing.h` has no such declaration.

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write` skill. `src/state_playing.c` is bank 255 (autobank) — confirmed.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent. Confirm:
- `finish_eval()` is `static` in `state_playing.c`, exposed via `#ifndef __SDCC` in `state_playing.h`
- `active_map_type_cache` is `static uint8_t` at file scope in `state_playing.c`
- `enter()` calls `track_get_map_type()` and stores result in `active_map_type_cache`
- `enter()` calls `hud_init(active_map_type_cache, track_get_lap_count())`
- For combat: `finish_armed = 0u` after `state_replace(&state_overmap)` (debounce reset not needed as state exits, but set for clarity)
- `lap_init()` still called for combat (with `track_get_lap_count()` = 1) — harmless

**Step 5: Write minimal implementation**

Add to `src/state_playing.h` (after existing declarations):

```c
#ifndef __SDCC
/* Test-only seam: pure win-condition logic, no hardware. */
uint8_t finish_eval(uint8_t map_type, uint8_t armed, int8_t pvy, uint8_t cps_cleared);
#endif
```

In `src/state_playing.c`, add file-scope static:

```c
static uint8_t active_map_type_cache;
```

Add pure helper (before `enter()`):

```c
static uint8_t finish_eval(uint8_t map_type, uint8_t armed, int8_t pvy, uint8_t cps_cleared) {
    if (!armed || pvy <= 0) return 0u;
    if (map_type == TRACK_TYPE_COMBAT) return 1u;
    return cps_cleared;
}
```

Update `enter()`:

```c
static void enter(void) {
    /* ... existing code ... */
    active_map_type_cache = track_get_map_type();
    lap_init(track_get_lap_count());
    finish_armed = 1u;
    /* ... */
    hud_init(active_map_type_cache, track_get_lap_count());
    hud_set_lap(lap_get_current(), lap_get_total());
    /* ... */
}
```

Update the finish tile check in `update()`:

```c
if (ct == TILE_FINISH) {
    if (finish_eval(active_map_type_cache, finish_armed, pvy,
                    checkpoint_all_cleared())) {
        finish_armed = 0u;
        if (active_map_type_cache == TRACK_TYPE_COMBAT) {
            state_replace(&state_overmap);
            return;
        }
        if (lap_advance()) {
            state_replace(&state_overmap);
            return;
        }
        checkpoint_reset();
        hud_set_lap(lap_get_current(), lap_get_total());
    }
} else {
    finish_armed = 1u;
}
```

**Step 6: Run tests to verify they pass**

```bash
make test
```
Expected: all `test_state_playing` tests PASS.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors. `hud_init()` call now matches new signature.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill (covers hud.c + state_playing.c changes).

**Step 9: Refactor checkpoint**

`finish_eval()` is pure and well-factored. `active_map_type_cache` is a single byte. No hard-coding. No follow-up needed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/state_playing.c`. Report issues; do not apply fixes.

**Step 11: Commit**

```bash
git add src/state_playing.h src/state_playing.c tests/test_state_playing.c
git commit -m "feat: state_playing caches map type, uses finish_eval(), calls hud_init with map_type+lap_total"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 3

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 8, Task 5 | Different header files; Task 8 can start once Task 5's track.h defines are written |
| B (sequential) | Task 9 | Depends on Task 8 (hud.h signature) |
| C (sequential) | Task 10 | Depends on Tasks 5, 6, 8, 9 — requires all defines, getters, and hud.h signature |

### Smoketest Checkpoint 3 — HUD and win-condition wired; race tracks verified

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
Expected: All budgets PASS.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**
Verify:
- Race track 0 (left dest on overmap): lap counter shows `1/1`, finishes after 1 crossing.
- Race track 1 (right dest on overmap): lap counter shows `1/3`, advances through 3 laps.
- Combat track not yet reachable from overmap (wired in next batch).

---

## Batch 4 — Overmap Wiring

### Task 11: Update overmap.tmx to add combat destination, regenerate overmap_map.c

**Files:**
- Modify: `assets/maps/overmap.tmx`
- Regenerate: `src/overmap_map.c`

**Depends on:** Smoketest Checkpoint 3 (confirms race track behaviour is stable)
**Parallelizable with:** none — single file, single regeneration.

**Step 1: Add combat DEST tile to overmap.tmx**

Open `assets/maps/overmap.tmx` in Tiled. Add a tile with GID 4 (`OVERMAP_TILE_DEST`, the same tile type as the two existing race destinations) at position **(col 9, row 9)** — one tile directly south of the player spawn at (9, 8).

Scan-order verification:
- (2, 8) → scanned first → `current_race_id = 0` (track 0, race)
- (17, 8) → scanned second → `current_race_id = 1` (track 1, race)
- (9, 9) → scanned third (row 9 > row 8) → `current_race_id = 2` (track 2, combat) ✓

Navigation verification: `find_next_node(0, 1)` from spawn (9, 8) checks (9, 9) — tile value 3 (`OVERMAP_TILE_DEST`) is non-blank (walkable) and non-road (immediately returned). Player navigates there on DOWN press.

**Step 2: Regenerate overmap_map.c**

```bash
python3 tools/tmx_to_array_c.py assets/maps/overmap.tmx src/overmap_map.c overmap_map config.h
```

Verify `src/overmap_map.c` row 9 now reads:
```c
/* row  9 */ 0,0,0,0,0,0,0,0,0,3,0,0,0,0,0,0,0,0,0,0,
```
(value 3 = `OVERMAP_TILE_DEST` at col 9)

**Step 3: Verify**

```bash
make test
```
Expected: all tests still PASS.

**Step 4: Ask user about integration test**

Per project policy, always ask the user before modifying or adding integration tests. Ask:
> "The new combat dest tile at (9,9) adds a DOWN navigation path from the overmap spawn. The existing `test_regression.py` only presses UP and LEFT, so it is unaffected. Would you like a new integration test function that navigates DOWN to the combat track and verifies it exits on first finish crossing?"

Wait for response before touching `test_regression.py`.

**Step 5: Commit**

```bash
git add assets/maps/overmap.tmx src/overmap_map.c
git commit -m "feat: add combat track destination to overmap.tmx at (9,9)"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 4

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 11 | Single task in this batch — no parallelism possible |

### Smoketest Checkpoint 4 — Full combat track playthrough in Emulicious

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
Expected: All budgets PASS.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

Verify all AC:
- **AC1**: Race tracks 0 and 1 play identically to before.
- **AC2**: Press DOWN on overmap → enters combat track → drive to finish tile → exits immediately on first crossing without requiring laps.
- **AC3**: No lap counter visible in HUD during the combat map session.
- **AC4**: Lap counter present and correct (`1/1` and `1/3`) during race map sessions.
- **AC5**: `src/track3_map.c` contains `track3_map_type = 1u`; `track_map.c` and `track2_map.c` contain `= 0u`.
- **AC6**: `make test` passes — confirmed at Task 10.
- **AC7**: `make build` passes with no new warnings — confirmed.
- **AC8**: Smoketest passed in this checkpoint.

Wait for user confirmation before pushing.
