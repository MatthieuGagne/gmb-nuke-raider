# Music Tempo Lag Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task.

**Goal:** Decouple music tempo from frame load so the song advances at a true 60 ticks/sec regardless of how long a frame takes, eliminating the tempo drag that grows as more entities are added.

**Architecture:** "VBlank-counted catch-up." The VBL ISR only increments a saturating byte counter (`music_ticks_owed`) — no bank switch, so it is interrupt-safe and avoids the documented `SWITCH_ROM`-in-ISR crash. The main loop drains the counter via `music_service()`, running `music_tick()` once per elapsed VBlank (clamped to `MUSIC_MAX_CATCHUP`). Behavior is byte-identical at 60 fps; under load the music stays on-tempo while visuals stutter (the chosen tradeoff). Spec: `docs/superpowers/specs/2026-06-08-music-tempo-lag-design.md`.

**Tech Stack:** GBDK-2020, SDCC, hUGEDriver, Unity (host tests via gcc).

## Open questions (must resolve before starting)

- None. Design validated by `music-expert`; resync coverage and helper double-tick resolved during grill-me (see spec + plan notes below).

---

## Implementation notes (resolved decisions)

- **Helper double-tick fix:** `vbl_sync()` and `vbl_display_off()` keep their **single** direct `music_tick()` (preserves `vbl_display_off`'s tight LCD-off-inside-VBlank timing — routing through `music_service()` could run up to 3 ticks and push the LCD-off write past the VBlank window). Immediately after the tick they **decrement `owed` by one** under `__critical`, so the next `music_service()` does not re-tick that VBlank.
- **Resync coverage:** `state_playing.enter()` always re-runs on every gameplay (re)entry (`state_manager.c` re-invokes `enter` on push/pop/replace) and always reaches `DISPLAY_ON` (line 121). `music_resync()` after that line covers every race start. No hidden pause/resume path.
- **`music_ticks_owed`** is one file-scope `static volatile uint8_t` in `music.c` — same allocation pattern as the existing `current_song_bank`; the hUGEDriver-WRAM-collision warning applies only to *static locals* inside `music_tick()`, not file-scope statics.
- **SFX unchanged:** `sfx_tick()` stays exactly once per frame. Looping it would truncate frame-authored SFX durations.

---

## Batch 1 — Music catch-up (the whole fix)

### Task 1: Music catch-up core + tests (host-testable)

**Files:**
- Modify: `src/config.h`, `src/music.h`, `src/music.c`
- Test: `tests/test_music.c`

**Depends on:** none
**Parallelizable with:** none — Tasks 2 and 3 both compile against symbols this task defines (`music_notify_vblank`, `music_service`, `music_resync`), so it must land first.

**Step 1: Write the failing tests**

In `tests/test_music.c`, add an extern for the mock counter and reset it in `setUp`:

```c
extern int hUGE_dosound_call_count;   /* tests/mocks/hUGEDriver_mock.c */

void setUp(void) {
    frame_ready = 0;
    _current_bank_mock = 0;
    hUGE_dosound_call_count = 0;
    music_resync();                   /* zero the catch-up counter between tests */
}
```

Add these test functions:

```c
/* music_service() with one owed VBlank runs exactly one driver tick. */
void test_music_service_one_owed_runs_one_tick(void) {
    music_resync();
    music_notify_vblank();                 /* owed = 1 */
    hUGE_dosound_call_count = 0;
    uint8_t ran = music_service();
    TEST_ASSERT_EQUAL_UINT8(1u, ran);
    TEST_ASSERT_EQUAL_INT(1, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* Three owed VBlanks (within the cap) run three driver ticks. */
void test_music_service_three_owed_runs_three_ticks(void) {
    music_resync();
    music_notify_vblank(); music_notify_vblank(); music_notify_vblank();
    hUGE_dosound_call_count = 0;
    uint8_t ran = music_service();
    TEST_ASSERT_EQUAL_UINT8(3u, ran);
    TEST_ASSERT_EQUAL_INT(3, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* Owed above MUSIC_MAX_CATCHUP clamps the drain but still fully zeroes the counter. */
void test_music_service_clamps_to_cap(void) {
    music_resync();
    for (uint8_t i = 0; i < 10u; i++) music_notify_vblank();
    hUGE_dosound_call_count = 0;
    uint8_t ran = music_service();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)MUSIC_MAX_CATCHUP, ran);
    TEST_ASSERT_EQUAL_INT((int)MUSIC_MAX_CATCHUP, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* The counter saturates at 255 and never wraps to 0. */
void test_music_notify_saturates_at_255(void) {
    music_resync();
    for (uint16_t i = 0; i < 300u; i++) music_notify_vblank();
    TEST_ASSERT_EQUAL_UINT8(255u, music_ticks_owed_peek());
}

/* music_resync() zeroes a non-zero counter. */
void test_music_resync_zeroes_counter(void) {
    music_notify_vblank(); music_notify_vblank();
    music_resync();
    TEST_ASSERT_EQUAL_UINT8(0u, music_ticks_owed_peek());
}

/* vbl_display_off() ticks exactly once and accounts for the VBlank it consumed,
 * so a following music_service() will not re-tick it (no double-tick). */
void test_vbl_display_off_accounts_one_tick(void) {
    music_resync();
    music_notify_vblank(); music_notify_vblank();   /* owed = 2 (simulate ISR) */
    frame_ready = 1;
    hUGE_dosound_call_count = 0;
    vbl_display_off();
    TEST_ASSERT_EQUAL_INT(1, hUGE_dosound_call_count);
    TEST_ASSERT_EQUAL_UINT8(1u, music_ticks_owed_peek());
}
```

Register each in `main()` with `RUN_TEST(...)`. Keep the three existing tests.

**Step 2: Run tests to verify they fail**

Run (from worktree): `make test`
Expected: FAIL — `music_notify_vblank` / `music_service` / `music_resync` / `music_ticks_owed_peek` undefined.

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `src/music.c`, `src/config.h`, `src/music.h` are existing bank-0 artifacts; no new `.c` file, so no `bank-manifest.json` change. Confirm the gate passes before writing.

**Step 4: HARD GATE — gbdk-expert**

Invoke the `gbdk-expert` agent. Confirm: file-scope `static volatile uint8_t` placement is safe; `__critical` snapshot/decrement usage is correct; `music_notify_vblank` stays non-BANKED bank-0; calling `music_resync()` after (not inside) `music_start()`'s `__critical` avoids nested critical sections.

**Step 5: Write the implementation**

`src/config.h` — after the `DEBUG_TICK_ADDR` line (~137):

```c
/* Music catch-up cap: max music_tick() calls music_service() runs in one frame to
 * resync tempo after a frame overrun. Bounds the catch-up so a multi-frame stall
 * cannot spiral or produce an audible fast-forward. Above this, excess ticks drop. */
#define MUSIC_MAX_CATCHUP 3u
```

`src/music.h` — after the `music_tick()` declaration (~line 18):

```c
/* music_notify_vblank() — called ONLY from vbl_isr(). Increments the catch-up
 * counter (saturating at 255). No bank switch, no hUGEDriver call -> interrupt-safe.
 * Must stay non-BANKED (bank 0). */
void music_notify_vblank(void);

/* music_service() — drain the catch-up counter: run music_tick() once per VBlank
 * elapsed since the last call (clamped to MUSIC_MAX_CATCHUP). Call once per main-
 * loop iteration in place of music_tick(). Returns the number of ticks run. */
uint8_t music_service(void);

/* music_resync() — zero the catch-up counter. Call on gameplay resume / LCD-on
 * (state_playing enter) and inside music_start(), so accumulated backlog does not
 * drain as an audible catch-up burst at a transition. */
void music_resync(void);

/* music_ticks_owed_peek() — test-visible read of the catch-up counter. */
uint8_t music_ticks_owed_peek(void);
```

`src/music.c`:
- Add `#include "config.h"` near the top (debug.h only includes it under `#ifdef DEBUG`).
- Add module state beside `current_song_bank` (~line 19): `static volatile uint8_t music_ticks_owed = 0u;`
- Add the four new functions:

```c
void music_notify_vblank(void) {
    if (music_ticks_owed < 255u) music_ticks_owed++;
}

uint8_t music_service(void) {
    uint8_t owed;
    __critical { owed = music_ticks_owed; music_ticks_owed = 0u; }
    if (owed > MUSIC_MAX_CATCHUP) owed = MUSIC_MAX_CATCHUP;
    for (uint8_t i = 0u; i < owed; i++) {
        music_tick();
    }
    return owed;
}

void music_resync(void) {
    __critical { music_ticks_owed = 0u; }
}

uint8_t music_ticks_owed_peek(void) {
    return music_ticks_owed;
}
```

- In `music_start()`, add `music_resync();` as the last line (AFTER the existing `__critical` block closes — do not nest):

```c
void music_start(uint8_t bank, const hUGESong_t *song) {
    current_song_bank = bank;
    __critical {
        uint8_t _saved_bank = CURRENT_BANK;
        SWITCH_ROM(bank);
        hUGE_init(song);
        SWITCH_ROM(_saved_bank);
    }
    music_resync();   /* fresh song has no backlog to honor */
}
```

- Update the two helpers to tick once and account for the consumed VBlank:

```c
void vbl_sync(void) {
    while (!frame_ready);
    frame_ready = 0;
    music_tick();
    __critical { if (music_ticks_owed) music_ticks_owed--; }
}

void vbl_display_off(void) {
    while (!frame_ready);
    frame_ready = 0;
    music_tick();
    __critical { if (music_ticks_owed) music_ticks_owed--; }
    LCDC_REG &= ~0x80U;
}
```

`music_tick()` itself is UNCHANGED.

**Step 6: Run tests to verify they pass**

Run: `make test`
Expected: PASS (all new + 3 existing music tests).

**Step 7: HARD GATE — build**

Invoke the `build` skill (or `make`). Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Confirm `src/music.c` stays in bank 0 and ROM/bank budgets are within limits.

**Step 9: Refactor checkpoint**

"Breaks when N > 1?" — The counter is a single scalar; catch-up is bounded by the config cap. No hard-coded entity assumptions. Proceed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)**

