#pragma bank 255
#include <gb/gb.h>
#include <gbdk/emu_debug.h>
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

static void enter(void) {
    EMU_printf("PLAYING enter\n");
    player_set_pos(track_start_x, track_start_y);
    EMU_printf("PLAYING pos set\n");
    player_reset_vel();
    DISPLAY_OFF;
    track_init();
    EMU_printf("PLAYING track_init done\n");
    camera_init(player_get_x(), player_get_y());
    EMU_printf("PLAYING camera_init done\n");
    hud_init();
    DISPLAY_ON;
    EMU_printf("PLAYING enter done\n");
}

static void update(void) {
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    hud_render();
    camera_flush_vram();
    camera_apply_scroll();   /* SCY applied AFTER VRAM is ready */
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

const State state_playing = { BANK(state_playing), enter, update, sp_exit };
