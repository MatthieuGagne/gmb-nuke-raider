#include <gb/gb.h>
#include "camera.h"
#include "track.h"

uint8_t cam_x;
uint8_t cam_y;

/* Camera clamp maxima: world px - screen px */
#define CAM_MAX_X  160u   /* MAP_PX_W(320) - SCREEN_W(160) */
#define CAM_MAX_Y  144u   /* MAP_PX_H(288) - SCREEN_H(144) */

/* Write one full world column to VRAM ring buffer.
 * VRAM x slot = world_tx % 32. Handles 36-row world (36 > 32 wraps). */
static void stream_column(uint8_t world_tx) {
    static uint8_t col_buf[MAP_TILES_H];
    uint8_t ty;
    uint8_t vram_x = world_tx & 31u;

    for (ty = 0u; ty < MAP_TILES_H; ty++) {
        col_buf[ty] = track_map[(uint16_t)ty * MAP_TILES_W + world_tx];
    }
    /* Write rows 0..31. Only write the wrapping rows 32..35 into VRAM rows 0..3
     * when the bottom of the viewport actually wraps (cam_y >= 113). */
    if (cam_y >= 113u) {
        /* Viewport wraps: VRAM rows 0-3 must hold world rows 32-35.
         * Write rows 4-31 first (skipping 0-3), then write 0-3 with
         * the wrap data — each VRAM slot written exactly once. */
        set_bkg_tiles(vram_x, 4u, 1u, 28u, &col_buf[4]);
        set_bkg_tiles(vram_x, 0u, 1u, (uint8_t)(MAP_TILES_H - 32u), &col_buf[32]);
    } else {
        set_bkg_tiles(vram_x, 0u, 1u, 32u, col_buf);
    }
}

/* Write one full world row to VRAM ring buffer.
 * VRAM y slot = world_ty % 32. Handles 40-col world (40 > 32 wraps). */
static void stream_row(uint8_t world_ty) {
    static uint8_t row_buf[MAP_TILES_W];
    uint8_t tx;
    uint8_t vram_y = world_ty & 31u;

    for (tx = 0u; tx < MAP_TILES_W; tx++) {
        row_buf[tx] = track_map[(uint16_t)world_ty * MAP_TILES_W + tx];
    }
    /* Write cols 0..31. Only write the wrapping cols 32..39 into VRAM cols 0..7
     * when the right edge of the viewport actually wraps (cam_x >= 97). */
    if (cam_x >= 97u) {
        /* Viewport wraps: VRAM cols 0-7 must hold world cols 32-39.
         * Write cols 8-31 first (skipping 0-7), then write 0-7 with
         * the wrap data — each VRAM slot written exactly once. */
        set_bkg_tiles(8u, vram_y, 24u, 1u, &row_buf[8]);
        set_bkg_tiles(0u, vram_y, (uint8_t)(MAP_TILES_W - 32u), 1u, &row_buf[32]);
    } else {
        set_bkg_tiles(0u, vram_y, 32u, 1u, row_buf);
    }
}

#define STREAM_BUF_SIZE 4u

typedef struct {
    uint8_t index;
    uint8_t is_row;  /* 0 = column, 1 = row */
} StreamEntry;

static StreamEntry stream_buf[STREAM_BUF_SIZE];
static uint8_t     stream_buf_len = 0u;

/* Clamp a signed camera candidate to [0, max]. Returns uint8_t. */
static uint8_t clamp_cam(int16_t v, uint8_t max) {
    if (v < 0) return 0u;
    if ((uint16_t)v > max) return max;
    return (uint8_t)v;
}

void camera_init(int16_t player_world_x, int16_t player_world_y) {
    uint8_t ty;

    /* Set scroll first so stream_row/stream_column use the correct cam position */
    cam_x = clamp_cam(player_world_x - 80, CAM_MAX_X);
    cam_y = clamp_cam(player_world_y - 72, CAM_MAX_Y);

    /* Preload all 36 world rows into VRAM ring buffer */
    for (ty = 0u; ty < MAP_TILES_H; ty++) {
        stream_row(ty);
    }

    move_bkg(cam_x, cam_y);
}

void camera_update(int16_t player_world_x, int16_t player_world_y) {
    uint8_t ncx = clamp_cam(player_world_x - 80, CAM_MAX_X);
    uint8_t ncy = clamp_cam(player_world_y - 72, CAM_MAX_Y);

    /* Buffer right column if right viewport edge crossed a tile boundary */
    {
        uint8_t old_right = (uint8_t)((cam_x + 159u) >> 3u);
        uint8_t new_right = (uint8_t)((ncx  + 159u) >> 3u);
        if (new_right != old_right && new_right < MAP_TILES_W
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_right;
            stream_buf[stream_buf_len].is_row = 0u;
            stream_buf_len++;
        }
    }
    /* Buffer left column if left viewport edge crossed a tile boundary */
    {
        uint8_t old_left = (uint8_t)(cam_x >> 3u);
        uint8_t new_left = (uint8_t)(ncx  >> 3u);
        if (new_left != old_left && new_left < MAP_TILES_W
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_left;
            stream_buf[stream_buf_len].is_row = 0u;
            stream_buf_len++;
        }
    }
    /* Buffer bottom row if bottom viewport edge crossed a tile boundary */
    {
        uint8_t old_bot = (uint8_t)((cam_y + 143u) >> 3u);
        uint8_t new_bot = (uint8_t)((ncy  + 143u) >> 3u);
        if (new_bot != old_bot && new_bot < MAP_TILES_H
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_bot;
            stream_buf[stream_buf_len].is_row = 1u;
            stream_buf_len++;
        }
    }
    /* Buffer top row if top viewport edge crossed a tile boundary */
    {
        uint8_t old_top = (uint8_t)(cam_y >> 3u);
        uint8_t new_top = (uint8_t)(ncy  >> 3u);
        if (new_top != old_top && new_top < MAP_TILES_H
                && stream_buf_len < STREAM_BUF_SIZE) {
            stream_buf[stream_buf_len].index  = new_top;
            stream_buf[stream_buf_len].is_row = 1u;
            stream_buf_len++;
        }
    }

    cam_x = ncx;
    cam_y = ncy;
    /* move_bkg() removed — called from main.c VBlank phase after camera_flush_vram() */
}

void camera_flush_vram(void) {
    uint8_t i;
    for (i = 0u; i < stream_buf_len; i++) {
        if (stream_buf[i].is_row) {
            stream_row(stream_buf[i].index);
        } else {
            stream_column(stream_buf[i].index);
        }
    }
    stream_buf_len = 0u;
}
