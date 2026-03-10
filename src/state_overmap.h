#ifndef STATE_OVERMAP_H
#define STATE_OVERMAP_H

#include <stdint.h>
#include "state_manager.h"

extern const State state_overmap;
extern uint8_t current_race_id;

/* Accessors used by unit tests */
uint8_t overmap_get_car_tx(void);
uint8_t overmap_get_car_ty(void);

#endif /* STATE_OVERMAP_H */
