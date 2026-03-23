#pragma bank 255
#include "lap.h"

static uint8_t lap_current;   /* 1-based: starts at 1, max = lap_total */
static uint8_t lap_total;

void lap_init(uint8_t total) BANKED {
    lap_total   = total;
    lap_current = 1u;
}

uint8_t lap_get_current(void) BANKED { return lap_current; }
uint8_t lap_get_total(void)   BANKED { return lap_total;   }

uint8_t lap_advance(void) BANKED {
    if (lap_current >= lap_total) {
        return 1u;  /* race complete */
    }
    lap_current = (uint8_t)(lap_current + 1u);
    return 0u;
}
