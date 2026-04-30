#ifndef ENEMY_H
#define ENEMY_H

#include <stdint.h>
#include "player.h"    /* player_dir_t */
#include "config.h"

/* Initialise enemy pool from pre-computed turret positions in ROM.
 * tile_base: OBJ tile index returned by loader_get_slot(TILE_ASSET_TURRET).
 * Reads track_get_id() to select the correct per-track array.
 * Must be called after track_select(). */
void    enemy_init(uint8_t tile_base) BANKED;

/* Zero the pool without map scan — host-test helper only. */
void    enemy_init_empty(void) BANKED;

/* Spawn a turret at tile coordinates (tx, ty).
 * Returns 1 on success, 0 if pool is full. */
uint8_t enemy_spawn(uint8_t tx, uint8_t ty) BANKED;

/* Per-frame update: decrement fire timers, fire bullets, check for destruction. */
void    enemy_update(int16_t player_px, int16_t player_py) BANKED;

/* Per-frame VBlank render: move OAM sprites to screen positions. */
void    enemy_render(void) BANKED;

/* Returns 1 if an active turret occupies tile (tx, ty). Used by player collision. */
uint8_t enemy_blocks_tile(uint8_t tx, uint8_t ty) BANKED;

/* Returns number of active enemies — used by tests. */
uint8_t enemy_count_active(void) BANKED;

/* Pure-logic helpers exposed for testing — not for production callers. */
player_dir_t enemy_dir_to_pixel(uint8_t tx, uint8_t ty,
                                 int16_t player_px, int16_t player_py) BANKED;

/* Test-only accessors — do not call from production code */
#ifndef __SDCC
uint8_t enemy_get_type(uint8_t i);
uint8_t enemy_get_dir(uint8_t i);
uint8_t enemy_get_timer(uint8_t i);
uint8_t enemy_is_screen_visible(uint8_t i);
#endif

#endif /* ENEMY_H */
