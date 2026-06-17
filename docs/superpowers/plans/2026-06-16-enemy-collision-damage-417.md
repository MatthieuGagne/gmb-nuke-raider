# Enemy Vehicle Collision Damage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ramming an enemy racer or the patrol/roamer chips its HP (1 HP per ram event, debounced per-enemy), complementing the player-only contact damage from #412, so the player car becomes a viable-but-costly melee weapon.

**Architecture:** Extend the existing `racer_apply_contact_damage` helper (#412) and the patrol's inline ram block to also decrement *enemy* HP, gated by a new per-enemy ram cooldown (mirrors the player's 30-frame i-frame). A 0-HP result routes through the existing lethal paths — racers reuse the #411 car-explosion death (extracted into a shared `racer_kill` helper), the patrol is deactivated (extracted into a shared `patrol_destroy` helper). Patrol gains a `patrol_hit_flash` field so it blinks on both bullet and ram hits (closing a pre-existing gap). Turrets are untouched and a regression test confirms their exclusion.

**Tech Stack:** GBDK-2020 / SDCC (target), gcc + Unity (host unit tests), C with SoA entity pools.

## Global Constraints

- All enemy modules (`racer.c`, `patrol.c`, `turret.c`) are `#pragma bank 255`; public functions are declared `BANKED`. `damage_apply` is cross-bank and already callable from both — copy the existing call style, do not add new banking machinery.
- **No new files** → no `bank-manifest.json` change required.
- All new fields are `uint8_t` SoA arrays sized `MAX_RACERS` / `MAX_PATROLS`. Use `uint`-suffixed literals (`0u`, `1u`) and explicit `(uint8_t)` casts on arithmetic, matching surrounding code (SDCC promotes to int).
- **Test helpers MUST live inside the existing `#ifndef __SDCC` / `#endif` guards** in each `.c` file so they are excluded from the ROM (keeps `make memory-check` budgets unaffected — AC9).
- Host tests auto-discover via `$(wildcard tests/test_*.c)`; new `test_*` functions must be registered in their file's `main()` `RUN_TEST(...)` list or they will not run.
- Constant values copied verbatim from the spec: `ENEMY_RAM_DAMAGE = 1`, `ENEMY_RAM_COOLDOWN = DAMAGE_INVINCIBILITY_FRAMES` (= 30), enemy max HP = `RACER_HP` = 5 (so 5 rams destroy), player side keeps `RACER_RAM_DAMAGE` (= 5) and its own existing 30-frame i-frame **unchanged**.
- `PATROL_HIT_FLASH_FRAMES = RACER_HIT_FLASH_FRAMES` (= 8).
- TDD: every behavioral task writes the failing test first, runs it RED, implements minimal code, runs it GREEN, commits. Run host tests with `make test` (see CLAUDE.md: it early-exits at the first failing binary in alphabetical order — fix earliest first).

---

### Task 1: Extract `racer_kill` helper (refactor, no behavior change)

Pulls the inline #411 lethal-hit block out of `racer_update` into a static helper so the ram path (Task 2) can reuse the exact same death sequence. Pure refactor — existing tests must stay green.

**Files:**
- Modify: `src/racer.c` (add static `racer_kill`; replace the inline death block in `racer_update`)
- Test: `tests/test_racer.c` (no new test — existing `test_racer_dying_deals_no_contact_damage` and any bullet-death test are the regression guard)

**Interfaces:**
- Consumes: nothing new.
- Produces: `static void racer_kill(uint8_t i);` — zeroes velocity, sets `racer_active[i]=0`, `racer_dying[i]=1`, `racer_death_timer[i]=RACER_DEATH_TICKS`, and spawns the 4-slot car explosion. Caller must have already set `racer_hp[i]=0`.

- [ ] **Step 1: Run the existing suite to confirm green baseline**

Run: `make test`
Expected: PASS (all binaries). This is the refactor's regression net.

- [ ] **Step 2: Add the static `racer_kill` helper**

In `src/racer.c`, immediately **before** `racer_update` (around line 258, after `racer_init_empty`), add:

```c
/* Lethal-hit path (#411): freeze the racer mid-explosion and play the car
 * blast on its own 4 OAM slots. Caller has already zeroed racer_hp[i]. Quadrant
 * flip + slot order mirror player_kill() and racer_render():
 * slot0=TL, slot1=BL, slot2=TR, slot3=BR. Shared by the bullet-hit branch
 * (racer_update) and the ram branch (racer_apply_contact_damage, #417). */
static void racer_kill(uint8_t i) {
    uint8_t base = explosion_car_base();
    racer_active[i]       = 0u;
    racer_dying[i]        = 1u;
    racer_death_timer[i]  = (uint8_t)RACER_DEATH_TICKS;
    racer_vx[i]           = (int8_t)0;
    racer_vy[i]           = (int8_t)0;
    explosion_spawn(racer_oam[i * 4u + 0u], base, 0u,                          EXPLOSION_KIND_RACER, 0u, 0u);
    explosion_spawn(racer_oam[i * 4u + 1u], base, S_FLIPY,                      EXPLOSION_KIND_RACER, 0u, 0u);
    explosion_spawn(racer_oam[i * 4u + 2u], base, S_FLIPX,                      EXPLOSION_KIND_RACER, 0u, 0u);
    explosion_spawn(racer_oam[i * 4u + 3u], base, (uint8_t)(S_FLIPX | S_FLIPY), EXPLOSION_KIND_RACER, 0u, 0u);
}
```

- [ ] **Step 3: Replace the inline death block in `racer_update`**

In `src/racer.c`, inside `racer_update`'s bullet-hit block, replace the entire `if (racer_hp[i] == 0u) { ... }` body (the lines that compute `base`, set `racer_active/dying/death_timer/vx/vy`, and the four `explosion_spawn` calls) with a single call:

```c
                    racer_hp[i] = (uint8_t)(racer_hp[i] - 1u);
                    racer_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
                    if (racer_hp[i] == 0u) {
                        racer_kill(i);
                    }
```

- [ ] **Step 4: Run tests to verify no behavior change**

Run: `make test`
Expected: PASS — identical to Step 1. The dying-racer and bullet-death tests confirm the extraction is behavior-preserving.

- [ ] **Step 5: Commit**

```bash
git add src/racer.c
git commit -m "refactor(racer): extract racer_kill helper for shared lethal path (#417)"
```

---

### Task 2: Racer enemy-side ram damage + per-racer cooldown + hit flash

Adds the shared damage constants, the per-racer ram cooldown SoA field, and rewrites `racer_apply_contact_damage` to decrement the overlapping racer's HP (debounced), flash it, and route a 0-HP result through `racer_kill`. Mutual player damage is preserved.

**Files:**
- Modify: `src/config.h` (add `ENEMY_RAM_DAMAGE`, `ENEMY_RAM_COOLDOWN`)
- Modify: `src/racer.c` (add `racer_ram_cooldown` SoA + init in both init fns + per-frame tick; rewrite `racer_apply_contact_damage`; add 2 test helpers)
- Modify: `src/racer.h` (declare 2 test helpers)
- Test: `tests/test_racer.c`

**Interfaces:**
- Consumes: `racer_kill(i)` (Task 1); `racer_active[]`, `racer_px[]`, `racer_py[]`, `racer_hp[]`, `racer_hit_flash[]` (existing SoA); `damage_apply(uint8_t)` (cross-bank, existing).
- Produces:
  - `#define ENEMY_RAM_DAMAGE 1u`, `#define ENEMY_RAM_COOLDOWN DAMAGE_INVINCIBILITY_FRAMES`
  - `static uint8_t racer_ram_cooldown[MAX_RACERS];`
  - `uint8_t racer_apply_contact_damage(int16_t px, int16_t py) BANKED;` — now also applies `ENEMY_RAM_DAMAGE` to each overlapping active racer behind its per-racer cooldown; still returns 1 if any overlap (caller plays SFX).
  - `uint8_t racer_get_ram_cooldown_for_test(uint8_t slot);`
  - `void    racer_set_ram_cooldown_for_test(uint8_t slot, uint8_t v);`

- [ ] **Step 1: Add the config constants**

In `src/config.h`, in the "Damage system" block (after `#define ENEMY_BULLET_DAMAGE 10u`, ~line 34), add:

```c
#define ENEMY_RAM_DAMAGE           1u   /* HP an enemy vehicle loses per ram event (#417) */
#define ENEMY_RAM_COOLDOWN         DAMAGE_INVINCIBILITY_FRAMES /* per-enemy ram debounce window (= player i-frame) (#417) */
```

- [ ] **Step 2: Add the SoA field and its init**

In `src/racer.c`, in the SoA block (after `static uint8_t racer_hit_flash[MAX_RACERS];`, ~line 33), add:

```c
static uint8_t  racer_ram_cooldown[MAX_RACERS]; /* per-racer ram-damage debounce (#417) */
```

In `racer_init`, in the per-slot init loop (after `racer_hit_flash[i] = 0u;`), add:

```c
        racer_ram_cooldown[i] = 0u;
```

In `racer_init_empty`, in its per-slot init loop (after `racer_hit_flash[i] = 0u;`), add the same line:

```c
        racer_ram_cooldown[i] = 0u;
```

- [ ] **Step 3: Add the per-frame cooldown tick**

In `src/racer.c`, in `racer_update`, immediately after the existing flash-timer tick block:

```c
        /* ---- Flash timer tick ---- */
        if (racer_hit_flash[i] > 0u) {
            racer_hit_flash[i] = (uint8_t)(racer_hit_flash[i] - 1u);
        }
```

add:

```c
        /* ---- Ram cooldown tick (#417) ---- */
        if (racer_ram_cooldown[i] > 0u) {
            racer_ram_cooldown[i] = (uint8_t)(racer_ram_cooldown[i] - 1u);
        }
```

- [ ] **Step 4: Write the failing tests**

In `tests/test_racer.c`, add these four tests (place them near the existing `test_racer_contact_damage_drains_player_hp`):

```c
void test_racer_ram_decrements_enemy_hp(void) {
    /* A ram chips ENEMY_RAM_DAMAGE off the racer's HP and arms its cooldown. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    damage_init();
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)RACER_HP, racer_get_hp_for_test(1u));
    TEST_ASSERT_EQUAL_UINT8(1u, racer_apply_contact_damage(40, 40));
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(RACER_HP - ENEMY_RAM_DAMAGE), racer_get_hp_for_test(1u));
    TEST_ASSERT_EQUAL_UINT8((uint8_t)ENEMY_RAM_COOLDOWN, racer_get_ram_cooldown_for_test(1u));
    TEST_ASSERT_GREATER_THAN_UINT8(0u, racer_get_hit_flash_for_test(1u));
}

void test_racer_ram_debounced_by_cooldown(void) {
    /* Sustained overlap deals at most one enemy hit per cooldown window. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    damage_init();
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_apply_contact_damage(40, 40);                       /* hp 5 -> 4, cooldown armed */
    racer_apply_contact_damage(40, 40);                       /* still in cooldown -> no drain */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(RACER_HP - ENEMY_RAM_DAMAGE), racer_get_hp_for_test(1u));
    racer_set_ram_cooldown_for_test(1u, 0u);                  /* window elapsed */
    racer_apply_contact_damage(40, 40);                       /* hp 4 -> 3 */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(RACER_HP - 2u * ENEMY_RAM_DAMAGE), racer_get_hp_for_test(1u));
}

void test_racer_ram_cooldown_decrements_in_update(void) {
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    damage_init();
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_apply_contact_damage(40, 40);                       /* cooldown = ENEMY_RAM_COOLDOWN */
    racer_update();                                           /* one frame */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(ENEMY_RAM_COOLDOWN - 1u), racer_get_ram_cooldown_for_test(1u));
}

void test_racer_ram_to_zero_hp_kills(void) {
    /* A ram that brings HP to 0 routes through the #411 death path. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    damage_init();
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(1u, (uint8_t)ENEMY_RAM_DAMAGE);     /* one ram from death */
    racer_apply_contact_damage(40, 40);
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_hp_for_test(1u));
    TEST_ASSERT_EQUAL_UINT8(1u, racer_is_dying_for_test(1u));
}

void test_racer_ram_still_damages_player_mutually(void) {
    /* AC4: the player still takes RACER_RAM_DAMAGE on the same contact. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    damage_init();
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_apply_contact_damage(40, 40);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PLAYER_MAX_HP - RACER_RAM_DAMAGE), damage_get_hp());
}

void test_racer_dying_takes_no_ram_damage(void) {
    /* R5: a dying racer (active=0) neither takes nor deals further ram damage. */
    uint8_t wp_tx[1] = { 4u };
    uint8_t wp_ty[1] = { 0u };
    damage_init();
    racer_spawn_for_test(32, 32, wp_tx, wp_ty, 1u, CHECKPOINT_DIR_N, 1u);
    racer_set_hp_for_test(1u, 1u);
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    racer_update();                                           /* lethal bullet -> dying, active=0 */
    TEST_ASSERT_EQUAL_UINT8(1u, racer_is_dying_for_test(1u));
    TEST_ASSERT_EQUAL_UINT8(0u, racer_apply_contact_damage(40, 40)); /* no hit reported */
    TEST_ASSERT_EQUAL_UINT8(0u, racer_get_hp_for_test(1u));          /* hp stays 0, no underflow */
}
```

Register all six in `main()` (alongside the other `RUN_TEST` lines):

```c
    RUN_TEST(test_racer_ram_decrements_enemy_hp);
    RUN_TEST(test_racer_ram_debounced_by_cooldown);
    RUN_TEST(test_racer_ram_cooldown_decrements_in_update);
    RUN_TEST(test_racer_ram_to_zero_hp_kills);
    RUN_TEST(test_racer_ram_still_damages_player_mutually);
    RUN_TEST(test_racer_dying_takes_no_ram_damage);
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `racer_get_ram_cooldown_for_test` / `racer_set_ram_cooldown_for_test` undefined (link error), and the HP/cooldown assertions fail because `racer_apply_contact_damage` does not yet decrement enemy HP.

- [ ] **Step 6: Add the test helpers**

In `src/racer.h`, near the other `*_for_test` declarations (~line 47), add:

```c
uint8_t racer_get_ram_cooldown_for_test(uint8_t slot);
void    racer_set_ram_cooldown_for_test(uint8_t slot, uint8_t v);
```

In `src/racer.c`, inside the existing `#ifndef __SDCC` block (near `racer_get_hit_flash_for_test`), add:

```c
uint8_t racer_get_ram_cooldown_for_test(uint8_t slot)        { return racer_ram_cooldown[slot]; }
void    racer_set_ram_cooldown_for_test(uint8_t slot, uint8_t v) { racer_ram_cooldown[slot] = v; }
```

- [ ] **Step 7: Rewrite `racer_apply_contact_damage`**

In `src/racer.c`, replace the entire existing `racer_apply_contact_damage` function body (~lines 585-594) with:

```c
/* Mutual contact damage (#412 player side + #417 enemy side). Loops the pool
 * directly so it knows WHICH racer was rammed. Player side is i-frame-debounced
 * inside damage_apply; enemy side uses a per-racer ram cooldown so sustained
 * overlap deals at most one enemy hit per ENEMY_RAM_COOLDOWN window. Dying
 * racers are active=0 and thus skipped (#411). Returns 1 on any overlap so
 * state_playing plays SFX_HIT. */
uint8_t racer_apply_contact_damage(int16_t px, int16_t py) BANKED {
    uint8_t i;
    uint8_t hit = 0u;
    for (i = 0u; i < MAX_RACERS; i++) {
        if (!racer_active[i]) continue;
        if (px < racer_px[i] + 16 && px + 16 > racer_px[i] &&
            py < racer_py[i] + 16 && py + 16 > racer_py[i]) {
            damage_apply(RACER_RAM_DAMAGE);   /* player side (#412); i-frame debounced */
            if (racer_ram_cooldown[i] == 0u) {
                racer_ram_cooldown[i] = (uint8_t)ENEMY_RAM_COOLDOWN;
                racer_hit_flash[i]    = (uint8_t)RACER_HIT_FLASH_FRAMES;
                if (racer_hp[i] <= (uint8_t)ENEMY_RAM_DAMAGE) {
                    racer_hp[i] = 0u;
                    racer_kill(i);
                } else {
                    racer_hp[i] = (uint8_t)(racer_hp[i] - ENEMY_RAM_DAMAGE);
                }
            }
            hit = 1u;
        }
    }
    return hit;
}
```

(Leave `racer_overlaps_player` in place — it remains a public predicate and may have its own tests.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `make test`
Expected: PASS — all six new racer tests green, plus the pre-existing `test_racer_contact_damage_drains_player_hp` and `test_racer_dying_deals_no_contact_damage` still green.

- [ ] **Step 9: Commit**

```bash
git add src/config.h src/racer.c src/racer.h tests/test_racer.c
git commit -m "feat(racer): enemy takes debounced ram damage, routes 0 HP to death (#417)"
```

---

### Task 3: Extract `patrol_destroy` helper (refactor, no behavior change)

Pulls the patrol's inline `active=0` + OAM-clear death block out of the bullet branch into a static helper so the ram path (Task 5) reuses it. Pure refactor.

**Files:**
- Modify: `src/patrol.c` (add static `patrol_destroy`; replace inline death block in the bullet branch)
- Test: `tests/test_patrol.c` (existing `test_fatal_hit_destroys_and_deactivates` is the regression guard)

**Interfaces:**
- Consumes: `patrol_active[]`, `patrol_oam[]` (existing SoA).
- Produces: `static void patrol_destroy(uint8_t i);` — sets `patrol_active[i]=0` and clears its 4 OAM slots. Caller continues the loop after calling it.

- [ ] **Step 1: Confirm green baseline**

Run: `make test`
Expected: PASS.

- [ ] **Step 2: Add the static `patrol_destroy` helper**

In `src/patrol.c`, immediately **before** `patrol_update` (after `patrol_init_empty`, ~line 134), add:

```c
/* Destroy a patrol: deactivate and park its 4 OAM slots off-screen. Shared by
 * the bullet-hit and ram-hit (#417) lethal paths. Caller should `continue`. */
static void patrol_destroy(uint8_t i) {
    patrol_active[i] = 0u;
    move_sprite(patrol_oam[i * 4u + 0u], 0u, 0u);
    move_sprite(patrol_oam[i * 4u + 1u], 0u, 0u);
    move_sprite(patrol_oam[i * 4u + 2u], 0u, 0u);
    move_sprite(patrol_oam[i * 4u + 3u], 0u, 0u);
}
```

- [ ] **Step 3: Replace the inline death block in the bullet branch**

In `src/patrol.c`, inside `patrol_update`'s bullet-hit block, replace the existing:

```c
                        patrol_hp[i]--;
                        if (patrol_hp[i] == 0u) {
                            patrol_active[i] = 0u;
                            move_sprite(patrol_oam[i * 4u + 0u], 0u, 0u);
                            move_sprite(patrol_oam[i * 4u + 1u], 0u, 0u);
                            move_sprite(patrol_oam[i * 4u + 2u], 0u, 0u);
                            move_sprite(patrol_oam[i * 4u + 3u], 0u, 0u);
                            continue;
                        }
```

with:

```c
                        patrol_hp[i]--;
                        if (patrol_hp[i] == 0u) {
                            patrol_destroy(i);
                            continue;
                        }
```

- [ ] **Step 4: Run tests to verify no behavior change**

Run: `make test`
Expected: PASS — identical to Step 1 (`test_fatal_hit_destroys_and_deactivates`, `test_bullet_hit_decrements_hp` still green).

- [ ] **Step 5: Commit**

```bash
git add src/patrol.c
git commit -m "refactor(patrol): extract patrol_destroy helper for shared death path (#417)"
```

---

### Task 4: Patrol hit-flash field + blink on bullet hit + render blink

Adds `patrol_hit_flash` (the patrol has none today, so it never blinked on bullet hits either — this closes that gap), drives it from the existing bullet hit, ticks it per frame, and renders the blink. This is the R6 patrol-feedback decision (chosen: add the field). Ram-driven flash comes in Task 5.

**Files:**
- Modify: `src/config.h` (add `PATROL_HIT_FLASH_FRAMES`)
- Modify: `src/patrol.c` (add `patrol_hit_flash` SoA + init in both init fns + per-frame tick; set on bullet hit; render blink; add test helper)
- Modify: `src/patrol.h` (declare test helper)
- Test: `tests/test_patrol.c`

**Interfaces:**
- Consumes: `patrol_active[]`, `patrol_hp[]`, `patrol_oam[]` (existing).
- Produces:
  - `#define PATROL_HIT_FLASH_FRAMES RACER_HIT_FLASH_FRAMES`
  - `static uint8_t patrol_hit_flash[MAX_PATROLS];`
  - `uint8_t patrol_get_hit_flash_for_test(uint8_t i);`

- [ ] **Step 1: Add the config constant**

In `src/config.h`, in the patrol block (after `#define PATROL_FIRE_INTERVAL 45u`, ~line 109), add:

```c
#define PATROL_HIT_FLASH_FRAMES  RACER_HIT_FLASH_FRAMES /* frames of hit-blink per hit (#417) */
```

- [ ] **Step 2: Add the SoA field and its init**

In `src/patrol.c`, in the SoA block (after `static uint8_t patrol_hp[MAX_PATROLS];`, ~line 24), add:

```c
static uint8_t patrol_hit_flash[MAX_PATROLS];   /* hit-blink countdown (#417) */
```

In `patrol_init`, in the per-slot init loop (after `patrol_wp_count[i] = 0u;`), add:

```c
        patrol_hit_flash[i] = 0u;
```

In `patrol_init_empty`, in its per-slot init loop (after `patrol_wp_count[i] = 0u;`), add the same line:

```c
        patrol_hit_flash[i] = 0u;
```

- [ ] **Step 3: Add the per-frame flash tick**

In `src/patrol.c`, in `patrol_update`, immediately after `if (!patrol_active[i]) continue;` (~line 164), add:

```c
        /* Hit-flash timer tick (#417) */
        if (patrol_hit_flash[i] > 0u) {
            patrol_hit_flash[i] = (uint8_t)(patrol_hit_flash[i] - 1u);
        }
```

- [ ] **Step 4: Set the flash on a non-lethal bullet hit**

In `src/patrol.c`, in the bullet-hit block (now using `patrol_destroy` from Task 3), update it so a surviving patrol blinks:

```c
                        patrol_hp[i]--;
                        if (patrol_hp[i] == 0u) {
                            patrol_destroy(i);
                            continue;
                        }
                        patrol_hit_flash[i] = (uint8_t)PATROL_HIT_FLASH_FRAMES; /* non-lethal blink (#417) */
```

- [ ] **Step 5: Render the blink**

In `src/patrol.c`, in `patrol_render`, after `d = patrol_dir[i];` and **before** the first `set_sprite_tile(...)` call, add (mirrors `racer_render`):

```c
        /* Hit flash — hide sprite on odd 2-frame intervals (#417, mirrors racer) */
        if (patrol_hit_flash[i] & 2u) {
            move_sprite(patrol_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }
```

- [ ] **Step 6: Write the failing test**

In `tests/test_patrol.c`, add (near `test_bullet_hit_decrements_hp`):

```c
void test_bullet_hit_sets_hit_flash(void) {
    /* A non-lethal bullet hit makes the patrol blink (#417 closes the prior gap). */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_mode_for_test(0u, PATROL_MODE_PATROL);
    patrol_set_hp_for_test(0u, 3u);                 /* survives the hit */
    projectile_fire(48u, 56u, DIR_T, PROJ_OWNER_PLAYER);
    patrol_update(0, 0);
    TEST_ASSERT_EQUAL_UINT8(1u, patrol_is_active(0u));
    TEST_ASSERT_GREATER_THAN_UINT8(0u, patrol_get_hit_flash_for_test(0u));
}
```

Register it in `main()`:

```c
    RUN_TEST(test_bullet_hit_sets_hit_flash);
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `patrol_get_hit_flash_for_test` undefined (link error).

- [ ] **Step 8: Add the test helper**

In `src/patrol.h`, near the other `patrol_get_*` declarations (~line 41), add:

```c
uint8_t patrol_get_hit_flash_for_test(uint8_t i);
```

In `src/patrol.c`, inside the existing `#ifndef __SDCC` block (near `patrol_get_hp`), add:

```c
uint8_t patrol_get_hit_flash_for_test(uint8_t i) { return patrol_hit_flash[i]; }
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `make test`
Expected: PASS — `test_bullet_hit_sets_hit_flash` green; `test_fatal_hit_destroys_and_deactivates` and `test_bullet_hit_decrements_hp` still green.

- [ ] **Step 10: Commit**

```bash
git add src/config.h src/patrol.c src/patrol.h tests/test_patrol.c
git commit -m "feat(patrol): add hit-flash field, blink on bullet hit (#417)"
```

---

### Task 5: Patrol enemy-side ram damage + per-patrol cooldown

Adds the per-patrol ram cooldown and rewrites the patrol's inline ram block to decrement patrol HP (debounced), flash it, and route a 0-HP result through `patrol_destroy`. Mutual player damage is preserved.

**Files:**
- Modify: `src/patrol.c` (add `patrol_ram_cooldown` SoA + init in both init fns + per-frame tick; modify ram block; add 2 test helpers)
- Modify: `src/patrol.h` (declare 2 test helpers)
- Test: `tests/test_patrol.c`

**Interfaces:**
- Consumes: `patrol_destroy(i)` (Task 3); `PATROL_HIT_FLASH_FRAMES`, `patrol_hit_flash[]` (Task 4); `ENEMY_RAM_DAMAGE`, `ENEMY_RAM_COOLDOWN` (Task 2); `RACER_RAM_DAMAGE`, `damage_apply` (existing).
- Produces:
  - `static uint8_t patrol_ram_cooldown[MAX_PATROLS];`
  - `uint8_t patrol_get_ram_cooldown_for_test(uint8_t i);`
  - `void    patrol_set_ram_cooldown_for_test(uint8_t i, uint8_t v);`

- [ ] **Step 1: Add the SoA field and its init**

In `src/patrol.c`, in the SoA block (after `patrol_hit_flash[MAX_PATROLS];` from Task 4), add:

```c
static uint8_t patrol_ram_cooldown[MAX_PATROLS]; /* per-patrol ram-damage debounce (#417) */
```

In `patrol_init` and `patrol_init_empty`, in each per-slot init loop (after `patrol_hit_flash[i] = 0u;`), add:

```c
        patrol_ram_cooldown[i] = 0u;
```

- [ ] **Step 2: Add the per-frame cooldown tick**

In `src/patrol.c`, in `patrol_update`, immediately after the flash tick added in Task 4, add:

```c
        /* Ram cooldown tick (#417) */
        if (patrol_ram_cooldown[i] > 0u) {
            patrol_ram_cooldown[i] = (uint8_t)(patrol_ram_cooldown[i] - 1u);
        }
```

- [ ] **Step 3: Write the failing tests**

In `tests/test_patrol.c`, add (near `test_ram_contact_damages_player`):

```c
void test_ram_decrements_patrol_hp(void) {
    /* AC2: ramming the patrol chips ENEMY_RAM_DAMAGE off its HP and arms cooldown. */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, (uint8_t)PATROL_HP);
    patrol_update(40, 32);                                    /* 16x16 boxes overlap -> ram */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PATROL_HP - ENEMY_RAM_DAMAGE), patrol_get_hp(0u));
    TEST_ASSERT_EQUAL_UINT8((uint8_t)ENEMY_RAM_COOLDOWN, patrol_get_ram_cooldown_for_test(0u));
    TEST_ASSERT_GREATER_THAN_UINT8(0u, patrol_get_hit_flash_for_test(0u));
}

