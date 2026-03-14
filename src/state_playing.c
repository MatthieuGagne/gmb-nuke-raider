#pragma bank 255
#include <gb/gb.h>
#include "input.h"
#include "state_manager.h"
#include "state_playing.h"
#include "state_overmap.h"
#include "player.h"
#include "track.h"
#include "camera.h"
#include "hud.h"

static void enter(void) {
    player_set_pos(track_start_x, track_start_y);
    player_reset_vel();
    DISPLAY_OFF;
    track_init();
    camera_init(player_get_x(), player_get_y());
    hud_init();
    DISPLAY_ON;
}

static void update(void) {
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    hud_render();
    camera_flush_vram();
    /* Game logic phase: runs during active display */
    player_update();
    camera_update(player_get_x(), player_get_y());
    hud_update();
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

const State state_playing = { enter, update, sp_exit };
