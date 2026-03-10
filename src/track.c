#include <gb/gb.h>
#include "track.h"

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