void test_ram_debounced_by_cooldown(void) {
    /* AC3: sustained overlap deals at most one enemy hit per cooldown window. */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, (uint8_t)PATROL_HP);
    patrol_update(40, 32);                                    /* hp -1, cooldown armed */
    patrol_update(40, 32);                                    /* cooldown ticked but still > 0 -> no drain */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PATROL_HP - ENEMY_RAM_DAMAGE), patrol_get_hp(0u));
    patrol_set_ram_cooldown_for_test(0u, 0u);                 /* window elapsed */
    patrol_update(40, 32);                                    /* hp -1 again */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PATROL_HP - 2u * ENEMY_RAM_DAMAGE), patrol_get_hp(0u));
}

void test_ram_to_zero_hp_destroys_patrol(void) {
    /* AC5: a ram that brings HP to 0 deactivates the patrol via the death path. */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, (uint8_t)ENEMY_RAM_DAMAGE);    /* one ram from death */
    patrol_update(40, 32);
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_is_active(0u));
    TEST_ASSERT_EQUAL_UINT8(0u, patrol_count_active());
}

void test_ram_still_damages_player_mutually(void) {
    /* AC4: player still takes RACER_RAM_DAMAGE on the same contact. */
    static uint8_t wtx[1] = {11u};
    static uint8_t wty[1] = {4u};
    damage_init();
    patrol_spawn_for_test(32, 32, wtx, wty, 1u);
    patrol_set_hp_for_test(0u, (uint8_t)PATROL_HP);
    patrol_update(40, 32);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PLAYER_MAX_HP - RACER_RAM_DAMAGE), damage_get_hp());
}
```

Register all four in `main()`:

```c
    RUN_TEST(test_ram_decrements_patrol_hp);
    RUN_TEST(test_ram_debounced_by_cooldown);
    RUN_TEST(test_ram_to_zero_hp_destroys_patrol);
    RUN_TEST(test_ram_still_damages_player_mutually);
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `make test`
Expected: FAIL — `patrol_get_ram_cooldown_for_test` / `patrol_set_ram_cooldown_for_test` undefined, and HP assertions fail (ram block does not yet decrement patrol HP).

