# Patrol Feature — PR3: Lazy Racer OAM + MAX_SPRITES Bump Implementation Plan

**REQUIRED SUB-SKILL:** Use the `superpowers:executing-plans` skill to execute this plan (the project-shadowed version with worktree + bank gates).

**Goal:** Free enough OAM on Track 1 so the upcoming patrol enemy's 4 sprites fit. Two changes: (1) raise `MAX_SPRITES` 28 → 32 (hardware OAM cap is 40, so 32 is safe), updating the OAM budget comment to account for the patrol's 4 sprites; (2) make racer OAM allocation **lazy** — a racer slot only claims its 4 sprite handles when it becomes ACTIVE, instead of the current unconditional pre-allocation of 12 handles (4 × `MAX_RACERS`=3) on every track. On Track 1 (no racers) this reclaims all 12 previously-wasted slots; on Track 2 it allocates 8 (2 active enemies) instead of 12.

**Architecture:** `racer.c` owns a fixed-size SoA pool (`MAX_RACERS` slots, slot 0 = player placeholder, slots 1..2 = enemies). Today `racer_init` calls `get_sprite()` four times per slot **unconditionally** in the init loop (`racer.c` lines 187–190), reserving 12 OAM handles even when no racer is active. This plan moves those four `get_sprite()` calls into the per-slot "found && waypoints" active block, initialises `racer_oam[]` to `SPRITE_POOL_INVALID` for inactive slots, and adds `SPRITE_POOL_INVALID` guards in `racer_render` and `racer_hide` so they skip unallocated slots (critical: `racer_hide` currently `move_sprite`s **every** slot unconditionally, which with uninitialised/invalid handles would corrupt OAM slot 0 — the player — or pass `0xFF` to `move_sprite`). `sprite_pool` gains a test-only `sprite_pool_active_count()` accessor (under `#ifndef __SDCC`) so the new test can assert "0 racers → 0 sprites allocated by `racer_init`."

**Tech Stack:** GBDK-2020 / SDCC (C, banked ROM, MBC5). Host-side unit tests via gcc + Unity (`make test`). OAM budget validated by `tools/memory_check.py` (`make memory-check`, also fires via PostToolUse hook after `make`).

