#ifndef STATE_HUB_H
#define STATE_HUB_H

#include <gb/gb.h>
#include "state_manager.h"

BANKREF_EXTERN(state_hub)
extern const State state_hub;

/* Set to 1 by state_overmap when hub tile is entered.
 * Reset to 0 by state_hub.enter(). Testability hook. */
extern uint8_t overmap_hub_entered;

uint8_t hub_get_cursor(void);
uint8_t hub_get_sub_state(void);

/* Exposed for unit testing — do not call from outside state_hub.c in production */
uint8_t render_wrapped(const char *text, uint8_t start_col, uint8_t start_row,
                        uint8_t width, uint8_t max_rows, uint8_t start_char);

#endif /* STATE_HUB_H */
