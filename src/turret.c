#pragma bank 255
#include <gb/gb.h>
#include "turret.h"
#include "config.h"
#include "track.h"
#include "projectile.h"
#include "damage.h"
#include "sprite_pool.h"
#include "loader.h"    /* load_npc_positions(), loader_get_slot() — NONBANKED helpers */
#include "camera.h"    /* cam_y — needed for OAM y coordinate calculations */

static uint8_t s_turret_tile_base;  /* OBJ tile index set by turret_init() */

/* SoA turret pool — tile coordinates + cached OAM x (never changes for turrets) */
static uint8_t turret_tx[MAX_ENEMIES];
static uint8_t turret_ty[MAX_ENEMIES];
static uint8_t turret_type[MAX_ENEMIES];    /* NPC_TYPE_* value set at spawn */
static uint8_t turret_dir[MAX_ENEMIES];     /* stored at spawn; ignored for turrets (fire toward player) */
static uint8_t turret_hp[MAX_ENEMIES];
static uint8_t turret_active[MAX_ENEMIES];
static uint8_t turret_timer[MAX_ENEMIES];
static uint8_t turret_oam[MAX_ENEMIES];
static uint8_t turret_oam_x[MAX_ENEMIES];  /* cached OAM x = tx*8+8 — turrets never move */

/* ---- internal helpers ---- */

static void _spawn_at(uint8_t i, uint8_t tx, uint8_t ty, uint8_t type, uint8_t dir) {
    turret_tx[i]     = tx;
    turret_ty[i]     = ty;
    turret_type[i]   = type;
    turret_dir[i]    = dir;
    turret_hp[i]     = TURRET_HP;
    turret_active[i] = 1u;
    turret_timer[i]  = TURRET_WIND_UP;
    turret_oam_x[i]  = (uint8_t)((uint16_t)tx * 8u + 8u);  /* OAM x cached once */
    turret_oam[i]    = get_sprite();
    if (turret_oam[i] != SPRITE_POOL_INVALID) {
        set_sprite_tile(turret_oam[i], s_turret_tile_base);
    }
}

/* ---- public API ---- */

void turret_init(uint8_t tile_base) BANKED {
    uint8_t i;
    uint8_t count = 0u;
    s_turret_tile_base = tile_base;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        turret_active[i] = 0u;
        turret_oam[i]    = SPRITE_POOL_INVALID;
    }
    load_npc_positions(track_get_id(),
                       turret_tx, turret_ty,
                       turret_type, turret_dir,
                       &count);
    for (i = 0u; i < count; i++) {
        _spawn_at(i, turret_tx[i], turret_ty[i], turret_type[i], turret_dir[i]);
    }
}

void turret_init_empty(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        turret_active[i] = 0u;
        turret_oam[i]    = SPRITE_POOL_INVALID;
    }
}

uint8_t turret_spawn(uint8_t tx, uint8_t ty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (!turret_active[i]) {
            _spawn_at(i, tx, ty, NPC_TYPE_TURRET, DIR_NONE);
            return 1u;
        }
    }
    return 0u;
}

player_dir_t turret_dir_to_pixel(uint8_t tx, uint8_t ty,
                                  int16_t player_px, int16_t player_py) BANKED {
    int16_t dx = player_px - (int16_t)((uint16_t)tx * 8u);
    int16_t dy = player_py - (int16_t)((uint16_t)ty * 8u);
    int16_t ax = dx < 0 ? -dx : dx;
    int16_t ay = dy < 0 ? -dy : dy;
    uint8_t toward_x;

    /* Threshold 1: cardinal E/W — |dx| > 2*|dy| */
    if (ax > (int16_t)(ay << 1)) {
        return dx > 0 ? DIR_R : DIR_L;
    }
    /* Threshold 2: cardinal N/S — |dy| > 2*|dx| */
    if (ay > (int16_t)(ax << 1)) {
        return dy > 0 ? DIR_B : DIR_T;
    }
    /* Threshold 3: intermediate sector — |dx| vs |dy| */
    toward_x = (uint8_t)(ax > ay);
    if (dx >= 0 && dy < 0) { return toward_x ? DIR_ENE : DIR_NNE; }
    if (dx >= 0)            { return toward_x ? DIR_ESE : DIR_SSE; }
    if (dy >= 0)            { return toward_x ? DIR_WSW : DIR_SSW; }
    return toward_x ? DIR_WNW : DIR_NNW;
}

