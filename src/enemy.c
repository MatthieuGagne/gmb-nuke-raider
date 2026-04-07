#pragma bank 255
#include <gb/gb.h>
#include "enemy.h"
#include "config.h"
#include "track.h"
#include "projectile.h"
#include "damage.h"
#include "sprite_pool.h"
#include "loader.h"    /* load_object_sprites() NONBANKED — do NOT call set_sprite_data() directly */
#include "camera.h"    /* cam_y — needed for OAM y coordinate calculations */

/* SoA enemy pool — tile coordinates + cached OAM x (never changes for turrets) */
static uint8_t enemy_tx[MAX_ENEMIES];
static uint8_t enemy_ty[MAX_ENEMIES];
static uint8_t enemy_type[MAX_ENEMIES];    /* NPC_TYPE_* value set at spawn */
static uint8_t enemy_dir[MAX_ENEMIES];     /* stored at spawn; ignored for turrets (fire toward player) */
static uint8_t enemy_hp[MAX_ENEMIES];
static uint8_t enemy_active[MAX_ENEMIES];
static uint8_t enemy_timer[MAX_ENEMIES];
static uint8_t enemy_oam[MAX_ENEMIES];
static uint8_t enemy_oam_x[MAX_ENEMIES];  /* cached OAM x = tx*8+8 — turrets never move */

/* ---- internal helpers ---- */

static void _spawn_at(uint8_t i, uint8_t tx, uint8_t ty, uint8_t type, uint8_t dir) {
    enemy_tx[i]     = tx;
    enemy_ty[i]     = ty;
    enemy_type[i]   = type;
    enemy_dir[i]    = dir;
    enemy_hp[i]     = TURRET_HP;
    enemy_active[i] = 1u;
    enemy_timer[i]  = 0u;
    enemy_oam_x[i]  = (uint8_t)((uint16_t)tx * 8u + 8u);  /* OAM x cached once */
    enemy_oam[i]    = get_sprite();
    if (enemy_oam[i] != SPRITE_POOL_INVALID) {
        set_sprite_tile(enemy_oam[i], TURRET_TILE_BASE);
    }
}

/* ---- public API ---- */

void enemy_init(void) BANKED {
    uint8_t i;
    uint8_t count = 0u;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        enemy_active[i] = 0u;
        enemy_oam[i]    = SPRITE_POOL_INVALID;
    }
    load_object_sprites();
    load_npc_positions(track_get_id(),
                       enemy_tx, enemy_ty,
                       enemy_type, enemy_dir,
                       &count);
    for (i = 0u; i < count; i++) {
        _spawn_at(i, enemy_tx[i], enemy_ty[i], enemy_type[i], enemy_dir[i]);
    }
}

void enemy_init_empty(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        enemy_active[i] = 0u;
        enemy_oam[i]    = SPRITE_POOL_INVALID;
    }
}

uint8_t enemy_spawn(uint8_t tx, uint8_t ty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (!enemy_active[i]) {
            _spawn_at(i, tx, ty, NPC_TYPE_TURRET, DIR_NONE);
            return 1u;
        }
    }
    return 0u;
}

player_dir_t enemy_dir_to_pixel(uint8_t tx, uint8_t ty,
                                  int16_t player_px, int16_t player_py) BANKED {
    int16_t dx = player_px - (int16_t)((uint16_t)tx * 8u);
    int16_t dy = player_py - (int16_t)((uint16_t)ty * 8u);
    int16_t ax = dx < 0 ? -dx : dx;
    int16_t ay = dy < 0 ? -dy : dy;

    /* Diagonal threshold: |dx| and |dy| within 2x of each other.
     * Use << 1 instead of * 2 — SM83 has no hardware multiply. */
    if (ax > (int16_t)(ay << 1)) {
        return dx > 0 ? DIR_R : DIR_L;
    }
    if (ay > (int16_t)(ax << 1)) {
        return dy > 0 ? DIR_B : DIR_T;
    }
    /* Diagonal */
    if (dx >= 0 && dy >= 0) return DIR_RB;
    if (dx >= 0 && dy <  0) return DIR_RT;
    if (dx <  0 && dy >= 0) return DIR_LB;
    return DIR_LT;
}

