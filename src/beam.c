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

static uint8_t s_axis;            /* BEAM_AXIS_H or BEAM_AXIS_V — fixed at fire */
static int16_t s_x0, s_x1;        /* world-pixel damage rect: [x0,x1) x [y0,y1) */
static int16_t s_y0, s_y1;
static int16_t s_lane_px;         /* cross-axis world pixel of the lane — fixed at fire */
static int16_t s_step;            /* +8 or -8 along the lane — fixed at fire */
static int16_t s_nose;            /* along-axis world pixel of the first cell; forward only */
static uint8_t s_lo_tile;         /* LOWEST world tile of the span to draw now */
static uint8_t s_count;           /* cells to draw now, <= BEAM_MAX_CELLS */
static uint8_t s_drawn_lo;        /* LOWEST world tile currently painted */
static uint8_t s_drawn_count;     /* cells currently painted */
static uint8_t s_lane_tile;       /* world tile row (H) or column (V) to re-stream */

static uint8_t s_cell_buf[BEAM_MAX_CELLS];

/* Raycast from world pixel `nose` along s_step on the fixed lane. Returns the
 * cell count and writes the LOWEST world tile of the span to *lo. One tile per
 * step, so no cell is skipped. A nose outside the screen clip returns 0, which
 * is what keeps the *lo shift below out of negative coordinates. */
static uint8_t beam_cast(int16_t nose, uint8_t *lo) {
    int16_t vis_lo, vis_hi, p, x, y;
    uint8_t n = 0u;
    uint8_t is_h = (s_axis == (uint8_t)BEAM_AXIS_H) ? 1u : 0u;

    if (is_h) {
        vis_lo = (int16_t)cam_x;
        vis_hi = (int16_t)((int16_t)cam_x + 159);
    } else {
        vis_lo = (int16_t)cam_y;
        vis_hi = (int16_t)((int16_t)cam_y + (int16_t)HUD_SCANLINE - 1);
    }

    p = nose;
    while (n < (uint8_t)BEAM_MAX_CELLS) {
        if (p < vis_lo || p > vis_hi) break;
        if (is_h) { x = p;         y = s_lane_px; }
        else      { x = s_lane_px; y = p;         }
        if (!track_passable(x, y)) break;
        n++;
        p = (int16_t)(p + s_step);
    }

    if (n == 0u) { *lo = 0u; return 0u; }
    if (s_step > 0) {
        *lo = (uint8_t)((uint16_t)nose >> 3u);
    } else {
        *lo = (uint8_t)((uint16_t)(int16_t)(nose + (int16_t)(s_step * (int16_t)(n - 1u))) >> 3u);
    }
    return n;
}

/* Paint the current span. set_bkg_tiles writes ascending, so the origin is the
 * LOWEST world tile of the span, never the first cell probed. */
static void beam_paint(void) {
    uint8_t vx = (uint8_t)(((s_axis == (uint8_t)BEAM_AXIS_H) ? s_lo_tile : s_lane_tile) & 31u);
    uint8_t vy = (uint8_t)(((s_axis == (uint8_t)BEAM_AXIS_H) ? s_lane_tile : s_lo_tile) & 31u);
    uint8_t first;

    if (s_axis == (uint8_t)BEAM_AXIS_H) {
        if ((uint8_t)(vx + s_count) > 32u) {
            first = (uint8_t)(32u - vx);
            set_bkg_tiles(vx, vy, first, 1u, s_cell_buf);
            set_bkg_tiles(0u, vy, (uint8_t)(s_count - first), 1u, s_cell_buf + first);
        } else {
            set_bkg_tiles(vx, vy, s_count, 1u, s_cell_buf);
        }
    } else {
        if ((uint8_t)(vy + s_count) > 32u) {
            first = (uint8_t)(32u - vy);
            set_bkg_tiles(vx, vy, 1u, first, s_cell_buf);
            set_bkg_tiles(vx, 0u, 1u, (uint8_t)(s_count - first), s_cell_buf + first);
        } else {
            set_bkg_tiles(vx, vy, 1u, s_count, s_cell_buf);
        }
    }
}

