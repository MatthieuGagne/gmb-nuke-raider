#pragma bank 255

#include <gb/gb.h>
#include <gb/cgb.h>
#include "racer.h"
#include "config.h"
#include "track.h"
#include "checkpoint.h"
#include "loader.h"
#include "sprite_pool.h"
#include "player.h"
#include "banking.h"

/* cam_y declared in camera.c — used for screen-space Y offset in racer_render */
extern int16_t cam_y;

/* ---- SoA pool ---- */
static int16_t  racer_px[MAX_RACERS];
static int16_t  racer_py[MAX_RACERS];
static uint8_t  racer_dir[MAX_RACERS];
static uint8_t  racer_wp_idx[MAX_RACERS];
uint8_t  racer_active[MAX_RACERS];
static uint8_t  racer_oam[MAX_RACERS * 4u];
static int8_t   racer_vx[MAX_RACERS];
static int8_t   racer_vy[MAX_RACERS];
static uint8_t  racer_gear[MAX_RACERS];
static uint8_t  racer_downshift_timer[MAX_RACERS];

/* ---- Track-level data ---- */
static uint8_t  s_wp_tx[MAX_RACER_WAYPOINTS];
static uint8_t  s_wp_ty[MAX_RACER_WAYPOINTS];
static uint8_t  s_wp_count;
static uint8_t  s_finish_dir;
static uint8_t  s_tile_base;
static uint8_t  s_laps_done;  /* completed wp cycles so far */
static uint8_t  s_lap_total;  /* number of full wp cycles required to win */

/* ---- Direction tables — copied from player.c exact values ---- */

/* Direction velocity deltas: 0=T, 1=RT, 2=R, 3=RB, 4=B, 5=LB, 6=L, 7=LT */
static const int8_t RACER_DIR_DX[8] = {  0,  1,  1,  1,  0, -1, -1, -1 };
static const int8_t RACER_DIR_DY[8] = { -1, -1,  0,  1,  1,  1,  0, -1 };

/* Tile index for each 2x2 OAM slot per direction.
 * Layout: UP=0-3, RIGHT=4-7, UPRIGHT=8-11, DOWNRIGHT=12-15.
 * These match player.c exactly so racer uses the same sprite sheet. */
static const uint8_t RACER_DIR_TILE_TL[8] = {
     0u, /*  T  */
     8u, /* RT  */
     4u, /*  R  */
    12u, /* RB  */
     1u, /*  B  */
    14u, /* LB  */
     6u, /*  L  */
    10u, /* LT  */
};
static const uint8_t RACER_DIR_TILE_BL[8] = {
     1u, /*  T  */
     9u, /* RT  */
     5u, /*  R  */
    13u, /* RB  */
     0u, /*  B  */
    15u, /* LB  */
     7u, /*  L  */
    11u, /* LT  */
};
static const uint8_t RACER_DIR_TILE_TR[8] = {
     2u, /*  T  */
    10u, /* RT  */
     6u, /*  R  */
    14u, /* RB  */
     3u, /*  B  */
    12u, /* LB  */
     4u, /*  L  */
     8u, /* LT  */
};
static const uint8_t RACER_DIR_TILE_BR[8] = {
     3u, /*  T  */
    11u, /* RT  */
     7u, /*  R  */
    15u, /* RB  */
     2u, /*  B  */
    13u, /* LB  */
     5u, /*  L  */
     9u, /* LT  */
};
static const uint8_t RACER_DIR_FLIP[8] = {
    0u,      /* T  */
    0u,      /* RT */
    0u,      /* R  */
    0u,      /* RB */
    S_FLIPY, /* B  */
    S_FLIPX, /* LB */
    S_FLIPX, /* L  */
    S_FLIPX, /* LT */
};

/* ---- Directional hitbox corners — mirrors player.c HITBOX_X/Y ---- */
static const uint8_t RACER_HITBOX_X[8][4] = {
    {2u, 13u,  2u, 13u},  /* DIR_T  */
    {8u, 14u,  1u,  8u},  /* DIR_RT */
    {0u, 15u,  0u, 15u},  /* DIR_R  */
    {1u,  8u,  8u, 14u},  /* DIR_RB */
    {2u, 13u,  2u, 13u},  /* DIR_B  */
    {8u, 14u,  1u,  8u},  /* DIR_LB */
    {0u, 15u,  0u, 15u},  /* DIR_L  */
    {1u,  8u,  8u, 14u},  /* DIR_LT */
};
static const uint8_t RACER_HITBOX_Y[8][4] = {
    {0u,  0u, 15u, 15u},  /* DIR_T  */
    {1u,  8u,  8u, 14u},  /* DIR_RT */
    {2u,  2u, 13u, 13u},  /* DIR_R  */
    {8u,  1u, 14u,  8u},  /* DIR_RB */
    {0u,  0u, 15u, 15u},  /* DIR_B  */
    {1u,  8u,  8u, 14u},  /* DIR_LB */
    {2u,  2u, 13u, 13u},  /* DIR_L  */
    {8u,  1u, 14u,  8u},  /* DIR_LT */
};

