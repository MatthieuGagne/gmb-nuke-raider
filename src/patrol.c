#pragma bank 255

#include <gb/gb.h>
#include <gb/cgb.h>
#include "patrol.h"
#include "config.h"
#include "track.h"
#include "loader.h"          /* load_patrol_waypoints, load_npc_positions, loader_get_slot */
#include "sprite_pool.h"
#include "projectile.h"
#include "damage.h"
#include "enemy_common.h"    /* enemy_aim_dir, enemy_dir_from_delta, enemy_wp_reached, enemy_wp_advance */
#include "vehicle_physics.h" /* vehicle_apply_physics, vehicle_step_axis_x/y */

extern int16_t cam_x;
extern int16_t cam_y;

/* ---- SoA pool ---- */
static int16_t patrol_px[MAX_PATROLS];
static int16_t patrol_py[MAX_PATROLS];
static int8_t  patrol_vx[MAX_PATROLS];
static int8_t  patrol_vy[MAX_PATROLS];
static uint8_t patrol_dir[MAX_PATROLS];
static uint8_t patrol_mode[MAX_PATROLS];
static uint8_t patrol_hp[MAX_PATROLS];
static uint8_t patrol_ram_cd[MAX_PATROLS];     /* per-patrol ram-damage cooldown (#417) */
static uint8_t patrol_hit_flash[MAX_PATROLS];  /* hit-blink frames, bullet + ram (#417) */
static uint8_t patrol_active[MAX_PATROLS];
static uint8_t patrol_timer[MAX_PATROLS];   /* fire-cadence countdown */
static uint8_t patrol_wp_idx[MAX_PATROLS];
static uint8_t patrol_oam[MAX_PATROLS * 4u];
static uint8_t patrol_wp_tx[MAX_PATROLS][PATROL_MAX_WAYPOINTS];
static uint8_t patrol_wp_ty[MAX_PATROLS][PATROL_MAX_WAYPOINTS];
static uint8_t patrol_wp_count[MAX_PATROLS];
static uint8_t s_tile_base;

/* ---- Directional car tile tables — identical to racer.c so it reuses the
 * player car sprite sheet. Layout: 0=T,1=RT,2=R,3=RB,4=B,5=LB,6=L,7=LT. ---- */
static const uint8_t PATROL_TILE_TL[8] = { 0u, 8u, 4u,12u, 1u,14u, 6u,10u };
static const uint8_t PATROL_TILE_BL[8] = { 1u, 9u, 5u,13u, 0u,15u, 7u,11u };
static const uint8_t PATROL_TILE_TR[8] = { 2u,10u, 6u,14u, 3u,12u, 4u, 8u };
static const uint8_t PATROL_TILE_BR[8] = { 3u,11u, 7u,15u, 2u,13u, 5u, 9u };
static const uint8_t PATROL_FLIP[8]    = { 0u, 0u, 0u, 0u, S_FLIPY, S_FLIPX, S_FLIPX, S_FLIPX };

/* ---- Manhattan helper (no multiply) ---- */
static uint16_t _manhattan(int16_t dx, int16_t dy) {
    uint16_t ax = (uint16_t)(dx < 0 ? -dx : dx);
    uint16_t ay = (uint16_t)(dy < 0 ? -dy : dy);
    return (uint16_t)(ax + ay);
}

/* ---- pure FSM ---- */
uint8_t patrol_fsm_next(uint8_t mode, int16_t dx, int16_t dy) BANKED {
    uint16_t m = _manhattan(dx, dy);
    if (mode == PATROL_MODE_PATROL) {
        if (m < (uint16_t)PATROL_DETECT_RADIUS) return PATROL_MODE_CHASE;
        return PATROL_MODE_PATROL;
    }
    /* CHASE */
    if (m >= (uint16_t)PATROL_LEAVE_RADIUS) return PATROL_MODE_PATROL;
    return PATROL_MODE_CHASE;
}

/* ---- internal spawn ---- */
static void _spawn(uint8_t i, int16_t px, int16_t py) {
    patrol_px[i]    = px;
    patrol_py[i]    = py;
    patrol_vx[i]    = (int8_t)0;
    patrol_vy[i]    = (int8_t)0;
    patrol_dir[i]   = DIR_B;
    patrol_mode[i]  = PATROL_MODE_PATROL;
    patrol_hp[i]    = (uint8_t)PATROL_HP;
    patrol_ram_cd[i]   = 0u;
    patrol_hit_flash[i]= 0u;
    patrol_active[i]= 1u;
    patrol_timer[i] = (uint8_t)PATROL_FIRE_INTERVAL;
    patrol_wp_idx[i]= 0u;
}

