#ifndef PLAYER_H
#define PLAYER_H

#include <gb/gb.h>
#include <stdint.h>

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

#endif /* PLAYER_H */
