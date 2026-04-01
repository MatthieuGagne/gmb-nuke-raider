#pragma bank 255
#include <gb/gb.h>
#include "camera.h"
#include "track.h"

volatile uint16_t cam_y;
volatile uint8_t  cam_scy_shadow;
volatile uint16_t cam_x;
volatile uint8_t  cam_scx_shadow;

/* Clamp signed v to [0, max]. */
static uint16_t clamp_cam(int16_t v, uint16_t max) {
    if (v < 0) return 0u;
    if ((uint16_t)v > max) return max;
    return (uint16_t)v;
}

/* cam_max_y = active_map_h * 8 - 144 (computed inline — cheaper than WRAM var) */
/* cam_max_x = active_map_w * 8 - 160 (computed inline) */

/* --- Row streaming ------------------------------------------------------- */

#define VIS_COLS 22u   /* visible tile columns: ceil(160/8) + 1 for partial */
#define VIS_ROWS 19u   /* visible tile rows:    ceil(144/8) + 1 for partial */

static uint8_t row_buf[VIS_COLS];

/* Snapshot of cam_tile_x captured at camera_update() time.
 * camera_flush_vram() uses this — never the live cam_x — to avoid stale writes. */
static uint8_t cam_tile_x_snap;

static void stream_row(uint8_t world_ty) {
    uint8_t vram_y = world_ty & 31u;
    uint8_t vram_x = cam_tile_x_snap & 31u;
    uint8_t first_count;
    track_fill_row_range(world_ty, cam_tile_x_snap, VIS_COLS, row_buf);
    if ((uint8_t)(vram_x + VIS_COLS) > 32u) {
        /* Window crosses BG ring boundary — split into two calls */
        first_count = 32u - vram_x;
        set_bkg_tiles(vram_x, vram_y, first_count, 1u, row_buf);
        set_bkg_tiles(0u,     vram_y, VIS_COLS - first_count, 1u, row_buf + first_count);
    } else {
        set_bkg_tiles(vram_x, vram_y, VIS_COLS, 1u, row_buf);
    }
}

/* --- Column streaming ---------------------------------------------------- */

static uint8_t col_buf[VIS_ROWS];

static void stream_col(uint8_t world_tx) {
    uint8_t cam_tile_y = (uint8_t)(cam_y >> 3u);
    uint8_t vram_x = world_tx & 31u;
    uint8_t vram_y = cam_tile_y & 31u;
    uint8_t first_count;
    track_fill_col(world_tx, cam_tile_y, VIS_ROWS, col_buf);
    if ((uint8_t)(vram_y + VIS_ROWS) > 32u) {
        first_count = 32u - vram_y;
        set_bkg_tiles(vram_x, vram_y, 1u, first_count, col_buf);
        set_bkg_tiles(vram_x, 0u,     1u, VIS_ROWS - first_count, col_buf + first_count);
    } else {
        set_bkg_tiles(vram_x, vram_y, 1u, VIS_ROWS, col_buf);
    }
}

/* --- Stream buffers ------------------------------------------------------ */
/* Capped at 1 event per axis per VBlank — player cannot cross more than
 * one tile boundary per axis per frame at max speed (8px/frame = 1 tile). */
#define STREAM_BUF_SIZE 2u

static uint8_t stream_row_buf[STREAM_BUF_SIZE];
static uint8_t stream_row_buf_len = 0u;

static uint8_t stream_col_buf[STREAM_BUF_SIZE];
static uint8_t stream_col_buf_len = 0u;

/* --- Public API ---------------------------------------------------------- */

void camera_init(int16_t player_world_x, int16_t player_world_y) BANKED {
    uint8_t ty;
    uint8_t first_row;
    uint16_t cam_max_x;
    uint16_t cam_max_y;

    stream_row_buf_len = 0u;
    stream_col_buf_len = 0u;

    cam_max_y = (uint16_t)active_map_h * 8u - 144u;
    cam_max_x = (active_map_w > 20u) ? ((uint16_t)active_map_w * 8u - 160u) : 0u;

    cam_y = clamp_cam(player_world_y - 72, cam_max_y);
    cam_x = clamp_cam(player_world_x - 80, cam_max_x);

    first_row = (uint8_t)(cam_y >> 3u);
    cam_tile_x_snap = (uint8_t)(cam_x >> 3u);

    for (ty = first_row; ty < first_row + 18u && ty < active_map_h; ty++) {
        stream_row(ty);
    }
}

void camera_update(int16_t player_world_x, int16_t player_world_y) BANKED {
    uint16_t ncy;
    uint16_t ncx;
    uint16_t cam_max_x;
    uint16_t cam_max_y;
    uint8_t old_top, new_top;
    uint8_t old_bot, new_bot;
    uint8_t old_left, new_left;
    uint8_t old_right, new_right;

    cam_max_y = (uint16_t)active_map_h * 8u - 144u;
    cam_max_x = (active_map_w > 20u) ? ((uint16_t)active_map_w * 8u - 160u) : 0u;

    ncy = clamp_cam(player_world_y - 72, cam_max_y);
    ncx = clamp_cam(player_world_x - 80, cam_max_x);

    /* Y: buffer row events (cap at 1 per VBlank — player can't cross >1 tile/frame) */
    if (ncy < cam_y) {
        old_top = (uint8_t)(cam_y >> 3u);
        new_top = (uint8_t)(ncy >> 3u);
        if (new_top != old_top && stream_row_buf_len < 1u) {
            stream_row_buf[stream_row_buf_len] = new_top;
            stream_row_buf_len++;
        }
    } else if (ncy > cam_y) {
        old_bot = (uint8_t)((cam_y + 143u) >> 3u);
        new_bot = (uint8_t)((ncy + 143u) >> 3u);
        if (new_bot != old_bot && new_bot < active_map_h && stream_row_buf_len < 1u) {
            stream_row_buf[stream_row_buf_len] = new_bot;
            stream_row_buf_len++;
        }
    }
    cam_y = ncy;

    /* X: buffer column events (cap at 1 per VBlank) */
    if (ncx < cam_x) {
        old_left = (uint8_t)(cam_x >> 3u);
        new_left = (uint8_t)(ncx >> 3u);
        if (new_left != old_left && stream_col_buf_len < 1u) {
            stream_col_buf[stream_col_buf_len] = new_left;
            stream_col_buf_len++;
        }
    } else if (ncx > cam_x) {
        old_right = (uint8_t)((cam_x + 159u) >> 3u);
        new_right = (uint8_t)((ncx + 159u) >> 3u);
        if (new_right != old_right && new_right < active_map_w && stream_col_buf_len < 1u) {
            stream_col_buf[stream_col_buf_len] = new_right;
            stream_col_buf_len++;
        }
    }
    cam_x = ncx;

    /* Snapshot cam_tile_x NOW so flush uses the value from this frame, not the next */
    cam_tile_x_snap = (uint8_t)(cam_x >> 3u);
}

void camera_flush_vram(void) BANKED {
    uint8_t i;
    for (i = 0u; i < stream_row_buf_len; i++) {
        stream_row(stream_row_buf[i]);
    }
    stream_row_buf_len = 0u;
    for (i = 0u; i < stream_col_buf_len; i++) {
        stream_col(stream_col_buf[i]);
    }
    stream_col_buf_len = 0u;
}

void camera_apply_scroll(void) BANKED {
    cam_scy_shadow = (uint8_t)cam_y;
    cam_scx_shadow = (uint8_t)cam_x;
}
