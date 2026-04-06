# Turret Firing, Object Disappear, and Heal Powerup — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two turret bugs (simultaneous firing, visual disappear on death), migrate the heal pad from a BG tile to a one-time-use powerup object, and clean up dead tile type constants.

**Architecture:** BG layer = terrain only (road, wall). Game objects (turrets, powerups) are OAM sprites placed via Tiled object layers (`enemies`, `powerups`). When an object disappears, the OAM sprite is cleared and the BG road shows through — no runtime tile patching needed. The turret firing bug is a global `proj_cooldown_tick` blocking all enemy shots after the first; fix is to bypass it for `PROJ_OWNER_ENEMY`. The turret and heal pad visual bugs share the same root cause: BG tile layer stored object graphics instead of terrain.

**Tech Stack:** GBDK-2020 / SDCC, Tiled TMX (object + tile layers), Unity host-side tests.

## Open questions

None — all resolved in grill-me session.

---

## Batch 1 — Architecture Fix: BG Tile Layer + Collision

### Task 1: Replace turret BG tiles with road in `track.tmx`

**Files:**
- Modify: `assets/maps/track.tmx`

**Depends on:** none
**Parallelizable with:** Task 2 (different files, no shared output symbol)

**Step 1: Verify GID 9 appears only at turret positions**

```bash
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('assets/maps/track.tmx')
root = tree.getroot()
layer = root.find('layer[@name=\"Track\"]')
data = [int(x.strip()) for x in layer.find('data').text.strip().split(',')]
w = int(layer.get('width'))
hits = [(i % w, i // w) for i, g in enumerate(data) if g == 9]
print('GID 9 positions (tx, ty):', hits)
"
```

Expected output: `GID 9 positions (tx, ty): [(4, 22), (15, 47), (5, 72)]`
If any unexpected positions appear, stop and investigate before patching.

**Step 2: Replace GID 9 → GID 2 (road) at the three turret positions**

```bash
python3 - <<'EOF'
import xml.etree.ElementTree as ET
ET.register_namespace('', 'http://www.w3.org/2001/XMLSchema')
tree = ET.parse('assets/maps/track.tmx')
root = tree.getroot()
layer = root.find('layer[@name="Track"]')
data_el = layer.find('data')
tokens = data_el.text.strip().split(',')
data = [int(t.strip()) for t in tokens]
w = int(layer.get('width'))
targets = {(4, 22), (15, 47), (5, 72)}
changed = 0
for i, g in enumerate(data):
    tx, ty = i % w, i // w
    if g == 9 and (tx, ty) in targets:
        data[i] = 2
        changed += 1
assert changed == 3, f"Expected 3 changes, got {changed}"
data_el.text = '\n' + ','.join(str(g) for g in data) + '\n'
tree.write('assets/maps/track.tmx', encoding='unicode', xml_declaration=False)
print(f"Patched {changed} turret tiles to road.")
EOF
```

**Step 3: Rebuild to regenerate `src/track_map.c`**

```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: zero errors, `build/nuke-raider.gb` produced.

**Step 4: Verify**

```bash
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('assets/maps/track.tmx')
root = tree.getroot()
layer = root.find('layer[@name=\"Track\"]')
data = [int(x.strip()) for x in layer.find('data').text.strip().split(',')]
hits = [i for i, g in enumerate(data) if g == 9]
print('Remaining GID 9 count:', len(hits))
"
```

Expected: `Remaining GID 9 count: 0`

**Step 5: Commit**

```bash
git add assets/maps/track.tmx
git commit -m "fix(map): replace turret BG tiles with road at 3 NPC spawn positions

Turrets are placed via the enemies object layer; the BG tile was
a redundant leftover from the tilemap-scan era (removed in f36eac8).
BG layer is now terrain-only at turret positions, matching the
conceptual model: objects are OAM sprites layered over BG terrain.

Closes partial: #287"
```

---

### Task 2: Remove `TILE_TURRET` from `corner_active_turret` in `player.c`

**Files:**
- Modify: `src/player.c`
- Test: `tests/test_terrain_physics.c` or `tests/test_player.c`

**Depends on:** none (can be done before or after Task 1; semantically motivated by Task 1)
**Parallelizable with:** Task 1 (different output files, no shared symbol dependency)

**Step 1: Write the failing test**

Locate `tests/test_terrain_physics.c` or `tests/test_player.c`. Add:

```c
/* After Task 1 the BG tile at turret positions is road (TILE_ROAD), not
 * TILE_TURRET. Collision must be driven by enemy_blocks_tile() alone. */
void test_turret_collision_driven_by_enemy_state_not_bg_tile(void) {
    /* No enemy spawned → tile is not blocked, even if BG were turret type */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_blocks_tile(4u, 22u));
    /* Spawn enemy at turret tile (4,22) → now blocked */
    enemy_spawn(4u, 22u);
    TEST_ASSERT_EQUAL_UINT8(1u, enemy_blocks_tile(4u, 22u));
}
```

Add `RUN_TEST(test_turret_collision_driven_by_enemy_state_not_bg_tile)` to `main()`.

**Step 2: Run test to verify it compiles and passes**

```bash
make test
```

Expected: PASS (this test verifies existing behaviour; the real gate is Step 5 confirming `corner_active_turret` no longer needs `track_tile_type`).

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `src/player.c` is `#pragma bank 255` (autobank) — confirm `bank-manifest.json` entry exists.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent: *"Confirm removing `track_tile_type(wx, wy) == TILE_TURRET &&` from `corner_active_turret()` in player.c is safe. The full condition becomes `return enemy_blocks_tile(tx, ty);`. Verify no SDCC/SM83 concerns with the resulting single-expression function."*

**Step 5: Write minimal implementation**

In `src/player.c`, change `corner_active_turret`:

```c
/* Before */
static uint8_t corner_active_turret(int16_t wx, int16_t wy) {
    uint8_t tx = (uint8_t)((uint16_t)wx >> 3u);
    uint8_t ty = (uint8_t)((uint16_t)wy >> 3u);
    return (track_tile_type(wx, wy) == TILE_TURRET) && enemy_blocks_tile(tx, ty);
}

/* After */
static uint8_t corner_active_turret(int16_t wx, int16_t wy) {
    uint8_t tx = (uint8_t)((uint16_t)wx >> 3u);
    uint8_t ty = (uint8_t)((uint16_t)wy >> 3u);
    return enemy_blocks_tile(tx, ty);
}
```

**Step 6: Run tests**

```bash
make test
```

Expected: PASS

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill. Verify bank placements.

**Step 9: Refactor checkpoint**

`track_tile_type()` is no longer called from `corner_active_turret`. Check if it is still called elsewhere; if `TILE_TURRET` in the LUT is now dead code, open a follow-up issue rather than removing it now (YAGNI — the type may be needed for future tile types).

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/player.c`. Report issues, do not apply fixes.

**Step 11: Commit**

```bash
git add src/player.c tests/test_terrain_physics.c  # or test_player.c
git commit -m "fix(player): turret collision driven by enemy state, not BG tile type

