#include <gb/gb.h>
#include "state_overmap.h"
#include "state_playing.h"
#include "state_manager.h"
#include "config.h"
#include "input.h"
#include "player.h"
#include "track.h"

/* ── Tile visual data (2bpp, 4 tiles × 16 bytes = 64 bytes in ROM) ──────── */
/* Color 0 = transparent/bg, color 1 = gray road, color 2 = border, color 3 = filled */
/* 2bpp encoding: each row = 2 bytes [low_plane, high_plane]                 */
/*   color 0: low=0, high=0  |  color 1: low=1, high=0  (0xFF,0x00)         */
/*   color 2: low=0, high=1  (0x00,0xFF)  |  color 3: low=1, high=1 (0xFF,0xFF) */
static const uint8_t overmap_tile_data[64] = {
    /* tile 0: blank — all color 0 */
    0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00,
    0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00,
    /* tile 1: road — horizontal band (rows 2-5 in color 1) */
    0x00,0x00, 0x00,0x00, 0xFF,0x00, 0xFF,0x00,
    0xFF,0x00, 0xFF,0x00, 0x00,0x00, 0x00,0x00,
    /* tile 2: hub — filled color 3 */
    0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF,
    0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF,
    /* tile 3: dest — outline in color 2 */
    0x00,0xFF, 0x00,0x81, 0x00,0x81, 0x00,0x81,
    0x00,0x81, 0x00,0x81, 0x00,0x81, 0x00,0xFF,
};

/* ── Overmap BKG tile map (20×18 = 360 bytes in ROM) ─────────────────────── */
/* All rows are blank except row 8 which has the road, hub, and dest tiles.   */
static const uint8_t overmap_map[OVERMAP_H * OVERMAP_W] = {
    /* rows 0-7: blank (8 × 20 = 160 zeros) */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 0 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 1 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 2 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 3 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 4 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 5 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 6 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 7 */
    /* row 8: blank,blank,dest,road×6,hub,road×7,dest,blank,blank */
    /* tx: 0  1  2                           3  4  5  6  7  8  */
    0, 0,
    OVERMAP_TILE_DEST,
    OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD,
    OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD,
    OVERMAP_TILE_HUB,
    OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD,
    OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD, OVERMAP_TILE_ROAD,
    OVERMAP_TILE_ROAD,
    OVERMAP_TILE_DEST,
    0, 0,
    /* rows 9-17: blank (9 × 20 = 180 zeros) */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 9  */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 10 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 11 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 12 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 13 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 14 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 15 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 16 */
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,  /* row 17 */
};

/* ── State ─────────────────────────────────────────────────────────────────── */
static uint8_t car_tx;
static uint8_t car_ty;
uint8_t current_race_id = 0u;

uint8_t overmap_get_car_tx(void) { return car_tx; }
uint8_t overmap_get_car_ty(void) { return car_ty; }

/* ── Helpers ────────────────────────────────────────────────────────────────── */
static uint8_t overmap_walkable(uint8_t tx, uint8_t ty) {
    return overmap_map[(uint16_t)ty * OVERMAP_W + tx] != OVERMAP_TILE_BLANK;
}

static void overmap_move_sprite(void) {
    /* OAM coords: screen_x = oam_x - 8, screen_y = oam_y - 16 */
    uint8_t sx = (uint8_t)(car_tx * 8u + 8u);
    uint8_t sy = (uint8_t)(car_ty * 8u + 16u);
    move_sprite(0u, sx, sy);
    move_sprite(1u, sx, (uint8_t)(sy + 8u));
}

/* ── State callbacks ─────────────────────────────────────────────────────────── */
static void enter(void) {
    car_tx = OVERMAP_HUB_TX;
    car_ty = OVERMAP_HUB_TY;

    wait_vbl_done();
    DISPLAY_OFF;
    set_bkg_data(0u, 4u, overmap_tile_data);
    set_bkg_tiles(0u, 0u, OVERMAP_W, OVERMAP_H, overmap_map);
    DISPLAY_ON;

    SHOW_BKG;
    SHOW_SPRITES;
    overmap_move_sprite();
}

static void update(void) {
    uint8_t new_tx = car_tx;
    uint8_t new_ty = car_ty;

    if      (KEY_TICKED(J_LEFT)  && car_tx > 0u)             new_tx = car_tx - 1u;
    else if (KEY_TICKED(J_RIGHT) && car_tx < OVERMAP_W - 1u) new_tx = car_tx + 1u;
    else if (KEY_TICKED(J_UP)    && car_ty > 0u)             new_ty = car_ty - 1u;
    else if (KEY_TICKED(J_DOWN)  && car_ty < OVERMAP_H - 1u) new_ty = car_ty + 1u;

    if (new_tx == car_tx && new_ty == car_ty) return;
    if (!overmap_walkable(new_tx, new_ty))    return;

    car_tx = new_tx;
    car_ty = new_ty;
    overmap_move_sprite();

    if (overmap_map[(uint16_t)car_ty * OVERMAP_W + car_tx] == OVERMAP_TILE_DEST) {
        current_race_id = (car_tx < OVERMAP_HUB_TX) ? 0u : 1u;
        player_set_pos(track_start_x, track_start_y);
        player_reset_vel();
        state_replace(&state_playing);
    }
}

static void om_exit(void) {
}

const State state_overmap = { enter, update, om_exit };
