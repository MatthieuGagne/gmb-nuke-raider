# LASER Primary Weapon Damage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LASER primary weapon deal more damage per bullet hit than CANNON, so a player who buys LASER at TRADER kills enemies in fewer shots.

**Architecture:** `projectile.c` caches a single per-hit damage value (default CANNON = 1). `projectile_check_hit_enemy()` returns that cached value on a hit (0 on miss) instead of a bare 0/1 flag. A new pure `enemy_apply_damage(hp, dmg)` helper in `enemy_common.c` subtracts damage floored at 0, so raising damage above 1 can't underflow a 1-HP enemy (e.g. TURRET_HP=1) to 255. `state_playing.c` seeds the cache from the loadout at race start — mirroring the `damage_init()` / `damage_set_armor_tier()` pattern from #423.

**Tech Stack:** GBDK-2020 / SDCC (C, Game Boy), Unity host-side unit tests (gcc), Make.

## Global Constraints

- **LASER damage = 2** (`WEAPON1_LASER_DAMAGE = 2u`); CANNON damage = 1 (`WEAPON1_CANNON_DAMAGE = 1u`). Racer/patrol (HP=5) die in 3 hits; turret (HP=1) dies in 1 hit.
- **Only `PROJ_OWNER_PLAYER` projectiles are affected.** Enemy bullets (`projectile_check_hit_player`) are unchanged and keep returning a 0/1 flag.
- **No change to fire cooldown, projectile speed, count, TTL, or sprite** — damage-per-hit only.
- **Ordering matters:** `projectile_init()` resets the damage cache to `WEAPON1_CANNON_DAMAGE`; `projectile_set_weapon1_damage(...)` MUST be called *after* `projectile_init()`.
- **SDCC C89-ish rule:** all local variable declarations go at the start of a block (no mid-block declarations).
- **No new `.c` file** → no `bank-manifest.json` change. `projectile.c`, `enemy_common.c`, `racer.c`, `turret.c`, `patrol.c`, `state_playing.c` are all `#pragma bank 255`.
- **Test harness:** every test binary links all of `src/*.c` (except `main.c`) via `TEST_LIB_SRC`, so new functions are linked automatically — no Makefile edit. `make test` stops at the first failing binary (alphabetical); fix earliest-first.
- **Every `src/*.c`/`src/*.h` write** triggers the `bank-pre-write` hook automatically and should be implemented via the `gbdk-expert` agent. After the ROM build, `bank-post-build` + `make memory-check` fire automatically.

---

### Task 1: `enemy_apply_damage` underflow-safe HP subtraction helper

Adds a shared pure helper so any enemy HP pool can take damage > 1 without a `uint8_t` underflow. This is the fix for the turret case (HP=1 hit for 2 must floor at 0, not wrap to 255). Fully standalone and testable.

**Files:**
- Modify: `src/enemy_common.h` (add declaration; update header comment)
- Modify: `src/enemy_common.c` (add function)
- Test: `tests/test_enemy_common.c`

**Interfaces:**
- Consumes: nothing.
- Produces: `uint8_t enemy_apply_damage(uint8_t hp, uint8_t dmg) BANKED;` — returns `hp - dmg` floored at 0. `dmg >= hp` yields 0.

- [ ] **Step 1: Write the failing tests**

Add this test group to `tests/test_enemy_common.c`, immediately before the `int main(void)` at line 166:

```c
/* ---- enemy_apply_damage: underflow-safe HP subtraction (#424) ---- */

void test_apply_damage_basic(void) {
    /* 5 HP minus 2 -> 3 */
    TEST_ASSERT_EQUAL_UINT8(3u, enemy_apply_damage(5u, 2u));
}
void test_apply_damage_cannon_single(void) {
    /* 1 damage decrements by 1 (CANNON parity) */
    TEST_ASSERT_EQUAL_UINT8(4u, enemy_apply_damage(5u, 1u));
}
void test_apply_damage_exact_kill(void) {
    /* dmg == hp -> 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_apply_damage(2u, 2u));
}
void test_apply_damage_turret_underflow(void) {
    /* TURRET_HP=1 hit for LASER (2) must floor at 0, NOT wrap to 255 */
    TEST_ASSERT_EQUAL_UINT8(0u, enemy_apply_damage(1u, 2u));
}
```