corner_active_turret() no longer checks track_tile_type() == TILE_TURRET.
BG layer is now terrain-only at turret positions (Task 1); the enemy
module's active flag is the sole source of truth for dynamic blocking.

Closes partial: #287"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2 | Different output files; Task 1 → TMX+track_map.c, Task 2 → player.c |

---

### Smoketest Checkpoint 1 — turrets visible, road under them, collision correct

**Step 1: Fetch and merge latest master**
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
Expected: all budgets PASS.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

Ask the user to navigate to track 1 and verify:
- Turret OAM sprites appear at correct positions
- Player cannot drive through an active turret
- No visual regression on road or background tiles

---

## Batch 2 — Firing Fix: Projectile Cooldown + Enemy Timer

### Task 3: Enemy shots bypass `proj_cooldown_tick` in `projectile.c`

**Files:**
- Modify: `src/projectile.c`
- Test: `tests/test_projectile.c`

**Depends on:** none
**Parallelizable with:** Task 4 (different output files, no shared symbol)

**Step 1: Write the failing tests**

Add to `tests/test_projectile.c`:

```c
/* Enemy shots are not gated by proj_cooldown_tick.
 * Two PROJ_OWNER_ENEMY fires in the same frame must both succeed. */
void test_projectile_enemy_bypasses_cooldown(void) {
    projectile_fire(80u, 80u, DIR_R, PROJ_OWNER_ENEMY);
    projectile_fire(80u, 80u, DIR_L, PROJ_OWNER_ENEMY);
    TEST_ASSERT_EQUAL_UINT8(2u, projectile_count_active());
}

/* Player cooldown is not polluted by an enemy shot fired first. */
void test_projectile_player_cooldown_unaffected_by_enemy_shot(void) {
    projectile_fire(80u, 80u, DIR_R, PROJ_OWNER_ENEMY);
    /* Player fires immediately after enemy — should succeed (cooldown not set by enemy) */
    projectile_fire(80u, 80u, DIR_T, PROJ_OWNER_PLAYER);
    TEST_ASSERT_EQUAL_UINT8(2u, projectile_count_active());
}

/* Player cooldown is still enforced for rapid player fire. */
void test_projectile_player_cooldown_still_applies(void) {
    projectile_fire(80u, 80u, DIR_R, PROJ_OWNER_PLAYER);
    projectile_fire(80u, 80u, DIR_L, PROJ_OWNER_PLAYER);  /* within cooldown */
    TEST_ASSERT_EQUAL_UINT8(1u, projectile_count_active());
}
```

Add `RUN_TEST` calls to `main()`.

**Step 2: Run test to verify it fails**

```bash
make test
```

Expected: `test_projectile_enemy_bypasses_cooldown` FAIL (second enemy shot blocked by cooldown).

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write` skill. `src/projectile.c` is `#pragma bank 255` — confirm manifest entry.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent: *"In projectile_fire(), modify the proj_cooldown_tick guard and the proj_cooldown_tick assignment so they apply only to PROJ_OWNER_PLAYER shots. Enemy shots (PROJ_OWNER_ENEMY) bypass both the cooldown check and do not set the cooldown. Confirm this is safe for SDCC bank 255 / SM83."*

**Step 5: Write minimal implementation**

In `src/projectile.c`, change `projectile_fire()`:

```c
void projectile_fire(uint8_t scr_x, uint8_t scr_y, player_dir_t dir, uint8_t owner) BANKED {
    uint8_t i;
    uint8_t oam;

    /* Cooldown applies to player only — enemy turrets fire on their own timers */
    if (owner == PROJ_OWNER_PLAYER && proj_cooldown_tick > 0u) return;

    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (!proj_active[i]) {
            oam = get_sprite();
            if (oam == SPRITE_POOL_INVALID) return;

            proj_x[i]      = scr_x;
            proj_y[i]      = scr_y;
            proj_dx[i]     = (int8_t)((int8_t)PROJ_SPEED * player_dir_dx(dir));
            proj_dy[i]     = (int8_t)((int8_t)PROJ_SPEED * player_dir_dy(dir));
            proj_ttl[i]    = PROJ_MAX_TTL;
            proj_owner[i]  = owner;
            proj_oam[i]    = oam;
            proj_active[i] = 1u;

            set_sprite_tile(oam, PROJ_TILE_BASE);
            if (owner == PROJ_OWNER_PLAYER) {
                proj_cooldown_tick = PROJ_FIRE_COOLDOWN;
            }
            sfx_play(SFX_SHOOT);
            return;
        }
    }
}
```

**Step 6: Run tests**

```bash
make test
```

Expected: PASS (including existing `test_projectile_fire_respects_cooldown`).

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill.

**Step 9: Refactor checkpoint**

Does this generalize? Yes — any future AI owner type would also bypass the player cooldown by default. If a future owner type needs its own cooldown, that can be added then (YAGNI).

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/projectile.c`.

**Step 11: Commit**

```bash
git add src/projectile.c tests/test_projectile.c
git commit -m "fix(projectile): enemy shots bypass player fire cooldown

proj_cooldown_tick guards and sets only for PROJ_OWNER_PLAYER.
Enemy turrets fire on their own per-turret timers; the global
cooldown was silently blocking turrets 1 and 2 every frame.

Closes partial: #287"
```

---

### Task 4: Init `enemy_timer` to 0 at spawn in `enemy.c`

**Files:**
- Modify: `src/enemy.c`
- Test: `tests/test_enemy.c`

**Depends on:** none
**Parallelizable with:** Task 3 (different output files, no shared symbol)

**Step 1: Write the failing test**

Add to `tests/test_enemy.c`:

```c
/* Add test accessor alongside existing #ifndef __SDCC block in enemy.c */
/* uint8_t enemy_get_timer(uint8_t i); — returns enemy_timer[i] */

void test_enemy_timer_zero_at_spawn(void) {
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(0u));
}

/* All three turrets spawned simultaneously share timer=0 — fire on the
 * same frame with no sequential dependency. */
void test_enemy_three_turrets_timer_all_zero(void) {
    enemy_spawn(4u, 22u);
    enemy_spawn(15u, 47u);
    enemy_spawn(5u, 72u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(1u));
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(2u));
}
```

Add `RUN_TEST` calls.

**Step 2: Run test to verify it fails**

```bash
make test
```

Expected: FAIL (`enemy_get_timer` undefined; after adding the accessor, timer = `TURRET_FIRE_INTERVAL` not 0).

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write` skill. `src/enemy.c` is `#pragma bank 255` — confirm manifest entry.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent: *"In enemy.c _spawn_at(), change enemy_timer[i] = TURRET_FIRE_INTERVAL to enemy_timer[i] = 0u. Also add enemy_get_timer() test accessor guarded by #ifndef __SDCC. Confirm no SDCC concern with timer starting at 0 and the existing update loop logic (fires on frame 0 when timer == 0, then resets to TURRET_FIRE_INTERVAL)."*

**Step 5: Write minimal implementation**

In `src/enemy.c`:

```c
/* In _spawn_at() — change one line */
enemy_timer[i]  = 0u;   /* was: TURRET_FIRE_INTERVAL — 0 fires immediately */
```