- [ ] **Step 5: Add the test helpers**

In `src/patrol.h`, near the other `patrol_*_for_test` declarations (~line 45), add:

```c
uint8_t patrol_get_ram_cooldown_for_test(uint8_t i);
void    patrol_set_ram_cooldown_for_test(uint8_t i, uint8_t v);
```

In `src/patrol.c`, inside the existing `#ifndef __SDCC` block (near `patrol_set_hp_for_test`), add:

```c
uint8_t patrol_get_ram_cooldown_for_test(uint8_t i)        { return patrol_ram_cooldown[i]; }
void    patrol_set_ram_cooldown_for_test(uint8_t i, uint8_t v) { patrol_ram_cooldown[i] = v; }
```

- [ ] **Step 6: Rewrite the patrol ram block**

In `src/patrol.c`, in `patrol_update`, replace the existing ram block:

```c
        /* --- Ram contact: car-vs-car 16x16 overlap deals contact damage.
         * damage.c i-frames (DAMAGE_INVINCIBILITY_FRAMES) rate-limit it. --- */
        {
            int16_t rdx = px - patrol_px[i];
            int16_t rdy = py - patrol_py[i];
            if (rdx > -16 && rdx < 16 && rdy > -16 && rdy < 16) {
                damage_apply(RACER_RAM_DAMAGE);
            }
        }
```

