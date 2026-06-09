# Design: Fix frame-rate-coupled music tempo lag

**Date:** 2026-06-08
**Status:** Approved (design), pending implementation plan
**Validated by:** `music-expert` agent (consultation)

## Problem

As more entities (enemy racers, turrets, projectiles, powerups) are added, the
music tempo audibly **drags** — the song plays slower the busier the frame gets.

### Root cause: music is frame-locked

`music_tick()` -> `hUGE_dosound()` is called **once per frame from the main loop**
(`src/main.c:64`), after `while (!frame_ready); frame_ready = 0;`. hUGEDriver's
tempo *is* its tick rate: it expects to be advanced once every 16.7 ms (60 Hz).

When `state_manager_update()` (the per-frame entity loop, `src/state_playing.c`)
overruns the 16.7 ms frame budget, the main loop misses VBlanks. The next
`music_tick()` therefore fires late, and the song advances slower than wall-clock.
The tempo is chained behind game logic, so **every feature added re-opens the gap.**

Confirmed symptom: tempo slows/drags (not stutter, not dropout) — textbook
frame-rate coupling.

## Goal and chosen tradeoff

Decouple music tempo from frame load so the song advances at a true 60 ticks/sec
regardless of how long a frame takes.

When the game is genuinely overloaded, **something must give**. The chosen tradeoff:
**music stays perfectly on-tempo; the visuals stutter** (game logic runs at whatever
framerate it can hit). This is the standard action-game choice — a dropped frame is
barely noticeable, a wobbling soundtrack is glaring.

## Why not move the tick into the VBlank ISR

The "obvious" fix — call `hUGE_dosound()` directly from the VBL interrupt — is
**explicitly forbidden in this project** and documented as a crash source
(`.claude/agents/music-expert.md`):

> Calling `music_tick()` inside `vbl_isr()` — `SWITCH_ROM` inside an ISR corrupts
> MBC shadow state, causing crashes after several deep BANKED call sequences.

`music_tick()` does a bank switch (`SWITCH_ROM`) to reach the song data. If the
interrupt fires while the main loop is mid banked-function-call trampoline, the
bank-shadow variable and the MBC hardware desync, and the ISR's restore corrupts it.
The crash surfaces much later, after many state transitions. This approach trades a
music-lag bug for an intermittent-crash bug and is **rejected**.

## Chosen design: VBlank-counted catch-up ticks

The interrupt never enters the audio engine and never switches banks. It does one
cheap, safe thing: count elapsed VBlanks. The main loop drains that count, running
the music tick once per elapsed VBlank to catch up.

### Data flow

```
VBlank fires (60 Hz, LCD on)
  - vbl_isr:  move_bkg(scroll)             <- unchanged
              music_notify_vblank()         <- NEW: music_ticks_owed++  (1 byte, no bank switch, no hUGE call)
              frame_ready = 1               <- unchanged

Main loop, each iteration:
  while (!frame_ready);  frame_ready = 0;   <- unchanged game-logic pacing
  owed = music_service();                    <- NEW: snapshot+zero counter, run music_tick() that many times
  sfx_tick();                                <- UNCHANGED: exactly once per real frame
  input_update();  state_manager_update();   <- unchanged
```

### Module API (all state encapsulated in `src/music.c`)

```c
/* music.c - new module-static state */
static volatile uint8_t music_ticks_owed;   /* VBlanks elapsed since last service */

/* Called from vbl_isr() ONLY. Non-BANKED, bank 0. No SWITCH_ROM, no hUGE call.
 * Saturates at 255 so the byte never wraps to 0 and falsely signals "no work". */
void music_notify_vblank(void) {
    if (music_ticks_owed < 255u) music_ticks_owed++;
}

/* Called from the main loop, replacing the single music_tick() call.
 * Snapshot+zero under __critical (atomic vs the ISR ++), clamp the LOCAL copy,
 * then advance the driver that many ticks. Returns ticks actually run. */
uint8_t music_service(void) {
    uint8_t owed;
    __critical { owed = music_ticks_owed; music_ticks_owed = 0u; }
    if (owed > MUSIC_MAX_CATCHUP) owed = MUSIC_MAX_CATCHUP;
    for (uint8_t i = 0u; i < owed; i++) music_tick();
    return owed;
}

/* Zero the backlog under __critical. Call when gameplay resumes / LCD turns back
 * on, and inside music_start(), so a transition doesn't trigger a catch-up burst. */
void music_resync(void) {
    __critical { music_ticks_owed = 0u; }
}
```

`music_tick()` itself is **unchanged** — it keeps its own `__critical` + bank
save/`SWITCH_ROM`/`hUGE_dosound`/restore. Calling it N times back-to-back from
`music_service()` is fine: the critical sections are sequential, not nested.

