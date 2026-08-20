---
summary: beam.c LASER hitscan weapon module — BG-tile lane rendering with zero OAM, raycast, ring-split, beam_fire/beam_update/beam_render wiring into player.c and state_playing.c, enemy beam polling, host-test lane geometry
tags: [beam, laser, hitscan, weapon, bg-tiles, oam, raycast, gbdk]
---

# Beam / LASER hitscan module (beam.c)

`src/beam.c` (`#pragma bank 255`, manifest bank 255) implements the LASER weapon-1
option as a BG-tile-painting hitscan. Repair of the painted trail lives in
[[beam-trail-repair]]; the streaming substrate is [[camera-streaming]]; damage routing
is [[enemy-damage-pipeline]].

## Core design (#430 Task 4)

Deliberately NOT a pool (one player, one beam — same shape as `proj_cooldown_tick` in
projectile.c). Renders by painting BG tiles along the lane via `set_bkg_tiles` and
repairing them through `camera_invalidate_row/col`, so it allocates **zero OAM** —
verified by `make memory-check` staying at 32/40 (Playing is already at the pool cap
`MAX_SPRITES=32`, so any OAM-based beam would have overflowed). WRAM cost ~38 B
(`s_cell_buf[BEAM_MAX_CELLS]`=22 + scalars); total went 1,486→1,508 B (18%).

- **The render ring-split MUST mirror `camera.c`:** horizontal uses
  `if ((uint8_t)(vx + count) > 32u) { first = 32-vx; set_bkg_tiles(vx,vy,first,1,buf);
  set_bkg_tiles(0,vy,count-first,1,buf+first); }`, vertical is the `(x,y,1,h)`
  transpose — byte-identical to `stream_row`/`stream_col`. Note `> 32u` not `>= 32u`: a
  span ending exactly at column 31 needs no split. `vx + count` maxes at 31+22=53, so
  the `uint8_t` cast cannot wrap.
- **`set_bkg_tiles` writes ASCENDING, so the cell-buffer origin must be the LOWEST
  world tile of the span, not the first cell probed.** DIR_L/DIR_T sweep descending;
  after the raycast loop `x`/`y` sit one step PAST the last painted cell, so
  `lo = (step > 0) ? (c + step) : (coord - step)` recovers it. Getting this wrong
  paints the lane mirrored on the far side of the car and passes the DIR_R test while
  failing DIR_L.
- **`int16_t` in the raycast loop is NOT narrowable** — the coords go negative
  (DIR_L/DIR_T from near the origin reach `-8`) and exceed 255 (64-tile map = 512 px),
  and `track_passable(int16_t,int16_t)` takes `int16_t` so narrowing would force a
  re-widen at the call. Use `(uint16_t)n * 8u` for the span width, never
  `(uint8_t)(n << 3u)`.
- **Hoist `s_axis` into a local `uint8_t is_h` at the top of `beam_fire`.** The
  function branches on the axis 5x including once per raycast iteration; on z80 each
  static read is an absolute load, a stack local is not. Pure win, no clarity cost.
- **`beam_update()` must pick `camera_invalidate_row` vs `_col` with if/else, NOT a
  ternary** — both arms are BANKED calls, the shape of the documented SDCC
  return-register corruption bug ([[sdcc-banking-rules]]). Guard the retry on the
  `uint8_t` return (1=queued): `camera_flush_vram()` zeroes both queue lengths every
  render phase, so a full buffer self-heals next frame.
- Guard `beam_hit_damage` on `s_cell_count == 0u` **as well as** the damage window: a
  shot into a wall flush against the muzzle still consumes the cooldown and returns 1,
  leaving `s_x0..s_y1` stale from the previous pulse. That guard is load-bearing, not
  defensive.
- `beam_dir_is_cardinal` must run BEFORE `player_dir_dx()` — `DIR_DX/DIR_DY` in
  player.c are only 8 wide, and turret sectors DIR_NNE..DIR_NNW are 8..15. Cardinals
  are the even values `<= DIR_L`.
- `sfx_play` is bank-0 NONBANKED (manifest bank 0) — calling it from a bank-255 module
  is the safe BANKED→NONBANKED direction, already done by
  player.c/powerup.c/projectile.c.
