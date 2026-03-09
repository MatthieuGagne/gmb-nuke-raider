#include <gb/gb.h>
#include "track.h"

/*
 * Tile 0: off-track (color index 2)  — 2bpp: low=0x00, high=0xFF
 * Tile 1: road surface (color index 1) — 2bpp: low=0xFF, high=0x00
 */
static const uint8_t track_tile_data[] = {
    /* Tile 0: off-track */
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    /* Tile 1: road */
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00
};

void track_init(void) {
    set_bkg_data(0, 2, track_tile_data);
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}

uint8_t track_passable(int16_t world_x, int16_t world_y) {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return 0u;
    tx = (uint8_t)((uint16_t)world_x / 8u);
    ty = (uint8_t)((uint16_t)world_y / 8u);
    if (tx >= MAP_TILES_W || ty >= MAP_TILES_H) return 0u;
    return track_map[(uint16_t)ty * MAP_TILES_W + tx] != 0u;
}
