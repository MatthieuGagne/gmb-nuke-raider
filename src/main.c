#include <gb/gb.h>
#include <gb/cgb.h>
#include "input.h"
#include "player.h"
#include "state_manager.h"
#include "state_title.h"

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

void main(void) {
    DISPLAY_OFF;

    init_palettes();
    player_init();

    DISPLAY_ON;

    state_manager_init();
    state_push(&state_title);

    while (1) {
        wait_vbl_done();
        input_update();           /* saves prev frame, reads joypad() */
        state_manager_update();   /* no longer passes raw joypad byte */
    }
}
