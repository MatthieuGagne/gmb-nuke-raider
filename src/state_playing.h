#ifndef STATE_PLAYING_H
#define STATE_PLAYING_H

#include <stdint.h>
#include "state_manager.h"

BANKREF_EXTERN(state_playing)
extern const State state_playing;

#ifndef __SDCC
/* Test-only seam: pure win-condition logic, no hardware. */
uint8_t finish_eval(uint8_t map_type, uint8_t armed, int8_t pvy, uint8_t cps_cleared);
#endif

#endif
