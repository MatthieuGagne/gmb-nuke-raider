/* music.c — hUGEDriver wrapper.
 *
 * IMPORTANT: This file intentionally omits #pragma bank 255.
 * music_tick() calls SET_BANK (inline SWITCH_ROM). If this code were in a
 * switched bank, SWITCH_ROM would remap the CPU's own instructions out from
 * under itself -> undefined behavior. Keep this file in bank 0.
 */
#include <gb/gb.h>
#include <gb/hardware.h>
#include "banking.h"
#include "hUGEDriver.h"
#include "music_data.h"
#include "music.h"

void music_init(void) {
    NR52_REG = 0x80;  /* enable APU */
    NR51_REG = 0xFF;  /* route all channels to both speakers */
    NR50_REG = 0x77;  /* max master volume */
    __critical {
        { SET_BANK(music_data_song);
          hUGE_init(&music_data_song);
          RESTORE_BANK(); }
    }
}

void music_tick(void) {
    { SET_BANK(music_data_song);
      hUGE_dosound();
      RESTORE_BANK(); }
}