Invoke the `gb-c-optimizer` agent on `src/music.c`. Validate only; report issues (do not apply now).

**Step 11: Commit**

```bash
git add src/config.h src/music.h src/music.c tests/test_music.c
git commit -m "feat(music): VBlank-counted catch-up ticks (music_service/notify/resync)"
```

---

### Task 2: Wire catch-up into the VBL ISR and main loop

**Files:**
- Modify: `src/main.c`

**Depends on:** Task 1 (uses `music_notify_vblank`, `music_service`)
**Parallelizable with:** Task 3 — different file (`state_playing.c`), no shared symbols defined by either.

**Step 1: Write the failing test** — N/A. `src/main.c` is excluded from the host test build (`TEST_LIB_SRC := $(filter-out src/main.c,...)`). Verified by build + Smoketest Checkpoint 1.

**Step 2: Run test to verify it fails** — N/A (see Step 1).

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write`. `src/main.c` is an existing bank-0 artifact; no manifest change.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert`. Confirm `music_notify_vblank()` is safe to call from `vbl_isr` (no bank switch, no hUGEDriver call) and that replacing `music_tick()` with `music_service()` in the loop is correct.

**Step 5: Write the implementation**

In `vbl_isr()` (currently main.c:39-42), add the counter increment:

```c
static void vbl_isr(void) {
    move_bkg(cam_scx_shadow, cam_scy_shadow);  /* apply shadow SCX/SCY at VBlank start */
    music_notify_vblank();                      /* count this VBlank (no bank switch — ISR-safe) */
    frame_ready = 1;
}
```

