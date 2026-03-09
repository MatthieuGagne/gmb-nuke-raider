#include <gb/gb.h>
#include "track.h"

/*
 * Tile 0: off-track — all pixels color index 2 (dark gray / wasteland)
 *         2bpp: low=0x00, high=0xFF per row
 * Tile 1: track surface — all pixels color index 1 (light gray / road)
 *         2bpp: low=0xFF, high=0x00 per row
 */
static const uint8_t track_tile_data[] = {
    /* Tile 0: off-track (color 2) */
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    /* Tile 1: track surface (color 1) */
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
    0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00
};

/*
 * 20x18 tile map. 0 = off-track, 1 = track.
 * Oval ring ~4 tiles wide; player (8x8 = 1 tile) fits with room to move.
 */
static const uint8_t track_map[18 * 20] = {
    /* row 0  */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 1  */ 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,
    /* row 2  */ 0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,
    /* row 3  */ 0,0,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,0,0,
    /* row 4  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 5  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 6  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 7  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 8  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 9  */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 10 */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 11 */ 0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,
    /* row 12 */ 0,0,1,1,1,1,0,0,0,0,0,0,0,0,1,1,1,1,0,0,
    /* row 13 */ 0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,
    /* row 14 */ 0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,
    /* row 15 */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 16 */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    /* row 17 */ 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
};

void track_init(void) {
    set_bkg_data(0, 2, track_tile_data);
    set_bkg_tiles(0, 0, 20, 18, track_map);
    SHOW_BKG;
}

uint8_t track_passable(uint8_t screen_x, uint8_t screen_y) {
    uint8_t tx = screen_x / 8u;
    uint8_t ty = screen_y / 8u;
    if (tx >= 20u || ty >= 18u) return 0u;
    return track_map[ty * 20u + tx] != 0u;
}
