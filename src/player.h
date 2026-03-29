#ifndef PLAYER_H
#define PLAYER_H

#include <gb/gb.h>
#include <stdint.h>

/* 8 facing directions — decoded from D-pad combos each frame.
 * Enum values are indices into DIR_DX / DIR_DY lookup tables. */
typedef enum {
    DIR_T  = 0,  /* North      (UP)           */
    DIR_RT = 1,  /* NE         (UP + RIGHT)   */
    DIR_R  = 2,  /* East       (RIGHT)        */
    DIR_RB = 3,  /* SE         (DOWN + RIGHT) */
    DIR_B  = 4,  /* South      (DOWN)         */
    DIR_LB = 5,  /* SW         (DOWN + LEFT)  */
    DIR_L  = 6,  /* West       (LEFT)         */
    DIR_LT = 7,  /* NW         (UP + LEFT)    */
} player_dir_t;

void     player_init(void) BANKED;
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
