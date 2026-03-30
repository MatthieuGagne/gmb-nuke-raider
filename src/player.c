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
#include "sfx.h"

static int16_t px;
static int16_t py;
static int8_t  vx;
static int8_t  vy;
static uint8_t player_sprite_slot[4];  /* 0=TL, 1=BL, 2=TR, 3=BR */
static uint8_t player_flicker_tick;
static player_dir_t player_dir = DIR_T;

/* Direction → velocity delta tables. Indexed by player_dir_t (0=T..7=LT). */
static const int8_t DIR_DX[8] = {  0,  1,  1,  1,  0, -1, -1, -1 };
static const int8_t DIR_DY[8] = { -1, -1,  0,  1,  1,  1,  0, -1 };

/* Direction → tile index for each 2×2 OAM position.
 * Derived directions use col-swap (FLIPX) or row-swap (FLIPY).
 * Tile layout per 16×16 set: base+0=TL, base+1=BL, base+2=TR, base+3=BR. */
static const uint8_t DIR_TILE_TL[8] = {
    PLAYER_TILE_UP_BASE        + 0u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 0u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 0u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 0u, /* RB */
    PLAYER_TILE_UP_BASE        + 1u, /* B  = UP FLIPY+row-swap → TL gets UP BL */
    PLAYER_TILE_DOWNRIGHT_BASE + 2u, /* LB = DR FLIPX+col-swap → TL gets DR TR */
    PLAYER_TILE_RIGHT_BASE     + 2u, /* L  = R  FLIPX+col-swap → TL gets R  TR */
    PLAYER_TILE_UPRIGHT_BASE   + 2u, /* LT = UR FLIPX+col-swap → TL gets UR TR */
};
static const uint8_t DIR_TILE_BL[8] = {
    PLAYER_TILE_UP_BASE        + 1u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 1u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 1u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 1u, /* RB */
    PLAYER_TILE_UP_BASE        + 0u, /* B  → BL gets UP TL */
    PLAYER_TILE_DOWNRIGHT_BASE + 3u, /* LB → BL gets DR BR */
    PLAYER_TILE_RIGHT_BASE     + 3u, /* L  → BL gets R  BR */
    PLAYER_TILE_UPRIGHT_BASE   + 3u, /* LT → BL gets UR BR */
};
static const uint8_t DIR_TILE_TR[8] = {
    PLAYER_TILE_UP_BASE        + 2u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 2u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 2u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 2u, /* RB */
    PLAYER_TILE_UP_BASE        + 3u, /* B  → TR gets UP BR */
    PLAYER_TILE_DOWNRIGHT_BASE + 0u, /* LB → TR gets DR TL */
    PLAYER_TILE_RIGHT_BASE     + 0u, /* L  → TR gets R  TL */
    PLAYER_TILE_UPRIGHT_BASE   + 0u, /* LT → TR gets UR TL */
};
static const uint8_t DIR_TILE_BR[8] = {
    PLAYER_TILE_UP_BASE        + 3u, /* T  */
    PLAYER_TILE_UPRIGHT_BASE   + 3u, /* RT */
    PLAYER_TILE_RIGHT_BASE     + 3u, /* R  */
    PLAYER_TILE_DOWNRIGHT_BASE + 3u, /* RB */
    PLAYER_TILE_UP_BASE        + 2u, /* B  → BR gets UP TR */
    PLAYER_TILE_DOWNRIGHT_BASE + 1u, /* LB → BR gets DR BL */
    PLAYER_TILE_RIGHT_BASE     + 1u, /* L  → BR gets R  BL */
    PLAYER_TILE_UPRIGHT_BASE   + 1u, /* LT → BR gets UR BL */
};
static const uint8_t DIR_FLIP[8] = {
    0u,      /* T  */
    0u,      /* RT */
    0u,      /* R  */
    0u,      /* RB */
    S_FLIPY, /* B  */
    S_FLIPX, /* LB */
    S_FLIPX, /* L  */
    S_FLIPX, /* LT */
};
/* Returns 1 if all 4 corners of the 16×16 hitbox at (wx, wy) are on track. */
static uint8_t corners_passable(int16_t wx, int16_t wy) {
    return track_passable(wx,        wy) &&
           track_passable(wx + 15,   wy) &&
           track_passable(wx,        wy + 15) &&
           track_passable(wx + 15,   wy + 15);
}

