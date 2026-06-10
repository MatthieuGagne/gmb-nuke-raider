#ifndef SPRITE_POOL_H
#define SPRITE_POOL_H

#include <stdint.h>
#include "config.h"

#define SPRITE_POOL_INVALID  0xFFu

void    sprite_pool_init(void) BANKED;
uint8_t get_sprite(void) BANKED;
void    clear_sprite(uint8_t i) BANKED;
void    clear_sprites_from(uint8_t i) BANKED;

#ifndef __SDCC
/* Host-test only: number of currently-claimed pool slots. Zero ROM/WRAM cost on hardware. */
uint8_t sprite_pool_active_count(void);
#endif

#endif /* SPRITE_POOL_H */