void beam_reset(void) BANKED {
    s_cooldown    = 0u;
    s_dmg_window  = 0u;
    s_vis_frames  = 0u;
    s_dirty       = 0u;
    s_count       = 0u;
    s_drawn_count = 0u;
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
    uint8_t n, lo, i;
    uint8_t seg_tile;

    if (!s_equipped)                return 0u;
    if (!beam_dir_is_cardinal(dir)) return 0u;
    if (s_cooldown > 0u)            return 0u;
    if (s_dirty)                    return 0u;

    cx = (int16_t)(px + 8);   /* car centre — px/py are the 16x16 top-left */
    cy = (int16_t)(py + 8);

    step_x = (int16_t)player_dir_dx((player_dir_t)dir) * 8;
    step_y = (int16_t)player_dir_dy((player_dir_t)dir) * 8;

    /* The axis, the lane and the direction are fixed for the whole pulse (R3). */
    if (step_y == 0) {
        s_axis    = (uint8_t)BEAM_AXIS_H;
        s_step    = step_x;
        s_lane_px = cy;
        s_nose    = (int16_t)(cx + step_x);
        seg_tile  = (uint8_t)(s_tile_base + (uint8_t)BEAM_TILE_OFS_H);
    } else {
        s_axis    = (uint8_t)BEAM_AXIS_V;
        s_step    = step_y;
        s_lane_px = cx;
        s_nose    = (int16_t)(cy + step_y);
        seg_tile  = (uint8_t)(s_tile_base + (uint8_t)BEAM_TILE_OFS_V);
    }
    s_lane_tile = (uint8_t)((uint16_t)s_lane_px >> 3u);

    /* Fill the whole buffer once: the span can grow later in the pulse when the
     * screen edge scrolls away from the car. */
    for (i = 0u; i < (uint8_t)BEAM_MAX_CELLS; i++) s_cell_buf[i] = seg_tile;

    n         = beam_cast(s_nose, &lo);
    s_count   = n;
    s_lo_tile = lo;

    s_cooldown   = (uint8_t)LASER_FIRE_COOLDOWN;
    s_dmg_window = 1u;                          /* closed by beam_update() */
    sfx_play(SFX_SHOOT);

    if (n == 0u) {
        /* Wall flush against the muzzle: the shot still costs a cooldown, but
         * paints nothing and hits nothing. beam_hit_damage() guards on n. */
        s_vis_frames  = 0u;
        s_dirty       = 0u;
        s_drawn_count = 0u;
        return 1u;
    }

    /* Damage rect == the span of THIS frame, and of no later frame (R8). */
    if (s_axis == (uint8_t)BEAM_AXIS_H) {
        s_x0 = (int16_t)((uint16_t)lo * 8u);
        s_x1 = (int16_t)(s_x0 + (int16_t)((uint16_t)n * 8u));
        s_y0 = (int16_t)(s_lane_px - (int16_t)BEAM_LANE_HALF);
        s_y1 = (int16_t)(s_lane_px + (int16_t)BEAM_LANE_HALF);
    } else {
        s_y0 = (int16_t)((uint16_t)lo * 8u);
        s_y1 = (int16_t)(s_y0 + (int16_t)((uint16_t)n * 8u));
        s_x0 = (int16_t)(s_lane_px - (int16_t)BEAM_LANE_HALF);
        s_x1 = (int16_t)(s_lane_px + (int16_t)BEAM_LANE_HALF);
    }

    s_vis_frames  = (uint8_t)BEAM_VISIBLE_FRAMES;
    s_dirty       = 1u;
    s_drawn_count = 0u;                         /* nothing painted yet */
    return 1u;
}

uint8_t beam_hit_damage(int16_t ex, int16_t ey, uint8_t box) BANKED {
    int16_t b;
    if (!s_dmg_window)      return 0u;
    if (s_count == 0u)      return 0u;
    b = (int16_t)box;
    /* AABB overlap against the lane rect. No consumption: pierce. */
    if (ex + b > s_x0 && ex < s_x1 &&
        ey + b > s_y0 && ey < s_y1) {
        return (uint8_t)WEAPON1_LASER_DAMAGE;
    }
    return 0u;
}

void beam_update(int16_t px, int16_t py) BANKED {
    if (s_cooldown > 0u)   s_cooldown--;
    s_dmg_window = 0u;                           /* exactly one frame */
    if (s_vis_frames > 0u) s_vis_frames--;

    if (s_vis_frames > 0u) {
        /* Live pulse: re-aim the start at the car nose and re-measure the
         * length. The start moves only along the shot direction, and never
         * backwards, so a reversing car opens a gap instead of dragging the
         * beam back (R2). */
        int16_t nose;
        uint8_t lo;
        if (s_axis == (uint8_t)BEAM_AXIS_H) {
            nose = (int16_t)(px + 8 + s_step);
        } else {
            nose = (int16_t)(py + 8 + s_step);
        }
        if (s_step > 0) {
            if (nose > s_nose) s_nose = nose;
        } else {
            if (nose < s_nose) s_nose = nose;
        }
        s_count   = beam_cast(s_nose, &lo);
        s_lo_tile = lo;
        return;
    }

    s_count = 0u;                                /* the pulse is over */
    if (s_dirty) {
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
        if (queued) s_dirty = 0u;
    }
}

void beam_render(void) BANKED {
    if (s_vis_frames == 0u) {
        /* The pulse ended. beam_update() queued the whole-lane repair, which
         * owns every cell this pulse painted (R7). */
        s_drawn_count = 0u;
        return;
    }
    if (s_count > 0u) beam_paint();
    s_drawn_lo    = s_lo_tile;
    s_drawn_count = s_count;
}