/* ---- Gear LUTs — racer-specific tuning (RACER_GEAR3_MAX_SPEED=5, player=6) ---- */
static const uint8_t RACER_GEAR_MAX_SPD[3] = {RACER_GEAR1_MAX_SPEED, RACER_GEAR2_MAX_SPEED, RACER_GEAR3_MAX_SPEED};
static const uint8_t RACER_GEAR_ACCEL_TBL[3] = {RACER_GEAR1_ACCEL, RACER_GEAR2_ACCEL, RACER_GEAR3_ACCEL};

/* ---- 4-corner passability check (dir-specific hitbox, no turret check for racer) ---- */
static uint8_t racer_corners_passable(int16_t wx, int16_t wy, uint8_t dir) {
    uint8_t i;
    for (i = 0u; i < 4u; i++) {
        int16_t cx = wx + (int16_t)RACER_HITBOX_X[dir][i];
        int16_t cy = wy + (int16_t)RACER_HITBOX_Y[dir][i];
        if (!track_passable(cx, cy)) return 0u;
    }
    return 1u;
}

/* ---- Direction from delta ---- */
static uint8_t racer_dir_from_delta(int8_t dx, int8_t dy) {
    int8_t ax = dx < 0 ? -dx : dx;
    int8_t ay = dy < 0 ? -dy : dy;
    if (ay > ax) {
        return (dy < 0) ? DIR_T : DIR_B;
    } else if (ax > ay) {
        return (dx < 0) ? DIR_L : DIR_R;
    } else {
        /* Diagonal: ax == ay */
        if (dy < 0 && dx < 0) return DIR_LT;
        if (dy < 0 && dx > 0) return DIR_RT;
        if (dy > 0 && dx < 0) return DIR_LB;
        return DIR_RB;
    }
}

/* ---- Finish direction check ---- */
static uint8_t racer_dir_matches_finish(uint8_t dir, uint8_t finish_dir) {
    if (finish_dir == CHECKPOINT_DIR_N) {
        return (dir == DIR_T || dir == DIR_LT || dir == DIR_RT) ? 1u : 0u;
    }
    if (finish_dir == CHECKPOINT_DIR_S) {
        return (dir == DIR_B || dir == DIR_LB || dir == DIR_RB) ? 1u : 0u;
    }
    if (finish_dir == CHECKPOINT_DIR_E) {
        return (dir == DIR_R || dir == DIR_RT || dir == DIR_RB) ? 1u : 0u;
    }
    if (finish_dir == CHECKPOINT_DIR_W) {
        return (dir == DIR_L || dir == DIR_LT || dir == DIR_LB) ? 1u : 0u;
    }
    return 0u;
}

void racer_init(uint8_t tile_base) BANKED {
    uint8_t i;
    uint8_t spawn_tx;
    uint8_t spawn_ty;
    uint8_t found;
    uint8_t track_id;

    for (i = 0u; i < MAX_RACERS; i++) {
        racer_active[i] = 0u;
        racer_vx[i] = (int8_t)0;
        racer_vy[i] = (int8_t)0;
        racer_gear[i] = 0u;
        racer_downshift_timer[i] = 0u;
    }
    s_tile_base  = tile_base;
    s_laps_done  = 0u;

    track_id = track_get_id();
    s_finish_dir = track_get_finish_direction();
    s_lap_total  = track_get_lap_count();
    load_racer_waypoints(track_id, s_wp_tx, s_wp_ty, &s_wp_count);
    found = load_racer_spawn(track_id, &spawn_tx, &spawn_ty);

    if (found && s_wp_count > 0u) {
        racer_active[0] = 1u;
        racer_px[0] = (int16_t)((uint16_t)spawn_tx * 8u);
        racer_py[0] = (int16_t)((uint16_t)spawn_ty * 8u);
        racer_wp_idx[0] = 0u;
        racer_dir[0] = track_get_start_dir();
        for (i = 0u; i < 4u; i++) {
            racer_oam[i] = get_sprite();
        }
    }

#ifdef __SDCC
    /* CGB sprite palette 1: red tint to distinguish racer from player */
    {
        static const uint16_t racer_pal[4] = {
            RGB(31u, 31u, 31u), /* white        */
            RGB(31u,  0u,  0u), /* red          */
            RGB(15u,  0u,  0u), /* dark red     */
            RGB( 0u,  0u,  0u), /* black        */
        };
        set_sprite_palette(1u, 1u, racer_pal);
    }
#endif /* __SDCC */
}

