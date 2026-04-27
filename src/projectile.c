#pragma bank 255
#include <gb/gb.h>
#include "banking.h"
#include "projectile.h"
#include "player.h"
#include "sprite_pool.h"
#include "camera.h"
#include "track.h"
#include "config.h"
#include "sfx.h"  /* sfx_play is NONBANKED (bank 0) — safe to call from any bank */
BANKREF(projectile)

/* ── Direction velocity tables ──────────────────────────────────────────── */
/* Maps player_dir_t (0-15) to bullet pixel velocity per frame.
 * Entries 0-7 match PROJ_SPEED * DIR_DX/DY (player directions, unchanged).
 * Entries 8-15 are turret-only intermediate directions at 22.5° steps. */
static const int8_t PROJ_VEL_DX[16] = {
    /*  0 DIR_T   */  0,
    /*  1 DIR_RT  */  4,
    /*  2 DIR_R   */  4,
    /*  3 DIR_RB  */  4,
    /*  4 DIR_B   */  0,
    /*  5 DIR_LB  */ -4,
    /*  6 DIR_L   */ -4,
    /*  7 DIR_LT  */ -4,
    /*  8 DIR_NNE */  2,
    /*  9 DIR_ENE */  4,
    /* 10 DIR_ESE */  4,
    /* 11 DIR_SSE */  2,
    /* 12 DIR_SSW */ -2,
    /* 13 DIR_WSW */ -4,
    /* 14 DIR_WNW */ -4,
    /* 15 DIR_NNW */ -2,
};
static const int8_t PROJ_VEL_DY[16] = {
    /*  0 DIR_T   */ -4,
    /*  1 DIR_RT  */ -4,
    /*  2 DIR_R   */  0,
    /*  3 DIR_RB  */  4,
    /*  4 DIR_B   */  4,
    /*  5 DIR_LB  */  4,
    /*  6 DIR_L   */  0,
    /*  7 DIR_LT  */ -4,
    /*  8 DIR_NNE */ -4,
    /*  9 DIR_ENE */ -2,
    /* 10 DIR_ESE */  2,
    /* 11 DIR_SSE */  4,
    /* 12 DIR_SSW */  4,
    /* 13 DIR_WSW */  2,
    /* 14 DIR_WNW */ -2,
    /* 15 DIR_NNW */ -4,
};

/* ── SoA bullet pool ───────────────────────────────────────────────────── */
static uint8_t proj_x[MAX_PROJECTILES];
static uint8_t proj_y[MAX_PROJECTILES];
static int8_t  proj_dx[MAX_PROJECTILES];   /* px/frame, signed */
static int8_t  proj_dy[MAX_PROJECTILES];
static uint8_t proj_active[MAX_PROJECTILES];
static uint8_t proj_owner[MAX_PROJECTILES];
static uint8_t proj_ttl[MAX_PROJECTILES];
static uint8_t proj_oam[MAX_PROJECTILES];  /* OAM slot assigned to each bullet */

static uint8_t proj_cooldown_tick = 0u;    /* frames until next fire is allowed */
static uint8_t s_proj_tile_base   = 0u;    /* VRAM sprite tile slot, set by projectile_init() */

/* ── init ──────────────────────────────────────────────────────────────── */

void projectile_init(uint8_t tile_base) BANKED {
    uint8_t i;
    s_proj_tile_base = tile_base;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (proj_active[i]) {
            clear_sprite(proj_oam[i]);
        }
        proj_active[i] = 0u;
    }
    proj_cooldown_tick = 0u;
}

/* ── fire ──────────────────────────────────────────────────────────────── */

