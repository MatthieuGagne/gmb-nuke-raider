#include <gb/gb.h>
#include <gb/cgb.h>
#include "camera.h"
#include "config.h"
#include "input.h"
#include "player.h"
#include "state_manager.h"
#include "state_title.h"
#include "music.h"

uint8_t input     = 0;
uint8_t prev_input = 0;

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

static volatile uint8_t frame_ready = 0;

static void vbl_isr(void) {
    frame_ready = 1;
    move_bkg(0, (uint8_t)cam_y);
    /* music_tick removed — no SET_BANK/SWITCH_ROM in ISR */
}

void main(void) {
    DISPLAY_OFF;

    init_palettes();
    player_init();
    music_init();
    add_VBL(vbl_isr);
    set_interrupts(VBL_IFLAG);

    DISPLAY_ON;

    state_manager_init();
    state_push(&state_title);

    while (1) {
        while (!frame_ready);
        frame_ready = 0;
        music_tick();             /* once per VBL, safely in main context */
        input_update();           /* saves prev frame, reads joypad() */
        state_manager_update();   /* no longer passes raw joypad byte */
    }
}