void patrol_init(uint8_t tile_base) BANKED {
    uint8_t i;
    uint8_t count = 0u;
    /* Scratch NPC buffers (sized for the NPC pool). */
    static uint8_t tx[MAX_NPCS], ty[MAX_NPCS], type[MAX_NPCS], dir[MAX_NPCS];
    uint8_t track_id;

    s_tile_base = tile_base;
    for (i = 0u; i < MAX_PATROLS; i++) {
        patrol_active[i] = 0u;
        patrol_wp_count[i] = 0u;
        patrol_oam[i * 4u + 0u] = get_sprite();
        patrol_oam[i * 4u + 1u] = get_sprite();
        patrol_oam[i * 4u + 2u] = get_sprite();
        patrol_oam[i * 4u + 3u] = get_sprite();
    }

    track_id = track_get_id();
    load_npc_positions(track_id, tx, ty, type, dir, &count);

    {
        uint8_t j = 0u;
        for (i = 0u; i < count && j < MAX_PATROLS; i++) {
            if (type[i] == NPC_TYPE_PATROL) {
                load_patrol_waypoints(track_id, j,
                                      patrol_wp_tx[j], patrol_wp_ty[j],
                                      &patrol_wp_count[j]);
                if (patrol_wp_count[j] > 0u) {
                    _spawn(j,
                           (int16_t)((uint16_t)tx[i] * 8u),
                           (int16_t)((uint16_t)ty[i] * 8u));
                    j++;
                }
            }
        }
    }

#ifdef __SDCC
    /* Reuse the racer red CGB sprite palette 1 (set_sprite_palette is idempotent). */
    {
        static const uint16_t patrol_pal[4] = {
            RGB(31u, 31u, 31u),
            RGB(31u,  0u,  0u),
            RGB(15u,  0u,  0u),
            RGB( 0u,  0u,  0u),
        };
        set_sprite_palette(1u, 1u, patrol_pal);
    }
#endif
}

void patrol_init_empty(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PATROLS; i++) {
        patrol_active[i] = 0u;
        patrol_wp_count[i] = 0u;
    }
}

void patrol_hide(void) BANKED {
    uint8_t i, j;
    for (i = 0u; i < MAX_PATROLS; i++) {
        for (j = 0u; j < 4u; j++) {
            move_sprite(patrol_oam[i * 4u + j], 0u, 0u);
        }
    }
}

uint8_t patrol_count_active(void) BANKED {
    uint8_t i, c = 0u;
    for (i = 0u; i < MAX_PATROLS; i++) {
        if (patrol_active[i]) c++;
    }
    return c;
}

/* Destroy a patrol: deactivate and hide its 4 OAM slots. Shared by the
 * bullet-hit and ram-hit paths (#417). */
static void patrol_kill(uint8_t i) {
    patrol_active[i] = 0u;
    move_sprite(patrol_oam[i * 4u + 0u], 0u, 0u);
    move_sprite(patrol_oam[i * 4u + 1u], 0u, 0u);
    move_sprite(patrol_oam[i * 4u + 2u], 0u, 0u);
    move_sprite(patrol_oam[i * 4u + 3u], 0u, 0u);
}

