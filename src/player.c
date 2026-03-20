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
static int8_t  facing_dx;          /* -1=left,  0=none, +1=right */
static int8_t  facing_dy;          /* -1=up,    0=none, +1=down  */
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
    facing_dx = 0;
    facing_dy = -1;    /* default: facing up (natural racing direction) */
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
    uint8_t stopped;

    /* Step 1: capture stopped state BEFORE friction alters velocity */
    stopped = (vx == 0 && vy == 0) ? 1u : 0u;

    /* Step 2: D-pad updates facing direction only — no direct thrust */
    if (buttons & J_LEFT)  { facing_dx = -1; facing_dy =  0; }
    if (buttons & J_RIGHT) { facing_dx =  1; facing_dy =  0; }
    if (buttons & J_UP)    { facing_dx =  0; facing_dy = -1; }
    if (buttons & J_DOWN)  { facing_dx =  0; facing_dy =  1; }

    /* Step 3: determine coast friction */
    if (terrain == TILE_SAND) {
        fric_x = (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = fric_x;
    } else if (terrain == TILE_OIL) {
        fric_x = 0;
        fric_y = 0;
    } else {
        /* Road / Boost: always apply coast friction on both axes */
        fric_x = (uint8_t)PLAYER_FRICTION;
        fric_y = (uint8_t)PLAYER_FRICTION;
    }

    /* Step 4: apply coast friction */
    for (i = 0; i < fric_x; i++) {
        if      (vx > 0) vx = (int8_t)(vx - 1);
        else if (vx < 0) vx = (int8_t)(vx + 1);
    }
    for (i = 0; i < fric_y; i++) {
        if      (vy > 0) vy = (int8_t)(vy - 1);
        else if (vy < 0) vy = (int8_t)(vy + 1);
    }

    /* Step 5: gas — A button accelerates in facing direction (disabled on oil) */
    if ((buttons & J_A) && terrain != TILE_OIL) {
        vx = (int8_t)(vx + facing_dx * (int8_t)PLAYER_ACCEL);
        vy = (int8_t)(vy + facing_dy * (int8_t)PLAYER_ACCEL);
    }

    /* Step 6: brake / reverse — B button */
    if (buttons & J_B) {
        if (!stopped) {
            /* Braking: extra friction pass (faster than coasting) */
            for (i = 0; i < PLAYER_FRICTION; i++) {
                if      (vx > 0) vx = (int8_t)(vx - 1);
                else if (vx < 0) vx = (int8_t)(vx + 1);
            }
            for (i = 0; i < PLAYER_FRICTION; i++) {
                if      (vy > 0) vy = (int8_t)(vy - 1);
                else if (vy < 0) vy = (int8_t)(vy + 1);
            }
        } else if (terrain != TILE_OIL) {
            /* Reverse: thrust opposite to facing, capped at PLAYER_REVERSE_MAX_SPEED */
            vx = (int8_t)(vx - facing_dx * (int8_t)PLAYER_ACCEL);
            vy = (int8_t)(vy - facing_dy * (int8_t)PLAYER_ACCEL);
            if (facing_dx > 0 && vx < -(int8_t)PLAYER_REVERSE_MAX_SPEED)
                vx = -(int8_t)PLAYER_REVERSE_MAX_SPEED;
            if (facing_dx < 0 && vx >  (int8_t)PLAYER_REVERSE_MAX_SPEED)
                vx =  (int8_t)PLAYER_REVERSE_MAX_SPEED;
            if (facing_dy > 0 && vy < -(int8_t)PLAYER_REVERSE_MAX_SPEED)
                vy = -(int8_t)PLAYER_REVERSE_MAX_SPEED;
            if (facing_dy < 0 && vy >  (int8_t)PLAYER_REVERSE_MAX_SPEED)
                vy =  (int8_t)PLAYER_REVERSE_MAX_SPEED;
        }
    }

    /* Step 7: boost kick (upward = negative vy) */
    if (terrain == TILE_BOOST) {
        vy = (int8_t)(vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    /* Step 8: clamp to max speed */
    {
        uint8_t max_vy = (terrain == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : PLAYER_MAX_SPEED;
        if (vx >  (int8_t)PLAYER_MAX_SPEED) vx =  (int8_t)PLAYER_MAX_SPEED;
        if (vx < -(int8_t)PLAYER_MAX_SPEED) vx = -(int8_t)PLAYER_MAX_SPEED;
        if (vy >  (int8_t)max_vy) vy =  (int8_t)max_vy;
        if (vy < -(int8_t)max_vy) vy = -(int8_t)max_vy;
    }
}
