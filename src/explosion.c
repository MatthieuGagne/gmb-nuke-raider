#pragma bank 255
#include <gb/gb.h>
#include "explosion.h"
#include "config.h"
#include "sprite_pool.h"

static uint8_t exp_active[MAX_EXPLOSIONS];
static uint8_t exp_frame[MAX_EXPLOSIONS];
static uint8_t exp_timer[MAX_EXPLOSIONS];
static uint8_t exp_oam[MAX_EXPLOSIONS];
static uint8_t exp_tile[MAX_EXPLOSIONS];
static uint8_t exp_flip[MAX_EXPLOSIONS];
static uint8_t exp_car[MAX_EXPLOSIONS];
static uint8_t s_car_active;

void explosion_init(uint8_t turret_base, uint8_t car_base) BANKED {
    uint8_t i;
    (void)turret_base; (void)car_base;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) exp_active[i] = 0u;
    s_car_active = 0u;
}

void explosion_spawn(uint8_t oam, uint8_t tile_base, uint8_t flip, uint8_t is_car) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) {
        if (!exp_active[i]) {
            exp_active[i] = 1u;
            exp_frame[i]  = 0u;
            exp_timer[i]  = 0u;
            exp_oam[i]    = oam;
            exp_tile[i]   = tile_base;
            exp_flip[i]   = flip;
            exp_car[i]    = is_car;
            if (is_car) s_car_active++;
            return;
        }
    }
}

void explosion_update(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) {
        if (!exp_active[i]) continue;
        exp_timer[i]++;
        if (exp_timer[i] >= EXPLOSION_FRAME_TICKS) {
            exp_timer[i] = 0u;
            exp_frame[i]++;
            if (exp_frame[i] >= EXPLOSION_NUM_FRAMES) {
                exp_active[i] = 0u;
                if (exp_car[i] && s_car_active) s_car_active--;
                clear_sprite(exp_oam[i]);
            }
        }
    }
}

void explosion_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) {
        if (!exp_active[i]) continue;
        set_sprite_prop(exp_oam[i], exp_flip[i]);
        set_sprite_tile(exp_oam[i], (uint8_t)(exp_tile[i] + exp_frame[i]));
    }
}

uint8_t explosion_is_done(void) BANKED { return (s_car_active == 0u) ? 1u : 0u; }

#ifndef __SDCC
uint8_t explosion_active_count(void) {
    uint8_t i, n = 0u;
    for (i = 0u; i < MAX_EXPLOSIONS; i++) if (exp_active[i]) n++;
    return n;
}
#endif
