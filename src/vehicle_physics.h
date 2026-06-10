#ifndef VEHICLE_PHYSICS_H
#define VEHICLE_PHYSICS_H

#include <gb/gb.h>
#include <stdint.h>
#include "track.h"   /* TileType, active_map_w, active_map_h, track_passable */

/* Shared vehicle terrain physics + axis-separated slide collision.
 * The physics math is split into friction (pre gear-accel) and boost_clamp
 * (post gear-accel) so gear-bearing callers (player/racer) can drop their
 * caller-specific gear-accel between the two; a gearless convenience composes
 * them for callers with no accel (patrol, PR4).
 * Collision is generic: no gear/turret/racer/dir-hitbox coupling — callers layer
 * their own gates (directional hitbox, dynamic blockers, gear reset, damage). */

/* Direction → velocity-delta tables (0=T..7=LT), shared with player/racer.
 * Exposed so callers can keep their gas-axis decisions consistent. */
extern const int8_t VEH_DIR_DX[8];
extern const int8_t VEH_DIR_DY[8];

/* Friction portion (PRE gear-accel). Applies SAND/OIL/ROAD friction to vx/vy.
 *  terrain : TileType at the vehicle centre (SAND doubles friction; OIL zeroes it)
 *  gas     : 1 if the vehicle is under power this frame, else 0 (caller decides)
 *  dir     : facing 0..7 — indexes VEH_DIR_DX/DY to pick the gas-relieved axis
 * Does NOT touch gears or boost. Gear-reset-on-oil stays in the caller. */
void vehicle_apply_friction(int8_t *vx, int8_t *vy, uint8_t terrain,
                            uint8_t gas, uint8_t dir) BANKED;

/* Boost + clamp portion (POST gear-accel). Applies the BOOST -TERRAIN_BOOST_DELTA
 * to *vy when terrain == TILE_BOOST, then clamps both axes to ±max_speed.
 *  max_speed : caller-supplied per-axis velocity clamp magnitude. */
void vehicle_apply_boost_clamp(int8_t *vx, int8_t *vy, uint8_t terrain,
                               uint8_t max_speed) BANKED;

/* Gearless convenience = vehicle_apply_friction(...) then
 * vehicle_apply_boost_clamp(...) with NO accel between. For callers that have no
 * gear acceleration (patrol, PR4). Gear-bearing callers must instead call the
 * two split functions with their accel in the middle. */
void vehicle_apply_physics(int8_t *vx, int8_t *vy, uint8_t terrain,
                           uint8_t gas, uint8_t dir, uint8_t max_speed) BANKED;

/* Axis-separated slide step. Returns px+vx when the resulting 16x16 footprint
 * is in-bounds [0, active_map_w*8 - 16] AND all four 16x16 corners are
 * track_passable; otherwise returns px unchanged (caller detects the block by
 * comparing the return value to the input px). No damage/gear/ram side effects. */
int16_t vehicle_step_axis_x(int16_t px, int16_t py, int8_t vx) BANKED;

/* Same as vehicle_step_axis_x for the Y axis, using active_map_h. */
int16_t vehicle_step_axis_y(int16_t px, int16_t py, int8_t vy) BANKED;

#endif /* VEHICLE_PHYSICS_H */
