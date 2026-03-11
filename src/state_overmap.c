#include <gb/gb.h>
#include "state_overmap.h"
#include "state_playing.h"
#include "state_hub.h"
#include "state_manager.h"
#include "config.h"
#include "input.h"
#include "player.h"
#include "track.h"

/* Tile and map data are generated from Aseprite/Tiled sources.
 * Edit assets/maps/overmap_tiles.aseprite in Aseprite or assets/maps/overmap.tmx
 * in Tiled, then run `make` to regenerate src/overmap_tiles.c and src/overmap_map.c. */

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
    { SET_BANK(overmap_tile_data);
      set_bkg_data(0u, overmap_tile_data_count, overmap_tile_data);
      RESTORE_BANK(); }
    { SET_BANK(overmap_map);
      set_bkg_tiles(0u, 0u, OVERMAP_W, OVERMAP_H, overmap_map);
      RESTORE_BANK(); }
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

    {
        uint8_t tile = overmap_map[(uint16_t)car_ty * OVERMAP_W + car_tx];
        if (tile == OVERMAP_TILE_CITY_HUB) {
            state_push(&state_hub);
            overmap_hub_entered = 1u;  /* set after enter() so hub can clear on re-entry */
            return;
        }
        if (tile == OVERMAP_TILE_DEST) {
            current_race_id = (car_tx < OVERMAP_HUB_TX) ? 0u : 1u;
            player_set_pos(track_start_x, track_start_y);
            player_reset_vel();
            state_replace(&state_playing);
        }
    }
}

static void om_exit(void) {
}

const State state_overmap = { enter, update, om_exit };
