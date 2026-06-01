#ifndef STATE_PLAYING_H
#define STATE_PLAYING_H

#include <stdint.h>
#include "state_manager.h"
#include "player.h"

BANKREF_EXTERN(state_playing)
extern const State state_playing;

#ifndef __SDCC
/* Test-only seam: pure win-condition logic, no hardware. */
uint8_t finish_eval(uint8_t map_type, uint8_t armed,
                    uint8_t pdir,
                    uint8_t finish_dir,
                    uint8_t cps_cleared);
/* Test-only seam: pure countdown phase-advance logic, no hardware.
 * Returns next phase (unchanged if frames < threshold, phase+1 if reached). */
uint8_t cd_advance(uint8_t phase, uint8_t frames);
/* Test-only seam: direction-aware position comparison.
 * Returns 1 = player ahead, 2 = racer ahead. */
uint8_t pos_from_dir(uint8_t dir,
                     int16_t px,  int16_t py,
                     int16_t rpx, int16_t rpy);
#endif

#endif