void racer_init_empty(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_RACERS; i++) {
        racer_active[i] = 0u;
        racer_vx[i] = (int8_t)0;
        racer_vy[i] = (int8_t)0;
        racer_gear[i] = 0u;
        racer_downshift_timer[i] = 0u;
    }
    s_wp_count  = 0u;
    s_laps_done = 0u;
    s_lap_total = 1u;
}

void racer_hide(void) BANKED {
    uint8_t i;
    uint8_t j;
    for (i = 0u; i < MAX_RACERS; i++) {
        for (j = 0u; j < 4u; j++) {
            move_sprite(racer_oam[i * 4u + j], 0u, 0u);
        }
    }
}

uint8_t racer_update(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_RACERS; i++) {
        int16_t target_px;
        int16_t target_py;
        int16_t dx16;
        int16_t dy16;
        int8_t  dx;
        int8_t  dy;
        uint8_t abs_dx;
        uint8_t abs_dy;
        uint8_t dir;
        uint8_t tx;
        uint8_t ty;
        uint8_t raw_tile;
        TileType tile_type;

        if (!racer_active[i]) continue;

        target_px = (int16_t)((uint16_t)s_wp_tx[racer_wp_idx[i]] * 8u + 4u);
        target_py = (int16_t)((uint16_t)s_wp_ty[racer_wp_idx[i]] * 8u + 4u);

        dx16 = target_px - racer_px[i];
        dy16 = target_py - racer_py[i];

        /* Clamp to int8 range */
        if (dx16 >  127) dx16 =  127;
        if (dx16 < -127) dx16 = -127;
        if (dy16 >  127) dy16 =  127;
        if (dy16 < -127) dy16 = -127;
        dx = (int8_t)dx16;
        dy = (int8_t)dy16;

        abs_dx = (uint8_t)(dx < 0 ? -dx : dx);
        abs_dy = (uint8_t)(dy < 0 ? -dy : dy);

        if ((uint8_t)(abs_dx + abs_dy) < RACER_WP_THRESHOLD) {
            racer_wp_idx[i]++;
            if (racer_wp_idx[i] >= s_wp_count) {
                racer_wp_idx[i] = 0u;
                s_laps_done++;
            }
        }

        dir = racer_dir_from_delta(dx, dy);
        racer_dir[i] = dir;

        /* Finish line detection — check current position before applying velocity.
         * Avoids chained BANKED calls: store raw tile before passing to type LUT. */
        tx = (uint8_t)((uint16_t)racer_px[i] >> 3u);
        ty = (uint8_t)((uint16_t)racer_py[i] >> 3u);
        raw_tile  = track_get_raw_tile(tx, ty);
        tile_type = track_tile_type_from_index(raw_tile);
        if (s_laps_done >= s_lap_total && tile_type == TILE_FINISH) {
            if (racer_dir_matches_finish(dir, s_finish_dir)) {
                return 1u;
            }
        }

        /* ---- Gear physics (mirrors player_apply_physics, always full throttle) ---- */
        {
            uint8_t fric_x;
            uint8_t fric_y;
            uint8_t gas;
            uint8_t j;
            uint8_t max_speed;
            uint8_t spd_x;
            uint8_t spd_y;
            uint8_t speed;

            gas = (tile_type != TILE_OIL) ? 1u : 0u;

            if (tile_type == TILE_SAND) {
                fric_x = (gas && RACER_DIR_DX[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
                fric_y = (gas && RACER_DIR_DY[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
            } else if (tile_type == TILE_OIL) {
                fric_x = 0u;
                fric_y = 0u;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            } else {
                fric_x = (gas && RACER_DIR_DX[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
                fric_y = (gas && RACER_DIR_DY[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
            }

            for (j = 0u; j < fric_x; j++) {
                if      (racer_vx[i] > 0) racer_vx[i] = (int8_t)(racer_vx[i] - 1);
                else if (racer_vx[i] < 0) racer_vx[i] = (int8_t)(racer_vx[i] + 1);
            }
            for (j = 0u; j < fric_y; j++) {
                if      (racer_vy[i] > 0) racer_vy[i] = (int8_t)(racer_vy[i] - 1);
                else if (racer_vy[i] < 0) racer_vy[i] = (int8_t)(racer_vy[i] + 1);
            }

            if (gas) {
                racer_vx[i] = (int8_t)(racer_vx[i] + (int8_t)((int8_t)RACER_GEAR_ACCEL_TBL[racer_gear[i]] * RACER_DIR_DX[dir]));
                racer_vy[i] = (int8_t)(racer_vy[i] + (int8_t)((int8_t)RACER_GEAR_ACCEL_TBL[racer_gear[i]] * RACER_DIR_DY[dir]));
            }

            if (tile_type == TILE_BOOST) {
                racer_vy[i] = (int8_t)(racer_vy[i] - (int8_t)TERRAIN_BOOST_DELTA);
            }

            max_speed = (tile_type == TILE_BOOST) ? TERRAIN_BOOST_MAX_SPEED : RACER_GEAR_MAX_SPD[racer_gear[i]];
            if (racer_vx[i] >  (int8_t)max_speed) racer_vx[i] =  (int8_t)max_speed;
            if (racer_vx[i] < -(int8_t)max_speed) racer_vx[i] = -(int8_t)max_speed;
            if (racer_vy[i] >  (int8_t)max_speed) racer_vy[i] =  (int8_t)max_speed;
            if (racer_vy[i] < -(int8_t)max_speed) racer_vy[i] = -(int8_t)max_speed;

            spd_x = (racer_vx[i] < 0) ? (uint8_t)(-racer_vx[i]) : (uint8_t)racer_vx[i];
            spd_y = (racer_vy[i] < 0) ? (uint8_t)(-racer_vy[i]) : (uint8_t)racer_vy[i];
            speed = (spd_x > spd_y) ? spd_x : spd_y;

            if (racer_gear[i] < 2u && speed >= RACER_GEAR_MAX_SPD[racer_gear[i]]) {
                racer_gear[i]++;
                racer_downshift_timer[i] = 0u;
            } else if (racer_gear[i] > 0u) {
                if (speed < RACER_GEAR_MAX_SPD[racer_gear[i] - 1u]) {
                    racer_downshift_timer[i]++;
                    if (racer_downshift_timer[i] >= RACER_GEAR_DOWNSHIFT_FRAMES) {
                        racer_gear[i]--;
                        racer_downshift_timer[i] = 0u;
                    }
                } else {
                    racer_downshift_timer[i] = 0u;
                }
            }
        }

        /* ---- Axis-split collision ---- */
        {
            int16_t new_px = (int16_t)(racer_px[i] + (int16_t)racer_vx[i]);
            int16_t new_py = (int16_t)(racer_py[i] + (int16_t)racer_vy[i]);

            if (racer_corners_passable(new_px, racer_py[i], dir)) {
                racer_px[i] = new_px;
            } else {
                racer_vx[i] = (int8_t)0;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            }

            if (racer_corners_passable(racer_px[i], new_py, dir)) {
                racer_py[i] = new_py;
            } else {
                racer_vy[i] = (int8_t)0;
                racer_gear[i] = 0u;
                racer_downshift_timer[i] = 0u;
            }
        }
    }
    return 0u;
}

void racer_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_RACERS; i++) {
        int16_t scr_x;
        int16_t scr_y;
        uint8_t hw_x;
        uint8_t hw_y;
        uint8_t d;
        uint8_t flags;

        if (!racer_active[i]) continue;

        scr_x = racer_px[i] + 8;
        scr_y = racer_py[i] - cam_y + 16;

        /* Skip if off-screen */
        if (scr_x < 0 || scr_x >= 168 || scr_y < 0 || scr_y >= 160) {
            move_sprite(racer_oam[i * 4u + 0u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 1u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 2u], 0u, 0u);
            move_sprite(racer_oam[i * 4u + 3u], 0u, 0u);
            continue;
        }

        hw_x = (uint8_t)scr_x;
        hw_y = (uint8_t)scr_y;
        d    = racer_dir[i];

        set_sprite_tile(racer_oam[i * 4u + 0u], s_tile_base + RACER_DIR_TILE_TL[d]);
        set_sprite_tile(racer_oam[i * 4u + 1u], s_tile_base + RACER_DIR_TILE_BL[d]);
        set_sprite_tile(racer_oam[i * 4u + 2u], s_tile_base + RACER_DIR_TILE_TR[d]);
        set_sprite_tile(racer_oam[i * 4u + 3u], s_tile_base + RACER_DIR_TILE_BR[d]);

        flags = RACER_DIR_FLIP[d];

#ifdef __SDCC
        /* CGB: use sprite palette 1 for racer, with S_PAL(1) in OBJ attribute */
        {
            uint8_t cgb_flags = flags | S_PAL(1u);
            set_sprite_prop(racer_oam[i * 4u + 0u], cgb_flags);
            set_sprite_prop(racer_oam[i * 4u + 1u], cgb_flags);
            set_sprite_prop(racer_oam[i * 4u + 2u], cgb_flags);
            set_sprite_prop(racer_oam[i * 4u + 3u], cgb_flags);
        }
#else
        set_sprite_prop(racer_oam[i * 4u + 0u], flags);
        set_sprite_prop(racer_oam[i * 4u + 1u], flags);
        set_sprite_prop(racer_oam[i * 4u + 2u], flags);
        set_sprite_prop(racer_oam[i * 4u + 3u], flags);
#endif /* __SDCC */

        move_sprite(racer_oam[i * 4u + 0u], hw_x,            hw_y);
        move_sprite(racer_oam[i * 4u + 1u], hw_x,            (uint8_t)(hw_y + 8u));
        move_sprite(racer_oam[i * 4u + 2u], (uint8_t)(hw_x + 8u), hw_y);
        move_sprite(racer_oam[i * 4u + 3u], (uint8_t)(hw_x + 8u), (uint8_t)(hw_y + 8u));
    }
}

#ifndef __SDCC

void racer_spawn_for_test(int16_t px, int16_t py,
                           uint8_t *wp_tx, uint8_t *wp_ty,
                           uint8_t wp_count, uint8_t finish_dir,
                           uint8_t lap_total) {
    uint8_t i;
    for (i = 0u; i < MAX_RACERS; i++) racer_active[i] = 0u;
    racer_active[0] = 1u;
    racer_px[0] = px;
    racer_py[0] = py;
    racer_wp_idx[0] = 0u;
    racer_dir[0] = DIR_T;
    racer_oam[0] = racer_oam[1] = racer_oam[2] = racer_oam[3] = 0u;
    for (i = 0u; i < wp_count && i < MAX_RACER_WAYPOINTS; i++) {
        s_wp_tx[i] = wp_tx[i];
        s_wp_ty[i] = wp_ty[i];
    }
    s_wp_count   = wp_count;
    s_finish_dir = finish_dir;
    s_lap_total  = lap_total;
    s_laps_done  = lap_total;  /* ready to trigger finish detection */
    racer_vx[0] = (int8_t)0;
    racer_vy[0] = (int8_t)0;
    racer_gear[0] = 0u;
    racer_downshift_timer[0] = 0u;
}

void racer_set_laps_done_for_test(uint8_t n) {
    s_laps_done = n;
}

void racer_place_on_finish_for_test(uint8_t tx, uint8_t ty, uint8_t dir) {
    racer_px[0] = (int16_t)((uint16_t)tx * 8u + 4u);
    racer_py[0] = (int16_t)((uint16_t)ty * 8u + 4u);
    racer_dir[0] = dir;
    /* Move waypoint far away so waypoint-advance threshold doesn't interfere */
    s_wp_tx[0] = 200u;
    s_wp_ty[0] = 200u;
    s_wp_count = 1u;
}

void racer_set_wp_idx_for_test(uint8_t slot, uint8_t idx) {
    racer_wp_idx[slot] = idx;
}

void racer_set_pos_for_test(uint8_t slot, int16_t px, int16_t py) {
    racer_px[slot] = px;
    racer_py[slot] = py;
}

uint8_t racer_get_wp_idx(uint8_t slot) {
    return racer_wp_idx[slot];
}

int8_t  racer_get_vx(uint8_t slot)  { return racer_vx[slot]; }
int8_t  racer_get_vy(uint8_t slot)  { return racer_vy[slot]; }
uint8_t racer_get_gear(uint8_t slot) { return racer_gear[slot]; }
int16_t racer_get_px(uint8_t slot)  { return racer_px[slot]; }
int16_t racer_get_py(uint8_t slot)  { return racer_py[slot]; }
void    racer_set_vel_for_test(uint8_t slot, int8_t vx, int8_t vy) {
    racer_vx[slot] = vx;
    racer_vy[slot] = vy;
}
void    racer_set_gear_for_test(uint8_t slot, uint8_t gear) {
    racer_gear[slot] = gear;
}

#endif /* __SDCC */
