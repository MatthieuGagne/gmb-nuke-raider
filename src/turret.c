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
#include "enemy_common.h"  /* enemy_aim_dir — shared aim math */
#include "explosion.h" /* explosion_spawn() — OAM hand-off on turret death */
#include "beam.h"      /* beam_hit_damage() — LASER hitscan poll (#430) */
#include "debug.h"

DBG_STATIC uint8_t s_turret_tile_base;  /* OBJ tile index set by turret_init() */
DBG_STATIC uint8_t s_explosion_base;    /* OBJ tile index set by turret_set_explosion_base() */

/* SoA turret pool — tile coordinates + cached OAM x (never changes for turrets) */
DBG_STATIC uint8_t turret_tx[MAX_ENEMIES];
DBG_STATIC uint8_t turret_ty[MAX_ENEMIES];
DBG_STATIC uint8_t turret_type[MAX_ENEMIES];    /* NPC_TYPE_* value set at spawn */
DBG_STATIC uint8_t turret_dir[MAX_ENEMIES];     /* stored at spawn; ignored for turrets (fire toward player) */
DBG_STATIC uint8_t turret_hp[MAX_ENEMIES];
DBG_STATIC uint8_t turret_active[MAX_ENEMIES];
DBG_STATIC uint8_t turret_timer[MAX_ENEMIES];
DBG_STATIC uint8_t turret_oam[MAX_ENEMIES];
DBG_STATIC uint8_t turret_oam_x[MAX_ENEMIES];  /* cached OAM x = tx*8+8 — turrets never move */

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
    {
        uint8_t j = 0u;
        for (i = 0u; i < count; i++) {
            if (turret_type[i] == NPC_TYPE_TURRET) {
                _spawn_at(j, turret_tx[i], turret_ty[i], turret_type[i], turret_dir[i]);
                j++;
            }
        }
    }
}

void turret_init_empty(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_ENEMIES; i++) {
        turret_active[i] = 0u;
        turret_oam[i]    = SPRITE_POOL_INVALID;
    }
}

void turret_set_explosion_base(uint8_t base) BANKED {
    s_explosion_base = base;
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

/* Deactivate turret i and hand its OAM slot to the explosion pool.
 * Shared by the bullet and beam damage paths (#430). The caller must `continue`
 * afterwards — this helper does not touch hp and does not skip the fire timer.
 * static, so NOT BANKED (same-bank call from turret_update). */
static void turret_destroy(uint8_t i) {
    turret_active[i] = 0u;
    if (turret_oam[i] != SPRITE_POOL_INVALID) {
        /* Do NOT clear_sprite here — explosion now owns this slot and will
         * call clear_sprite when the animation finishes. */
        explosion_spawn(turret_oam[i], s_explosion_base, 0u, 0u,
                        turret_oam_x[i],   /* world pixel x = tx*8+8 */
                        turret_ty[i]);     /* world tile y */
        turret_oam[i] = SPRITE_POOL_INVALID;
    }
}

void turret_update(int16_t player_px, int16_t player_py) BANKED {
    uint8_t i;
    /* Player OAM-space position — must match projectile coordinate space.
     * proj_x/proj_y are stored as OAM coords (world_x+8 / world_y-cam_y+16). */
    uint8_t player_oam_x = (uint8_t)((int16_t)player_px + 16);
    uint8_t player_oam_y = (uint8_t)((int16_t)player_py - (int16_t)cam_y + 24);

    for (i = 0u; i < MAX_ENEMIES; i++) {
        int16_t vis_x, vis_y;
        uint16_t world_y;
        uint8_t scr_x, scr_y;
        if (!turret_active[i]) continue;

        /* World pixel y = ty*8. Hoisted: the visibility test and the beam poll
         * both need it, and an 8x8->16 multiply per turret per frame is not
         * free on z80. ty <= 255 so ty*8 <= 2040 — always positive in int16_t. */
        world_y = (uint16_t)turret_ty[i] * 8u;

        /* OAM-space position — adjusted for both scroll axes */
        vis_x = (int16_t)turret_oam_x[i] - (int16_t)cam_x;
        vis_y = (int16_t)world_y - (int16_t)cam_y + 16;

        /* Skip hit detection, timer, and fire for off-screen turrets */
        if (vis_x < 0 || vis_x >= 168 || vis_y < 0 || vis_y >= 160) continue;

        scr_x = (uint8_t)vis_x;
        scr_y = (uint8_t)vis_y;

        /* Check if a player bullet hit this turret */
        {
            uint8_t dmg = projectile_check_hit_enemy(scr_x, scr_y, TURRET_HIT_RADIUS);
            if (dmg) {
                turret_hp[i] = enemy_apply_damage(turret_hp[i], dmg);
                if (turret_hp[i] == 0u) {
                    turret_destroy(i);
                    continue;
                }
            }
        }

        /* #430: turrets are 8x8 at the tile origin; world x = tx*8.
         * This poll deliberately STAYS INSIDE the visibility guard at :110 —
         * every statement past it is already gated and there is no "outside"
         * without restructuring the loop. Harmless: vis_x correctly subtracts
         * cam_x and the beam is itself screen-clipped. The bullet branch above
         * `continue`s when it destroys a turret, so a bullet kill never reaches
         * this poll. */
        {
            uint8_t bdmg = beam_hit_damage((int16_t)((uint16_t)turret_tx[i] * 8u),
                                           (int16_t)world_y, 8u);
            if (bdmg) {
                turret_hp[i] = enemy_apply_damage(turret_hp[i], bdmg);
                if (turret_hp[i] == 0u) { turret_destroy(i); continue; }
            }
        }

        /* Fire timer — only runs when turret is on screen */
        if (turret_timer[i] > 0u) {
            turret_timer[i]--;
        } else {
            player_dir_t dir = enemy_aim_dir(
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
