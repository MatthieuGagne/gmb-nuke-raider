#ifndef BEAM_H
#define BEAM_H

#include <stdint.h>
#include "banking.h"

/* LASER instantaneous beam (#430).
 * Cardinal-only hitscan. Damage resolves on the fire frame through a one-frame
 * window that every enemy module polls; rendering paints BG tiles along the lane
 * and repairs them through the camera streamer. Never allocates an OAM slot —
 * the Playing sprite pool peaks at 32/32. */

/* tile_base: BG tile index from loader_get_slot(TILE_ASSET_BEAM).
 * +BEAM_TILE_OFS_H = horizontal segment, +BEAM_TILE_OFS_V = vertical.
 * Clears all pulse state and the equipped flag. */
void    beam_init(uint8_t tile_base) BANKED;

/* Clears pulse state, cooldown and the pending restore. Keeps tile base and the
 * equipped flag. */
void    beam_reset(void) BANKED;

/* 1 when the race loadout's WEAPON1 is LASER. Seeded once at race start. */
void    beam_set_equipped(uint8_t is_laser) BANKED;
uint8_t beam_is_equipped(void) BANKED;

/* Fire a pulse. px/py are the player's world-pixel top-left corner; dir is a
 * player_dir_t. Returns 1 if a pulse fired, 0 if refused (not equipped, facing a
 * diagonal, or still on cooldown). A refused diagonal press costs nothing. */
uint8_t beam_fire(int16_t px, int16_t py, uint8_t dir) BANKED;

/* Per-frame tick. Call in the game-logic phase AFTER camera_update(). px/py are
 * the player's world-pixel top-left corner, the same values beam_fire() takes.
 * Closes the damage window, ticks the cooldown and the visible timer, re-aims
 * the live pulse's start at the car nose, re-measures its length, and queues the
 * whole-lane BG restore when the pulse ends. */
void    beam_update(int16_t px, int16_t py) BANKED;

/* VBlank-phase render. Call immediately after camera_flush_vram(). */
void    beam_render(void) BANKED;

/* Damage for an enemy whose world-pixel top-left corner is (ex, ey) and whose
 * AABB is box x box. Returns WEAPON1_LASER_DAMAGE on a lane hit, else 0.
 * Non-consuming: every enemy in the lane is damaged by the same pulse. */
uint8_t beam_hit_damage(int16_t ex, int16_t ey, uint8_t box) BANKED;

/* Pure helper — 1 for DIR_T / DIR_R / DIR_B / DIR_L, 0 for every other facing. */
uint8_t beam_dir_is_cardinal(uint8_t dir) BANKED;

#endif /* BEAM_H */