Add test accessor at bottom of `enemy.c`:

```c
#ifndef __SDCC
uint8_t enemy_get_type(uint8_t i)  { return enemy_type[i]; }
uint8_t enemy_get_dir(uint8_t i)   { return enemy_dir[i]; }
uint8_t enemy_get_timer(uint8_t i) { return enemy_timer[i]; }
#endif
```

Add declaration to `src/enemy.h` inside `#ifndef __SDCC` guard:

```c
#ifndef __SDCC
uint8_t enemy_get_type(uint8_t i);
uint8_t enemy_get_dir(uint8_t i);
uint8_t enemy_get_timer(uint8_t i);
#endif
```

Update existing test `test_enemy_timer_does_not_fire_early` — it says "timer starts at TURRET_FIRE_INTERVAL" which is now wrong. Change the comment to reflect the new behaviour (timer starts at 0, fires on frame 1):

```c
void test_enemy_timer_fires_on_first_frame(void) {
    /* Timer starts at 0 — turret fires on the very first update call.
     * After firing, timer resets to TURRET_FIRE_INTERVAL. */
    enemy_spawn(10u, 20u);
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_get_timer(0u));
    /* After one tick (simulated by enemy_tick_timers), timer would go to
     * TURRET_FIRE_INTERVAL - 1 = 59 IF fire hadn't occurred.
     * We can't call enemy_update() here (requires full VRAM/cam context),
     * so we verify the timer value at spawn as the acceptance signal. */
}
```

Also remove or rename the now-stale `test_enemy_timer_does_not_fire_early` test to avoid confusion.

**Step 6: Run tests**

```bash
make test
```

Expected: PASS.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill.

**Step 9: Refactor checkpoint**

Does timer=0 generalize? Yes — any new NPC type added in future should also fire immediately on spawn (or use its own init value). The constant is per-type and can be overridden in `_spawn_at()` for different NPC types when they are added.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/enemy.c`.

**Step 11: Commit**

```bash
git add src/enemy.c src/enemy.h tests/test_enemy.c
git commit -m "fix(enemy): init enemy_timer to 0 at spawn — all turrets fire on frame 1

Previously TURRET_FIRE_INTERVAL (60 frames) caused a silent 1-second
delay before first shot. Combined with the projectile cooldown fix,
all 3 turrets now fire simultaneously at race start.

Closes partial: #287"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 2

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 3, Task 4 | Different output files (projectile.c, enemy.c); no shared output symbol |

---

### Smoketest Checkpoint 2 — all 3 turrets fire simultaneously; killed turret tile disappears

**Step 1: Fetch and merge latest master**
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
Expected: all budgets PASS.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

Ask the user to:
1. Start a race on track 1 and verify all 3 turrets fire projectiles toward the player simultaneously on frame 1 (no initial delay, no sequential gating).
2. Kill one turret — verify its OAM sprite disappears immediately and the BG tile shows road (not turret graphic).
3. Verify killing turret 1 does not change turret 2 or 3's firing cadence.
4. Verify player takes damage from enemy projectiles (no regression on hit detection).
5. Verify player cannot drive through an active turret (collision still works).

---

## Batch 3 — Heal Powerup: Sprite Assets, Config, Data Pipeline

### Task 5: Add heal pad tile to object sprite sheet + rename `load_turret_tiles` → `load_object_sprites`

**Files:**
- Modify: `assets/sprites/turret.png` (extend to 16×8 — heal pad tile at right half)
- Regenerate: `src/turret_sprite.c` (via `tools/png_to_tiles.py`)
- Modify: `src/loader.c` (rename function, update comment; loads 2 tiles now)
- Modify: `src/loader.h` (rename declaration)
- Modify: `src/enemy.c` (update call site from `load_turret_tiles` → `load_object_sprites`)

**Depends on:** none
**Parallelizable with:** none — writes `loader.c` and `loader.h`; Task 6 also modifies these files

**Step 1: Extend `turret.png` and regenerate `turret_sprite.c`**

Invoke the `sprite-expert` agent:

> "In `assets/sprites/turret.png` (currently 8×8, 1 tile — the turret sprite), add a second 8×8 tile for the heal pad. The source pixel data for the heal pad is in `assets/maps/tileset.png` at tile index 7 (0-based; the tileset is 72×8 pixels — a single row of 9 tiles). Tile 7 occupies pixel columns 56–63 (x=56 to x=63), full height (y=0 to y=7). Extend `assets/sprites/turret.png` to 16×8 by placing the heal pad pixels in the right 8 columns. Both PNGs must be mode P (indexed) with the same 4-color GB palette. Then run:
> ```bash
> python3 tools/png_to_tiles.py --bank 255 assets/sprites/turret.png src/turret_sprite.c turret_tile_data
> ```
> Verify `turret_tile_data_count = 2u` in `src/turret_sprite.c`. Commit `assets/sprites/turret.png` and `src/turret_sprite.c` together."

**Step 2: Write the failing test**

There is no new behavioral test for the rename itself — the compile gate is the test. In `tests/test_enemy.c`, add a comment at the top:

```c
/* Task 5: load_object_sprites() must exist in loader.h — fails to compile before Task 5 */
```

Run:
```bash
make test
```
Expected: PASS with current code (before rename this confirms existing tests pass). Proceed.

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm entries exist in `bank-manifest.json` for:
- `src/loader.c` (bank 0)
- `src/enemy.c` (bank 255, autobank)
- `src/turret_sprite.c` (bank 255, autobank)

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent: *"In `loader.c`, `load_turret_tiles()` calls `set_sprite_data(TURRET_TILE_BASE, turret_tile_data_count, turret_tile_data)`. After adding a second tile (heal pad) to the sprite data, `turret_tile_data_count` becomes 2. The call will now load 2 tiles at VRAM slots 18 (turret) and 19 (heal pad). `POWERUP_TILE_BASE` will be 19u. Confirm this is safe and correct — the loader loads N consecutive tiles from a single array. Verify no SDCC concern with renaming a NONBANKED function."*

**Step 5: Rename in `loader.c`, `loader.h`, `enemy.c`**

In `src/loader.c`:
```c
/* Before */
void load_turret_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(turret_tile_data));
    set_sprite_data(TURRET_TILE_BASE, turret_tile_data_count, turret_tile_data);
    SWITCH_ROM(saved);
}

/* After — loads turret (slot 18) and heal pad (slot 19) from a single 2-tile array */
void load_object_sprites(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(turret_tile_data));
    set_sprite_data(TURRET_TILE_BASE, turret_tile_data_count, turret_tile_data);
    SWITCH_ROM(saved);
}
```

In `src/loader.h`:
```c
/* Before */
void load_turret_tiles(void) NONBANKED;

/* After */
void load_object_sprites(void) NONBANKED;
```

In `src/enemy.c`, `enemy_init()`:
```c
/* Before */
load_turret_tiles();

/* After */
load_object_sprites();
```

**Step 6: Run tests**

```bash
make test
```
Expected: PASS

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill. Verify bank placements unchanged.

**Step 9: Refactor checkpoint**

