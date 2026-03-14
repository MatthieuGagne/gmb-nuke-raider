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

#define TRAVEL_FRAMES_PER_TILE 4u   /* file-local tuning — not in config.h */

static uint8_t traveling;           /* 0=idle, 1=animating */
static uint8_t travel_dir;          /* J_LEFT/J_RIGHT/J_UP/J_DOWN bitmask */
static uint8_t travel_frame_count;  /* counts down to 0 before each tile step */
static uint8_t dest_tx;
static uint8_t dest_ty;

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

static uint8_t find_next_node(int8_t dx, int8_t dy, uint8_t *out_tx, uint8_t *out_ty) {
    int8_t cx = (int8_t)car_tx + dx;
    int8_t cy = (int8_t)car_ty + dy;
    if (cx < 0 || cy < 0 || cx >= (int8_t)OVERMAP_W || cy >= (int8_t)OVERMAP_H)
        return 0u;
    {
        uint8_t ux = (uint8_t)cx;
        uint8_t uy = (uint8_t)cy;
        if (!overmap_walkable(ux, uy)) return 0u;  /* first tile blank -> no move */
    }
    while (cx >= 0 && cy >= 0 && cx < (int8_t)OVERMAP_W && cy < (int8_t)OVERMAP_H) {
        {
            uint8_t ux = (uint8_t)cx;
            uint8_t uy = (uint8_t)cy;
            uint8_t tile = overmap_map[(uint16_t)uy * OVERMAP_W + ux];
            if (tile != OVERMAP_TILE_ROAD) {
                *out_tx = ux; *out_ty = uy;
                return 1u;
            }
        }
        cx += dx; cy += dy;
    }
    return 0u;
}

static void overmap_check_tile_effect(void) {
    uint8_t tile = overmap_map[(uint16_t)car_ty * OVERMAP_W + car_tx];
    if (tile == OVERMAP_TILE_CITY_HUB) {
        traveling = 0u;               /* clear BEFORE state_push — no reset needed on pop */
        state_push(&state_hub);
        overmap_hub_entered = 1u;
        return;
    }
    if (tile == OVERMAP_TILE_DEST) {
        traveling = 0u;
        current_race_id = (car_tx < OVERMAP_HUB_TX) ? 0u : 1u;
        player_set_pos(track_start_x, track_start_y);
        player_reset_vel();
        state_replace(&state_playing);
    }
}

/* ── State callbacks ─────────────────────────────────────────────────────────── */
static void enter(void) {
    car_tx = OVERMAP_HUB_TX;
    car_ty = OVERMAP_HUB_TY;
    traveling = 0u; travel_dir = 0u; travel_frame_count = 0u;
    dest_tx = 0u;   dest_ty = 0u;

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
    if (traveling) {
        if (travel_frame_count > 0u) { travel_frame_count--; return; }
        if      (travel_dir == J_LEFT  && car_tx > 0u)             car_tx--;
        else if (travel_dir == J_RIGHT && car_tx < OVERMAP_W - 1u) car_tx++;
        else if (travel_dir == J_UP    && car_ty > 0u)             car_ty--;
        else if (travel_dir == J_DOWN  && car_ty < OVERMAP_H - 1u) car_ty++;
        overmap_move_sprite();
        if (car_tx == dest_tx && car_ty == dest_ty) {
            traveling = 0u;
            overmap_check_tile_effect();
            return;
        }
        travel_frame_count = TRAVEL_FRAMES_PER_TILE - 1u;
        return;
    }
    if (KEY_TICKED(J_LEFT)) {
        if (find_next_node(-1, 0, &dest_tx, &dest_ty)) {
            traveling = 1u; travel_dir = J_LEFT;
            travel_frame_count = TRAVEL_FRAMES_PER_TILE - 1u;
        }
    } else if (KEY_TICKED(J_RIGHT)) {
        if (find_next_node(1, 0, &dest_tx, &dest_ty)) {
            traveling = 1u; travel_dir = J_RIGHT;
            travel_frame_count = TRAVEL_FRAMES_PER_TILE - 1u;
        }
    } else if (KEY_TICKED(J_UP)) {
        if (find_next_node(0, -1, &dest_tx, &dest_ty)) {
            traveling = 1u; travel_dir = J_UP;
            travel_frame_count = TRAVEL_FRAMES_PER_TILE - 1u;
        }
    } else if (KEY_TICKED(J_DOWN)) {
        if (find_next_node(0, 1, &dest_tx, &dest_ty)) {
            traveling = 1u; travel_dir = J_DOWN;
            travel_frame_count = TRAVEL_FRAMES_PER_TILE - 1u;
        }
    }
}

static void om_exit(void) {
}

const State state_overmap = { enter, update, om_exit };
