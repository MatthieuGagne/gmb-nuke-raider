---
summary: Explosion module and OAM sprite patterns — OAM slot hand-off on entity death, screen-space drift fix (move_sprite each frame minus cam), explosion_spawn, turret_set_explosion_base, clear_sprite bank safety, sprite pool
tags: [explosion, oam, sprites, sprite-pool, gbdk, death-animation]
---

# Explosion module & OAM patterns

Patterns from `explosion.c` / `sprite_pool.c` for death animations and OAM ownership.
Death-path callers are documented in [[enemy-damage-pipeline]] and
[[beam-laser-module]].

## Bank safety of the death path

BANKED→BANKED call to `clear_sprite` from `explosion_update` is safe. `clear_sprite`
(from `sprite_pool.c`, `#pragma bank 255`) only calls `move_sprite` (OAM write, not
VRAM tile data), so no `SWITCH_ROM` hazard even though both functions are in autobank.
The bank-0 trampoline handles the dispatch correctly ([[sdcc-banking-rules]]).

## API shape

- Explosion module `turret_base`/`car_base` params in `explosion_init` are
  intentionally unused, suppressed with `(void)` casts. The actual tile base is passed
  per-spawn via `explosion_spawn(oam, tile_base, flip, is_car)`, not cached at init
  time. This API shape allows the caller (`state_playing`) to pass different tile slots
  per explosion type without the module needing to cache them.
- `explosion_active_count()` is `#ifndef __SDCC` only — a host-test helper with zero
  WRAM/ROM cost on hardware. The `BANKED` public API (`explosion_init`,
  `explosion_spawn`, `explosion_update`, `explosion_render`, `explosion_is_done`) is
  all that ships to ROM.
- `turret_set_explosion_base()` caches the explosion tile base in the turret module.
  Called from `state_playing.enter()` after `explosion_init()`. Pattern: a separate
  setter (not a second `turret_init` param) when adding a cross-module tile-base
  dependency post-hoc — avoids changing existing init signatures used throughout tests.

## OAM hand-off pattern for entity death animations

On entity death, pass the entity's OAM slot directly to
`explosion_spawn(oam, tile_base, flip, is_car, wx, wty)` — do NOT call `clear_sprite`
first. The explosion pool owns the slot until `explosion_update` fires `clear_sprite`
after all frames complete. The entity sets its `oam` field to `SPRITE_POOL_INVALID`
immediately after the hand-off. `wx` = world pixel x (e.g. `turret_oam_x[i]`); `wty` =
world tile y (e.g. `turret_ty[i]`). For car blasts pass `wx=0, wty=0` —
`player_render` repositions those OAM slots each frame independently.

## OAM sprites are screen-space — the turret explosion drift fix

`explosion_render` must call `move_sprite` each frame using the stored world coords
(`exp_wx`, `exp_wty`) minus cam_x/cam_y. Without this, the explosion sits at the
turret's last-rendered screen position and drifts as the camera scrolls. Formula:
`scr_x = exp_wx[i] - cam_x; scr_y = exp_wty[i]*8 - cam_y + 16`. Hide off-screen entries
with `move_sprite(oam, 0, 0)`. Car blast entries skip this path — player_render owns
their OAM position.
