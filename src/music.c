/* music.c — hUGEDriver wrapper.
 *
 * IMPORTANT: This file intentionally omits #pragma bank 255.
 * music_tick() calls SWITCH_ROM. If this code were in a switched bank,
 * SWITCH_ROM would remap the CPU's own instructions out from under itself
 * -> undefined behavior. Keep this file in bank 0.
 *
 * With multiple tracks in different autobanks, current_song_bank stores
 * which bank the active track lives in so music_tick() can SET_BANK correctly.
 */
#include <gb/gb.h>
#include <gb/hardware.h>
#include "banking.h"
#include "hUGEDriver.h"
#include "music_data.h"
#include "music.h"

static uint8_t current_song_bank = 0;

void music_init(void) {
    NR52_REG = 0x80;  /* enable APU */
    NR51_REG = 0xFF;  /* route all channels to both speakers */
    NR50_REG = 0x77;  /* max master volume */
    current_song_bank = BANK(music_data_song);
    __critical {
        { SET_BANK(music_data_song);
          hUGE_init(&music_data_song);
          RESTORE_BANK(); }
    }
}

void music_start(uint8_t bank, const hUGESong_t *song) {
    current_song_bank = bank;
    __critical {
        uint8_t _saved_bank = CURRENT_BANK;
        SWITCH_ROM(bank);
        hUGE_init(song);
        SWITCH_ROM(_saved_bank);
    }
}

void music_tick(void) {
    __critical {
        uint8_t _saved_bank = CURRENT_BANK;
        SWITCH_ROM(current_song_bank);
        hUGE_dosound();
        SWITCH_ROM(_saved_bank);
    }
}

void vbl_sync(void) {
    while (!frame_ready);
    frame_ready = 0;
    music_tick();
}

void vbl_display_off(void) {
    while (!frame_ready);      /* wait for VBlank start */
    frame_ready = 0;
    music_tick();              /* tick music for this VBlank */
    LCDC_REG &= ~0x80U;       /* disable LCD — safe: we're in VBlank */
}
