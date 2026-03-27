#pragma bank 255
#include <gb/gb.h>
#include "banking.h"
#include "projectile.h"
#include "player.h"
#include "sprite_pool.h"
#include "loader.h"
#include "camera.h"
#include "track.h"
#include "config.h"
BANKREF(projectile)

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

/* ── init ──────────────────────────────────────────────────────────────── */

void projectile_init(void) BANKED {
    uint8_t i;
    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (proj_active[i]) {
            clear_sprite(proj_oam[i]);
        }
        proj_active[i] = 0u;
    }
    proj_cooldown_tick = 0u;
    load_bullet_tiles();
}

/* ── fire ──────────────────────────────────────────────────────────────── */

void projectile_fire(uint8_t scr_x, uint8_t scr_y, player_dir_t dir) BANKED {
    uint8_t i;
    uint8_t oam;

    if (proj_cooldown_tick > 0u) return;   /* still cooling down */

    for (i = 0u; i < MAX_PROJECTILES; i++) {
        if (!proj_active[i]) {
            oam = get_sprite();
            if (oam == SPRITE_POOL_INVALID) return;  /* OAM pool full */

            proj_x[i]      = scr_x;
            proj_y[i]      = scr_y;
            proj_dx[i]     = (int8_t)((int8_t)PROJ_SPEED * player_dir_dx(dir));
            proj_dy[i]     = (int8_t)((int8_t)PROJ_SPEED * player_dir_dy(dir));
            proj_ttl[i]    = PROJ_MAX_TTL;
            proj_owner[i]  = PROJ_OWNER_PLAYER;
            proj_oam[i]    = oam;
            proj_active[i] = 1u;

            set_sprite_tile(oam, PROJ_TILE_BASE);
            proj_cooldown_tick = PROJ_FIRE_COOLDOWN;
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
