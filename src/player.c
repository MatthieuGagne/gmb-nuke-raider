#include <gb/gb.h>
#include "player.h"
#include "track.h"

/* Solid 8x8 tile: all pixels color index 3 (GBDK 2bpp planar: low plane | high plane per row) */
static const uint8_t player_tile_data[] = {
    0xFF, 0xFF,   /* row 0 */
    0xFF, 0xFF,   /* row 1 */
    0xFF, 0xFF,   /* row 2 */
    0xFF, 0xFF,   /* row 3 */
    0xFF, 0xFF,   /* row 4 */
    0xFF, 0xFF,   /* row 5 */
    0xFF, 0xFF,   /* row 6 */
    0xFF, 0xFF    /* row 7 */
};

/* Screen bounds — GB sprite hardware: x+8 offset, y+16 offset */
#define PX_MIN  8u
#define PX_MAX  160u  /* sprite right edge at screen x=159: (160-8)+7=159 */
#define PY_MIN  16u
#define PY_MAX  152u  /* sprite bottom edge at screen y=143: (152-16)+7=143 */

#define PLAYER_START_X  88u   /* on track: screen (80,108) = tile (10,13) */
#define PLAYER_START_Y  124u

static uint8_t px;
static uint8_t py;

/* Returns 1 if all 4 corners of a sprite at (hw_px, hw_py) are on driveable track */
static uint8_t corners_passable(uint8_t hw_px, uint8_t hw_py) {
    uint8_t sx = (uint8_t)(hw_px - 8u);
    uint8_t sy = (uint8_t)(hw_py - 16u);
    return track_passable(sx, sy) &&
           track_passable((uint8_t)(sx + 7u), sy) &&
           track_passable(sx, (uint8_t)(sy + 7u)) &&
           track_passable((uint8_t)(sx + 7u), (uint8_t)(sy + 7u));
}

void player_init(void) {
    SPRITES_8x8;
    set_sprite_data(0, 1, player_tile_data);
    set_sprite_tile(0, 0);
    px = PLAYER_START_X;
    py = PLAYER_START_Y;
    SHOW_SPRITES;
}

void player_update(uint8_t input) {
    if (input & J_LEFT) {
        uint8_t new_px = clamp_u8((uint8_t)(px - 1u), PX_MIN, PX_MAX);
        if (corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_RIGHT) {
        uint8_t new_px = clamp_u8((uint8_t)(px + 1u), PX_MIN, PX_MAX);
        if (corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_UP) {
        uint8_t new_py = clamp_u8((uint8_t)(py - 1u), PY_MIN, PY_MAX);
        if (corners_passable(px, new_py)) py = new_py;
    }
    if (input & J_DOWN) {
        uint8_t new_py = clamp_u8((uint8_t)(py + 1u), PY_MIN, PY_MAX);
        if (corners_passable(px, new_py)) py = new_py;
    }
}

void player_render(void) {
    move_sprite(0, px, py);
}

void player_set_pos(uint8_t x, uint8_t y) {
    px = x;
    py = y;
}

uint8_t player_get_x(void) { return px; }
uint8_t player_get_y(void) { return py; }