void player_init(void) BANKED {
    SPRITES_8x8;
    sprite_pool_init();
    player_sprite_slot[0] = get_sprite();  /* TL */
    player_sprite_slot[1] = get_sprite();  /* BL */
    player_sprite_slot[2] = get_sprite();  /* TR */
    player_sprite_slot[3] = get_sprite();  /* BR */
    load_player_tiles();
    set_sprite_tile(player_sprite_slot[0], PLAYER_TILE_UP_BASE + 0u);
    set_sprite_tile(player_sprite_slot[1], PLAYER_TILE_UP_BASE + 1u);
    set_sprite_tile(player_sprite_slot[2], PLAYER_TILE_UP_BASE + 2u);
    set_sprite_tile(player_sprite_slot[3], PLAYER_TILE_UP_BASE + 3u);
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

    damage_tick();

    /* Query terrain at 16×16 centre */
    terrain = track_tile_type((int16_t)(px + 8), (int16_t)(py + 8));
    player_apply_physics(input, terrain);

    /* Fire machine gun on A (held + cooldown managed inside projectile module).
     * sfx_play(SFX_SHOOT) is called inside projectile_fire() — only fires when a
     * projectile actually spawns (every PROJ_FIRE_COOLDOWN frames), not every frame. */
    if (KEY_PRESSED(J_A)) {
        uint8_t scr_x = (uint8_t)(px + 16);
        uint8_t scr_y = (uint8_t)(py - cam_y + 24);
        projectile_fire(scr_x, scr_y, player_dir, PROJ_OWNER_PLAYER);
    }

    /* Apply X velocity — zero on wall/edge collision.
     * SFX_HIT targets CH4; SFX_SHOOT (in projectile_fire) also targets CH4.
     * Same-frame contention: last caller wins — HIT overwrites SHOOT if both fire. */
    new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 && new_px <= 144 && corners_passable(new_px, py)) {
        px = new_px;
    } else {
        vx = 0;
        damage_apply(1u);
        sfx_play(SFX_HIT);
    }

    /* Apply Y velocity — Y clamp: [0, MAP_PX_H - 16] */
    new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= 0 && new_py <= (int16_t)(MAP_PX_H - 16u) && corners_passable(px, new_py)) {
        py = new_py;
    } else {
        vy = 0;
        damage_apply(1u);
        sfx_play(SFX_HIT);
    }

    /* Repair tile: heal HP when standing on a repair pad.
     * SFX_HEAL plays only on the transition frame entering the tile — re-triggering
     * every frame would restart the CH1 sweep unit and kill the rising arc effect. */
    {
        static uint8_t prev_on_repair = 0u;
        if (terrain == TILE_REPAIR) {
            damage_heal(DAMAGE_REPAIR_AMOUNT);
            if (!prev_on_repair) {
                sfx_play(SFX_HEAL);
            }
            prev_on_repair = 1u;
        } else {
            prev_on_repair = 0u;
        }
    }
}

