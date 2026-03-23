#pragma bank 255
#include <gb/gb.h>
#include "track.h"
#include "banking.h"
#include "loader.h"

/* Tile index → TileType lookup table — static const is linked into ROM by SDCC on sm83 */
#define TILE_LUT_LEN 8u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
    TILE_ROAD,   /* 6: finish line visual — passable */
    TILE_REPAIR, /* 7: repair pad */
};

/* --- Track dispatch state --- */
static uint8_t active_track_id;

/* Active track parameters — copied from the selected track's descriptor
 * at track_select() time. Avoids cross-bank reads in hot-path accessors.
 * Default to track 0 so passable/raw_tile calls work before track_select(). */
static const uint8_t *active_map     = track_map;
static int16_t        active_start_x;
static int16_t        active_start_y;
static uint8_t        active_finish_ty;
static uint8_t        active_lap_count;

void track_select(uint8_t id) BANKED {
    active_track_id = id;
    if (id == 0u) {
        active_map       = track_map;
        active_start_x   = track_start_x;
        active_start_y   = track_start_y;
        active_finish_ty = track_finish_line_y;
        active_lap_count = 3u;
    } else {
        active_map       = track2_map;
        active_start_x   = track2_start_x;
        active_start_y   = track2_start_y;
        active_finish_ty = track2_finish_line_y;
        active_lap_count = 3u;
    }
}

uint8_t track_get_finish_ty(void) BANKED { return active_finish_ty; }
uint8_t track_get_lap_count(void) BANKED { return active_lap_count; }
int16_t track_get_start_x(void)   BANKED { return active_start_x;   }
int16_t track_get_start_y(void)   BANKED { return active_start_y;   }

TileType track_tile_type_from_index(uint8_t tile_idx) BANKED {
    if (tile_idx >= TILE_LUT_LEN) return TILE_ROAD;
    return (TileType)tile_type_lut[tile_idx];
}

TileType track_tile_type(int16_t world_x, int16_t world_y) BANKED {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return TILE_WALL;
    tx = (uint8_t)((uint16_t)world_x >> 3u);
    ty = (uint8_t)((uint16_t)world_y >> 3u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return TILE_WALL;
    return track_tile_type_from_index(active_map[(uint16_t)ty * MAP_TILES_W + tx]);
}

void track_init(void) BANKED {
    if (active_track_id == 0u) {
        load_track_tiles();
    } else {
        load_track2_tiles();
    }
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}

uint8_t track_get_raw_tile(uint8_t tx, uint8_t ty) BANKED {
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return 0u;
    return active_map[(uint16_t)ty * MAP_TILES_W + tx];
}

uint8_t track_passable(int16_t world_x, int16_t world_y) BANKED {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return 0u;
    tx = (uint8_t)((uint16_t)world_x >> 3u);
    ty = (uint8_t)((uint16_t)world_y >> 3u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return 0u;
    return active_map[(uint16_t)ty * MAP_TILES_W + tx] != 0u;
}
