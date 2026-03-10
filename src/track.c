#include <gb/gb.h>
#include "track.h"

/* Tile index → TileType lookup table — static const is linked into ROM by SDCC on sm83 */
#define TILE_LUT_LEN 6u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
};

TileType track_tile_type_from_index(uint8_t tile_idx) {
    if (tile_idx >= TILE_LUT_LEN) return TILE_ROAD;
    return (TileType)tile_type_lut[tile_idx];
}

TileType track_tile_type(int16_t world_x, int16_t world_y) {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return TILE_WALL;
    tx = (uint8_t)((uint16_t)world_x >> 3u);
    ty = (uint8_t)((uint16_t)world_y >> 3u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return TILE_WALL;
    return track_tile_type_from_index(track_map[(uint16_t)ty * MAP_TILES_W + tx]);
}

/* Tile data generated from assets/maps/tileset.png — see src/track_tiles.c */
extern const uint8_t track_tile_data[];
extern const uint8_t track_tile_data_count;

void track_init(void) {
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}

uint8_t track_passable(int16_t world_x, int16_t world_y) {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return 0u;
    tx = (uint8_t)((uint16_t)world_x >> 3u);
    ty = (uint8_t)((uint16_t)world_y >> 3u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return 0u;
    return track_map[(uint16_t)ty * MAP_TILES_W + tx] != 0u;
}
