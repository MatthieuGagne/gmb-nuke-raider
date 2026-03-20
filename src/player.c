#pragma bank 255
#include <gb/gb.h>
#include "input.h"
#include "player.h"
#include "banking.h"
#include "track.h"
#include "camera.h"
#include "loader.h"
#include "sprite_pool.h"
#include "config.h"

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


void player_init(void) BANKED {
    SPRITES_8x8;
    sprite_pool_init();
    player_sprite_slot     = get_sprite();  /* OAM slot for top half    */
    player_sprite_slot_bot = get_sprite();  /* OAM slot for bottom half */
    load_player_tiles();
    set_sprite_tile(player_sprite_slot,     0); /* top    half = tile 0 */
    set_sprite_tile(player_sprite_slot_bot, 1); /* bottom half = tile 1 */
    load_track_start_pos(&px, &py);
    vx = 0;
    vy = 0;
    SHOW_SPRITES;
}

void player_update(void) BANKED {
    int16_t new_px;
    int16_t new_py;
    TileType terrain;

    /* Query terrain at player centre (4px = centre of 8-wide hitbox) */
    terrain = track_tile_type((int16_t)(px + 4), (int16_t)(py + 4));
    player_apply_physics(input, terrain);

    /* Apply X velocity — zero on wall/edge collision */
    new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 && new_px <= 159 && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        vx = 0;
    }

    /* Apply Y velocity — zero on wall/edge collision */
    new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= (int16_t)cam_y && new_py <= (int16_t)(cam_y + (HUD_SCANLINE - 16u)) && corners_passable(px, new_py)) {
        py = new_py;
    } else {
        vy = 0;
    }
}

void player_render(void) BANKED {
    /* cam_x is always 0; cam_y is uint16_t but py >= cam_y is enforced so offset fits uint8_t */
    uint8_t hw_x = (uint8_t)(px + 8);
    uint8_t hw_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 16);
    move_sprite(player_sprite_slot,     hw_x, hw_y);
    move_sprite(player_sprite_slot_bot, hw_x, (uint8_t)(hw_y + 8u));

}

void player_set_pos(int16_t x, int16_t y) BANKED {
    px = x;
    py = y;
}

int16_t player_get_x(void) BANKED  { return px; }
int16_t player_get_y(void) BANKED  { return py; }
int8_t  player_get_vx(void) BANKED { return vx; }
int8_t  player_get_vy(void) BANKED { return vy; }

void player_reset_vel(void) BANKED {
    vx = 0;
    vy = 0;
}

void player_apply_physics(uint8_t buttons, TileType terrain) BANKED {
    uint8_t i;
    uint8_t fric_x;
    uint8_t fric_y;

    /* Step 1: determine friction */
    if (terrain == TILE_SAND) {
        fric_x = (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = fric_x;
    } else if (terrain == TILE_OIL) {
        fric_x = 0;
        fric_y = 0;
    } else {
        /* Road / Boost: friction only on unpressed axis */
        fric_x = (buttons & (J_LEFT | J_RIGHT)) ? 0u : (uint8_t)PLAYER_FRICTION;
        fric_y = (buttons & (J_UP   | J_DOWN))  ? 0u : (uint8_t)PLAYER_FRICTION;
    }

    /* Step 2: apply X friction */
    for (i = 0; i < fric_x; i++) {
        if      (vx > 0) vx = (int8_t)(vx - 1);
        else if (vx < 0) vx = (int8_t)(vx + 1);
    }

    /* Step 3: apply Y friction */
    for (i = 0; i < fric_y; i++) {
        if      (vy > 0) vy = (int8_t)(vy - 1);
        else if (vy < 0) vy = (int8_t)(vy + 1);
    }

    /* Step 4: input acceleration (disabled on oil) */
    if (terrain != TILE_OIL) {
        if (buttons & J_LEFT)  vx = (int8_t)(vx - (int8_t)PLAYER_ACCEL);
        if (buttons & J_RIGHT) vx = (int8_t)(vx + (int8_t)PLAYER_ACCEL);
        if (buttons & J_UP)    vy = (int8_t)(vy - (int8_t)PLAYER_ACCEL);
        if (buttons & J_DOWN)  vy = (int8_t)(vy + (int8_t)PLAYER_ACCEL);
    }

    /* Step 5: boost kick (upward = negative vy) */
    if (terrain == TILE_BOOST) {
        vy = (int8_t)(vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    /* Step 6: clamp vx; clamp vy with boost-aware cap */
    {
        uint8_t max_vy = (terrain == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : PLAYER_MAX_SPEED;
        if (vx >  (int8_t)PLAYER_MAX_SPEED) vx =  (int8_t)PLAYER_MAX_SPEED;
        if (vx < -(int8_t)PLAYER_MAX_SPEED) vx = -(int8_t)PLAYER_MAX_SPEED;
        if (vy >  (int8_t)max_vy) vy =  (int8_t)max_vy;
        if (vy < -(int8_t)max_vy) vy = -(int8_t)max_vy;
    }
}
