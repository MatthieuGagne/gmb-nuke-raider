#pragma bank 255
#include <gb/gb.h>
#include "input.h"
#include "state_manager.h"
#include "state_playing.h"
#include "state_overmap.h"
#include "state_game_over.h"
#include "player.h"
#include "track.h"
#include "camera.h"
#include "hud.h"
#include "damage.h"

static void enter(void) {
    { int16_t sx, sy;
      SET_BANK(track_start_x);
      sx = track_start_x; sy = track_start_y;
      RESTORE_BANK();
      player_set_pos(sx, sy); }
    player_reset_vel();
    DISPLAY_OFF;
    track_init();
    camera_init(player_get_x(), player_get_y());
    hud_init();
    damage_init();
    DISPLAY_ON;
}

static void update(void) {
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    hud_render();
    camera_flush_vram();
    /* Game logic phase: runs during active display */
    damage_tick();           /* decrement invincibility BEFORE player moves */
    player_update();         /* may call damage_apply() on wall hit */
    if (damage_is_dead()) {
        state_replace(&state_game_over);
        return;
    }
    hud_set_hp(damage_get_hp());
    camera_update(player_get_x(), player_get_y());
    hud_update();
    /* Finish line detection — check must be last so physics runs first */
    {
        uint8_t fin_ty = (uint8_t)((uint16_t)player_get_y() >> 3u);
        uint8_t fly;
        { SET_BANK(track_finish_line_y);
          fly = track_finish_line_y;
          RESTORE_BANK(); }
        if (fin_ty == fly) {
            state_replace(&state_overmap);
            return;
        }
    }
}

static void sp_exit(void) {
    HIDE_WIN;
}

const State state_playing = { enter, update, sp_exit };