void turret_update(int16_t player_px, int16_t player_py) BANKED {
    uint8_t i;
    /* Player OAM-space position — must match projectile coordinate space.
     * proj_x/proj_y are stored as OAM coords (world_x+8 / world_y-cam_y+16). */
    uint8_t player_oam_x = (uint8_t)((int16_t)player_px + 16);
    uint8_t player_oam_y = (uint8_t)((int16_t)player_py - (int16_t)cam_y + 24);

    for (i = 0u; i < MAX_ENEMIES; i++) {
        int16_t vis_x, vis_y;
        uint8_t scr_x, scr_y;
        if (!turret_active[i]) continue;

        /* OAM-space position — adjusted for both scroll axes */
        vis_x = (int16_t)turret_oam_x[i] - (int16_t)cam_x;
        vis_y = (int16_t)((uint16_t)turret_ty[i] * 8u) - (int16_t)cam_y + 16;

        /* Skip hit detection, timer, and fire for off-screen turrets */
        if (vis_x < 0 || vis_x >= 168 || vis_y < 0 || vis_y >= 160) continue;

        scr_x = (uint8_t)vis_x;
        scr_y = (uint8_t)vis_y;

        /* Check if a player bullet hit this turret */
        if (projectile_check_hit_enemy(scr_x, scr_y, TURRET_HIT_RADIUS)) {
            turret_hp[i]--;
            if (turret_hp[i] == 0u) {
                turret_active[i] = 0u;
                if (turret_oam[i] != SPRITE_POOL_INVALID) {
                    clear_sprite(turret_oam[i]);
                    turret_oam[i] = SPRITE_POOL_INVALID;
                }
                continue;
            }
        }

        /* Fire timer — only runs when turret is on screen */
        if (turret_timer[i] > 0u) {
            turret_timer[i]--;
        } else {
            player_dir_t dir = turret_dir_to_pixel(
                turret_tx[i], turret_ty[i], player_px, player_py);
            projectile_fire(scr_x, scr_y, dir, PROJ_OWNER_ENEMY);
            turret_timer[i] = TURRET_FIRE_INTERVAL;
        }
    }

    /* Check if any enemy bullet hit the player */
    if (projectile_check_hit_player(player_oam_x, player_oam_y, TURRET_HIT_RADIUS)) {
        damage_apply(ENEMY_BULLET_DAMAGE);
    }
}

void turret_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        int16_t oam_x_s, oam_y;
        if (!turret_active[i] || turret_oam[i] == SPRITE_POOL_INVALID) continue;
        oam_y   = (int16_t)((uint16_t)turret_ty[i] * 8u) - (int16_t)cam_y + 16;
        oam_x_s = (int16_t)turret_oam_x[i] - (int16_t)cam_x;
        if (oam_y < 0 || oam_y > 175 || oam_x_s < 0 || oam_x_s > 167) continue;
        move_sprite(turret_oam[i], (uint8_t)oam_x_s, (uint8_t)oam_y);
    }
}

uint8_t turret_blocks_tile(uint8_t tx, uint8_t ty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (turret_active[i] && turret_tx[i] == tx && turret_ty[i] == ty) {
            return 1u;
        }
    }
    return 0u;
}

uint8_t turret_count_active(void) BANKED {
    uint8_t i, count = 0u;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (turret_active[i]) count++;
    }
    return count;
}

#ifndef __SDCC
uint8_t turret_get_type(uint8_t i)  { return turret_type[i]; }
uint8_t turret_get_dir(uint8_t i)   { return turret_dir[i]; }
uint8_t turret_get_timer(uint8_t i) { return turret_timer[i]; }
uint8_t turret_is_screen_visible(uint8_t i) {
    int16_t vis_x = (int16_t)turret_oam_x[i] - (int16_t)cam_x;
    int16_t vis_y = (int16_t)((uint16_t)turret_ty[i] * 8u) - (int16_t)cam_y + 16;
    return (vis_x >= 0 && vis_x < 168 && vis_y >= 0 && vis_y < 160) ? 1u : 0u;
}
#endif
