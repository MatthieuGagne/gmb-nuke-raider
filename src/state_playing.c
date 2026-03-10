#include <gb/gb.h>
#include "input.h"
#include "state_manager.h"
#include "state_playing.h"
#include "player.h"
#include "track.h"
#include "camera.h"
#include "debug.h"

#ifdef DEBUG
static uint16_t frame_count = 0u;
#endif

static void enter(void) {
    DISPLAY_OFF;
    track_init();
    camera_init(player_get_x(), player_get_y());
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
    /* VBlank phase: all VRAM writes immediately after wait_vbl_done() */
    player_render();
    camera_flush_vram();
    /* SCY is 8-bit and wraps at 256. Truncation is correct: stream_row() places
     * world row ty at VRAM row (ty & 31), so (uint8_t)cam_y correctly indexes
     * the ring buffer. */
    move_bkg(0u, (uint8_t)cam_y);
    /* Game logic phase: runs during active display */
    player_update();
    camera_update(player_get_x(), player_get_y());
}

static void sp_exit(void) {
}

const State state_playing = { enter, update, sp_exit };
