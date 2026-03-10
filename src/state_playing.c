#include <gb/gb.h>
#include "input.h"
#include "state_manager.h"
#include "state_playing.h"
#include "player.h"
#include "track.h"
#include "camera.h"
#include "hud.h"
#include "debug.h"

#ifdef DEBUG
static uint16_t frame_count = 0u;
#endif

static void enter(void) {
    DISPLAY_OFF;
    track_init();
    camera_init(player_get_x(), player_get_y());
    hud_init();
    DISPLAY_ON;
}

static void update(void) {
#ifdef DEBUG
    frame_count++;
    if (frame_count % 60u == 0u) {
        DBG_INT("frame", (int)frame_count);
        DBG_INT("px", (int)player_get_x());
        DBG_INT("py", (int)player_get_y());
    }
#endif
    /* VBlank phase: all VRAM writes immediately after frame_ready */
    player_render();
    hud_render();
    camera_flush_vram();
    /* Game logic phase: runs during active display */
    player_update();
    camera_update(player_get_x(), player_get_y());
    hud_update();
}

static void sp_exit(void) {
}

const State state_playing = { enter, update, sp_exit };