void projectile_fire(uint8_t scr_x, uint8_t scr_y, player_dir_t dir, uint8_t owner) BANKED {
    uint8_t i;
    uint8_t oam;

    /* Cooldown applies to player only — enemy turrets fire on their own timers */
    if (owner == PROJ_OWNER_PLAYER && proj_cooldown_tick > 0u) return;

    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (!proj_active[i]) {
            oam = get_sprite();
            if (oam == SPRITE_POOL_INVALID) return;  /* OAM pool full */

            proj_x[i]      = scr_x;
            proj_y[i]      = scr_y;
            proj_dx[i]     = PROJ_VEL_DX[(uint8_t)dir];
            proj_dy[i]     = PROJ_VEL_DY[(uint8_t)dir];
            proj_ttl[i]    = PROJ_MAX_TTL;
            proj_owner[i]  = owner;
            proj_oam[i]    = oam;
            proj_active[i] = 1u;

            set_sprite_tile(oam, s_proj_tile_base);
            if (owner == PROJ_OWNER_PLAYER) {
                proj_cooldown_tick = PROJ_FIRE_COOLDOWN;
            }
            sfx_play(SFX_SHOOT);  /* fire SFX exactly once per actual projectile spawn */
            return;
        }
    }
}

/* ── update ────────────────────────────────────────────────────────────── */

void projectile_update(void) BANKED {
    uint8_t  i;
    uint8_t  nx;
    uint8_t  ny;
    int16_t  world_x;
    int16_t  world_y;

    if (proj_cooldown_tick > 0u) proj_cooldown_tick--;

    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (!proj_active[i]) continue;

        /* Advance position */
        nx = (uint8_t)((int16_t)proj_x[i] + (int16_t)proj_dx[i]);
        ny = (uint8_t)((int16_t)proj_y[i] + (int16_t)proj_dy[i]);

        /* Convert destination screen coords → world pixel coords.
         * world_x = scr_x - 8  (GBDK OAM X has 8px left margin)
         * world_y = scr_y + cam_y - 16  (GBDK OAM Y has 16px top margin) */
        world_x = (int16_t)nx - 8;
        world_y = (int16_t)ny + (int16_t)cam_y - 16;

        /* Despawn: wall hit, screen boundary, or max-range cap expired.
         * Wall check is first — track_passable returns 0 for out-of-bounds,
         * naturally covering extreme positions before boundary math. */
        if (!track_passable(world_x, world_y) ||
                nx < 8u || nx >= 168u ||
                ny < 16u || ny >= HUD_SCANLINE ||
                proj_ttl[i] == 0u) {
            clear_sprite(proj_oam[i]);
            proj_active[i] = 0u;
            continue;
        }

        proj_ttl[i]--;
        proj_x[i] = nx;
        proj_y[i] = ny;
    }
}

/* ── render ────────────────────────────────────────────────────────────── */

void projectile_render(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (proj_active[i]) {
            move_sprite(proj_oam[i], proj_x[i], proj_y[i]);
        }
    }
}

/* ── hit detection ─────────────────────────────────────────────────────── */

uint8_t projectile_check_hit_player(uint8_t cx, uint8_t cy, uint8_t r) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        int16_t dx, dy;
        if (!proj_active[i]) continue;
        if (proj_owner[i] != PROJ_OWNER_ENEMY) continue;
        dx = (int16_t)proj_x[i] - (int16_t)cx;
        dy = (int16_t)proj_y[i] - (int16_t)cy;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if ((uint8_t)dx <= r && (uint8_t)dy <= r) {
            proj_active[i] = 0u;
            clear_sprite(proj_oam[i]);
            return 1u;
        }
    }
    return 0u;
}

uint8_t projectile_check_hit_enemy(uint8_t cx, uint8_t cy, uint8_t r) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        int16_t dx, dy;
        if (!proj_active[i]) continue;
        if (proj_owner[i] != PROJ_OWNER_PLAYER) continue;
        dx = (int16_t)proj_x[i] - (int16_t)cx;
        dy = (int16_t)proj_y[i] - (int16_t)cy;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if ((uint8_t)dx <= r && (uint8_t)dy <= r) {
            proj_active[i] = 0u;
            clear_sprite(proj_oam[i]);
            return 1u;
        }
    }
    return 0u;
}

/* ── test/debug accessors ─────────────────────────────────────────────── */

uint8_t projectile_count_active(void) BANKED {
    uint8_t i;
    uint8_t count = 0u;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (proj_active[i]) count++;
    }
    return count;
}

uint8_t projectile_get_x(uint8_t slot) BANKED {
    if (slot >= MAX_PROJECTILES) return 0u;
    return proj_x[slot];
}

uint8_t projectile_get_y(uint8_t slot) BANKED {
    if (slot >= MAX_PROJECTILES) return 0u;
    return proj_y[slot];
}
