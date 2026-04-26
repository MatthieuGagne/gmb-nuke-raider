#ifndef PLAYER_H
#define PLAYER_H

#include <gb/gb.h>
#include <stdint.h>

/* 16 facing directions.
 * Values 0-7: player-usable (decoded from D-pad).
 * Values 8-15: turret-only intermediate directions (22.5° steps).
 * All values are indices into PROJ_VEL_DX/DY tables in projectile.c. */
typedef enum {
    DIR_T   = 0,   /* North       (UP)           */
    DIR_RT  = 1,   /* NE 45°      (UP + RIGHT)   */
    DIR_R   = 2,   /* East        (RIGHT)        */
    DIR_RB  = 3,   /* SE 45°      (DOWN + RIGHT) */
    DIR_B   = 4,   /* South       (DOWN)         */
    DIR_LB  = 5,   /* SW 45°      (DOWN + LEFT)  */
    DIR_L   = 6,   /* West        (LEFT)         */
    DIR_LT  = 7,   /* NW 45°      (UP + LEFT)    */
    /* Turret-only intermediate directions (22.5° steps) */
    DIR_NNE = 8,   /* N-NE 22.5°  */
    DIR_ENE = 9,   /* E-NE 67.5°  */
    DIR_ESE = 10,  /* E-SE 112.5° */
    DIR_SSE = 11,  /* S-SE 157.5° */
    DIR_SSW = 12,  /* S-SW 202.5° */
    DIR_WSW = 13,  /* W-SW 247.5° */
    DIR_WNW = 14,  /* W-NW 292.5° */
    DIR_NNW = 15,  /* N-NW 337.5° */
} player_dir_t;

void     player_init(uint8_t tile_base) BANKED;
void     player_update(void) BANKED;
void     player_render(void) BANKED;
void     player_set_pos(int16_t x, int16_t y) BANKED;
int16_t  player_get_x(void) BANKED;
int16_t  player_get_y(void) BANKED;
int8_t   player_get_vx(void) BANKED;
int8_t   player_get_vy(void) BANKED;

#include "track.h"

void player_reset_vel(void) BANKED;
void player_apply_physics(uint8_t buttons, TileType terrain) BANKED;
player_dir_t player_get_dir(void) BANKED;
int8_t player_dir_dx(player_dir_t dir) BANKED;
int8_t player_dir_dy(player_dir_t dir) BANKED;

#endif /* PLAYER_H */
