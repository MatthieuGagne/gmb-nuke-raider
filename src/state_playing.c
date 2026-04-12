#pragma bank 255
#include <gb/gb.h>
#include "banking.h"
#include "input.h"
#include "state_manager.h"
#include "state_playing.h"
#include "state_overmap.h"
BANKREF(state_playing)
BANKREF_EXTERN(state_playing)
#include "player.h"
#include "track.h"
#include "camera.h"
#include "hud.h"
#include "loader.h"
#include "damage.h"
#include "state_game_over.h"
#include "state_results.h"
#include "economy.h"
#include "projectile.h"
#include "lap.h"
#include "checkpoint.h"
#include "enemy.h"
#include "powerup.h"

static uint8_t finish_armed;        /* 1 = ready to detect finish; 0 = debounced */
static uint8_t active_map_type_cache; /* cached at enter(); TRACK_TYPE_RACE or TRACK_TYPE_COMBAT */

#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
finish_eval(uint8_t map_type, uint8_t armed, int8_t pvy, uint8_t cps_cleared) {
    if (!armed || pvy <= 0) return 0u;
    if (map_type == TRACK_TYPE_COMBAT) return 1u;
    return cps_cleared;
}

static void enter(void) {
    loader_set_track(track_get_id());
    loader_load_state(k_playing_assets, k_playing_assets_count);
    player_init(loader_get_slot(TILE_ASSET_PLAYER));
    int16_t sx = track_get_start_x();
    int16_t sy = track_get_start_y();
    player_set_pos(sx, sy);
    player_reset_vel();
    damage_init();
    projectile_init(loader_get_slot(TILE_ASSET_BULLET));
    enemy_init();
    powerup_init();
    lap_init(track_get_lap_count());
    active_map_type_cache = track_get_map_type();
    finish_armed = 1u;
    DISPLAY_OFF;
    track_init();
    checkpoint_init(track_get_checkpoints(), track_get_checkpoint_count());
    camera_init(player_get_x(), player_get_y());
    hud_init(track_get_map_type(), track_get_lap_count());
    hud_set_lap(lap_get_current(), lap_get_total());
    camera_apply_scroll();
    player_render();
    DISPLAY_ON;
}

static void update(void) {
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    projectile_render();
    enemy_render();
    powerup_render();
    hud_render();
    camera_flush_vram();
    camera_apply_scroll();   /* SCY applied AFTER VRAM is ready */
    /* Game logic phase: runs during active display */
    player_update();
    /* Hoist position/velocity once — avoids repeated BANKED trampoline calls below */
    {
        int16_t px   = player_get_x();
        int16_t py   = player_get_y();
        int8_t  pvx  = player_get_vx();
        int8_t  pvy  = player_get_vy();
        int16_t y_max;
        TileType ct;
        /* HUD boundary clamp: prevent car from entering HUD zone (screen Y >= HUD_SCANLINE).
         * cam_y is the camera scroll offset; car is 16px tall (2 OAM slots).
         * Cast safety: cam_y in [0,656], max sum = 656+128-16 = 768 < INT16_MAX. */
        y_max = (int16_t)((uint16_t)cam_y + (uint16_t)HUD_SCANLINE - 16u);
        if (py > y_max) {
            py = y_max;
            player_set_pos(px, py);
        }
        /* Checkpoint update — runs after player_update() and HUD clamp */
        checkpoint_update(px, py, pvx, pvy);
        projectile_update();
        enemy_update(px, py);
        powerup_update((uint8_t)((uint16_t)px >> 3u), (uint8_t)((uint16_t)py >> 3u));
        hud_set_hp(damage_get_hp());    /* sync damage HP to HUD each frame */
        camera_update(px, py);
        hud_update();
        /* Death check */
        if (damage_is_dead()) {
            state_replace(&state_game_over, BANK(state_game_over));
            return;
        }
        /* Finish line detection:
         * - tile-type check replaces hardcoded Y-row
         * - finish_armed debounces: clears on entry, re-arms on exit
         * - vy > 0 guard: only count when moving downward (prevents backward crossing)
         * - checkpoint_all_cleared() gate: all CPs must be crossed in order */
        ct = track_tile_type((int16_t)(px + 4), (int16_t)(py + 4));
        if (ct == TILE_FINISH) {
            if (finish_eval(active_map_type_cache, finish_armed, pvy,
                            checkpoint_all_cleared())) {
                finish_armed = 0u;
                if (active_map_type_cache == TRACK_TYPE_COMBAT) {
                    state_pop();
                    return;
                }
                if (lap_advance()) {
                    /* Final lap complete — award scrap and show results */
                    {
                        uint16_t reward = track_get_reward();
                        state_results_set_earned(reward);
                        economy_add_scrap(reward);
                    }
                    state_replace(&state_results, BANK(state_results));
                    return;
                }
                /* Lap complete — reset checkpoints for next lap, update HUD */
                checkpoint_reset();
                hud_set_lap(lap_get_current(), lap_get_total());
            }
        } else {
            finish_armed = 1u;
        }
    }
}

static void sp_exit(void) {
    loader_unload_state();
    HIDE_WIN;
    cam_scx_shadow = 0u;
    cam_scy_shadow = 0u;
}

const State state_playing = { BANK(state_playing), enter, update, sp_exit };