Register them in `main()` by adding these lines after `RUN_TEST(test_ram_overlap_misses_beyond_reach);` (line 204):

```c
    RUN_TEST(test_apply_damage_basic);
    RUN_TEST(test_apply_damage_cannon_single);
    RUN_TEST(test_apply_damage_exact_kill);
    RUN_TEST(test_apply_damage_turret_underflow);
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from the worktree dir, PowerShell — see `CLAUDE.local.md`):
```powershell
$env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
make test
```
Expected: FAIL — `test_enemy_common` fails to compile/link with an implicit-declaration / undefined-reference error for `enemy_apply_damage`.

- [ ] **Step 3: Add the declaration to `src/enemy_common.h`**

Update the header top comment (line 8) from:
```c
/* Shared enemy-AI math used by turret.c, racer.c, and (PR4) patrol.c.
 * All functions are pure (no side effects, no static state). */
```
to:
```c
/* Shared enemy AI and combat math used by turret.c, racer.c, and patrol.c.
 * All functions are pure (no side effects, no static state). */
```

Add this declaration immediately before the final `#endif /* ENEMY_COMMON_H */` (after the `enemy_ram_overlap` declaration at line 34):
```c
/* Subtract dmg from an enemy HP pool, flooring at 0 (no uint8_t underflow).
 * Returns the new HP; dmg >= hp yields 0 (dead), never wraps to 255. Shared by
 * racer.c, turret.c, and patrol.c so per-hit damage above 1 (e.g. LASER = 2 vs
 * TURRET_HP = 1) can't wrap a low-HP enemy to 255 (#424). */
uint8_t enemy_apply_damage(uint8_t hp, uint8_t dmg) BANKED;
```

- [ ] **Step 4: Add the implementation to `src/enemy_common.c`**

