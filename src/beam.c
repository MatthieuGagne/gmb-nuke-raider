#pragma bank 255
#include <gb/gb.h>
#include "beam.h"
#include "camera.h"
#include "track.h"
#include "player.h"
#include "sfx.h"
#include "config.h"

BANKREF(beam)

/* Single instance, not a pool: one player, one beam. Same shape as
 * proj_cooldown_tick in projectile.c. */
static uint8_t s_tile_base;
static uint8_t s_equipped;
static uint8_t s_cooldown;        /* frames until the next pulse may fire */
static uint8_t s_dmg_window;      /* 1 only on the fire frame */
static uint8_t s_vis_frames;      /* frames the lane stays painted */
static uint8_t s_dirty;           /* BG cells painted, restore still owed */

static uint8_t s_axis;            /* BEAM_AXIS_H or BEAM_AXIS_V */
static int16_t s_x0, s_x1;        /* world-pixel damage rect: [x0,x1) x [y0,y1) */
static int16_t s_y0, s_y1;
static uint8_t s_cell_tx;         /* LOWEST world tile x of the painted span */
static uint8_t s_cell_ty;         /* LOWEST world tile y of the painted span */
static uint8_t s_cell_count;      /* BG cells painted, <= BEAM_MAX_CELLS */
static uint8_t s_lane_tile;       /* world tile row (H) or column (V) to re-stream */

static uint8_t s_cell_buf[BEAM_MAX_CELLS];

void beam_reset(void) BANKED {
    s_cooldown   = 0u;
    s_dmg_window = 0u;
    s_vis_frames = 0u;
    s_dirty      = 0u;
    s_cell_count = 0u;
    s_x0 = s_x1 = s_y0 = s_y1 = 0;
}

void beam_init(uint8_t tile_base) BANKED {
    s_tile_base = tile_base;
    s_equipped  = 0u;
    beam_reset();
}

void beam_set_equipped(uint8_t is_laser) BANKED { s_equipped = is_laser ? 1u : 0u; }
uint8_t beam_is_equipped(void) BANKED           { return s_equipped; }

uint8_t beam_dir_is_cardinal(uint8_t dir) BANKED {
    /* DIR_T=0, DIR_R=2, DIR_B=4, DIR_L=6 — the even values of the low octant.
     * Odd values are the 45-degree diagonals; 8..15 are turret-only sectors.
     * This guard must stay BEFORE player_dir_dx(), whose table is only 8 wide. */
    return (dir <= (uint8_t)DIR_L && (dir & 1u) == 0u) ? 1u : 0u;
}

uint8_t beam_fire(int16_t px, int16_t py, uint8_t dir) BANKED {
    int16_t cx, cy;
    int16_t step_x, step_y;
    int16_t x, y;
    int16_t vis_lo, vis_hi;
    int16_t lo;
    uint8_t n;
    uint8_t seg_tile;
    uint8_t is_h;     /* local mirror of s_axis — a static reload per raycast
                       * iteration is an absolute load on z80; this is a stack
                       * slot the register allocator can keep live. */

    if (!s_equipped)                return 0u;
    if (!beam_dir_is_cardinal(dir)) return 0u;
    if (s_cooldown > 0u)            return 0u;
    if (s_dirty)                    return 0u;

    cx = (int16_t)(px + 8);   /* car centre — px/py are the 16x16 top-left */
    cy = (int16_t)(py + 8);

    step_x = (int16_t)player_dir_dx((player_dir_t)dir) * 8;
    step_y = (int16_t)player_dir_dy((player_dir_t)dir) * 8;

    is_h     = (step_y == 0) ? 1u : 0u;
    s_axis   = is_h ? (uint8_t)BEAM_AXIS_H : (uint8_t)BEAM_AXIS_V;
    seg_tile = (uint8_t)(s_tile_base + (is_h ? (uint8_t)BEAM_TILE_OFS_H
                                             : (uint8_t)BEAM_TILE_OFS_V));

    /* Screen clip, in world coordinates. */
    if (is_h) {
        vis_lo = (int16_t)cam_x;
        vis_hi = (int16_t)((int16_t)cam_x + 159);
    } else {
        vis_lo = (int16_t)cam_y;
        vis_hi = (int16_t)((int16_t)cam_y + (int16_t)HUD_SCANLINE - 1);
    }

    /* Raycast one tile per step, starting one cell AHEAD of the car.
     * Step magnitude is 8 == tile size, so no cell is skipped. */
    x = (int16_t)(cx + step_x);
    y = (int16_t)(cy + step_y);
    n = 0u;
    while (n < (uint8_t)BEAM_MAX_CELLS) {
        int16_t probe = is_h ? x : y;
        if (probe < vis_lo || probe > vis_hi)  break;
        if (!track_passable(x, y))             break;
        s_cell_buf[n] = seg_tile;
        n++;
        x = (int16_t)(x + step_x);
        y = (int16_t)(y + step_y);
    }
    s_cell_count = n;

    s_cooldown   = (uint8_t)LASER_FIRE_COOLDOWN;
    s_dmg_window = 1u;                          /* closed by beam_update() */
    sfx_play(SFX_SHOOT);

    if (n == 0u) {
        /* Wall flush against the muzzle: the shot still costs a cooldown, but
         * paints nothing and hits nothing. beam_hit_damage() guards on n. */
        s_vis_frames = 0u;
        s_dirty      = 0u;
        return 1u;
    }

    /* Origin = the LOWEST world coordinate of the swept span, because
     * set_bkg_tiles writes ascending. For DIR_R / DIR_B that is the first cell
     * probed; for DIR_L / DIR_T it is the last. x/y sit one step past the final
     * painted cell, so backing off one step recovers it. */
    if (is_h) {
        lo = (step_x > 0) ? (int16_t)(cx + step_x) : (int16_t)(x - step_x);
        s_cell_tx   = (uint8_t)((uint16_t)lo >> 3u);
        s_cell_ty   = (uint8_t)((uint16_t)cy >> 3u);
        s_lane_tile = s_cell_ty;
        /* Damage rect == the painted span exactly. */
        s_x0 = (int16_t)((uint16_t)s_cell_tx * 8u);
        s_x1 = (int16_t)(s_x0 + (int16_t)((uint16_t)n * 8u));
        s_y0 = (int16_t)(cy - (int16_t)BEAM_LANE_HALF);
        s_y1 = (int16_t)(cy + (int16_t)BEAM_LANE_HALF);
    } else {
        lo = (step_y > 0) ? (int16_t)(cy + step_y) : (int16_t)(y - step_y);
        s_cell_ty   = (uint8_t)((uint16_t)lo >> 3u);
        s_cell_tx   = (uint8_t)((uint16_t)cx >> 3u);
        s_lane_tile = s_cell_tx;
        s_y0 = (int16_t)((uint16_t)s_cell_ty * 8u);
        s_y1 = (int16_t)(s_y0 + (int16_t)((uint16_t)n * 8u));
        s_x0 = (int16_t)(cx - (int16_t)BEAM_LANE_HALF);
        s_x1 = (int16_t)(cx + (int16_t)BEAM_LANE_HALF);
    }

    s_vis_frames = (uint8_t)BEAM_VISIBLE_FRAMES;
    s_dirty      = 1u;
    return 1u;
}