void player_render(void) BANKED {
    uint8_t hw_x = (uint8_t)(px + 8u);
    uint8_t hw_y = (uint8_t)(py - cam_y + 16);
    uint8_t flip = DIR_FLIP[player_dir];

    set_sprite_tile(player_sprite_slot[0], DIR_TILE_TL[player_dir]);
    set_sprite_tile(player_sprite_slot[1], DIR_TILE_BL[player_dir]);
    set_sprite_tile(player_sprite_slot[2], DIR_TILE_TR[player_dir]);
    set_sprite_tile(player_sprite_slot[3], DIR_TILE_BR[player_dir]);
    set_sprite_prop(player_sprite_slot[0], flip);
    set_sprite_prop(player_sprite_slot[1], flip);
    set_sprite_prop(player_sprite_slot[2], flip);
    set_sprite_prop(player_sprite_slot[3], flip);

    player_flicker_tick++;
    if (damage_get_hp() <= 20u && (player_flicker_tick & 8u)) {
        move_sprite(player_sprite_slot[0], 0u, 0u);
        move_sprite(player_sprite_slot[1], 0u, 0u);
        move_sprite(player_sprite_slot[2], 0u, 0u);
        move_sprite(player_sprite_slot[3], 0u, 0u);
    } else {
        move_sprite(player_sprite_slot[0], hw_x,                     hw_y);
        move_sprite(player_sprite_slot[1], hw_x,                     (uint8_t)(hw_y + 8u));
        move_sprite(player_sprite_slot[2], (uint8_t)(hw_x + 8u),     hw_y);
        move_sprite(player_sprite_slot[3], (uint8_t)(hw_x + 8u),     (uint8_t)(hw_y + 8u));
    }
}

void player_set_pos(int16_t x, int16_t y) BANKED { px = x; py = y; }
int16_t player_get_x(void) BANKED  { return px; }
int16_t player_get_y(void) BANKED  { return py; }
int8_t  player_get_vx(void) BANKED { return vx; }
int8_t  player_get_vy(void) BANKED { return vy; }

void player_reset_vel(void) BANKED { vx = 0; vy = 0; }

static player_dir_t decode_dir(uint8_t buttons) {
    if ((buttons & J_UP)   && (buttons & J_RIGHT)) return DIR_RT;
    if ((buttons & J_DOWN) && (buttons & J_RIGHT)) return DIR_RB;
    if ((buttons & J_DOWN) && (buttons & J_LEFT))  return DIR_LB;
    if ((buttons & J_UP)   && (buttons & J_LEFT))  return DIR_LT;
    if (buttons & J_UP)    return DIR_T;
    if (buttons & J_RIGHT) return DIR_R;
    if (buttons & J_DOWN)  return DIR_B;
    if (buttons & J_LEFT)  return DIR_L;
    return player_dir;
}

player_dir_t player_get_dir(void) BANKED { return player_dir; }
int8_t player_dir_dx(player_dir_t dir) BANKED { return DIR_DX[dir]; }
int8_t player_dir_dy(player_dir_t dir) BANKED { return DIR_DY[dir]; }

void player_apply_physics(uint8_t buttons, TileType terrain) BANKED {
    uint8_t i;
    uint8_t fric_x;
    uint8_t fric_y;
    uint8_t gas;

    player_dir = decode_dir(buttons);
    gas = (terrain != TILE_OIL && (buttons & (J_UP | J_DOWN | J_LEFT | J_RIGHT))) ? 1u : 0u;

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

    for (i = 0u; i < fric_x; i++) {
        if      (vx > 0) vx = (int8_t)(vx - 1);
        else if (vx < 0) vx = (int8_t)(vx + 1);
    }
    for (i = 0u; i < fric_y; i++) {
        if      (vy > 0) vy = (int8_t)(vy - 1);
        else if (vy < 0) vy = (int8_t)(vy + 1);
    }

    if (gas) {
        vx = (int8_t)(vx + (int8_t)((int8_t)PLAYER_ACCEL * DIR_DX[player_dir]));
        vy = (int8_t)(vy + (int8_t)((int8_t)PLAYER_ACCEL * DIR_DY[player_dir]));
    }

    if (terrain == TILE_BOOST) {
        vy = (int8_t)(vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    {
        uint8_t max_speed = (terrain == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : PLAYER_MAX_SPEED;
        if (vx >  (int8_t)max_speed) vx =  (int8_t)max_speed;
        if (vx < -(int8_t)max_speed) vx = -(int8_t)max_speed;
        if (vy >  (int8_t)max_speed) vy =  (int8_t)max_speed;
        if (vy < -(int8_t)max_speed) vy = -(int8_t)max_speed;
    }
}
