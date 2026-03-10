#include <gb/gb.h>
#include "player.h"
#include "track.h"
#include "camera.h"
#include "debug.h"

/* Solid 8x8 sprite: all pixels color index 3 */
static const uint8_t player_tile_data[] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
};

/* Player start: center of initial viewport, on road (tile col 10, row 10) */
#define PLAYER_START_X  80
#define PLAYER_START_Y  80

static int16_t px;
static int16_t py;

/* Returns 1 if all 4 corners of a player at world (wx, wy) are on track. */
static uint8_t corners_passable(int16_t wx, int16_t wy) {
    return track_passable(wx,       wy) &&
           track_passable(wx + 7,   wy) &&
           track_passable(wx,       wy + 7) &&
           track_passable(wx + 7,   wy + 7);
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
    int16_t new_px;
    int16_t new_py;
    if (input & J_LEFT) {
        new_px = px - 1;
        if (new_px >= 0 && corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_RIGHT) {
        new_px = px + 1;
        if (new_px <= 159 && corners_passable(new_px, py)) px = new_px;
    }
    if (input & J_UP) {
        new_py = py - 1;
        if (new_py >= (int16_t)cam_y && corners_passable(px, new_py)) py = new_py;
    }
    if (input & J_DOWN) {
        new_py = py + 1;
        if (new_py <= (int16_t)(cam_y + 143u) && corners_passable(px, new_py)) py = new_py;
    }
}

void player_render(void) {
    /* cam_x is always 0; cam_y is uint16_t but py >= cam_y is enforced so offset fits uint8_t */
    uint8_t hw_x = (uint8_t)(px + 8);
    uint8_t hw_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 16);
    move_sprite(0, hw_x, hw_y);
    /* Log when sprite is near or outside visible bounds (x<8 or x>167, y<16 or y>159) */
    if (hw_x < 8u || hw_x > 167u || hw_y < 16u || hw_y > 159u) {
        DBG_INT("hw_x_oob", hw_x);
        DBG_INT("hw_y_oob", hw_y);
    }
}

void player_set_pos(int16_t x, int16_t y) {
    px = x;
    py = y;
}

int16_t player_get_x(void) { return px; }
int16_t player_get_y(void) { return py; }
