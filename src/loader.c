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
BANKREF_EXTERN(track3_checkpoints)

#include "track_powerup_externs.h"

extern const uint8_t track3_map[];
BANKREF_EXTERN(track3_map)

extern const CheckpointDef track3_checkpoints[];
extern const uint8_t        track3_checkpoint_count;

extern uint8_t active_map_w;
extern uint8_t active_map_h;

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

void load_track3_tiles(void) NONBANKED {
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

void load_object_sprites(void) NONBANKED {
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
    } else if (id == 1u) {
        SWITCH_ROM(BANK(track2_checkpoints));
        n = track2_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) {
            dst[i] = track2_checkpoints[i];
        }
    } else {
        SWITCH_ROM(BANK(track3_checkpoints));
        n = track3_checkpoint_count;
        if (n > MAX_CHECKPOINTS) n = MAX_CHECKPOINTS;
        for (i = 0u; i < n; i++) {
            dst[i] = track3_checkpoints[i];
        }
    }
    *count = n;
    SWITCH_ROM(saved);
}

void load_track_header(uint8_t id) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    if (id == 0u) {
        SWITCH_ROM(BANK(track_map));
        active_map_w = track_map[0];
        active_map_h = track_map[1];
    } else if (id == 1u) {
        SWITCH_ROM(BANK(track2_map));
        active_map_w = track2_map[0];
        active_map_h = track2_map[1];
    } else {
        SWITCH_ROM(BANK(track3_map));
        active_map_w = track3_map[0];
        active_map_h = track3_map[1];
    }
    SWITCH_ROM(saved);
}

void load_npc_positions(uint8_t id,
                         uint8_t *out_tx,
                         uint8_t *out_ty,
                         uint8_t *out_type,
                         uint8_t *out_dir,
                         uint8_t *out_count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 1u) {
        SWITCH_ROM(BANK(track2_npc_count));
        n = track2_npc_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track2_npc_tx[i];
            out_ty[i]   = track2_npc_ty[i];
            out_type[i] = track2_npc_type[i];
            out_dir[i]  = track2_npc_dir[i];
        }
    } else if (id == 2u) {
        SWITCH_ROM(BANK(track3_npc_count));
        n = track3_npc_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track3_npc_tx[i];
            out_ty[i]   = track3_npc_ty[i];
            out_type[i] = track3_npc_type[i];
            out_dir[i]  = track3_npc_dir[i];
        }
    } else {
        SWITCH_ROM(BANK(track_npc_count));
        n = track_npc_count;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track_npc_tx[i];
            out_ty[i]   = track_npc_ty[i];
            out_type[i] = track_npc_type[i];
            out_dir[i]  = track_npc_dir[i];
        }
    }
    *out_count = n;
    SWITCH_ROM(saved);
}

void load_powerup_positions(uint8_t id,
                             uint8_t *out_tx,
                             uint8_t *out_ty,
                             uint8_t *out_type,
                             uint8_t *out_count) NONBANKED {
    uint8_t saved = CURRENT_BANK;
    uint8_t i;
    uint8_t n;
    if (id == 1u) {
        SWITCH_ROM(BANK(track2_powerup_count));
        n = track2_powerup_count;
        if (n > MAX_POWERUPS) n = MAX_POWERUPS;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track2_powerup_tx[i];
            out_ty[i]   = track2_powerup_ty[i];
            out_type[i] = track2_powerup_type[i];
        }
    } else if (id == 2u) {
        SWITCH_ROM(BANK(track3_powerup_count));
        n = track3_powerup_count;
        if (n > MAX_POWERUPS) n = MAX_POWERUPS;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track3_powerup_tx[i];
            out_ty[i]   = track3_powerup_ty[i];
            out_type[i] = track3_powerup_type[i];
        }
    } else {
        SWITCH_ROM(BANK(track_powerup_count));
        n = track_powerup_count;
        if (n > MAX_POWERUPS) n = MAX_POWERUPS;
        for (i = 0u; i < n; i++) {
            out_tx[i]   = track_powerup_tx[i];
            out_ty[i]   = track_powerup_ty[i];
            out_type[i] = track_powerup_type[i];
        }
    }
    *out_count = n;
    SWITCH_ROM(saved);
}

#ifdef __SDCC
void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) NONBANKED {
    uint8_t i;
    volatile uint8_t *dst = (volatile uint8_t *)
        (0x9800u + ((uint16_t)(vram_y & 31u) << 5u) + (vram_x & 31u));
    for (i = 0u; i < count; i++) dst[i] = tiles[i];
}
#endif /* __SDCC */