- Test seam: `track_test_set_map()` takes RAW tile data with **no 2-byte header**;
  `camera_init(0,0)` on a 20x16 map clamps both axes to 0
  (`cam_max_y = h*8 - HUD_SCANLINE = 0`).

## Wiring the LASER fire branch into player.c + the frame loop (#430 Task 6)

`player.c` (bank 255) `#include "beam.h"`; the `KEY_PRESSED(J_A)` block is a two-way
branch: `if (beam_is_equipped()) { (void)beam_fire(px, py, (uint8_t)player_dir); } else
{ <existing scr_x/scr_y + projectile_fire> }`. `KEY_PRESSED` is level-triggered
(`((input) & (k))`, `input.h:19`) — that is what makes BOTH weapons auto-repeat while A
is held; each module owns its own cooldown, so the fire site itself must stay
stateless. Do NOT "fix" it to an edge test. The `uint8_t scr_x/scr_y` decls are now the
first statements of the `else` block (SDCC requires decls at block start) — moving them
out breaks compilation. `(void)` on a BANKED return is zero codegen.
`(uint8_t)player_dir` is explicit and safe (0..7); `beam_fire` re-checks cardinality
itself.

- `state_playing.c` gets exactly three edits, and **two of them are
  position-critical**: `beam_render()` immediately AFTER `camera_flush_vram()` (a later
  streamer pass would erase the painted lane), and `beam_update()` immediately AFTER
  `camera_update(px, py)` and after every enemy update. `camera_update()` only appends
  a stream event while its buffer is `< 1u` (camera.c:160,167) whereas
  `camera_invalidate_row/col` use the full `STREAM_BUF_SIZE=2` — queueing the beam
  repair first makes the camera silently drop its own row stream and leave an unpainted
  row while scrolling ([[camera-streaming]]).
- `beam_set_equipped(loadout_get_weapon1() == LOADOUT_WEAPON1_LASER)` in `enter()` is a
  BANKED return → comparison → BANKED arg. That is NOT the documented ternary hazard
  (the comparison result is a materialized scalar), and it is the same shape as the
  already-proven `projectile_set_weapon1_damage(WEAPON1_DAMAGE_TABLE[loadout_get_weapon1()])`
  on the line above ([[enemy-damage-pipeline]]). Order: it must follow `beam_init()`,
  which clears the equipped flag.
- Cost: OAM stays 32/40 (beam paints BG tiles, allocates no sprite), WRAM unchanged at
  1,509 B, ROM_1 unchanged at 100%. A
  `-Wconversion -Wsign-conversion -Wshadow -Wcast-qual` pass on both files is clean for
  the new code; the only two warnings are pre-existing in `player_render` (line 264).
  (Technique: [[verification-techniques]].)

## Enemy modules polling the beam (#430 Task 7)

turret.c / racer.c / patrol.c (all `#pragma bank 255`) each `#include "beam.h"` and add
ONE block per per-entity loop:
`uint8_t bdmg = beam_hit_damage(X_px[i], X_py[i], 16u); if (bdmg) { X_hp[i] =
enemy_apply_damage(X_hp[i], bdmg); X_hit_flash[i] = RACER_HIT_FLASH_FRAMES; if
(X_hp[i]==0u) { X_kill(i); } }`. Turret uses box `8u` and world coords `tx*8, ty*8`
(8x8 at the tile origin), no hit-flash field. `uint8_t bdmg` MUST be the first
statement of its block (SDCC); storing the BANKED return in a stack local then passing
it to BANKED `enemy_apply_damage` is the proven #424 Task 3 shape — NOT the ternary
hazard. `beam_hit_damage` is non-consuming (pierces), so every enemy in the lane is
damaged by one pulse — no "first hit wins" ordering to reason about.

