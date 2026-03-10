#ifndef SPRITE_POOL_H
#define SPRITE_POOL_H

#include <stdint.h>
#include "config.h"

#define SPRITE_POOL_INVALID  0xFFu

void    sprite_pool_init(void) BANKED;
uint8_t get_sprite(void) BANKED;
void    clear_sprite(uint8_t i) BANKED;
void    clear_sprites_from(uint8_t i) BANKED;

#endif /* SPRITE_POOL_H */
