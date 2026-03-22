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

static void enter(void) {
    {
        int16_t sx, sy;
        load_track_start_pos(&sx, &sy);
        player_set_pos(sx, sy);
    }
    player_reset_vel();
    damage_init();          /* reset HP pool for new race */
    DISPLAY_OFF;
    track_init();
    camera_init(player_get_x(), player_get_y());
    hud_init();
    camera_apply_scroll();  /* pre-set SCY so first visible frame is correct */
    player_render();        /* pre-set OAM so sprites start in race position  */
    DISPLAY_ON;
}

static void update(void) {
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    hud_render();
    camera_flush_vram();
    camera_apply_scroll();   /* SCY applied AFTER VRAM is ready */
    /* Game logic phase: runs during active display */
    player_update();
    hud_set_hp(damage_get_hp());    /* sync damage HP to HUD each frame */
    camera_update(player_get_x(), player_get_y());
    hud_update();
    /* Death check */
    if (damage_is_dead()) {
        state_replace(&state_game_over);
        return;
    }
    /* Finish line detection — check must be last so physics runs first */
    {
        uint8_t fin_ty = (uint8_t)((uint16_t)player_get_y() >> 3u);
        if (fin_ty == track_finish_line_y) {
            state_replace(&state_overmap);
            return;
        }
    }
}

static void sp_exit(void) {
    HIDE_WIN;
}

const State state_playing = { BANK(state_playing), enter, update, sp_exit };