### Key properties

1. **Tempo cannot drag.** Over any window, exactly one music tick runs per elapsed
   VBlank. Average tempo is locked to wall-clock no matter how slow a frame is.
2. **Zero change at 60 fps.** When not overloaded, `owed` is always 1 — byte-for-byte
   identical to today's behavior. The fix only engages on an actual overrun.
3. **ISR is bank-safe.** It only does a saturating byte increment — no `SWITCH_ROM`,
   no hUGE call, no BANKED trampoline. The documented crash hazard cannot occur.
4. **SFX is untouched.** Because the ISR never enters hUGEDriver, there are no new
   races with `sfx_play`/`sfx_tick`/`music_start`. SFX timing is unchanged.

### Catch-up cap

`MUSIC_MAX_CATCHUP` in `src/config.h`, **default 3**. Bounds the drain so a
multi-frame stall can't spiral and can't produce a long audible "fast-forward".
Above the cap, excess ticks are dropped (the only case where tiny drift returns —
well beyond any playable framerate). Per project rules this cap is explicit, tunable,
and documented — not a silent truncation.

Trade-off note (from `music-expert`): when catching up N ticks in <1 ms,
`hUGE_dosound()` advances N rows' worth of state near-instantly; intermediate note
triggers are overwritten by the last tick, producing a brief catch-up glitch instead
of a tempo drag. A small cap (2-3) keeps this imperceptible while still resyncing.

## Edge cases

### LCD-off transitions (`vbl_sync`, `vbl_display_off`)

With the LCD off, the VBlank interrupt does **not** fire, so `music_ticks_owed`
stops incrementing — no runaway during loads. The hazard is the *boundary*: a stale
`owed` accumulated just before a transition would drain as a catch-up burst exactly
when a state changes (visually busy, worst place for it).

**Resolution:** call `music_resync()` when gameplay resumes / the LCD turns back on,
and inside `music_start()` (a fresh song has no backlog to honor). The cap alone
prevents a hang; only the explicit reset prevents the spurious burst.

`vbl_sync()` / `vbl_display_off()` keep their direct `music_tick()` call (explicit
single-tick paths around LCD transitions). The implementation plan must **audit
their callers** (currently `state_hub.c` uses `vbl_display_off()` in 4 places;
`main.c` does not call `vbl_sync()`) to confirm no double-ticking, with
`music_resync()` on resume as the backstop.

### DEBUG tick counter

`music_tick()` calls `DBG_TICK_INC()`. Under catch-up this counts *driver ticks*,
not *frames*, so any diagnostic/test asserting "tick count == frame count" would
break under overrun. The plan must verify `test_music*` and DEBUG diagnostics don't
assume a 1:1 frame:tick ratio.

## Files impacted

- `src/music.c` — add `music_ticks_owed`, `music_notify_vblank()`, `music_service()`,
  `music_resync()`. `music_tick()` unchanged. `music_start()` calls `music_resync()`.
- `src/music.h` — declare the three new functions.
- `src/main.c` — `vbl_isr()` calls `music_notify_vblank()`; main loop replaces
  `music_tick();` with `music_service();` (keeps `sfx_tick()` once per frame).
- `src/config.h` — add `MUSIC_MAX_CATCHUP` (default 3).
- `src/state_playing.c` (or wherever gameplay resumes / LCD turns on) — call
  `music_resync()` on entry/resume.
- `tests/test_music.c` — new tests (below).

All of `src/music.c`, `src/sfx.c`, `src/main.c` stay in **bank 0** (home bank);
`music_notify_vblank()` must be non-`BANKED`. No `bank-manifest.json` change (no new
files).

## Testing (TDD)

`music_service()` is a pure, host-testable function; `tests/test_music.c` already
mocks hUGEDriver. New tests:

- `owed = 1` -> `music_service()` runs exactly one tick, returns 1, counter ends at 0.
- `owed = 3` -> runs three ticks, returns 3.
- `owed > MUSIC_MAX_CATCHUP` -> clamps to the cap, counter still fully zeroed.
- `music_notify_vblank()` saturates at 255 (does not wrap to 0).
- `music_resync()` zeros a non-zero counter.
- `music_service()` snapshot-and-zero leaves the counter at 0 after the call.
- Regression: at `owed = 1` behavior matches the pre-change single-tick path.

## Out of scope

- Optimizing the entity loop to reduce overruns (a separate, complementary follow-up
  that would shrink the *visual* stutter; not required for the music fix).
- Any change to hUGEDriver, song data, or the SFX engine.
- Moving `sfx_tick()` to catch-up (rejected — would truncate frame-authored SFX).
