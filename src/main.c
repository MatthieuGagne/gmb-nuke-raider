#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "player.h"
#include "track.h"
#include "camera.h"

typedef enum {
    STATE_INIT,
    STATE_TITLE,
    STATE_PLAYING,
    STATE_GAME_OVER
} GameState;

static GameState state = STATE_INIT;

static const uint16_t bkg_pal[] = {
    RGB(31, 31, 31),
    RGB(20, 20, 20),
    RGB(10, 10, 10),
    RGB(0,  0,  0)
};
static const uint16_t spr_pal[] = {
    RGB(31, 31, 31),
    RGB(20, 20, 20),
    RGB(10, 10, 10),
    RGB(0,  0,  0)
};

static void init_palettes(void) {
    if (_cpu == CGB_TYPE) {
        set_bkg_palette(0, 1, bkg_pal);
        set_sprite_palette(0, 1, spr_pal);
    }
}

static void show_title(void) {
    cls();
    gotoxy(2, 6);
    printf("WASTELAND RACER");
    gotoxy(3, 10);
    printf("Press START");
    state = STATE_TITLE;
}

void main(void) {
    DISPLAY_OFF;

    init_palettes();
    player_init();

    DISPLAY_ON;

    show_title();

    while (1) {
        wait_vbl_done();

        switch (state) {
            case STATE_TITLE:
                if (joypad() & J_START) {
                    track_init();
                    camera_init(player_get_x(), player_get_y());
                    state = STATE_PLAYING;
                }
                break;

            case STATE_PLAYING:
                /* VBlank phase: all VRAM writes immediately after wait_vbl_done() */
                player_render();
                camera_flush_vram();
                move_bkg(cam_x, cam_y);
                /* Game logic phase: runs during active display */
                player_update(joypad());
                camera_update(player_get_x(), player_get_y());
                break;

            case STATE_GAME_OVER:
                break;

            default:
                break;
        }
    }
}