In the main loop (currently main.c:61-68), replace the single `music_tick()` with `music_service()`; `sfx_tick()` stays once:

```c
    while (1) {
        while (!frame_ready);
        frame_ready = 0;
        music_service();          /* catch up music for every elapsed VBlank */
        sfx_tick();               /* exactly once per frame */
        input_update();
        state_manager_update();
    }
```

(`main.c` already `#include "music.h"`.)

**Step 6: Run tests** — `make test`. Expected: PASS (unchanged from Task 1; main.c not tested).

**Step 7: HARD GATE — build** — `make`. Expected: ROM, zero errors.

**Step 8: HARD GATE — bank-post-build** — invoke `bank-post-build`.

**Step 9: Refactor checkpoint** — no hard-coded N. Proceed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)** — run on `src/main.c`, report only.

**Step 11: Commit**

```bash
git add src/main.c
git commit -m "feat(music): drive catch-up from VBL ISR + main loop music_service()"
```

---

### Task 3: Resync on gameplay entry

**Files:**
- Modify: `src/state_playing.c`

**Depends on:** Task 1 (uses `music_resync`)
**Parallelizable with:** Task 2 — different file (`main.c`), no shared symbols.

**Step 1: Write the failing test** — N/A. `state_playing.enter()` LCD/transition behavior is not host-unit-tested; verified by Smoketest Checkpoint 1.

