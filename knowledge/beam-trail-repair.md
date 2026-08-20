---
summary: Incremental beam-trail repair — beam_repair_leaving, s_lane_repair fallback flag, beam_cast memo invalidation (s_cast_memo_ok reset), render-phase vs game-logic-phase queueing rules (#582)
tags: [beam, repair, camera, bg-tiles, memo, vblank, gbdk]
---

# Beam trail repair (#582)

How the painted LASER lane ([[beam-laser-module]]) gets un-painted as the car moves,
using [[camera-streaming]]'s `camera_repair_cells` and the invalidate queue.

## Incremental repair via beam_repair_leaving (#582 Task 3)

New `static uint8_t s_lane_repair` in `beam.c` (bank 255) flags "the whole lane needs a
restream", cleared in `beam_reset()` and both `beam_fire()` exit paths (the `n==0u`
wall-flush early return AND the normal path), set only inside `beam_repair_leaving()`.
`beam_render()` now calls `beam_repair_leaving()` (repaint cells the span left) BEFORE
`beam_paint()` (paint the current span) — order matters, the old trail must clear
before the new span draws. The helper computes two runs (`lo_n` = near-end cells that
advanced past, `hi_n` = far-end cells that shrank) from the previous frame's
`(s_drawn_lo, s_drawn_count)` vs this frame's `(s_lo_tile, s_count)`; `s_count==0u`
(pulse-end-of-life OR nose flush against a wall) means the WHOLE previous span left
(`lo_n = pc`). Each run ≤ `CAMERA_REPAIR_MAX_CELLS` (4) is repaired synchronously via
`camera_repair_cells()`; a run that exceeds it (car teleported / tested with an
artificial 40px jump) sets `s_lane_repair=1` and returns WITHOUT calling
`camera_repair_cells` — `beam_render()` runs in the render phase, before
`camera_update()`, and `camera_invalidate_row/col` must not be queued there
(src/camera.h:53 — queueing before `camera_update()` makes the camera drop its own
scroll stream). `beam_update()` (game-logic phase, runs after `camera_update()`) drains
the flag at the TOP of its live-pulse branch, using if/else (not a ternary) between
`camera_invalidate_row`/`_col` — the same shape already used at end-of-pulse
([[sdcc-banking-rules]]). The flag survives across the pulse boundary: it's cleared
only when the invalidate call actually queues (`queued==1`), mirrored in both the
live-pulse drain site and the end-of-pulse `s_dirty` drain site. All arithmetic is
`uint8_t` with explicit casts on every `+`/`-`; values stay ≤ `BEAM_MAX_CELLS`=22 so no
overflow. `make test` 32/32 in test_beam (28 pre-existing + 4 new), full suite 1007
tests green; `make`/`bank-post-build`/`memory-check` all exit 0 with OAM unchanged
32/40 (beam still paints BG tiles only, zero OAM cost).

## The beam_cast memo and its mandatory reset (#582 follow-up)

Regression-test the `s_cast_memo_ok = 0u;` reset in `beam_fire()`: `beam_cast()`'s memo
key is `(nose, vis_lo, vis_hi)` and deliberately omits `s_step`/`s_lane_px`/`s_axis` —
safe only because `beam_fire()` unconditionally invalidates the memo at the top of
every new pulse. Two pulses fired in opposite directions from different `px` can
collide on the same `nose` (e.g. `DIR_R` from px=64 → nose 80; `DIR_L` from px=80 →
nose 80, same camera) — without the reset, the second pulse silently reuses the first
pulse's cached span/count. `test_a_new_pulse_recasts_when_only_the_direction_flips` in
`tests/test_beam.c` proves this: drain the cooldown with `beam_update()` in a loop
(`beam_reset()` would also clear the memo and mask the bug), then fire the colliding
second pulse and assert the painted span matches the NEW direction, not the old one.
Confirmed by deletion: removing the reset line makes this one test FAIL
(`Expected 64 Was 0`) while all other beam tests still pass — proof the new test, not
the rest of the suite, is what catches this class of bug. One sentence was added to the
`beam_cast()` invariant comment noting `track_passable()`'s map/collision-mask data is
race-fixed (mutated only by `track_select()` from `state_overmap.c`, never inside
`STATE_PLAYING`) and is deliberately outside the key too — a future
runtime-mutable-tile feature (destructible walls, repair pads) would need to also bust
this memo.

## The header comment was wrong; the hi_n arm had no coverage (#582 final review)

`beam_repair_leaving()`'s header comment was factually wrong, and the fix was
comment-only, no logic change. It claimed a run longer than `CAMERA_REPAIR_MAX_CELLS`
"cannot happen while the car drives" — false: the `nc == 0u` branch (nose lands on a
wall or leaves the screen clip, R9) sets `lo_n = pc`, and `pc` can be the WHOLE painted
span, which routes straight into the fallback on an ordinary in-play pulse. The
fallback also does not repair same-frame: `beam_render()` only raises `s_lane_repair`;
`beam_update()` queues the restream after `camera_update()`; `camera_flush_vram()`
drains it the NEXT frame — a deliberate one-frame deviation from R5's "same frame"
rule, traded so a single VBlank never writes 22 repair tiles atop the camera stream.

**The `hi_n` arm (the NEAR end for `DIR_L`/`DIR_T`) had zero test coverage** — every
existing moving-car beam test fired `DIR_R`/`DIR_B`, where the near end is the LOW end
and `lo_n` carries the repair; `DIR_L`/`DIR_T` chase toward a LOWER tile index, so the
cell that leaves is at the HIGH end. **Proved the new tests bite, not just
green-by-luck**: commented out `if (s_drawn_count > 0u) beam_repair_leaving();` in
`beam_render()`, re-ran `make test` — both new hi_n tests failed
(`Expected 1 Was 64`/`65`, i.e. still reading the beam tile instead of the repaired
track tile), along with the pre-existing repair tests (expected, since the whole
function was disabled); restored the line, all 36 tests in `test_beam` passed. This
before/after-diff technique (temporarily neuter the function under test, confirm red,
restore, confirm green) is the concrete instance of "prove it bites" for a
repair/repaint-class feature where a wrong assertion could otherwise pass against a
no-op — see [[verification-techniques]].