with:

```c
        /* --- Ram contact: car-vs-car 16x16 overlap. Player side is i-frame
         * debounced in damage.c (#412); enemy side uses a per-patrol ram
         * cooldown and routes 0 HP through the shared death path (#417). --- */
        {
            int16_t rdx = px - patrol_px[i];
            int16_t rdy = py - patrol_py[i];
            if (rdx > -16 && rdx < 16 && rdy > -16 && rdy < 16) {
                damage_apply(RACER_RAM_DAMAGE);          /* player side (#412) */
                if (patrol_ram_cooldown[i] == 0u) {      /* enemy side (#417) */
                    patrol_ram_cooldown[i] = (uint8_t)ENEMY_RAM_COOLDOWN;
                    patrol_hit_flash[i]    = (uint8_t)PATROL_HIT_FLASH_FRAMES;
                    if (patrol_hp[i] <= (uint8_t)ENEMY_RAM_DAMAGE) {
                        patrol_hp[i] = 0u;
                        patrol_destroy(i);
                        continue;                        /* destroyed — skip rest of this patrol */
                    } else {
                        patrol_hp[i] = (uint8_t)(patrol_hp[i] - ENEMY_RAM_DAMAGE);
                    }
                }
            }
        }
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `make test`
Expected: PASS — all four new patrol tests green; `test_ram_contact_damages_player` and `test_destroyed_patrol_deals_no_contact_damage` still green (the destroyed-patrol no-op is already covered by the `if (!patrol_active[i]) continue;` guard, satisfying R5/AC6 for patrol).

- [ ] **Step 8: Commit**

```bash
git add src/patrol.c src/patrol.h tests/test_patrol.c
git commit -m "feat(patrol): enemy takes debounced ram damage, routes 0 HP to destroy (#417)"
```

---

### Task 6: Turret exclusion regression test (AC8)

No production change — turrets have no contact-damage path and must keep it that way. Add a host test that overlaps the player with a turret and confirms the turret is unharmed.

**Files:**
- Test: `tests/test_turret.c`

**Interfaces:**
- Consumes: `turret_init_empty()`, `turret_spawn(tx, ty)`, `turret_update(px, py)`, `turret_count_active()` (existing); `cam_x`/`cam_y` via `camera.h` (already included in this test file).

- [ ] **Step 1: Write the test**

In `tests/test_turret.c`, add:

```c
void test_turret_takes_no_contact_damage(void) {
    /* AC8: a turret overlapping the player takes no collision damage. With cam=0
     * the turret at tile (10,10) is on-screen (oam_x=88, vis_y=96); a player
     * overlapping its 16x16 box must not destroy it (turrets are excluded). */
    cam_x = 0;
    cam_y = 0;
    turret_spawn(10u, 10u);                      /* world pixel ~ (80,80) */
    TEST_ASSERT_EQUAL_UINT8(1u, turret_count_active());
    turret_update(80, 80);                        /* player overlapping the turret */
    TEST_ASSERT_EQUAL_UINT8(1u, turret_count_active()); /* still alive — no ram damage */
}
```

Register it in `main()`:

```c
    RUN_TEST(test_turret_takes_no_contact_damage);
