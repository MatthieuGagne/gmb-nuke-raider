#pragma bank 255
#include <gb/gb.h>
#include "race_state.h"

static uint8_t rs_cp_next[MAX_RACERS];
static uint8_t rs_laps[MAX_RACERS];
static uint8_t rs_active[MAX_RACERS];
static uint8_t rs_lap_total;

void    race_state_init(uint8_t lap_total) BANKED { (void)lap_total; }
void    race_state_set_active(uint8_t slot, uint8_t active) BANKED { (void)slot; (void)active; }
void    race_state_update_cp(uint8_t slot, int16_t x, int16_t y, uint8_t dir) BANKED {
    (void)slot; (void)x; (void)y; (void)dir;
}
uint8_t race_state_advance_lap(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_get_cp(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_get_laps(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_get_lap_total(void) BANKED { return 0u; }
uint8_t race_state_all_cp_cleared(uint8_t slot) BANKED { (void)slot; return 0u; }
uint8_t race_state_rank_player(void) BANKED { return 1u; }

#ifndef __SDCC
void race_state_set_laps_for_test(uint8_t slot, uint8_t n) { (void)slot; (void)n; }
void race_state_set_cp_for_test(uint8_t slot, uint8_t n) { (void)slot; (void)n; }
/* NOTE: pos_from_dir and pos_from_manhattan are defined in state_playing.c for
 * the red phase. They will migrate here in the green phase (Task 5) when
 * state_playing.c's definitions are removed. Do not define them here yet or the
 * host-test link will see duplicate symbols. */
#endif
