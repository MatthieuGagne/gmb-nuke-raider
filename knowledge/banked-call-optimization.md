---
summary: Confirmed SM83/GBDK optimization patterns — cutting BANKED bank-trampoline calls in hot loops, safe SoA hoisting, verified int8 thrust headroom (gb-c-optimizer anti-patterns)
tags: [gbdk, sdcc, performance, banking, patrol]
---

# BANKED call optimization patterns

Confirmed anti-patterns and fixes from the `gb-c-optimizer` pass. Every `BANKED` call costs a
bank trampoline on SM83, so the recurring win is *calling less*, not calling faster.
See [[sdcc-banking-rules]] for the correctness rules these sit on top of.

## Loop-invariant BANKED accessors recomputed per iteration

`race_state.c` rank loop: `track_get_checkpoint_count()`, `track_get_checkpoints()`,
`player_get_x/y()`, and `track_get_finish_direction()` — all `BANKED`, so all paying trampoline
cost — were called inside a per-rival loop in the full-tie branch.

**Fix:** compute lazily ONCE on the first full tie behind a `tie_ready` flag, cache the results
(`player_px`/`py`, count, next pointer, `finish_dir`, `past_all_cps`), and reuse them for
subsequent full-tie rivals. Lazy rather than eager because the full-tie branch is rare — this
avoids repeated trampolines without paying the cost when no tie occurs.

## Double BANKED step-call for block detection

`patrol.c` / `racer.c` pattern: to detect a wall block, the code called
`vehicle_step_axis_x(px, py, vx)` to move, then `vehicle_step_axis_x(px, py, 0)` again to
compare — two cross-bank (bank 255) trampoline calls per axis, per entity, per frame.

**Cheaper form:** cache the pre-move value, call step once, then compare.

```c
int16_t old = px;
px = vehicle_step_axis_x(px, py, vx);
if (px == old && vx != 0) vx = 0;
```

The `vehicle_step_axis_*` contract already states "caller detects the block by comparing the
return value to the input px", so the second call is pure waste. Halves the per-axis trampoline
cost.

**Status as of patrol PR4:** nice-to-have, not a defect, because `MAX_PATROLS=1`. It becomes
material when N > 1.

## Hoisting an SoA element to a local is unsafe when the element is mutated

`patrol_update` reads `patrol_px[i]` / `patrol_py[i]` roughly 6–12 times but *also writes them*
(the `vehicle_step_axis` result). A naive `int16_t ppx = patrol_px[i]` hoist desyncs unless the
value is written back.

**Correct form:** work on a local copy, then store once at the end. Treat this as a perf
nice-to-have requiring care, never a blind hoist.

## Patrol velocity thrust add cannot overflow int8 (verified, PR4)

Friction only *decrements* magnitude toward zero, and the prior frame was clamped to
±`PATROL_SPEED` (±3). Thrust is `PATROL_SPEED * VEH_DIR_D{X,Y}[dir]` ∈ {−3, 0, 3}, so the worst
intermediate is ±6, after which `boost_clamp` re-clamps to ±3. No int8 overflow — the pattern is
safe to reuse.

## Redundant bare `{ }` block left after a refactor

Removing an `if (...) {` guard can leave a `{ ... }` block with no controlling statement, which
over-indents the body. Delete the braces and de-indent; behaviour-neutral.
