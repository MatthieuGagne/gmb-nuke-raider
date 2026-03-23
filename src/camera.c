#pragma bank 255
#include <gb/gb.h>
#include "camera.h"
#include "track.h"

volatile uint16_t cam_y;
volatile uint8_t  cam_scy_shadow;

/* CAM_MAX_Y = (MAP_TILES_H * 8) - 144 = (100*8) - 144 = 656 */
#define CAM_MAX_Y  656u

/* Write one full world row into the VRAM ring buffer.
 * VRAM y slot = world_ty % 32. MAP_TILES_W=20 <= 32: no X wrapping needed.
 * track_get_raw_tile() is BANKED — the trampoline handles bank switching safely.
 * Direct access to track_map[] is forbidden here (camera.c and track_map.c may
 * be in different autobanks). */
static void stream_row(uint8_t world_ty) {
    static uint8_t row_buf[MAP_TILES_W];
    uint8_t tx;
    uint8_t vram_y = world_ty & 31u;

    for (tx = 0u; tx < MAP_TILES_W; tx++) {
        row_buf[tx] = track_get_raw_tile(tx, world_ty);
    }
    set_bkg_tiles(0u, vram_y, MAP_TILES_W, 1u, row_buf);
}

#define STREAM_BUF_SIZE 6u

static uint8_t stream_buf[STREAM_BUF_SIZE];
static uint8_t stream_buf_len = 0u;

/* Clamp signed v to [0, max]. */
static uint16_t clamp_cam(int16_t v, uint16_t max) {
    if (v < 0) return 0u;
    if ((uint16_t)v > max) return max;  /* safe: v >= 0 guaranteed by prior guard */
    return (uint16_t)v;
}

void camera_init(int16_t player_world_x, int16_t player_world_y) BANKED {
    uint8_t ty;
    uint8_t first_row;
    (void)player_world_x;  /* cam_x is always 0; no horizontal scroll */

    stream_buf_len = 0u;
    cam_y = clamp_cam(player_world_y - 72, CAM_MAX_Y);
    first_row = (uint8_t)(cam_y >> 3u);

    /* Preload only the 18 initially visible rows, not all 100 */
    for (ty = first_row; ty < first_row + 18u && ty < MAP_TILES_H; ty++) {
        stream_row(ty);
    }

}

void camera_update(int16_t player_world_x, int16_t player_world_y) BANKED {
    uint16_t ncy;
    uint8_t old_top, new_top;
    uint8_t old_bot, new_bot;
    (void)player_world_x;

    ncy = clamp_cam(player_world_y - 72, CAM_MAX_Y);

    if (ncy < cam_y) {
        /* Scrolling UP: buffer new top row when viewport top crosses tile boundary */
        old_top = (uint8_t)(cam_y >> 3u);
        new_top = (uint8_t)(ncy >> 3u);
        if (new_top != old_top && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len] = new_top;
            stream_buf_len++;
        }
    } else if (ncy > cam_y) {
        /* Scrolling DOWN: buffer new bottom row when viewport bottom crosses tile boundary */
        old_bot = (uint8_t)((cam_y + 143u) >> 3u);   /* 143 = 144px viewport - 1 */
        new_bot = (uint8_t)((ncy + 143u) >> 3u);
        if (new_bot != old_bot && new_bot < MAP_TILES_H && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len] = new_bot;
            stream_buf_len++;
        }
    }

    cam_y = ncy;
}

void camera_flush_vram(void) BANKED {
    uint8_t i;
    for (i = 0u; i < stream_buf_len; i++) {
        stream_row(stream_buf[i]);
    }
    stream_buf_len = 0u;
}

void camera_apply_scroll(void) BANKED {
    cam_scy_shadow = (uint8_t)cam_y;
}
