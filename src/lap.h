#ifndef LAP_H
#define LAP_H

#include <gb/gb.h>
#include <stdint.h>

/* Lap state module — tracks current lap progress for a race.
 * All functions are BANKED (autobank 255). */

void    lap_init(uint8_t total) BANKED;     /* call in state_playing enter() */
uint8_t lap_get_current(void) BANKED;       /* 1-based current lap number */
uint8_t lap_get_total(void) BANKED;
uint8_t lap_advance(void) BANKED;           /* returns 1 when race complete, 0 otherwise */

#endif /* LAP_H */
