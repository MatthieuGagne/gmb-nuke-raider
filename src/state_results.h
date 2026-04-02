#ifndef STATE_RESULTS_H
#define STATE_RESULTS_H

#include <stdint.h>
#include "state_manager.h"

extern const State state_results;

void state_results_set_earned(uint16_t amount) BANKED;

#endif /* STATE_RESULTS_H */