**Prerequisites:** This is **PR3 of 4** for the patrol feature (issue #144). It assumes **PR1 (`enemy_common.c` extraction)** and **PR2 (shared vehicle-physics convergence)** are merged. PR3 is, however, largely **independent** of PR1/PR2 — it touches only OAM allocation in `racer.c`, plus `config.h` and `sprite_pool.{c,h}`. It does NOT touch `patrol.c` (that is PR4). If PR1/PR2 are not yet merged, this plan still applies cleanly to the current `racer.c`; only merge order with master changes.

---

## File Structure

Files touched by this PR:

```
src/config.h            # MAX_SPRITES 28 -> 32; OAM budget comment updated for patrol's 4
src/sprite_pool.h       # NEW test-only accessor declaration (#ifndef __SDCC)
src/sprite_pool.c       # NEW test-only sprite_pool_active_count() (#ifndef __SDCC)
src/racer.c             # lazy OAM allocation; INVALID init; render/hide guards
tests/test_sprite_pool.c  # test for sprite_pool_active_count()
tests/test_racer.c      # lazy-OAM tests; render/hide-safe-with-INVALID tests
```

No new `.c`/`.h` modules → **no `bank-manifest.json` change** (all touched `.c` files already have manifest entries).

---

## Task 1 — Add `sprite_pool_active_count()` test seam (RED → GREEN)

This is the allocation-count seam the lazy-OAM racer test needs. `sprite_pool` does not currently expose how many slots are claimed; we add a host-test-only accessor that counts active slots. Wrapped in `#ifndef __SDCC` so it costs zero ROM/WRAM on hardware.

- [ ] **STEP 1.1 (RED):** Add a failing test to `tests/test_sprite_pool.c`. Insert before `int main(void)`:

```c
/* --- sprite_pool_active_count (host-test seam) ---------------------- */

/* Fresh pool reports zero active slots */
void test_active_count_zero_after_init(void) {
    TEST_ASSERT_EQUAL_UINT8(0u, sprite_pool_active_count());
}

/* Each get_sprite() increments the active count */
void test_active_count_tracks_allocations(void) {
    get_sprite();
    get_sprite();
    TEST_ASSERT_EQUAL_UINT8(2u, sprite_pool_active_count());
}

/* clear_sprite() decrements the active count */
void test_active_count_decrements_on_clear(void) {
    uint8_t s0 = get_sprite();
    get_sprite();
    clear_sprite(s0);
    TEST_ASSERT_EQUAL_UINT8(1u, sprite_pool_active_count());
}
```

  And register them in `main()` after `RUN_TEST(test_clear_sprites_from_zero_frees_all);`:

```c
    RUN_TEST(test_active_count_zero_after_init);
    RUN_TEST(test_active_count_tracks_allocations);
    RUN_TEST(test_active_count_decrements_on_clear);
```

- [ ] **STEP 1.2:** Run `make test` **from the worktree directory** (`C:\Code\nuke-raider\.claude\worktrees\feat-patrol-enemy-common`). Expected: **FAIL** — compile/link error, `sprite_pool_active_count` undefined. This confirms the test exercises the new seam.

- [ ] **STEP 1.3:** **GB gate** (writing `src/sprite_pool.h`): bank-pre-write fires automatically (PreToolUse hook); consult `gbdk-expert` only if a hardware-API question arises (none expected here — pure host-test seam). Add the declaration to `src/sprite_pool.h` inside the header, before `#endif`:

```c
#ifndef __SDCC
/* Host-test only: number of currently-claimed pool slots. Zero ROM/WRAM cost on hardware. */
uint8_t sprite_pool_active_count(void);
#endif
```

- [ ] **STEP 1.4:** **GB gate** (writing `src/sprite_pool.c`): bank-pre-write fires automatically. Add the definition to `src/sprite_pool.c`, after `clear_sprites_from` and before end of file. Note: NOT `BANKED` — it is host-test-only and excluded on hardware:

```c
#ifndef __SDCC
uint8_t sprite_pool_active_count(void) {
    uint8_t i;
    uint8_t n = 0u;
    for (i = 0u; i < MAX_SPRITES; i++) {
        if (spr_act[i]) n++;
    }
    return n;
}
#endif
```

- [ ] **STEP 1.5:** Run `make test` from the worktree directory. Expected: **PASS** — all `test_sprite_pool` tests green (existing 8 + new 3).

- [ ] **STEP 1.6:** Commit: `git commit -am "test(sprite_pool): add host-only sprite_pool_active_count seam"`.

---

## Task 2 — Lazy racer OAM allocation + INVALID init (RED → GREEN)

Move the four `get_sprite()` calls out of the unconditional init loop into the per-slot active block. Initialise `racer_oam[]` to `SPRITE_POOL_INVALID` for every slot first, so inactive slots carry a sentinel (not a stale/zero handle).

- [ ] **STEP 2.1 (RED):** Add a failing test to `tests/test_racer.c`. The test needs the `sprite_pool` seam, so add the include near the top (after `#include "projectile.h"`):

```c
#include "sprite_pool.h"
```

  Then add this test before `int main(void)`:

```c
/* === Lazy OAM allocation (PR3) === */

/* Track 0 (track.tmx) has no racers → racer_init must allocate ZERO sprites. */
void test_racer_init_allocates_no_sprites_when_no_racers(void) {
    sprite_pool_init();
    track_test_set_id(0u);
    racer_init(0u);
    TEST_ASSERT_EQUAL_UINT8(0u, sprite_pool_active_count());
}

/* Track 1 (id=1, track2.tmx) has 2 active enemy racers → 2 * 4 = 8 sprites,
 * NOT 12 (the old unconditional 4 * MAX_RACERS pre-allocation). */
void test_racer_init_allocates_four_per_active_racer(void) {
    sprite_pool_init();
    track_test_set_id(1u);
    racer_init(0u);
    TEST_ASSERT_EQUAL_UINT8(8u, sprite_pool_active_count());
}
```

  Register both in `main()` after `RUN_TEST(test_racer_init_skips_slot_when_no_waypoints);`:

```c
    RUN_TEST(test_racer_init_allocates_no_sprites_when_no_racers);
    RUN_TEST(test_racer_init_allocates_four_per_active_racer);
```

- [ ] **STEP 2.2:** Run `make test` from the worktree directory. Expected: **FAIL** — `test_racer_init_allocates_no_sprites_when_no_racers` asserts 0 but gets 12 (current code pre-allocates 4 × `MAX_RACERS`); `test_racer_init_allocates_four_per_active_racer` asserts 8 but gets 12.

- [ ] **STEP 2.3:** **GB gate** (writing `src/racer.c`): bank-pre-write fires automatically. Dispatch `gbdk-expert` in implementation mode only if needed; this change is a control-flow move of existing `get_sprite()` calls (no new hardware API), so a quick consult is sufficient. Edit `racer_init` in `src/racer.c`.

  **BEFORE** (lines ~178–211, the init loop + active loop):

```c
    for (i = 0u; i < MAX_RACERS; i++) {
        racer_active[i] = 0u;
        racer_vx[i] = (int8_t)0;
        racer_vy[i] = (int8_t)0;
        racer_gear[i] = 0u;
        racer_downshift_timer[i] = 0u;
        racer_hp[i]           = (uint8_t)RACER_HP;
        racer_hit_flash[i]    = 0u;
        racer_finish_armed[i] = 1u;
        racer_oam[i * 4u + 0u] = get_sprite();
        racer_oam[i * 4u + 1u] = get_sprite();
        racer_oam[i * 4u + 2u] = get_sprite();
        racer_oam[i * 4u + 3u] = get_sprite();
    }
    s_tile_base  = tile_base;

    track_id = track_get_id();
    s_finish_dir = track_get_finish_direction();

    /* Load each enemy slot (slots 1..MAX_RACERS-1; enemy index = i-1). */
    for (i = 1u; i < MAX_RACERS; i++) {
        load_racer_waypoints(track_id, i - 1u,
                             s_wp_tx[i - 1u], s_wp_ty[i - 1u],
                             &s_wp_count[i - 1u]);
        found = load_racer_spawn(track_id, i - 1u, &spawn_tx, &spawn_ty);
        if (found && s_wp_count[i - 1u] > 0u) {
            racer_active[i] = 1u;
            race_state_set_active(i, 1u);
            racer_px[i] = (int16_t)((uint16_t)spawn_tx * 8u);
            racer_py[i] = (int16_t)((uint16_t)spawn_ty * 8u);
            racer_wp_idx[i] = 0u;
            racer_dir[i] = track_get_start_dir();
        }
    }
```

  **AFTER** (init loop initialises OAM to INVALID instead of allocating; active block claims the 4 handles):

```c
    for (i = 0u; i < MAX_RACERS; i++) {
        racer_active[i] = 0u;
        racer_vx[i] = (int8_t)0;
        racer_vy[i] = (int8_t)0;
        racer_gear[i] = 0u;
        racer_downshift_timer[i] = 0u;
        racer_hp[i]           = (uint8_t)RACER_HP;
        racer_hit_flash[i]    = 0u;
        racer_finish_armed[i] = 1u;
        /* Lazy OAM: inactive slots hold the sentinel; handles are claimed below
         * only when the slot becomes active. Reclaims all 12 slots on Track 1. */
        racer_oam[i * 4u + 0u] = SPRITE_POOL_INVALID;
        racer_oam[i * 4u + 1u] = SPRITE_POOL_INVALID;
        racer_oam[i * 4u + 2u] = SPRITE_POOL_INVALID;
        racer_oam[i * 4u + 3u] = SPRITE_POOL_INVALID;
    }
    s_tile_base  = tile_base;

    track_id = track_get_id();
    s_finish_dir = track_get_finish_direction();

    /* Load each enemy slot (slots 1..MAX_RACERS-1; enemy index = i-1). */
    for (i = 1u; i < MAX_RACERS; i++) {
        load_racer_waypoints(track_id, i - 1u,
                             s_wp_tx[i - 1u], s_wp_ty[i - 1u],
                             &s_wp_count[i - 1u]);
        found = load_racer_spawn(track_id, i - 1u, &spawn_tx, &spawn_ty);
        if (found && s_wp_count[i - 1u] > 0u) {
            racer_active[i] = 1u;
            race_state_set_active(i, 1u);
            racer_px[i] = (int16_t)((uint16_t)spawn_tx * 8u);
            racer_py[i] = (int16_t)((uint16_t)spawn_ty * 8u);
            racer_wp_idx[i] = 0u;
            racer_dir[i] = track_get_start_dir();
            /* Lazy OAM: claim 4 sprite handles now that the slot is active. */
            racer_oam[i * 4u + 0u] = get_sprite();
            racer_oam[i * 4u + 1u] = get_sprite();
            racer_oam[i * 4u + 2u] = get_sprite();
            racer_oam[i * 4u + 3u] = get_sprite();
        }
    }
```

- [ ] **STEP 2.4:** Run `make test` from the worktree directory. Expected: **GREEN** for the two new lazy-OAM tests. **Note:** `racer_render`/`racer_hide` guards are not yet added, so any existing test that calls `racer_render`/`racer_hide` on an inactive slot may now pass `SPRITE_POOL_INVALID` to `move_sprite` — Task 3 adds the guards. If a regression test fails here, it is expected and resolved by Task 3; do NOT fix it any other way. (The `racer_spawn_for_test` helper sets `racer_oam[4..7]=0`, so existing slot-1 render tests still use valid handles.)

- [ ] **STEP 2.5:** Commit: `git commit -am "feat(racer): lazy OAM allocation — claim 4 handles only on active slots"`.

---

## Task 3 — `SPRITE_POOL_INVALID` guards in `racer_render` and `racer_hide` (RED → GREEN)

`racer_hide` currently `move_sprite`s every slot's 4 handles unconditionally — with lazy allocation, inactive slots now hold `SPRITE_POOL_INVALID` (`0xFF`), which `move_sprite` would treat as OAM index 255 (out of range; on hardware undefined, and the mock guards `nb < 40` but the intent is wrong). `racer_render`'s inactive/off-screen/hit-flash branches also `move_sprite` raw handles. Guard all of them: skip any handle equal to `SPRITE_POOL_INVALID`.

- [ ] **STEP 3.1 (RED):** Add tests to `tests/test_racer.c` that assert render/hide are safe when slots are unallocated. These rely on the move_sprite mock counter (`mock_move_sprite_call_count`) declared in `tests/mocks/mock_sprites.c`. Add the extern near the top of `test_racer.c` (after the `extern int16_t cam_y;` line):

```c
extern int mock_move_sprite_call_count;
extern void mock_move_sprite_reset(void);
```

  Add these tests before `int main(void)`:

```c
/* === Render/hide safe with SPRITE_POOL_INVALID slots (PR3) === */

/* After racer_init on a track with no racers, all OAM handles are INVALID.
 * racer_hide must NOT call move_sprite on any of them. */
void test_racer_hide_skips_invalid_slots(void) {
    sprite_pool_init();
    track_test_set_id(0u);   /* no racers → all slots INVALID */
    racer_init(0u);
    mock_move_sprite_reset();
    racer_hide();
    TEST_ASSERT_EQUAL_INT(0, mock_move_sprite_call_count);
}

/* racer_render with no active racers (all INVALID) must NOT move_sprite. */
void test_racer_render_skips_invalid_slots(void) {
    sprite_pool_init();
    track_test_set_id(0u);
    racer_init(0u);
    mock_move_sprite_reset();
    racer_render();
    TEST_ASSERT_EQUAL_INT(0, mock_move_sprite_call_count);
}
```

  Register in `main()` after the Task 2 registrations:

```c
    RUN_TEST(test_racer_hide_skips_invalid_slots);
    RUN_TEST(test_racer_render_skips_invalid_slots);
```

- [ ] **STEP 3.2:** Run `make test` from the worktree directory. Expected: **FAIL** — `racer_hide` calls `move_sprite` 12 times (4 × `MAX_RACERS`) on INVALID handles; `racer_render`'s inactive branch calls `move_sprite` 4 × `MAX_RACERS` times. Both assert 0 calls.

- [ ] **STEP 3.3:** **GB gate** (writing `src/racer.c`): bank-pre-write fires automatically; `gbdk-expert` consult if needed (pure guard logic, no new API).

  **3.3a — `racer_hide`.** BEFORE (lines ~245–253):

```c
void racer_hide(void) BANKED {
    uint8_t i;
    uint8_t j;
    for (i = 0u; i < MAX_RACERS; i++) {
        for (j = 0u; j < 4u; j++) {
            move_sprite(racer_oam[i * 4u + j], 0u, 0u);
        }
    }
}
```

  AFTER:

```c
void racer_hide(void) BANKED {
    uint8_t i;
    uint8_t j;
    for (i = 0u; i < MAX_RACERS; i++) {
        for (j = 0u; j < 4u; j++) {
            uint8_t h = racer_oam[i * 4u + j];
            if (h != SPRITE_POOL_INVALID) {
                move_sprite(h, 0u, 0u);
            }
        }
    }
}
```

  **3.3b — `racer_render`.** Add an early skip for unallocated slots at the very top of the per-slot body, before the existing `if (!racer_active[i])` block. Because lazy allocation guarantees an inactive slot always has INVALID handles (and an active slot always has valid ones), a single guard on the first handle is sufficient and cheap.

  BEFORE (the head of the loop body, lines ~440–454):

```c
    for (i = 0u; i < MAX_RACERS; i++) {
        int16_t scr_x;
        int16_t scr_y;
        uint8_t hw_x;
        uint8_t hw_y;
        uint8_t d;
        uint8_t flags;

        if (!racer_active[i]) {
            move_sprite(racer_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }
```

  AFTER:

```c
    for (i = 0u; i < MAX_RACERS; i++) {
        int16_t scr_x;
        int16_t scr_y;
        uint8_t hw_x;
        uint8_t hw_y;
        uint8_t d;
        uint8_t flags;

        /* Unallocated slot (lazy OAM): no handles to move. */
        if (racer_oam[i * 4u + 0u] == SPRITE_POOL_INVALID) {
            continue;
        }

        if (!racer_active[i]) {
            move_sprite(racer_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }
```

  Note: the hit-flash and off-screen branches further down in `racer_render` are now only reached for slots with valid handles (guaranteed by the new top guard), so they need no change.

- [ ] **STEP 3.4:** Run `make test` from the worktree directory. Expected: **GREEN** — the two new render/hide tests pass, and the full `test_racer` suite (all pre-existing tests + Task 2 tests) stays green. If any pre-existing test regressed, stop and reconcile against `racer_spawn_for_test` (which sets `racer_oam[4..7]=0`, valid handles) — do not weaken the guard.

- [ ] **STEP 3.5:** Commit: `git commit -am "fix(racer): guard render/hide against SPRITE_POOL_INVALID slots"`.

---

## Task 4 — Raise `MAX_SPRITES` 28 → 32 + update OAM budget comment

- [ ] **STEP 4.1:** **GB gate** (writing `src/config.h`): bank-pre-write fires automatically. Edit `src/config.h`.

  BEFORE (lines 8–9):

```c
/* OAM budget: player=4, dialog_arrow=1 (fixed), projectiles≤8, turrets≤8; hardware cap=40 */
#define MAX_SPRITES  28
```

  AFTER:

```c
/* OAM budget: player=4, dialog_arrow=1 (fixed), projectiles≤8, turrets≤8, racer pool (lazy,
 * ≤8 = 2 active enemies × 4) + patrol=4 (PR4). 32 + 3 fixed = 35 ≤ hardware cap 40. */
#define MAX_SPRITES  32
```

- [ ] **STEP 4.2:** Run `make test` from the worktree directory. Expected: **GREEN** — the `test_sprite_pool` and `test_racer` suites are parameterised on `MAX_SPRITES`; the bump must not break them (the `test_active_count_*` and lazy-OAM tests assert absolute counts ≤ 12, well under 32). Confirm full suite green.

- [ ] **STEP 4.3:** Commit: `git commit -am "feat(config): raise MAX_SPRITES 28->32 for patrol OAM headroom"`.

---

## Task 5 — Build + `make memory-check` OAM PASS verification

- [ ] **STEP 5.1:** Build the ROM from the worktree directory: `make`. Expected: clean compile, no errors. (bank-post-build + `make memory-check` fire automatically via the PostToolUse hook after a successful `make`.)

- [ ] **STEP 5.2:** Run the OAM budget check explicitly: `make memory-check`. Expected output shows OAM **PASS**, with 35 / 40 sprites (32 pool + 3 fixed):

```
=== GB Memory Validation Report ===
WRAM:  ...  PASS
VRAM:  ...  PASS
OAM:   35 / 40 sprites  (87%)  PASS

PASS
```

  Confirm the OAM line reads `35 / 40 sprites` and `PASS`. (`memory_check.py` computes `MAX_SPRITES (32) + OAM_FIXED_SLOTS (3) = 35`; 35/40 = 87% < 100% FAIL threshold and ≥ 80% WARN threshold — so the line shows **PASS**? No: 87% ≥ 80% → status is **WARN**.) **Decision point:** 35/40 = 87.5% lands in the WARN band (`WARN_FRAC=0.80`). The spec calls for OAM **PASS**. WARN is non-fatal (exit 0) and the budget is not exceeded, but to land a clean PASS, see STEP 5.3.

- [ ] **STEP 5.3:** **Reconcile WARN vs PASS.** 32 + 3 = 35 sprites = 87.5% of 40, which `memory_check.py` classifies as **WARN** (≥ 80%), not PASS. This is expected and acceptable — the binding constraint per issue #144 is that Track 1 *fits* (no FAIL/overflow), and the hook treats WARN as non-fatal (exit 0). Document in the PR body that OAM is WARN (35/40, 87%) by design — the patrol feature deliberately runs OAM near capacity, and `MAX_PATROLS>1` is explicitly out of scope pending a fresh audit. **Do not** lower `MAX_SPRITES` below 32 to chase a PASS band: 32 is the minimum that fits player(4) + dialog_arrow(1) + projectiles(8) + turrets(3, Track 1) + racer pool(lazy) + patrol(4). If the user requires a literal PASS line, the only correct lever is reducing a pool ceiling, which is out of scope for PR3 — surface this to the user rather than silently shrinking a budget.

> Verification note: AC7 in #144 says "OAM PASS (Track 1 fits within MAX_SPRITES=32)". The operative clause is *fits* — i.e. no FAIL. Treat WARN-at-87% as satisfying AC7, and call it out explicitly in the PR body.

---

## Task 6 — Self-Review

- [ ] **STEP 6.1: Spec-coverage table** — confirm every PR3 requirement maps to a task:

| PR3 requirement (from #144 R11 / OAM notes) | Task(s) | Verified by |
|---|---|---|
| Raise `MAX_SPRITES` 28 → 32 | Task 4 | STEP 4.2 (tests green), STEP 5.2 (memory-check) |
| Update OAM budget comment for patrol's 4 | Task 4 (STEP 4.1) | comment text review |
| Lazy racer OAM — allocate only for ACTIVE slots | Task 2 | `test_racer_init_allocates_no_sprites_when_no_racers` (=0), `test_racer_init_allocates_four_per_active_racer` (=8) |
| Init `racer_oam[]` to `SPRITE_POOL_INVALID` for inactive slots | Task 2 (STEP 2.3) | render/hide guard tests in Task 3 |
| `SPRITE_POOL_INVALID` guard in `racer_render` | Task 3 (STEP 3.3b) | `test_racer_render_skips_invalid_slots` |
| `SPRITE_POOL_INVALID` guard in `racer_hide` (no slot-0 corruption) | Task 3 (STEP 3.3a) | `test_racer_hide_skips_invalid_slots` |
| Reclaim 12 wasted slots on Track 1 | Task 2 | `test_racer_init_allocates_no_sprites_when_no_racers` |
| Track 2 allocates 8 not 12 | Task 2 | `test_racer_init_allocates_four_per_active_racer` |
| Allocation-count test seam | Task 1 | `sprite_pool_active_count()` + 3 tests |
| `test_racer` stays green (regression) | Tasks 2–4 | STEP 3.4, STEP 4.2 |
| `make memory-check` OAM PASS (fits) | Task 5 | STEP 5.2 / 5.3 |

- [ ] **STEP 6.2: Placeholder scan** — grep the diff for `TODO`, `TBD`, `FIXME`, `placeholder`, `...` in changed lines. Expected: none. Every step above contains complete, paste-ready code.

- [ ] **STEP 6.3: Type-consistency check** — confirm: `racer_oam[]` is `uint8_t` and `SPRITE_POOL_INVALID` is `0xFFu` (uint8_t-compatible) — assignment and comparison are type-clean. `sprite_pool_active_count()` returns `uint8_t` (≤ `MAX_SPRITES`=32, fits). `get_sprite()` returns `uint8_t`. `mock_move_sprite_call_count` is `int` — tests compare with `TEST_ASSERT_EQUAL_INT`. No signed/unsigned mismatch; no SDCC enum widening (no enums introduced).

- [ ] **STEP 6.4: Seam-cost check** — confirm `sprite_pool_active_count()` and its declaration are both inside `#ifndef __SDCC` (zero ROM/WRAM on hardware). Confirm the new `racer.c` guards compile on hardware (no `#ifndef __SDCC` wrapping — they are production code).

---

## Task 7 — Smoketest gate, push, and PR (per CLAUDE.md)

- [ ] **STEP 7.1:** Confirm current directory is the worktree (`pwd` → `...\worktrees\feat-patrol-enemy-common`).

- [ ] **STEP 7.2:** Fetch + merge latest master from the worktree directory: `git fetch origin && git merge origin/master`. Resolve any conflict in `racer.c` / `config.h` (PR1/PR2 may have touched `racer.c`). NEVER use `git merge master` alone.

- [ ] **STEP 7.3:** Clean build: `make clean && make`. `make memory-check` fires via PostToolUse hook — confirm no FAIL/ERROR (WARN on OAM is acceptable per STEP 5.3).

- [ ] **STEP 7.4:** Run the full host test suite once more: `make test` from the worktree directory. Expected: all suites green, including `test_racer`, `test_race_scenario`, `test_player`, `test_turret`, `test_sprite_pool`.

- [ ] **STEP 7.5:** Ask the user for confirmation before launching the ROM. On confirm, launch from the worktree directory (Windows: PowerShell `Start-Process`, per project memory — Bash `java -jar` exits silently): `Start-Process java -ArgumentList '-jar','C:\Tools\Emulicious\Emulicious.jar','build/nuke-raider.gb'`.

- [ ] **STEP 7.6: Smoketest checks** (ask the user to confirm each):
  - Track 1: no sprite flicker, no OAM corruption, player car renders correctly (slot 0 intact — this is the `racer_hide` corruption risk the guards fix).
  - Track 2: two enemy racers render and move correctly; race-position HUD P:1 / P:2 / P:3 still correct (regression check for the lazy-OAM change).
  - Returning Overmap → Track 1 → Track 2 repeatedly does not leak or mis-assign OAM handles (lazy alloc/free across track entries).

- [ ] **STEP 7.7:** Only after the user confirms the smoketest passes: update `README.md` only if user-visible behavior changed (this PR is internal OAM plumbing — likely no README change needed; skip if so).

- [ ] **STEP 7.8:** Push the branch and create the PR:

```
gh pr create --title "Patrol PR3: lazy racer OAM + MAX_SPRITES 28->32" --body "<body>"
```

  PR body must include:
  - `Part of #144` (this is PR3 of 4; it does NOT close the issue).
  - Summary: lazy racer OAM allocation (reclaims 12 slots on Track 1, allocates 8 on Track 2), `SPRITE_POOL_INVALID` guards in `racer_render`/`racer_hide` (fixes potential slot-0/player OAM corruption in `racer_hide`), `MAX_SPRITES` 28→32, host-test `sprite_pool_active_count()` seam.
  - OAM note: `make memory-check` reports OAM **WARN 35/40 (87%)** by design — within hardware cap, fits Track 1; satisfies AC7's "fits" clause. `MAX_PATROLS>1` out of scope pending re-audit.
  - Footer: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **STEP 7.9:** Commit `.claude/settings.local.json` if any new tool permission was approved during the session (per CLAUDE.md).
