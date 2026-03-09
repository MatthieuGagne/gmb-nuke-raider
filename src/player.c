#include <gb/gb.h>
#include "player.h"

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
#define PX_MAX  167u
#define PY_MIN  16u
#define PY_MAX  159u

#define PLAYER_START_X  80u
#define PLAYER_START_Y  72u

static uint8_t px;
static uint8_t py;

void player_init(void) {
    SPRITES_8x8;
    set_sprite_data(0, 1, player_tile_data);
    set_sprite_tile(0, 0);
    px = PLAYER_START_X;
    py = PLAYER_START_Y;
    SHOW_SPRITES;
}

void player_update(uint8_t input) {
    if (input & J_LEFT)  px = clamp_u8((uint8_t)(px - 1u), PX_MIN, PX_MAX);
    if (input & J_RIGHT) px = clamp_u8((uint8_t)(px + 1u), PX_MIN, PX_MAX);
    if (input & J_UP)    py = clamp_u8((uint8_t)(py - 1u), PY_MIN, PY_MAX);
    if (input & J_DOWN)  py = clamp_u8((uint8_t)(py + 1u), PY_MIN, PY_MAX);
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