void patrol_update(int16_t px, int16_t py) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PATROLS; i++) {
        int16_t dx16, dy16;
        int16_t target_px, target_py;
        int8_t  dx, dy;
        uint8_t dir;
        uint8_t terrain;
        uint8_t gas;
        uint8_t tx, ty;
        TileType tt;

        if (!patrol_active[i]) continue;

        /* --- Per-frame timers: ram cooldown + hit-flash (#417) --- */
        if (patrol_ram_cd[i] > 0u)    patrol_ram_cd[i]--;
        if (patrol_hit_flash[i] > 0u) patrol_hit_flash[i]--;

        /* --- FSM: choose mode from player delta (Manhattan hysteresis) --- */
        dx16 = px - patrol_px[i];
        dy16 = py - patrol_py[i];
        patrol_mode[i] = patrol_fsm_next(patrol_mode[i], dx16, dy16);

        /* --- Select movement target --- */
        if (patrol_mode[i] == PATROL_MODE_CHASE) {
            target_px = px;
            target_py = py;
        } else {
            target_px = (int16_t)((uint16_t)patrol_wp_tx[i][patrol_wp_idx[i]] * 8u + 4u);
            target_py = (int16_t)((uint16_t)patrol_wp_ty[i][patrol_wp_idx[i]] * 8u + 4u);
        }

        dx16 = target_px - patrol_px[i];
        dy16 = target_py - patrol_py[i];
        if (dx16 >  127) dx16 =  127;
        if (dx16 < -127) dx16 = -127;
        if (dy16 >  127) dy16 =  127;
        if (dy16 < -127) dy16 = -127;
        dx = (int8_t)dx16;
        dy = (int8_t)dy16;

        /* --- Waypoint advance (PATROL only) --- */
        if (patrol_mode[i] == PATROL_MODE_PATROL) {
            uint8_t reached = enemy_wp_reached(dx, dy, (uint8_t)PATROL_WP_THRESHOLD);
            patrol_wp_idx[i] = enemy_wp_advance(patrol_wp_idx[i],
                                                patrol_wp_count[i], reached);
        }

        /* --- Facing --- */
        dir = enemy_dir_from_delta(dx, dy);
        patrol_dir[i] = dir;

        /* --- Terrain under the patrol's current tile --- */
        tx = (uint8_t)(((uint16_t)patrol_px[i] + 8u) >> 3u);
        ty = (uint8_t)((uint16_t)patrol_py[i] >> 3u);
        tt = track_tile_type_from_index(track_get_raw_tile(tx, ty));
        gas = (tt != TILE_OIL) ? 1u : 0u;
        terrain = (uint8_t)tt;

        /* --- Shared vehicle physics + axis-separated slide collision (R10) ---
         * Split API: friction (pre-accel) → per-axis homing thrust → boost+clamp.
         * Thrust is applied independently on each axis toward the target (NOT
         * along the 8-way facing dir): dominant-axis-only thrust stalls against
         * walls and corner-camps; per-axis thrust closes both deltas at once
         * and slides along walls. ±2px deadzone avoids jitter at the target. */
        vehicle_apply_friction(&patrol_vx[i], &patrol_vy[i], terrain, gas, dir);
        if (gas) {
            if      (dx >  2) patrol_vx[i] = (int8_t)(patrol_vx[i] + (int8_t)PATROL_SPEED);
            else if (dx < -2) patrol_vx[i] = (int8_t)(patrol_vx[i] - (int8_t)PATROL_SPEED);
            if      (dy >  2) patrol_vy[i] = (int8_t)(patrol_vy[i] + (int8_t)PATROL_SPEED);
            else if (dy < -2) patrol_vy[i] = (int8_t)(patrol_vy[i] - (int8_t)PATROL_SPEED);
        }
        {
            /* Boost pads let the patrol exceed its normal top speed (AC4),
             * mirroring racer.c; otherwise clamp to PATROL_SPEED. */
            uint8_t max_speed = (tt == TILE_BOOST)
                                ? (uint8_t)TERRAIN_BOOST_MAX_SPEED
                                : (uint8_t)PATROL_SPEED;
            vehicle_apply_boost_clamp(&patrol_vx[i], &patrol_vy[i], terrain, max_speed);
        }
        {
            /* Axis-separated slide; a blocked axis zeroes its velocity so the
             * free axis keeps closing (wall slide, no corner pinning). */
            int16_t old_p = patrol_px[i];
            patrol_px[i] = vehicle_step_axis_x(old_p, patrol_py[i], patrol_vx[i]);
            if (patrol_px[i] == old_p && patrol_vx[i] != 0) {
                patrol_vx[i] = (int8_t)0;
            }
            old_p = patrol_py[i];
            patrol_py[i] = vehicle_step_axis_y(patrol_px[i], old_p, patrol_vy[i]);
            if (patrol_py[i] == old_p && patrol_vy[i] != 0) {
                patrol_vy[i] = (int8_t)0;
            }
        }

        /* --- Ram contact: car-vs-car overlap via the SHARED enemy_ram_overlap
         * test (identical logic to racer.c, ENEMY_RAM_REACH margin so a flush
         * contact rams from any side). The player takes damage on every overlap
         * (damage.c i-frames debounce). The patrol takes ENEMY_RAM_DAMAGE behind
         * its own 30-frame cooldown; a 0-HP result destroys it (#417). --- */
        {
            if (enemy_ram_overlap(px, py, patrol_px[i], patrol_py[i])) {
                damage_apply(RACER_RAM_DAMAGE);
                if (patrol_ram_cd[i] == 0u) {
                    patrol_ram_cd[i]    = (uint8_t)ENEMY_RAM_COOLDOWN;
                    patrol_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
                    /* Underflow-safe and lethal-exact only while ENEMY_RAM_DAMAGE == 1
                     * (the == 0u test cannot be stepped over). Mirrors the 1-HP bullet
                     * path; raising ENEMY_RAM_DAMAGE needs an hp <= DAMAGE guard here. */
                    patrol_hp[i]        = (uint8_t)(patrol_hp[i] - ENEMY_RAM_DAMAGE);
                    if (patrol_hp[i] == 0u) {
                        patrol_kill(i);
                        continue;
                    }
                }
            }
        }

        /* --- On-screen gating: fire + hit only when visible --- */
        {
            int16_t scr_cx = patrol_px[i] + 16;          /* center x, OAM space */
            int16_t scr_cy = patrol_py[i] - cam_y + 24;  /* center y, OAM space */
            int16_t scr_x  = patrol_px[i] + 8  - cam_x;  /* sprite top-left x */
            int16_t scr_y  = patrol_py[i] - cam_y + 16;  /* sprite top-left y */
            uint8_t on_screen =
                (scr_x >= 0 && scr_x < 168 && scr_y >= 0 && scr_y < 160) ? 1u : 0u;

            if (on_screen) {
                /* Take player bullet hits */
                if (scr_cx >= 0 && scr_cx < 168 && scr_cy >= 0 && scr_cy < 160) {
                    if (projectile_check_hit_enemy((uint8_t)scr_cx, (uint8_t)scr_cy,
                                                   (uint8_t)PATROL_HIT_RADIUS)) {
                        patrol_hp[i]--;
                        patrol_hit_flash[i] = (uint8_t)RACER_HIT_FLASH_FRAMES;
                        if (patrol_hp[i] == 0u) {
                            patrol_kill(i);
                            continue;
                        }
                    }
                }
                /* Fire: CHASE + within fire radius + cadence */
                if (patrol_mode[i] == PATROL_MODE_CHASE &&
                    _manhattan((int16_t)(px - patrol_px[i]),
                               (int16_t)(py - patrol_py[i]))
                        < (uint16_t)PATROL_FIRE_RADIUS) {
                    if (patrol_timer[i] > 0u) {
                        patrol_timer[i]--;
                    } else {
                        player_dir_t fdir = enemy_aim_dir(tx, ty, px, py);
                        projectile_fire((uint8_t)scr_cx, (uint8_t)scr_cy,
                                        fdir, PROJ_OWNER_ENEMY);
                        patrol_timer[i] = (uint8_t)PATROL_FIRE_INTERVAL;
                    }
                } else {
                    patrol_timer[i] = (uint8_t)PATROL_FIRE_INTERVAL;
                }
            }
        }
    }

    /* Enemy bullets hitting the player (OAM-space, mirrors turret_update). */
    {
        uint8_t player_oam_x = (uint8_t)((int16_t)px + 16);
        uint8_t player_oam_y = (uint8_t)((int16_t)py - (int16_t)cam_y + 24);
        if (projectile_check_hit_player(player_oam_x, player_oam_y,
                                        (uint8_t)PATROL_HIT_RADIUS)) {
            damage_apply(ENEMY_BULLET_DAMAGE);
        }
    }
}