uint8_t beam_hit_damage(int16_t ex, int16_t ey, uint8_t box) BANKED {
    int16_t b;
    if (!s_dmg_window)      return 0u;
    if (s_cell_count == 0u) return 0u;
    b = (int16_t)box;
    /* AABB overlap against the lane rect. No consumption: pierce. */
    if (ex + b > s_x0 && ex < s_x1 &&
        ey + b > s_y0 && ey < s_y1) {
        return (uint8_t)WEAPON1_LASER_DAMAGE;
    }
    return 0u;
}

void beam_update(void) BANKED {
    if (s_cooldown > 0u)   s_cooldown--;
    s_dmg_window = 0u;                           /* exactly one frame */
    if (s_vis_frames > 0u) s_vis_frames--;
    if (s_vis_frames == 0u && s_dirty) {
        /* Repair the lane. Retry on a later frame if the queue was full —
         * camera_flush_vram() zeroes both lengths every render phase.
         *
         * if/else, NOT a ternary: both arms are BANKED calls, and SDCC mangles
         * the return register when BANKED calls meet in a ternary. */
        uint8_t queued;
        if (s_axis == (uint8_t)BEAM_AXIS_H) {
            queued = camera_invalidate_row(s_lane_tile);
        } else {
            queued = camera_invalidate_col(s_lane_tile);
        }
        if (queued) {
            s_dirty      = 0u;
            s_cell_count = 0u;
        }
    }
}

void beam_render(void) BANKED {
    uint8_t vx, vy, first;

    if (s_vis_frames == 0u || s_cell_count == 0u) return;

    vx = (uint8_t)(s_cell_tx & 31u);
    vy = (uint8_t)(s_cell_ty & 31u);

    if (s_axis == (uint8_t)BEAM_AXIS_H) {
        if ((uint8_t)(vx + s_cell_count) > 32u) {
            first = (uint8_t)(32u - vx);
            set_bkg_tiles(vx, vy, first, 1u, s_cell_buf);
            set_bkg_tiles(0u, vy, (uint8_t)(s_cell_count - first), 1u, s_cell_buf + first);
        } else {
            set_bkg_tiles(vx, vy, s_cell_count, 1u, s_cell_buf);
        }
    } else {
        if ((uint8_t)(vy + s_cell_count) > 32u) {
            first = (uint8_t)(32u - vy);
            set_bkg_tiles(vx, vy, 1u, first, s_cell_buf);
            set_bkg_tiles(vx, 0u, 1u, (uint8_t)(s_cell_count - first), s_cell_buf + first);
        } else {
            set_bkg_tiles(vx, vy, 1u, s_cell_count, s_cell_buf);
        }
    }
}