Check: any remaining references to `load_turret_tiles` in the codebase?
```bash
grep -r "load_turret_tiles" src/ tests/
```
Expected: zero matches.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/loader.c` and `src/enemy.c`. Report issues, do not apply fixes.

**Step 11: Commit**

```bash
git add assets/sprites/turret.png src/turret_sprite.c src/loader.c src/loader.h src/enemy.c
git commit -m "feat(sprites): add heal pad tile to object sprite sheet; rename load_turret_tiles→load_object_sprites

turret_sprite.c now carries 2 tiles: slot 18 = turret, slot 19 = heal pad.
load_object_sprites() loads both at TURRET_TILE_BASE in one set_sprite_data call.
Prepares POWERUP_TILE_BASE=19 for src/powerup.c (Task 7).

Closes partial: #287"
```

---

### Task 6: TMX heal pad tiles → road, `powerups` object layer, `tmx_to_c.py` extension, `config.h` powerup constants, `load_powerup_positions()` in `loader.c`

**Files:**
- Modify: `assets/maps/track.tmx` (GID 8 → GID 2 at 2 heal pad positions; add `powerups` objectgroup)
- Modify: `tools/tmx_to_c.py` (add `parse_powerup_objects()`, emit powerup arrays, add `emit_powerup_header()`)
- Regenerate: `src/track_map.c` (new powerup arrays; `make` regenerates this)
- Create: `src/track_powerup_externs.h` (extern declarations for all tracks)
- Modify: `Makefile` (add rule for `src/track_powerup_externs.h`)
- Modify: `src/config.h` (add `MAX_POWERUPS`, `POWERUP_HEAL_AMOUNT`, `POWERUP_TYPE_HEAL`, `POWERUP_TILE_BASE`; remove `DAMAGE_REPAIR_AMOUNT`)
- Modify: `src/loader.c` (add `load_powerup_positions()`)
- Modify: `src/loader.h` (add declaration)

**Depends on:** Task 5 (loader.c must be at its post-rename state before adding a new function)
**Parallelizable with:** none — depends on Task 5

**Step 1: Verify GID 8 positions in `track.tmx`**

```bash
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('assets/maps/track.tmx')
root = tree.getroot()
layer = root.find('layer[@name=\"Track\"]')
data = [int(x.strip()) for x in layer.find('data').text.strip().split(',')]
w = int(layer.get('width'))
hits = [(i % w, i // w) for i, g in enumerate(data) if g == 8]
print('GID 8 (heal pad) positions (tx, ty):', hits)
"
```

Expected: `GID 8 (heal pad) positions (tx, ty): [(11, 20), (8, 96)]`
If extra positions appear, stop and investigate before patching.

**Step 2: Replace GID 8 → GID 2 (road) and add `powerups` objectgroup in `track.tmx`**

```bash
python3 - <<'EOF'
import xml.etree.ElementTree as ET
ET.register_namespace('', '')
tree = ET.parse('assets/maps/track.tmx')
root = tree.getroot()

# Patch heal pad BG tiles → road
layer = root.find('layer[@name="Track"]')
data_el = layer.find('data')
tokens = data_el.text.strip().split(',')
data = [int(t.strip()) for t in tokens]
w = int(layer.get('width'))
targets = {(11, 20), (8, 96)}
changed = 0
for i, g in enumerate(data):
    tx, ty = i % w, i // w
    if g == 8 and (tx, ty) in targets:
        data[i] = 2
        changed += 1
assert changed == 2, f"Expected 2 changes, got {changed}"
data_el.text = '\n' + ','.join(str(g) for g in data) + '\n'

# Add powerups objectgroup
import xml.etree.ElementTree as ET2
og = ET2.SubElement(root, 'objectgroup')
og.set('name', 'powerups')
# Heal pad at tile (11,20): pixel (88,160)
obj1 = ET2.SubElement(og, 'object')
obj1.set('id', '200')
obj1.set('name', 'heal')
obj1.set('x', '88')
obj1.set('y', '160')
obj1.set('width', '8')
obj1.set('height', '8')
# Heal pad at tile (8,96): pixel (64,768)
obj2 = ET2.SubElement(og, 'object')
obj2.set('id', '201')
obj2.set('name', 'heal')
obj2.set('x', '64')
obj2.set('y', '768')
obj2.set('width', '8')
obj2.set('height', '8')

tree.write('assets/maps/track.tmx', encoding='unicode', xml_declaration=False)
print(f"Patched {changed} heal pad tiles to road. Added powerups objectgroup with 2 objects.")
EOF
```

**Step 3: Verify**

```bash
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('assets/maps/track.tmx')
root = tree.getroot()
layer = root.find('layer[@name=\"Track\"]')
data = [int(x.strip()) for x in layer.find('data').text.strip().split(',')]
hits = [i for i, g in enumerate(data) if g == 8]
print('Remaining GID 8 count:', len(hits))
pog = root.find('objectgroup[@name=\"powerups\"]')
objs = pog.findall('object') if pog is not None else []
print('Powerup objects:', [(o.get('name'), o.get('x'), o.get('y')) for o in objs])
"
```

Expected:
```
Remaining GID 8 count: 0
Powerup objects: [('heal', '88', '160'), ('heal', '64', '768')]
```

**Step 4: Extend `tools/tmx_to_c.py`**

Add the following to `tmx_to_c.py`:

```python
# Powerup type map — must match POWERUP_TYPE_* in src/config.h
POWERUP_TYPE_MAP = {
    'heal': 0,
}
MAX_POWERUPS_PY = 4  # must match MAX_POWERUPS in config.h

def parse_powerup_objects(root):
    """Extract powerup spawn data from the 'powerups' object layer.

    Each object must be snapped to an 8px tile grid.
    Supported object names: 'heal' → POWERUP_TYPE_HEAL (0).
    Returns a list of (tx, ty, type_val) tuples capped at MAX_POWERUPS_PY.
    Returns empty list if layer is absent or empty.
    """
    powerups = []
    for og in root.findall('objectgroup'):
        if og.get('name') != 'powerups':
            continue
        for obj in og.findall('object'):
            name = obj.get('name', '').strip()
            type_val = POWERUP_TYPE_MAP.get(name)
            if type_val is None:
                raise ValueError(f"Unknown powerup name '{name}' — add to POWERUP_TYPE_MAP")
            px = float(obj.get('x', 0))
            py = float(obj.get('y', 0))
            tx = int(px) // 8
            ty = int(py) // 8
            powerups.append((tx, ty, type_val))
            if len(powerups) >= MAX_POWERUPS_PY:
                break
        break  # only process first 'powerups' layer
    return powerups
```

In `tmx_to_c()`, after the NPC arrays are written, add:

```python
    powerups = parse_powerup_objects(root)
    pu_count = len(powerups)
    pu_tx   = [t[0] for t in powerups] + [0] * (MAX_POWERUPS_PY - pu_count)
    pu_ty   = [t[1] for t in powerups] + [0] * (MAX_POWERUPS_PY - pu_count)
    pu_type = [t[2] for t in powerups] + [0] * (MAX_POWERUPS_PY - pu_count)

    f.write(f"\nBANKREF({prefix}_powerup_count)\n")
    f.write(f"const uint8_t {prefix}_powerup_count = {pu_count}u;\n\n")
    f.write(f"BANKREF({prefix}_powerup_tx)\n")
    f.write(f"const uint8_t {prefix}_powerup_tx[4] = {{ {fmt_arr(pu_tx)} }};\n\n")
    f.write(f"BANKREF({prefix}_powerup_ty)\n")
    f.write(f"const uint8_t {prefix}_powerup_ty[4] = {{ {fmt_arr(pu_ty)} }};\n\n")
    f.write(f"BANKREF({prefix}_powerup_type)\n")
    f.write(f"const uint8_t {prefix}_powerup_type[4] = {{ {fmt_arr(pu_type)} }};\n")
```

Also add `emit_powerup_header(out_path, tmx_paths)` following the `emit_npc_header` pattern:

```python
def emit_powerup_header(out_path, tmx_paths):
    """Generate src/track_powerup_externs.h with extern declarations for all tracks."""
    prefixes = []
    for i, p in enumerate(tmx_paths):
        prefixes.append('track' if i == 0 else f'track{i + 1}')

    lines = [
        '/* GENERATED — do not edit by hand. Regenerate with:',
        ' *   python3 tools/tmx_to_c.py --emit-powerup-header src/track_powerup_externs.h \\',
        ' *     assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx',
        ' */',
        '#ifndef TRACK_POWERUP_EXTERNS_H',
        '#define TRACK_POWERUP_EXTERNS_H',
        '',
        '#include <stdint.h>',
        '#include "banking.h"',
        '',
    ]
    for prefix in prefixes:
        lines += [
            f'extern const uint8_t  {prefix}_powerup_count;',
            f'extern const uint8_t  {prefix}_powerup_tx[];',
            f'extern const uint8_t  {prefix}_powerup_ty[];',
            f'extern const uint8_t  {prefix}_powerup_type[];',
            f'BANKREF_EXTERN({prefix}_powerup_count)',
            f'BANKREF_EXTERN({prefix}_powerup_tx)',
            f'BANKREF_EXTERN({prefix}_powerup_ty)',
            f'BANKREF_EXTERN({prefix}_powerup_type)',
            '',
        ]
    lines += ['#endif /* TRACK_POWERUP_EXTERNS_H */']
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
```

Wire the `--emit-powerup-header` flag into the `main()` argument parser (follow the `--emit-header` pattern).

**Step 5: Run `tools/test_tmx_to_c.py` to verify**

```bash
python3 -m unittest tests.test_tmx_to_c -v
```

Expected: PASS (existing tests still pass; new powerup parsing is tested by verifying count/tx/ty in the output for a TMX with a powerups layer).

If tests fail, fix `tmx_to_c.py` before continuing.

**Step 6: Generate `src/track_powerup_externs.h`**

```bash
python3 tools/tmx_to_c.py --emit-powerup-header src/track_powerup_externs.h \
    assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx
```

Expected: `src/track_powerup_externs.h` created with extern declarations for `track_powerup_count`, `track_powerup_tx`, `track_powerup_ty`, `track_powerup_type` and their `track2_` / `track3_` equivalents.

**Step 7: Add Makefile rule for `src/track_powerup_externs.h`**

In `Makefile`, after the existing `src/track_npc_externs.h` rule (around line 40-44), add:

```makefile
# Generate powerup extern header — included by src/loader.c.
# Checked into git so CI works without Python/Tiled.
src/track_powerup_externs.h: assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx tools/tmx_to_c.py
	python3 tools/tmx_to_c.py --emit-powerup-header src/track_powerup_externs.h \
	    assets/maps/track.tmx assets/maps/track2.tmx assets/maps/track3.tmx

$(TARGET): src/track_powerup_externs.h
```

**Step 8: Update `src/config.h`**

Add powerup constants. Remove `DAMAGE_REPAIR_AMOUNT` (dead after player.c cleanup in Task 8):

```c
/* Powerup pool */
#define MAX_POWERUPS         4u
#define POWERUP_TYPE_HEAL    0u   /* must match POWERUP_TYPE_MAP['heal'] in tools/tmx_to_c.py */
#define POWERUP_HEAL_AMOUNT  50u  /* HP restored on collect */
#define POWERUP_TILE_BASE    19u  /* VRAM sprite tile slot — after turret (18); shares slot 19
                                   * with OVERMAP_CAR_TILE_BASE+1 (mutual exclusion by state) */
```

Remove this line from config.h:
```c
#define DAMAGE_REPAIR_AMOUNT       20u   /* HP restored by TILE_REPAIR */
```

**Step 9: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `loader.c` (bank 0) entry exists in `bank-manifest.json`. `src/track_powerup_externs.h` is a header only — no manifest entry needed.

**Step 10: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent: *"In `loader.c` (bank 0, NONBANKED), implement `load_powerup_positions(uint8_t id, uint8_t *out_tx, uint8_t *out_ty, uint8_t *out_type, uint8_t *out_count)` following the same SWITCH_ROM pattern as `load_npc_positions()`. The function reads from `{prefix}_powerup_count`, `{prefix}_powerup_tx`, `{prefix}_powerup_ty`, `{prefix}_powerup_type` arrays (declared in `src/track_powerup_externs.h`). id=0→track, id=1→track2, id=2→track3. Out buffer must be at least MAX_POWERUPS bytes. Confirm the implementation is safe."*

**Step 11: Implement `load_powerup_positions()` in `loader.c` and `loader.h`**

In `src/loader.c`, add `#include "track_powerup_externs.h"` near the top, then add the function following `load_npc_positions()`:

```c
void load_powerup_positions(uint8_t id,
                             uint8_t *out_tx,
                             uint8_t *out_ty,
                             uint8_t *out_type,
                             uint8_t *out_count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 1u) {
        SWITCH_ROM(BANK(track2_powerup_count));
        n = track2_powerup_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track2_powerup_tx[i];
            out_ty[i]   = track2_powerup_ty[i];
            out_type[i] = track2_powerup_type[i];
        }
    } else if (id == 2u) {
        SWITCH_ROM(BANK(track3_powerup_count));
        n = track3_powerup_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track3_powerup_tx[i];
            out_ty[i]   = track3_powerup_ty[i];
            out_type[i] = track3_powerup_type[i];
        }
    } else {
        SWITCH_ROM(BANK(track_powerup_count));
        n = track_powerup_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track_powerup_tx[i];
            out_ty[i]   = track_powerup_ty[i];
            out_type[i] = track_powerup_type[i];
        }
    }
    *out_count = n;
    SWITCH_ROM(saved);
}
```

In `src/loader.h`, add:

```c
/* Copies powerup spawn arrays for track `id` (0=track, 1=track2, 2=track3).
 * Output buffers must be at least MAX_POWERUPS bytes each.
 * out_type receives POWERUP_TYPE_* values. */
void load_powerup_positions(uint8_t id,
                             uint8_t *out_tx,
                             uint8_t *out_ty,
                             uint8_t *out_type,
                             uint8_t *out_count) NONBANKED;
```

**Step 12: Rebuild and verify**

```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: zero errors. `src/track_map.c` is regenerated with powerup arrays.

```bash
make test
```

Expected: PASS (no breakage from config.h removal of `DAMAGE_REPAIR_AMOUNT` yet — that's cleaned up in Task 8).

Wait — `DAMAGE_REPAIR_AMOUNT` is removed in Step 8 above, but `tests/test_damage.c` and `tests/test_player.c` still reference it. Remove `DAMAGE_REPAIR_AMOUNT` from config.h **only after** updating those test files. Move the config.h removal to Task 8 to avoid breaking the test suite here.

Revised Step 8: Add only the new constants to `config.h` (do NOT remove `DAMAGE_REPAIR_AMOUNT` yet):

```c
/* Powerup pool */
#define MAX_POWERUPS         4u
#define POWERUP_TYPE_HEAL    0u
#define POWERUP_HEAL_AMOUNT  50u
#define POWERUP_TILE_BASE    19u
```

The `DAMAGE_REPAIR_AMOUNT` removal and test cleanup go in Task 8.

**Step 13: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill. Verify bank placements and ROM budgets pass.

**Step 14: Refactor checkpoint**

Check: any track file (`track2_map.c`, `track3_map.c`) that doesn't have a `powerups` layer in its TMX — those must emit `count=0` and 1-element placeholder arrays (same pattern as empty checkpoints). Verify by inspecting `src/track2_map.c` and `src/track3_map.c` after rebuild:

```bash
grep "powerup_count" src/track2_map.c src/track3_map.c
```

Expected: `const uint8_t track2_powerup_count = 0u;` and `const uint8_t track3_powerup_count = 0u;`

**Step 15: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/loader.c`. Report issues, do not apply fixes.

**Step 16: Commit**

```bash
git add assets/maps/track.tmx tools/tmx_to_c.py src/track_map.c src/track2_map.c src/track3_map.c \
    src/track_powerup_externs.h Makefile src/config.h src/loader.c src/loader.h
git commit -m "feat(powerup): add powerups TMX layer, tmx_to_c extension, config constants, load_powerup_positions

- track.tmx: heal pad BG tiles (11,20)+(8,96) → road; new 'powerups' objectgroup
- tmx_to_c.py: parse_powerup_objects() + emit_powerup_header() + --emit-powerup-header flag
- track_powerup_externs.h: generated extern declarations for all 3 tracks
- config.h: MAX_POWERUPS=4, POWERUP_HEAL_AMOUNT=50, POWERUP_TYPE_HEAL=0, POWERUP_TILE_BASE=19
- loader.c/h: load_powerup_positions() NONBANKED following load_npc_positions() pattern

Closes partial: #287"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 3

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 5 | No upstream dependency; must complete before Task 6 (shared loader.c output) |
| B (sequential) | Task 6 | Depends on Task 5 — reads loader.c at its post-rename state |

---

### Smoketest Checkpoint 3 — heal pad BG tile gone; existing turret behavior unchanged

**Step 1: Fetch and merge latest master**
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
Expected: all budgets PASS. VRAM +1 tile (heal pad sprite slot 19) — net zero vs. removed BG tile entries.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

Ask the user to:
1. Start a race on track 1. Drive to where the heal pads used to be — tiles (11,20) and (8,96). Verify the BG shows road, not a repair pad tile.
2. Verify turrets still appear as OAM sprites and still fire (no regression from Task 5 sprite/loader change).
3. Verify killing a turret still clears the OAM sprite and shows road beneath it.

---

## Batch 4 — Heal Powerup: Module + Integration + Cleanup

### Task 7: `src/powerup.c` + `src/powerup.h` + `tests/test_powerup.c` + `bank-manifest.json`

**Files:**
- Create: `src/powerup.h`
- Create: `src/powerup.c`
- Create: `tests/test_powerup.c`
- Modify: `bank-manifest.json`

**Depends on:** Task 6 (needs `config.h` powerup constants and `track_powerup_externs.h`)
**Parallelizable with:** none — Task 8 needs `powerup.h` to wire `state_playing.c`

**Step 1: Write the failing tests in `tests/test_powerup.c`**

```c
#include "unity.h"
#include "powerup.h"
#include "config.h"

void setUp(void)    { powerup_init_empty(); }
void tearDown(void) {}

void test_powerup_pool_empty_after_init_empty(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, powerup_count_active());
}

void test_powerup_type_constant_defined(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, POWERUP_TYPE_HEAL);
}

