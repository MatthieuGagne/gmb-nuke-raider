#pragma bank 255
#include <gb/gb.h>
#include "powerup.h"
#include "config.h"
#include "track.h"
#include "damage.h"
#include "sfx.h"
#include "sprite_pool.h"
#include "loader.h"    /* load_powerup_positions() NONBANKED */
#include "camera.h"    /* cam_y — needed for OAM y coordinate calculations */

/* SoA powerup pool — tile coordinates + OAM slot + type */
static uint8_t powerup_tx[MAX_POWERUPS];
static uint8_t powerup_ty[MAX_POWERUPS];
static uint8_t powerup_type[MAX_POWERUPS];
static uint8_t powerup_active[MAX_POWERUPS];
static uint8_t powerup_oam[MAX_POWERUPS];

/* ---- public API ---- */

void powerup_init(void) BANKED {
    uint8_t i;
    uint8_t count = 0u;
    for (i = 0u; i < MAX_POWERUPS; i++) {
        powerup_active[i] = 0u;
        powerup_oam[i]    = SPRITE_POOL_INVALID;
    }
    load_powerup_positions(track_get_id(),
                           powerup_tx, powerup_ty,
                           powerup_type, &count);
    for (i = 0u; i < count; i++) {
        powerup_active[i] = 1u;
        powerup_oam[i]    = get_sprite();
        if (powerup_oam[i] != SPRITE_POOL_INVALID) {
            set_sprite_tile(powerup_oam[i], POWERUP_TILE_BASE);
        }
    }
}

void powerup_init_empty(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_POWERUPS; i++) {
        powerup_active[i] = 0u;
        powerup_oam[i]    = SPRITE_POOL_INVALID;
        powerup_tx[i]     = 0u;
        powerup_ty[i]     = 0u;
        powerup_type[i]   = 0u;
    }
}

void powerup_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_POWERUPS; i++) {
        int16_t oam_y;
        if (!powerup_active[i] || powerup_oam[i] == SPRITE_POOL_INVALID) continue;
        /* Powerup OAM y accounts for camera scroll — powerups are in world space */
        oam_y = (int16_t)((uint16_t)powerup_ty[i] * 8u) - (int16_t)cam_y + 16;
        if (oam_y < 0 || oam_y > 175) continue;   /* off screen — skip */
        move_sprite(powerup_oam[i],
                    (uint8_t)((uint16_t)powerup_tx[i] * 8u + 8u),
                    (uint8_t)oam_y);
    }
}

void powerup_update(uint8_t player_tx, uint8_t player_ty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_POWERUPS; i++) {
        if (!powerup_active[i]) continue;
        if (powerup_tx[i] == player_tx && powerup_ty[i] == player_ty) {
            /* Collect: heal + sfx + deactivate */
            damage_heal(POWERUP_HEAL_AMOUNT);
            sfx_play(SFX_HEAL);
            if (powerup_oam[i] != SPRITE_POOL_INVALID) {
                clear_sprite(powerup_oam[i]);
                powerup_oam[i] = SPRITE_POOL_INVALID;
            }
            powerup_active[i] = 0u;
        }
    }
}

uint8_t powerup_count_active(void) BANKED {
    uint8_t i;
    uint8_t count = 0u;
    for (i = 0u; i < MAX_POWERUPS; i++) {
        if (powerup_active[i]) count++;
    }
    return count;
}

#ifndef __SDCC
void powerup_test_spawn(uint8_t tx, uint8_t ty, uint8_t type) {
    uint8_t i;
    for (i = 0u; i < MAX_POWERUPS; i++) {
        if (!powerup_active[i]) {
            powerup_tx[i]     = tx;
            powerup_ty[i]     = ty;
            powerup_type[i]   = type;
            powerup_active[i] = 1u;
            powerup_oam[i]    = SPRITE_POOL_INVALID;
            return;
        }
    }
}

uint8_t powerup_get_active(uint8_t i) { return powerup_active[i]; }
uint8_t powerup_get_type(uint8_t i)   { return powerup_type[i]; }
uint8_t powerup_get_tx(uint8_t i)     { return powerup_tx[i]; }
uint8_t powerup_get_ty(uint8_t i)     { return powerup_ty[i]; }
#endif
