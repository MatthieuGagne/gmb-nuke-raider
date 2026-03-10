#pragma bank 255
#include <gb/gb.h>
#include "sprite_pool.h"
#include "config.h"

static uint8_t spr_act[MAX_SPRITES];

void sprite_pool_init(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_SPRITES; i++) {
        spr_act[i] = 0u;
        move_sprite(i, 0u, 0u);
    }
}

uint8_t get_sprite(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_SPRITES; i++) {
        if (!spr_act[i]) {
            spr_act[i] = 1u;
            return i;
        }
    }
    return SPRITE_POOL_INVALID;
}

void clear_sprite(uint8_t i) BANKED {
    move_sprite(i, 0u, 0u);
    spr_act[i] = 0u;
}

void clear_sprites_from(uint8_t i) BANKED {
    uint8_t j;
    for (j = i; j < MAX_SPRITES; j++) {
        clear_sprite(j);
    }
}
