#include <gb/gb.h>
#include <gbdk/emu_debug.h>
#include "banking.h"
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
uint8_t current_hub_id  = 0u;

/* Scan-result SoA arrays — populated by overmap_scan_map() in enter() */
static uint8_t overmap_hub_tx[1u];
static uint8_t overmap_hub_ty[1u];
static uint8_t overmap_dest_tx[MAX_OVERMAP_DESTS];
static uint8_t overmap_dest_ty[MAX_OVERMAP_DESTS];
static uint8_t overmap_city_hub_tx[MAX_OVERMAP_HUBS];
static uint8_t overmap_city_hub_ty[MAX_OVERMAP_HUBS];
static uint8_t overmap_dest_count;
static uint8_t overmap_city_hub_count;

#define TRAVEL_FRAMES_PER_TILE 4u   /* file-local tuning — not in config.h */

static uint8_t traveling;           /* 0=idle, 1=animating */
static uint8_t travel_dir;          /* J_LEFT/J_RIGHT/J_UP/J_DOWN bitmask */
static uint8_t travel_frame_count;  /* counts down to 0 before each tile step */
static uint8_t dest_tx;
static uint8_t dest_ty;

uint8_t overmap_get_car_tx(void) { return car_tx; }
uint8_t overmap_get_car_ty(void) { return car_ty; }

/* Must be called inside SET_BANK(overmap_map) on hardware;
 * SET_BANK is a no-op in host tests so direct access is safe. */
static void overmap_scan_map(void) {
    uint8_t tx, ty;
    uint8_t hub_found = 0u;
    overmap_dest_count     = 0u;
    overmap_city_hub_count = 0u;
    for (ty = 0u; ty < OVERMAP_H; ty++) {
        for (tx = 0u; tx < OVERMAP_W; tx++) {
            uint8_t tile = overmap_map[(uint16_t)ty * OVERMAP_W + tx];
            if (tile == OVERMAP_TILE_HUB && !hub_found) {
                overmap_hub_tx[0] = tx;
                overmap_hub_ty[0] = ty;
                hub_found = 1u;
            } else if (tile == OVERMAP_TILE_DEST &&
                       overmap_dest_count < MAX_OVERMAP_DESTS) {
                overmap_dest_tx[overmap_dest_count] = tx;
                overmap_dest_ty[overmap_dest_count] = ty;
                overmap_dest_count++;
            } else if (tile == OVERMAP_TILE_CITY_HUB &&
                       overmap_city_hub_count < MAX_OVERMAP_HUBS) {
                overmap_city_hub_tx[overmap_city_hub_count] = tx;
                overmap_city_hub_ty[overmap_city_hub_count] = ty;
                overmap_city_hub_count++;
            }
        }
    }
}

uint8_t overmap_get_spawn_tx(void) { return overmap_hub_tx[0]; }
uint8_t overmap_get_spawn_ty(void) { return overmap_hub_ty[0]; }

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
    EMU_printf("tile_effect tile=%hu\n", tile);
    if (tile == OVERMAP_TILE_CITY_HUB) {
        uint8_t i;
        traveling = 0u;
        current_hub_id = 0u;
        for (i = 0u; i < overmap_city_hub_count; i++) {
            if (overmap_city_hub_tx[i] == car_tx &&
                overmap_city_hub_ty[i] == car_ty) {
                current_hub_id = i;
                break;
            }
        }
        state_push(&state_hub);
        overmap_hub_entered = 1u;
        return;
    }
    if (tile == OVERMAP_TILE_DEST) {
        uint8_t i;
        traveling = 0u;
        current_race_id = 0u;
        for (i = 0u; i < overmap_dest_count; i++) {
            if (overmap_dest_tx[i] == car_tx &&
                overmap_dest_ty[i] == car_ty) {
                current_race_id = i;
                break;
            }
        }
        player_set_pos(track_start_x, track_start_y);
        player_reset_vel();
        state_replace(&state_playing);
    }
}

/* ── State callbacks ─────────────────────────────────────────────────────────── */
static void enter(void) {
    EMU_printf("OVERMAP enter\n");
    { SET_BANK(overmap_map);
      overmap_scan_map();
      RESTORE_BANK(); }
    car_tx = overmap_hub_tx[0];
    car_ty = overmap_hub_ty[0];
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
            { SET_BANK(overmap_map);
              overmap_check_tile_effect();
              RESTORE_BANK(); }
            return;
        }
        travel_frame_count = TRAVEL_FRAMES_PER_TILE - 1u;
        return;
    }
    { SET_BANK(overmap_map);
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
      RESTORE_BANK(); }
}

static void om_exit(void) {
}

const State state_overmap = { 0, enter, update, om_exit };