void test_powerup_spawn_and_active(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    TEST_ASSERT_EQUAL_UINT8(1u, powerup_count_active());
}

void test_powerup_no_collect_when_player_elsewhere(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    powerup_update(10u, 10u);
    TEST_ASSERT_EQUAL_UINT8(1u, powerup_count_active());
}

void test_powerup_collect_deactivates(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    powerup_update(5u, 5u);  /* player at same tile → collect */
    TEST_ASSERT_EQUAL_UINT8(0u, powerup_count_active());
}

void test_powerup_collect_is_one_shot(void) {
    powerup_test_spawn(5u, 5u, POWERUP_TYPE_HEAL);
    powerup_update(5u, 5u);  /* collect */
    powerup_update(5u, 5u);  /* second pass — no active powerup */
    TEST_ASSERT_EQUAL_UINT8(0u, powerup_count_active());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_powerup_pool_empty_after_init_empty);
    RUN_TEST(test_powerup_type_constant_defined);
    RUN_TEST(test_powerup_spawn_and_active);
    RUN_TEST(test_powerup_no_collect_when_player_elsewhere);
    RUN_TEST(test_powerup_collect_deactivates);
    RUN_TEST(test_powerup_collect_is_one_shot);
    return UNITY_END();
}
```

**Step 2: Run test to verify it fails**

```bash
make test
```

Expected: FAIL — `powerup.h` not found, build stops at `test_powerup` binary.

**Step 3: HARD GATE — bank-manifest.json**

Add entry to `bank-manifest.json` before writing `src/powerup.c`:

```json
"src/powerup.c": {"bank": 255, "reason": "autobank — gameplay module called via invoke() in state_manager.c"}
```

**Step 4: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm the new entry in `bank-manifest.json`.

**Step 5: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent: *"Implement `src/powerup.c` and `src/powerup.h` for Nuke Raider GBC. Requirements: SoA pool (MAX_POWERUPS=4) with `powerup_tx[]`, `powerup_ty[]`, `powerup_type[]`, `powerup_active[]`, `powerup_oam[]` (all `static uint8_t`). `#pragma bank 255`. Public API (all BANKED): `powerup_init(void)` calls `load_powerup_positions(track_get_id(), ...)` then allocates OAM via `get_sprite()` + `set_sprite_tile(oam, POWERUP_TILE_BASE)`; `powerup_init_empty(void)` zeros pool (for tests — no hardware calls); `powerup_update(uint8_t player_tx, uint8_t player_ty)` tile-based detection: if `powerup_active[i] && player_tx==powerup_tx[i] && player_ty==powerup_ty[i]` → `damage_heal(POWERUP_HEAL_AMOUNT)`, `sfx_play(SFX_HEAL)`, `clear_sprite(oam)`, `powerup_active[i]=0`; `powerup_render(void)` calls `move_sprite(oam, oam_x, oam_y)` using `cam_y` (same pattern as `enemy_render()`); `powerup_count_active(void)` returns active count. Under `#ifndef __SDCC`: `powerup_test_spawn(tx,ty,type)` adds to pool (OAM = SPRITE_POOL_INVALID for host tests), plus read accessors `powerup_get_active/type/tx/ty(i)`. Constraints: uint8_t loops, no malloc, no float, no compound literals."*