void patrol_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PATROLS; i++) {
        int16_t scr_x, scr_y;
        uint8_t hw_x, hw_y, d, flags;

        if (!patrol_active[i]) {
            move_sprite(patrol_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }

        /* Hit flash — hide sprite on odd 2-frame intervals (#417). */
        if (patrol_hit_flash[i] & 2u) {
            move_sprite(patrol_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }

        /* Recompute screen pos from world px/py & camera each frame (NOT cached). */
        scr_x = patrol_px[i] + 8;
        scr_y = patrol_py[i] - cam_y + 16;
        if (scr_x < 0 || scr_x >= 168 || scr_y < 0 || scr_y >= 160) {
            move_sprite(patrol_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(patrol_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }

        hw_x = (uint8_t)scr_x;
        hw_y = (uint8_t)scr_y;
        d    = patrol_dir[i];

        set_sprite_tile(patrol_oam[i * 4u + 0u], s_tile_base + PATROL_TILE_TL[d]);
        set_sprite_tile(patrol_oam[i * 4u + 1u], s_tile_base + PATROL_TILE_BL[d]);
        set_sprite_tile(patrol_oam[i * 4u + 2u], s_tile_base + PATROL_TILE_TR[d]);
        set_sprite_tile(patrol_oam[i * 4u + 3u], s_tile_base + PATROL_TILE_BR[d]);

        flags = PATROL_FLIP[d];
#ifdef __SDCC
        {
            uint8_t cgb = flags | S_PAL(1u);
            set_sprite_prop(patrol_oam[i * 4u + 0u], cgb);
            set_sprite_prop(patrol_oam[i * 4u + 1u], cgb);
            set_sprite_prop(patrol_oam[i * 4u + 2u], cgb);
            set_sprite_prop(patrol_oam[i * 4u + 3u], cgb);
        }
#else
        set_sprite_prop(patrol_oam[i * 4u + 0u], flags);
        set_sprite_prop(patrol_oam[i * 4u + 1u], flags);
        set_sprite_prop(patrol_oam[i * 4u + 2u], flags);
        set_sprite_prop(patrol_oam[i * 4u + 3u], flags);
#endif

        move_sprite(patrol_oam[i * 4u + 0u], hw_x,                hw_y);
        move_sprite(patrol_oam[i * 4u + 1u], hw_x,                (uint8_t)(hw_y + 8u));
        move_sprite(patrol_oam[i * 4u + 2u], (uint8_t)(hw_x + 8u), hw_y);
        move_sprite(patrol_oam[i * 4u + 3u], (uint8_t)(hw_x + 8u), (uint8_t)(hw_y + 8u));
    }
}

#ifndef __SDCC
uint8_t patrol_get_state(uint8_t i)  { return patrol_mode[i]; }
uint8_t patrol_get_hp(uint8_t i)     { return patrol_hp[i]; }
int16_t patrol_get_px(uint8_t i)     { return patrol_px[i]; }
int16_t patrol_get_py(uint8_t i)     { return patrol_py[i]; }
uint8_t patrol_get_wp_idx(uint8_t i) { return patrol_wp_idx[i]; }
uint8_t patrol_is_active(uint8_t i)  { return patrol_active[i]; }

void patrol_set_pos_for_test(uint8_t i, int16_t px, int16_t py) {
    patrol_px[i] = px; patrol_py[i] = py;
}
void patrol_set_mode_for_test(uint8_t i, uint8_t mode) { patrol_mode[i] = mode; }
void patrol_set_hp_for_test(uint8_t i, uint8_t hp)     { patrol_hp[i] = hp; }
void patrol_set_fire_timer_for_test(uint8_t i, uint8_t t) { patrol_timer[i] = t; }
uint8_t patrol_get_ram_cd(uint8_t i)                   { return patrol_ram_cd[i]; }
void patrol_set_ram_cd_for_test(uint8_t i, uint8_t c)  { patrol_ram_cd[i] = c; }
uint8_t patrol_get_hit_flash(uint8_t i)                { return patrol_hit_flash[i]; }

void patrol_spawn_for_test(int16_t px, int16_t py,
                           uint8_t *wp_tx, uint8_t *wp_ty, uint8_t wp_count) {
    uint8_t k;
    for (k = 0u; k < MAX_PATROLS; k++) patrol_active[k] = 0u;
    _spawn(0u, px, py);
    if (wp_count > PATROL_MAX_WAYPOINTS) wp_count = PATROL_MAX_WAYPOINTS;
    for (k = 0u; k < wp_count; k++) {
        patrol_wp_tx[0][k] = wp_tx[k];
        patrol_wp_ty[0][k] = wp_ty[k];
    }
    patrol_wp_count[0] = wp_count;
    patrol_oam[0] = patrol_oam[1] = patrol_oam[2] = patrol_oam[3] = 0u;
}
#endif
