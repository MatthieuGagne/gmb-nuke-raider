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
    /* Write rows 0..31 in one call, then rows 32..35 wrap to VRAM rows 0..3 */
    set_bkg_tiles(vram_x, 0u, 1u, 32u, col_buf);
    set_bkg_tiles(vram_x, 0u, 1u, (uint8_t)(MAP_TILES_H - 32u), &col_buf[32]);
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
    /* Write cols 0..31 in one call, then cols 32..39 wrap to VRAM cols 0..7 */
    set_bkg_tiles(0u, vram_y, 32u, 1u, row_buf);
    set_bkg_tiles(0u, vram_y, (uint8_t)(MAP_TILES_W - 32u), 1u, &row_buf[32]);
}

/* Clamp a signed camera candidate to [0, max]. Returns uint8_t. */
static uint8_t clamp_cam(int16_t v, uint8_t max) {
    if (v < 0) return 0u;
    if ((uint16_t)v > max) return max;
    return (uint8_t)v;
}

void camera_init(int16_t player_world_x, int16_t player_world_y) {
    uint8_t ty;

    /* Preload all 36 world rows into VRAM ring buffer */
    for (ty = 0u; ty < MAP_TILES_H; ty++) {
        stream_row(ty);
    }

    /* Set initial scroll centered on player */
    cam_x = clamp_cam(player_world_x - 80, CAM_MAX_X);
    cam_y = clamp_cam(player_world_y - 72, CAM_MAX_Y);
    move_bkg(cam_x, cam_y);
}

void camera_update(int16_t player_world_x, int16_t player_world_y) {
    uint8_t ncx = clamp_cam(player_world_x - 80, CAM_MAX_X);
    uint8_t ncy = clamp_cam(player_world_y - 72, CAM_MAX_Y);

    /* Stream right column if right viewport edge crossed a tile boundary */
    {
        uint8_t old_right = (uint8_t)((cam_x + 159u) >> 3u);
        uint8_t new_right = (uint8_t)((ncx  + 159u) >> 3u);
        if (new_right != old_right && new_right < MAP_TILES_W) {
            stream_column(new_right);
        }
    }
    /* Stream left column if left viewport edge crossed a tile boundary */
    {
        uint8_t old_left = (uint8_t)(cam_x >> 3u);
        uint8_t new_left = (uint8_t)(ncx  >> 3u);
        if (new_left != old_left && new_left < MAP_TILES_W) {
            stream_column(new_left);
        }
    }
    /* Stream bottom row if bottom viewport edge crossed a tile boundary */
    {
        uint8_t old_bot = (uint8_t)((cam_y + 143u) >> 3u);
        uint8_t new_bot = (uint8_t)((ncy  + 143u) >> 3u);
        if (new_bot != old_bot && new_bot < MAP_TILES_H) {
            stream_row(new_bot);
        }
    }
    /* Stream top row if top viewport edge crossed a tile boundary */
    {
        uint8_t old_top = (uint8_t)(cam_y >> 3u);
        uint8_t new_top = (uint8_t)(ncy  >> 3u);
        if (new_top != old_top && new_top < MAP_TILES_H) {
            stream_row(new_top);
        }
    }

    cam_x = ncx;
    cam_y = ncy;
    move_bkg(cam_x, cam_y);
}