```

- [ ] **Step 2: Run tests to verify it passes**

Run: `make test`
Expected: PASS — the turret survives the overlapping update (there is no turret contact-damage code; this test guards against a future regression).

- [ ] **Step 3: Commit**

```bash
git add tests/test_turret.c
git commit -m "test(turret): confirm turrets take no collision damage (#417)"
```

---

### Task 7: Integration — clean build, memory check, full suite (AC9)

Verifies the ROM builds, host tests all pass, and memory budgets are unaffected. This is the gate before the smoketest in the project workflow.

**Files:** none (verification only).

- [ ] **Step 1: Run the full host test suite**

Run: `make test`
Expected: PASS — every `test_*` binary green (racer, patrol, turret, and all others).

- [ ] **Step 2: Clean ROM build (PowerShell, from the worktree dir)**

```powershell
$env:GBDK_HOME = "C:/gbdk"
$env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
make clean ; make
```

Expected: `build/nuke-raider.gb` produced, no compiler/linker errors. (The `bank-post-build` + `make memory-check` PostToolUse hooks fire automatically.)

- [ ] **Step 3: Confirm memory budgets (AC9)**

Run: `make memory-check`
Expected: WRAM / VRAM / OAM all PASS or WARN (no FAIL/ERROR). The new fields cost +1 byte/racer (`racer_ram_cooldown`), +2 bytes/patrol (`patrol_hit_flash` + `patrol_ram_cooldown`); test helpers are excluded from ROM via `#ifndef __SDCC`.

