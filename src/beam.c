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
static uint8_t s_lane_repair;     /* 1 = the whole lane needs a restream; queued in beam_update() */

/* beam_cast() memo — see the comment inside beam_cast() for the invariant.
 * Reset (s_cast_memo_ok = 0) at the start of every new pulse in beam_fire(). */
static uint8_t s_cast_memo_ok;
static int16_t s_cast_nose;
static int16_t s_cast_vis_lo;
static int16_t s_cast_vis_hi;
static uint8_t s_cast_n;
static uint8_t s_cast_lo;

static uint8_t s_cell_buf[BEAM_MAX_CELLS];

/* Raycast from world pixel `nose` along s_step on the fixed lane. Returns the
 * cell count and writes the LOWEST world tile of the span to *lo. One tile per
 * step, so no cell is skipped. A nose outside the screen clip returns 0, which
 * is what keeps the *lo shift below out of negative coordinates.
 *
 * The scan is the hot cost: up to BEAM_MAX_CELLS calls to track_passable(),
 * each paging the ROM bank twice via loader_map_read_byte(). s_axis, s_step and
 * s_lane_px are fixed for the whole pulse (R3), so nose/vis_lo/vis_hi are the
 * ONLY inputs that can change the result from one call to the next. When all
 * three repeat — car and camera both idle along the beam axis, e.g. the "start
 * never moves backwards" case in beam_update() — the scan is skipped and the
 * previous result is reused verbatim; this is memoizing a pure function on
 * identical inputs, so it cannot change what gets drawn (#582). */
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

    if (s_cast_memo_ok && nose == s_cast_nose &&
        vis_lo == s_cast_vis_lo && vis_hi == s_cast_vis_hi) {
        *lo = s_cast_lo;
        return s_cast_n;
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

    s_cast_memo_ok = 1u;
    s_cast_nose    = nose;
    s_cast_vis_lo  = vis_lo;
    s_cast_vis_hi  = vis_hi;

    if (n == 0u) {
        *lo = 0u;
        s_cast_n  = 0u;
        s_cast_lo = 0u;
        return 0u;
    }
    if (s_step > 0) {
        *lo = (uint8_t)((uint16_t)nose >> 3u);
    } else {
        *lo = (uint8_t)((uint16_t)(int16_t)(nose + (int16_t)(s_step * (int16_t)(n - 1u))) >> 3u);
    }
    s_cast_n  = n;
    s_cast_lo = *lo;
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
    s_lane_repair = 0u;
    s_cast_memo_ok = 0u;
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

    /* A new pulse can flip axis, lane and step, so a stale memo from the
     * previous pulse must never be reused even if nose/vis happen to match. */
    s_cast_memo_ok = 0u;
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
        s_lane_repair = 0u;
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
    s_lane_repair = 0u;
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

        if (s_lane_repair) {
            /* This runs after camera_update(), which is what makes queueing
             * legal here (src/camera.h:53). if/else, NOT a ternary: both arms
             * are BANKED calls. */
            uint8_t queued;
            if (s_axis == (uint8_t)BEAM_AXIS_H) {
                queued = camera_invalidate_row(s_lane_tile);
            } else {
                queued = camera_invalidate_col(s_lane_tile);
            }
            if (queued) s_lane_repair = 0u;
        }

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
        if (queued) {
            s_dirty       = 0u;
            s_lane_repair = 0u;
        }
    }
}

/* Repaint the cells that left the span since the last painted frame (R5, R6).
 * At top speed the car crosses at most one tile boundary per frame, and the
 * screen edge moves at most one tile per frame, so each run is one cell. A run
 * longer than CAMERA_REPAIR_MAX_CELLS cannot happen while the car drives; if
 * one appears, fall back to the whole lane rather than write 22 cells in one
 * VBlank. */
static void beam_repair_leaving(void) {
    uint8_t a  = s_drawn_lo;
    uint8_t pc = s_drawn_count;
    uint8_t b  = s_lo_tile;
    uint8_t nc = s_count;
    uint8_t lo_n     = 0u;
    uint8_t hi_n     = 0u;
    uint8_t hi_start = 0u;

    if (nc == 0u) {
        lo_n = pc;                                  /* the whole span left (R9) */
    } else {
        if (b > a) {
            lo_n = (uint8_t)(b - a);                /* the near end moved forward */
            if (lo_n > pc) lo_n = pc;
        }
        if ((uint8_t)(b + nc) < (uint8_t)(a + pc)) {
            if ((uint8_t)(b + nc) > a) hi_start = (uint8_t)(b + nc);
            else                       hi_start = a;
            hi_n = (uint8_t)((uint8_t)(a + pc) - hi_start);
        }
    }

    if (lo_n > (uint8_t)CAMERA_REPAIR_MAX_CELLS ||
        hi_n > (uint8_t)CAMERA_REPAIR_MAX_CELLS) {
        /* Raise the flag only. camera_invalidate_row/col must not run in the
         * render phase: queueing before camera_update() makes the camera drop
         * its own scroll stream (src/camera.h:53). beam_update() drains this. */
        s_lane_repair = 1u;
        return;
    }

    if (lo_n > 0u) {
        if (s_axis == (uint8_t)BEAM_AXIS_H) {
            camera_repair_cells(a, s_lane_tile, lo_n, 0u);
        } else {
            camera_repair_cells(s_lane_tile, a, lo_n, 1u);
        }
    }
    if (hi_n > 0u) {
        if (s_axis == (uint8_t)BEAM_AXIS_H) {
            camera_repair_cells(hi_start, s_lane_tile, hi_n, 0u);
        } else {
            camera_repair_cells(s_lane_tile, hi_start, hi_n, 1u);
        }
    }
}

void beam_render(void) BANKED {
    if (s_vis_frames == 0u) {
        /* The pulse ended. beam_update() queued the whole-lane repair, which
         * owns every cell this pulse painted (R7). */
        s_drawn_count = 0u;
        return;
    }
    if (s_drawn_count > 0u) beam_repair_leaving();
    if (s_count > 0u)       beam_paint();
    s_drawn_lo    = s_lo_tile;
    s_drawn_count = s_count;
}
