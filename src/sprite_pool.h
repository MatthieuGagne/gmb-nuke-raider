#ifndef SPRITE_POOL_H
#define SPRITE_POOL_H

#include <stdint.h>
#include "config.h"

#define SPRITE_POOL_INVALID  0xFFu

void    sprite_pool_init(void);
uint8_t get_sprite(void);
void    clear_sprite(uint8_t i);
void    clear_sprites_from(uint8_t i);

#endif /* SPRITE_POOL_H */