- [ ] **Step 4: Smoketest gate (per CLAUDE.md "Smoketest gate")**

Follow the project smoketest sequence before any push/PR: fetch + merge `origin/master`, clean build (already done), then ask the user to confirm launching the ROM in Emulicious and manually verify: ramming an enemy racer ~5 times destroys it with the #411 explosion; ramming the patrol ~5 times destroys it; both blink on non-lethal hits; the player still loses HP on contact. Only after the user confirms: update `README.md` if user-visible behavior changed, then push and open the PR with `Closes #417`.

---

## Self-Review

**1. Spec coverage:**
- R1 / AC1 / AC2 — enemy damage on overlap: Tasks 2 (racer) & 5 (patrol). ✓
- R2 — `ENEMY_RAM_DAMAGE = 1`, 5 rams kill (HP = `RACER_HP` = 5): Task 2 Step 1, tests in Tasks 2 & 5. ✓
- R3 / AC3 — per-enemy 30-frame cooldown debounce: `racer_ram_cooldown` (Task 2), `patrol_ram_cooldown` (Task 5); player i-frame untouched (`damage_apply` unchanged). ✓
- R4 / AC5 — 0 HP routes through existing death (#411 racer / destroy patrol) via `racer_kill` (Task 1) and `patrol_destroy` (Task 3). ✓
- R5 / AC6(no-op) — dying racer / destroyed patrol take/deal nothing: covered by `active=0` guards; explicit tests in Tasks 2 & 5. ✓
- R6 / AC7 — non-lethal ram blink: `racer_hit_flash` reuse (Task 2), `patrol_hit_flash` added + driven by bullet (Task 4) and ram (Task 5). ✓
- R7 / AC8 — turrets excluded: no production change + regression test (Task 6). ✓
- AC4 — mutual player damage preserved: explicit tests in Tasks 2 & 5; `damage_apply(RACER_RAM_DAMAGE)` retained. ✓
- AC9 — memory budgets: Task 7 Step 3; helpers guarded out of ROM. ✓
- AC10 — host tests for HP decrement, debounce, ram-to-kill, mutual damage, dying/destroyed no-op, turret exclusion: Tasks 2, 5, 6. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to" — every code step shows complete code and every command shows expected output. ✓

**3. Type consistency:** `racer_kill(uint8_t)` and `patrol_destroy(uint8_t)` defined in Tasks 1/3, consumed in Tasks 2/5. `ENEMY_RAM_DAMAGE`/`ENEMY_RAM_COOLDOWN` defined Task 2, consumed Task 5. `PATROL_HIT_FLASH_FRAMES`/`patrol_hit_flash` defined Task 4, consumed Task 5. Test helper names (`racer_get/set_ram_cooldown_for_test`, `patrol_get_hit_flash_for_test`, `patrol_get/set_ram_cooldown_for_test`) match between `.h` declarations, `.c` definitions, and test call sites. ✓