- **Placement differs per module and is deliberate.** racer.c: OUTSIDE the
  `scr_cx/scr_cy` on-screen guard, because `scr_cx = racer_px[i] + 16` never subtracts
  `cam_x` (latent bug on horizontally scrolling tracks) and the beam is world-space +
  self-clipping. patrol.c: AFTER the `if (on_screen)` block closes, still inside the
  per-patrol loop. turret.c: INSIDE the `vis_x < 0 || …` guard — every statement past
  it is already gated and there is no "outside" without restructuring the loop;
  harmless because `vis_x` DOES subtract `cam_x`. The bullet branch already `continue`s
  on a kill, so a bullet-killed enemy never reaches the beam poll.
- `turret_destroy(uint8_t i)` extracted as a same-bank `static` (so NOT `BANKED`)
  helper above `turret_update`, shared by the bullet and beam death paths:
  `turret_active[i]=0u` + `explosion_spawn(turret_oam[i], s_explosion_base, 0u, 0u,
  turret_oam_x[i], turret_ty[i])` + `turret_oam[i]=SPRITE_POOL_INVALID`. Caller must
  `continue` — the helper touches neither hp nor the fire timer. Mirrors
  `patrol_destroy`/`racer_kill` ([[enemy-damage-pipeline]],
  [[explosion-oam-patterns]]).
- **TURRET_HP=1 vs WEAPON1_LASER_DAMAGE=2 is the #424 underflow regression guard**: one
  pulse must destroy a turret and drop `turret_count_active()`. Raw `hp - dmg` wraps to
  255 and leaves it alive; `enemy_apply_damage` floors at 0. Assert the ACTIVE COUNT,
  not hp — hp is the thing that would silently be 255.
- Cost: WRAM unchanged (1,509 B — all new state is stack locals), OAM unchanged 32/40,
  VRAM unchanged 76/384. `make bank-post-build` and `make memory-check` both exit 0.

## Host-test lane geometry & test-ordering hazards

**The default host-test lane geometry for `beam_fire(64,64,DIR_R)` ends at world x 128
EXCLUSIVE — an enemy placed at exactly 128 misses.** With the default `track_map`
(20x100, road = cols 4..15, col 16 is tile 0 = impassable), the raycast starts at tile
x 10 and stops at tile x 16, so `n = 6` cells and the damage rect is `s_x0 = 80`,
`s_x1 = 80 + 6*8 = 128`, band y = (68,76) (`BEAM_LANE_HALF = 4`). `beam_hit_damage`
tests `ex < s_x1`, so a 16x16 enemy at `ex = 128` is a legitimate MISS. Use 112 for the
second (pierce) enemy — the last 16-wide slot fully inside that does not overlap one at
96. Also remember the pools run PHYSICS BEFORE the poll: a racer with `wp_count = 0`
targets `s_wp_tx[n][0]` (0 → world (4,4)), picks DIR_L and steps 2 px west; a CHASEing
patrol steps `PATROL_SPEED = 5` px toward the player. Verify the POST-move coordinate
is in the lane, not the spawn coordinate.

- `racer_spawn_for_test(px, py, NULL, NULL, 0u, …)` is safe — the wp copy loop is
  bounded by `wp_count`, so NULL is never dereferenced. Activating a second racer by
  hand (`racer_active[2] = 1u` + `racer_set_pos_for_test(2u, …)`) is also safe:
  `enemy_wp_advance` guards `wp_count == 0` with `next >= wp_count`, no modulo.
- **`tests/test_racer.c`: put beam tests ABOVE every `track_test_set_map()` caller**
  (the first is `test_racer_finish_triggers_game_over`, 3rd `RUN_TEST`) — `setUp`
  restores `active_map_w/h` but NOT `loader_active_map_ptr`, so a stale 8x8 map makes
  `track_passable` index ~2000 into a 64-byte array and the raycast breaks on garbage.
  `tests/test_patrol.c` and `tests/test_turret.c` never inject a map, so order is free
  there — but `test_turret.c`'s `setUp` does NOT reset `cam_x`/`cam_y` and a
  neighbouring visibility test leaves `cam_y = 100`, so pin both in the test body.
  (Same family as the `test_player.c` hazard in [[host-test-gotchas]].)
- `tests/test_racer.c` already has `extern int16_t cam_y;` (racer.c's view); add
  `extern volatile uint16_t cam_x;` (camera.c's real type) rather than including
  `camera.h`, which would collide on `cam_y`.