**Step 6: Write implementation from gbdk-expert output**

Write `src/powerup.h` and `src/powerup.c` from the gbdk-expert output. Verify against the requirements above.

**Step 7: Run tests to verify they pass**

```bash
make test
```

Expected: PASS — all 6 test_powerup tests green.

**Step 8: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: zero errors.

**Step 9: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill. Verify bank placements. Check OAM budget: player=4, dialog=1, projectiles≤8, turrets≤8, powerups≤4 → total ≤ 25, well within 40 limit.

**Step 10: Refactor checkpoint**

"Does `powerup_update()` work correctly when MAX_POWERUPS=4 and all 4 are collected? What happens when `get_sprite()` returns `SPRITE_POOL_INVALID` for all 4 powerups?" Verify the OAM guard is in place: `if (powerup_oam[i] != SPRITE_POOL_INVALID) { clear_sprite(powerup_oam[i]); }`.

**Step 11: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/powerup.c`. Report issues, do not apply fixes.

**Step 12: Commit**

```bash
git add src/powerup.h src/powerup.c tests/test_powerup.c bank-manifest.json
git commit -m "feat(powerup): add generic powerup module with SoA pool and tile-based collection

MAX_POWERUPS=4, POWERUP_TYPE_HEAL=0 (50HP single-contact collect).
powerup_update() fires damage_heal + sfx_play(SFX_HEAL) on tile match.
TDD: 6 host-side tests pass with make test.