/* Decrement fire timers by 1 frame.
 * WARNING: do NOT call in the same frame as enemy_update() — both decrement
 * enemy_timer[], which would halve TURRET_FIRE_INTERVAL. Test helper only. */
void enemy_tick_timers(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (enemy_active[i] && enemy_timer[i] > 0u) {
            enemy_timer[i]--;
        }
    }
}

void enemy_update(int16_t player_px, int16_t player_py) BANKED {
    uint8_t i;
    /* Player OAM-space position — must match projectile coordinate space.
     * proj_x/proj_y are stored as OAM coords (world_x+8 / world_y-cam_y+16). */
    uint8_t player_oam_x = (uint8_t)((int16_t)player_px + 16);
    uint8_t player_oam_y = (uint8_t)((int16_t)player_py - (int16_t)cam_y + 24);

    for (i = 0u; i < MAX_ENEMIES; i++) {
        uint8_t scr_x, scr_y;
        if (!enemy_active[i]) continue;

        /* OAM-space position of this turret — used for fire + hit detection.
         * scr_x cached in enemy_oam_x[]; scr_y recalculated each frame (cam_y moves). */
        scr_x = enemy_oam_x[i];
        scr_y = (uint8_t)((int16_t)((uint16_t)enemy_ty[i] * 8u) - (int16_t)cam_y + 16);

        /* Check if a player bullet hit this turret */
        if (projectile_check_hit_enemy(scr_x, scr_y, TURRET_HIT_RADIUS)) {
            enemy_hp[i]--;
            if (enemy_hp[i] == 0u) {
                enemy_active[i] = 0u;
                if (enemy_oam[i] != SPRITE_POOL_INVALID) {
                    clear_sprite(enemy_oam[i]);
                    enemy_oam[i] = SPRITE_POOL_INVALID;
                }
                continue;
            }
        }

        /* Fire timer */
        if (enemy_timer[i] > 0u) {
            enemy_timer[i]--;
        } else {
            player_dir_t dir = enemy_dir_to_pixel(
                enemy_tx[i], enemy_ty[i], player_px, player_py);
            projectile_fire(scr_x, scr_y, dir, PROJ_OWNER_ENEMY);
            enemy_timer[i] = TURRET_FIRE_INTERVAL;
        }
    }

    /* Check if any enemy bullet hit the player */
    if (projectile_check_hit_player(player_oam_x, player_oam_y, TURRET_HIT_RADIUS)) {
        damage_apply(ENEMY_BULLET_DAMAGE);
    }
}

void enemy_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        int16_t oam_y;
        if (!enemy_active[i] || enemy_oam[i] == SPRITE_POOL_INVALID) continue;
        /* Turret OAM y accounts for camera scroll — turrets are in world space */
        oam_y = (int16_t)((uint16_t)enemy_ty[i] * 8u) - (int16_t)cam_y + 16;
        if (oam_y < 0 || oam_y > 175) continue;   /* off screen — skip */
        move_sprite(enemy_oam[i], enemy_oam_x[i], (uint8_t)oam_y);
    }
}

uint8_t enemy_blocks_tile(uint8_t tx, uint8_t ty) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (enemy_active[i] && enemy_tx[i] == tx && enemy_ty[i] == ty) {
            return 1u;
        }
    }
    return 0u;
}

uint8_t enemy_count_active(void) BANKED {
    uint8_t i, count = 0u;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        if (enemy_active[i]) count++;
    }
    return count;
}

#ifndef __SDCC
uint8_t enemy_get_type(uint8_t i)  { return enemy_type[i]; }
uint8_t enemy_get_dir(uint8_t i)   { return enemy_dir[i]; }
uint8_t enemy_get_timer(uint8_t i) { return enemy_timer[i]; }
#endif