Append this function at the end of the file (after `enemy_ram_overlap`, line 71):
```c
/* enemy_apply_damage — subtract dmg from hp, floored at 0 (underflow-safe). */
uint8_t enemy_apply_damage(uint8_t hp, uint8_t dmg) BANKED {
    return (dmg >= hp) ? 0u : (uint8_t)(hp - dmg);
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```powershell
make test
```
Expected: PASS — `test_enemy_common` green (all prior tests still pass; 4 new asserts pass). Note `make test` runs binaries alphabetically and stops at the first failure; if an earlier binary fails, it is unrelated to this change — investigate separately.

- [ ] **Step 6: Commit**

```powershell
git add src/enemy_common.h src/enemy_common.c tests/test_enemy_common.c
git commit -m @'
feat(enemy): underflow-safe enemy_apply_damage helper (#424)

Adds a shared pure helper flooring HP subtraction at 0 so per-hit
damage above 1 can't wrap a 1-HP enemy (TURRET_HP) to 255.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
'@
```

---

### Task 2: Per-weapon damage cache in `projectile.c` + config constants

Adds the tunable config constants and makes `projectile_check_hit_enemy()` return the cached per-hit damage (0 on miss). Adds the setter and the `projectile_init()` reset. `projectile_check_hit_player()` is left untouched (enemy bullets unchanged).

**Files:**
- Modify: `src/config.h` (add `WEAPON1_CANNON_DAMAGE`, `WEAPON1_LASER_DAMAGE`, `WEAPON1_DAMAGE_TABLE`)
- Modify: `src/projectile.h` (declare setter; update `check_hit_enemy` doc)
- Modify: `src/projectile.c` (cache field, init reset, setter, return value)
- Test: `tests/test_projectile.c`

**Interfaces:**
- Consumes: `WEAPON1_CANNON_DAMAGE`, `WEAPON1_LASER_DAMAGE` from `config.h`.
- Produces:
  - `void projectile_set_weapon1_damage(uint8_t dmg) BANKED;`
  - `projectile_check_hit_enemy(cx, cy, r)` now returns the cached WEAPON1 damage (`>= 1`) on hit, `0` on miss (was `1`/`0`).
  - `WEAPON1_DAMAGE_TABLE[LOADOUT_OPTIONS_PER_FIELD]` = `{ WEAPON1_CANNON_DAMAGE, WEAPON1_LASER_DAMAGE }` (consumed by Task 4).

- [ ] **Step 1: Add the config constants**

In `src/config.h`, add the two scalar constants immediately after `#define ENEMY_BULLET_DAMAGE 10u` (line 35), in the damage section:
```c
#define WEAPON1_CANNON_DAMAGE      1u   /* player CANNON (tier 0): HP removed per bullet hit */
#define WEAPON1_LASER_DAMAGE       2u   /* player LASER  (tier 1): kills RACER_HP=5 in 3 hits (#424) */
```

Add the lookup table immediately after the `#endif` that closes the `LOADOUT_STRINGS_DEFINED` block (line 213), before the `/* Upgrade shop: ... */` comment (line 215):
```c
/* Per-weapon bullet damage, indexed by loadout WEAPON1 option (0=CANNON, 1=LASER).
 * Consumed by state_playing.c to seed the projectile damage cache at race start.
 * Guarded like LOADOUT_STRINGS so a TU can opt out with a pre-#define. */
#ifndef WEAPON1_DAMAGE_TABLE_DEFINED
#define WEAPON1_DAMAGE_TABLE_DEFINED
static const uint8_t WEAPON1_DAMAGE_TABLE[LOADOUT_OPTIONS_PER_FIELD] = {
    WEAPON1_CANNON_DAMAGE, WEAPON1_LASER_DAMAGE
};
#endif
```

- [ ] **Step 2: Write the failing tests**

Add this test group to `tests/test_projectile.c`, immediately before `int main(void)` (line 201). (`setUp()` already calls `projectile_init(17u)`, which after Step 4 resets the cache to CANNON, so each test starts from a known CANNON default.)

```c
/* ── per-weapon damage (#424) ─────────────────────────────────────────── */

/* check_hit_enemy returns the cached CANNON damage (default = 1) */
void test_check_hit_enemy_default_cannon_damage(void) {
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_PLAYER);
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_CANNON_DAMAGE,
                            projectile_check_hit_enemy(80u, 80u, 8u));
}

/* After set to LASER, check_hit_enemy returns the LASER damage */
void test_check_hit_enemy_laser_damage(void) {
    projectile_set_weapon1_damage(WEAPON1_LASER_DAMAGE);
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_PLAYER);
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_LASER_DAMAGE,
                            projectile_check_hit_enemy(80u, 80u, 8u));
}

/* A miss returns 0 regardless of the cached damage */
void test_check_hit_enemy_miss_returns_zero(void) {
    projectile_set_weapon1_damage(WEAPON1_LASER_DAMAGE);
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_PLAYER);
    TEST_ASSERT_EQUAL_UINT8(0u, projectile_check_hit_enemy(20u, 20u, 4u));
}

/* projectile_init() resets the cache back to CANNON */
void test_projectile_init_resets_weapon_damage(void) {
    projectile_set_weapon1_damage(WEAPON1_LASER_DAMAGE);
    projectile_init(17u);   /* must reset cache to CANNON */
    projectile_fire(80u, 80u, DIR_B, PROJ_OWNER_PLAYER);
    TEST_ASSERT_EQUAL_UINT8(WEAPON1_CANNON_DAMAGE,
                            projectile_check_hit_enemy(80u, 80u, 8u));
}
```

Register them in `main()` after `RUN_TEST(test_projectile_render_uses_tile_base);` (line 223):
```c
    RUN_TEST(test_check_hit_enemy_default_cannon_damage);
    RUN_TEST(test_check_hit_enemy_laser_damage);
    RUN_TEST(test_check_hit_enemy_miss_returns_zero);
    RUN_TEST(test_projectile_init_resets_weapon_damage);
```

- [ ] **Step 3: Run the tests to verify they fail**

Run:
```powershell
make test
```
Expected: FAIL — `test_projectile` fails to compile/link with an undefined-reference error for `projectile_set_weapon1_damage` (and the LASER/reset asserts would fail since `check_hit_enemy` still returns a hardcoded `1`).

- [ ] **Step 4: Implement in `src/projectile.c` and declare in `src/projectile.h`**

In `src/projectile.h`, replace the `check_hit_*` doc comment block (lines 20–25) with:
```c
/* Hit detection — consume the first matching projectile within radius r of (cx,cy).
 * check_hit_player: matches PROJ_OWNER_ENEMY bullets; returns 1 on hit, 0 on miss.
 * check_hit_enemy:  matches PROJ_OWNER_PLAYER bullets; returns the cached WEAPON1
 *                   per-hit damage (>= 1) on hit, 0 on miss. */
uint8_t projectile_check_hit_player(uint8_t cx, uint8_t cy, uint8_t r) BANKED;
uint8_t projectile_check_hit_enemy(uint8_t cx, uint8_t cy, uint8_t r) BANKED;
```

Add the setter declaration immediately after the `projectile_init` declaration (line 12):
```c
/* Set the per-hit damage a PLAYER bullet deals to an enemy. Seeded once at race
 * start from the loadout (see state_playing). projectile_init() resets it to
 * WEAPON1_CANNON_DAMAGE, so call this AFTER projectile_init() (#424). */
void    projectile_set_weapon1_damage(uint8_t dmg) BANKED;
```

In `src/projectile.c`:

Add the cache field after `static uint8_t s_proj_tile_base = 0u;` (line 65):
```c
static uint8_t s_weapon1_damage   = WEAPON1_CANNON_DAMAGE;  /* HP a player bullet removes per hit; re-seeded at race start (#424) */
```

In `projectile_init()`, add the reset immediately after `proj_cooldown_tick = 0u;` (line 78), before the closing brace:
```c
    s_weapon1_damage = WEAPON1_CANNON_DAMAGE;  /* reset to CANNON; state_playing re-seeds from loadout */
```

Add the setter immediately after the `projectile_init()` function (after line 79), before the `/* ── fire ── */` comment:
```c
void projectile_set_weapon1_damage(uint8_t dmg) BANKED {
    s_weapon1_damage = dmg;
}
```

In `projectile_check_hit_enemy()`, change the hit `return 1u;` (line 202) to:
```c
            return s_weapon1_damage;
```
Leave `projectile_check_hit_player()`'s `return 1u;` (line 182) unchanged.

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```powershell
make test
```
Expected: PASS — `test_projectile` green. The pre-existing `test_check_hit_enemy_player_bullet` (asserts `== 1u`) still passes because the default cache is `WEAPON1_CANNON_DAMAGE == 1`.

- [ ] **Step 6: Commit**

```powershell
git add src/config.h src/projectile.h src/projectile.c tests/test_projectile.c
git commit -m @'
feat(projectile): per-weapon damage cache, check_hit_enemy returns damage (#424)

check_hit_enemy now returns the cached WEAPON1 per-hit damage (0 on
miss). New projectile_set_weapon1_damage() setter; projectile_init()
resets the cache to CANNON. Adds WEAPON1_* config constants + table.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
'@
```

---

### Task 3: Apply returned damage in the enemy bullet-hit paths

Wires `racer.c`, `turret.c`, and `patrol.c` bullet-hit handlers to use the value returned by `projectile_check_hit_enemy()` through `enemy_apply_damage()`. Ram-collision paths are intentionally left unchanged (they use `ENEMY_RAM_DAMAGE == 1`, out of scope per R6).

**Files:**
- Modify: `src/racer.c:440-446`
- Modify: `src/turret.c:116-131`
- Modify: `src/patrol.c:296-304`
- Test: `tests/test_racer.c`

**Interfaces:**
- Consumes: `projectile_check_hit_enemy()` (returns damage, Task 2), `enemy_apply_damage()` (Task 1). All three files already `#include "enemy_common.h"`.
- Produces: no new public API. Behavior: a player bullet removes `s_weapon1_damage` HP per hit, floored at 0.

- [ ] **Step 1: Write the failing test (LASER kills a racer in 3 hits)**

Add this test to `tests/test_racer.c`, immediately after `test_racer_bullet_hit_reduces_hp` (ends at line 480). It mirrors that test's exact setup: `track_test_set_map(...)` for the flat map and `racer_spawn_for_test(...)` to place racer slot 1 at world (32,32).

```c
void test_racer_laser_kills_in_three_hits(void) {
    /* cam_y=0 (setUp). Racer at world (32,32); OAM center = (48,56).
     * With WEAPON1_LASER_DAMAGE=2, RACER_HP=5 dies in ceil(5/2)=3 hits. */
    static const uint8_t flat_map[8u * 8u] = {
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
        1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,
    };
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    uint8_t k;
    track_test_set_map(flat_map, 8u, 8u);
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    projectile_set_weapon1_damage(WEAPON1_LASER_DAMAGE);
    racer_set_hp_for_test(1u, RACER_HP);

    /* Hit 1: 5 -> 3 */
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(RACER_HP - WEAPON1_LASER_DAMAGE),
                            racer_get_hp_for_test(1u));  /* 5 - 2 = 3 */

    /* Hit 2: 3 -> 1 (drain fire cooldown first, then re-fire) */
    for (k = 0u; k < PROJ_FIRE_COOLDOWN; k++) projectile_update();
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(1u, racer_get_hp_for_test(1u));

    /* Hit 3: 1 -> 0, floored (underflow-safe), racer destroyed */
    for (k = 0u; k < PROJ_FIRE_COOLDOWN; k++) projectile_update();
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_hp_for_test(1u));
}
```

Register it in `main()` after `RUN_TEST(test_racer_bullet_hit_reduces_hp);` (line 948):
```c
    RUN_TEST(test_racer_laser_kills_in_three_hits);
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```powershell
make test
```
Expected: FAIL — `test_racer_laser_kills_in_three_hits` fails: the racer still loses only 1 HP per hit (old `racer_hp[i] - 1u` path), so after the first hit HP is 4, not 3.

- [ ] **Step 3: Update `src/racer.c` bullet-hit path**

Replace lines 440–446:
```c
                if (projectile_check_hit_enemy((uint8_t)scr_cx, (uint8_t)scr_cy, RACER_HIT_RADIUS)) {
                    racer_hp[i] = (uint8_t)(racer_hp[i] - 1u);
                    racer_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
                    if (racer_hp[i] == 0u) {
                        racer_kill(i);
                    }
                }
```
with (the `uint8_t dmg` declaration sits at the start of the enclosing `if (scr_cx >= 0 ...)` block — legal under SDCC):
```c
                uint8_t dmg = projectile_check_hit_enemy((uint8_t)scr_cx, (uint8_t)scr_cy, RACER_HIT_RADIUS);
                if (dmg) {
                    racer_hp[i] = enemy_apply_damage(racer_hp[i], dmg);
                    racer_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
                    if (racer_hp[i] == 0u) {
                        racer_kill(i);
                    }
                }
```

- [ ] **Step 4: Update `src/turret.c` bullet-hit path**

Replace lines 116–131:
```c
        if (projectile_check_hit_enemy(scr_x, scr_y, TURRET_HIT_RADIUS)) {
            turret_hp[i]--;
            if (turret_hp[i] == 0u) {
                turret_active[i] = 0u;
                if (turret_oam[i] != SPRITE_POOL_INVALID) {
                    /* Hand the OAM slot to the explosion pool.
                     * Do NOT clear_sprite here — explosion now owns this slot
                     * and will call clear_sprite when the animation finishes. */
                    explosion_spawn(turret_oam[i], s_explosion_base, 0u, 0u,
                                    turret_oam_x[i],        /* world pixel x = tx*8+8 */
                                    turret_ty[i]);           /* world tile y */
                    turret_oam[i] = SPRITE_POOL_INVALID;
                }
                continue;
            }
        }
```
with (wrap in a block so `dmg` is declared at block start; `enemy_apply_damage` floors TURRET_HP=1 hit-for-2 at 0):
```c
        {
            uint8_t dmg = projectile_check_hit_enemy(scr_x, scr_y, TURRET_HIT_RADIUS);
            if (dmg) {
                turret_hp[i] = enemy_apply_damage(turret_hp[i], dmg);
                if (turret_hp[i] == 0u) {
                    turret_active[i] = 0u;
                    if (turret_oam[i] != SPRITE_POOL_INVALID) {
                        /* Hand the OAM slot to the explosion pool.
                         * Do NOT clear_sprite here — explosion now owns this slot
                         * and will call clear_sprite when the animation finishes. */
                        explosion_spawn(turret_oam[i], s_explosion_base, 0u, 0u,
                                        turret_oam_x[i],        /* world pixel x = tx*8+8 */
                                        turret_ty[i]);           /* world tile y */
                        turret_oam[i] = SPRITE_POOL_INVALID;
                    }
                    continue;
                }
            }
        }
```

- [ ] **Step 5: Update `src/patrol.c` bullet-hit path**

Replace lines 296–304:
```c
                    if (projectile_check_hit_enemy((uint8_t)scr_cx, (uint8_t)scr_cy,
                                                   (uint8_t)PATROL_HIT_RADIUS)) {
                        patrol_hp[i]--;
                        patrol_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
                        if (patrol_hp[i] == 0u) {
                            patrol_kill(i);
                            continue;
                        }
                    }
```
with (the `uint8_t dmg` declaration sits at the start of the enclosing `if (scr_cx >= 0 ...)` block):
```c
                    uint8_t dmg = projectile_check_hit_enemy((uint8_t)scr_cx, (uint8_t)scr_cy,
                                                             (uint8_t)PATROL_HIT_RADIUS);
                    if (dmg) {
                        patrol_hp[i] = enemy_apply_damage(patrol_hp[i], dmg);
                        patrol_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
                        if (patrol_hp[i] == 0u) {
                            patrol_kill(i);
                            continue;
                        }
                    }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```powershell
make test
```
Expected: PASS — `test_racer_laser_kills_in_three_hits` passes, and the pre-existing `test_racer_bullet_hit_reduces_hp` / `test_racer_destroyed_when_hp_reaches_zero` stay green (CANNON default = 1 → `enemy_apply_damage(5,1)=4`, `enemy_apply_damage(1,1)=0`).

- [ ] **Step 7: Commit**

```powershell
git add src/racer.c src/turret.c src/patrol.c tests/test_racer.c
git commit -m @'
feat(enemy): apply per-hit weapon damage on player bullet hits (#424)

racer/turret/patrol bullet-hit paths now subtract the damage returned
by projectile_check_hit_enemy() via enemy_apply_damage (underflow-safe).
Ram paths unchanged (ENEMY_RAM_DAMAGE=1, out of scope).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
'@
```

---

### Task 4: Seed the projectile damage cache from the loadout at race start

Wires the loadout selection into the projectile damage cache at race start, mirroring the `damage_set_armor_tier(loadout_get_armor())` call from #423. This is the integration point that makes AC3 (buy LASER → fewer shots) real. Verified by clean build + smoketest (no host unit test — this is state-enter wiring).

**Files:**
- Modify: `src/state_playing.c:95` (add one call after `projectile_init(...)`)

**Interfaces:**
- Consumes: `projectile_set_weapon1_damage()` (Task 2), `WEAPON1_DAMAGE_TABLE` (Task 2, in `config.h`), `loadout_get_weapon1()` (existing, `loadout.h`). `state_playing.c` already includes `projectile.h`, `loadout.h`, and `config.h`.
- Produces: nothing.

- [ ] **Step 1: Add the seeding call**

In `src/state_playing.c`, the current enter sequence is:
```c
    projectile_init(loader_get_slot(TILE_ASSET_BULLET));
    turret_init(loader_get_slot(TILE_ASSET_TURRET));
```
Insert the seed line immediately after `projectile_init(...)` (line 95), so it runs *after* the init that resets the cache to CANNON:
```c
    projectile_init(loader_get_slot(TILE_ASSET_BULLET));
    projectile_set_weapon1_damage(WEAPON1_DAMAGE_TABLE[loadout_get_weapon1()]);  /* LASER deals more per hit (#424) */
    turret_init(loader_get_slot(TILE_ASSET_TURRET));
```

- [ ] **Step 2: Run the host tests (no regression)**

Run:
```powershell
make test
```
Expected: PASS — all binaries green (this change adds no test; it must not break existing ones).

- [ ] **Step 3: Clean build the ROM**

Run (from the worktree dir):
```powershell
$env:GBDK_HOME = "C:/gbdk"
$env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
make clean ; make
```
Expected: `build/nuke-raider.gb` produced with no errors. The `bank-post-build` + `make memory-check` PostToolUse hooks fire automatically — confirm no bank/WRAM/VRAM/OAM budget is FAIL or ERROR.

- [ ] **Step 4: Commit**

```powershell
git add src/state_playing.c
git commit -m @'
feat(playing): seed projectile weapon damage from loadout at race start (#424)

Calls projectile_set_weapon1_damage(WEAPON1_DAMAGE_TABLE[weapon1]) after
projectile_init(), mirroring the damage_set_armor_tier pattern (#423).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
'@
```

---

### Task 5: Smoketest, docs, PR

Final integration gate per the project workflow. No code beyond the README doc update.

**Files:**
- Modify: `README.md` (if it documents weapon/loadout behavior)

- [ ] **Step 1: Fetch and merge latest master**

Run (from the worktree dir):
```powershell
git fetch origin ; git merge origin/master
```
Resolve any conflicts (most likely in `config.h` near the loadout/damage sections). Re-run `make test` after resolving.

- [ ] **Step 2: Clean build**

```powershell
$env:GBDK_HOME = "C:/gbdk"
$env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
make clean ; make
```
Expected: ROM built, `make memory-check` hook reports no FAIL/ERROR.

- [ ] **Step 3: Smoketest in the emulator** (ask the user to confirm before launching)

Ask the user to confirm, then launch from the worktree dir:
```powershell
Start-Process java -ArgumentList '-jar','C:\Tools\Emulicious\Emulicious.jar','build/nuke-raider.gb'
```
Verify AC3 with the user: buy LASER at TRADER (WEAPON1 unlock), start a race, and confirm a racer is destroyed in **3 bullet hits** instead of 5. Confirm a turret still dies in 1 hit (no 255-HP wrap). Ask the user to confirm it looks correct.

- [ ] **Step 4: Update README (only if user-visible weapon behavior is documented there)**

Grep `README.md` for existing weapon/loadout/LASER/CANNON copy. If a weapons section exists, add a line noting LASER deals 2 damage per hit vs CANNON's 1 (kills a racer in 3 shots vs 5). If no such section exists, skip this step.

- [ ] **Step 5: Push and open the PR**

```powershell
git push -u origin worktree-plan-laser-weapon-damage-424
gh pr create --title "feat: LASER primary weapon — more damage per hit (#424)" --body @'
Implements the LASER primary-weapon damage effect.

- CANNON = 1 dmg/hit, LASER = 2 dmg/hit (config-tunable). Racer/patrol (HP=5) die in 3 LASER hits vs 5 CANNON.
- `projectile_check_hit_enemy()` returns cached per-hit damage; seeded from loadout at race start (mirrors #423 armor pattern).
- New underflow-safe `enemy_apply_damage()` shared by racer/turret/patrol (turret HP=1 floors at 0, no 255 wrap).
- Enemy bullets and ram damage unchanged.

Closes #424

🤖 Generated with [Claude Code](https://claude.com/claude-code)
'@
```

- [ ] **Step 6: Verify the linked issue closed on merge**

After the PR merges, confirm #424 is closed. If not:
```powershell
gh issue close 424
```

---

## Acceptance Criteria Coverage

- **AC1** (unit: LASER decrements by LASER value, CANNON by 1) → Task 2 `test_check_hit_enemy_laser_damage` / `test_check_hit_enemy_default_cannon_damage`; Task 1 `test_apply_damage_basic` / `test_apply_damage_cannon_single`.
- **AC2** (unit: RACER_HP=5 dies in `ceil(5/laser)`=3 LASER hits vs 5 CANNON) → Task 3 `test_racer_laser_kills_in_three_hits`; CANNON parity via existing `test_racer_destroyed_when_hp_reaches_zero`.
- **AC3** (smoketest: buy LASER, destroy racer in fewer shots) → Task 4 wiring + Task 5 Step 3.
- **AC4** (`make test` green, clean build, `make memory-check` no FAIL) → every task's test step + Task 4 Step 3 + Task 5 Step 2.

## Out of Scope (unchanged)

- Fire-rate, speed, range, piercing; new bullet sprite; secondary weapon; enemy weapon variation.
- Ram-collision damage paths (`racer.c` / `patrol.c` `ENEMY_RAM_DAMAGE`) — left as-is; they use damage=1 and have documented guards. Converting them to `enemy_apply_damage` is a valid future cleanup but out of scope here (R6: damage-per-hit for player bullets only).
