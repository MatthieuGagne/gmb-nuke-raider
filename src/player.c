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
#include "damage.h"
#include "projectile.h"

static int16_t px;
static int16_t py;
static int8_t  vx;
static int8_t  vy;
static uint8_t player_sprite_slot     = 0;
static uint8_t player_sprite_slot_bot = 0;
static uint8_t player_flicker_tick;
static player_dir_t player_dir = DIR_T;  /* current facing, init to north */

/* Direction → velocity delta tables. Indexed by player_dir_t (0=T..7=LT).
 * Values are multiplied by PLAYER_ACCEL at application time. */
static const int8_t DIR_DX[8] = {  0,  1,  1,  1,  0, -1, -1, -1 };
static const int8_t DIR_DY[8] = { -1, -1,  0,  1,  1,  1,  0, -1 };

/* Sprite tile top-half index per direction. Bot-half = top+1.
 * Left directions (LB, L, LT) reuse the mirrored right-side tile with S_FLIPX. */
static const uint8_t DIR_TILE_TOP[8] = {
    PLAYER_TILE_T,   /* T  */
    PLAYER_TILE_RT,  /* RT */
    PLAYER_TILE_R,   /* R  */
    PLAYER_TILE_RB,  /* RB */
    PLAYER_TILE_T,   /* B  → same tiles as T */
    PLAYER_TILE_RB,  /* LB → RB + FLIPX */
    PLAYER_TILE_R,   /* L  → R  + FLIPX */
    PLAYER_TILE_RT,  /* LT → RT + FLIPX */
};

static const uint8_t DIR_FLIPX[8] = { 0, 0, 0, 0, 0, 1, 1, 1 };

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
    player_dir = DIR_T;
    player_flicker_tick = 0u;
    SHOW_SPRITES;
}

void player_update(void) BANKED {
    int16_t new_px;
    int16_t new_py;
    TileType terrain;

    damage_tick();   /* decrement invincibility cooldown each frame */

    /* Query terrain at player centre (4px = centre of 8-wide hitbox) */
    terrain = track_tile_type((int16_t)(px + 4), (int16_t)(py + 4));
    player_apply_physics(input, terrain);

    /* Fire machine gun on Select (held + cooldown managed inside projectile module) */
    if (KEY_PRESSED(J_A)) {
        uint8_t scr_x = (uint8_t)((int16_t)px + 8);
        uint8_t scr_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 16);
        projectile_fire(scr_x, scr_y, player_dir);
    }

    /* Apply X velocity — zero on wall/edge collision */
    new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 && new_px <= 159 && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        vx = 0;
        damage_apply(1u);
    }

    /* Apply Y velocity — zero on wall/edge collision */
    new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= (int16_t)cam_y && new_py <= (int16_t)(cam_y + (HUD_SCANLINE - 16u)) && corners_passable(px, new_py)) {
        py = new_py;
    } else {
        vy = 0;
        damage_apply(1u);
    }

    /* Repair tile: heal HP when standing on a repair pad */
    if (terrain == TILE_REPAIR) {
        damage_heal(DAMAGE_REPAIR_AMOUNT);
    }
}

