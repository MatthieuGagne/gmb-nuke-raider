#ifndef PLAYER_H
#define PLAYER_H

#include <gb/gb.h>
#include <stdint.h>

/* Player domain API */
void    player_init(void);
void    player_update(uint8_t input);
void    player_render(void);
void    player_set_pos(uint8_t x, uint8_t y);
uint8_t player_get_x(void);
uint8_t player_get_y(void);

/* Clamping helper — static inline for zero call overhead on Z80 */
static inline uint8_t clamp_u8(uint8_t v, uint8_t lo, uint8_t hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

#endif /* PLAYER_H */
