#ifndef PLAYER_H
#define PLAYER_H

#include <gb/gb.h>
#include <stdint.h>

void     player_init(void);
void     player_update(uint8_t input);
void     player_render(void);
void     player_set_pos(int16_t x, int16_t y);
int16_t  player_get_x(void);
int16_t  player_get_y(void);

#endif /* PLAYER_H */
