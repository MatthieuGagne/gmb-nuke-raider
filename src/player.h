#ifndef PLAYER_H
#define PLAYER_H

#include <gb/gb.h>
#include <stdint.h>

void     player_init(void);
void     player_update(void);
void     player_render(void);
void     player_set_pos(int16_t x, int16_t y);
int16_t  player_get_x(void);
int16_t  player_get_y(void);
int8_t   player_get_vx(void);
int8_t   player_get_vy(void);

#include "track.h"

void player_reset_vel(void);
void player_apply_physics(uint8_t buttons, TileType terrain);

#endif /* PLAYER_H */
