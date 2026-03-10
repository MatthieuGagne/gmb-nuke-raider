#include <gb/gb.h>
#include "input.h"
#include "player.h"
#include "track.h"
#include "camera.h"
#include "debug.h"
#include "sprite_pool.h"
#include "config.h"

extern const uint8_t player_tile_data[];
extern const uint8_t player_tile_data_count;

static int16_t px;
static int16_t py;
static int8_t  vx;
static int8_t  vy;
static uint8_t player_sprite_slot     = 0;
static uint8_t player_sprite_slot_bot = 0;

/* Returns 1 if all 4 corners of a player at world (wx, wy) are on track. */
static uint8_t corners_passable(int16_t wx, int16_t wy) {
    return track_passable(wx,       wy) &&
           track_passable(wx + 7,   wy) &&
           track_passable(wx,       wy + 7) &&
           track_passable(wx + 7,   wy + 7);
}


void player_init(void) {
    SPRITES_8x8;
    sprite_pool_init();
    player_sprite_slot     = get_sprite();  /* OAM slot for top half    */
    player_sprite_slot_bot = get_sprite();  /* OAM slot for bottom half */
    set_sprite_data(0, 2, player_tile_data); /* load 2 tiles (32 bytes)  */
    set_sprite_tile(player_sprite_slot,     0); /* top    half = tile 0 */
    set_sprite_tile(player_sprite_slot_bot, 1); /* bottom half = tile 1 */
    px = track_start_x;
    py = track_start_y;
    vx = 0;
    vy = 0;
    SHOW_SPRITES;
}

void player_update(void) {
    int16_t new_px;
    int16_t new_py;

    /* --- X axis: accelerate, decelerate, or apply friction --- */
    if (KEY_PRESSED(J_RIGHT)) {
        vx = (vx + PLAYER_ACCEL > PLAYER_MAX_SPEED) ? PLAYER_MAX_SPEED : (int8_t)(vx + PLAYER_ACCEL);
    } else if (KEY_PRESSED(J_LEFT)) {
        vx = (vx - PLAYER_ACCEL < -PLAYER_MAX_SPEED) ? -PLAYER_MAX_SPEED : (int8_t)(vx - PLAYER_ACCEL);
    } else if (vx > 0) {
        vx = (int8_t)(vx - PLAYER_FRICTION);
        if (vx < 0) vx = 0;
    } else if (vx < 0) {
        vx = (int8_t)(vx + PLAYER_FRICTION);
        if (vx > 0) vx = 0;
    }

    /* --- Y axis: accelerate, decelerate, or apply friction --- */
    if (KEY_PRESSED(J_DOWN)) {
        vy = (vy + PLAYER_ACCEL > PLAYER_MAX_SPEED) ? PLAYER_MAX_SPEED : (int8_t)(vy + PLAYER_ACCEL);
    } else if (KEY_PRESSED(J_UP)) {
        vy = (vy - PLAYER_ACCEL < -PLAYER_MAX_SPEED) ? -PLAYER_MAX_SPEED : (int8_t)(vy - PLAYER_ACCEL);
    } else if (vy > 0) {
        vy = (int8_t)(vy - PLAYER_FRICTION);
        if (vy < 0) vy = 0;
    } else if (vy < 0) {
        vy = (int8_t)(vy + PLAYER_FRICTION);
        if (vy > 0) vy = 0;
    }

    /* --- Apply X velocity; zero on wall or screen-edge collision --- */
    new_px = px + vx;
    if (new_px >= 0 && new_px <= 159 && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        vx = 0;
    }

    /* --- Apply Y velocity; zero on wall or screen-edge collision --- */
    new_py = py + vy;
    if (new_py >= (int16_t)cam_y && new_py <= (int16_t)(cam_y + (HUD_SCANLINE - 16u)) && corners_passable(px, new_py)) {
        py = new_py;
    } else {
        vy = 0;
    }
}

void player_render(void) {
    /* cam_x is always 0; cam_y is uint16_t but py >= cam_y is enforced so offset fits uint8_t */
    uint8_t hw_x = (uint8_t)(px + 8);
    uint8_t hw_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 16);
    move_sprite(player_sprite_slot,     hw_x, hw_y);
    move_sprite(player_sprite_slot_bot, hw_x, (uint8_t)(hw_y + 8u));
    /* Log when sprite is near or outside visible bounds */
    if (hw_x < 8u || hw_x > 167u || hw_y < 16u || hw_y > 159u) {
        DBG_INT("hw_x_oob", hw_x);
        DBG_INT("hw_y_oob", hw_y);
    }
}

void player_set_pos(int16_t x, int16_t y) {
    px = x;
    py = y;
}

int16_t player_get_x(void)  { return px; }
int16_t player_get_y(void)  { return py; }
int8_t  player_get_vx(void) { return vx; }
int8_t  player_get_vy(void) { return vy; }
