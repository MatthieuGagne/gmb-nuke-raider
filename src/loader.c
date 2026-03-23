/* src/loader.c — bank 0 (no #pragma bank). Only bank-0 code may call SWITCH_ROM. */
#include <gb/gb.h>
#include "loader.h"
#include "banking.h"
#include "player.h"
#include "track.h"
#include "config.h"

extern const uint8_t player_tile_data[];
extern const uint8_t player_tile_data_count;
BANKREF_EXTERN(player_tile_data)

extern const uint8_t bullet_tile_data[];
extern const uint8_t bullet_tile_data_count;
BANKREF_EXTERN(bullet_tile_data)

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

void load_bullet_tiles(void) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(bullet_tile_data));
    set_sprite_data(PROJ_TILE_BASE, bullet_tile_data_count, bullet_tile_data);
    SWITCH_ROM(saved);
}

void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(BANK(track_start_x));
    *x = track_start_x;
    *y = track_start_y;
    SWITCH_ROM(saved);
}
