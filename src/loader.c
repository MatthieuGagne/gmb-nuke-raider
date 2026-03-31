/* src/loader.c — bank 0 (no #pragma bank). Only bank-0 code may call SWITCH_ROM. */
#include <gb/gb.h>
#include "loader.h"
#include "banking.h"
#include "player.h"
#include "track.h"
#include "config.h"
#include "overmap_car_sprite.h"

extern const uint8_t player_tile_data[];
extern const uint8_t player_tile_data_count;
BANKREF_EXTERN(player_tile_data)

extern const uint8_t bullet_tile_data[];
extern const uint8_t bullet_tile_data_count;
BANKREF_EXTERN(bullet_tile_data)

extern const uint8_t turret_tile_data[];
extern const uint8_t turret_tile_data_count;
BANKREF_EXTERN(turret_tile_data)

BANKREF_EXTERN(track_checkpoints)
BANKREF_EXTERN(track2_checkpoints)

void load_player_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(player_tile_data));
    set_sprite_data(0, player_tile_data_count, player_tile_data);
    SWITCH_ROM(saved);
}

void load_track_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_tile_data));
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    SWITCH_ROM(saved);
}

void load_track2_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_tile_data));
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    SWITCH_ROM(saved);
}

void load_bullet_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(bullet_tile_data));
    set_sprite_data(PROJ_TILE_BASE, bullet_tile_data_count, bullet_tile_data);
    SWITCH_ROM(saved);
}

void load_turret_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(turret_tile_data));
    set_sprite_data(TURRET_TILE_BASE, turret_tile_data_count, turret_tile_data);
    SWITCH_ROM(saved);
}

/* Loads overmap car tiles into VRAM sprite slots 18–19 (OVERMAP_CAR_TILE_BASE).
   Must be called inside DISPLAY_OFF during STATE_OVERMAP enter() only.
   Slot 18 is shared with TURRET_TILE_BASE — mutual exclusion enforced by
   state machine: turret loads only in STATE_PLAYING, car loads only in STATE_OVERMAP. */
void load_overmap_car_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(overmap_car_tile_data));
    set_sprite_data(OVERMAP_CAR_TILE_BASE, overmap_car_tile_data_count, overmap_car_tile_data);
    SWITCH_ROM(saved);
}

void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_start_x));
    *x = track_start_x;
    *y = track_start_y;
    SWITCH_ROM(saved);
}

void load_checkpoints(uint8_t id, CheckpointDef *dst, uint8_t *count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 0u) {
        SWITCH_ROM(BANK(track_checkpoints));
        n = track_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) {
            dst[i] = track_checkpoints[i];
        }
    } else {
        SWITCH_ROM(BANK(track2_checkpoints));
        n = track2_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) {
            dst[i] = track2_checkpoints[i];
        }
    }
    *count = n;
    SWITCH_ROM(saved);
}