void player_render(void) BANKED {
    uint8_t hw_x    = (uint8_t)(px + 8u);
    uint8_t hw_y    = (uint8_t)((int16_t)py - (int16_t)cam_y + 16);
    uint8_t tile_top = DIR_TILE_TOP[player_dir];
    uint8_t flip     = DIR_FLIPX[player_dir] ? S_FLIPX : 0u;

    set_sprite_tile(player_sprite_slot,     tile_top);
    set_sprite_tile(player_sprite_slot_bot, (uint8_t)(tile_top + 1u));
    set_sprite_prop(player_sprite_slot,     flip);
    set_sprite_prop(player_sprite_slot_bot, flip);

    player_flicker_tick++;
    if (damage_get_hp() <= 2u && (player_flicker_tick & 8u)) {
        move_sprite(player_sprite_slot,     0u, 0u);
        move_sprite(player_sprite_slot_bot, 0u, 0u);
    } else {
        move_sprite(player_sprite_slot,     hw_x, hw_y);
        move_sprite(player_sprite_slot_bot, hw_x, (uint8_t)(hw_y + 8u));
    }
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

/* Decode 8-directional facing from D-pad buttons.
 * Diagonal combos take priority over cardinals.
 * If no D-pad button is held, the last direction is preserved. */
static player_dir_t decode_dir(uint8_t buttons) {
    uint8_t up    = (buttons & J_UP)    ? 1u : 0u;
    uint8_t down  = (buttons & J_DOWN)  ? 1u : 0u;
    uint8_t left  = (buttons & J_LEFT)  ? 1u : 0u;
    uint8_t right = (buttons & J_RIGHT) ? 1u : 0u;
    if (up   && right) return DIR_RT;
    if (down && right) return DIR_RB;
    if (down && left)  return DIR_LB;
    if (up   && left)  return DIR_LT;
    if (up)    return DIR_T;
    if (right) return DIR_R;
    if (down)  return DIR_B;
    if (left)  return DIR_L;
    return player_dir;  /* no dpad: keep previous direction */
}

player_dir_t player_get_dir(void) BANKED { return player_dir; }
int8_t player_dir_dx(player_dir_t dir) BANKED { return DIR_DX[dir]; }
int8_t player_dir_dy(player_dir_t dir) BANKED { return DIR_DY[dir]; }

void player_apply_physics(uint8_t buttons, TileType terrain) BANKED {
    uint8_t i;
    uint8_t fric_x;
    uint8_t fric_y;
    uint8_t gas;

    /* Step 1: decode facing direction from D-pad */
    player_dir = decode_dir(buttons);

    /* Step 2: any D-pad button held = gas (disabled on oil) */
    gas = (terrain != TILE_OIL && (buttons & (J_UP | J_DOWN | J_LEFT | J_RIGHT))) ? 1u : 0u;

    /* Step 3: coast friction per axis.
     * Friction is suppressed on an axis when gas is being applied along it. */
    if (terrain == TILE_SAND) {
        fric_x = (gas && DIR_DX[player_dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = (gas && DIR_DY[player_dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
    } else if (terrain == TILE_OIL) {
        fric_x = 0u;
        fric_y = 0u;
    } else {
        fric_x = (gas && DIR_DX[player_dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
        fric_y = (gas && DIR_DY[player_dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
    }

    /* Step 4: apply X coast friction */
    for (i = 0u; i < fric_x; i++) {
        if      (vx > 0) vx = (int8_t)(vx - 1);
        else if (vx < 0) vx = (int8_t)(vx + 1);
    }

    /* Step 5: apply Y coast friction */
    for (i = 0u; i < fric_y; i++) {
        if      (vy > 0) vy = (int8_t)(vy - 1);
        else if (vy < 0) vy = (int8_t)(vy + 1);
    }

    /* Step 6: apply gas vector — direction lookup table */
    if (gas) {
        vx = (int8_t)(vx + (int8_t)((int8_t)PLAYER_ACCEL * DIR_DX[player_dir]));
        vy = (int8_t)(vy + (int8_t)((int8_t)PLAYER_ACCEL * DIR_DY[player_dir]));
    }

    /* Step 7: boost kick (upward = negative vy) */
    if (terrain == TILE_BOOST) {
        vy = (int8_t)(vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    /* Step 8: clamp to max speed */
    {
        uint8_t max_speed = (terrain == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : PLAYER_MAX_SPEED;
        if (vx >  (int8_t)max_speed) vx =  (int8_t)max_speed;
        if (vx < -(int8_t)max_speed) vx = -(int8_t)max_speed;
        if (vy >  (int8_t)max_speed) vy =  (int8_t)max_speed;
        if (vy < -(int8_t)max_speed) vy = -(int8_t)max_speed;
    }
}