Closes partial: #287"
```

---

### Task 8: `player.c` cleanup + `track.c`/`track.h` LUT cleanup + test cleanup + `state_playing.c` wiring

**Files:**
- Modify: `src/player.c` (remove TILE_REPAIR block + `prev_on_repair` static)
- Modify: `src/track.c` (shrink LUT: remove TILE_REPAIR and TILE_TURRET entries; `TILE_LUT_LEN` 9 → 7)
- Modify: `src/track.h` (remove `#define TILE_REPAIR 5u` and `#define TILE_TURRET 7u`)
- Modify: `src/config.h` (remove `DAMAGE_REPAIR_AMOUNT 20u`)
- Modify: `src/state_playing.c` (add `powerup_init()`, `powerup_render()`, `powerup_update()`)
- Modify: `tests/test_track.c` (remove tests referencing removed constants; update tile count comment)
- Modify: `tests/test_damage.c` (replace `DAMAGE_REPAIR_AMOUNT` → `20u`)
- Modify: `tests/test_player.c` (replace `DAMAGE_REPAIR_AMOUNT` → `20u`)

**Depends on:** Task 7 (`powerup.h` must exist before `state_playing.c` can include it)
**Parallelizable with:** none — depends on Task 7

**Step 1: Audit test files for removed constants**

Before touching any test file, verify every reference to the constants being removed:

```bash
grep -rn "DAMAGE_REPAIR_AMOUNT\|TILE_REPAIR\|TILE_TURRET" tests/
```

Expected output (verify it matches exactly before proceeding):
- `tests/test_damage.c`: `DAMAGE_REPAIR_AMOUNT` on lines 136, 142, 143
- `tests/test_player.c`: `DAMAGE_REPAIR_AMOUNT` on line 253
- `tests/test_track.c`: `TILE_REPAIR` on lines 96, 138, 176, 180; `TILE_TURRET` on lines 176, 177, 178, 179, 180; tile count test on line 107

If any other files appear, stop and update the plan before proceeding.

**Step 2: Write the failing test (pre-conditions)**

The cleanup is tested via compilation. Add to `tests/test_track.c` a new test replacing the old ones:

```c
/* After LUT shrink: tile indices 7 and 8 are OOB → road (passable).
 * tile_data_count stays 9 — tileset PNG unchanged; only LUT shrank. */
void test_tile_lut_len_is_7(void) {
    /* Tile index 6 = TILE_FINISH — last valid LUT entry */
    TEST_ASSERT_EQUAL_UINT8(TILE_FINISH, track_tile_type_from_index(6u));
    /* Tile index 7 = OOB → treated as road */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(7u));
    /* Tile index 8 = OOB → treated as road */
    TEST_ASSERT_EQUAL_UINT8(TILE_ROAD, track_tile_type_from_index(8u));
}
```

Add `RUN_TEST(test_tile_lut_len_is_7)` to `main()` in `test_track.c`.

Remove these test functions and their `RUN_TEST` calls from `tests/test_track.c`:
- `test_tile_type_from_index_repair` (line 95–97) — references `TILE_REPAIR`
- `test_track_tile_type_repair` (lines 136–139) — references `TILE_REPAIR`; tile (12,40) is no longer a repair pad after TMX cleanup
- `test_tile_turret_not_passable` (lines 175–181) — references `TILE_REPAIR` and `TILE_TURRET`

Update the comment in `test_track_tile_data_count_is_9` (line 106):
```c
/* tileset PNG has 9 tiles (0–8). LUT only maps 0–6 (indices 7–8 no longer placed in maps).
 * track_tile_data_count counts raw PNG tiles, not LUT entries. */
TEST_ASSERT_EQUAL_UINT8(9u, track_tile_data_count);
```

In `tests/test_damage.c`, replace:
- Line 136: `damage_heal(DAMAGE_REPAIR_AMOUNT);` → `damage_heal(20u);`
- Line 142: `damage_heal(DAMAGE_REPAIR_AMOUNT);` → `damage_heal(20u);`
- Line 143: `TEST_ASSERT_EQUAL_UINT8(DAMAGE_REPAIR_AMOUNT, damage_get_hp());` → `TEST_ASSERT_EQUAL_UINT8(20u, damage_get_hp());`

In `tests/test_player.c`, replace:
- Line 253: `damage_heal(DAMAGE_REPAIR_AMOUNT);             /* hp += 20 → 99 */` → `damage_heal(20u);             /* hp += 20 → 99 */`

Run:
```bash
make test
```