**Step 2: Run test to verify it fails** — N/A (see Step 1).

**Step 3: HARD GATE — bank-pre-write**

Invoke `bank-pre-write`. `src/state_playing.c` is an existing banked artifact already in the manifest; no manifest change.

**Step 4: HARD GATE — gbdk-expert**

Invoke `gbdk-expert`. Confirm calling `music_resync()` (a bank-0 function) from banked `state_playing.c` `enter()` is safe (it is invoked via the state manager's `invoke()` trampoline, like all other bank-0 calls here), and that `#include "music.h"` is present (add if missing).

**Step 5: Write the implementation**

In `state_playing.c` `enter()`, add `music_resync()` immediately after `DISPLAY_ON;` (currently line 121):

```c
    DISPLAY_ON;
    music_resync();   /* zero catch-up backlog so the race start does not burp */
}
```

Ensure `#include "music.h"` is in the file's includes; add it if absent.

**Step 6: Run tests** — `make test`. Expected: PASS (unchanged).

**Step 7: HARD GATE — build** — `make`. Expected: ROM, zero errors.

**Step 8: HARD GATE — bank-post-build** — invoke `bank-post-build`.

**Step 9: Refactor checkpoint** — single call, no N. Proceed.

**Step 10: HARD GATE — gb-c-optimizer (validate only)** — run on `src/state_playing.c`, report only.

**Step 11: Commit**

```bash
git add src/state_playing.c
git commit -m "feat(music): resync catch-up counter on gameplay entry"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential, first) | Task 1 | Defines `music_notify_vblank` / `music_service` / `music_resync`; host-testable core. Must complete before B. |
| B (parallel) | Task 2, Task 3 | Different files (`main.c`, `state_playing.c`); both depend only on Task 1; neither uses a symbol the other defines. |

### Smoketest Checkpoint 1 — music holds tempo under load; transitions and SFX clean

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: all budgets PASS. Fix any FAIL/ERROR before continuing.

**Step 4: Launch ROM (run from worktree directory — use PowerShell tool, not Bash)**
```powershell
Start-Process -FilePath "java" -ArgumentList "-jar", "C:\Tools\Emulicious\Emulicious.jar", "build\nuke-raider.gb" -PassThru
```

**Step 5: Confirm with user.** Verify:
- Title/overmap/hub music plays at normal tempo and pitch (no change vs before).
- Start a race and drive into the busiest part of the track (multiple racers/turrets/projectiles on screen). **The music tempo stays steady — it must NOT drag/slow down** as the action gets heavy. Visual stutter under heavy load is acceptable and expected.
- Hub menu/dialog transitions (which use `vbl_display_off`) sound normal — no speed-up or stutter in the music during menu re-renders.
- Fire weapons and take hits — SFX play at normal length (not cut short), and music is unaffected.

Wait for explicit user confirmation before finishing the branch.

---

## Plan Self-Review

| # | Check | Result |
|---|-------|--------|
| 1 | No hardcoded values | PASS — catch-up bound is `MUSIC_MAX_CATCHUP` in `config.h`; `255` is the inherent `uint8_t` saturation ceiling. |
| 2 | All tasks have test criteria | PASS — Task 1 has `make test` assertions; Tasks 2/3 have build + explicit smoketest checks (and document why no host test). |
| 3 | Parallel annotations justified | PASS — Task 1 `none` justified (defines shared symbols); Tasks 2/3 parallelizable, justified (different files, no shared symbols). |
| 4 | Parallel Execution Groups table present | PASS — table precedes the checkpoint. |
| 5 | No design narrative leaked | PASS — rationale lives in the spec; plan carries file paths, code, and steps. |
