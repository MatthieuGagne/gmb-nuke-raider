#ifndef PROJECTILE_H
#define PROJECTILE_H

#include <gb/gb.h>
#include <stdint.h>
#include "player.h"  /* player_dir_t */

/* Owner tags — reserved for enemy bullets (Issue #3) */
#define PROJ_OWNER_PLAYER 0u
#define PROJ_OWNER_ENEMY  1u

void    projectile_init(void) BANKED;
void    projectile_fire(uint8_t scr_x, uint8_t scr_y, player_dir_t dir, uint8_t owner) BANKED;
void    projectile_update(void) BANKED;
void    projectile_render(void) BANKED;

/* Test / debug accessors */
uint8_t projectile_count_active(void) BANKED;

/* Hit detection — consume the first matching projectile within radius r of (cx,cy).
 * check_hit_player: only matches PROJ_OWNER_ENEMY bullets.
 * check_hit_enemy:  only matches PROJ_OWNER_PLAYER bullets.
 * Returns 1 on hit (bullet consumed), 0 on miss. */
uint8_t projectile_check_hit_player(uint8_t cx, uint8_t cy, uint8_t r) BANKED;
uint8_t projectile_check_hit_enemy(uint8_t cx, uint8_t cy, uint8_t r) BANKED;
uint8_t projectile_get_x(uint8_t slot) BANKED;
uint8_t projectile_get_y(uint8_t slot) BANKED;

#endif /* PROJECTILE_H */