Expected: FAIL — `TILE_REPAIR`, `TILE_TURRET`, `DAMAGE_REPAIR_AMOUNT` undefined (compile errors in test files that haven't been updated yet, or in src files). Fix each file below.

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write` skill. Confirm manifest entries for:
- `src/player.c` (bank 255, autobank)
- `src/track.c` (bank 255, autobank)
- `src/state_playing.c` (bank 255, autobank)

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert` agent: *"Review these 3 changes for correctness: (1) Remove `prev_on_repair` static local and the TILE_REPAIR block from `player_update()` in `player.c` — the static is `static uint8_t prev_on_repair = 0u;` inside a block. Confirm removing it is safe (no other code in player.c references it). (2) Shrink `tile_type_lut[TILE_LUT_LEN]` in `track.c` from 9 to 7 entries by removing `TILE_REPAIR` and `TILE_TURRET` rows; set `TILE_LUT_LEN` to 7. Confirm `track_tile_type_from_index()` OOB guard still handles indices 7 and 8 safely. (3) Wire `powerup_init()` in `state_playing.c enter()`, `powerup_render()` in the VBlank phase, and `powerup_update((uint8_t)(px >> 3u), (uint8_t)(py >> 3u))` in the logic phase. Show where each call fits in the existing function bodies."*

**Step 5: Apply all changes**

*`src/player.c`* — remove the TILE_REPAIR block (lines 172–186 per original numbering):

```c
/* Remove this entire block: */
    /* Repair tile: heal HP when standing on a repair pad. ... */
    {
        static uint8_t prev_on_repair = 0u;
        if (terrain == TILE_REPAIR) {
            damage_heal(DAMAGE_REPAIR_AMOUNT);
            if (!prev_on_repair) {
                sfx_play(SFX_HEAL);
            }
            prev_on_repair = 1u;
        } else {
            prev_on_repair = 0u;
        }
    }
```

Also remove the `#include "track.h"` if `TILE_REPAIR` was its only use — but verify first: `track_passable()` and other track functions are used in `player.c`, so `track.h` stays.

*`src/track.c`* — shrink LUT:

```c
/* Before */
#define TILE_LUT_LEN 9u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
    TILE_FINISH, /* 6: finish line */
    TILE_REPAIR, /* 7: repair pad */
    TILE_TURRET, /* 8: turret emplacement — impassable while active */
};

/* After */
#define TILE_LUT_LEN 7u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
    TILE_FINISH, /* 6: finish line */
    /* Indices 7-8 (formerly repair, turret) removed — no longer placed in maps.
     * track_tile_type_from_index() returns TILE_ROAD for OOB indices. */
};
```

*`src/track.h`* — remove dead defines:

```c
/* Remove these two lines: */
#define TILE_REPAIR 5u
#define TILE_TURRET  7u
```

*`src/config.h`* — remove `DAMAGE_REPAIR_AMOUNT`:

```c
/* Remove this line: */
#define DAMAGE_REPAIR_AMOUNT       20u   /* HP restored by TILE_REPAIR */
```

*`src/state_playing.c`* — add include and wiring:

Add `#include "powerup.h"` to the include block at the top.

In `enter()`, after `enemy_init()`:
```c
    enemy_init();
    powerup_init();   /* load powerup positions for this track */
```

In `update()`, VBlank phase (after `enemy_render()`):
```c
    enemy_render();
    powerup_render();
```

In `update()`, logic phase (after `enemy_update(px, py)`):
```c
        enemy_update(px, py);
        powerup_update((uint8_t)((uint16_t)px >> 3u), (uint8_t)((uint16_t)py >> 3u));
```

**Step 6: Run tests**

```bash
make test
```

Expected: PASS — all test binaries green.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke `bank-post-build` skill. Verify bank placements and all budgets PASS.

**Step 9: Refactor checkpoint**

"Does `powerup_update()` receive the correct tile coordinates? `px >> 3` converts pixel X to tile X — verify this matches the coordinate system used in `track_tile_type()` (which also divides by 8)."

Check: `DAMAGE_REPAIR_AMOUNT` — now fully removed. Check `test_damage.c` and `test_player.c` compile without it.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke `gb-c-optimizer` on `src/player.c`, `src/track.c`, `src/state_playing.c`. Report issues, do not apply fixes.

**Step 11: Commit**

```bash
git add src/player.c src/track.c src/track.h src/config.h src/state_playing.c \
    tests/test_track.c tests/test_damage.c tests/test_player.c
git commit -m "feat(powerup): wire powerup module; remove TILE_REPAIR/TILE_TURRET dead code

state_playing: powerup_init/render/update wired in enter/VBlank/logic phases.
player.c: remove TILE_REPAIR heal block and prev_on_repair static.
track.c/h: LUT shrinks 9→7; TILE_REPAIR+TILE_TURRET defines removed.
config.h: DAMAGE_REPAIR_AMOUNT removed (dead — powerup uses POWERUP_HEAL_AMOUNT).
Tests: DAMAGE_REPAIR_AMOUNT references replaced with literal 20u; stale tile tests removed.

Closes partial: #287"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 4

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 7 | New files (powerup.c/h); no upstream dependency within Batch 4 |
| B (sequential) | Task 8 | Depends on Task 7 — state_playing.c needs powerup.h |

---

### Smoketest Checkpoint 4 — heal powerup spawns, heals, disappears on collect

**Step 1: Fetch and merge latest master**
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
Expected: all budgets PASS. WRAM +20 bytes (powerup SoA pool); OAM ≤ 25 used; VRAM net zero.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

Ask the user to:
1. Start a race on track 1. Verify two heal pad sprites appear at approximately tiles (11,20) and (8,96) — they scroll with the camera.
2. Drive over one heal pad — verify the OAM sprite disappears on contact and HP increases by 50.
3. Drive over the same tile again — verify nothing happens (one-shot collect, powerup gone).
4. Verify no TILE_REPAIR regression: the old static repair pads should NOT appear anywhere on the track.
5. Verify turret behavior unchanged (fire, disappear on kill).
6. Verify player takes damage from turret projectiles (no regression).

---

## Plan Self-Review Checklist

| # | Check | Status |
|---|-------|--------|
| 1 | No hardcoded values | ✓ All tile GIDs resolved at plan-time (GID 9→2, GID 8→2); all constants from `config.h`; powerup pixel coords derived from tile coords × 8 |
| 2 | All tasks have explicit test criteria | ✓ Every task states `make test` command + expected output |
| 3 | Parallel annotations justified | ✓ See below |
| 4 | Parallel Execution Groups tables present | ✓ Before each Smoketest Checkpoint |
| 5 | No implementation details leaked from brainstorming | ✓ |

**Parallelism justifications:**
- Task 1 ‖ Task 2: Task 1 outputs `track_map.c` (generated, not imported by player.c). Task 2 outputs `player.c`. No shared symbol at compile time.
- Task 3 ‖ Task 4: Task 3 outputs `projectile.c`. Task 4 outputs `enemy.c` + `enemy.h`. Task 4 does not call any new symbol introduced by Task 3; existing `projectile_fire()` signature is unchanged.
- Task 5 ‖ none: writes `loader.c` and `loader.h`; Task 6 also writes these files → must be sequential.
- Task 6 ‖ none: depends on Task 5 output (`loader.c` at post-rename state); single-writer on `config.h`, `tmx_to_c.py`, `track_powerup_externs.h`.
- Task 7 ‖ none: creates new files (`powerup.c`, `powerup.h`); Task 8 requires `powerup.h` to compile `state_playing.c` → must be sequential.
- Task 8 ‖ none: depends on Task 7 (`state_playing.c` includes `powerup.h`); writes multiple shared files (`player.c`, `track.c`, `track.h`, `config.h`, `state_playing.c`) making it unsafe to split further.
