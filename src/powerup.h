#ifndef POWERUP_H
#define POWERUP_H

#include <gb/gb.h>
#include <stdint.h>
#include "config.h"

/* Initialise powerup pool from track data (calls load_powerup_positions + get_sprite). */
void powerup_init(void) BANKED;

/* Zero pool without hardware calls — for host-side unit tests. */
void powerup_init_empty(void) BANKED;

/* Move OAM sprites to screen positions based on current camera.
 * Must be called during VBlank. */
void powerup_render(void) BANKED;

/* Check tile-based player overlap; collect on match.
 * player_tx/player_ty are tile coordinates (pixel >> 3). */
void powerup_update(uint8_t player_tx, uint8_t player_ty) BANKED;

/* Returns number of currently active powerups. */
uint8_t powerup_count_active(void) BANKED;

#ifndef __SDCC
/* Test-only helpers — not compiled into ROM. */
void    powerup_test_spawn(uint8_t tx, uint8_t ty, uint8_t type);
uint8_t powerup_get_active(uint8_t i);
uint8_t powerup_get_type(uint8_t i);
uint8_t powerup_get_tx(uint8_t i);
uint8_t powerup_get_ty(uint8_t i);
#endif

#endif /* POWERUP_H */
