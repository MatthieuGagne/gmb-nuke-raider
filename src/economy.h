#ifndef ECONOMY_H
#define ECONOMY_H

#include <gb/gb.h>
#include <stdint.h>

/* Economy module — tracks the player's scrap balance.
 * All functions are BANKED (autobank 255). */

void     economy_init(void) BANKED;
void     economy_add_scrap(uint16_t amount) BANKED;
uint8_t  economy_spend_scrap(uint16_t amount) BANKED; /* returns 1 on success, 0 if insufficient */
uint16_t economy_get_scrap(void) BANKED;

#endif /* ECONOMY_H */
