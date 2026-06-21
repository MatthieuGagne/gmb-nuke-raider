#ifndef ENEMY_COMMON_H
#define ENEMY_COMMON_H

#include <stdint.h>
#include "player.h"    /* player_dir_t */
#include "banking.h"   /* BANKED */

/* Shared enemy-AI math used by turret.c, racer.c, and (PR4) patrol.c.
 * All functions are pure (no side effects, no static state). */

/* 16-way aim direction from a source tile toward a player pixel position.
 * tx, ty: source tile coordinates. player_px, player_py: player pixel coords.
 * Returns a player_dir_t (cardinal or one of the 8 intermediate sectors). */
player_dir_t enemy_aim_dir(uint8_t tx, uint8_t ty,
                           int16_t player_px, int16_t player_py) BANKED;

/* 8-way direction from a signed delta. Returns a uint8_t DIR_* value
 * (DIR_T/RT/R/RB/B/LB/L/LT). Diagonals chosen when |dx| == |dy|. */
uint8_t enemy_dir_from_delta(int8_t dx, int8_t dy) BANKED;

/* Returns 1 if the Manhattan distance |dx|+|dy| is strictly below threshold. */
uint8_t enemy_wp_reached(int8_t dx, int8_t dy, uint8_t threshold) BANKED;

/* Returns the next waypoint index. If reached is non-zero, advances cur_idx by
 * one, wrapping to 0 when it would reach wp_count. If reached is zero, returns
 * cur_idx unchanged. */
uint8_t enemy_wp_advance(uint8_t cur_idx, uint8_t wp_count, uint8_t reached) BANKED;

/* Ram-collision test: 1 if the player 16x16 AABB at (px,py) overlaps the enemy
 * 16x16 AABB at (ex,ey), with the enemy box inflated by ENEMY_RAM_REACH on every
 * side. The margin lets a car solid-blocked flush against an enemy still ram it
 * from any direction. Shared by racer.c and patrol.c so both use identical
 * collision logic (#417). */
uint8_t enemy_ram_overlap(int16_t px, int16_t py, int16_t ex, int16_t ey) BANKED;

#endif /* ENEMY_COMMON_H */
