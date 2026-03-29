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
#include "projectile.h"
#include "lap.h"

static uint8_t finish_armed;   /* 1 = ready to detect finish; 0 = debounced */

static void enter(void) {
    int16_t sx = track_get_start_x();
    int16_t sy = track_get_start_y();
    player_set_pos(sx, sy);
    player_reset_vel();
    damage_init();
    projectile_init();
    lap_init(track_get_lap_count());
    finish_armed = 1u;
    DISPLAY_OFF;
    track_init();
    camera_init(player_get_x(), player_get_y());
    hud_init();
    hud_set_lap(lap_get_current(), lap_get_total());
    camera_apply_scroll();
    player_render();
    DISPLAY_ON;
}

static void update(void) {
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    projectile_render();
    hud_render();
    camera_flush_vram();
    camera_apply_scroll();   /* SCY applied AFTER VRAM is ready */
    /* Game logic phase: runs during active display */
    player_update();
    projectile_update();
    hud_set_hp(damage_get_hp());    /* sync damage HP to HUD each frame */
    camera_update(player_get_x(), player_get_y());
    hud_update();
    /* Death check */
    if (damage_is_dead()) {
        state_replace(&state_game_over);
        return;
    }
    /* Finish line detection:
     * - tile-type check replaces hardcoded Y-row
     * - finish_armed debounces: clears on entry, re-arms on exit
     * - vy > 0 guard: only count when moving downward (prevents AC3 backward crossing) */
    {
        int16_t px = player_get_x();
        int16_t py = player_get_y();
        TileType ct = track_tile_type((int16_t)(px + 4), (int16_t)(py + 4));
        if (ct == TILE_FINISH) {
            if (finish_armed && player_get_vy() > 0) {
                finish_armed = 0u;
                if (lap_advance()) {
                    /* Final lap complete — return to overmap */
                    state_replace(&state_overmap);
                    return;
                }
                /* Lap complete — update HUD; player continues naturally (no teleport) */
                hud_set_lap(lap_get_current(), lap_get_total());
            }
        } else {
            finish_armed = 1u;
        }
    }
}

static void sp_exit(void) {
    HIDE_WIN;
}

const State state_playing = { BANK(state_playing), enter, update, sp_exit };
